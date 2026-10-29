"""Reproducible digits fixture: one validation pilot, then a frozen comparison.

Data: https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html
Optimizer: https://docs.pytorch.org/docs/stable/generated/torch.optim.AdamW.html
Splits: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html
Serialization: https://huggingface.co/docs/safetensors/en/api/torch
No test outcome selects a model, epoch, or hyperparameter. Every measurement is saved.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import random
import sys
import time

import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import torch
from torch import nn
from safetensors.torch import save_file, load_file


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset(protocol):
    """Split before fitting; a known constant normalization has no estimated parameters."""
    data = load_digits()
    x, y = data.data.astype(np.float32)/16, data.target.astype(np.int64)
    train, held = train_test_split(np.arange(len(y)),test_size=.4,stratify=y,random_state=protocol['split_seed'])
    validation, test = train_test_split(held,test_size=.5,stratify=y[held],random_state=protocol['split_seed'])
    splits = {'train':train,'validation':validation,'test':test}
    assert all(not set(a)&set(b) for a,b in ((train,validation),(train,test),(validation,test)))
    assert len(set(np.concatenate(list(splits.values())))) == len(y)
    assert x.shape[1] == protocol['architecture'][0]
    return x,y,splits


def network(protocol):
    """The architecture is shared by every neural arm; only the registered intervention varies."""
    inputs, hidden, outputs = protocol['architecture']
    return nn.Sequential(nn.Linear(inputs,hidden),nn.ReLU(),nn.Linear(hidden,outputs))


def fit_mlp(root, protocol, method, seed, x, y, splits, device):
    """Save the complete loss trajectory and reload the checkpoint before evaluation."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    model = network(protocol).to(device)
    optimizer = torch.optim.AdamW(model.parameters(),lr=protocol['learning_rate'],weight_decay=protocol['weight_decay'][method])
    train = splits['train']
    labels = y[train].copy()
    if method == 'shuffled_labels':
        labels = np.random.default_rng(seed).permutation(labels)
    inputs = torch.as_tensor(x[train],device=device)
    targets = torch.as_tensor(labels,device=device)
    val_x = torch.as_tensor(x[splits['validation']],device=device)
    val_y = torch.as_tensor(y[splits['validation']],device=device)
    order_rng = torch.Generator().manual_seed(seed)
    history = []
    for epoch in range(protocol['epochs']):
        model.train()
        order = torch.randperm(len(train),generator=order_rng).to(device)
        total = 0.0
        for indices in order.split(protocol['batch_size']):
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(model(inputs[indices]),targets[indices])
            loss.backward()
            optimizer.step()
            total += float(loss.detach())*len(indices)
        model.eval()
        with torch.no_grad():
            validation_loss = float(nn.functional.cross_entropy(model(val_x),val_y))
        history.append({'epoch':epoch+1,'train_loss':total/len(train),'validation_loss':validation_loss})
        print(f'[{timestamp()}] {method} seed={seed} '+json.dumps(history[-1]),flush=True)
    destination = root/'models'/f'{method}-s{seed}.safetensors'
    save_file({key:value.detach().cpu().contiguous() for key,value in model.state_dict().items()},str(destination))
    restored = network(protocol).to(device)
    restored.load_state_dict(load_file(str(destination),device=str(device)))
    restored.eval()
    with torch.no_grad():
        reference = model(torch.as_tensor(x,device=device))
        reloaded = restored(torch.as_tensor(x,device=device))
        torch.testing.assert_close(reference,reloaded,rtol=0,atol=0)
    return reloaded.argmax(dim=1).cpu().numpy(), history, destination


