"""The local control surface rejects cross-origin writes and replays durable state."""
import pytest
from fastapi.testclient import TestClient

from auto_eureka_scientist.web.server import create_app


@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path)
    app.state.service.launch=lambda *args,**kwargs:None
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        client.headers['X-Eureka-Token']=client.get('/api/meta').json()['token']
        yield client


def test_create_snapshot_settings_and_duplicate_action(client):
    response=client.post('/api/runs',json={'settings':{'backend':'claude','publish':False,'max_loops':2},'specs':[{'text':'A'},{'text':'B'}]})
    assert response.status_code==200,response.text
    run=response.json()['id']
    snapshot=client.get(f'/api/runs/{run}').json()
    assert len(snapshot['specs'])==2 and snapshot['run']['calls']==0
    patch=client.patch(f'/api/runs/{run}/settings',json={'settings':{'max_calls':4},'revision':0})
    assert patch.status_code==200
    assert client.patch(f'/api/runs/{run}/settings',json={'settings':{'max_calls':8},'revision':0}).status_code==409
    payload={'kind':'pause','request_id':'same'}
    a=client.post(f'/api/runs/{run}/actions',json=payload).json()
    b=client.post(f'/api/runs/{run}/actions',json=payload).json()
    assert a['id']==b['id']


def test_local_request_guards_and_artifact_paths(client):
    assert client.post('/api/runs',json={},headers={'Origin':'https://untrusted.example'}).status_code==403
    assert client.get('/api/meta',headers={'Host':'untrusted.example'}).status_code==403
    assert client.get('/api/file',params={'path':'../outside.txt'}).status_code==400
    assert client.get('/api/file',params={'path':'.env'}).status_code==400
    assert client.get('/').status_code==200
    assert client.get('/assets/app.js').status_code==200


def test_settings_presets_validate_before_writing(client):
    assert client.put('/api/presets/careful',json={'schema_version':1,'settings':{'max_loops':3}}).status_code==200
    assert client.get('/api/presets/careful').json()['settings']['max_loops']==3
    assert client.put('/api/presets/secrets',json={'schema_version':1,'settings':{'API_KEY':'secret'}}).status_code==400


def test_new_run_defaults_refresh_and_do_not_override_explicit_or_preset_values(client):
    assert client.get('/api/meta').json()['defaults']['max_loops']==1
    assert client.put('/api/defaults',json={'schema_version':1,'settings':{'max_loops':3}}).status_code==200
    defaults=client.get('/api/meta').json()['defaults']
    assert defaults['max_loops']==3 and defaults['mode']=='continuous'
    client.put('/api/presets/endless',json={'schema_version':1,'settings':{'max_loops':None}})
    run=client.post('/api/runs',json={'preset':'endless','settings':{'publish':False},'specs':[{'text':'A'}],'start':False}).json()['id']
    assert client.get(f'/api/runs/{run}').json()['run']['config']['max_loops'] is None
    run=client.post('/api/runs',json={'preset':'endless','settings':{'publish':False,'max_loops':2},'specs':[{'text':'B'}],'start':False}).json()['id']
    assert client.get(f'/api/runs/{run}').json()['run']['config']['max_loops']==2


def test_openapi_uses_registry_types_and_cycle_scope(client):
    schemas=client.get('/openapi.json').json()['components']['schemas']
    fields=schemas['RunInput']['properties']['settings']['properties']
    assert fields['max_loops']['type']==['integer','null']
    assert fields['max_loops']['x-apply']=='immediate'
    overrides=schemas['Spec']['properties']['settings']['properties']
    assert 'repair_retries' in overrides and 'model' not in overrides and 'max_calls' not in overrides
