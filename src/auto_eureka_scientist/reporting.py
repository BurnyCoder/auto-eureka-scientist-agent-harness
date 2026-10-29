"""Deterministic artifacts from recorded observations; no model-generated numbers.

Bootstrap: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html
Plotting: https://matplotlib.org/stable/users/explain/quick_start.html
PDF: https://pandoc.org/MANUAL.html#creating-a-pdf
"""
from pathlib import Path
from importlib.resources import files
import json
import shutil

from .science import check_predictions, experiments, snapshot_evidence, verify_results
from .util import command, read_json, write_json


def metrics(cycle: Path) -> dict:
    records = experiments(cycle)
    errors = verify_results(cycle) if records else []
    if errors:
        raise ValueError('; '.join(errors))
    protocol = read_json(cycle/'research/protocol.json') if (cycle/'research/protocol.json').exists() else {}
    return summarize_records(records,protocol)


def summarize_records(records: list, protocol: dict) -> dict:
    """Recompute numerical summaries from raw observations, including public snapshots."""
    errors = [error for record in records for error in check_predictions(record)]
    if len({record['id'] for record in records})!=len(records):
        errors.append('Duplicate experiment identifiers')
    if errors:
        raise ValueError('; '.join(errors))
    rows = [{key:item.get(key) for key in ('id','method','seed','split','analysis_kind','accuracy','seconds','device','checkpoint','checkpoint_reload_verified')} for item in records]
    result = {'experiments':rows,'primary':None,'limitations':[
        'Conditional test-example intervals do not estimate variation over new training seeds, writers, or datasets.',
        'A small single-task study does not establish general model or harness superiority.']}
    paired = []
    shared_ids = None
    import numpy as np
    for seed in protocol.get('seeds',[]):
        selected = {r['method']:r for r in records if r.get('seed') == seed and r.get('split') == 'test'}
        if {'regularized','unregularized'} <= selected.keys():
            left,right = selected['regularized'],selected['unregularized']
            if left['example_ids'] != right['example_ids'] or left['y_true'] != right['y_true']:
                raise ValueError('Primary comparison requires identical paired examples and labels')
            if shared_ids is not None and shared_ids!=(left['example_ids'],left['y_true']):
                raise ValueError('Bootstrap requires identical example order across training seeds')
            shared_ids = (left['example_ids'],left['y_true'])
            truth = np.asarray(left['y_true'])
            paired.append((np.asarray(left['y_pred']) == truth).astype(float)-(np.asarray(right['y_pred']) == truth))
    if paired and len(paired) == len(protocol['seeds']):
        differences = np.asarray(paired)
        if not np.any(differences):
            result['limitations'].append('No discordant predictions were observed in the primary pairs. The empirical bootstrap interval collapses to zero; this is not an equivalence test or a guarantee about unseen examples.')
        per_example = differences.mean(axis=0)
        rng = np.random.default_rng(protocol.get('bootstrap_seed',2026))
        n_resamples = protocol.get('bootstrap_resamples',10000)
        estimates = np.empty(n_resamples)
        for start in range(0,n_resamples,500):
            end = min(start+500,n_resamples)
            indices = rng.integers(0,len(per_example),size=(end-start,len(per_example)))
            estimates[start:end] = per_example[indices].mean(axis=1)
        low,high = np.quantile(estimates,[.025,.975]).tolist()
        result['primary'] = {'name':protocol['primary_metric'],'mean_difference':float(per_example.mean()),
                             'ci95':[low,high],'bootstrap_resamples':n_resamples,
                             'seed_effects':differences.mean(axis=1).tolist(),
                             'seed_sample_sd':float(differences.mean(axis=1).std(ddof=1)) if len(paired)>1 else None,
                             'conclusion':'supports improvement' if low>0 else 'contradicts improvement' if high<0 else 'inconclusive',
                             'uncertainty_unit':'test examples, conditional on the registered trained models'}
    return result


def markdown_table(summary: dict, *, compact=False) -> str:
    if compact:
        lines = ['| Method | Seed | Split | Accuracy | Seconds | Device |',
                 '|-------------------------|-----:|------------|-----------:|----------:|----------|']
        for row in summary['experiments']:
            score = f"{row['accuracy']:.6f}" if row['accuracy'] is not None else 'not recorded'
            seconds = f"{row['seconds']:.3f}" if row['seconds'] is not None else 'not recorded'
            lines.append(f"| {str(row['method']).replace('_',' ')} | {row['seed']} | {row['split']} | {score} | {seconds} | {row['device']} |")
        return '\n'.join(lines)
    lines = ['| Experiment | Method | Seed | Split | Accuracy | Seconds | Device |',
             '|---|---|---:|---|---:|---:|---|']
    for row in summary['experiments']:
        accuracy = f"{row['accuracy']:.6f}" if row['accuracy'] is not None else 'not recorded'
        seconds = f"{row['seconds']:.3f}" if row['seconds'] is not None else 'not recorded'
        lines.append(f"| {row['id']} | {row['method']} | {row['seed']} | {row['split']} | {accuracy} | {seconds} | {row['device']} |")
    return '\n'.join(lines)


