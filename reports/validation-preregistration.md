# Prospective harness validation

Registered before any live Haiku/Luna inference or trained validation result. The implementation, tests, README, this document, and fixed scientific protocol will be committed and pushed before those calls. Offline fake CLI outputs and unit-test arithmetic are fixtures, not scientific results.

## Questions and hypotheses

The primary engineering question is whether the harness can execute its required phases with verified artifacts and public receipts through each selected backend within the assigned limits. The engineering hypothesis is that each independent trial completes the required cycle. It is falsified for a trial by a persistent failure, missing required evidence, or a cap reached before completion. Partial completion is published honestly. This is an existence test, not an estimate of general agent reliability.

The scientific question is whether the preregistered regularized MLP improves test accuracy relative to the unregularized MLP. A positive effect is a hypothesis, not an expected acceptance condition. Both negative and inconclusive outcomes can satisfy the engineering criterion.

## Fixed design

Haiku and Luna run sequentially from identical task and fixture specifications in independent local directories, GitHub repositories, and HF collections. Each gets at most **60 active minutes and 20 coding-CLI invocations**, counting failed calls and retries. Each run selects one backend and model throughout, including reviews and helpers. Other model options are not live-tested. Exact model identities are recorded when exposed by the CLI; unavailable identities are explicitly labeled, never guessed. No model substitution rescues a failed run.

The [machine-readable protocol](../src/auto_eureka_scientist/resources/digits_protocol.json) is authoritative for the scientific configuration. Scikit-learn's bundled digits data is attributed to [UCI](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits). Split seed 42 creates a stratified 60/20/20 partition by splitting off 40% then halving the held-out part. Integer rounding follows scikit-learn. Pixel values are divided by their documented range, 16; no held-out preprocessing is fitted.

The MLP has dimensions 64 → 128 → 10, ReLU, AdamW, learning rate 0.001, batch size 64, and 50 fixed epochs. Compare weight decay 0.01 to 0 using seeds 0, 1, 2. Weight decay 0.001 is descriptive sensitivity analysis. Logistic regression, a training class-prior baseline, and shuffled-training-label controls are included. Neural arms share initialization and minibatch-order seeds. No test outcome selects hyperparameters or epochs.

Publish the regularized seed-0 pilot using validation results before comparisons. Reuse its frozen checkpoint for its final registered test evaluation. Save configurations, predictions, split IDs, histories and checkpoints. Use CUDA when supported and record the actual execution device. Provider inference is remote and cannot use this local GPU.

## Primary analysis and falsification

The primary scientific effect is the mean regularized-minus-unregularized test accuracy difference across registered seeds. Resample test-example indices jointly across seeds and methods, with 10,000 bootstrap draws and bootstrap RNG seed 2026. Report the percentile 95% interval, explicitly conditional on this fixed set of trained models, plus separate per-seed effects and their sample standard deviation. The interval does not quantify uncertainty over unseen training seeds, writers, or datasets.

An interval wholly above zero supports improvement under this protocol; wholly below zero contradicts it; overlapping zero is inconclusive. Retain every comparison and failed attempt. Do not choose among protocols or analyses using observed test outcomes. New hypotheses informed by results need a new prospective protocol and untouched data, or exploratory labeling.

Alternative explanations include no meaningful decay effect, harmful decay, seed variability, a coding error, leakage, or a stronger simple baseline. Prediction recomputation, disjoint split assertions, paired designs, checkpoint reload checks, the decay ablation, the shuffled-label control, and the logistic/class-prior baselines address specific alternatives. Writer-level generalization cannot be established from these random example partitions. The supplied fixture creates a common implementation confound; these trials do not measure independent algorithm discovery.

## Evidence and stopping

The engineering primary metric is verified completion of all required operational phases and artifacts. Secondary descriptive quantities are CLI calls, active wall time, retry/failure reasons, observed search use, exposed model identities, and reported usage. Missing costs remain unknown. No statistical comparison between providers is planned.

Verify fake CLI transports and recovery before live calls. After the live trials verify fresh-clone setup, numerical regeneration, checkpoint loading, PDF layout, browser filtering, public URLs and HF artifacts. Publish failed or partial trials and preserve their remaining work. One substantive review is planned, with additional fixes only for concrete failures. No open-ended review loop.

Methodological guidance: [Neel Nanda](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL), [Lones](https://arxiv.org/abs/2108.02497), [Lipton and Steinhardt](https://arxiv.org/abs/1807.03341), and the [NeurIPS checklist](https://neurips.cc/public/guides/PaperChecklist).
