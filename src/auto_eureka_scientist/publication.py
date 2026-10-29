"""Idempotent GitHub/Hugging Face publication using the user's authenticated CLIs.

https://cli.github.com/manual/gh_repo_create
https://cli.github.com/manual/gh_pr_merge
https://huggingface.co/docs/huggingface_hub/guides/cli
"""
from pathlib import Path
import json
import re
import shutil

from .util import command, digest, now, read_json, write_json


def commit(project: Path, message: str) -> str:
    """Protect the explicitly requested credential exclusion at the publication boundary."""
    command(['git','add','--all'],project)
    tracked = command(['git','ls-files','-z'],project).split('\0')
    for name in filter(None,tracked):
        path = Path(name)
        if path.name == '.env' or '.eureka' in path.parts or path.suffix in ('.pem','.key','.sqlite3'):
            raise RuntimeError(f'Publication includes excluded credential/runtime path: {name}')
        full = project/path
        if full.is_file() and full.stat().st_size < 2_000_000:
            text = full.read_text(encoding='utf-8',errors='ignore')
            if re.search(r'(?:ghp_[A-Za-z0-9]{36}|sk-proj-[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)',text):
                raise RuntimeError(f'Possible credential in {name}; content withheld')
    if command(['git','diff','--cached','--name-only'],project):
        command(['git','commit','-m',message],project)
    return command(['git','rev-parse','HEAD'],project)


