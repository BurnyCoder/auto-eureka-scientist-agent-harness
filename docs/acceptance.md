# Requirement-to-evidence map

This map distinguishes implemented behavior from observed live acceptance. The [generated report](../reports/validation-summary.md) records the outcomes: Haiku remained incomplete; Luna's accepted workflow required disclosed post-publication provenance repairs. Trial-specific section checklists and results are retained in each project. Neither execution is a frozen-version autonomy benchmark.

| Requirement | Evidence location |
|---|---|
| Existing work, licenses, sources | `docs/sources.md`; trial source/retrieval ledgers |
| Scientific mindset and Neel stages | `policy.py`, `contracts.py`, `docs/research-contracts.md` |
| Preregistration/statistical design | `reports/validation-preregistration.md`, immutable cycle protocol and registration |
| Technical grounding/simplicity/modularity | Source-linked modules; public entry point delegates to controller/phases |
| Claims, positive/negative findings | Claim/evidence checks and generated reports |
| Paper, author and AI statement | `reporting.py`; statement only at paper bottom |
| Eval tables, examples, plots | `reporting.py`, static explorer; missing objectives labeled |
| Per-experiment and consolidated learnings | Experiment JSON, generated experiment reports and summary; decisions/highlights |
| README/install/reproduction/docs | Root README, docs, trial reproduction instructions and locked dependencies |
| Order of work | Core/preregistration commits precede live calls; core/pilot publication gates |
| Complete timestamped logs | Raw pipes and transcripts under ignored `.eureka` |
| Tests/debugging/review | Fake CLI unit/integration tests; trial review artifacts; final verification report |
| GitHub/PRs/Pages/HF | `publication.py`, idempotent receipts and public URLs |
| uv/local environment/.env | Project setup, lockfile, `.env.example`, ignored local config |
| Scope and local GPU | Selected project cwd; recorded actual CUDA/CPU device |
| Generated numbers and consistency | `eureka render` derives tables/figures/model cards/site from saved predictions |
| Final checks and visual inspection | Public-clone, checkpoint, PDF and browser receipts under `reports/verification/`; failures and repairs retained |

The final artifact checks are independent of accepted phase counts. Regeneration and parent verification do not fill missing Haiku phases or add unrecorded work to either model's budget. Luna's initial failing verification, exact-byte diagnosis and repair ledger document why its original completion status was insufficient. Public evidence snapshots and Git byte-preservation tests address the observed defects.

Full local CLI streams remain in ignored runtime directories. Published execution summaries expose status, prompt hashes, attempts and reported model usage without raw transcripts or credentials. A byte hash verifies identity, not semantic truth; source inspection and claim review still require research judgment. The implementation review documents additional limits of publication retries and hard-crash recovery.

Reward plots do not apply to the supervised digits objective. Counterfactual concept swapping is not part of this classification protocol; weight-decay intervention and label shuffling are the specified causal/mechanistic probes. The harness itself has no trained weights; model uploads apply to its validation studies. These exceptions must remain explicit in the relevant reports.
