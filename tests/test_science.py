"""Negative tests prevent empty evidence and retroactive confirmation from passing."""
from pathlib import Path
import pytest

from auto_eureka_scientist.science import artifact_evidence, validate_protocol, verify_claims, check_predictions
from auto_eureka_scientist.util import digest, write_json


def test_exploration_does_not_require_a_made_up_hypothesis():
    protocol = {'analysis_kind':'exploratory','question':'What varies?', 'objective':'Identify anomalies',
                'measurements':['accuracy'],'data_boundaries':'training only','budget':'one pilot',
                'analysis_plan':'Describe observations without confirmatory claims'}
    assert not validate_protocol(protocol)


def test_confirmation_requires_distinguishing_predictions():
    protocol = {'analysis_kind':'confirmatory','question':'Does regularization help?',
                'primary_metric':'accuracy difference','analysis_plan':'paired bootstrap',
                'hypotheses':[{'id':'h1','prediction':'positive','alternatives':['no effect']}],
                'data_boundaries':'untouched test','budget':'one hour','methods':['MLP'],
                'seeds':[0,1,2],'falsification':'negative interval'}
    assert any('distinguishing' in error for error in validate_protocol(protocol))


def test_exploratory_evidence_cannot_be_claimed_as_confirmatory():
    claims = [{'id':'c1','text':'A beats B','analysis_kind':'confirmatory','evidence':['e1'],
               'limitations':'single task'}]
    experiments = [{'id':'e1','analysis_kind':'exploratory'}]
    assert any('exploratory' in error for error in verify_claims(claims,experiments,[]))


def test_metrics_are_recomputed_from_predictions():
    assert check_predictions({'y_true':[0,1,2], 'y_pred':[0,0,2], 'accuracy':2/3}) == []
    assert check_predictions({'y_true':[0,1,2], 'y_pred':[0,0,2], 'accuracy':1.0})


def test_local_audit_evidence_requires_hash_and_preserves_exploratory_status(tmp_path):
    cycle = tmp_path/'cycles/001'
    write_json(cycle/'research/audit.json',{'passed':True})
    record = {'id':'audit','path':'cycles/001/research/audit.json','sha256':digest(cycle/'research/audit.json'),'analysis_kind':'exploratory'}
    write_json(cycle/'research/evidence.json',[record])
    artifacts, errors = artifact_evidence(cycle)
    assert not errors
    claim = {'id':'c','text':'Audit passed','limitations':'Post hoc','evidence':['audit'],'analysis_kind':'confirmatory'}
    assert any('exploratory' in e for e in verify_claims([claim],[],[],artifacts))
    write_json(cycle/'research/audit.json',{'passed':False})
    assert any('hash mismatch' in e for e in artifact_evidence(cycle)[1])

