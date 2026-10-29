"""Executable checks for provenance, leakage boundaries, and claim arithmetic.

These checks cannot prove a scientific claim. They make common omissions observable.
Sources: https://scikit-learn.org/stable/common_pitfalls.html and
https://neurips.cc/public/guides/PaperChecklist
"""
from pathlib import Path
import hashlib
import math
import urllib.request

from .util import digest, now, read_json, write_json


def validate_protocol(protocol: dict) -> list[str]:
    errors = []
    kind = protocol.get('analysis_kind')
    required = ['question','analysis_plan','data_boundaries','budget']
    if kind == 'exploratory':
        required += ['objective','measurements']
    elif kind == 'confirmatory':
        required += ['primary_metric','hypotheses','methods','seeds','falsification']
        for hypothesis in protocol.get('hypotheses',[]):
            if not isinstance(hypothesis,dict) or not hypothesis.get('alternatives') or not hypothesis.get('distinguishing_predictions'):
                errors.append('Each hypothesis needs alternatives and distinguishing_predictions')
    else:
        errors.append('protocol analysis_kind must be exploratory or confirmatory')
    errors.extend(f'protocol missing {key}' for key in required if not protocol.get(key))
    return errors


def check_predictions(experiment: dict) -> list[str]:
    if 'accuracy' not in experiment:
        return []
    true, predicted = experiment.get('y_true',[]), experiment.get('y_pred',[])
    if not true or len(true) != len(predicted):
        return [f"{experiment.get('id','experiment')}: missing/alignment-invalid predictions"]
    actual = sum(a == b for a,b in zip(true,predicted))/len(true)
    identifiers = experiment.get('example_ids')
    if identifiers is not None and (len(identifiers)!=len(true) or len(set(identifiers))!=len(identifiers)):
        return [f"{experiment.get('id')}: duplicate or misaligned example IDs"]
    if not math.isfinite(experiment['accuracy']) or not math.isclose(actual,experiment['accuracy'],abs_tol=1e-12):
        return [f"{experiment.get('id','experiment')}: accuracy does not match predictions"]
    return []


def verify_claims(claims: list, experiments: list, sources: list, artifacts=()) -> list[str]:
    errors = []
    items = [*experiments,*sources,*artifacts]
    evidence = {item['id']: item for item in items}
    if len(items) != len(evidence):
        from collections import Counter
        duplicates = sorted(key for key,count in Counter(item['id'] for item in items).items() if count>1)
        errors.append(f'Evidence identifiers must be unique across all ledgers; duplicated: {duplicates}')
    for claim in claims:
        if not claim.get('text') or not claim.get('limitations') or not claim.get('evidence'):
            errors.append(f"Claim {claim.get('id')}: text, limitations, and evidence required")
        for reference in claim.get('evidence',[]):
            if reference not in evidence:
                errors.append(f'Unknown claim evidence: {reference}')
            elif claim.get('analysis_kind') == 'confirmatory' and evidence[reference].get('analysis_kind') == 'exploratory':
                errors.append(f'Claim {claim.get("id")}: exploratory evidence cannot become confirmatory')
    return errors


def artifact_evidence(cycle: Path) -> tuple[list, list]:
    """Local audits need typed provenance too; a filename alone is not confirmation."""
    ledger = cycle/'research/evidence.json'
    records = read_json(ledger) if ledger.exists() else []
    errors = []
    for record in records:
        if not record.get('id') or record.get('analysis_kind') not in ('exploratory','confirmatory','not_applicable'):
            errors.append(f'Artifact evidence {record.get("id")}: analysis_kind must be exploratory, confirmatory, or not_applicable; got {record.get("analysis_kind")}')
        path = cycle.parents[1]/record.get('path','')
        if not path.is_file():
            errors.append(f'Artifact evidence file missing: {record.get("path")}')
        elif record.get('sha256') != digest(path):
            errors.append(f'Artifact evidence hash mismatch: {record.get("id")}')
    return [r for r in records if r.get('id')], errors


