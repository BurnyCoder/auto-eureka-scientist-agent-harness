"""Regressions for observable gaps found in the second plan audit; no live calls."""
import json
from pathlib import Path

import pytest

from auto_eureka_scientist.adapters import Response, model_error, parse_response
from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.publication import Publisher
from auto_eureka_scientist.science import verify_results, verify_claims
from auto_eureka_scientist.state import Store
from auto_eureka_scientist.util import digest, write_json
from auto_eureka_scientist.workspace import initialize, prepare_cycle
from auto_eureka_scientist.science import resolve_artifact
from auto_eureka_scientist.cli import configuration, parser


def test_new_authorized_models_remain_pinned(tmp_path):
    for backend,model,resolved in [('claude','sonnet','claude-sonnet-fixture'),('codex','gpt-6.1-sol','gpt-6.1-sol')]:
        config = RunConfig(str(tmp_path),backend,model=model,profile='digits-replication')
        assert (config.max_minutes,config.max_calls)==(60,20)
        assert not model_error(config,Response(models=[resolved]))
        assert model_error(config,Response(models=['claude-haiku-fixture' if backend=='claude' else 'gpt-6-luna']))
    exact = RunConfig(str(tmp_path),'claude',model='claude-haiku-5-4',profile='digits')
    assert model_error(exact,Response(models=['claude-haiku-5-5']))


def test_replication_is_not_new_confirmatory_evidence(tmp_path):
    initialize(tmp_path,profile='digits-replication')
    cycle = prepare_cycle(tmp_path,1,'digits-replication',{'max_minutes':180,'max_calls':60})
    protocol = json.loads((cycle/'research/protocol.json').read_text())
    assert protocol['analysis_kind']=='exploratory'
    assert protocol['measurements'] and protocol['prior_results_known']
    assert protocol['seeds']==[0,1,2] and protocol['epochs']==50
    assert '180 active minutes' in protocol['budget']


def test_nullable_provider_events_do_not_crash_parser(tmp_path):
    (tmp_path/'stdout.jsonl').write_text(json.dumps({'type':'item.completed','item':None})+'\n'+
        json.dumps({'type':'result','structured_output':{'status':'complete'}})+'\n')
    assert parse_response('claude',tmp_path).value=={'status':'complete'}


def test_model_upload_receipt_tracks_file_content(tmp_path,monkeypatch):
    store = Store(tmp_path)
    config = RunConfig(str(tmp_path),'claude',owner='fixture')
    run_id = store.create(config,'offline','policy')
    cycle = tmp_path/'cycles/001'
    write_json(cycle/'reports/metrics.json',{'same_metric':True})
    (cycle/'models').mkdir()
    weights = cycle/'models/weights.npz'
    weights.write_bytes(b'first weights')
    pub = Publisher(config,store,run_id,lambda:30)
    uploads = []
    def call(args,check=True):
        if args[:2]==['hf','upload']:
            uploads.append(args)
            return json.dumps({'url':'https://example.com/commit'})
        if args[:3]==['hf','collections','create']:
            return json.dumps({'slug':'fixture/collection'})
        return json.dumps({'exists':True})
    monkeypatch.setattr(pub,'call',call)
    pub.models(cycle,'pilot')
    pub.models(cycle,'pilot')
    weights.write_bytes(b'changed weights, same predictions')
    pub.models(cycle,'pilot')
    assert len(uploads)==2
    store.close()


def test_failed_pr_check_prevents_merge(tmp_path,monkeypatch):
    store = Store(tmp_path)
    config = RunConfig(str(tmp_path),'claude')
    run_id = store.create(config,'offline','policy')
    pub = Publisher(config,store,run_id,lambda:30)
    monkeypatch.setattr(pub,'bootstrap',lambda:{'base':'main','url':'https://example.com/repo'})
    monkeypatch.setattr('auto_eureka_scientist.publication.commit',lambda *args:'head-sha')
    commands = []
    def call(args,check=True):
        commands.append(args)
        if args[:2]==['git','branch']: return 'feature'
        if args[:3]==['gh','pr','list']: return json.dumps([{'number':1,'state':'OPEN','url':'https://example.com/pr/1'}])
        if args[:3]==['gh','pr','view']:
            return json.dumps({'headRefOid':'head-sha','statusCheckRollup':[{'status':'COMPLETED','conclusion':'FAILURE','name':'tests'}]})
        return ''
    monkeypatch.setattr(pub,'call',call)
    with pytest.raises(RuntimeError,match='checks'):
        pub.checkpoint(1,'core')
    assert not any(args[:3]==['gh','pr','merge'] for args in commands)
    assert store.receipt(run_id,'github:1:core') is None
    store.close()


def test_changed_published_source_is_detected(tmp_path):
    write_json(tmp_path/'research/protocol.json',{'analysis_kind':'exploratory'})
    write_json(tmp_path/'research/registration.json',{'protocol_sha256':digest(tmp_path/'research/protocol.json'),'registered_at':'2026-01-01'})
    (tmp_path/'study.py').write_text('original source')
    write_json(tmp_path/'research/core-code.json',{'sha256':digest(tmp_path/'study.py')})
    (tmp_path/'study.py').write_text('different source after publication')
    assert any('source' in error for error in verify_results(tmp_path))


def test_claim_requires_a_valid_analysis_kind():
    claim = {'id':'bad','text':'A result','evidence':['source'],'limitations':'Scoped','analysis_kind':'unclassified'}
    assert verify_claims([claim],[],[{'id':'source'}])


