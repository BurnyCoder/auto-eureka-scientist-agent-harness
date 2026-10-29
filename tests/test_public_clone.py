"""Public artifacts must remain inspectable after private state has been excluded."""
from types import SimpleNamespace

from auto_eureka_scientist.cli import inspect_artifacts
from auto_eureka_scientist.util import write_json


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
