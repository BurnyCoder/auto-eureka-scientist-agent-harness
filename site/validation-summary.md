# Recorded validation outcomes

| Trial | Status | Completed phases | Calls | Active minutes | Reported model identities |
|---|---|---:|---:|---:|---|
| haiku | budget_exhausted | 5 | 17 | 60.00 | claude-haiku-5-5 |
| luna | complete | 8 | 10 | 27.29 | not exposed |

The saved offline test report records 27 tests, 0 failures and 0 errors.

## haiku

[Repository](https://github.com/BurnyCoder/eureka-digits-haiku) · [Explorer](https://BurnyCoder.github.io/eureka-digits-haiku/) · [Model bundle](https://huggingface.co/BurnyCoder/eureka-digits-haiku-models)

Recorded status: budget_exhausted. budget_exhausted

| Experiment | Method | Seed | Split | Accuracy | Seconds | Device |
|---|---|---:|---|---:|---:|---|
| class_prior_s0 | class_prior | 0 | test | 0.102778 | 0.026 | cpu |
| logistic_s0 | logistic | 0 | test | 0.955556 | 0.107 | cpu |
| pilot_regularized_s0 | regularized | 0 | validation | 0.966574 | 6.805 | cuda |
| regularized_s0 | regularized | 0 | test | 0.963889 | 0.486 | cuda |
| regularized_s1 | regularized | 1 | test | 0.969444 | 6.630 | cuda |
| regularized_s2 | regularized | 2 | test | 0.969444 | 2.553 | cuda |
| sensitivity_s0 | sensitivity | 0 | test | 0.963889 | 2.525 | cuda |
| sensitivity_s1 | sensitivity | 1 | test | 0.969444 | 2.583 | cuda |
| sensitivity_s2 | sensitivity | 2 | test | 0.969444 | 2.481 | cuda |
| shuffled_labels_s0 | shuffled_labels | 0 | test | 0.061111 | 2.465 | cuda |
| shuffled_labels_s1 | shuffled_labels | 1 | test | 0.116667 | 2.470 | cuda |
| shuffled_labels_s2 | shuffled_labels | 2 | test | 0.108333 | 2.367 | cuda |
| unregularized_s0 | unregularized | 0 | test | 0.963889 | 2.426 | cuda |
| unregularized_s1 | unregularized | 1 | test | 0.969444 | 2.393 | cuda |
| unregularized_s2 | unregularized | 2 | test | 0.969444 | 2.501 | cuda |

Mean paired accuracy effect: 0.000000; conditional 95% interval [0.000000, 0.000000]. Decision: **inconclusive**. Seed-effect sample SD: 0.000000.

## luna

[Repository](https://github.com/BurnyCoder/eureka-digits-luna) · [Explorer](https://BurnyCoder.github.io/eureka-digits-luna/) · [Model bundle](https://huggingface.co/BurnyCoder/eureka-digits-luna-models)

Recorded status: complete. All required phases completed

| Experiment | Method | Seed | Split | Accuracy | Seconds | Device |
|---|---|---:|---|---:|---:|---|
| class_prior_s0 | class_prior | 0 | test | 0.102778 | 0.038 | cpu |
| logistic_s0 | logistic | 0 | test | 0.955556 | 0.107 | cpu |
| pilot_regularized_s0 | regularized | 0 | validation | 0.966574 | 7.616 | cuda |
| regularized_s0 | regularized | 0 | test | 0.963889 | 0.288 | cuda |
| regularized_s1 | regularized | 1 | test | 0.969444 | 6.002 | cuda |
| regularized_s2 | regularized | 2 | test | 0.969444 | 2.192 | cuda |
| sensitivity_s0 | sensitivity | 0 | test | 0.963889 | 2.394 | cuda |
| sensitivity_s1 | sensitivity | 1 | test | 0.969444 | 2.348 | cuda |
| sensitivity_s2 | sensitivity | 2 | test | 0.969444 | 2.258 | cuda |
| shuffled_labels_s0 | shuffled_labels | 0 | test | 0.061111 | 2.333 | cuda |
| shuffled_labels_s1 | shuffled_labels | 1 | test | 0.116667 | 2.353 | cuda |
| shuffled_labels_s2 | shuffled_labels | 2 | test | 0.108333 | 2.369 | cuda |
| unregularized_s0 | unregularized | 0 | test | 0.963889 | 2.235 | cuda |
| unregularized_s1 | unregularized | 1 | test | 0.969444 | 2.374 | cuda |
| unregularized_s2 | unregularized | 2 | test | 0.969444 | 2.323 | cuda |

Mean paired accuracy effect: 0.000000; conditional 95% interval [0.000000, 0.000000]. Decision: **inconclusive**. Seed-effect sample SD: 0.000000.

## Interpretation and limitations

The engineering endpoint is verified phase and artifact completion, independent of the direction of the regularization effect. Haiku reached the active-time cap with analysis, review and final publication unaccepted. That trial did not satisfy the completion criterion. Its draft claims and interpretation remain available for diagnosis but are excluded from the generated paper and explorer. Parent publication of available results did not complete those missing phases.

Luna's controller accepted the workflow within its limits. A later audit found that Git newline conversion and regenerated documents invalidated evidence hashes. Exact historical bytes were recovered from reversible newline changes and saved review copies, then pinned in immutable snapshots. The final repaired artifacts pass the recorded checks; this outcome required post-run mechanical repair and does not demonstrate untouched autonomous completion. Initial failures, diagnosis and repaired receipts are retained in `reports/verification/` and the trial repository.

Both trials actually used search, editing, execution, CUDA training, reporting and publication. The prospective protocol and tested harness were pushed before any live call. The pilot checkpoint and validation findings preceded sensitivity experiments. Only the selected provider/model was invoked within each run. Claude reported its resolved identity; Codex did not expose one, so its requested identifier must not be mistaken for a verified snapshot. No other model option was live-tested.

The trials used the same supplied training implementation, task and protocol. Their matching scientific predictions therefore do not show independent algorithm invention. Harness defects were repaired during development and the later trial inherited those repairs. Active time excludes controller downtime between resumes; repair and post-run verification work is disclosed separately. The table is a record of these executions, not a fair provider comparison, frozen-version benchmark or guarantee about future research.

The primary directional result is inconclusive. The observed paired correctness outcomes coincide, causing the empirical bootstrap interval to collapse. This is not an equivalence test or a guarantee about unseen examples. The intervals condition on the fitted models and fixed example split; seed variability is separate and neither covers new writers or datasets. Descriptive control and sensitivity outcomes remain exploratory. Near-chance shuffled-label performance cannot rule out every implementation error or leakage pathway.

The pilot fixture evaluates test features without their labels when checking checkpoint reload; only validation predictions are scored and saved for the pilot. Claims that no test features were accessed would be inaccurate. No test outcome selected the registered configuration. The available dataset fields do not support a writer-held-out evaluation.

Public checkpoints were loaded with tensor-only or non-pickle readers and their predictions compared with saved records. Numerical tables are recomputed from raw predictions; figures use explicit scales and identify unavailable measurements. PDF pages and interactive filters were inspected separately. These checks establish specific reproducible artifacts, not semantic correctness of every source or general scientific validity. Reward curves and model weights for the harness itself are inapplicable; the supervised validation studies provide loss curves and model collections.

