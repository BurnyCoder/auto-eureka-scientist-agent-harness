"""Rebuild the harness validation report from saved trial evidence, without inference.

The supplied scientific definitions are shared; no provider-ranking statistic is inferred.
"""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import statistics
import xml.etree.ElementTree as ET

from auto_eureka_scientist.reporting import metrics, markdown_table, summarize_records, figures
from auto_eureka_scientist.architecture import architecture_panel, render_architecture
from auto_eureka_scientist.science import experiments
from auto_eureka_scientist.util import read_json, write_json


def collect(root: Path):
    trials = []
    destination = root/'reports/validation-data'
    destination.mkdir(parents=True,exist_ok=True)
    for name,backend in [('haiku-original',None),('haiku-extended','haiku'),('luna','luna'),('sonnet','sonnet'),('sol','sol')]:
        if backend is None:
            trial = read_json(destination/'haiku.json')
            trial['name'] = name
            publication = read_json(root/'reports/verification/haiku-final-publication.json')
            trial['explorer'] = trial['repository']+'/blob/'+publication['github']['sha']+'/site/paper.pdf'
            trial['summary'] = summarize_records(trial['records'],trial['protocol'])
            trials.append(trial)
            continue
        project = root/'workspaces'/f'eureka-digits-{backend}'
        summaries = sorted((project/'reports').glob('run-*.json'))
        saved = destination/f'{name}.json'
        if summaries:
            run = read_json(summaries[-1])
            cycle = project/'cycles/001'
            summary = metrics(cycle) if (cycle/'research/registration.json').exists() else {'experiments':[],'primary':None}
            records = experiments(cycle)
            trial = {'name':name,'run':run,'summary':summary,'records':records,'protocol':read_json(cycle/'research/protocol.json'),
                     'repository':f'https://github.com/BurnyCoder/{project.name}',
                     'explorer':f'https://BurnyCoder.github.io/{project.name}/',
                     'models':f'https://huggingface.co/BurnyCoder/{project.name}-models'}
            write_json(saved,trial)
        elif saved.exists():
            trial = read_json(saved)
        else:
            continue
        trial['summary'] = summarize_records(trial['records'],trial['protocol'])
        trials.append(trial)
    return trials


