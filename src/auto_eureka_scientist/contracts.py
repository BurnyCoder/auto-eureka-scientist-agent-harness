"""Small shared JSON contracts for CLI handoffs and auditable research records."""
import jsonschema


PHASES = ('research','preregister','core','pilot','experiments','analysis','review','publish')
STAGES = ('ideation','exploration','understanding','distillation')


def object_schema(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


TEXT = {'type':'string'}
TEXTS = {'type':'array','items':TEXT}
PHASE_SCHEMA = object_schema({
    'status': {'type':'string','enum':['complete','needs_work','blocked']},
    'summary':TEXT, 'artifacts':TEXTS, 'evidence':TEXTS, 'issues':TEXTS,
    'stage':{'type':'string','enum':list(STAGES)},
    'analysis_kind':{'type':'string','enum':['exploratory','confirmatory','not_applicable']},
    'objective':TEXT, 'predictions':TEXTS, 'alternatives':TEXTS, 'observations':TEXTS,
    'learning':TEXT, 'rationale':TEXT,
    'decision':{'type':'string','enum':['continue','revisit','finish']},
    'revisit_phase':{'type':'string','enum':['',*PHASES]},
    'not_applicable':{'type':'array','items':object_schema({'requirement':TEXT,'reason':TEXT})},
})


def validate_handoff(value):
    if isinstance(value,dict):
        # Empty navigation/NA fields convey no evidence and need not cost a repair call.
        value.setdefault('revisit_phase','')
        value.setdefault('not_applicable',[])
    jsonschema.validate(value, PHASE_SCHEMA)
    for key in ('summary','objective','rationale'):
        if not value[key].strip():
            raise ValueError(f'Empty {key} is not a valid handoff')
    if value['decision'] == 'revisit' and not value['revisit_phase']:
        raise ValueError('revisit requires revisit_phase')
    return value

