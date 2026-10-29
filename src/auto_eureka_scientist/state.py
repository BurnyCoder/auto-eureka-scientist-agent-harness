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
        ''')

    def create(self, config: RunConfig, task: str, policy_hash: str) -> str:
        run_id = uuid.uuid4().hex[:12]
        with self.lock, self.db:
            self.db.execute('INSERT INTO runs(id,created,updated,config,task,policy_hash,status) VALUES(?,?,?,?,?,?,?)',
                            (run_id, now(), now(), json.dumps(config.to_dict()), task, policy_hash, 'ready'))
        return run_id

    def get(self, run_id: str | None = None) -> dict:
        with self.lock:
            row = self.db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone() if run_id else (
                self.db.execute('SELECT * FROM runs ORDER BY created DESC LIMIT 1').fetchone())
        if row is None:
            raise ValueError('No matching run. Use eureka run first.')
        value = dict(row)
        value['config'] = json.loads(value['config'])
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
        """Use PID plus creation time so a recycled PID cannot impersonate an owner."""
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.get(run_id)
            try:
                if row['owner_pid'] and abs(psutil.Process(row['owner_pid']).create_time()-row['owner_start']) < .01:
                    raise RuntimeError('This run already has a live controller')
            except psutil.NoSuchProcess:
                pass
            process = psutil.Process()
            self.update(run_id, owner_pid=process.pid, owner_start=process.create_time(), status='running', stop=0)

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

