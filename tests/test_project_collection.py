"""Project collection inheritance, legacy publication recovery and Hub retries."""
import json
import pytest

from auto_eureka_scientist.cli import configuration, parser
from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.engine import Controller
from auto_eureka_scientist.publication import Publisher
from auto_eureka_scientist.state import Store
from auto_eureka_scientist.util import command
from auto_eureka_scientist.workspace import initialize


MARKER = '.eureka-collection'
SHARED = 'fixture/shared-collection'
RETIRED = 'fixture/retired-collection'


def test_new_study_inherits_collection_and_carries_it_in_git(tmp_path, monkeypatch):
    family = tmp_path / 'family'
    family.mkdir()
    (family / MARKER).write_text(SHARED + '\n')
    child = family / 'workspaces' / 'study'
    args = parser().parse_args(['run', '--project', str(child), '--backend', 'claude', '--task', 'task.md'])
    assert configuration(args).hf_collection == SHARED
    with monkeypatch.context() as environment:
        environment.setenv('EUREKA_HF_COLLECTION', RETIRED)
        with pytest.raises(ValueError, match='collection'):
            configuration(args)

    initialize(child)
    initialize(child)  # Reattaching an initialized study preserves its portable setting.
    command(['git', 'add', MARKER], child)
    command(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.org',
             'commit', '-m', 'Record collection'], child)
    standalone = tmp_path / 'standalone'
    command(['git', 'clone', str(child), str(standalone)], tmp_path)
    assert RunConfig(str(standalone), 'codex').hf_collection == SHARED
    assert RunConfig(str(tmp_path / 'independent'), 'codex', hf_collection=RETIRED).hf_collection == RETIRED
    (child / MARKER).write_text(RETIRED)
    with pytest.raises(ValueError, match='collection'):
        initialize(child)


@pytest.mark.parametrize('previous_collection', ['', RETIRED])
def test_resume_adopts_project_collection_and_preserves_history(tmp_path, previous_collection):
    config = RunConfig(str(tmp_path), 'claude', hf_collection=previous_collection)
    store = Store(tmp_path)
    try:
        run = store.create(config, 'Old study', 'policy')
        store.begin_attempt(run, 'pilot', 'fixture')
        store.receipt(run, 'hf:collection', {'slug': RETIRED})
        (tmp_path / MARKER).write_text(SHARED)
        saved = store.get(run)['config']
        assert Controller(store, run).config.hf_collection == SHARED  # Console worker recovery.
        args = parser().parse_args(['resume', '--project', str(tmp_path)])
        resumed = configuration(args, saved)
        assert resumed.hf_collection == SHARED
        args.hf_collection = RETIRED
        with pytest.raises(ValueError, match='collection'):
            configuration(args, saved)
        store.reconfigure(run, resumed)
        assert store.get(run)['config']['hf_collection'] == SHARED
        assert store.get(run)['calls'] == 1
        assert store.receipt(run, 'hf:collection') == {'slug': RETIRED}
        assert store.receipt(run, 'configuration_history')['changes'][-1]['previous'] == saved
    finally:
        store.close()


def test_collection_checked_before_upload_and_membership_retry_reuses_upload(tmp_path, monkeypatch):
    (tmp_path / MARKER).write_text(SHARED)
    config = RunConfig(str(tmp_path), 'claude', owner='fixture')
    store = Store(tmp_path)
    try:
        run = store.create(config, 'Offline', 'policy')
        cycle = tmp_path / 'cycles/001'
        models = cycle / 'models'
        models.mkdir(parents=True)
        (models / 'weights.npz').write_bytes(b'fixture')
        calls = []

        def fake_hub(args, check=True):
            operation = tuple(args[:3])
            calls.append(operation)
            if operation == ('hf', 'collections', 'info'):
                assert args[3] == SHARED
                if calls.count(operation) == 1:
                    raise RuntimeError('collection unavailable')
                return json.dumps({'slug': SHARED})
            if operation[:2] == ('hf', 'upload'):
                return json.dumps({'url': 'https://example.org/commit'})
            if operation == ('hf', 'collections', 'add-item'):
                assert args[3:6] == [SHARED, f'fixture/{tmp_path.name}-models', 'model']
                assert '--exists-ok' in args
                if calls.count(operation) == 1:
                    raise RuntimeError('membership interrupted')
                return '{}'
            assert operation == ('hf', 'models', 'info')
            return '{"sha":"revision"}'

        publisher = Publisher(config, store, run, lambda: 60)
        monkeypatch.setattr(publisher, 'call', fake_hub)
        with pytest.raises(RuntimeError, match='collection unavailable'):
            publisher.models(cycle, 'pilot')
        assert calls == [('hf', 'collections', 'info')]
        with pytest.raises(RuntimeError, match='membership interrupted'):
            publisher.models(cycle, 'pilot')
        receipt = publisher.models(cycle, 'pilot')
        assert receipt['collection'].endswith('/' + SHARED) and receipt['verified']
        assert publisher.models(cycle, 'pilot') == receipt
        assert sum(entry[:2] == ('hf', 'upload') for entry in calls) == 1
    finally:
        store.close()
