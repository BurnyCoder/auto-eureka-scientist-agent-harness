"""Full offline loops exercise controls with actual subprocess streams, not mock replies."""
import asyncio
import json
from pathlib import Path
import sys

import pytest

from auto_eureka_scientist import engine
from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.engine import Controller
from auto_eureka_scientist.policy import policy_hash
from auto_eureka_scientist.state import Store
from auto_eureka_scientist.workspace import initialize
from test_pipeline import FakePublisher


@pytest.fixture
def fixture_run(tmp_path,monkeypatch):
    initialize(tmp_path)
    fixture=Path(__file__).with_name('fake_cli.py')
    monkeypatch.setattr(engine,'invocation',lambda c,l,e:([sys.executable,str(fixture),*(['--codex-fixture'] if c.backend=='codex' else [])],None))
    monkeypatch.setattr('auto_eureka_scientist.operator.invocation',lambda c,l,e,**kw:([sys.executable,str(fixture),*(['--codex-fixture'] if c.backend=='codex' else [])],None))
    monkeypatch.setattr('auto_eureka_scientist.phases.retrieve_sources',lambda c:[])
    monkeypatch.setattr(engine,'commit',lambda *a:'fixture-sha')
    monkeypatch.setattr(engine,'render',lambda *a,**kw:{})
    publisher=FakePublisher();publisher.fail_once=False
    store=Store(tmp_path)
    def make(backend='claude',**settings):
        run=store.create(RunConfig(str(tmp_path),backend,publish=False,**settings),'A',policy_hash())
        return run
    yield store,publisher,make
    store.close()


@pytest.mark.asyncio
async def test_three_completed_loops_alternate_two_specs(fixture_run):
    store,publisher,make=fixture_run
    run=make(mode='continuous',max_loops=3)
    store.set_specs(run,[{'text':'A'},{'text':'B'}])
    result=await Controller(store,run,publisher=publisher,echo=False).run()
    assert result['status']=='complete',result['message']
    assert result['loops_completed']==3 and result['calls']==24
    snapshots=[json.loads(r[0])['text'] for r in store.db.execute('SELECT value FROM cycle_specs ORDER BY cycle')]
    assert snapshots==['A','B','A']


@pytest.mark.asyncio
async def test_step_pause_chat_and_resume_keep_phase_and_budgets(fixture_run):
    store,publisher,make=fixture_run
    run=make()
    store.enqueue_action(run,'step')
    first=await Controller(store,run,publisher=publisher,echo=False).run()
    assert first['status']=='paused' and first['phase_index']==1 and first['calls']==1
    store.add_message(run,'What phase is next?',kind='ask')
    answered=await Controller(store,run,publisher=publisher,echo=False).run(maintenance=True)
    assert answered['status']=='paused' and answered['phase_index']==1 and answered['calls']==2
    assert store.messages(run)[0]['answer']=='Recorded phase explained by an offline fixture.'
    result=await Controller(store,run,publisher=publisher,echo=False).run()
    assert result['status']=='complete' and result['calls']==9
    assert result['elapsed']>=answered['elapsed']>=first['elapsed']


@pytest.mark.asyncio
async def test_call_budget_stops_entire_queue_even_in_skip_mode(fixture_run):
    store,publisher,make=fixture_run
    run=make(mode='continuous',max_calls=1,failure_policy='skip')
    result=await Controller(store,run,publisher=publisher,echo=False).run()
    assert result['status']=='budget_exhausted' and result['loops_completed']==0 and result['calls']==1


@pytest.mark.asyncio
async def test_empty_queue_pauses_without_inference(fixture_run):
    store,publisher,make=fixture_run
    run=make(mode='continuous')
    store.set_specs(run,[])
    result=await Controller(store,run,publisher=publisher,echo=False).run()
    assert result['status']=='paused' and result['calls']==0


def test_setting_application_boundaries(fixture_run):
    store,publisher,make=fixture_run
    run=make()
    controller=Controller(store,run,publisher=publisher,echo=False)
    store.patch_settings(run,{'reasoning':'low','max_calls':5},expected_revision=0)
    controller.refresh()
    assert controller.config.reasoning=='high' and controller.config.max_calls==5
    controller.refresh('next invocation')
    assert controller.config.reasoning=='low'
