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

from .adapters import invocation, model_error, parse_response, terminal_event
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
from .operator import OperatorRuntime
from .events import EventSink


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


class Controller(OperatorRuntime):
    def __init__(self, store: Store, run_id: str, *, publisher=None, echo=True):
        self.store,self.run_id = store,run_id
        row = store.get(run_id)
        self.config = RunConfig(**row['config'])
        effective=store.receipt(run_id,'effective_settings') or {}
        from .settings import schema
        for key,definition in schema()['properties'].items():
            if definition['x-apply']=='next cycle' and key in effective:
                setattr(self.config,key,effective[key])
        self.project = Path(self.config.project)
        self.started = time.monotonic()
        self.consumed = row['elapsed']
        self.echo = echo
        self.publisher = publisher or Publisher(self.config,store,run_id,self.remaining)
        self.done = threading.Event()
        if isinstance(self.publisher,Publisher): self.publisher.cancelled=self.cancellation

    def remaining(self):
        limit = self.config.max_minutes
        return float('inf') if limit is None else max(0,limit*60-self.consumed-(time.monotonic()-self.started))

    def limit_reason(self, *, call=False):
        row = self.store.get(self.run_id)
        if row['stop']:
            return 'stop requested'
        if self.remaining() <= 0:
            return 'time budget exhausted'
        if self.config.max_loops is not None and row['loops_completed']>=self.config.max_loops and row['phase_index']<len(PHASES):
            return 'completed-loop budget exhausted'
        if self.config.max_cycles is not None and row['cycles_started']>self.config.max_cycles:
            return 'started-cycle budget exhausted'
        if call and self.config.max_calls is not None and row['calls'] >= self.config.max_calls:
            return 'call budget exhausted'
        return ''

    def heartbeat(self):
        # Persist active wall time even if the controller is killed, with one-second granularity.
        while not self.done.wait(self.config.heartbeat_seconds):
            self.refresh()
            self.store.update(self.run_id,elapsed=self.consumed+time.monotonic()-self.started)

    async def check_command(self, cycle: Path):
        # Preserve the agent's cited output before a repeat check or our receipt replaces it.
        snapshot_evidence(cycle)
        check = read_json(cycle/'research/checks.json')
        cwd = cycle if check.get('cwd') == 'cycle' else self.project
        result = await execute(check['command'],'',cwd,self.project/'.eureka'/self.run_id/'checks',
                               time.monotonic()+min(self.remaining(),self.config.command_timeout),self.cancellation,echo=self.echo,
                               emit=EventSink(self.store,self.run_id,phase='core-check'),termination_grace=self.config.termination_grace)
        if result.returncode or result.reason != 'exited':
            if result.reason in ('paused','stopped','interrupt_requested','skip_requested','revision_requested'):
                raise InterruptedError(result.reason)
            if result.reason=='budget_exhausted' and self.remaining()<=0:
                raise InterruptedError('time budget exhausted')
            raise ValueError(f'Core checks failed: {asdict(result)}')
        write_json(cycle/'research/core-checks.json',{'command':check['command'],'at':now(),**asdict(result)})

    async def finalize(self, phase: str, cycle: Path, handoff: dict):
        """Publication errors resume here without paying for another model response."""
        number = self.store.get(self.run_id)['cycle']
        if phase in ('core','pilot','publish'):
            self.gate(f'publication-gate:{number}:{phase}',self.config.pause_before_publication)
        self.emit('phase.finalizing',phase=phase)
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
                   timeout=min(self.config.render_timeout,self.remaining()),cancelled=self.cancellation,
                   figure_dpi=self.config.figure_dpi,figure_format=self.config.preview_format)
        if phase in ('pilot','publish'):
            model_files = list((cycle/'models').glob('*.safetensors'))+list((cycle/'models').glob('*.npz'))
            if model_files:
                models = self.publisher.models(cycle,phase)
            elif self.config.profile.startswith('digits'):
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
        self.emit('phase.accepted',phase=phase,handoff=handoff)
        # The append-only handoff history retains revisited phases as separate observations.
        record = {'at':now(),'phase':phase,**handoff}
        decisions = cycle/'research/decisions.jsonl'
        import json
        with decisions.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(record,ensure_ascii=False)+'\n')

    async def phase(self, phase: str, cycle: Path):
        key = f'pending:{self.store.get(self.run_id)["cycle"]}:{phase}'
        errors = []
        previous = self.store.attempts(self.run_id,cycle=self.store.get(self.run_id)['cycle'],phase=phase)
        if previous and previous[-1]['result']:
            errors = json.loads(previous[-1]['result']).get('errors',[])
        # A controller may crash after the CLI has finished but before its result commits.
        # Recover only a complete provider terminal event, then revalidate the files.
        unfinished = [a for a in previous if a['status']=='running']
        if unfinished and not self.store.receipt(self.run_id,key):
            attempt = unfinished[-1]
            logs = self.project/'.eureka'/self.run_id/f'{attempt["id"]:04d}-{phase}'
            if terminal_event(self.config.backend,logs):
                response = parse_response(self.config.backend,logs)
                errors = [e for e in (response.error,model_error(self.config,response)) if e]
                errors += self.check_outputs(phase,cycle,response.value,response.searched) if not errors else []
                if not errors:
                    if phase=='core':
                        await self.check_command(cycle)
                    execution = read_json(logs/'execution.json') if (logs/'execution.json').exists() else None
                    audit = {'recovered_from_terminal_event':True,'execution':execution,'errors':[],
                             'models':response.models,'usage':response.usage,'searched':response.searched,
                             'handoff':response.value,'model_identity_status':'reported' if response.models else 'not exposed'}
                    self.store.finish_attempt(attempt['id'],'accepted',audit)
                    write_json(logs/'outcome.json',audit)
                    self.store.receipt(self.run_id,key,{'handoff':response.value,'searched':response.searched})
                else:
                    self.store.finish_attempt(attempt['id'],'failed',{'errors':errors,'models':response.models,
                                              'usage':response.usage,'handoff':response.value,'recovered_from_terminal_event':True})
        pending = self.store.receipt(self.run_id,key)
        if pending and pending.get('consumed'):
            accepted = next((p for p in self.store.phases(self.run_id) if p['name']==phase),None)
            if accepted and not verify_phase(phase,cycle,accepted['result']):
                return accepted['result']
        if pending and not pending.get('consumed'):
            searched = pending.get('searched',any(json.loads(a['result'] or '{}').get('searched') for a in previous))
            errors = self.check_outputs(phase,cycle,pending['handoff'],searched)
            if not errors:
                await self.finalize(phase,cycle,pending['handoff'])
                self.store.receipt(self.run_id,key,{'consumed':True})
                return pending['handoff']
        repairs,transports = 0,0
        while True:
            self.refresh('next invocation')
            await self.controls(cycle)
            await self.chat()
            if reason := self.limit_reason(call=True):
                raise InterruptedError(reason)
            run = self.prompt_context(self.store.get(self.run_id))
            prompt = make_prompt(run,phase,cycle,self.store.phases(self.run_id),errors)
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
            attempt = self.store.begin_attempt(self.run_id,phase,prompt_hash)
            self.store.deliver_messages(self.run_id,attempt)
            logs = self.project/'.eureka'/self.run_id/f'{attempt:04d}-{phase}'
            argv,env = invocation(self.config,logs,environment(self.project))
            write_json(logs/'invocation.json',{'argv':argv,'prompt_sha256':prompt_hash,'at':now(),
                                              'requested_model':self.config.model,'model_pin':self.config.model_pin,'backend':self.config.backend})
            log(f'{self.run_id}: cycle {run["cycle"]}, {phase}, CLI call {run["calls"]+1}')
            self.emit('phase.started',phase=phase,attempt=attempt)
            execution = await execute(argv,prompt,self.project,logs,
                                      time.monotonic()+min(self.remaining(),self.config.invocation_timeout or float('inf')),
                                      self.cancellation,env=env,echo=self.echo,
                                      emit=EventSink(self.store,self.run_id,phase=phase,attempt=attempt,cycle=run['cycle']),
                                      no_output_timeout=self.config.no_output_timeout,termination_grace=self.config.termination_grace)
            write_json(logs/'execution.json',asdict(execution))
            response = parse_response(self.config.backend,logs)
            errors = [error for error in (response.error,model_error(self.config,response)) if error]
            if execution.returncode:
                stderr = (logs/'stderr.log').read_text(encoding='utf-8',errors='replace')
                errors.append(f'CLI exited {execution.returncode}: {stderr}')
            if execution.reason != 'exited':
                self.store.finish_attempt(attempt,execution.reason,{'execution':asdict(execution)})
                if execution.reason=='no_output_timeout' or (execution.reason=='budget_exhausted' and self.remaining()>0):
                    raise RuntimeError('CLI invocation timeout: '+execution.reason)
                raise InterruptedError(execution.reason)
            if not errors:
                errors = self.check_outputs(phase,cycle,response.value,response.searched)
                if not errors and phase=='core':
                    try:
                        await self.check_command(cycle)
                    except ValueError as exc:
                        errors.append(str(exc))
            audit = {'execution':asdict(execution),'errors':errors,'models':response.models,
                     'model_identity_status':'reported' if response.models else 'not exposed by CLI; requested identifier only',
                     'usage':response.usage,'searched':response.searched,'handoff':response.value}
            write_json(logs/'outcome.json',audit)
            self.store.finish_attempt(attempt,'failed' if errors else 'accepted',audit)
            self.emit('verification.result',phase=phase,attempt=attempt,errors=errors,usage=response.usage,models=response.models)
            if not errors:
                self.store.receipt(self.run_id,key,{'handoff':response.value,'searched':response.searched})
                await self.finalize(phase,cycle,response.value)
                self.store.receipt(self.run_id,key,{'consumed':True})
                return response.value
            log('Phase requires repair: '+'; '.join(errors))
            if model_error(self.config,response) or re.search(r'model.*(not found|not available|does not exist|unsupported)|not authenticated|invalid api key',str(errors),re.I):
                raise RuntimeError('; '.join(errors))
            transient = re.search(r'429|502|503|504|connection reset|transport error|temporarily unavailable|rate limit',str(errors),re.I)
            if transient:
                transports += 1
                if transports>self.config.transport_retries:
                    raise RuntimeError('Transport retries exhausted: '+'; '.join(errors))
                delay=min(self.config.retry_delay*self.config.retry_multiplier**(transports-1),self.config.retry_max,self.remaining())
                self.emit('retry.waiting',seconds=delay,attempt=attempt)
                await self.delay(delay)
            else:
                repairs += 1
                if repairs>self.config.repair_retries:
                    raise RuntimeError('Targeted repairs exhausted: '+'; '.join(errors))

    def check_outputs(self, phase, cycle, handoff, searched):
        """Use the same research checks for fresh responses and crash recovery."""
        errors = verify_phase(phase,cycle,handoff,fetch=phase=='research')
        if self.config.profile.startswith('digits'):
            if phase=='research' and not searched:
                errors.append('Digits trial research requires an observed native web search/fetch tool event')
            if phase=='experiments':
                required = {f'{method}_s{seed}' for method in ('regularized','unregularized','sensitivity','shuffled_labels') for seed in (0,1,2)}|{'logistic_s0','class_prior_s0','pilot_regularized_s0'}
                missing = required-{r.get('id') for r in experiments(cycle)}
                if missing:
                    errors.append(f'Missing registered comparisons: {sorted(missing)}')
        return errors

    async def complete_loop(self,cycle):
        """Finalize every cycle, including continuous runs, before advancing the queue."""
        row=self.store.get(self.run_id)
        key=f'loop-finalized:{row["cycle"]}'
        if self.store.receipt(self.run_id,key): return
        with self.store.lock:
            completed=self.store.db.execute("SELECT 1 FROM cycle_outcomes WHERE run_id=? AND cycle=? AND status='complete'",(self.run_id,row['cycle'])).fetchone()
        if completed:
            self.store.receipt(self.run_id,key,{'complete':True})
            return
        saved=self.store.phases(self.run_id)
        errors=[error for phase in saved for error in verify_phase(phase['name'],cycle,phase['result'])]
        if set(p['name'] for p in saved)!=set(PHASES): errors.append('Not all phases have been accepted')
        if errors: raise ValueError('Final artifact verification failed: '+'; '.join(errors))
        self.store.update(self.run_id,status='finalizing',elapsed=self.consumed+time.monotonic()-self.started)
        self.write_summary()
        render(self.project,cycle,backend='Claude Code' if self.config.backend=='claude' else 'Codex',
               timeout=min(self.config.render_timeout,self.remaining()),cancelled=self.cancellation,
               figure_dpi=self.config.figure_dpi,figure_format=self.config.preview_format)
        self.publisher.branch(row['cycle'],'summary')
        self.publisher.checkpoint(row['cycle'],'summary')
        # A crash between these writes is harmless: both markers are idempotent.
        self.store.finish_cycle(self.run_id,'complete')
        self.store.receipt(self.run_id,key,{'complete':True})

    def schedule_cycle(self, *, status, carry=False):
        self.store.finish_cycle(self.run_id,status,advance=True,carry=carry)

    async def run(self, *, maintenance=False):
        previous_status=self.store.get(self.run_id)['status']
        self.store.acquire(self.run_id)
        self.emit('run.started',maintenance=maintenance)
        heartbeat = threading.Thread(target=self.heartbeat,daemon=True)
        heartbeat.start()
        try:
            if self.store.get(self.run_id)['policy_hash'] != policy_hash():
                raise ValueError('Canonical policy changed; preserve the original run or start a new run')
            if reason := self.limit_reason():
                raise InterruptedError(reason)
            preserve_artifact_bytes(self.project)
            if not maintenance: self.publisher.bootstrap()
            active_cycle=(self.store.receipt(self.run_id,'applied-cycle') or {}).get('cycle')
            while True:
                row = self.store.get(self.run_id)
                revision = self.store.receipt(self.run_id,'next-cycle') or self.store.receipt(self.run_id,'revised-hypothesis-cycle')
                if revision and revision.get('from_cycle')==row['cycle']:
                    if self.config.max_cycles and row['cycles_started']>=self.config.max_cycles:
                        raise InterruptedError('cycle budget exhausted before revised hypothesis')
                    self.store.advance_cycle(self.run_id,
                        message='Starting next cycle; earlier results retained',carry_spec=revision.get('carry',True))
                    continue
                self.refresh('next cycle' if active_cycle!=row['cycle'] else 'immediate')
                active_cycle=row['cycle']
                if self.store.active_spec(self.run_id) is None and not maintenance:
                    raise InterruptedError('paused: no enabled specs')
                cycle = prepare_cycle(self.project,row['cycle'],self.config.profile,self.config.to_dict())
                try:
                    await self.controls(cycle)
                    await self.chat()
                    if maintenance:
                        self.store.update(self.run_id,status=previous_status,message='Requested maintenance completed')
                        break
                    if reason := self.limit_reason(): raise InterruptedError(reason)
                    if row['phase_index']>=len(PHASES):
                        await self.complete_loop(cycle)
                        row=self.store.get(self.run_id)
                        if self.config.mode=='cycle' or (self.config.max_loops and row['loops_completed']>=self.config.max_loops) or (self.config.max_cycles and row['cycles_started']>=self.config.max_cycles):
                            self.store.update(self.run_id,status='complete',message='Requested verified loops completed')
                            break
                        if self.config.stop_after=='cycle': raise InterruptedError('stop after cycle')
                        self.store.update(self.run_id,status='running')
                        await self.delay(self.config.cycle_delay)
                        self.schedule_cycle(status='complete')
                        continue
                    if row['phase_index']==0: self.publisher.branch(row['cycle'],'core')
                    phase=PHASES[row['phase_index']]
                    self.refresh('next invocation')
                    self.gate(f'phase-gate:{row["cycle"]}:{phase}',phase in self.config.pause_before)
                    result=await self.phase(phase,cycle)
                    next_index=row['phase_index']+1
                    if result['decision']=='revisit':
                        next_index=PHASES.index(result['revisit_phase'])
                        if next_index>=row['phase_index']: raise ValueError('Revisit must name an earlier phase')
                        if next_index<=1 and experiments(cycle):
                            self.schedule_cycle(status='revised',carry=True)
                            continue
                    self.store.navigate(self.run_id,next_index,revisit=result['decision']=='revisit')
                    if self.config.stop_after=='phase': raise InterruptedError('stop after phase')
                    pause=self.store.receipt(self.run_id,'pause_after_phase')
                    if pause and pause.get('enabled'):
                        self.store.receipt(self.run_id,'pause_after_phase',{'enabled':False})
                        raise InterruptedError('paused after phase')
                except InterruptedError as exc:
                    reason=str(exc)
                    if reason=='interrupt_requested':
                        self.finish_controls('interrupt')
                        self.emit('run.interrupted_for_message')
                        continue
                    if reason in ('skip_requested','revision_requested'):
                        self.schedule_cycle(status='skipped' if reason=='skip_requested' else 'revised',carry='latest' if reason=='revision_requested' else False)
                        self.finish_controls('skip','new_cycle')
                        if reason=='skip_requested' and self.store.no_progress(self.run_id):
                            raise InterruptedError('paused: queue exhausted without progress')
                        continue
                    raise
                except Exception as exc:
                    if self.config.failure_policy!='skip' or self.limit_reason() or maintenance: raise
                    self.emit('spec.failed',error=str(exc))
                    self.schedule_cycle(status='skipped')
                    if self.store.no_progress(self.run_id):
                        raise InterruptedError('paused: queue exhausted without progress')
        except InterruptedError as exc:
            self.finish_controls('pause','stop')
            status='paused' if 'pause' in str(exc) else 'stopped' if 'stop' in str(exc) else 'budget_exhausted'
            self.store.update(self.run_id,status=status,message=str(exc))
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
            self.emit('run.finished',status=self.store.get(self.run_id)['status'])
        return self.store.get(self.run_id)

    def write_summary(self):
        """Publishable metadata intentionally excludes raw prompts, output and secrets."""
        run = self.store.get(self.run_id)
        import json
        attempts = []
        history=self.store.receipt(self.run_id,'configuration_history') or {'changes':[]}
        public_keys={'backend','model','model_pin','max_minutes','max_calls','max_cycles','max_loops','mode','profile','publish','failure_policy'}
        history={'changes':[{**change,**{field:{k:v for k,v in change.get(field,{}).items() if k in public_keys}
                   for field in ('previous','updated')}} for change in history['changes']]}
        for row in self.store.attempts(self.run_id):
            result = json.loads(row['result']) if row['result'] else {}
            attempts.append({'id':row['id'],'cycle':row['cycle'],'phase':row['phase'],'status':row['status'],
                             'started':row['started'],'ended':row['ended'],'prompt_sha256':row['prompt'],
                             'models':result.get('models',[]),'model_identity_status':result.get('model_identity_status'),
                             'usage':result.get('usage',{}),'searched':result.get('searched',False)})
        write_json(self.project/'reports'/f'run-{self.run_id}.json',{
            'id':self.run_id,'backend':self.config.backend,'requested_model':self.config.model,
            'model_pin':self.config.model_pin,
            'cycle':run['cycle'],'cycles_started':run['cycles_started'],
            'loops_completed':run['loops_completed'],
            'status':run['status'],'message':run['message'],'calls':run['calls'],'active_seconds':run['elapsed'],
            'limits':{'minutes':self.config.max_minutes,'calls':self.config.max_calls,'loops':self.config.max_loops},
            'configuration_history':history,
            'policy_sha256':run['policy_hash'],'completed_phases':[p['name'] for p in self.store.phases(self.run_id)],
            'attempts':attempts})
