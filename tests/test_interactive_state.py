"""Operator changes and queue navigation must survive replay and concurrent clients."""
import pytest

from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.state import Store


def create(tmp_path, **options):
    store = Store(tmp_path)
    run = store.create(RunConfig(str(tmp_path),'claude',publish=False,**options),'A','policy')
    return store,run


def test_queue_snapshot_and_atomic_completion(tmp_path):
    store,run = create(tmp_path,mode='continuous',max_loops=3)
    store.set_specs(run,[{'title':'A','text':'first'},{'title':'B','text':'second'}])
    assert store.active_spec(run)['text']=='first'
    specs = store.specs(run)
    specs[0]['text']='edited later'
    store.set_specs(run,specs)
    assert store.active_spec(run)['text']=='first'
    store.finish_cycle(run,'complete')
    store.finish_cycle(run,'complete')
    assert store.get(run)['loops_completed']==1
    store.advance_cycle(run)
    assert store.active_spec(run)['text']=='second'
    store.finish_cycle(run,'complete')
    store.advance_cycle(run)
    assert store.active_spec(run)['text']=='edited later'
    assert len(store.events(run))>0
    store.close()


def test_idempotent_actions_and_settings_revision_conflicts(tmp_path):
    store,run = create(tmp_path)
    first=store.enqueue_action(run,'pause',{},'same-key')
    assert store.enqueue_action(run,'pause',{},'same-key')['id']==first['id']
    with pytest.raises(ValueError): store.enqueue_action(run,'stop',{},'same-key')
    store.patch_settings(run,{'max_calls':5},expected_revision=0)
    with pytest.raises(ValueError,match='revision'):
        store.patch_settings(run,{'max_calls':8},expected_revision=0)
    assert store.get(run)['config']['max_calls']==5
    with pytest.raises(ValueError,match='new run'):
        store.patch_settings(run,{'model':'another-model'},expected_revision=1)
    store.close()


def test_message_scopes_and_event_replay(tmp_path):
    store,run=create(tmp_path)
    message=store.add_message(run,'Keep the negative results',kind='steer',scope='cycle')
    assert store.messages(run)[0]['id']==message['id']
    store.deliver_messages(run,1)
    assert store.messages(run)[0]['status']=='delivered'
    cursor=store.events(run)[-1]['id']
    store.event(run,'test',{'text':'ž'})
    assert [e['type'] for e in store.events(run,after=cursor)]==['test']
    store.close()
