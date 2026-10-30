"""Boundary faults and limits are tested with actual subprocesses and durable records."""
import asyncio
import json
import sys

import pytest

from auto_eureka_scientist import engine
from auto_eureka_scientist.engine import Controller
from auto_eureka_scientist.events import EventSink
from test_operator import fixture_run


@pytest.mark.asyncio
async def test_accepted_phase_survives_crash_before_navigation(fixture_run):
    store,publisher,make=fixture_run
    run=make()
    store.enqueue_action(run,'step')
    first=await Controller(store,run,publisher=publisher,echo=False).run()
    store.update(run,phase_index=0)  # Fault boundary: accepted receipt, old pointer.
    store.enqueue_action(run,'step')
    second=await Controller(store,run,publisher=publisher,echo=False).run()
    assert second['phase_index']==1 and second['calls']==first['calls']==1


@pytest.mark.asyncio
async def test_completion_marker_survives_final_receipt_crash(fixture_run,monkeypatch):
    store,publisher,make=fixture_run
    run=make()
    original=store.receipt
    tripped=[]
    def receipt(run_id,key,value=None):
        if key.startswith('loop-finalized:') and value and not tripped:
            tripped.append(True)
            raise RuntimeError('crash after completion transaction')
        return original(run_id,key,value)
    monkeypatch.setattr(store,'receipt',receipt)
    first=await Controller(store,run,publisher=publisher,echo=False).run()
    assert first['status']=='blocked' and first['loops_completed']==1
    second=await Controller(store,run,publisher=publisher,echo=False).run()
    assert second['status']=='complete' and second['loops_completed']==1 and second['calls']==8
    assert publisher.published.count('summary')==1


@pytest.mark.asyncio
@pytest.mark.parametrize('policy,expected,calls',[('pause','blocked',1),('skip','paused',2)])
async def test_persistent_failure_policy_bounds_queue_pass(fixture_run,monkeypatch,policy,expected,calls):
    store,publisher,make=fixture_run
    monkeypatch.setattr(engine,'invocation',lambda *args:([sys.executable,'-c','print("invalid response")'],None))
    run=make(mode='continuous',failure_policy=policy,repair_retries=0)
    store.set_specs(run,[{'text':'A'},{'text':'B'}])
    result=await Controller(store,run,publisher=publisher,echo=False).run()
    assert result['status']==expected and result['calls']==calls and result['loops_completed']==0


@pytest.mark.asyncio
@pytest.mark.parametrize('control',['pause','stop','interrupt'])
async def test_immediate_controls_terminate_owned_invocation(fixture_run,monkeypatch,control):
    store,publisher,make=fixture_run
    normal=engine.invocation
    calls=[]
    def invocation(*args):
        calls.append(True)
        if len(calls)==1:return [sys.executable,'-c','import time; print("started",flush=True); time.sleep(30)'],None
        return normal(*args)
    monkeypatch.setattr(engine,'invocation',invocation)
    run=make(max_calls=1,heartbeat_seconds=.1,termination_grace=.1)
    task=asyncio.create_task(Controller(store,run,publisher=publisher,echo=False).run())
    async with asyncio.timeout(15):
        while not any(e['type']=='process.started' for e in store.events(run)):await asyncio.sleep(.02)
        store.enqueue_action(run,control)
        result=await task
    assert result['status']=={'pause':'paused','stop':'stopped','interrupt':'budget_exhausted'}[control]
    assert result['calls']==1 and result['loops_completed']==0
    assert any(e['type']=='process.finished' and e['data']['reason']!='exited' for e in store.events(run))


@pytest.mark.asyncio
async def test_time_limit_counts_execution_and_excludes_idle_pause(fixture_run,monkeypatch):
    store,publisher,make=fixture_run
    monkeypatch.setattr(engine,'invocation',lambda *args:([sys.executable,'-c','import time; time.sleep(10)'],None))
    run=make(max_minutes=.005,heartbeat_seconds=.1,termination_grace=0)
    result=await Controller(store,run,publisher=publisher,echo=False).run()
    assert result['status']=='budget_exhausted' and result['elapsed']>=.3
    elapsed=store.get(run)['elapsed']
    await asyncio.sleep(.1)
    assert store.get(run)['elapsed']==elapsed


def test_next_cycle_settings_remain_pending_across_controller_restart(fixture_run):
    store,publisher,make=fixture_run
    run=make()
    first=Controller(store,run,publisher=publisher,echo=False)
    first.refresh('next cycle')
    store.patch_settings(run,{'cycle_delay':15},expected_revision=0)
    second=Controller(store,run,publisher=publisher,echo=False)
    second.refresh('next invocation')
    assert second.config.cycle_delay==0
    store.advance_cycle(run)
    second.refresh('next cycle')
    assert second.config.cycle_delay==15


