"""The controller must recover publication without paying for another inference."""
from pathlib import Path
import json

import pytest

from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.state import Store
from auto_eureka_scientist.engine import Controller, register_protocol
from auto_eureka_scientist.util import write_json, digest


def test_registration_cannot_rewrite_history(tmp_path):
    cycle = tmp_path/'cycles/001'
    (cycle/'research').mkdir(parents=True)
    protocol = cycle/'research/protocol.json'
    write_json(protocol, {'analysis_kind':'exploratory'})
    first = register_protocol(cycle, 'committed-sha')
    write_json(protocol, {'analysis_kind':'confirmatory'})
    with pytest.raises(ValueError, match='changed'):
        register_protocol(cycle, 'later-sha')
    assert json.loads((cycle/'research/registration.json').read_text()) == first
    assert (cycle/'research/protocol-history'/f"{first['protocol_sha256']}.json").exists()


def test_resume_keeps_calls_elapsed_and_pending_handoff(tmp_path):
    store = Store(tmp_path)
    config = RunConfig(str(tmp_path),'codex',publish=False,max_calls=1,max_minutes=1)
    run_id = store.create(config,'test','hash')
    attempt = store.begin_attempt(run_id,'research','prompt-hash')
    store.finish_attempt(attempt,'accepted',{})
    store.update(run_id,elapsed=30)
    store.receipt(run_id,'pending:1:research',{'summary':'already verified'})
    controller = Controller(store,run_id)
    assert controller.remaining() <= 30
    assert store.get(run_id)['calls'] == 1
    assert store.receipt(run_id,'pending:1:research')['summary'] == 'already verified'
    assert controller.limit_reason(call=True) == 'call budget exhausted'
    store.close()


def test_live_profile_never_extends_trial_limits(tmp_path):
    with pytest.raises(ValueError,match='capped'):
        RunConfig(str(tmp_path),'claude',profile='digits',max_calls=21)

