"""Phase instructions and observable deliverables, not an agent's self-awarded score."""
import json
from pathlib import Path

from .contracts import PHASES, PHASE_SCHEMA, validate_handoff
from .policy import NEEL, policy_bytes, requirements
from .science import artifact_evidence, experiments, resolve_artifact, retrieve_sources, validate_protocol, verify_claims, verify_results
from .util import digest, read_json


DELIVERABLES = {
    'research':['reports/research.md','research/sources.json','reports/highlights.md'],
    'preregister':['reports/preregistration.md','research/protocol.json'],
    'core':['docs/reproduction.md'],
    'pilot':['reports/pilot.md'],
    'experiments':['reports/experiments.md'],
    'analysis':['research/claims.json','reports/interpretation.md','research/requirements.json'],
    'review':['reports/review.md'],
    'publish':['reports/final.md'],
}

INSTRUCTIONS = {
    'research': 'Use live web search and read primary sources. Write a literature review and source ledger: an array of objects with id, title, url, summary, license (or unknown), accessed_at. Cite the prior method and scientific process sources. Keep highlights and anomalies. Do not train models yet.',
    'preregister': 'Write a prospective preregistration matching research/protocol.json, with hypotheses, alternative explanations, distinguishing_predictions, primary metric, falsification, methods, seeds, data_boundaries, budget, and analysis_plan. Exploratory work instead needs objective and measurements. Do not train. The controller will commit and freeze this protocol.',
    'core': 'Implement the project, meaningful tests, and docs/reproduction.md. Run the checks and write research/checks.json as {"command": [executable, arguments...], "cwd": "cycle" or "project"}; the controller reruns that command. Do not train before the controller publishes core. Document baseline/control/ablation methods. Do not overwrite the registered protocol.',
    'pilot': 'Run one initial trained model, record validation predictions, loss history, exact configuration, and checkpoint. Write reports/pilot.md with observed learnings, not invented numbers. The controller renders and publishes the first result/model before comparative runs. Do not run comparative or sensitivity experiments in this phase.',
    'experiments': 'Run the preregistered comparisons, seed and hyperparameter sensitivity, controls and ablations. Keep the test split untouched until this planned evaluation. Save every attempt and outcome, including negative results. Write reports/experiments.md and update highlights.',
    'analysis': 'Create research/claims.json: array of {id,text,analysis_kind,evidence:[source or experiment IDs],limitations}. Distinguish confirmation from exploration. Write reports/interpretation.md with motivation, context, methods, implications, negative findings, limitations and related work, using evidence IDs and no hand-typed empirical scores. Fill every research/requirements.json item with status satisfied or not_applicable, evidence paths, and a reason. The controller generates all numeric tables, plots, paper and site.',
    'review': 'Do one substantive code/science/citation/reproducibility/security/presentation review. Inspect the generated paper and website; test examples. Fix concrete failures and document findings and residual limits in reports/review.md. If evidence is missing request revisit to an earlier phase; never conceal it. Do not claim visual inspection unless actually performed.',
    'publish': 'Reconcile README, reports, docs, claims and requirement checklist with actual results. Write reports/final.md, noting negative and inconclusive findings and remaining limits. The controller regenerates artifacts and publishes commits, Pages, and HF models. Finish this cycle without starting a new one yourself.',
}


