"""User-facing commands; orchestration and scientific mechanics live in modules."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from .config import RunConfig, environment
from .contracts import PHASES
from .engine import Controller
from .phases import verify_phase
from .policy import policy_hash
from .reporting import render
from .state import Store
from .util import command, read_json
from .workspace import initialize, prepare_cycle


def parser():
    root = argparse.ArgumentParser(prog='eureka',description='Resumable scientific research through one selected coding CLI')
    commands = root.add_subparsers(dest='command',required=True)
    for name in ('init','doctor','run','resume','status','stop','verify','render'):
        item = commands.add_parser(name)
        item.add_argument('--project',type=Path,default=Path.cwd())
        if name in ('init','run'):
            item.add_argument('--profile',choices=('research','digits'),default='research')
            item.add_argument('--task',type=Path,required=name=='run')
        if name in ('run','resume'):
            item.add_argument('--backend',choices=('claude','codex'),required=name=='run')
            item.add_argument('--model')
            item.add_argument('--mode',choices=('cycle','continuous','budget'))
            item.add_argument('--max-minutes',type=float)
            item.add_argument('--max-calls',type=int)
            item.add_argument('--max-cycles',type=int)
            item.add_argument('--publish',action=argparse.BooleanOptionalAction,default=None)
            item.add_argument('--owner')
            item.add_argument('--repository')
            item.add_argument('--executable')
        if name in ('resume','status','stop','verify','render'):
            item.add_argument('--run-id')
        if name in ('verify','render'):
            item.add_argument('--cycle',type=int)
        if name=='render':
            item.add_argument('--no-pdf',action='store_true')
            item.add_argument('--backend',choices=('claude','codex'))
        if name=='doctor':
            item.add_argument('--backend',choices=('claude','codex'))
    return root


def doctor(project: Path, backend=None):
    """No inference: inspect executables, authentication, configured model and GPU."""
    checks = {}
    checks_to_run = {'git':['git','--version'],'uv':['uv','--version'],
                     'github':['gh','api','user','--jq','.login'],'huggingface':['hf','auth','whoami'],
                     'pandoc':['pandoc','--version'],'latex':['pdflatex','--version'],
                     'gpu':['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader']}
    for provider in ([backend] if backend else ['claude','codex']):
        checks_to_run[provider] = [provider,'--version']
        checks_to_run[provider+'_auth'] = [provider,'auth','status'] if provider=='claude' else [provider,'login','status']
    for name,args in checks_to_run.items():
        try:
            checks[name] = {'ok':True,'detail':command(args,project,timeout=30)}
        except (OSError,RuntimeError,TimeoutError) as exc:
            checks[name] = {'ok':False,'detail':str(exc)}
    env = environment(project)
    checks['models'] = {'claude':env.get('EUREKA_CLAUDE_MODEL','haiku'),
                        'codex':env.get('EUREKA_CODEX_MODEL','gpt-6-luna'),
                        'availability':'Only a live selected-model invocation can establish account availability'}
    checks['python'] = {'version':sys.version,'executable':sys.executable}
    return checks


def configuration(args, previous=None):
    project = args.project.resolve()
    env = environment(project)
    values = dict(previous or {'project':str(project),'backend':args.backend,'profile':args.profile})
    if previous and args.backend and args.backend!=previous['backend']:
        raise ValueError('Resume retains its backend; start a new run to change providers')
    for key in ('model','mode','max_minutes','max_calls','max_cycles','publish','owner','repository','executable'):
        value = getattr(args,key,None)
        if value is None and not previous:
            variable = f'EUREKA_{args.backend.upper()}_MODEL' if key=='model' else f'EUREKA_{key.upper()}'
            value = env.get(variable)
            if value is not None:
                if key=='max_minutes': value = float(value)
                if key in ('max_calls','max_cycles'): value = int(value)
                if key=='publish': value = str(value).lower() not in ('false','0','no')
        if value is not None:
            values[key] = value
    if previous and args.model and args.model!=previous['model']:
        raise ValueError('Resume retains its model; start a separate run for a different model')
    return RunConfig(**values)


def inspect_artifacts(args):
    """A public clone can regenerate evidence without private SQLite conversations."""
    project = args.project.resolve()
    recorded = None
    if (project/'.eureka/state.sqlite3').exists():
        store = Store(project)
        try:
            recorded = store.get(args.run_id)
        except ValueError:
            if args.run_id:
                raise
        finally:
            store.close()
    cycles = sorted(path for path in (project/'cycles').glob('*') if path.is_dir() and path.name.isdigit())
    if not cycles:
        raise ValueError('No recorded cycle directory')
    number = args.cycle or (recorded['cycle'] if recorded else int(cycles[-1].name))
    cycle = project/'cycles'/f'{number:03d}'
    if args.command=='render':
        summaries = sorted((project/'reports').glob('run-*.json'))
        backend = getattr(args,'backend',None) or (recorded['config']['backend'] if recorded else
                   read_json(summaries[-1]).get('backend') if summaries else None)
        return render(project,cycle,backend={'claude':'Claude Code','codex':'Codex'}.get(backend,'an unrecorded backend'),pdf=not args.no_pdf)
    if recorded:
        store = Store(project)
        completed = {p['name']:p['result'] for p in store.phases(recorded['id'],number)}
        store.close()
    else:
        history = cycle/'research/decisions.jsonl'
        completed = {row['phase']:{key:value for key,value in row.items() if key not in ('phase','at')}
                     for line in history.read_text(encoding='utf-8').splitlines() if (row:=json.loads(line))} if history.exists() else {}
    errors = {phase:verify_phase(phase,cycle,handoff) for phase,handoff in completed.items()}
    return {'cycle':number,'phases':errors,'complete':set(completed)==set(PHASES) and not any(errors.values()),
            'state_source':'private SQLite' if recorded else 'public artifact history'}


def main():
    # Windows redirected consoles may default to a legacy code page; logs stay UTF-8.
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):
            stream.reconfigure(encoding='utf-8',errors='backslashreplace')
    args = parser().parse_args()
    project = args.project.resolve()
    try:
        if args.command=='doctor':
            result = doctor(project,args.backend)
        elif args.command in ('verify','render'):
            result = inspect_artifacts(args)
        elif args.command=='init':
            task = args.task.read_text(encoding='utf-8-sig') if args.task else ''
            initialize(project,profile=args.profile,task=task)
            prepare_cycle(project,1,args.profile)
            result = {'project':str(project),'profile':args.profile,'status':'initialized'}
        elif args.command=='run':
            config = configuration(args)
            task = args.task.read_text(encoding='utf-8-sig')
            initialize(project,profile=config.profile,task=task)
            prepare_cycle(project,1,config.profile)
            store = Store(project)
            run_id = store.create(config,task,policy_hash())
            result = asyncio.run(Controller(store,run_id).run())
            store.close()
        else:
            store = Store(project)
            run = store.get(args.run_id)
            if args.command=='resume':
                if run['status']=='complete':
                    raise ValueError('Run is already complete; start another run for new research')
                config = configuration(args,run['config'])
                store.update(run['id'],config=config.to_dict())
                result = asyncio.run(Controller(store,run['id']).run())
            elif args.command=='status':
                result = {key:run[key] for key in ('id','status','cycle','phase_index','calls','elapsed','message','config')}
                result['next_phase'] = PHASES[run['phase_index']] if run['phase_index']<len(PHASES) else None
            elif args.command=='stop':
                store.update(run['id'],stop=1)
                result = {'id':run['id'],'stop_requested':True}
            store.close()
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        if args.command=='verify':
            return 0 if result['complete'] else 2
        return 0 if not isinstance(result,dict) or result.get('status') not in ('blocked','budget_exhausted','interrupted') else 2
    except (ValueError,OSError,RuntimeError) as exc:
        print(f'eureka: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
