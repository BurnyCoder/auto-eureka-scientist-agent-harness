"""Operator boundaries shared by browser and CLI execution; no second research agent.

Fresh-context calls use the existing provider transport. Questions have their own
schema and accounting records and cannot accept a scientific phase.
"""
from dataclasses import asdict
import hashlib
import json
import time
import asyncio

from .adapters import invocation, parse_response, model_error, terminal_event
from .config import RunConfig, environment
from .contracts import PHASES, object_schema
from .events import EventSink
from .execution import execute
from .policy import policy_bytes
from .settings import schema
from .util import write_json


CHAT_SCHEMA = object_schema({'reply':{'type':'string'},'references':{'type':'array','items':{'type':'string'}}})


class OperatorRuntime:
    def emit(self,kind,**data):
        row=self.store.get(self.run_id)
        self.store.event(self.run_id,kind,{'cycle':row['cycle'],'phase_index':row['phase_index'],**data})

    def refresh(self,boundary='immediate'):
        """Apply only settings whose documented boundary has actually been crossed."""
        desired=self.store.get(self.run_id)['config']
        permitted={'immediate'}
        if boundary in ('next invocation','next cycle'): permitted.add('next invocation')
        if boundary=='next cycle': permitted.add('next cycle')
        values=self.config.to_dict()
        for key,definition in schema()['properties'].items():
            if definition['x-apply'] in permitted and key in desired: values[key]=desired[key]
        spec=self.store.active_spec(self.run_id)
        if spec:
            values.update(spec.get('settings',{}))
        self.config=RunConfig(**values)
        self.publisher.config=self.config
        self.store.receipt(self.run_id,'effective_settings',self.config.to_dict())
        if boundary=='next cycle':
            self.store.receipt(self.run_id,'applied-cycle',{'cycle':self.store.get(self.run_id)['cycle']})

    def cancellation(self):
        """Immediate controls are polled by owned processes, including publication."""
        if self.store.get(self.run_id)['stop']: return 'stopped'
        if self.remaining()<=0: return 'budget_exhausted'
        reasons={'pause':'paused','stop':'stopped','interrupt':'interrupt_requested',
                 'skip':'skip_requested','new_cycle':'revision_requested'}
        for action in self.store.actions(self.run_id):
            if action['kind'] in reasons: return reasons[action['kind']]
        return False

    async def delay(self,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if cancellation:=self.cancellation(): raise InterruptedError(cancellation)
            if self.remaining()<=0: raise InterruptedError('time budget exhausted')
            await asyncio.sleep(min(.1,max(0,deadline-time.monotonic())))

    def gate(self,key,enabled):
        """A persistent gate pauses once; resume passes it without another inference."""
        if not enabled: return
        state=self.store.receipt(self.run_id,key)
        if state is None:
            self.store.receipt(self.run_id,key,{'waiting':True})
            raise InterruptedError('paused at '+key)
        if state.get('waiting'):
            self.store.receipt(self.run_id,key,{'passed':True})

    def finish_controls(self,*kinds):
        for action in self.store.actions(self.run_id):
            if action['kind'] in kinds: self.store.finish_action(action['id'])

    async def controls(self,cycle):
        for action in self.store.actions(self.run_id):
            kind=action['kind']
            if kind in ('pause','stop','skip','new_cycle'):
                raise InterruptedError(self.cancellation())
            try:
                if kind=='interrupt': pass  # At a boundary there is no process left to interrupt.
                elif kind in ('step','pause_after_phase'):
                    self.store.receipt(self.run_id,'pause_after_phase',{'enabled':True})
                elif kind=='stop_after_cycle':
                    self.store.patch_settings(self.run_id,{'stop_after':'cycle'})
                elif kind=='revisit':
                    from .contracts import PHASES
                    phase=action['payload'].get('phase')
                    if phase not in PHASES: raise ValueError('Unknown revisit phase')
                    self.store.add_message(self.run_id,f'Operator requests revisiting {phase}. Use a verified revisit handoff; preserve prior evidence.',kind='steer')
                elif kind=='verify':
                    from .phases import verify_phase
                    errors={p['name']:verify_phase(p['name'],cycle,p['result']) for p in self.store.phases(self.run_id)}
                    self.emit('verification.result',errors=errors)
                elif kind=='render':
                    from .reporting import render
                    self.write_summary()
                    render(self.project,cycle,backend='Claude Code' if self.config.backend=='claude' else 'Codex',
                        timeout=min(self.config.render_timeout,self.remaining()),cancelled=self.cancellation,
                        figure_dpi=self.config.figure_dpi,figure_format=self.config.preview_format)
                    self.emit('render.complete')
                elif kind not in ('resume','retry','publication'):
                    raise ValueError('Unknown control action')
                self.store.finish_action(action['id'])
            except InterruptedError: raise
            except Exception as exc: self.store.finish_action(action['id'],error=str(exc))

    async def chat(self):
        """Answer queued questions using recorded context and the same selected model."""
        for message in self.store.questions(self.run_id):
            self.refresh('next invocation')
            if message['status']=='delivered':
                # A terminal response can be recovered after a worker crash without a
                # second paid call. Incomplete turns fail visibly instead of replaying.
                logs=self.project/'.eureka'/self.run_id/f'{message["attempt"]:04d}-chat'
                response=parse_response(self.config.backend,logs)
                error=response.error or model_error(self.config,response)
                if not terminal_event(self.config.backend,logs): error=error or 'Interrupted question has no completed provider turn'
                import jsonschema
                try: jsonschema.validate(response.value,CHAT_SCHEMA)
                except jsonschema.ValidationError: error=error or 'Interrupted question has no complete reply'
                self.store.answer_message(message['id'],error or response.value['reply'],message['attempt'],failed=bool(error))
                self.store.finish_attempt(message['attempt'],'failed' if error else 'accepted',
                    {'recovered':True,'errors':[error] if error else [],'usage':response.usage,'models':response.models})
                continue
            if reason:=self.limit_reason(call=True): raise InterruptedError(reason)
            run=self.store.get(self.run_id)
            spec=self.store.active_spec(self.run_id)
            history=[{'kind':m['kind'],'text':m['text'],'answer':m['answer']} for m in self.store.messages(self.run_id,limit=self.config.history_page_size) if m['id']!=message['id']]
            context=json.dumps(history,ensure_ascii=False)[-self.config.chat_history_chars:] if self.config.chat_history_chars else ''
            prompt=(policy_bytes().decode('utf-8-sig')+'\n--- HARNESS CHAT QUESTION ---\n'
                'Answer the question from the supplied recorded context. This is a Q&A turn, not a research phase. '
                'Do not change files, run experiments, publish, invoke other agents, or claim new observations. '
                'You may inspect referenced project artifacts to explain them. Distinguish recorded facts from inference.\n'
                f'Current spec: {json.dumps(spec,ensure_ascii=False)}\n'
                f'Run state: {json.dumps({k:run[k] for k in ("status","cycle","phase_index","calls","elapsed","message")})}\n'
                f'Next phase: {PHASES[run["phase_index"]] if run["phase_index"]<len(PHASES) else "Final verification and completion"}\n'
                f'Accepted phases: {json.dumps(self.store.phases(self.run_id),ensure_ascii=False)}\n'
                f'Recent conversation: {context}\nQuestion: {message["text"]}\nReturn JSON with reply and references.')
            attempt=self.store.begin_attempt(self.run_id,'chat',hashlib.sha256(prompt.encode()).hexdigest())
            self.store.deliver_question(message['id'],attempt)
            logs=self.project/'.eureka'/self.run_id/f'{attempt:04d}-chat'
            sink=EventSink(self.store,self.run_id,attempt=attempt,cycle=run['cycle'],phase='chat')
            self.emit('message.delivered',ids=[message['id']],attempt=attempt)
            argv,env=invocation(self.config,logs,environment(self.project),response_schema=CHAT_SCHEMA)
            execution=await execute(argv,prompt,self.project,logs,
                time.monotonic()+min(self.remaining(),self.config.invocation_timeout or float('inf')),
                self.cancellation,env=env,echo=self.echo,emit=sink,no_output_timeout=self.config.no_output_timeout,
                termination_grace=self.config.termination_grace)
            response=parse_response(self.config.backend,logs)
            error=response.error or model_error(self.config,response)
            if execution.reason!='exited' or execution.returncode: error=execution.reason
            if not error:
                import jsonschema
                try: jsonschema.validate(response.value,CHAT_SCHEMA)
                except jsonschema.ValidationError as exc: error=exc.message
            audit={'execution':asdict(execution),'errors':[error] if error else [],'usage':response.usage,'models':response.models}
            self.store.finish_attempt(attempt,'failed' if error else 'accepted',audit)
            write_json(logs/'outcome.json',audit)
            self.store.answer_message(message['id'],error or response.value['reply'],attempt,failed=bool(error))
            if execution.reason!='exited': raise InterruptedError(execution.reason)

    def prompt_context(self,run):
        spec=self.store.active_spec(self.run_id)
        run={**run,'task':spec['text'] if spec else run['task'],'config':self.config.to_dict()}
        run['research_parameters']=spec.get('parameters',{}) if spec else {}
        messages=self.store.steering(self.run_id)
        run['operator_instructions']=[{'id':m['id'],'text':m['text'],'scope':m['scope']} for m in messages]
        return run
