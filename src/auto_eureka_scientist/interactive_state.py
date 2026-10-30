"""Durable operator records, separate from scientific handoffs and raw transcripts.

Transactions and write serialization: https://www.sqlite.org/lang_transaction.html
All mutating requests have persistent identities; browsers are observers, not owners.
"""
import hashlib
import json
import random
import uuid

from .settings import schema, validate
from .util import now


class InteractiveState:
    def migrate_interactive(self):
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, at TEXT, type TEXT, data TEXT);
            CREATE INDEX IF NOT EXISTS events_run ON events(run_id,id);
            CREATE TABLE IF NOT EXISTS actions (
              id TEXT PRIMARY KEY, run_id TEXT, kind TEXT, payload TEXT, status TEXT, at TEXT, result TEXT);
            CREATE TABLE IF NOT EXISTS messages (
              id TEXT PRIMARY KEY, run_id TEXT, cycle INTEGER, kind TEXT, scope TEXT, text TEXT,
              status TEXT, at TEXT, attempt INTEGER, answer TEXT);
            CREATE INDEX IF NOT EXISTS messages_run ON messages(run_id,status);
            CREATE INDEX IF NOT EXISTS actions_run ON actions(run_id,status);
            CREATE INDEX IF NOT EXISTS attempts_run ON attempts(run_id,cycle,phase);
            CREATE TABLE IF NOT EXISTS specs (
              id TEXT PRIMARY KEY, run_id TEXT, position INTEGER, revision INTEGER, value TEXT);
            CREATE TABLE IF NOT EXISTS spec_history (
              id TEXT, revision INTEGER, at TEXT, value TEXT, PRIMARY KEY(id,revision));
            CREATE TABLE IF NOT EXISTS cycle_specs (
              run_id TEXT, cycle INTEGER, value TEXT, PRIMARY KEY(run_id,cycle));
            CREATE TABLE IF NOT EXISTS cycle_outcomes (
              run_id TEXT, cycle INTEGER, status TEXT, at TEXT, PRIMARY KEY(run_id,cycle));
            CREATE TABLE IF NOT EXISTS queue_state (
              run_id TEXT PRIMARY KEY, remaining TEXT, pass INTEGER DEFAULT 0, misses INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS settings_changes (
              id INTEGER PRIMARY KEY, run_id TEXT, at TEXT, revision INTEGER, patch TEXT,
              previous TEXT, timing TEXT, calls INTEGER, elapsed REAL);
        ''')
        if 'revision' not in {r[1] for r in self.db.execute('PRAGMA table_info(runs)')}:
            self.db.execute('ALTER TABLE runs ADD COLUMN revision INTEGER DEFAULT 0')
        # Only terminal legacy runs are imported as completed, never unfinished phase sets.
        if version<1:
            self.db.execute("INSERT OR IGNORE INTO cycle_outcomes SELECT id,cycle,'complete',updated FROM runs WHERE status='complete'")
            self.db.execute('PRAGMA user_version=1')
        self.db.commit()

    def event(self, run_id, kind, data):
        with self.lock, self.db:
            cursor = self.db.execute('INSERT INTO events(run_id,at,type,data) VALUES(?,?,?,?)',
                                     (run_id,now(),kind,json.dumps(data,ensure_ascii=False)))
            return cursor.lastrowid

    def events(self, run_id, *, after=0, before=None, limit=200):
        with self.lock:
            if before is not None:
                rows = list(reversed(self.db.execute('SELECT * FROM events WHERE run_id=? AND id<? ORDER BY id DESC LIMIT ?',
                    (run_id,before,min(max(limit,1),2000))).fetchall()))
            else:
                rows = self.db.execute('SELECT * FROM events WHERE run_id=? AND id>? ORDER BY id LIMIT ?',
                    (run_id,after,min(max(limit,1),2000))).fetchall()
        return [{**dict(r),'data':json.loads(r['data'])} for r in rows]

    def list_runs(self):
        with self.lock:
            ids = [r[0] for r in self.db.execute('SELECT id FROM runs ORDER BY created DESC,rowid DESC')]
        return [self.get(identifier) for identifier in ids]

    def set_specs(self, run_id, entries):
        """Replace the future queue; immutable active-cycle snapshots are independent."""
        if not isinstance(entries,list): raise ValueError('Specs must be a list')
        allowed = {k for k,v in schema()['properties'].items() if v['x-scope']=='cycle'}
        normalized, identifiers = [], set()
        for index, entry in enumerate(entries):
            if not isinstance(entry,dict) or not isinstance(entry.get('text'),str) or not entry['text'].strip():
                raise ValueError('Each spec needs nonempty text')
            overrides = entry.get('settings',{})
            parameters=entry.get('parameters',{})
            if not isinstance(parameters,dict): raise ValueError('Research parameters must be a JSON object')
            validate(overrides,partial=True)
            if set(overrides)-allowed: raise ValueError('Spec overrides must be cycle-scoped settings')
            identifier = entry.get('id') or uuid.uuid4().hex[:12]
            if identifier in identifiers: raise ValueError('Duplicate spec identity; duplicate with a new ID')
            identifiers.add(identifier)
            normalized.append({'id':identifier,'title':str(entry.get('title') or f'Spec {index+1}'),
                'text':entry['text'],'enabled':bool(entry.get('enabled',True)), 'settings':overrides,'parameters':parameters})
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            run = self.get(run_id)
            for entry in normalized:
                foreign = self.db.execute('SELECT run_id FROM specs WHERE id=?',(entry['id'],)).fetchone()
                if foreign and foreign[0]!=run_id: raise ValueError('Spec belongs to another run')
                prior = self.db.execute('SELECT COALESCE(MAX(revision),0) FROM spec_history WHERE id=?',(entry['id'],)).fetchone()[0]
                supplied=next((e.get('revision') for e in entries if e.get('id')==entry['id']),None)
                if supplied is not None and supplied!=prior: raise ValueError('Spec revision conflict; refresh the queue')
                entry['revision'] = prior+1
            self.db.execute('DELETE FROM specs WHERE run_id=?',(run_id,))
            for index, entry in enumerate(normalized):
                value = json.dumps(entry,ensure_ascii=False)
                self.db.execute('INSERT INTO specs VALUES(?,?,?,?,?)',(entry['id'],run_id,index,entry['revision'],value))
                self.db.execute('INSERT INTO spec_history VALUES(?,?,?,?)',(entry['id'],entry['revision'],now(),value))
            active = self.db.execute('SELECT value FROM cycle_specs WHERE run_id=? AND cycle=?',(run_id,run['cycle'])).fetchone()
            active_id = json.loads(active[0])['id'] if active else None
            pending = [e['id'] for e in normalized if e['enabled'] and e['id']!=active_id]
            self.db.execute('INSERT INTO queue_state(run_id,remaining) VALUES(?,?) ON CONFLICT(run_id) DO UPDATE SET remaining=excluded.remaining',
                            (run_id,json.dumps(pending)))
            self.db.execute('INSERT OR REPLACE INTO receipts VALUES(?,?,?,?)',(run_id,'queue_initialized','{}',now()))
        self.event(run_id,'queue.updated',{'specs':[{'id':e['id'],'revision':e['revision'],'title':e['title']} for e in normalized]})
        return normalized

    def specs(self, run_id):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute('SELECT value FROM specs WHERE run_id=? ORDER BY position',(run_id,))]

    def active_spec(self, run_id):
        run = self.get(run_id)
        with self.lock:
            saved = self.db.execute('SELECT value FROM cycle_specs WHERE run_id=? AND cycle=?',(run_id,run['cycle'])).fetchone()
        if saved: return json.loads(saved[0])
        # Legacy CLI runs have a single implicit spec and require no queue migration.
        entries = self.specs(run_id)
        if not entries and self.receipt(run_id,'queue_initialized') is None:
            entries = self.set_specs(run_id,[{'title':'Research spec','text':run['task']}])
            self.receipt(run_id,'queue_initialized',{'at':now()})
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            saved = self.db.execute('SELECT value FROM cycle_specs WHERE run_id=? AND cycle=?',(run_id,run['cycle'])).fetchone()
            if saved: return json.loads(saved[0])
            enabled = {e['id']:e for e in entries if e['enabled']}
            if not enabled: return None
            state = self.db.execute('SELECT * FROM queue_state WHERE run_id=?',(run_id,)).fetchone()
            pending = [key for key in json.loads(state['remaining']) if key in enabled] if state else []
            passes = state['pass'] if state else 0
            # Seeded order is persisted before any inference; a resumed run never reshuffles it.
            if not pending or (passes==0 and not self.db.execute('SELECT 1 FROM cycle_specs WHERE run_id=?',(run_id,)).fetchone()):
                pending = list(enabled)
                if run['config'].get('queue_order')=='shuffle':
                    random.Random(run['config'].get('queue_seed',0)+passes).shuffle(pending)
                if passes==0:
                    start=run['config'].get('queue_start',0)%len(pending)
                    pending=pending[start:]+pending[:start]
                passes+=1
            selected = enabled[pending.pop(0)]
            selected = {**selected,'sha256':hashlib.sha256(selected['text'].encode()).hexdigest()}
            self.db.execute('INSERT INTO cycle_specs VALUES(?,?,?)',(run_id,run['cycle'],json.dumps(selected,ensure_ascii=False)))
            self.db.execute('INSERT INTO queue_state(run_id,remaining,pass) VALUES(?,?,?) ON CONFLICT(run_id) DO UPDATE SET remaining=excluded.remaining,pass=excluded.pass',
                            (run_id,json.dumps(pending),passes))
        self.event(run_id,'spec.selected',selected)
        return selected

    def finish_cycle(self, run_id, status, *, advance=False, carry=False):
        """The completion marker is the idempotency boundary before advancing cycles."""
        if status not in ('complete','skipped','revised'): raise ValueError('Invalid cycle outcome')
        with self.lock,self.db:
            self.db.execute('BEGIN IMMEDIATE')
            run=self.get(run_id)
            cursor=self.db.execute('INSERT OR IGNORE INTO cycle_outcomes VALUES(?,?,?,?)',(run_id,run['cycle'],status,now()))
            if cursor.rowcount:
                if status=='complete': self.db.execute('UPDATE queue_state SET misses=0 WHERE run_id=?',(run_id,))
                elif status=='skipped': self.db.execute('UPDATE queue_state SET misses=misses+1 WHERE run_id=?',(run_id,))
            if advance:
                self.db.execute('INSERT OR REPLACE INTO receipts VALUES(?,?,?,?)',
                    (run_id,'next-cycle',json.dumps({'from_cycle':run['cycle'],'carry':carry}),now()))
        if cursor.rowcount: self.event(run_id,'cycle.'+status,{'cycle':run['cycle']})

    def no_progress(self,run_id):
        with self.lock:
            row=self.db.execute('SELECT misses FROM queue_state WHERE run_id=?',(run_id,)).fetchone()
        count=sum(e['enabled'] for e in self.specs(run_id))
        return bool(row and row[0]>=max(1,count)*self.get(run_id)['config'].get('no_progress_passes',1))

    def enqueue_action(self, run_id, kind, payload=None, request_id=None):
        payload=payload or {}
        identifier=request_id or uuid.uuid4().hex
        self.get(run_id)
        with self.lock,self.db:
            existing=self.db.execute('SELECT * FROM actions WHERE id=?',(identifier,)).fetchone()
            if existing:
                if existing['run_id']!=run_id or existing['kind']!=kind or json.loads(existing['payload'])!=payload:
                    raise ValueError('Action identity already used for another request')
                return dict(existing)
            self.db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?)',(identifier,run_id,kind,json.dumps(payload),'queued',now(),'{}'))
        self.event(run_id,'control.queued',{'id':identifier,'kind':kind})
        return {'id':identifier,'kind':kind,'status':'queued'}

    def actions(self,run_id, *, pending=True, limit=None):
        with self.lock:
            query='SELECT * FROM actions WHERE run_id=? '+("AND status='queued' " if pending else '')+'ORDER BY rowid'
            rows=self.db.execute(query+(' DESC LIMIT ?' if limit is not None else ''),(run_id,limit) if limit is not None else (run_id,)).fetchall()
            if limit is not None: rows=list(reversed(rows))
        return [{**dict(r),'payload':json.loads(r['payload']),'result':json.loads(r['result'])} for r in rows]

    def finish_action(self,identifier, *, error=''):
        with self.lock,self.db:
            row=self.db.execute('SELECT run_id,kind FROM actions WHERE id=?',(identifier,)).fetchone()
            self.db.execute('UPDATE actions SET status=?,result=? WHERE id=?',('failed' if error else 'applied',json.dumps({'error':error}),identifier))
        self.event(row[0],'control.failed' if error else 'control.applied',{'id':identifier,'kind':row[1],'error':error})

    def add_message(self,run_id,text, *, kind='steer',scope='next_invocation',request_id=None):
        if kind not in ('ask','steer') or scope not in ('next_invocation','cycle','run') or not text.strip():
            raise ValueError('Invalid message')
        identifier=request_id or uuid.uuid4().hex
        run=self.get(run_id)
        with self.lock,self.db:
            row=self.db.execute('SELECT * FROM messages WHERE id=?',(identifier,)).fetchone()
            if row:
                if row['run_id']!=run_id or row['text']!=text or row['kind']!=kind or row['scope']!=scope:
                    raise ValueError('Message identity already used')
                return dict(row)
            self.db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,NULL,NULL)',
                (identifier,run_id,run['cycle'],kind,scope,text,'queued',now()))
        self.event(run_id,'message.queued',{'id':identifier,'kind':kind,'text':text,'scope':scope})
        return {'id':identifier,'status':'queued','kind':kind}

    def messages(self,run_id, *, limit=None):
        with self.lock:
            if limit is not None:
                return list(reversed([dict(r) for r in self.db.execute('SELECT * FROM messages WHERE run_id=? ORDER BY at DESC,rowid DESC LIMIT ?',(run_id,limit))]))
            return [dict(r) for r in self.db.execute('SELECT * FROM messages WHERE run_id=? ORDER BY at,rowid',(run_id,))]

    def deliver_question(self, identifier, attempt):
        with self.lock,self.db:
            self.db.execute("UPDATE messages SET status='delivered',attempt=? WHERE id=?",(attempt,identifier))

    def steering(self,run_id):
        run=self.get(run_id)
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM messages WHERE run_id=? AND kind='steer' AND (status='queued' OR scope='run' OR (scope='cycle' AND cycle=?)) ORDER BY rowid",(run_id,run['cycle']))]

    def questions(self,run_id):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM messages WHERE run_id=? AND kind='ask' AND status IN ('queued','delivered') ORDER BY rowid",(run_id,))]

    def deliver_messages(self,run_id,attempt):
        identifiers=[m['id'] for m in self.steering(run_id) if m['status']=='queued']
        with self.lock,self.db:
            for identifier in identifiers:
                self.db.execute("UPDATE messages SET status='delivered',attempt=? WHERE id=?",(attempt,identifier))
        if identifiers: self.event(run_id,'message.delivered',{'ids':identifiers,'attempt':attempt})

    def answer_message(self,identifier,answer,attempt, *, failed=False):
        with self.lock,self.db:
            row=self.db.execute('SELECT run_id FROM messages WHERE id=?',(identifier,)).fetchone()
            self.db.execute('UPDATE messages SET status=?,answer=?,attempt=? WHERE id=?',('failed' if failed else 'answered',answer,attempt,identifier))
        self.event(row[0],'message.failed' if failed else 'message.answered',{'id':identifier,'text':answer,'attempt':attempt})

    def patch_settings(self,run_id,patch, *, expected_revision=None):
        from .config import RunConfig
        validate(patch,partial=True)
        with self.lock,self.db:
            self.db.execute('BEGIN IMMEDIATE')
            run=self.get(run_id)
            if expected_revision is not None and expected_revision!=run['revision']:
                raise ValueError('Settings revision conflict; refresh before applying changes')
            changed={k:v for k,v in patch.items() if run['config'].get(k)!=v}
            for key in changed:
                if schema()['properties'][key]['x-apply']=='new run': raise ValueError(f'{key} requires a new run')
            updated=RunConfig(**{**run['config'],**changed}).to_dict()
            revision=run['revision']+1
            timing={k:schema()['properties'][k]['x-apply'] for k in changed}
            self.db.execute('INSERT INTO settings_changes(run_id,at,revision,patch,previous,timing,calls,elapsed) VALUES(?,?,?,?,?,?,?,?)',
                (run_id,now(),revision,json.dumps(changed),json.dumps(run['config']),json.dumps(timing),run['calls'],run['elapsed']))
            self.db.execute('UPDATE runs SET config=?,revision=? WHERE id=?',(json.dumps(updated),revision,run_id))
        self.event(run_id,'settings.changed',{'revision':revision,'patch':changed,'timing':timing})
        return self.get(run_id)
