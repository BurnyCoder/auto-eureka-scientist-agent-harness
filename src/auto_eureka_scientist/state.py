"""Transactional local progress and receipts, independently of provider conversations.

SQLite transactions: https://docs.python.org/3/library/sqlite3.html
"""
from pathlib import Path
import json
import sqlite3
import threading
import uuid

import psutil

from .config import RunConfig
from .util import now


class Store:
    def __init__(self, project: Path):
        self.project = project
        directory = project / '.eureka'
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(directory / 'state.sqlite3', timeout=30, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY, created TEXT, updated TEXT, config TEXT, task TEXT, policy_hash TEXT,
              status TEXT, cycle INTEGER DEFAULT 1, phase_index INTEGER DEFAULT 0,
              calls INTEGER DEFAULT 0, elapsed REAL DEFAULT 0, stop INTEGER DEFAULT 0,
              owner_pid INTEGER DEFAULT 0, owner_start REAL DEFAULT 0, message TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS attempts (
              id INTEGER PRIMARY KEY, run_id TEXT, cycle INTEGER, phase TEXT, started TEXT,
              ended TEXT, status TEXT, prompt TEXT, result TEXT);
            CREATE TABLE IF NOT EXISTS phases (
              run_id TEXT, cycle INTEGER, name TEXT, result TEXT, artifacts TEXT, completed TEXT,
              PRIMARY KEY(run_id,cycle,name));
            CREATE TABLE IF NOT EXISTS receipts (
              run_id TEXT, key TEXT, value TEXT, updated TEXT, PRIMARY KEY(run_id,key));
            CREATE TABLE IF NOT EXISTS cycles (number INTEGER PRIMARY KEY, run_id TEXT);
        ''')
        # Preserve ownership when opening databases created before cycle allocation.
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO cycles SELECT cycle,run_id FROM phases')
            self.db.execute('INSERT OR IGNORE INTO cycles SELECT cycle,run_id FROM attempts')
            self.db.execute('INSERT OR IGNORE INTO cycles SELECT cycle,id FROM runs')

    def reserve_cycle(self, run_id: str) -> int:
        """Reserve a project-wide number inside the caller's write transaction.

        Existing directories also count, including public clones without SQLite.
        https://www.sqlite.org/lang_transaction.html#deferred_immediate_and_exclusive_transactions
        """
        directories = [int(path.name) for path in (self.project/'cycles').glob('*')
                       if path.is_dir() and path.name.isdigit()]
        recorded = self.db.execute('SELECT COALESCE(MAX(number),0) FROM cycles').fetchone()[0]
        number = max([recorded,*directories])+1
        self.db.execute('INSERT INTO cycles VALUES(?,?)',(number,run_id))
        return number

    def create(self, config: RunConfig, task: str, policy_hash: str) -> str:
        run_id = uuid.uuid4().hex[:12]
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            cycle = self.reserve_cycle(run_id)
            self.db.execute('INSERT INTO runs(id,created,updated,config,task,policy_hash,status,cycle) VALUES(?,?,?,?,?,?,?,?)',
                            (run_id, now(), now(), json.dumps(config.to_dict()), task, policy_hash, 'ready',cycle))
        return run_id

    def advance_cycle(self, run_id: str, *, message=''):
        """Keep earlier observations and reservations when continuing research."""
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.get(run_id)
            number = self.reserve_cycle(run_id)
            self.update(run_id,cycle=number,phase_index=0,message=message)

    def get(self, run_id: str | None = None, *, cycle: int | None = None) -> dict:
        with self.lock:
            if run_id:
                row = self.db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
            elif cycle is not None:
                row = self.db.execute('SELECT runs.* FROM runs JOIN cycles ON runs.id=cycles.run_id WHERE cycles.number=?',
                                      (cycle,)).fetchone()
            else:
                row = self.db.execute('SELECT * FROM runs ORDER BY created DESC,rowid DESC LIMIT 1').fetchone()
            if row is None:
                raise ValueError('No matching run. Use eureka run first.')
            value = dict(row)
            value['config'] = json.loads(value['config'])
            value['cycles_started'] = self.db.execute('SELECT COUNT(*) FROM cycles WHERE run_id=?',(value['id'],)).fetchone()[0]
        return value

    def update(self, run_id, **values):
        allowed = {'status','cycle','phase_index','elapsed','stop','owner_pid','owner_start','message','config'}
        if not values or not set(values) <= allowed:
            raise ValueError('Invalid run update')
        values = {**values, 'updated': now()}
        if 'config' in values:
            values['config'] = json.dumps(values['config'])
        with self.lock, self.db:
            self.db.execute('UPDATE runs SET '+','.join(f'{key}=?' for key in values)+' WHERE id=?',
                            (*values.values(),run_id))

    def acquire(self, run_id: str):
        """Serialize project writers; PID creation time rejects recycled owners."""
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.get(run_id)
            for row in self.db.execute('SELECT owner_pid,owner_start FROM runs WHERE owner_pid<>0'):
                try:
                    if abs(psutil.Process(row['owner_pid']).create_time()-row['owner_start']) < .01:
                        raise RuntimeError('This project already has a live controller')
                except psutil.NoSuchProcess:
                    pass
            process = psutil.Process()
            self.update(run_id, owner_pid=process.pid, owner_start=process.create_time(), status='running', stop=0, message='')

    def reconfigure(self, run_id: str, config: RunConfig):
        """Record explicit resume changes without resetting calls, time or earlier outcomes."""
        with self.lock, self.db:
            run = self.get(run_id)
            updated = config.to_dict()
            if run['config'] != updated:
                history = self.receipt(run_id,'configuration_history') or {'changes':[]}
                history['changes'].append({'at':now(),'previous':run['config'],'updated':updated,
                    'calls':run['calls'],'active_seconds':run['elapsed'],'previous_status':run['status']})
                self.receipt(run_id,'configuration_history',history)
                self.update(run_id,config=updated)

    def begin_attempt(self, run_id: str, phase: str, prompt: str) -> int:
        with self.lock, self.db:
            run = self.get(run_id)
            limit = run['config']['max_calls']
            if limit is not None and run['calls'] >= limit:
                raise RuntimeError('call budget exhausted')
            cursor = self.db.execute('INSERT INTO attempts(run_id,cycle,phase,started,status,prompt) VALUES(?,?,?,?,?,?)',
                                     (run_id,run['cycle'],phase,now(),'running',prompt))
            self.db.execute('UPDATE runs SET calls=calls+1 WHERE id=?', (run_id,))
            return cursor.lastrowid

    def finish_attempt(self, attempt: int, status: str, result: dict):
        with self.lock, self.db:
            self.db.execute('UPDATE attempts SET ended=?,status=?,result=? WHERE id=?',
                            (now(),status,json.dumps(result,ensure_ascii=False),attempt))

    def complete_phase(self, run_id, name, result, artifacts):
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO phases VALUES(?,?,?,?,?,?)',
                            (run_id,self.get(run_id)['cycle'],name,json.dumps(result),json.dumps(artifacts),now()))

    def phases(self, run_id, cycle=None):
        with self.lock:
            rows = self.db.execute('SELECT * FROM phases WHERE run_id=? AND cycle=? ORDER BY completed',
                                   (run_id,cycle or self.get(run_id)['cycle'])).fetchall()
        return [{**dict(row),'result':json.loads(row['result']),'artifacts':json.loads(row['artifacts'])} for row in rows]

    def attempts(self, run_id):
        with self.lock:
            return [dict(row) for row in self.db.execute('SELECT * FROM attempts WHERE run_id=? ORDER BY id',(run_id,))]

    def receipt(self, run_id: str, key: str, value: dict | None = None):
        with self.lock, self.db:
            if value is not None:
                self.db.execute('INSERT OR REPLACE INTO receipts VALUES(?,?,?,?)', (run_id,key,json.dumps(value),now()))
            row = self.db.execute('SELECT value FROM receipts WHERE run_id=? AND key=?',(run_id,key)).fetchone()
        return json.loads(row['value']) if row else None

    def close(self):
        self.db.close()

