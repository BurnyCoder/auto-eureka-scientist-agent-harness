"""Continuing a project must preserve its earlier results and per-run limits."""
import json
from pathlib import Path
import sys
import sqlite3

import pytest

from auto_eureka_scientist import engine
from auto_eureka_scientist import cli
from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.engine import Controller
from auto_eureka_scientist.policy import policy_hash
from auto_eureka_scientist.state import Store
from auto_eureka_scientist.util import write_json
from auto_eureka_scientist.workspace import initialize
from test_pipeline import FakePublisher


def test_new_runs_reserve_distinct_cycles_and_keep_project_ownership(tmp_path):
    store = Store(tmp_path)
    config = RunConfig(str(tmp_path),'claude',publish=False)
    first = store.create(config,'first task',policy_hash())
    second = store.create(config,'second task',policy_hash())
    assert store.get(first)['cycle']==1
    assert store.get(second)['cycle']==2
    store.acquire(first)
    with pytest.raises(RuntimeError,match='project.*live controller'):
        store.acquire(second)
    store.update(first,owner_pid=0,owner_start=0)
    store.advance_cycle(first)
    assert store.get(first)['cycle']==3
    assert store.get(first)['cycles_started']==2
    assert store.get(second)['cycle']==2
    store.close()


def test_legacy_state_migrates_without_resetting_progress(tmp_path):
    store = Store(tmp_path)
    config = RunConfig(str(tmp_path),'claude',publish=False)
    run_id = store.create(config,'existing task','policy')
    store.complete_phase(run_id,'research',{'summary':'Retained observation'}, {})
    store.update(run_id,cycle=2,elapsed=12)
    store.begin_attempt(run_id,'research','existing prompt')
    store.close()
    with sqlite3.connect(tmp_path/'.eureka/state.sqlite3') as legacy:
        legacy.execute('DROP TABLE cycles')  # Match the previously released schema.
    migrated = Store(tmp_path)
    row = migrated.get(run_id)
    assert row['cycle']==2 and row['cycles_started']==2 and row['elapsed']==12 and row['calls']==1
    assert migrated.phases(run_id,1)[0]['result']['summary']=='Retained observation'
    next_run = migrated.create(config,'new task','policy')
    assert migrated.get(next_run)['cycle']==3
    migrated.close()


def test_cli_attach_and_new_run_leave_existing_cycle_bytes_untouched(tmp_path,monkeypatch):
    initialize(tmp_path)
    protocol = tmp_path/'cycles/001/research/protocol.json'
    write_json(protocol,{'budget':'Earlier registered allowance'})
    original = protocol.read_bytes()
    task = tmp_path/'task.md'
    task.write_text('Continue research',encoding='utf-8')
    class NoInference:
        def __init__(self,store,run_id): self.store,self.run_id = store,run_id
        async def run(self): return self.store.get(self.run_id)
    monkeypatch.setattr(cli,'Controller',NoInference)
    monkeypatch.setattr(sys,'argv',['eureka','init','--project',str(tmp_path),'--profile','digits'])
    assert cli.main()==0
    monkeypatch.setattr(sys,'argv',['eureka','run','--project',str(tmp_path),'--profile','digits',
                                  '--task',str(task),'--backend','claude','--no-publish'])
    assert cli.main()==0
    assert protocol.read_bytes()==original
    assert not (tmp_path/'cycles/001/study.py').exists()
    store = Store(tmp_path)
    assert store.get()['cycle']==2
    store.close()


@pytest.mark.asyncio
async def test_continuous_run_attaches_public_history_without_overwriting_it(tmp_path,monkeypatch):
    initialize(tmp_path)
    archive = tmp_path/'cycles/001'
    write_json(archive/'research/protocol.json',{'question':'Earlier hypothesis'})
    write_json(archive/'results/negative.json',{'observation':'Earlier negative finding'})
    prior = {'phase':'publish','summary':'Earlier negative finding','learning':'Retain the alternative explanation'}
    (archive/'research/decisions.jsonl').write_text(json.dumps(prior)+'\n',encoding='utf-8')
    original = {p.relative_to(archive).as_posix():p.read_bytes() for p in archive.rglob('*') if p.is_file()}
    fake = Path(__file__).with_name('fake_cli.py')
    monkeypatch.setattr(engine,'invocation',lambda config,logs,env:([sys.executable,str(fake)],None))
    monkeypatch.setattr('auto_eureka_scientist.phases.retrieve_sources',lambda cycle:[])
    monkeypatch.setattr(engine,'commit',lambda *args:'committed-fixture')
    monkeypatch.setattr(engine,'render',lambda *args,**kwargs:{})
    publisher = FakePublisher()
    publisher.fail_once = False
    store = Store(tmp_path)
    run_id = store.create(RunConfig(str(tmp_path),'claude',publish=False,mode='continuous',max_cycles=2),
                          'Continue from the earlier negative finding',policy_hash())
    assert store.get(run_id)['cycle']==2
    outcome = await Controller(store,run_id,publisher=publisher,echo=False).run()
    assert outcome['status']=='complete',outcome['message']
    assert outcome['cycle']==3 and outcome['cycles_started']==2 and outcome['calls']==16
    assert len(store.phases(run_id,2))==len(store.phases(run_id,3))==8
    assert {p.relative_to(archive).as_posix():p.read_bytes() for p in archive.rglob('*') if p.is_file()}==original
    prompt = (tmp_path/'.eureka'/run_id/'0001-research/prompt.txt').read_text(encoding='utf-8')
    assert 'Earlier negative finding' in prompt and 'cycles/001/research/decisions.jsonl' in prompt
    store.close()


@pytest.mark.asyncio
async def test_revised_hypothesis_waits_for_extended_cycle_budget(tmp_path,monkeypatch):
    initialize(tmp_path)
    (tmp_path/'revisit-hypothesis-once').touch()
    fake = Path(__file__).with_name('fake_cli.py')
    monkeypatch.setattr(engine,'invocation',lambda config,logs,env:([sys.executable,str(fake)],None))
    monkeypatch.setattr('auto_eureka_scientist.phases.retrieve_sources',lambda cycle:[])
    monkeypatch.setattr(engine,'commit',lambda *args:'committed-fixture')
    monkeypatch.setattr(engine,'render',lambda *args,**kwargs:{})
    publisher = FakePublisher()
    publisher.fail_once = False
    store = Store(tmp_path)
    config = RunConfig(str(tmp_path),'claude',publish=False,max_cycles=1)
    run_id = store.create(config,'Revise a hypothesis without replacing observations',policy_hash())
    first = await Controller(store,run_id,publisher=publisher,echo=False).run()
    assert first['status']=='budget_exhausted' and first['calls']==7
    original = (tmp_path/'cycles/001/results/experiments.json').read_bytes()
    config.max_cycles = 2
    store.reconfigure(run_id,config)
    second = await Controller(store,run_id,publisher=publisher,echo=False).run()
    assert second['status']=='complete',second['message']
    assert second['cycle']==2 and second['calls']==15
    assert len(store.phases(run_id,1))==7 and len(store.phases(run_id,2))==8
    assert (tmp_path/'cycles/001/results/experiments.json').read_bytes()==original
    store.close()
