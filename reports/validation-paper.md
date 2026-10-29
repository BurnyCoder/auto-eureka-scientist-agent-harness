---
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

Each trial uses the same supplied digits fixture and prospective protocol in reports/validation-preregistration.md. The fixed weight-decay comparison includes simple baselines, shuffled training labels, multiple seeds and descriptive sensitivity. Test-example bootstrap intervals condition on the trained models. The shared implementation is a confound for any claim about independent algorithm discovery.

# Results, claims, discussion, and implications

# Recorded validation outcomes

| Trial | Recorded status | Phases | Calls | Minutes |
|---|---|---:|---:|---:|
| haiku | budget exhausted | 5 | 17 | 60.00 |
| luna | complete | 8 | 10 | 27.29 |

The saved offline test report records 27 tests, 0 failures and 0 errors.

## haiku

[Repository](https://github.com/BurnyCoder/eureka-digits-haiku) · [Explorer](https://BurnyCoder.github.io/eureka-digits-haiku/) · [Model bundle](https://huggingface.co/BurnyCoder/eureka-digits-haiku-models)

Recorded status: budget_exhausted. budget_exhausted

| Method | Seed | Split | Accuracy | Seconds | Device |
|-------------------------|-----:|------------|-----------:|----------:|----------|
| class prior | 0 | test | 0.102778 | 0.026 | cpu |
| logistic | 0 | test | 0.955556 | 0.107 | cpu |
| regularized | 0 | validation | 0.966574 | 6.805 | cuda |
| regularized | 0 | test | 0.963889 | 0.486 | cuda |
| regularized | 1 | test | 0.969444 | 6.630 | cuda |
| regularized | 2 | test | 0.969444 | 2.553 | cuda |
| sensitivity | 0 | test | 0.963889 | 2.525 | cuda |
| sensitivity | 1 | test | 0.969444 | 2.583 | cuda |
| sensitivity | 2 | test | 0.969444 | 2.481 | cuda |
| shuffled labels | 0 | test | 0.061111 | 2.465 | cuda |
| shuffled labels | 1 | test | 0.116667 | 2.470 | cuda |
| shuffled labels | 2 | test | 0.108333 | 2.367 | cuda |
| unregularized | 0 | test | 0.963889 | 2.426 | cuda |
| unregularized | 1 | test | 0.969444 | 2.393 | cuda |
| unregularized | 2 | test | 0.969444 | 2.501 | cuda |

Mean paired accuracy effect: 0.000000; conditional 95% interval [0.000000, 0.000000]. Decision: **inconclusive**. Seed-effect sample SD: 0.000000.

## luna

[Repository](https://github.com/BurnyCoder/eureka-digits-luna) · [Explorer](https://BurnyCoder.github.io/eureka-digits-luna/) · [Model bundle](https://huggingface.co/BurnyCoder/eureka-digits-luna-models)

Recorded status: complete. All required phases completed

| Method | Seed | Split | Accuracy | Seconds | Device |
|-------------------------|-----:|------------|-----------:|----------:|----------|
| class prior | 0 | test | 0.102778 | 0.038 | cpu |
| logistic | 0 | test | 0.955556 | 0.107 | cpu |
| regularized | 0 | validation | 0.966574 | 7.616 | cuda |
| regularized | 0 | test | 0.963889 | 0.288 | cuda |
| regularized | 1 | test | 0.969444 | 6.002 | cuda |
| regularized | 2 | test | 0.969444 | 2.192 | cuda |
| sensitivity | 0 | test | 0.963889 | 2.394 | cuda |
| sensitivity | 1 | test | 0.969444 | 2.348 | cuda |
| sensitivity | 2 | test | 0.969444 | 2.258 | cuda |
| shuffled labels | 0 | test | 0.061111 | 2.333 | cuda |
| shuffled labels | 1 | test | 0.116667 | 2.353 | cuda |
| shuffled labels | 2 | test | 0.108333 | 2.369 | cuda |
| unregularized | 0 | test | 0.963889 | 2.235 | cuda |
| unregularized | 1 | test | 0.969444 | 2.374 | cuda |
| unregularized | 2 | test | 0.969444 | 2.323 | cuda |

Mean paired accuracy effect: 0.000000; conditional 95% interval [0.000000, 0.000000]. Decision: **inconclusive**. Seed-effect sample SD: 0.000000.

## Interpretation and limitations

The engineering endpoint is verified phase and artifact completion, independent of the direction of the regularization effect. Haiku reached the active-time cap with analysis, review and final publication unaccepted. That trial did not satisfy the completion criterion. Its draft claims and interpretation remain available for diagnosis but are excluded from the generated paper and explorer. Parent publication of available results did not complete those missing phases.

Luna's controller accepted the workflow within its limits. A later audit found that Git newline conversion and regenerated documents invalidated evidence hashes. Exact historical bytes were recovered from reversible newline changes and saved review copies, then pinned in immutable snapshots. The final repaired artifacts pass the recorded checks; this outcome required post-run mechanical repair and does not demonstrate untouched autonomous completion. Initial failures, diagnosis and repaired receipts are retained in `reports/verification/` and the trial repository.

Both trials actually used search, editing, execution, CUDA training, reporting and publication. The prospective protocol and tested harness were pushed before any live call. The pilot checkpoint and validation findings preceded sensitivity experiments. Only the selected provider/model was invoked within each run. Claude reported its resolved identity; Codex did not expose one, so its requested identifier must not be mistaken for a verified snapshot. No other model option was live-tested.

The trials used the same supplied training implementation, task and protocol. Their matching scientific predictions therefore do not show independent algorithm invention. Harness defects were repaired during development and the later trial inherited those repairs. Active time excludes controller downtime between resumes; repair and post-run verification work is disclosed separately. The table is a record of these executions, not a fair provider comparison, frozen-version benchmark or guarantee about future research.

The primary directional result is inconclusive. The observed paired correctness outcomes coincide, causing the empirical bootstrap interval to collapse. This is not an equivalence test or a guarantee about unseen examples. The intervals condition on the fitted models and fixed example split; seed variability is separate and neither covers new writers or datasets. Descriptive control and sensitivity outcomes remain exploratory. Near-chance shuffled-label performance cannot rule out every implementation error or leakage pathway.

The pilot fixture evaluates test features without their labels when checking checkpoint reload; only validation predictions are scored and saved for the pilot. Claims that no test features were accessed would be inaccurate. No test outcome selected the registered configuration. The available dataset fields do not support a writer-held-out evaluation.

Public checkpoints were loaded with tensor-only or non-pickle readers and their predictions compared with saved records. Numerical tables are recomputed from raw predictions; figures use explicit scales and identify unavailable measurements. PDF pages and interactive filters were inspected separately. These checks establish specific reproducible artifacts, not semantic correctness of every source or general scientific validity. Reward curves and model weights for the harness itself are inapplicable; the supervised validation studies provide loss curves and model collections.



## haiku: Recorded accuracies

![Recorded accuracies](figures/haiku/figures/accuracy.png)

*Recorded accuracies; regenerated from saved predictions.*


## haiku: First saved test examples per method

![First saved test examples per method](figures/haiku/figures/examples.png)

*First saved test examples per method; regenerated from saved predictions.*


## luna: Recorded accuracies

![Recorded accuracies](figures/luna/figures/accuracy.png)

*Recorded accuracies; regenerated from saved predictions.*


## luna: First saved test examples per method

![First saved test examples per method](figures/luna/figures/examples.png)

*First saved test examples per method; regenerated from saved predictions.*


# Conclusion

These are particular observed executions. Successful artifact checks do not prove semantic correctness, causal validity, or source support. Negative and incomplete outcomes remain part of the record.

# Appendix: reproduction

Install the locked harness environment and run `uv run --extra research python scripts/summarize_validation.py`. Saved validation JSON supports regenerating this report without private transcripts or further model calls. Trial repositories retain their protocols, predictions, code and publication history; checkpoints reside in the corresponding model bundles.

# AI statement

Codex wrote this harness codebase and report from the exact specification supplied by a human. The selected CLI performed each trial's research phases. Human cleanup and rewriting are in progress.
