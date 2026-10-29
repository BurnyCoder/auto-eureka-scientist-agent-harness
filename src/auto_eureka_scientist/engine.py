"""A small durable phase loop. Each inference is fresh; artifacts carry the memory.

Design reference: https://www.anthropic.com/research/effective-harnesses-for-long-running-agents
The controller verifies observable contracts, not the truth of arbitrary research.
"""
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import threading
import time

from .adapters import invocation, model_error, parse_response
from .config import RunConfig, environment
from .contracts import PHASES
from .execution import execute
from .phases import artifact_hashes, make_prompt, verify_phase
from .policy import policy_hash
from .publication import Publisher, commit, install_pages_workflow
from .reporting import render
from .science import experiments, snapshot_evidence
from .state import Store
from .util import digest, log, now, read_json, write_json
from .workspace import prepare_cycle, preserve_artifact_bytes


def register_protocol(cycle: Path, commit_sha: str) -> dict:
    """Freeze an immutable copy before any result, retaining earlier hypotheses."""
    protocol = cycle/'research/protocol.json'
    receipt_path = cycle/'research/registration.json'
    fingerprint = digest(protocol)
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if receipt['protocol_sha256'] != fingerprint:
            raise ValueError('Protocol changed after registration; open a new cycle with untouched evaluation data')
        return receipt
    if experiments(cycle):
        raise ValueError('Cannot preregister after results already exist')
    archive = cycle/'research/protocol-history'/f'{fingerprint}.json'
    archive.parent.mkdir(parents=True,exist_ok=True)
    archive.write_bytes(protocol.read_bytes())
    receipt = {'registered_at':now(),'protocol_sha256':fingerprint,'commit':commit_sha}
    write_json(receipt_path,receipt)
    return receipt