class Publisher:
    def __init__(self, config, store, run_id, remaining):
        self.config, self.store, self.run_id = config, store, run_id
        self.project = Path(config.project)
        self.remaining = remaining

    def call(self, args, check=True):
        return command(args,self.project,timeout=min(180,self.remaining()),check=check,
                       cancelled=lambda:bool(self.store.get(self.run_id)['stop']))

    def bootstrap(self):
        existing = self.store.receipt(self.run_id,'repository')
        if existing:
            return existing
        sha = commit(self.project,'Initialize research project and reproducibility policy')
        if not self.config.publish:
            receipt = {'local':True,'base':self.call(['git','branch','--show-current']),'sha':sha}
        else:
            owner = self.config.owner or self.call(['gh','api','user','--jq','.login'])
            name = self.config.repository or self.project.name
            full_name = name if '/' in name else f'{owner}/{name}'
            remote = self.call(['git','remote','get-url','origin'],check=False)
            if not remote:
                # gh creates a new repository or fails; it never overwrites an unrelated remote.
                self.call(['gh','repo','create',full_name,'--public','--source',str(self.project),'--remote','origin'])
            info = json.loads(self.call(['gh','repo','view','--json','nameWithOwner,url,defaultBranchRef']))
            base = (info.get('defaultBranchRef') or {}).get('name') or self.call(['git','branch','--show-current'])
            self.call(['git','push','-u','origin',base])
            receipt = {'repository':info['nameWithOwner'],'url':info['url'],'base':base,'sha':sha}
        self.store.receipt(self.run_id,'repository',receipt)
        return receipt

    def branch(self, cycle: int, milestone: str):
        repo = self.bootstrap()
        branch = f'eureka/{self.run_id}-c{cycle}-{milestone}'
        current = self.call(['git','branch','--show-current'])
        if current == branch:
            return
        branches = self.call(['git','branch','--list',branch])
        self.call(['git','switch',branch] if branches else ['git','switch','-c',branch])

    def checkpoint(self, cycle: int, milestone: str) -> dict:
        key = f'github:{cycle}:{milestone}'
        receipt = self.store.receipt(self.run_id,key)
        if receipt:
            return receipt
        repo = self.bootstrap()
        sha = commit(self.project,f'Research cycle {cycle}: {milestone}')
        if not self.config.publish:
            receipt = {'local':True,'sha':sha,'at':now()}
        else:
            branch = self.call(['git','branch','--show-current'])
            self.call(['git','push','-u','origin',branch])
            if branch == repo['base']:
                receipt = {'sha':sha,'url':repo['url'],'at':now()}
            else:
                matches = json.loads(self.call(['gh','pr','list','--head',branch,'--state','all','--json','number,url,state']))
                if matches:
                    pr = matches[0]
                else:
                    body = self.project/'.eureka/pr-body.md'
                    body.write_text(f'Publish the verified {milestone} checkpoint for research cycle {cycle}.\n\n'
                                    'Evidence, commands, provenance and limitations are recorded in the cycle reports. '
                                    'Metrics are regenerated from stored predictions.\n',encoding='utf-8')
                    url = self.call(['gh','pr','create','--base',repo['base'],'--head',branch,'--title',
                                    f'Research cycle {cycle}: {milestone}','--body-file',str(body)])
                    pr = json.loads(self.call(['gh','pr','view',url,'--json','number,url,state']))
                # Preserve preregistration commits in reachable history; do not squash them away.
                if pr['state'] != 'MERGED':
                    self.call(['gh','pr','merge',str(pr['number']),'--merge','--match-head-commit',sha])
                self.call(['git','switch',repo['base']])
                self.call(['git','pull','--ff-only','origin',repo['base']])
                receipt = {'sha':sha,'pr':pr['url'],'url':repo['url'],'at':now()}
        self.store.receipt(self.run_id,key,receipt)
        return receipt

    def models(self, cycle: Path, milestone: str) -> dict:
        if not self.config.publish:
            return {'local':True,'at':now()}
        files = sorted(path for path in (cycle/'models').rglob('*') if path.is_file())
        if not files:
            raise RuntimeError('No model artifacts to publish')
        fingerprint = digest(cycle/'reports/metrics.json')
        key = f'hf:{cycle.name}:{milestone}:{fingerprint}'
        if previous := self.store.receipt(self.run_id,key):
            return previous
        owner = self.config.owner or self.call(['gh','api','user','--jq','.login'])
        repo_id = f'{owner}/{self.project.name}-models'
        upload = json.loads(self.call(['hf','upload',repo_id,str(cycle/'models'),'.','--json']))
        collection_key = 'hf:collection'
        collection = self.store.receipt(self.run_id,collection_key)
        if not collection:
            collection = json.loads(self.call(['hf','collections','create',self.project.name,'--namespace',owner,
                                              '--description','Reproducible research models and their recorded evaluation evidence',
                                              '--exists-ok','--json']))
            self.store.receipt(self.run_id,collection_key,collection)
        slug = collection.get('slug') or collection.get('collection',{}).get('slug')
        if not slug:
            raise RuntimeError('HF collection response did not contain its slug')
        self.call(['hf','collections','add-item',slug,repo_id,'model','--exists-ok','--json'])
        info = json.loads(self.call(['hf','models','info',repo_id,'--json']))
        receipt = {'repository':repo_id,'url':f'https://huggingface.co/{repo_id}',
                   'collection':f'https://huggingface.co/collections/{slug}','upload':upload,
                   'verified':bool(info),'at':now()}
        self.store.receipt(self.run_id,key,receipt)
        return receipt

    def enable_pages(self):
        if not self.config.publish:
            return {'local':True}
        repo = self.bootstrap()['repository']
        try:
            pages = json.loads(self.call(['gh','api',f'repos/{repo}/pages']))
        except RuntimeError:
            pages = json.loads(self.call(['gh','api','--method','POST',f'repos/{repo}/pages','-f','build_type=workflow']))
        self.store.receipt(self.run_id,'pages',pages)
        return pages


def install_pages_workflow(project: Path):
    destination = project/'.github/workflows/pages.yml'
    destination.parent.mkdir(parents=True,exist_ok=True)
    if not destination.exists():
        destination.write_text('''name: Publish research explorer
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v6
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v4
        with:
          path: site
      - uses: actions/deploy-pages@v4
        id: deployment
''',encoding='utf-8')