def retrieve_sources(cycle: Path, timeout=20) -> list[str]:
    """Record actual retrieval separately from the agent's source summary.

    Only metadata and hashes are persisted, not copyrighted page bodies. A successful
    fetch is provenance evidence, not an automatic fact-check of the associated claim.
    """
    sources = read_json(cycle/'research/sources.json')
    output = cycle/'research/retrievals.json'
    previous = read_json(output) if output.exists() else {}
    errors = []
    for source in sources:
        identifier, url = source.get('id'), source.get('url','')
        if not identifier or not url.startswith(('https://','http://')) or not source.get('summary'):
            errors.append('Each source requires id, http(s) URL, and a grounded summary')
            continue
        if previous.get(identifier,{}).get('url') == url and previous[identifier].get('ok'):
            continue
        try:
            request = urllib.request.Request(url,headers={'User-Agent':'AutoEureka/0.1 (research citation verification)'})
            with urllib.request.urlopen(request,timeout=timeout) as response:
                body = response.read(2_000_000)
                previous[identifier] = {'url':url,'final_url':response.url,'ok':True,'at':now(),
                                        'sha256':hashlib.sha256(body).hexdigest(),'sample_bytes':len(body)}
        except Exception as exc:
            previous[identifier] = {'url':url,'ok':False,'at':now(),'error':str(exc)}
            if not source.get('access_limitation'):
                errors.append(f'Source {identifier} could not be independently fetched: {exc}; supply a working primary URL or document access_limitation')
    write_json(output,previous)
    if not any(record.get('ok') for record in previous.values()):
        errors.append('No independently retrievable source')
    return errors


def experiments(cycle: Path) -> list[dict]:
    """Select declared experiment records, excluding auxiliary aggregate JSON.

    A partial record with either identifying field still reaches validation. Aggregate
    summaries must never become additional samples in the registered comparison.
    """
    directory = cycle/'results'
    values = [read_json(path) for path in sorted(directory.glob('*.json'))] if directory.exists() else []
    return [value for value in values if isinstance(value,dict) and ('id' in value or 'method' in value)]


def verify_results(cycle: Path) -> list[str]:
    errors = []
    records = experiments(cycle)
    if len({record.get('id') for record in records})!=len(records):
        errors.append('Duplicate experiment identifiers')
    registration_path = cycle/'research/registration.json'
    if not registration_path.exists():
        return ['Missing committed preregistration receipt']
    registration = read_json(registration_path)
    if digest(cycle/'research/protocol.json') != registration['protocol_sha256']:
        errors.append('Protocol changed after registration; preserve it and register a new research cycle')
    for experiment in records:
        errors.extend(check_predictions(experiment))
        if experiment.get('protocol_sha256') != registration['protocol_sha256']:
            errors.append(f"{experiment.get('id')}: protocol hash mismatch")
        if not experiment.get('started_at') or experiment['started_at'] < registration['registered_at']:
            errors.append(f"{experiment.get('id')}: missing or pre-registration start time")
        if not experiment.get('method') or not experiment.get('analysis_kind'):
            errors.append('Experiments require method and analysis_kind')
        code_receipt = cycle/'research/core-code.json'
        if code_receipt.exists() and experiment.get('code_sha256') != read_json(code_receipt)['sha256']:
            errors.append(f"{experiment.get('id')}: training code differs from published core")
        checkpoint = experiment.get('checkpoint')
        if checkpoint:
            if not (cycle/checkpoint).is_file():
                errors.append(f"{experiment.get('id')}: checkpoint missing; download the published model bundle")
            elif digest(cycle/checkpoint) != experiment.get('checkpoint_sha256'):
                errors.append(f"{experiment.get('id')}: checkpoint hash mismatch")
        splits = experiment.get('split_ids',{})
        names = list(splits)
        for i,name in enumerate(names):
            for other in names[i+1:]:
                if set(splits[name]) & set(splits[other]):
                    errors.append(f'{name}/{other}: overlapping data IDs')
    return errors

