"""CLI-specific wire formats behind one transport, with no cross-provider fallback.

https://code.claude.com/docs/en/headless
https://learn.chatgpt.com/docs/non-interactive-mode
"""
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import shutil

from .config import RunConfig
from .contracts import PHASE_SCHEMA
from .util import read_json, write_json


def invocation(config: RunConfig, logs: Path, base_env: dict) -> tuple[list[str], dict]:
    """Per-process settings preserve global CLI configuration and existing logins."""
    executable = config.executable or shutil.which(config.backend) or config.backend
    env = {**os.environ, **{k:str(v) for k,v in base_env.items() if v is not None},
           'PYTHONIOENCODING':'utf-8', 'PYTHONUTF8':'1'}
    # Nested CLI sessions use their own conversations. No credentials are copied to files.
    env.pop('CLAUDECODE',None)
    if config.backend == 'claude':
        env['CLAUDE_CODE_SUBAGENT_MODEL'] = config.model
        env['CLAUDE_CODE_SUBAGENT_MODEL_FORCE'] = '1'
        settings = {'sandbox':{'enabled':False}, 'fallbackModel':[], 'availableModels':[config.model]}
        schema = {**PHASE_SCHEMA,'required':[key for key in PHASE_SCHEMA['required'] if key not in ('revisit_phase','not_applicable')]}
        return [executable,'-p','--model',config.model,'--dangerously-skip-permissions',
                '--settings',json.dumps(settings),'--output-format','stream-json','--verbose',
                '--include-partial-messages','--json-schema',json.dumps(schema)], env
    logs.mkdir(parents=True,exist_ok=True)
    schema_path = logs / 'response-schema.json'
    write_json(schema_path,PHASE_SCHEMA)
    # Validation counts every inference; native delegated agents would escape that counter.
    helper_settings = ['--disable','multi_agent'] if config.profile.startswith('digits') else []
    return [executable,'exec','--model',config.model,'--dangerously-bypass-approvals-and-sandbox',*helper_settings,
            '-c','web_search="live"','-c',f'model_reasoning_effort="{config.reasoning}"',
            '--json','--color','never','--output-schema',str(schema_path),
            '--output-last-message',str(logs/'response.json'),'-'], env


@dataclass
class Response:
    value: dict | None = None
    error: str = ''
    models: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    searched: bool = False


def parse_response(backend: str, logs: Path) -> Response:
    """Read complete raw events; explicit provider errors outweigh process exit code."""
    response = Response()
    messages = []
    path = logs/'stdout.jsonl'
    if not path.exists():
        response.error = 'No provider output'
        return response
    with path.open(encoding='utf-8',errors='replace') as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event,dict):
                continue
            message = event.get('message') if isinstance(event.get('message'),dict) else {}
            model = event.get('model') or message.get('model')
            if isinstance(model,str) and model not in response.models:
                response.models.append(model)
            if event.get('type') in ('error','turn.failed') or event.get('is_error'):
                response.error = str(event.get('error') or event.get('errors') or event.get('result') or event.get('subtype') or event.get('type'))
            if isinstance(event.get('usage'),dict):
                response.usage = event['usage']
            if isinstance(event.get('modelUsage'),dict):
                response.usage['model_usage'] = event['modelUsage']
                for model in event['modelUsage']:
                    if model not in response.models:
                        response.models.append(model)
            if 'total_cost_usd' in event:
                response.usage['reported_cost_usd'] = event['total_cost_usd']
            if event.get('structured_output'):
                response.value = event['structured_output']
            if event.get('type') == 'result' and isinstance(event.get('result'),str):
                messages.append(event['result'])
            item = event.get('item') if isinstance(event.get('item'),dict) else {}
            if item.get('type') == 'agent_message':
                messages.append(item.get('text',''))
            if item.get('type') == 'web_search':
                response.searched = True
            for block in message.get('content') or []:
                if isinstance(block,dict) and block.get('name') in ('WebSearch','WebFetch'):
                    response.searched = True
    if backend == 'codex' and (logs/'response.json').exists():
        try:
            response.value = read_json(logs/'response.json')
        except ValueError:
            pass
    if response.value is None:
        for message in reversed(messages):
            try:
                candidate = json.loads(message.strip().removeprefix('```json').removesuffix('```').strip())
                if isinstance(candidate,dict):
                    response.value = candidate
                    break
            except ValueError:
                continue
    if response.value is None and not response.error:
        response.error = 'Missing structured phase result'
    return response


def model_error(config: RunConfig, response: Response) -> str:
    """Audit every model identifier actually reported by the CLI, including helpers."""
    for model in response.models:
        valid = model == config.model or (config.backend == 'claude' and config.model in ('haiku','sonnet','opus')
                                         and model.startswith(f'claude-{config.model}-'))
        if not valid:
            return f'Unexpected model {model}; requested {config.model}. No fallback permitted.'
    return ''