def build(root: Path, pdf: bool):
    trials = collect(root)
    render_architecture(root/'reports/figures')
    for extension in ('.png','.svg'):
        shutil.copy2(root/'reports/figures'/f'architecture{extension}',root/'docs/images'/f'architecture{extension}')
    extended = next((trial for trial in trials if trial['name']=='haiku-extended'),None)
    # Keep both execution checkpoints, but do not repeat identical scientific tables/figures.
    repeated = {trial['name'] for trial in trials if trial['name']=='haiku-original'
                and extended and trial['records']==extended['records']}
    scientific_trials = [trial for trial in trials if trial['name'] not in repeated]
    lines = ['| Trial | Status | Completed phases | Calls | Active minutes | Reported model identities |',
             '|---|---|---:|---:|---:|---|']
    for trial in trials:
        run = trial['run']
        identities = sorted({m for a in run['attempts'] for m in a['models']})
        lines.append(f"| {trial['name']} | {run['status']} | {len(run['completed_phases'])} | {run['calls']} | {run['active_seconds']/60:.2f} | {', '.join(identities) or 'not exposed'} |")
    table = '\n'.join(lines)
    comparison = ['| Trial | Method | Test records | Mean accuracy | Seed SD |','|---|---|---:|---:|---:|']
    for trial in scientific_trials:
        methods = sorted({r['method'] for r in trial['summary']['experiments'] if r['split']=='test'})
        for method in methods:
            scores = [r['accuracy'] for r in trial['summary']['experiments'] if r['split']=='test' and r['method']==method]
            spread = f'{statistics.stdev(scores):.6f}' if len(scores)>1 else 'not estimable'
            comparison.append(f"| {trial['name']} | {method} | {len(scores)} | {statistics.mean(scores):.6f} | {spread} |")
    comparison_table = '\n'.join(comparison)
    test_path = root/'reports/offline-tests.xml'
    tests = ''
    if test_path.exists():
        suite = ET.parse(test_path).getroot().find('testsuite')
        tests = f"The saved offline test report records {suite.get('tests')} tests, {suite.get('failures')} failures and {suite.get('errors')} errors."
    body = '# Recorded validation outcomes\n\n'+table+'\n\n'+tests+'\n'
    for trial in trials:
        run = trial['run']
        body += f"\n## {trial['name']}\n\n[Repository]({trial['repository']}) · [Explorer]({trial['explorer']}) · [Model bundle]({trial['models']})\n\n"
        if trial['name'] in repeated:
            body += (f"Recorded status: {run['status']}. {run['message']}\n\n"
                     'Its saved experiment records are unchanged in the continuation. Scientific tables and figures are shown once under haiku-extended; the original cutoff remains in the execution table and linked historical paper.\n')
            continue
        body += f"Recorded status: {run['status']}. {run['message']}\n\n"+markdown_table(trial['summary'])+'\n\n'
        primary = trial['summary']['primary']
        if primary:
            body += f"Mean paired accuracy effect: {primary['mean_difference']:.6f}; conditional 95% interval [{primary['ci95'][0]:.6f}, {primary['ci95'][1]:.6f}]. Decision: **{primary['conclusion']}**. Seed-effect sample SD: {primary['seed_sample_sd']:.6f}.\n"
        else:
            body += 'The primary scientific effect is not yet available.\n'
    interpretation = root/'reports/validation-interpretation.md'
    authored = interpretation.read_text(encoding='utf-8') if interpretation.exists() else 'Validation is in progress. Public links are verified separately; constructing a URL is not proof of publication.'
    body += '\n## Interpretation and limitations\n\n'+authored+'\n'
    (root/'reports/validation-summary.md').write_text(body,encoding='utf-8')
    paper_body = body
    compact = ['| Trial | Recorded status | Phases | Calls | Minutes |','|---|---|---:|---:|---:|']
    for trial in trials:
        run = trial['run']
        compact.append(f"| {trial['name']} | {run['status'].replace('_',' ')} | {len(run['completed_phases'])} | {run['calls']} | {run['active_seconds']/60:.2f} |")
    paper_body = paper_body.replace(table,'\n'.join(compact))
    for trial in scientific_trials:
        paper_body = paper_body.replace(markdown_table(trial['summary']),markdown_table(trial['summary'],compact=True))
        figure_root = root/'reports/figures'/trial['name']
        figures(figure_root,trial['records'],harness_diagram=False)
        for name,caption in [('accuracy','Recorded accuracies'),('examples','First saved test examples per method')]:
            paper_body += f"\n\n## {trial['name']}: {caption}\n\n![{caption}](figures/{trial['name']}/figures/{name}.png)\n\n*{caption}; regenerated from saved predictions.*\n"
    paper = '''---
title: "Auto Eureka Scientist: bounded CLI harness validation"
author: 'Libor “Burny” Burian'
geometry: margin=1in
fontsize: 10pt
---

# Abstract

This report documents bounded executions of a resumable research harness through separately selected coding CLIs. It evaluates observable completion and provenance, not broad scientific competence or comparative provider superiority.

# Context, motivation, and introduction

Long-running research needs persistent evidence, prospective protocols and truthful failure reporting. The harness connects fresh contexts through files and transactional state, then checks phase-specific outputs before accepting progress.

# Background, methods, and related work

The architecture draws on [Anthropic's harness design](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents) and [Neel Nanda's research process](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL). Statistical and reporting guidance comes from [Lones](https://arxiv.org/abs/2108.02497), [Lipton and Steinhardt](https://arxiv.org/abs/1807.03341), and the [NeurIPS checklist](https://neurips.cc/public/guides/PaperChecklist). Source/license decisions are documented in docs/sources.md.

The local operator console adds schema-driven configuration, a versioned spec queue, serial budgeted Q&A, conversational steering and replayable execution events using [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/). An owned worker continues independently of browser connections. Loop counts advance only after the existing phase checks and required publication succeed; active-time accounting includes chat and configured delays and excludes operator pauses. Immutable spec snapshots and transactional completion markers preserve recovery semantics. This changes the harness interface and control plane, not the scientific methods or previously observed results. Separate console engineering evidence and its Haiku/Luna-only prospective smoke protocol are documented in reports/console-acceptance.md and reports/console-validation-preregistration.md.

The original bounded trials follow reports/validation-preregistration.md. The user-authorized Haiku continuation and Sonnet/GPT-6.1 Sol replications follow reports/validation-extension-preregistration.md. Original and extended Haiku rows are successive observations of the same run, not independent trials. Sonnet and Sol use known evaluation data and are explicitly exploratory engineering replications. The scientific definitions retain the fixed weight-decay comparison, simple baselines, shuffled training labels, registered seeds and descriptive sensitivity. Test-example bootstrap intervals condition on the trained models. The shared implementation is a confound for any claim about independent algorithm discovery.

\\clearpage

![Research cycle, publication gates and optional return to a new cycle.](figures/architecture-phases.png){width=95%}

*Operational phases. Distillation and review may reopen earlier work; changed hypotheses preserve earlier observations in a separate cycle.*

\\clearpage

![Execution loop, durable memory and bounded recovery.](figures/architecture-runtime.png){width=100%}

*Execution architecture. The selected CLI produces evidence; the controller verifies, persists and publishes it. See [architecture and recovery](https://github.com/BurnyCoder/auto-eureka-scientist-agent-harness/blob/main/docs/architecture.md) for implementation details.*

\\clearpage

# Results, claims, discussion, and implications

'''+paper_body+'''

\\clearpage

# Conclusion

These are particular observed executions. Successful artifact checks do not prove semantic correctness, causal validity, or source support. Negative and incomplete outcomes remain part of the record.

# Appendix: reproduction

Install the locked harness environment and run `uv run --extra research python scripts/summarize_validation.py`. Saved validation JSON supports regenerating this report without private transcripts or further model calls. Trial repositories retain their protocols, predictions, code and publication history; checkpoints reside in the corresponding model bundles.

# AI statement

Codex wrote this harness codebase and report from the exact specification supplied by a human. The selected CLI performed each trial's research phases. Human cleanup and rewriting are in progress.
'''
    (root/'reports/validation-paper.md').write_text(paper,encoding='utf-8')
    readme = root/'README.md'
    content = readme.read_text(encoding='utf-8')
    start,end = '<!-- VALIDATION:START -->','<!-- VALIDATION:END -->'
    block = (f'{start}\n## Recorded validation\n\n{table}\n\n[Full report](reports/validation-summary.md). {tests}\n\n'
             'Saved test accuracies by method. SD describes the recorded seed variation, not a confidence interval.\n\n'
             f'{comparison_table}\n\n![All recorded Luna scores, including the validation pilot](reports/figures/luna/figures/accuracy.png)\n{end}')
    if start in content:
        content = content[:content.index(start)]+block+content[content.index(end)+len(end):]
    else:
        content += '\n\n'+block+'\n'
    readme.write_text(content,encoding='utf-8')
    site = root/'site'
    site.mkdir(exist_ok=True)
    (site/'figures').mkdir(exist_ok=True)
    for diagram in (root/'reports/figures').glob('architecture*.svg'):
        shutil.copy2(diagram,site/'figures'/diagram.name)
    # Root Pages links to independent trial explorers; it does not combine test outcomes.
    rows = ''.join(f'<tr><td>{t["name"]}</td><td>{t["run"]["status"].replace("_"," ")}</td><td>{len(t["run"]["completed_phases"])}</td><td>{t["run"]["calls"]}</td><td><a href="{t["explorer"]}">Explore evidence</a></td></tr>' for t in trials)
    (site/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Auto Eureka Scientist</title>
<style>body{font:17px/1.6 system-ui;max-width:980px;margin:auto;padding:40px;color:#18313c;background:#f5f7f8}h1{font-size:3rem;line-height:1.1}table{width:100%;border-collapse:collapse;background:white}td,th{padding:14px;text-align:left;border-bottom:1px solid #ccdce3}a{color:#006a98}.tag{letter-spacing:.14em;color:#54727f;font-size:.8rem}.scroll{overflow:auto}@media(max-width:600px){body{padding:18px}td,th{padding:10px}}</style>
<div class="tag">DURABLE RESEARCH / OBSERVABLE EVIDENCE</div><h1>Auto Eureka Scientist</h1>
<p>One selected coding CLI, persistent scientific artifacts, and explicit completion checks.</p>
'''+architecture_panel()+'''
<h2>Recorded validation</h2>
<p>These executions share fixed scientific definitions. Their outcomes do not establish general scientific reliability or rank the providers.</p>
<p>The original and extended Haiku rows describe the same run before and after an explicitly authorized budget increase. The original cutoff is preserved. Luna required post-run provenance repairs. Sonnet and GPT-6.1 Sol are exploratory replications with prior results known. Read the report for failures and interventions.</p>
<p>Parent review corrected scientific overclaims in Haiku and Sonnet. Sonnet's first call was rejected for background Haiku usage; later accepted calls used its explicit Sonnet pin. Sol required recovery of an audit overwritten by the controller. Completed phases do not mean an untouched autonomous run.</p>
<div class="scroll"><table><thead><tr><th>Trial</th><th>Status</th><th>Phases</th><th>Calls</th><th>Evidence</th></tr></thead><tbody>'''+rows+'''</tbody></table></div>
<p><a href="validation-paper.pdf">Validation paper</a> · <a href="validation-summary.md">Full report</a> · <a href="https://github.com/BurnyCoder/auto-eureka-scientist-agent-harness">Code and prospective protocol</a> · <a href="https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL">Neel Nanda's research process</a></p></html>''',encoding='utf-8')
    shutil.copy2(root/'reports/validation-summary.md',site/'validation-summary.md')
    if pdf:
        subprocess.run(['pandoc','validation-paper.md','--from=markdown-implicit_figures','--standalone','--pdf-engine=pdflatex','-o','validation-paper.pdf'],cwd=root/'reports',check=True,timeout=180)
        shutil.copy2(root/'reports/validation-paper.pdf',site/'validation-paper.pdf')
    # Keep raw observations once in reports/validation-data; the hub needs summaries only.
    write_json(site/'validation.json',[{key:trial[key] for key in ('name','summary','repository','explorer','models')}
                                      for trial in trials])


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-pdf',action='store_true')
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1],not args.no_pdf)
    from console_reference import generate
    generate()