def make_prompt(run: dict, phase: str, cycle: Path, previous: list, errors: list[str]) -> str:
    import sys
    project = Path(run['config']['project'])
    relative = cycle.relative_to(project).as_posix()
    fixture = ''
    if run['config']['profile'].startswith('digits'):
        import sys
        fixture = f'''\nDigits validation uses the supplied reproducible fixture. Preserve its fixed protocol and study.py scientific definitions.
The current Python with research dependencies is {sys.executable}. Execute as an argument array or properly quoted shell paths.
Core test command: ["{sys.executable.replace(chr(92),'/')}", "study.py", "check"], cwd cycle.
Pilot: run study.py pilot in {relative}; comparisons: run study.py experiments there.
The fixture provides actual training, leakage checks, predictions, safetensors, and logs.
You must inspect it and its outputs, research sources, author the scientific interpretation, and review its validity.
Do not invoke any LLM API, agent CLI, alternative model, or collaborator yourself. The harness owns all inference calls.
'''
    example = {'status':'complete','summary':'Describe the completed work honestly.',
               'artifacts':[f'{relative}/{path}' for path in DELIVERABLES[phase]],'evidence':[],'issues':[],
               'stage':'distillation' if phase in ('analysis','review','publish') else 'exploration',
               'analysis_kind':'exploratory','objective':'State this phase objective.',
               'predictions':[],'alternatives':[],'observations':[],'learning':'State what changed.',
               'rationale':'Explain the next action.','decision':'finish' if phase=='publish' else 'continue',
               'revisit_phase':'','not_applicable':[]}
    return f'''{policy_bytes().decode('utf-8-sig')}

--- HARNESS EXECUTION CONTRACT ---
{NEEL}
Task: {run['task']}
Backend/model: {run['config']['backend']} / {run['config']['model']}
Project root: {project}
All phase artifact paths below are relative to {relative}. Stay in this project; do not inspect sibling projects.
Current phase: {phase}. Do ONLY this phase, not later phases. Canonical policy requirements are applied at their appropriate phases.
Publishing and controller state are owned by the harness: do not edit .eureka, change Git branches, commit, push, create repositories, or perform uploads yourself.
You may read .eureka logs for this project. The controller handles those publication actions after verifying your artifacts.
Use installed tools directly; no sandbox or permission prompts are imposed by the harness.
Do not ask the user to proceed. On an actual blocker, return status blocked and a concrete explanation.
Research protocol histories and result files must be preserved; never delete negative results.
Put derived summaries and auxiliary analyses in research/ or reports/. Only JSON objects declaring id or method count as experiment records; aggregates never count as additional experiments.
On a repair, reuse valid existing artifacts and measurements. Correct the listed failures; do not repeat training merely to repair a handoff path.
For claims, cite IDs already present in research/sources.json or results/*.json. You do not need to copy experiments into another ledger. For an additional local audit, use research/evidence.json, for example [{{"id":"audit-splits","path":"{relative}/research/split-audit.json","sha256":"actual file hash","analysis_kind":"exploratory"}}]. Keep IDs unique. Post-hoc audits and claims based on them are exploratory. Use not_applicable for non-empirical documentation only.
Active seconds already used: {run.get('elapsed',0)}; total minute limit: {run['config'].get('max_minutes')}. CLI calls already used: {run.get('calls',0)}; total call limit: {run['config'].get('max_calls')}. Leave time for subsequent phases and publication; prioritize the immediate deliverables and cheap informative checks.
These current limits include explicit user-authorized extensions. Earlier protocol budgets remain historical records; do not rewrite them or treat them as a reason to stop an authorized continuation.
Required deliverables: {json.dumps(DELIVERABLES[phase])}
Instructions: {INSTRUCTIONS[phase]}
{fixture}
Previous completed phase summaries:
{json.dumps([{'phase':p['name'],'summary':p['result']['summary'],'learning':p['result'].get('learning','')} for p in previous],ensure_ascii=False)}
Corrections required from prior attempt: {json.dumps(errors,ensure_ascii=False)}
Return the structured phase result. File paths can be relative to the cycle or project; use project-relative paths if both would exist.
Use this handoff shape, replacing its descriptive placeholders with actual observations: {json.dumps(example,ensure_ascii=False)}
Before returning, check your files without another model call: "{sys.executable}" -m auto_eureka_scientist.cli verify --project "{project}" --cycle {run.get('cycle',int(cycle.name))} --phase {phase}
This draft check does not accept the phase or modify its scientific conclusions. Address concrete reported errors, then return your handoff. Empty revisit_phase and not_applicable fields are optional for Claude.
Provide predictions, competing alternatives, observations and learning appropriate to this phase. Do not fabricate future observations.
Use decision revisit with a named earlier phase if needed; use continue otherwise (finish in publish).
'''


def verify_phase(phase: str, cycle: Path, result: dict, *, fetch=False) -> list[str]:
    errors = []
    try:
        validate_handoff(result)
    except Exception as exc:
        return [f'Invalid handoff: {exc}']
    if result['status'] != 'complete':
        errors += result['issues'] or [f"Agent returned {result['status']}"]
    project = cycle.parents[1]
    for artifact in result['artifacts']:
        try:
            if not resolve_artifact(cycle,artifact).exists():
                errors.append(f'Handoff artifact missing: {artifact}')
        except ValueError as exc:
            errors.append(str(exc))
    for name in DELIVERABLES[phase]:
        path = cycle/name
        if not path.is_file() or not path.stat().st_size:
            errors.append(f'Missing nonempty artifact {name}')
    if errors:
        return errors
    try:
        if phase == 'research':
            sources = read_json(cycle/'research/sources.json')
            if not isinstance(sources,list) or not sources:
                errors.append('Source ledger must be a nonempty array')
            elif fetch:
                errors.extend(retrieve_sources(cycle))
        if phase == 'preregister':
            errors.extend(validate_protocol(read_json(cycle/'research/protocol.json')))
        if phase == 'core':
            checks = read_json(cycle/'research/checks.json')
            if not checks.get('command') or not isinstance(checks['command'],list):
                errors.append('research/checks.json requires a command argument array')
            elif not all(isinstance(arg,str) for arg in checks['command']):
                errors.append('Check command arguments must be strings')
        if phase in ('pilot','experiments','analysis','review','publish'):
            records = experiments(cycle)
            if not records:
                errors.append('No experiment records')
            else:
                errors.extend(verify_results(cycle))
        if phase in ('analysis','review','publish'):
            local_evidence, evidence_errors = artifact_evidence(cycle)
            errors.extend(evidence_errors)
            errors.extend(verify_claims(read_json(cycle/'research/claims.json'),experiments(cycle),read_json(cycle/'research/sources.json'),local_evidence))
            checklist = {item['id']:item for item in read_json(cycle/'research/requirements.json')}
            for requirement in requirements():
                item = checklist.get(requirement['id'],{})
                if item.get('status') == 'not_applicable':
                    if not item.get('reason','').strip():
                        errors.append(f"{requirement['id']}: explain not_applicable")
                elif item.get('status') == 'satisfied':
                    if not item.get('evidence'):
                        errors.append(f"{requirement['id']}: evidence required")
                    for evidence in item.get('evidence',[]):
                        if not resolve_artifact(cycle,evidence).exists():
                            errors.append(f'Checklist evidence missing: {evidence}')
                else:
                    errors.append(f"{requirement['id']}: requirement not addressed")
    except (ValueError,TypeError,KeyError,FileNotFoundError) as exc:
        errors.append(f'Invalid research record: {exc}')
    return errors


def artifact_hashes(cycle: Path) -> dict:
    return {str(path.relative_to(cycle)):digest(path) for path in cycle.rglob('*')
            if path.is_file() and '__pycache__' not in path.parts and 'models' not in path.parts}

