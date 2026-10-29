# Substantive implementation and methodology review

One review of the implemented controller, adapters, persistence, scientific fixture, reporting and publication was performed after the tested core was pushed. Live execution and presentation checks are recorded separately as evidence becomes available.

## Findings and repairs

- Windows console encoding could fail on valid Unicode output from `doctor`; the public CLI now selects UTF-8 explicitly. Raw subprocess files already used UTF-8/bytes.
- Git's platform newline conversion could change canonical policy bytes and source hashes. Attributes now preserve policy bytes and keep executable text files on LF. The original working-file policy hash remains unchanged; fresh-clone tests pass.
- A local core-check failure initially stopped at finalization instead of entering the bounded repair loop. Checks now run before accepting the handoff, so a concrete test failure can receive a targeted repair.
- Provider errors can contain a null or string `message`; parsing now treats only object messages as assistant containers.
- Bootstrap pairing must align examples across seeds as well as across methods. The analysis now rejects mismatched cross-seed order, and prediction checks reject duplicated/misaligned IDs.
- The class-prior checkpoint path originally marked reload verification without performing the read. The fixture now reloads it and verifies predictions. Baselines report CPU execution rather than inheriting the available neural-device label. Both changes were completed before any training.
- The paper attribution now distinguishes the Codex-authored harness/fixture from the selected backend's research phases and interpretation.
- The live Haiku pilot exposed the provider-message parser issue in the already-running controller. Its terminal event and corrected artifacts were intact. Recovery now recognizes a completed terminal event, reparses and verifies the handoff, and resumes publication without another inference. A fake-process regression reproduces a parser crash at this exact boundary. Historical attempts lacking a saved process exit record retain unknown execution metadata.
- Public-clone inspection now uses published decision history without requiring the private SQLite database. Auxiliary aggregate files no longer count as experiment samples. Local claim evidence has an explicit hash-and-analysis-kind ledger, and resumed repairs receive previous failure details. These fixes followed observed Haiku contract failures; the trial is therefore also a development run, not an untouched evaluation of a frozen harness version.
- Publication subprocesses now honor stop requests while draining both output pipes; PDF subprocesses receive the remaining time budget. Cancellation tests cover this path separately from model invocations.
- Final artifact inspection found two publication defects: Git newline conversion changed byte hashes of Windows-written JSON, and regeneration replaced files cited by a review. Cycle/site artifacts now preserve exact bytes; public evidence receives immutable content-addressed snapshots before later edits. A real Git commit/checkout regression covers CRLF preservation, and a renderer regression checks that reviewed content remains available. The controller now verifies artifacts after publication. The initial failing Luna audit and byte-level diagnosis are retained separately from repaired verification receipts.

## Scientific assessment and limits

The weight-decay effect is a controlled fixed-architecture comparison, conditional on the dataset split and registered seeds. Paired example bootstrap resampling preserves dependence across methods and seeds, but does not quantify generalization to new writers, datasets, training-population randomness, or adaptive follow-up hypotheses. Seed variation is separately descriptive. The shuffled-label control addresses a specific memorization/leakage concern; it cannot rule out every confound.

Shared fixture code and deterministic seeds prevent interpreting differences between the trials as independent algorithm-discovery ability. CLI identities are reported only when exposed; requested identifiers are explicitly distinguished. Citation retrieval and schema validation cannot establish semantic correctness or causal truth. No exhaustive security claim is made: unrestricted native execution is intentional, and the publication exclusion scan is limited.

Publication is resumable at accepted handoffs and receipts. A hard OS crash can leave orphaned processes needing inspection. Exact-once external publication cannot be guaranteed across every service/network failure, although repository/PR discovery, content-based upload receipts, and collection existence checks cover ordinary retries. Public deployment, PDF layout, checkpoint loading and browser interactions require the separate final verification.
