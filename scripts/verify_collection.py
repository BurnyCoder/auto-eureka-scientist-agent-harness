# /// script
# requires-python = ">=3.14"
# dependencies = ["huggingface-hub==1.30.0"]
# ///
"""Read live Hub memberships, public model revisions and the child repositories' collection links.

Run with `uv run scripts/verify_collection.py`. Hub collection listings contain at most four
sample items per collection, so fetch each relevant collection in full.
https://huggingface.co/docs/huggingface_hub/guides/collections
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import urlopen

from huggingface_hub import HfApi, get_token


ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / 'reports/verification'


def github(*args):
    """Read from GitHub using the authenticated CLI, pinning file reads to a public revision."""
    return subprocess.check_output(['gh', 'api', *args], text=True, encoding='utf-8', timeout=30).strip()


def github_file(repo, revision, filename):
    return github('-H', 'Accept: application/vnd.github.raw+json',
                  f'repos/{repo}/contents/{filename}?ref={revision}')


def public_link(url):
    """Follow public redirects and distinguish a retired endpoint from a service error."""
    try:
        with urlopen(url, timeout=30) as response:
            return {'status': response.status, 'final_url': response.geturl()}
    except HTTPError as error:
        if error.code != 404:
            raise
        return {'status': error.code, 'final_url': error.geturl()}


def snapshot():
    slug = (ROOT / '.eureka-collection').read_text(encoding='utf-8').strip()
    owner = slug.split('/')[0]
    url = f'https://huggingface.co/collections/{slug}'
    expected = json.loads((RECEIPTS / 'shared-collection.json').read_text())['items']
    historical = {json.loads(path.read_text())['models']['collection'].split('/collections/')[1]
                  for path in RECEIPTS.glob('*-final-publication.json')}
    api = HfApi()
    actor = api.whoami()['name'] if get_token() else None
    owned = {c.slug for c in api.list_collections(owner=owner)}
    project_slugs = {s for s in owned if s in historical or
                     s.split('/')[1].startswith(('auto-eureka-scientist', 'eureka-digits-'))}
    memberships, revisions, children = {}, {}, {}
    for model in sorted(expected):
        memberships[model] = sorted(c.slug for c in api.list_collections(owner=owner, item=f'models/{model}'))
        project_slugs.update(memberships[model])
        revisions[model] = api.model_info(model, token=False).sha
        repo = model.removesuffix('-models')
        sha = github(f'repos/{repo}/commits/main', '--jq', '.sha')
        entry = {'commit': sha, 'marker': github_file(repo, sha, '.eureka-collection')}
        if repo in (f'{owner}/eureka-digits-haiku', f'{owner}/eureka-digits-luna'):
            entry['readme'] = f'https://github.com/{repo}/blob/{sha}/README.md'
            entry['readme_links_to_shared_collection'] = f']({url})' in github_file(repo, sha, 'README.md')
        children[repo] = entry

    collections = {}
    for candidate in sorted(project_slugs):
        collection = api.get_collection(candidate)
        collections[candidate] = [{'type': item.item_type, 'id': item.item_id} for item in collection.items]
    shared = api.get_collection(slug, token=False)
    shared_models = {item.item_id for item in shared.items if item.item_type == 'model'}
    destination = public_link(url)
    retired = {s: public_link(f'https://huggingface.co/api/collections/{s}') for s in sorted(historical - {slug})}
    checks = {
        'owner_authenticated': actor == owner,
        'one_project_collection': project_slugs == {slug},
        'all_expected_models_in_public_collection': set(expected) <= shared_models and not shared.private,
        'public_model_revisions_available': all(revisions.values()),
        'public_destination_resolves': destination['status'] == 200,
        'retired_collection_endpoints_return_404': all(link['status'] == 404 for link in retired.values()),
        'each_model_in_only_the_shared_owner_collection': all(items == [slug] for items in memberships.values()),
        'child_markers_and_updated_readme_links': all(child['marker'] == slug and
            child.get('readme_links_to_shared_collection', True) for child in children.values()),
    }
    return {'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'url': url, 'checks': checks,
            'collections': collections, 'owner_memberships': memberships, 'public_model_revisions': revisions,
            'child_github_repositories': children, 'public_destination': destination, 'retired_endpoints': retired}


if __name__ == '__main__':
    result = snapshot()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(result['checks'].values()) else 1)
