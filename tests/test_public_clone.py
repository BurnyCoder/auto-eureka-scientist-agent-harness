"""Public artifacts must remain inspectable after private state has been excluded."""
from types import SimpleNamespace
import subprocess
import sys
import json
import pytest

from auto_eureka_scientist.cli import inspect_artifacts
from auto_eureka_scientist.util import write_json
from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.state import Store


def test_render_routes_a_public_clone_without_sqlite(tmp_path,monkeypatch):
    (tmp_path/'cycles/001').mkdir(parents=True)
    write_json(tmp_path/'reports/run-example.json',{'backend':'claude'})
    monkeypatch.setattr('auto_eureka_scientist.cli.render',lambda project,cycle,**options:{'cycle':cycle.name,**options})
    args = SimpleNamespace(project=tmp_path,run_id=None,cycle=None,command='render',backend=None,no_pdf=True)
    assert inspect_artifacts(args)=={'cycle':'001','backend':'Claude Code','pdf':False}
    assert not (tmp_path/'.eureka').exists()


def test_stateless_verify_does_not_claim_unrecorded_phases(tmp_path):
    (tmp_path/'cycles/001').mkdir(parents=True)
    args = SimpleNamespace(project=tmp_path,run_id=None,cycle=None,command='verify')
    assert inspect_artifacts(args)=={'cycle':1,'phases':{},'complete':False,'state_source':'public artifact history'}
    process = subprocess.run([sys.executable,'-m','auto_eureka_scientist.cli','verify','--project',str(tmp_path)],capture_output=True,text=True,encoding='utf-8')
    assert process.returncode==2
    assert not json.loads(process.stdout)['complete']


@pytest.mark.parametrize('private_state',[False,True])
def test_render_uses_the_requested_cycles_backend(tmp_path,monkeypatch,private_state):
    if private_state:
        store = Store(tmp_path)
        store.create(RunConfig(str(tmp_path),'claude'),'earlier task','hash')
        store.create(RunConfig(str(tmp_path),'codex'),'later task','hash')
        store.close()
    for cycle,backend in ((1,'claude'),(2,'codex')):
        (tmp_path/f'cycles/{cycle:03d}').mkdir(parents=True)
        write_json(tmp_path/f'reports/run-{cycle}.json',{'backend':backend,'attempts':[{'cycle':cycle}]})
    monkeypatch.setattr('auto_eureka_scientist.cli.render',lambda project,cycle,**options:{'cycle':cycle.name,**options})
    args = SimpleNamespace(project=tmp_path,run_id=None,cycle=1,command='render',backend=None,no_pdf=True)
    assert inspect_artifacts(args)=={'cycle':'001','backend':'Claude Code','pdf':False}
