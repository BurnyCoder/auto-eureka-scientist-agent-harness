# Prospective console transport validation addendum

This addendum covers new live inference for the local chat/control interface. It does not modify the earlier scientific trials, their registered protocols, or their outcomes. Offline implementation tests were developed before this addendum; they are engineering regression checks, not prospective empirical evidence.

Before any new live call, commit and push the implementation and this addendum. Complete fake-CLI checks for both wire formats first. The only models permitted in this validation are Claude Haiku (`haiku`) and GPT-6 Luna (`gpt-6-luna`), in separate recorded runs, with fallback disabled. Other model settings may be validated as data without invoking them.

**Question and hypothesis.** Can each selected CLI answer a queued question through the console's worker/controller transport while preserving the scientific phase pointer and charging its actual invocation to the same recorded allowance?

**Primary metric.** A smoke passes only if its question becomes `answered`, its reply is nonempty and schema-valid, its phase pointer is unchanged, its call counter increases, and every reported model matches the selected model/family. An unavailable reported identity remains unavailable; requested identity alone does not establish provider execution identity.

**Design and budget.** Use a new private local project for each backend and a fixed question asking it to explain the supplied recorded run state. Publication is disabled. No training, scientific claims, tools that change files, or provider comparison is requested. Set a cumulative maximum of two CLI invocations and five active minutes per backend, with no fallback and no transport/repair retries. The first attempt is the planned observation; the second allowance is reserved for a disclosed mechanical repair, not a replacement observation. Stop after both backends have an outcome. Retain failed attempts.

**Analysis and falsification.** Save run ID, requested/reported identity, message status, before/after phase and call counters, elapsed time and any provider-reported usage. Generate the acceptance table from that JSON. A failed schema, unanswered question, changed phase, mixed model, lost counter, or exhausted allowance falsifies the narrow pass condition for that attempt. Report failure rather than substituting a model or silently extending its budget.

The offline controls test active-time limits, bounded failures, replay, duplicate requests, queue snapshots, interrupted processes, accepted-phase recovery and completion accounting. Browser acceptance uses fake transports and separately records observed interactions. Neither kind of test demonstrates autonomous scientific validity. Sources: [Claude headless CLI](https://code.claude.com/docs/en/headless), [Codex non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode), [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/).
