# Requirement-to-evidence map

This map describes implementation evidence, not a claim that live acceptance already passed. Trial-specific section checklists and results are generated in each project.

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
| Final checks and visual inspection | Trial acceptance and final parent verification artifacts, initially pending |

Reward plots do not apply to the supervised digits objective. Counterfactual concept swapping is not part of this classification protocol; weight-decay intervention and label shuffling are the specified causal/mechanistic probes. The harness itself has no trained weights; model uploads apply to its validation studies. These exceptions must remain explicit in the relevant reports.