def figures(cycle: Path, records=None):
    """Plot recorded scores, histories and deterministic prediction examples."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    records = experiments(cycle) if records is None else records
    (cycle/'figures').mkdir(parents=True,exist_ok=True)
    if not records or not any('accuracy' in r for r in records):
        return
    fig, ax = plt.subplots(figsize=(9,max(3,len(records)*.3)))
    for i,row in enumerate(records):
        if row.get('accuracy') is not None:
            ax.scatter(row['accuracy'],i,color='#0072B2' if row.get('split')=='test' else '#D55E00')
    ax.set(yticks=range(len(records)),yticklabels=[r['id'] for r in records],xlim=(0,1),xlabel='Accuracy (fraction)',
           title='Recorded outcomes: blue = test; orange = validation pilot')
    ax.grid(axis='x',alpha=.25)
    fig.tight_layout()
    fig.savefig(cycle/'figures/accuracy.png',dpi=160)
    plt.close(fig)
    fig,ax = plt.subplots(figsize=(9,4))
    for record in records:
        history = record.get('history',[])
        if history:
            ax.plot([p['epoch'] for p in history],[p['validation_loss'] for p in history],label=record['id'],alpha=.8)
    ax.set(xlabel='Epoch',ylabel='Validation cross-entropy',title='All recorded validation loss curves')
    if ax.lines:
        ax.legend(fontsize=6,ncol=3)
    fig.tight_layout()
    fig.savefig(cycle/'figures/loss.png',dpi=160)
    plt.close(fig)
    fig,ax = plt.subplots(figsize=(10,2))
    ax.axis('off')
    labels = ['Task + policy','Selected CLI','Evidence checks','Reports + models']
    for i,label in enumerate(labels):
        ax.text(.12+i*.25,.5,label,ha='center',va='center',bbox={'boxstyle':'round','facecolor':'#e7f0f5','edgecolor':'#0072B2'},fontsize=9)
        if i<3:
            ax.annotate('',xy=(.25+i*.25,.5),xytext=(.22+i*.25,.5),arrowprops={'arrowstyle':'->'})
    fig.savefig(cycle/'figures/architecture.png',dpi=160,bbox_inches='tight')
    plt.close(fig)
    # Select in saved order, without inspecting correctness or choosing favorable cases.
    examples = {}
    for record in records:
        if record.get('y_true') and record.get('split')=='test':
            examples.setdefault(record['method'],record)
    if examples:
        fig,axes = plt.subplots(len(examples),1,figsize=(10,max(2,len(examples)*.65)),squeeze=False)
        for ax,record in zip(axes[:,0],examples.values()):
            ax.axis('off')
            ax.text(0,.5,record['id'],fontsize=8,va='center')
            for i,(truth,prediction,identifier) in enumerate(zip(record['y_true'][:6],record['y_pred'][:6],record['example_ids'][:6])):
                ax.text(.30+i*.115,.5,f'ID {identifier}\n{prediction} / {truth}',fontsize=8,ha='center',va='center',
                        bbox={'facecolor':'#e7f1e9' if prediction==truth else '#f8e4dc','edgecolor':'#adc4cf'})
        fig.suptitle('Saved examples: prediction / true label; first test record per method',fontsize=10)
        fig.tight_layout()
        fig.savefig(cycle/'figures/examples.png',dpi=160)
        plt.close(fig)


def render(project: Path, cycle: Path, *, backend='Codex', pdf=True, timeout=180, cancelled=None) -> dict:
    """One command rebuilds reports, figures, paper, model card, and browser data."""
    reports = cycle/'reports'
    reports.mkdir(parents=True,exist_ok=True)
    snapshots = sorted((project/'reports').glob('run-*.json'),key=lambda path:path.stat().st_mtime)
    run_status = read_json(snapshots[-1]) if snapshots else None
    unaccepted = (run_status and run_status['status'] not in ('running','complete')
                  and 'analysis' not in run_status['completed_phases'])
    snapshot_evidence(cycle,allow_unverified=bool(unaccepted))
    summary = metrics(cycle)
    status_text = (f"Recorded harness status: **{run_status['status']}**; {len(run_status['completed_phases'])} operational phases accepted. "
                   'Measurements below do not imply completion of unaccepted phases.' if run_status else
                   'Research is in progress; no final run-status snapshot is available.')
    write_json(reports/'metrics.json',summary)
    table = markdown_table(summary)
    figures(cycle)
    sources = read_json(cycle/'research/sources.json') if (cycle/'research/sources.json').exists() else []
    references = '\n'.join(f"- [{s['id']}: {s.get('title',s['id'])}]({s['url']})" for s in sources)
    protocol = read_json(cycle/'research/protocol.json')
    primary = summary['primary']
    seed_spread = f"{primary['seed_sample_sd']:.6f}" if primary and primary['seed_sample_sd'] is not None else 'not estimable from the recorded seeds'
    primary_text = ('The registered primary comparison is pending; no confirmatory conclusion is available.' if primary is None else
                    f"The mean paired accuracy difference is {primary['mean_difference']:.6f}, with conditional 95% bootstrap interval "
                    f"[{primary['ci95'][0]:.6f}, {primary['ci95'][1]:.6f}]. The registered decision is **{primary['conclusion']}**. "
                    f"The sample standard deviation across seed effects is {seed_spread}. "
                    f"The interval uses {primary['bootstrap_resamples']} paired resamples of test examples and conditions on the trained models.")
    interpretation_path = reports/'interpretation.md'
    interpretation = interpretation_path.read_text(encoding='utf-8') if interpretation_path.exists() else (
        'This is a preliminary artifact generated before final interpretation. All available outcomes are retained; '
        'a completed experiment is not evidence that the favored hypothesis is true.')
    claims = read_json(cycle/'research/claims.json') if (cycle/'research/claims.json').exists() else []
    if unaccepted:
        interpretation = ('The analysis phase was not accepted before this run stopped. Its draft interpretation '
                          'and claim ledger are preserved in the repository, but are excluded from this generated '
                          'paper because their evidence contracts remain unresolved. The tables and primary '
                          'calculation above are regenerated from saved predictions; review remains incomplete.')
        claims = []
    source_urls = {s['id']:s['url'] for s in sources}
    publication = cycle/'research/core-publication.json'
    repository_url = read_json(publication).get('url','') if publication.exists() else ''
    def artifact_link(path):
        import os
        from urllib.parse import quote
        if repository_url:
            return repository_url+'/blob/main/'+quote(path.relative_to(project).as_posix(),safe='/')
        return Path(os.path.relpath(path,reports)).as_posix()
    audit_path = project/'reports/post-run-publication.md'
    audit_notice = (f'Post-run repairs or publication work are documented in the [audit disclosure]({artifact_link(audit_path)}). '
                    'They are separate from the bounded model execution.' if audit_path.exists() else '')
    ledger = cycle/'research/evidence.json'
    if ledger.exists():
        source_urls.update({r['id']:artifact_link(project/r['path']) for r in read_json(ledger)})
    def evidence_link(identifier):
        url = source_urls.get(identifier,artifact_link(cycle/f'results/{identifier}.json'))
        return f'[{identifier}]({url})'
    claim_text = '\n'.join(f"- **{c['id']}**: {c['text']} Evidence: {', '.join(evidence_link(ref) for ref in c['evidence'])}. Limitations: {c['limitations']}" for c in claims) or 'Claims have not yet been distilled.'
    methodology = '\n'.join(f'- **{key}**: {json.dumps(protocol[key],ensure_ascii=False)}' for key in
                             ('analysis_kind','prior_results_known','objective','question','architecture','optimizer','learning_rate','batch_size','epochs','methods','seeds','data_boundaries','analysis_plan','hyperparameter_rationale') if key in protocol)
    def figure(name,caption):
        return f'![{caption}](../figures/{name}.png)\n\n*{caption}.*' if (cycle/f'figures/{name}.png').exists() else f'{caption}: no applicable measurement recorded.'
    paper = f'''---
title: "{project.name}: reproducible research report"
author: 'Libor “Burny” Burian'
geometry: margin=1in
fontsize: 10pt
---

# Abstract

This report records a bounded research cycle executed through {backend}. {primary_text}

{status_text}

{audit_notice}

# Context, motivation, and introduction

{protocol.get('question','See the registered protocol.')}

The objective is reproducible evidence and an inspectable research process. This study does not establish broad scientific reliability or superiority of an agent model.

# Background and method

{methodology}

{figure('architecture','Research architecture')}

# Results

{markdown_table(summary,compact=True)}

{primary_text}

{figure('accuracy','All recorded accuracies')}

{figure('loss','Recorded learning curves')}

{figure('examples','First saved test examples; no correctness-based selection')}

# Claims and evidence

{claim_text}

# Discussion, implications, and learnings

{interpretation}

# Limitations

{chr(10).join('- '+text for text in summary['limitations'])}

Exploratory outcomes do not become confirmatory by inclusion in this document. Missing metrics are not zero. Measurements without an applicable recorded objective are omitted; see the requirement checklist for explanations.

# Related work and sources

{references}

# Conclusion

{primary_text}

# Appendix: reproducibility and provenance

The committed protocol, per-experiment JSON files, saved predictions, loss histories, and checkpoints are the source of all numerical tables and figures. Rebuild using `eureka render`. See `docs/reproduction.md` for execution commands and environment details.

# AI statement

Codex wrote the harness and study fixture; {backend} performed this cycle and authored its interpretation. The harness generated this paper from recorded artifacts. A human supplied the exact specification. Human cleanup and rewriting are in progress.
'''
    (reports/'paper.md').write_text(paper,encoding='utf-8')
    (reports/'summary.md').write_text('# All experiments\n\n'+status_text+'\n\n'+table+'\n\n'+primary_text+'\n\n'+methodology+'\n\n'+interpretation+'\n\n## Sources\n\n'+references+'\n',encoding='utf-8')
    for record in experiments(cycle):
        text = f"# {record['id']}\n\nMethod: {record['method']}. Analysis: {record['analysis_kind']}.\n\n"
        text += markdown_table({'experiments':[next(r for r in summary['experiments'] if r['id']==record['id'])]})
        # Global MLP hyperparameters must not be attributed to simple baseline methods.
        if record['method']=='logistic':
            specific = f"Multinomial logistic regression: C={protocol.get('logistic_C')}, max_iter={protocol.get('logistic_max_iter')}. Neural architecture, AdamW, batches and epochs do not apply. See the [scikit-learn estimator](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)."
        elif record['method']=='class_prior':
            specific = 'Class-prior baseline fitted on training labels. Neural architecture, optimizer, batches and epochs do not apply. The committed study source defines prediction behavior.'
        else:
            specific = methodology
        text += '\n\n## Method, provenance, and learning\n\n'+specific+'\n\n'+record.get('expected_observation','See protocol.')+'\n\n'+record.get('limitations','See consolidated limitations.')
        text += f"\n\nProtocol SHA256: `{record.get('protocol_sha256')}`. Code SHA256: `{record.get('code_sha256')}`.\n"
        (reports/f"experiment-{record['id']}.md").write_text(text,encoding='utf-8')
    root_readme = project/'README.md'
    original = root_readme.read_text(encoding='utf-8') if root_readme.exists() else '# '+project.name+'\n'
    start,end = '<!-- EUREKA:RESULTS:START -->','<!-- EUREKA:RESULTS:END -->'
    block = f'{start}\n## Recorded results\n\n{status_text}\n\n{table}\n\n{primary_text}\n\nSee [full report](cycles/{cycle.name}/reports/summary.md).\n{end}'
    if start in original and end in original:
        original = original[:original.index(start)]+block+original[original.index(end)+len(end):]
    else:
        original += '\n\n'+block+'\n'
    root_readme.write_text(original,encoding='utf-8')
    model_dir = cycle/'models'
    model_dir.mkdir(exist_ok=True)
    (model_dir/'README.md').write_text('---\ntags:\n- reproducibility\n---\n\n# '+project.name+'\n\n'
                                     'Experimental checkpoints. Input definitions, preprocessing and usage limitations are specified by the registered protocol and reproduction guide.\n\n'+table+'\n\n'+primary_text+'\n\n'+methodology+'\n\n'+references,encoding='utf-8')
    if (cycle/'study.py').exists():
        shutil.copy2(cycle/'study.py',model_dir/'study.py')
        shutil.copy2(cycle/'research/protocol.json',model_dir/'protocol.json')
    site = project/'site'
    site.mkdir(exist_ok=True)
    site_paper = paper.replace('](../figures/','](figures/')
    if not repository_url:
        site_paper = site_paper.replace('](../',f'](../cycles/{cycle.name}/')
    (site/'paper.md').write_text(site_paper,encoding='utf-8')
    for figure_path in (cycle/'figures').glob('*.png'):
        (site/'figures').mkdir(exist_ok=True)
        shutil.copy2(figure_path,site/'figures'/figure_path.name)
    (site/'index.html').write_bytes(files('auto_eureka_scientist').joinpath('resources/explorer.html').read_bytes())
    write_json(site/'data.json',{'title':project.name,'cycle':cycle.name,**summary,
                               'run_status':run_status,
                               'records':[{**r,'outcome':r.get('outcome','measured')} for r in experiments(cycle)],
                               'sources':sources,'claims':claims})
    if pdf:
        if not shutil.which('pandoc') or not shutil.which('pdflatex'):
            raise RuntimeError('PDF rendering requires pandoc and pdflatex; Markdown and site outputs were preserved')
        # Inline images avoid longtable/float interactions that can overlap page footers.
        # https://pandoc.org/MANUAL.html#extension-implicit_figures
        command(['pandoc','paper.md','--from=markdown-implicit_figures','--standalone','--pdf-engine=pdflatex','-o','paper.pdf'],reports,timeout=timeout,cancelled=cancelled)
        shutil.copy2(reports/'paper.pdf',site/'paper.pdf')
    return summary