def test_explicit_extension_retains_consumed_budget(tmp_path):
    previous = RunConfig(str(tmp_path),'claude',profile='digits').to_dict()
    args = parser().parse_args(['resume','--project',str(tmp_path),'--max-minutes','180','--max-calls','60'])
    config = configuration(args,previous)
    assert (config.max_minutes,config.max_calls)==(180,60)
    store = Store(tmp_path)
    run_id = store.create(RunConfig(**previous),'fixture','policy')
    store.begin_attempt(run_id,'research','prompt')
    store.update(run_id,elapsed=3600)
    store.reconfigure(run_id,config)
    run = store.get(run_id)
    assert (run['calls'],run['elapsed'])==(1,3600)
    changes = store.receipt(run_id,'configuration_history')['changes']
    assert changes[-1]['previous']['max_minutes']==60
    assert changes[-1]['updated']['max_minutes']==180
    store.close()


def test_paths_accept_either_unambiguous_root(tmp_path):
    cycle = tmp_path/'cycles/001'
    write_json(cycle/'research/observation.json',{'observation':'recorded'})
    assert resolve_artifact(cycle,'research/observation.json')==cycle/'research/observation.json'
    assert resolve_artifact(cycle,'cycles/001/research/observation.json')==cycle/'research/observation.json'
    write_json(tmp_path/'research/observation.json',{'different':True})
    with pytest.raises(ValueError,match='Ambiguous'):
        resolve_artifact(cycle,'research/observation.json')
    with pytest.raises(ValueError,match='outside'):
        resolve_artifact(cycle,'../../../../outside.txt')


def test_claude_optional_empty_fields_still_validate(tmp_path):
    from auto_eureka_scientist.contracts import validate_handoff
    from auto_eureka_scientist.adapters import invocation
    argv,_ = invocation(RunConfig(str(tmp_path),'claude'),tmp_path,{})
    schema = json.loads(argv[argv.index('--json-schema')+1])
    assert 'revisit_phase' not in schema['required']
    value = {'status':'complete','summary':'Real work','artifacts':[],'evidence':[],'issues':[],
        'stage':'exploration','analysis_kind':'exploratory','objective':'Probe','predictions':[],
        'alternatives':[],'observations':[],'learning':'Negative result','rationale':'Continue',
        'decision':'continue'}
    assert validate_handoff(value)['not_applicable']==[]
    value['decision']='revisit'
    with pytest.raises(ValueError,match='requires'):
        validate_handoff(value)


def test_recovery_checks_keep_live_search_requirement(tmp_path,monkeypatch):
    from auto_eureka_scientist.engine import Controller
    store = Store(tmp_path)
    config = RunConfig(str(tmp_path),'claude',profile='digits')
    run_id = store.create(config,'offline','policy')
    monkeypatch.setattr('auto_eureka_scientist.engine.verify_phase',lambda *args,**kwargs:[])
    controller = Controller(store,run_id)
    assert controller.check_outputs('research',tmp_path,{},False)
    assert not controller.check_outputs('research',tmp_path,{},True)
    assert 'Missing registered comparisons' in controller.check_outputs('experiments',tmp_path,{},False)[0]
    store.close()


def test_claude_pin_covers_internal_background_models(tmp_path):
    from auto_eureka_scientist.adapters import invocation
    selected = 'claude-sonnet-5-5'
    config = RunConfig(str(tmp_path),'claude',model='sonnet',model_pin=selected)
    argv,env = invocation(config,tmp_path,{'ANTHROPIC_DEFAULT_HAIKU_MODEL':'claude-haiku-other'})
    settings = json.loads(argv[argv.index('--settings')+1])
    assert argv[argv.index('--model')+1]==selected
    assert env['ANTHROPIC_DEFAULT_HAIKU_MODEL']==selected
    assert settings['env']['ANTHROPIC_DEFAULT_HAIKU_MODEL']==selected
    assert not model_error(config,Response(models=[selected]))
    assert model_error(config,Response(models=['claude-sonnet-different']))
    with pytest.raises(ValueError,match='pin'):
        RunConfig(str(tmp_path),'claude',model='sonnet',model_pin='claude-haiku-other')


@pytest.mark.asyncio
async def test_controller_recheck_preserves_agent_cited_receipt(tmp_path):
    """A successful repeat check must not overwrite the agent's cited evidence."""
    import sys
    from auto_eureka_scientist.engine import Controller
    from auto_eureka_scientist.science import artifact_evidence
    from auto_eureka_scientist.util import read_json
    cycle = tmp_path/'cycles/001'
    write_json(cycle/'research/checks.json',{'command':[sys.executable,'-c','print("check passed")'],'cwd':'cycle'})
    original = {'agent_check':'original output including negative probes'}
    write_json(cycle/'research/core-checks.json',original)
    write_json(cycle/'research/evidence.json',[{'id':'audit-core-checks','analysis_kind':'exploratory',
        'path':'cycles/001/research/core-checks.json','sha256':digest(cycle/'research/core-checks.json')}])
    store = Store(tmp_path)
    run_id = store.create(RunConfig(str(tmp_path),'claude'),'offline','policy')
    await Controller(store,run_id,echo=False).check_command(cycle)
    evidence,errors = artifact_evidence(cycle)
    assert not errors
    assert read_json(tmp_path/evidence[0]['path'])==original
    assert read_json(cycle/'research/core-checks.json')['returncode']==0
    store.close()