def test_stream_partial_unicode_and_unknown_provider_events(fixture_run):
    store,_,make=fixture_run
    run=make()
    sink=EventSink(store,run)
    raw=json.dumps({'type':'stream_event','event':{'delta':{'type':'text_delta','text':'žluťoučký 🔬'}}},ensure_ascii=False)
    sink.stream('stdout',raw[:17]);sink.stream('stdout',raw[17:]+'\n')
    sink.stream('stdout','{"message":{"content":[null,"unknown"]},"event":"unknown"}\n')
    sink.finish()
    assert any(e['type']=='agent.delta' and e['data']['text']=='žluťoučký 🔬' for e in store.events(run))


@pytest.mark.asyncio
async def test_question_crash_recovers_without_second_call(fixture_run):
    store,publisher,make=fixture_run
    run=make()
    question=store.add_message(run,'Explain the recorded state',kind='ask')
    result=await Controller(store,run,publisher=publisher,echo=False).run(maintenance=True)
    message=store.messages(run)[0]
    # Reproduce the boundary after the terminal CLI event but before message commit.
    store.deliver_question(question['id'],message['attempt'])
    recovered=await Controller(store,run,publisher=publisher,echo=False).run(maintenance=True)
    assert recovered['calls']==result['calls']==1 and recovered['phase_index']==0
    assert store.messages(run)[0]['status']=='answered'


@pytest.mark.asyncio
async def test_question_crash_does_not_accept_unfinished_provider_turn(fixture_run):
    store,publisher,make=fixture_run
    run=make(backend='codex')
    question=store.add_message(run,'Explain the recorded state',kind='ask')
    result=await Controller(store,run,publisher=publisher,echo=False).run(maintenance=True)
    message=store.messages(run)[0]
    logs=store.project/'.eureka'/run/f'{message["attempt"]:04d}-chat'
    raw=logs/'stdout.jsonl'
    raw.write_text('\n'.join(line for line in raw.read_text(encoding='utf-8').splitlines()
        if json.loads(line).get('type')!='turn.completed')+'\n',encoding='utf-8')
    store.deliver_question(question['id'],message['attempt'])
    recovered=await Controller(store,run,publisher=publisher,echo=False).run(maintenance=True)
    assert recovered['calls']==result['calls']==1 and recovered['phase_index']==0
    assert store.messages(run)[0]['status']=='failed'


def test_shuffled_queue_and_cycle_overrides_survive_reopen(fixture_run):
    store,publisher,make=fixture_run
    run=make(queue_order='shuffle',queue_seed=42)
    entries=store.set_specs(run,[{'text':letter,'settings':{'pinned_instructions':'Immutable '+letter}} for letter in 'ABC'])
    first=store.active_spec(run)
    remaining=store.db.execute('SELECT remaining FROM queue_state WHERE run_id=?',(run,)).fetchone()[0]
    from auto_eureka_scientist.state import Store
    other=Store(store.project)
    try:
        assert other.active_spec(run)==first
        assert other.db.execute('SELECT remaining FROM queue_state WHERE run_id=?',(run,)).fetchone()[0]==remaining
        other.finish_cycle(run,'skipped',advance=True)
        other.advance_cycle(run)
        second=other.active_spec(run)
        assert second['id']==json.loads(remaining)[0]
    finally:other.close()
    controller=Controller(store,run,publisher=publisher,echo=False)
    controller.refresh('next cycle')
    assert controller.config.pinned_instructions=='Immutable '+second['text']
    updated=store.set_specs(run,entries)
    with pytest.raises(ValueError,match='conflict'):store.set_specs(run,entries)
    assert store.active_spec(run)==second


def test_explicit_revised_cycle_uses_latest_spec_without_rewriting_old_snapshot(fixture_run):
    store,_,make=fixture_run
    run=make()
    original=store.set_specs(run,[{'text':'Original','parameters':{'seed':1}}])
    frozen=store.active_spec(run)
    updated=[{**original[0],'text':'Revised','parameters':{'seed':2}}]
    store.set_specs(run,updated)
    assert store.active_spec(run)==frozen
    store.finish_cycle(run,'revised',advance=True,carry='latest')
    store.advance_cycle(run,carry_spec='latest')
    assert store.active_spec(run)['parameters']=={'seed':2}
    assert store.get(run)['loops_completed']==0
