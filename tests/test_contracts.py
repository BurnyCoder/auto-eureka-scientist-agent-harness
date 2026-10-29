"""Contracts keep scientific progression independent of an agent's success claim."""
import json
from pathlib import Path

import pytest

from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.adapters import invocation, parse_response
from auto_eureka_scientist.state import Store
from auto_eureka_scientist.policy import policy_bytes, requirements
from auto_eureka_scientist.phases import make_prompt


def test_policy_is_preserved():
    original = Path(__file__).parents[1] / 'prompts/full.txt'
    assert policy_bytes() == original.read_bytes()
    assert len(requirements()) == original.read_text(encoding='utf-8').count('\n## ') + 1


def test_every_phase_prompt_contains_the_entire_canonical_policy(tmp_path):
    from auto_eureka_scientist.contracts import PHASES
    run = {'config':RunConfig(str(tmp_path),'claude').to_dict(),'task':'A research question'}
    for phase in PHASES:
        prompt = make_prompt(run,phase,tmp_path/'cycles/001',[],[])
        assert policy_bytes().decode('utf-8-sig') in prompt
        assert 'revisit_phase' in prompt and 'not_applicable' in prompt


def test_models_are_configurable_but_validation_is_pinned(tmp_path):
    for backend, model in [('claude', 'some-future-claude'), ('codex', 'some-future-gpt')]:
        config = RunConfig(str(tmp_path), backend=backend, model=model)
        command, env = invocation(config, tmp_path, {})
        assert model in command
        with pytest.raises(ValueError, match='validation'):
            RunConfig(str(tmp_path), backend=backend, model=model, profile='digits')


def test_native_unrestricted_flags_and_streaming(tmp_path):
    claude, _ = invocation(RunConfig(str(tmp_path), backend='claude'), tmp_path, {})
    codex, _ = invocation(RunConfig(str(tmp_path), backend='codex'), tmp_path, {})
    assert '--dangerously-skip-permissions' in claude
    assert 'stream-json' in claude
    assert '--include-partial-messages' in claude
    assert '--dangerously-bypass-approvals-and-sandbox' in codex
    assert 'web_search="live"' in codex
    assert '--json' in codex


def test_error_event_overrides_zero_exit_and_partial_success(tmp_path):
    log = tmp_path / 'stdout.jsonl'
    log.write_text(json.dumps({'type':'result','is_error':True,'result':'rate limit reached'})+'\n')
    response = parse_response('claude', tmp_path)
    assert response.error and 'rate limit' in response.error
    log.write_text(json.dumps({'type':'error','message':None,'error':'model not available'})+'\n')
    assert 'not available' in parse_response('codex',tmp_path).error


def test_state_persists_counters_and_publication_receipts(tmp_path):
    store = Store(tmp_path)
    run_id = store.create(RunConfig(str(tmp_path), backend='claude'), 'task', 'policyhash')
    attempt = store.begin_attempt(run_id, 'research', 'p.txt')
    store.finish_attempt(attempt, 'failed', {'reason':'network'})
    store.update(run_id, elapsed=12.5, status='blocked')
    store.receipt(run_id, 'github:core', {'url':'https://example.com/repo'})
    store.close()
    reopened = Store(tmp_path)
    assert reopened.get(run_id)['calls'] == 1
    assert reopened.get(run_id)['elapsed'] == 12.5
    assert reopened.receipt(run_id, 'github:core')['url'].endswith('/repo')
    reopened.close()


def test_budget_mode_requires_a_limit(tmp_path):
    with pytest.raises(ValueError, match='budget'):
        RunConfig(str(tmp_path), backend='codex', mode='budget')

