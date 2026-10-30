"""Configuration is a reproducible input, shared by CLI, API and browser forms."""
import json

import pytest

from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.settings import schema, resolve_settings, save_preset, load_preset, parse_overrides


def test_registry_describes_every_serialized_setting(tmp_path):
    config = RunConfig(str(tmp_path), 'claude').to_dict()
    properties = schema()['properties']
    assert set(config) == set(properties)
    assert all(p.get('description') and p.get('x-apply') for p in properties.values())
    assert properties['max_loops']['default'] is None  # Legacy continuous runs remain continuous.


def test_explicit_null_and_source_precedence(tmp_path, monkeypatch):
    (tmp_path/'.env').write_text('EUREKA_MAX_CALLS=7\nEUREKA_REASONING=low\n')
    monkeypatch.setenv('EUREKA_MAX_CALLS', '9')
    values = resolve_settings(tmp_path, {'backend':'claude', 'max_calls':None}, defaults={'max_calls':2})
    assert values['max_calls'] is None and values['reasoning'] == 'low'
    assert parse_overrides(['max_calls=null','pause_before=["pilot"]']) == {'max_calls':None,'pause_before':['pilot']}
    with pytest.raises(ValueError, match='Unknown'):
        parse_overrides(['not_a_setting=true'])


def test_presets_roundtrip_and_reject_secrets_or_unknown_fields(tmp_path):
    save_preset(tmp_path, 'careful', {'max_loops':3,'pause_before':['pilot']})
    assert load_preset(tmp_path, 'careful')['max_loops'] == 3
    with pytest.raises(ValueError):
        save_preset(tmp_path, '../escape', {})
    with pytest.raises(ValueError):
        save_preset(tmp_path, 'secret', {'OPENAI_API_KEY':'do-not-save'})
    assert 'do-not-save' not in ''.join(p.read_text() for p in (tmp_path/'.eureka').rglob('*.json'))


@pytest.mark.parametrize('patch', [{'max_loops':0}, {'repair_retries':-1}, {'heartbeat_seconds':0},
    {'pause_before':['missing']}, {'queue_order':'randomly'}, {'font_size':1000}, {'max_calls':True}])
def test_invalid_settings_fail_before_execution(tmp_path, patch):
    with pytest.raises(ValueError):
        RunConfig(str(tmp_path), 'claude', **patch)


def test_resume_ignores_environment_and_preset_precedence(tmp_path,monkeypatch):
    from auto_eureka_scientist.cli import parser,configuration
    saved=RunConfig(str(tmp_path),'codex',max_calls=4,publish=False).to_dict()
    monkeypatch.setenv('EUREKA_MAX_CALLS','99')
    (tmp_path/'.env').write_text('EUREKA_CODEX_MODEL=must-not-replace-recorded-model\n')
    args=parser().parse_args(['resume','--project',str(tmp_path),'--set','max_minutes=null'])
    resumed=configuration(args,saved)
    assert resumed.max_calls==4 and resumed.model=='gpt-6-luna'
    resolved=resolve_settings(tmp_path,{'backend':'claude'},defaults={'theme':'dark'},preset={'theme':'light'})
    assert resolved['theme']=='light' and resolved['max_calls']==99


def test_backend_capabilities_and_nonfinite_limits_rejected(tmp_path):
    with pytest.raises(ValueError,match='model_pin'):
        RunConfig(str(tmp_path),'codex',model_pin='gpt-6-luna')
    with pytest.raises(ValueError,match='finite'):
        parse_overrides(['max_minutes=NaN'])
    assert schema()['properties']['model_pin']['x-backends']==['claude']
