# Auto Eureka Scientist development

New console validation invokes only Claude Haiku (`haiku`) and GPT-6 Luna (`gpt-6-luna`), in separate runs without fallback. Historical Sonnet/Sol authorization and results do not authorize new console validation on those models. Follow `reports/console-validation-preregistration.md` before live calls. Include `--extra ui` in the CUDA-host test command. Regenerate the settings reference and console acceptance tables with `uv run python scripts/console_reference.py`; keep test projects under ignored `tmp/`.

Read `prompts/full.txt`, the unchanged canonical user policy. Do not modify it or its packaged copy independently. Preserve the approved workflow and the [Neel Nanda research-process reference](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL).

Keep one backend and model per recorded run. The user also authorized Sonnet and GPT-6.1 Sol. The user explicitly authorized larger budgets after the original Haiku cutoff: preserve that bounded result and use recorded extensions without resetting counters. Run fake CLI tests before live calls. Commit and push core and prospective validation addenda before new inference. Never erase negative outcomes or turn observed findings into prospective confirmation. Use the shared Hugging Face research collection documented in reports/validation-extension-preregistration.md.

Use `uv`, the local environment, modular Python and source-linked explanations. Run `uv run --extra research --extra cuda pytest` on this CUDA host. Keep `.env`, credentials, `.eureka` raw transcripts, and child project directories out of Git. Public numerical results must be regenerated from saved result files. Read `docs/architecture.md` before changing recovery or publication semantics.
