"""Real child processes exercise both protocols, bounded retries and crash recovery."""
from pathlib import Path
import sys

import pytest

from auto_eureka_scientist import engine
from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.engine import Controller
from auto_eureka_scientist.policy import policy_hash
from auto_eureka_scientist.state import Store
from auto_eureka_scientist.workspace import initialize


class FakePublisher:
    def __init__(self):
        self.fail_once = True
        self.published = []
    def bootstrap(self): return {}
    def branch(self,*args): pass
    def enable_pages(self): return {'local':True}
    def checkpoint(self,cycle,phase):
        if phase=='pilot' and self.fail_once:
            self.fail_once = False
            raise RuntimeError('Simulated publication outage')
        self.published.append(phase)
        return {'local':True,'sha':'fixture'}


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['claude','codex'])
async def test_pipeline_recovers_without_duplicate_model_call(tmp_path,monkeypatch,backend):
    project = tmp_path/'Unicode ž research'
    initialize(project)
    (project/'transient-once').touch()
    (project/'revisit-once').touch()
    fake = Path(__file__).with_name('fake_cli.py')
    monkeypatch.setattr(engine,'invocation',lambda config,logs,env:([sys.executable,str(fake),*(['--codex-fixture'] if backend=='codex' else [])],None))
    monkeypatch.setattr('auto_eureka_scientist.phases.retrieve_sources',lambda cycle:[])
    monkeypatch.setattr(engine,'commit',lambda *args:'committed-fixture')
    monkeypatch.setattr(engine,'render',lambda *args,**kwargs:{})
    store = Store(project)
    run_id = store.create(RunConfig(str(project),backend,publish=False,max_calls=20),'offline task',policy_hash())
    publisher = FakePublisher()
    first = await Controller(store,run_id,publisher=publisher,echo=False).run()
    assert first['status']=='blocked' and 'publication outage' in first['message']
    calls_at_failure = first['calls']
    second = await Controller(store,run_id,publisher=publisher,echo=False).run()
    assert second['status']=='complete',second['message']
    assert second['calls']==calls_at_failure+7  # experiments, analysis, review; revisit those; publish
    assert publisher.published==['core','pilot','publish']
    assert len(store.phases(run_id))==8
    assert (project/'cycles/001/results/pilot.json').exists()
    history = (project/'cycles/001/research/decisions.jsonl').read_text()
    assert history.count('"phase": "review"')==2
    store.close()