def experiment(root, protocol, method, seed, split, device, *, pilot=False):
    identifier = ('pilot_' if pilot else '')+f'{method}_s{seed}'
    destination = root/'results'/f'{identifier}.json'
    if destination.exists():
        record = load(destination)
        assert record['protocol_sha256'] == sha(root/'research/protocol.json'), 'Stale protocol'
        assert record['code_sha256'] == sha(Path(__file__)), 'Code changed after results; preserve old run and preregister a new cycle'
        print(f'[{timestamp()}] Reusing verified experiment {identifier}',flush=True)
        return record
    registration = load(root/'research/registration.json')
    assert registration['protocol_sha256'] == sha(root/'research/protocol.json'), 'Unregistered protocol change'
    started_at, started = timestamp(), time.perf_counter()
    x,y,splits = dataset(protocol)
    history = []
    if method in protocol['weight_decay']:
        # The published pilot checkpoint is reused for the matching final comparison.
        pilot_path = root/'results/pilot_regularized_s0.json'
        if method == 'regularized' and seed == 0 and not pilot and pilot_path.exists():
            old = load(pilot_path)
            assert old['code_sha256'] == sha(Path(__file__))
            checkpoint = root/old['checkpoint']
            model = network(protocol).to(device)
            model.load_state_dict(load_file(str(checkpoint),device=str(device)))
            model.eval()
            with torch.no_grad():
                predicted = model(torch.as_tensor(x,device=device)).argmax(1).cpu().numpy()
            history = old['history']
        else:
            predicted, history, checkpoint = fit_mlp(root,protocol,method,seed,x,y,splits,device)
    elif method == 'logistic':
        model = LogisticRegression(C=protocol['logistic_C'],max_iter=protocol['logistic_max_iter'],random_state=seed)
        model.fit(x[splits['train']],y[splits['train']])
        predicted = model.predict(x)
        checkpoint = root/'models/logistic.npz'
        np.savez(checkpoint,coef=model.coef_,intercept=model.intercept_,classes=model.classes_)
        with np.load(checkpoint) as saved:
            restored = saved['classes'][(x@saved['coef'].T+saved['intercept']).argmax(1)]
        np.testing.assert_array_equal(predicted,restored)
    else:
        classes, counts = np.unique(y[splits['train']],return_counts=True)
        predicted = np.full(len(y),classes[counts.argmax()])
        checkpoint = root/'models/class_prior.npz'
        np.savez(checkpoint,classes=classes,probabilities=counts/counts.sum())
        with np.load(checkpoint) as saved:
            restored = np.full(len(y),saved['classes'][saved['probabilities'].argmax()])
        np.testing.assert_array_equal(predicted,restored)
    indices = splits[split]
    record = {'id':identifier,'method':method,'seed':seed,'split':split,
              'analysis_kind':'exploratory' if pilot or method in ('sensitivity','shuffled_labels','logistic','class_prior') else 'confirmatory',
              'started_at':started_at,'finished_at':timestamp(),'seconds':time.perf_counter()-started,
              'accuracy':float(np.mean(predicted[indices] == y[indices])),
              'y_true':y[indices].tolist(),'y_pred':predicted[indices].tolist(),'example_ids':indices.tolist(),
              'split_ids':{key:value.tolist() for key,value in splits.items()},
              'protocol_sha256':sha(root/'research/protocol.json'),'code_sha256':sha(Path(__file__)),
              'dataset_sha256':hashlib.sha256(x.tobytes()+y.tobytes()).hexdigest(),
              'device':str(device) if method in protocol['weight_decay'] else 'cpu',
              'hardware':torch.cuda.get_device_name(0) if device.type=='cuda' else 'CPU',
              'torch_version':torch.__version__,'numpy_version':np.__version__,
              'history':history,'checkpoint':str(checkpoint.relative_to(root)).replace('\\','/'),
              'checkpoint_sha256':sha(checkpoint),'checkpoint_reload_verified':True,
              'expected_observation':'Real-label models should outperform the label-shuffled control; the primary decay effect may be positive, negative, or inconclusive.',
              'limitations':'One random example split without writer IDs; conditional intervals exclude training-population uncertainty.'}
    write(destination,record)
    print(f'[{timestamp()}] SAVED '+json.dumps({k:record[k] for k in ('id','accuracy','seconds','device')}),flush=True)
    return record


def main():
    root = Path(__file__).resolve().parent
    protocol = load(root/'research/protocol.json')
    operation = sys.argv[1] if len(sys.argv)>1 else 'check'
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
    torch.set_num_threads(2)
    x,y,splits = dataset(protocol)
    if operation == 'check':
        assert protocol['seeds'] == [0,1,2]
        assert set(protocol['weight_decay']) == {'regularized','unregularized','sensitivity','shuffled_labels'}
        assert np.isfinite(x).all() and x.min() >= 0 and x.max() <= 1
        print(json.dumps({'status':'passed','dataset_shape':list(x.shape),'split_sizes':{k:len(v) for k,v in splits.items()}}))
        return
    if operation not in ('pilot','experiments'):
        raise ValueError('Use check, pilot, or experiments')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if operation == 'pilot':
        experiment(root,protocol,'regularized',0,'validation',device,pilot=True)
    else:
        if not (root/'research/pilot-publication.json').exists():
            raise RuntimeError('Publish the first pilot and checkpoint before sensitivity experiments')
        for method in protocol['methods']:
            for seed in protocol['seeds'] if method in protocol['weight_decay'] else [0]:
                experiment(root,protocol,method,seed,'test',device)


if __name__ == '__main__':
    main()
