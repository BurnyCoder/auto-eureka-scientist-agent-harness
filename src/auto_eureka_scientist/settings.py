"""One settings catalogue for validation, documented forms and reproducible inputs.

Schema annotations: https://json-schema.org/understanding-json-schema/reference/annotations
Environment layering: https://bbc2.github.io/python-dotenv/#other-use-cases
"""
from copy import deepcopy
from dataclasses import MISSING, field, fields
import json
from pathlib import Path
import re

import jsonschema

from .util import read_json, write_json


def setting(default=MISSING, *, description, category='Run', apply='new run', kind=None,
            choices=None, minimum=None, maximum=None, scope='run', advanced=False, items=None,
            backends=None, units=None):
    """Attach the schema and presentation contract to the actual dataclass field."""
    if kind is None:
        kind = 'boolean' if isinstance(default,bool) else 'integer' if isinstance(default,int) else (
            'number' if isinstance(default,float) else 'array' if isinstance(default,list) else 'string')
    metadata = {'description':description, 'type':kind, 'x-category':category, 'x-apply':apply,
                'x-scope':scope, 'x-advanced':advanced,'x-backends':backends or ['claude','codex']}
    if units: metadata['x-units']=units
    if default is not MISSING: metadata['default'] = default
    if choices is not None: metadata['enum'] = choices
    if minimum is not None: metadata['minimum'] = minimum
    if maximum is not None: metadata['maximum'] = maximum
    if kind == 'array': metadata['items'] = items or {'type':'string'}
    if isinstance(default,(dict,list)):
        return field(default_factory=lambda:deepcopy(default),metadata=metadata)
    return field(default=default,metadata=metadata)


def schema():
    """JSON Schema defaults describe values; resolve_settings applies them explicitly."""
    from .config import RunConfig
    properties = {f.name:{'title':f.name.replace('_',' ').capitalize(), **dict(f.metadata)} for f in fields(RunConfig)}
    for key,definition in properties.items():
        if key.endswith(('_timeout','_seconds','_delay','_grace','_max')) and key!='retry_multiplier': definition.setdefault('x-units','seconds')
        elif key=='max_minutes': definition['x-units']='active minutes'
        elif key.endswith('_chars'): definition['x-units']='characters'
        elif key.endswith('_width') or key=='font_size': definition['x-units']='pixels'
        elif key=='figure_dpi': definition['x-units']='dots per inch'
        elif key=='stream_batch_ms': definition['x-units']='milliseconds'
        elif key=='cost_warning_usd': definition['x-units']='USD, provider reported'
        else: definition.setdefault('x-units','value')
    return {'type':'object','additionalProperties':False,'required':['project','backend'],'properties':properties}


def validate(values, *, partial=False):
    try: json.dumps(values,allow_nan=False)
    except (ValueError,TypeError): raise ValueError('Settings must contain finite JSON values') from None
    contract = schema()
    if partial: contract = {**contract,'required':[]}
    try:
        jsonschema.Draft202012Validator(contract).validate(values)
    except jsonschema.ValidationError as exc:
        raise ValueError(f'{".".join(map(str,exc.path)) or "settings"}: {exc.message}') from None


def parse_overrides(entries):
    """Parse JSON values without evaluating Python, shell syntax or environment secrets."""
    result = {}
    for entry in entries or []:
        key, separator, raw = entry.partition('=')
        if not separator or key not in schema()['properties']:
            raise ValueError(f'Unknown setting: {key}')
        try: value = json.loads(raw)
        except ValueError: value = raw
        result[key] = value
    validate(result,partial=True)
    return result


def resolve_settings(project: Path, explicit: dict, *, defaults=None, preset=None):
    """Resolve a NEW run only. Resume patches the saved snapshot instead."""
    from .config import environment
    values = {**(defaults or {}), **(preset or {})}
    env = environment(project)
    backend = explicit.get('backend', env.get('EUREKA_BACKEND', values.get('backend','claude')))
    for key, definition in schema()['properties'].items():
        variable = f'EUREKA_{backend.upper()}_MODEL' if key=='model' else f'EUREKA_{key.upper()}'
        raw = env.get(variable)
        if raw is None: continue
        try: value = json.loads(raw)
        except (ValueError,TypeError): value = raw
        if definition['type']=='boolean' and isinstance(value,str):
            value = value.lower() not in ('false','0','no')
        values[key] = value
    values.update(explicit)
    values.update(project=str(project.resolve()), backend=backend)
    validate(values,partial=True)
    return values


def preset_path(project, name):
    if not re.fullmatch(r'[\w -]{1,80}',name): raise ValueError('Invalid preset name')
    return Path(project)/'.eureka'/'presets'/f'{name}.json'


def save_preset(project, name, values):
    validate(values,partial=True)
    # Credentials are never settings; exclude machine-specific identity from shared exports.
    values = {k:v for k,v in values.items() if k not in ('project','executable')}
    write_json(preset_path(project,name), {'schema_version':1,'settings':values})


def load_preset(project, name):
    return import_settings(read_json(preset_path(project,name)))


def import_settings(document):
    if document.get('schema_version') != 1 or not isinstance(document.get('settings'),dict):
        raise ValueError('Expected schema_version 1 and a settings object')
    validate(document['settings'],partial=True)
    return document['settings']
