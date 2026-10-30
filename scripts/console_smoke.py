"""Run the preregistered bounded Haiku or Luna question through the real owned worker.

Run only after committing/pushing console-validation-preregistration.md and core.
Outputs are transport observations, never scientific findings or model rankings.
"""
import argparse
import json
from pathlib import Path
import time

from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.policy import policy_hash
from auto_eureka_scientist.util import now,read_json,write_json
from auto_eureka_scientist.web.service import Service
from auto_eureka_scientist.workspace import initialize


def run(backend):
    root=Path(__file__).resolve().parents[1]
    model={'claude':'haiku','codex':'gpt-6-luna'}[backend]
    project=root/'tmp'/('console-live-'+model)
    initialize(project,task='Prospective console Q&A transport smoke; no experiments.')
    service=Service(project)
    config=RunConfig(str(project),backend,model=model,publish=False,max_calls=2,max_minutes=5,
        repair_retries=0,transport_retries=0,invocation_timeout=120,gpu_monitor=False,open_browser=False)
    identifier=service.store.create(config,'Explain recorded harness state without changing artifacts.',policy_hash())
    question=service.store.add_message(identifier,
        'From the supplied recorded state only: which research phase is next, how many phases have been accepted, '
        'and does answering this question complete a research phase? Reply concisely. Do not execute tools, change files, or run experiments.',kind='ask')
    before=service.store.get(identifier)
    try:
        service.launch(identifier,maintenance=True)
        deadline=time.monotonic()+310
        while service.workers[identifier].poll() is None and time.monotonic()<deadline:time.sleep(.2)
        if service.workers[identifier].poll() is None:
            service.store.update(identifier,stop=1)
            service.workers[identifier].wait(timeout=10)
        after=service.store.get(identifier)
        message=next(m for m in service.store.messages(identifier) if m['id']==question['id'])
        attempts=service.store.attempts(identifier)
        audits=[json.loads(a['result'] or '{}') for a in attempts]
        record={'at':now(),'run_id':identifier,'model':model,'backend':backend,'status':message['status'],
            'calls':after['calls'],'phase_before':before['phase_index'],'phase_after':after['phase_index'],
            'accepted_phases':len(service.store.phases(identifier)),'active_seconds':after['elapsed'],
            'reported_models':sorted({m for audit in audits for m in audit.get('models',[])}),
            'usage':[audit.get('usage',{}) for audit in audits],
            'errors':[error for audit in audits for error in audit.get('errors',[])],
            'reply':message.get('answer'),'run_status':after['status'],'run_message':after['message']}
        path=root/'reports/console-acceptance.json'
        document=read_json(path) if path.exists() else {'browser':[],'live':[]}
        document.setdefault('live',[]).append(record)
        write_json(path,document)
        print(json.dumps(record,ensure_ascii=False,indent=2),flush=True)
        return 0 if message['status']=='answered' and after['calls']==1 and after['phase_index']==before['phase_index'] else 2
    finally:service.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=['claude','codex'],required=True)
    raise SystemExit(run(parser.parse_args().backend))
