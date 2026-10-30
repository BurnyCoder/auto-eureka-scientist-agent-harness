"""Local worker ownership, telemetry and read models for the HTTP interface.

Owned-process identity follows https://psutil.readthedocs.io/en/latest/#process-class
The worker keeps running if a browser disconnects; shutdown only targets its own PIDs.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil

from ..config import RunConfig
from ..execution import terminate_tree
from ..state import Store
from ..util import command, now


class Service:
    def __init__(self,project):
        self.project=Path(project).resolve()
        self.store=Store(self.project)
        self.lock=threading.RLock()
        self.workers={}
        self.readers=[]
        self.worker_command=[sys.executable,'-m','auto_eureka_scientist.cli','_worker']
        self.telemetry_cache=(0,{})
        self.processes={}

    def alive(self,run):
        worker=self.workers.get(run['id'])
        if worker and worker.poll() is None: return True
        try:
            return bool(run['owner_pid'] and abs(psutil.Process(run['owner_pid']).create_time()-run['owner_start'])<.01)
        except (psutil.NoSuchProcess,psutil.AccessDenied): return False

    def launch(self,run_id, *, maintenance=False, allow_complete=False):
        with self.lock:
            run=self.store.get(run_id)
            if self.alive(run): return
            if not maintenance and not allow_complete and run['status']=='complete': raise ValueError('Completed run: start a new run or request a revised cycle for further research')
            for other in self.store.list_runs():
                if self.alive(other): raise ValueError('This project already has a live controller')
            argv=[*self.worker_command,'--project',str(self.project),'--run-id',run_id]
            if maintenance: argv.append('--maintenance')
            env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
            worker=subprocess.Popen(argv,cwd=self.project,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            self.workers[run_id]=worker
            def drain():
                logs=self.project/'.eureka'/run_id
                logs.mkdir(parents=True,exist_ok=True)
                with (logs/'controller.log').open('ab') as stream:
                    while chunk:=worker.stdout.read1(65536):
                        stream.write(chunk); stream.flush()
                        print(chunk.decode('utf-8',errors='replace'),end='',flush=True)
                worker.wait()
            reader=threading.Thread(target=drain,daemon=True)
            reader.start(); self.readers.append(reader)

    def telemetry(self,config,run):
        checked,data=self.telemetry_cache
        if time.monotonic()-checked<config.telemetry_seconds: return data
        data={'at':now(),'process':None,'machine_gpus':None}
        if config.cpu_monitor and self.alive(run) and run['owner_pid']:
            try:
                root=psutil.Process(run['owner_pid'])
                cpu=0; memory=0
                for process in [root,*root.children(recursive=True)]:
                    identity=(process.pid,process.create_time())
                    previous=self.processes.setdefault(identity,process)
                    cpu+=previous.cpu_percent(); memory+=previous.memory_info().rss
                data['process']={'cpu_percent':cpu,'ram_bytes':memory,'pid':root.pid}
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
        if config.gpu_monitor:
            try:
                raw=command(['nvidia-smi','--query-gpu=name,utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],self.project,timeout=2)
                data['machine_gpus']=[dict(zip(('name','utilization_percent','used_mib','total_mib'),[p.strip() for p in line.split(',')])) for line in raw.splitlines()]
            except (OSError,RuntimeError,TimeoutError): pass
        self.telemetry_cache=(time.monotonic(),data)
        return data

    def snapshot(self,run_id):
        run=self.store.get(run_id)
        config=RunConfig(**run['config'])
        attempts=self.store.attempts(run_id,limit=config.history_page_size)
        for attempt in attempts:
            result=json.loads(attempt['result'] or '{}')
            attempt['result']=result
        with self.store.lock:
            cost=self.store.db.execute("SELECT SUM(json_extract(result,'$.usage.reported_cost_usd')) FROM attempts WHERE run_id=?",(run_id,)).fetchone()[0]
            active=self.store.db.execute('SELECT value FROM cycle_specs WHERE run_id=? AND cycle=?',(run_id,run['cycle'])).fetchone()
            latest=self.store.db.execute('SELECT COALESCE(MAX(id),0) FROM events WHERE run_id=?',(run_id,)).fetchone()[0]
            changes=[dict(r) for r in self.store.db.execute('SELECT * FROM settings_changes WHERE run_id=? ORDER BY id',(run_id,))]
            receipts=[{'key':r[0],'value':json.loads(r[1])} for r in self.store.db.execute(
                "SELECT key,value FROM receipts WHERE run_id=? AND (key LIKE 'github:%' OR key LIKE 'hf:%' OR key IN ('repository','pages'))",(run_id,))]
        return {'run':run,'worker_alive':self.alive(run),'specs':self.store.specs(run_id),
            'active_spec':json.loads(active[0]) if active else None,'phases':self.store.phases(run_id),
            'attempts':attempts,'messages':self.store.messages(run_id,limit=config.history_page_size),'actions':self.store.actions(run_id,pending=False,limit=config.history_page_size),
            'effective_settings':self.store.receipt(run_id,'effective_settings') or run['config'],
            'settings_changes':changes,'event_cursor':latest,'telemetry':self.telemetry(config,run),
            'reported_cost_usd':cost,'publications':receipts}

    def action(self,run_id,kind,payload,request_id):
        valid={'pause','stop','interrupt','skip','new_cycle','step','pause_after_phase','stop_after_cycle',
               'revisit','verify','render','resume','retry','publication'}
        if kind not in valid: raise ValueError('Unknown action')
        with self.lock:
            result=self.store.enqueue_action(run_id,kind,payload,request_id)
            if result['status']!='queued': return result
            run=self.store.get(run_id)
            if not self.alive(run):
                if kind in ('pause','stop'):
                    self.store.update(run_id,status='paused' if kind=='pause' else 'stopped',message='Operator '+kind)
                    self.store.finish_action(result['id'])
                else:
                    self.launch(run_id,maintenance=kind in ('verify','render'),allow_complete=kind=='new_cycle')
            return result

    def safe_file(self,relative):
        path=(self.project/relative).resolve()
        if not path.is_relative_to(self.project): raise ValueError('Path is outside this project')
        parts=path.relative_to(self.project).parts
        if any(p.casefold() in ('.git','.eureka','.venv','node_modules') or p.casefold().startswith('.env') for p in parts) or path.suffix.casefold() in ('.key','.pem','.sqlite3'):
            raise ValueError('Private runtime or credential path is not an artifact')
        if not path.is_file(): raise ValueError('Artifact not found')
        return path

    def artifacts(self,run_id):
        run=self.store.get(run_id)
        cycle=self.project/'cycles'/f'{run["cycle"]:03d}'
        paths=list(cycle.rglob('*')) if cycle.exists() else []
        paths.extend(self.project/'reports'/f'run-{run_id}.json' for _ in [0])
        result=[]
        for path in paths:
            if not path.is_file(): continue
            try: checked=self.safe_file(path.relative_to(self.project))
            except ValueError: continue
            result.append({'path':checked.relative_to(self.project).as_posix(),'bytes':checked.stat().st_size})
        return result

    def close(self):
        for run_id,worker in self.workers.items():
            if worker.poll() is None:
                self.store.update(run_id,stop=1)
                try: worker.wait(timeout=5)
                except subprocess.TimeoutExpired: terminate_tree(worker.pid)
        for reader in self.readers: reader.join(timeout=2)
        self.store.close()
