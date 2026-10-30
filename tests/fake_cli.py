"""Offline wire-format fixture: writes artifacts, never contacts a model or service."""
import json
from pathlib import Path
import re
import sys

from auto_eureka_scientist.phases import DELIVERABLES
from auto_eureka_scientist.policy import requirements
from auto_eureka_scientist.util import now, read_json, write_json

prompt = sys.stdin.read()
if (Path.cwd()/'fixture-delay').exists():
    import time
    print(json.dumps({'type':'fixture.progress','text':'Offline invocation started'}),flush=True)
    time.sleep(float((Path.cwd()/'fixture-delay').read_text()))
if '--- HARNESS CHAT QUESTION ---' in prompt:
    value={'reply':'Recorded phase explained by an offline fixture.','references':[]}
    if '--codex-fixture' in sys.argv:
        print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}),flush=True)
        print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':10}}),flush=True)
    else:
        print(json.dumps({'type':'result','structured_output':value,'model':'claude-haiku-fixture'}),flush=True)
    raise SystemExit(0)
phase = re.search(r'Current phase: (\w+)\.',prompt).group(1)
root = Path.cwd()
cycle = root/re.search(r'All phase artifact paths below are relative to (cycles/\d+)\.',prompt).group(1)
if (root/'transient-once').exists():
    (root/'transient-once').unlink()
    print(json.dumps({'type':'error','error':'503 temporarily unavailable'}),flush=True)
    raise SystemExit(0)
for name in DELIVERABLES[phase]:
    if name.endswith('.md'):
        (cycle/name).write_text('Offline fixture: negative and inconclusive outcomes are retained.\n',encoding='utf-8')
if phase=='research':
    write_json(cycle/'research/sources.json',[{'id':'source','url':'https://example.com','summary':'Fixture only'}])
if phase=='preregister':
    write_json(cycle/'research/protocol.json',{'analysis_kind':'exploratory','question':'Can the fixture complete?',
               'objective':'Observe recovery','measurements':['completion'],'analysis_plan':'Keep failures',
               'data_boundaries':'No held-out data claimed','budget':'offline'})
if phase=='core':
    failing = (root/'check-fails-once').exists()
    (root/'check-fails-once').unlink(missing_ok=True)
    check = 'raise SystemExit(1)' if failing else 'print("checks passed")'
    write_json(cycle/'research/checks.json',{'command':[sys.executable,'-c',check],'cwd':'cycle'})
if phase in ('pilot','experiments'):
    registration = read_json(cycle/'research/registration.json')
    write_json(cycle/f'results/{phase}.json',{'id':phase,'method':'fixture','outcome':'negative',
               'analysis_kind':'exploratory','started_at':now(),'protocol_sha256':registration['protocol_sha256']})
if phase=='analysis':
    write_json(cycle/'research/claims.json',[{'id':'negative','text':'The fixture recorded a negative outcome',
               'analysis_kind':'exploratory','evidence':['experiments'],'limitations':'Offline fixture only'}])
    write_json(cycle/'research/requirements.json',[{**r,'status':'not_applicable','reason':'Offline test fixture',
                                                  'evidence':[]} for r in requirements()])
decision = 'finish' if phase=='publish' else 'continue'
revisit = ''
if phase=='review' and (root/'revisit-once').exists():
    (root/'revisit-once').unlink()
    decision,revisit = 'revisit','experiments'
if phase=='review' and (root/'revisit-hypothesis-once').exists():
    (root/'revisit-hypothesis-once').unlink()
    decision,revisit = 'revisit','research'
result = {'status':'complete','summary':f'Fixture {phase}','artifacts':[(cycle/p).relative_to(root).as_posix() for p in DELIVERABLES[phase]],
          'evidence':[],'issues':[],'stage':'exploration','analysis_kind':'exploratory','objective':'Test recovery',
          'predictions':['No inference needed to recover a publication'],'alternatives':['A duplicate call is a bug'],
          'observations':['See durable fixture artifacts'],'learning':'Negative outcomes can complete',
          'rationale':'Exercise controller boundaries','decision':decision,'revisit_phase':revisit,
          'not_applicable':[{'requirement':'model_uploads','reason':'No model trained in this offline fixture'}]}
if '--codex-fixture' in sys.argv:
    print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(result)}}),flush=True)
else:
    print(json.dumps({'type':'result','structured_output':result,'model':'claude-haiku-fixture'}),flush=True)