class Controller:
    def __init__(self, store: Store, run_id: str, *, publisher=None, echo=True):
        self.store,self.run_id = store,run_id
        row = store.get(run_id)
        self.config = RunConfig(**row['config'])
        self.project = Path(self.config.project)
        self.started = time.monotonic()
        self.consumed = row['elapsed']
        self.echo = echo
        self.publisher = publisher or Publisher(self.config,store,run_id,self.remaining)
        self.done = threading.Event()

    def remaining(self):
        limit = self.config.max_minutes
        return float('inf') if limit is None else max(0,limit*60-self.consumed-(time.monotonic()-self.started))

    def limit_reason(self, *, call=False):
        row = self.store.get(self.run_id)
        if row['stop']:
            return 'stop requested'
        if self.remaining() <= 0:
            return 'time budget exhausted'
        if call and self.config.max_calls is not None and row['calls'] >= self.config.max_calls:
            return 'call budget exhausted'
        return ''

    def heartbeat(self):
        # Persist active wall time even if the controller is killed, with one-second granularity.
        while not self.done.wait(1):
            self.store.update(self.run_id,elapsed=self.consumed+time.monotonic()-self.started)

    async def check_command(self, cycle: Path):
        check = read_json(cycle/'research/checks.json')
        cwd = cycle if check.get('cwd') == 'cycle' else self.project
        result = await execute(check['command'],'',cwd,self.project/'.eureka'/self.run_id/'checks',
                               time.monotonic()+self.remaining(),lambda:bool(self.store.get(self.run_id)['stop']),echo=self.echo)
        if result.returncode or result.reason != 'exited':
            raise ValueError(f'Core checks failed: {asdict(result)}')
        write_json(cycle/'research/core-checks.json',{'command':check['command'],'at':now(),**asdict(result)})

    async def finalize(self, phase: str, cycle: Path, handoff: dict):
        """Publication errors resume here without paying for another model response."""
        number = self.store.get(self.run_id)['cycle']
        snapshot_evidence(cycle)
        if phase == 'preregister':
            sha = commit(self.project,f'Preregister research cycle {number} before results')
            register_protocol(cycle,sha)
        if phase == 'core':
            if (cycle/'study.py').exists():
                write_json(cycle/'research/core-code.json',{'sha256':digest(cycle/'study.py'),'at':now()})
            receipt = self.publisher.checkpoint(number,'core')
            write_json(cycle/'research/core-publication.json',receipt)
            self.publisher.branch(number,'pilot')
        if phase in ('pilot','analysis','publish'):
            self.write_summary()
            render(self.project,cycle,backend='Claude Code' if self.config.backend=='claude' else 'Codex',
                   timeout=min(180,self.remaining()),cancelled=lambda:bool(self.store.get(self.run_id)['stop']))
        if phase in ('pilot','publish'):
            model_files = list((cycle/'models').glob('*.safetensors'))+list((cycle/'models').glob('*.npz'))
            if model_files:
                models = self.publisher.models(cycle,phase)
            elif self.config.profile == 'digits':
                raise ValueError('Digits validation requires a real checkpoint')
            else:
                explanation = next((item['reason'] for item in handoff['not_applicable'] if item['requirement']=='model_uploads'),'')
                if not explanation:
                    raise ValueError('Explain model_uploads in not_applicable when no model was trained')
                models = {'not_applicable':explanation}
            install_pages_workflow(self.project)
            pages = self.publisher.enable_pages()
            receipt = self.publisher.checkpoint(number,phase)
            write_json(cycle/f'research/{phase}-publication.json',{'github':receipt,'models':models,'pages':pages})
            if phase == 'pilot':
                self.publisher.branch(number,'final')
            errors = verify_phase(phase,cycle,handoff)
            if errors:
                raise ValueError('Post-publication artifact verification failed: '+'; '.join(errors))
        self.store.complete_phase(self.run_id,phase,handoff,artifact_hashes(cycle))
        # The append-only handoff history retains revisited phases as separate observations.
        record = {'at':now(),'phase':phase,**handoff}
        decisions = cycle/'research/decisions.jsonl'
        import json
        with decisions.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(record,ensure_ascii=False)+'\n')

    async def phase(self, phase: str, cycle: Path):
        key = f'pending:{self.store.get(self.run_id)["cycle"]}:{phase}'
        errors = []
        previous = [a for a in self.store.attempts(self.run_id) if a['cycle']==self.store.get(self.run_id)['cycle'] and a['phase']==phase]
        if previous and previous[-1]['result']:
            errors = json.loads(previous[-1]['result']).get('errors',[])
        # A controller may crash after the CLI has finished but before its result commits.
        # Recover only a complete provider terminal event, then revalidate the files.
        unfinished = [a for a in self.store.attempts(self.run_id) if a['cycle']==self.store.get(self.run_id)['cycle']
                      and a['phase']==phase and a['status']=='running']
        if unfinished and not self.store.receipt(self.run_id,key):
            attempt = unfinished[-1]
            logs = self.project/'.eureka'/self.run_id/f'{attempt["id"]:04d}-{phase}'
            raw = logs/'stdout.jsonl'
            terminal = False
            if raw.exists():
                with raw.open(encoding='utf-8') as stream:
                    for line in stream:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(event,dict) and (event.get('type')=='turn.completed' or
                            (event.get('type')=='result' and not event.get('is_error'))):
                            terminal = True
            if terminal:
                response = parse_response(self.config.backend,logs)
                errors = [e for e in (response.error,model_error(self.config,response)) if e]
                errors += verify_phase(phase,cycle,response.value) if not errors else []
                if not errors:
                    if phase=='core':
                        await self.check_command(cycle)
                    execution = read_json(logs/'execution.json') if (logs/'execution.json').exists() else None
                    audit = {'recovered_from_terminal_event':True,'execution':execution,'errors':[],
                             'models':response.models,'usage':response.usage,'searched':response.searched,
                             'handoff':response.value,'model_identity_status':'reported' if response.models else 'not exposed'}
                    self.store.finish_attempt(attempt['id'],'accepted',audit)
                    write_json(logs/'outcome.json',audit)
                    self.store.receipt(self.run_id,key,{'handoff':response.value})
                else:
                    self.store.finish_attempt(attempt['id'],'failed',{'errors':errors,'models':response.models,
                                              'usage':response.usage,'handoff':response.value,'recovered_from_terminal_event':True})
        pending = self.store.receipt(self.run_id,key)
        if pending and not pending.get('consumed'):
            errors = verify_phase(phase,cycle,pending['handoff'])
            if not errors:
                await self.finalize(phase,cycle,pending['handoff'])
                self.store.receipt(self.run_id,key,{'consumed':True})
                return pending['handoff']
        repairs,transports = 0,0
        while True:
            if reason := self.limit_reason(call=True):
                raise InterruptedError(reason)
            run = self.store.get(self.run_id)
            prompt = make_prompt(run,phase,cycle,self.store.phases(self.run_id),errors)
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
            attempt = self.store.begin_attempt(self.run_id,phase,prompt_hash)
            logs = self.project/'.eureka'/self.run_id/f'{attempt:04d}-{phase}'
            argv,env = invocation(self.config,logs,environment(self.project))
            write_json(logs/'invocation.json',{'argv':argv,'prompt_sha256':prompt_hash,'at':now(),
                                              'requested_model':self.config.model,'backend':self.config.backend})
            log(f'{self.run_id}: cycle {run["cycle"]}, {phase}, CLI call {run["calls"]+1}')
            execution = await execute(argv,prompt,self.project,logs,time.monotonic()+self.remaining(),
                                      lambda:bool(self.store.get(self.run_id)['stop']),env=env,echo=self.echo)
            write_json(logs/'execution.json',asdict(execution))
            response = parse_response(self.config.backend,logs)
            errors = [error for error in (response.error,model_error(self.config,response)) if error]
            if execution.returncode:
                stderr = (logs/'stderr.log').read_text(encoding='utf-8',errors='replace')
                errors.append(f'CLI exited {execution.returncode}: {stderr}')
            if execution.reason != 'exited':
                self.store.finish_attempt(attempt,execution.reason,{'execution':asdict(execution)})
                raise InterruptedError(execution.reason)
            if not errors:
                errors = verify_phase(phase,cycle,response.value,fetch=phase=='research')
                if not errors and phase=='core':
                    try:
                        await self.check_command(cycle)
                    except ValueError as exc:
                        errors.append(str(exc))
                if self.config.profile=='digits' and phase=='research' and not response.searched:
                    errors.append('Digits trial research requires an observed native web search/fetch tool event')
                if self.config.profile=='digits' and phase=='experiments':
                    required = {f'{method}_s{seed}' for method in ('regularized','unregularized','sensitivity','shuffled_labels') for seed in (0,1,2)}|{'logistic_s0','class_prior_s0','pilot_regularized_s0'}
                    missing = required-{r.get('id') for r in experiments(cycle) if isinstance(r,dict)}
                    if missing:
                        errors.append(f'Missing registered comparisons: {sorted(missing)}')
            audit = {'execution':asdict(execution),'errors':errors,'models':response.models,
                     'model_identity_status':'reported' if response.models else 'not exposed by CLI; requested identifier only',
                     'usage':response.usage,'searched':response.searched,'handoff':response.value}
            write_json(logs/'outcome.json',audit)
            self.store.finish_attempt(attempt,'failed' if errors else 'accepted',audit)
            if not errors:
                self.store.receipt(self.run_id,key,{'handoff':response.value})
                await self.finalize(phase,cycle,response.value)
                self.store.receipt(self.run_id,key,{'consumed':True})
                return response.value
            log('Phase requires repair: '+'; '.join(errors))
            if model_error(self.config,response) or re.search(r'model.*(not found|not available|does not exist|unsupported)|not authenticated|invalid api key',str(errors),re.I):
                raise RuntimeError('; '.join(errors))
            transient = re.search(r'429|502|503|504|connection reset|transport error|temporarily unavailable|rate limit',str(errors),re.I)
            if transient:
                transports += 1
                if transports>2:
                    raise RuntimeError('Transport retries exhausted: '+'; '.join(errors))
                await asyncio.sleep(min(2**transports,self.remaining()))
            else:
                repairs += 1
                if repairs>2:
                    raise RuntimeError('Targeted repairs exhausted: '+'; '.join(errors))

    async def run(self):
        self.store.acquire(self.run_id)
        heartbeat = threading.Thread(target=self.heartbeat,daemon=True)
        heartbeat.start()
        try:
            if self.store.get(self.run_id)['policy_hash'] != policy_hash():
                raise ValueError('Canonical policy changed; preserve the original run or start a new run')
            if reason := self.limit_reason():
                raise InterruptedError(reason)
            preserve_artifact_bytes(self.project)
            self.publisher.bootstrap()
            while True:
                row = self.store.get(self.run_id)
                cycle = prepare_cycle(self.project,row['cycle'],self.config.profile)
                if row['phase_index'] == 0:
                    self.publisher.branch(row['cycle'],'core')
                if row['phase_index'] >= len(PHASES):
                    if self.config.mode == 'cycle' or (self.config.max_cycles and row['cycle']>=self.config.max_cycles):
                        self.store.update(self.run_id,status='complete',message='All required phases completed')
                        # The phase publication precedes its acceptance record. Publish a
                        # final snapshot too, so public clones can verify the final phase.
                        self.store.update(self.run_id,elapsed=self.consumed+time.monotonic()-self.started)
                        self.write_summary()
                        render(self.project,cycle,backend='Claude Code' if self.config.backend=='claude' else 'Codex',
                               timeout=min(180,self.remaining()),cancelled=lambda:bool(self.store.get(self.run_id)['stop']))
                        self.publisher.branch(row['cycle'],'summary')
                        self.publisher.checkpoint(row['cycle'],'summary')
                        errors = [error for saved in self.store.phases(self.run_id)
                                  for error in verify_phase(saved['name'],cycle,saved['result'])]
                        if errors:
                            raise ValueError('Final artifact verification failed: '+'; '.join(errors))
                        break
                    self.store.update(self.run_id,cycle=row['cycle']+1,phase_index=0)
                    continue
                if reason := self.limit_reason():
                    raise InterruptedError(reason)
                phase = PHASES[row['phase_index']]
                result = await self.phase(phase,cycle)
                next_index = row['phase_index']+1
                if result['decision']=='revisit':
                    next_index = PHASES.index(result['revisit_phase'])
                    if next_index>=row['phase_index']:
                        raise ValueError('Revisit must name an earlier phase')
                    if next_index<=1 and experiments(cycle):
                        self.store.update(self.run_id,cycle=row['cycle']+1,phase_index=0,
                                          message='New cycle required for revised hypothesis; earlier results retained')
                        continue
                self.store.update(self.run_id,phase_index=next_index)
        except InterruptedError as exc:
            self.store.update(self.run_id,status='stopped' if 'stop' in str(exc) else 'budget_exhausted',message=str(exc))
        except (KeyboardInterrupt,asyncio.CancelledError):
            self.store.update(self.run_id,status='interrupted',message='Interrupted; owned CLI processes terminated')
        except Exception as exc:
            reason = self.limit_reason()
            self.store.update(self.run_id,status=('stopped' if 'stop' in reason else 'budget_exhausted') if reason else 'blocked',message=reason or str(exc))
            log(f'Resumable failure: {exc}')
        finally:
            self.done.set()
            heartbeat.join(timeout=2)
            self.store.update(self.run_id,elapsed=self.consumed+time.monotonic()-self.started,owner_pid=0,owner_start=0)
            self.write_summary()
        return self.store.get(self.run_id)

    def write_summary(self):
        """Publishable metadata intentionally excludes raw prompts, output and secrets."""
        run = self.store.get(self.run_id)
        import json
        attempts = []
        for row in self.store.attempts(self.run_id):
            result = json.loads(row['result']) if row['result'] else {}
            attempts.append({'id':row['id'],'cycle':row['cycle'],'phase':row['phase'],'status':row['status'],
                             'started':row['started'],'ended':row['ended'],'prompt_sha256':row['prompt'],
                             'models':result.get('models',[]),'model_identity_status':result.get('model_identity_status'),
                             'usage':result.get('usage',{}),'searched':result.get('searched',False)})
        write_json(self.project/'reports'/f'run-{self.run_id}.json',{
            'id':self.run_id,'backend':self.config.backend,'requested_model':self.config.model,
            'status':run['status'],'message':run['message'],'calls':run['calls'],'active_seconds':run['elapsed'],
            'limits':{'minutes':self.config.max_minutes,'calls':self.config.max_calls},
            'policy_sha256':run['policy_hash'],'completed_phases':[p['name'] for p in self.store.phases(self.run_id)],
            'attempts':attempts})
