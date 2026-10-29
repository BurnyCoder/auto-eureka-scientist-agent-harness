# Auto Eureka Scientist development

Read `prompts/full.txt`, the unchanged canonical user policy. Do not modify it or its packaged copy independently. Preserve the approved workflow and the [Neel Nanda research-process reference](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL).

Keep one backend and model per recorded run. Only Haiku and Luna may be used in live validation, including helper/review inference. Run fake CLI tests before live calls. Commit and push core and the validation preregistration before the first live inference. Never erase negative outcomes, reset a trial's counters, or turn observed findings into prospective confirmation.

Use `uv`, the local environment, modular Python and source-linked explanations. Run `uv run --extra research --extra cuda pytest` on this CUDA host. Keep `.env`, credentials, `.eureka` raw transcripts, and child project directories out of Git. Public numerical results must be regenerated from saved result files. Read `docs/architecture.md` before changing recovery or publication semantics.
