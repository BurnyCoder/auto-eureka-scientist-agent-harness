"""An independent arithmetic example checks the paired conditional bootstrap."""
from auto_eureka_scientist.reporting import metrics
from auto_eureka_scientist.util import digest, write_json
import pytest
from auto_eureka_scientist.util import read_json


def test_bootstrap_uses_matched_predictions_and_keeps_negative_results(tmp_path):
    protocol = {'seeds':[0,1,2],'bootstrap_resamples':1000,'primary_metric':'difference'}
    write_json(tmp_path/'research/protocol.json',protocol)
    registration = {'registered_at':'2026-01-01','protocol_sha256':digest(tmp_path/'research/protocol.json')}
    write_json(tmp_path/'research/registration.json',registration)
    for seed in protocol['seeds']:
        for method,predictions in [('regularized',[0,0,0,0]),('unregularized',[0,1,1,1])]:
            write_json(tmp_path/f'results/{method}{seed}.json',{
                'id':f'{method}{seed}','method':method,'seed':seed,'split':'test',
                'analysis_kind':'confirmatory','y_true':[0,1,1,1],'y_pred':predictions,
                'example_ids':[10,11,12,13], 'accuracy':.25 if method=='regularized' else 1.,
                'started_at':'2026-01-02','protocol_sha256':registration['protocol_sha256']})
    write_json(tmp_path/'results/auxiliary-summary.json',{'mean_difference':999,'description':'Not a per-experiment record'})
    summary = metrics(tmp_path)
    assert summary['primary']['mean_difference'] == -.75
    assert summary['primary']['conclusion'] == 'contradicts improvement'
    assert len(summary['experiments']) == 6
    for method in ('regularized','unregularized'):
        path = tmp_path/f'results/{method}2.json'
        record = read_json(path)
        record['example_ids'] = [13,12,11,10]
        write_json(path,record)
    with pytest.raises(ValueError,match='across training seeds'):
        metrics(tmp_path)
