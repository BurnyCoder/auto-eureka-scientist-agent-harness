"""Verify downloaded digits checkpoints and regenerated numbers without training.

Uses safetensors' tensor-only loader and NumPy's non-pickle archive reader:
https://huggingface.co/docs/safetensors/en/api/torch
https://numpy.org/doc/stable/reference/generated/numpy.load.html
"""
import argparse
import importlib.util
from pathlib import Path
import platform
import urllib.request

import numpy as np
import torch
from safetensors.torch import load_file

from auto_eureka_scientist.reporting import metrics
from auto_eureka_scientist.science import experiments, verify_results
from auto_eureka_scientist.util import digest, now, read_json, write_json


def verify(project: Path, urls: list[str]) -> dict:
    """Compare every saved prediction to inference from its published checkpoint."""
    cycle = project/'cycles/001'
    spec = importlib.util.spec_from_file_location('verified_study',cycle/'study.py')
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)
    protocol = read_json(cycle/'research/protocol.json')
    x, y, _ = study.dataset(protocol)
    results = []
    for record in experiments(cycle):
        checkpoint = cycle/record['checkpoint']
        if checkpoint.suffix == '.safetensors':
            model = study.network(protocol).eval()
            model.load_state_dict(load_file(str(checkpoint),device='cpu'))
            with torch.no_grad():
                predicted = model(torch.from_numpy(x)).argmax(1).numpy()
        else:
            with np.load(checkpoint,allow_pickle=False) as saved:
                if 'coef' in saved:
                    predicted = saved['classes'][(x@saved['coef'].T+saved['intercept']).argmax(1)]
                else:
                    predicted = np.full(len(x),saved['classes'][saved['probabilities'].argmax()])
        ids = record['example_ids']
        results.append({'id':record['id'],'checkpoint_sha256':digest(checkpoint),
                        'hash_matches':digest(checkpoint)==record['checkpoint_sha256'],
                        'predictions_match':bool(np.array_equal(predicted[ids],record['y_pred'])),
                        'labels_match':bool(np.array_equal(y[ids],record['y_true']))})
    actual = metrics(cycle)
    saved_metrics = read_json(cycle/'reports/metrics.json')
    numerical_match = actual['primary']==saved_metrics['primary'] and actual['experiments']==saved_metrics['experiments']
    pages = []
    for url in urls:
        try:
            with urllib.request.urlopen(url,timeout=30) as response:
                pages.append({'url':url,'status':response.status,'final_url':response.url})
        except Exception as exc:
            pages.append({'url':url,'error':str(exc)})
    errors = verify_results(cycle)
    return {'at':now(),'project':project.name,'python':platform.python_version(),'torch':torch.__version__,
            'verification_device':'cpu','source_sha256':digest(cycle/'study.py'),
            'records':results,'numerical_regeneration_matches':numerical_match,'research_errors':errors,
            'urls':pages,'passed':bool(results) and numerical_match and not errors
            and all(r['hash_matches'] and r['predictions_match'] and r['labels_match'] for r in results)
            and all(p.get('status')==200 for p in pages)}


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--url',action='append',default=[])
    args = parser.parse_args()
    result = verify(args.project.resolve(),args.url)
    write_json(args.output,result)
    print({'passed':result['passed'],'checkpoints':len(result['records']),'output':str(args.output)})
    raise SystemExit(0 if result['passed'] else 1)
