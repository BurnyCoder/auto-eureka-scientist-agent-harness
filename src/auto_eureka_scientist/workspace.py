"""Initialize or attach projects without replacing existing user files."""
from importlib.resources import files
from pathlib import Path
import shutil

from .config import RunConfig
from .policy import policy_bytes, requirements
from .util import command, read_json, write_json


def initialize(project: Path, *, profile='research', task='', harness_revision=''):
    project.mkdir(parents=True,exist_ok=True)
    for name in ('.eureka','docs','reports','cycles'):
        (project/name).mkdir(exist_ok=True)
    policy = project/'research-policy.txt'
    if not policy.exists():
        policy.write_bytes(policy_bytes())
    for name in ('AGENTS.md','CLAUDE.md'):
        path = project/name
        if not path.exists():
            path.write_text('# Research instructions\n\nRead research-policy.txt. Follow the current harness phase. '
                            'Preserve all evidence and do not invoke another backend or model.\n',encoding='utf-8')
    ignore = project/'.gitignore'
    additions = '\n# Local execution state and credentials\n.eureka/\n.env\n.venv/\n__pycache__/\n.pytest_cache/\n*.pyc\nmodels/\n'
    if not ignore.exists() or '.eureka/' not in ignore.read_text(encoding='utf-8'):
        with ignore.open('a',encoding='utf-8') as stream:
            stream.write(additions)
    if not (project/'README.md').exists():
        (project/'README.md').write_text('# '+project.name+'\n\n'+task+'\n\nRun status: not yet executed. '
                                       'See cycles/ for protocols, code, and generated reports.\n',encoding='utf-8')
    if not (project/'.git').exists():
        command(['git','init','-b','main'],project)
    config_path = project/'.eureka/project.json'
    if not config_path.exists():
        write_json(config_path,{'profile':profile,'task':task,'harness_revision':harness_revision})


def prepare_cycle(project: Path, cycle_number: int, profile: str) -> Path:
    cycle = project/'cycles'/f'{cycle_number:03d}'
    for directory in ('research','reports','results','models','figures','docs'):
        (cycle/directory).mkdir(parents=True,exist_ok=True)
    checklist = cycle/'research/requirements.json'
    if not checklist.exists():
        write_json(checklist,[{**item,'status':'pending','evidence':[],'reason':''} for item in requirements()])
    if profile == 'digits':
        for source,target in [('digits_protocol.json','research/protocol.json'),('digits_study.py','study.py')]:
            destination = cycle/target
            if not destination.exists():
                destination.write_bytes(files('auto_eureka_scientist').joinpath('resources',source).read_bytes())
        pyproject = project/'pyproject.toml'
        if not pyproject.exists():
            pyproject.write_text('''[project]
name = "eureka-digits-study"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = ["numpy", "scipy", "scikit-learn", "torch", "safetensors", "matplotlib"]
''',encoding='utf-8')
    return cycle

