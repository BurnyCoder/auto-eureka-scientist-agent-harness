# Reproduce published artifacts without another model call

Clone this harness and install its lockfile. The trial repositories contain source code, prospective protocols, saved predictions, loss trajectories and interpretation. Checkpoints are distributed separately through their Hugging Face model bundles. Neither private SQLite state nor local agent transcripts are required for numerical regeneration.

```powershell
git clone https://github.com/BurnyCoder/auto-eureka-scientist-agent-harness.git
cd auto-eureka-scientist-agent-harness
uv sync --locked --extra research --extra cuda
git clone https://github.com/BurnyCoder/eureka-digits-haiku.git workspaces/eureka-digits-haiku
hf download BurnyCoder/eureka-digits-haiku-models --local-dir workspaces/eureka-digits-haiku/cycles/001/models
uv run --extra research --extra cuda eureka render --project workspaces/eureka-digits-haiku
uv run --extra research --extra cuda eureka verify --project workspaces/eureka-digits-haiku
uv run --extra research --extra cuda python scripts/verify_artifacts.py --project workspaces/eureka-digits-haiku --output reports/haiku-reproduction.json
```

Replace `haiku` with `luna` for the other independently recorded trial. Omit the `cuda` extra on platforms without a compatible CUDA wheel; CPU regeneration is supported. Exact package versions are in `uv.lock`; observed training versions and device details are in each result record. CPU and CUDA installation choices are explicit because wheel availability can differ. The checkpoint verification command performs CPU inference and checks hashes and saved predictions, without training or inference through an LLM.

`render` rebuilds numerical tables, figures, generated experiment reports, the consolidated report, paper, model-card metrics, README results and explorer data. Pandoc and `pdflatex` must be installed for PDF output; `--no-pdf` regenerates the other artifacts. The original predictions remain the source of the regenerated measurements. Authored interpretation and prospective protocols are separate from generated numerical sections.

`verify` reports accepted phase artifacts and remaining failures. A partial trial stays partial after rendering: generating a paper does not complete unaccepted research phases. Model downloads are required before checkpoint-dependent checks pass.

For a new training reproduction, use a new project or cycle and prospectively register it. Do not overwrite the published experiment records or relabel the original observations. The CLI's supplied digits fixture documents its pilot and comparison commands in each trial's cycle documentation.

Rebuild the harness-level validation tables, report, PDF and Pages data from the committed trial snapshots with:

```powershell
uv run --extra research --extra cuda python scripts/summarize_validation.py
```

The saved snapshots preserve the observed trial status. This command does not run either coding CLI, download credentials, or infer that a constructed public URL is reachable. Independent verification receipts are stored under `reports/verification/` when available.
