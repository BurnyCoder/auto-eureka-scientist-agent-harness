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

## Scientific assessment and limits

The weight-decay effect is a controlled fixed-architecture comparison, conditional on the dataset split and registered seeds. Paired example bootstrap resampling preserves dependence across methods and seeds, but does not quantify generalization to new writers, datasets, training-population randomness, or adaptive follow-up hypotheses. Seed variation is separately descriptive. The shuffled-label control addresses a specific memorization/leakage concern; it cannot rule out every confound.

Shared fixture code and deterministic seeds prevent interpreting differences between the trials as independent algorithm-discovery ability. CLI identities are reported only when exposed; requested identifiers are explicitly distinguished. Citation retrieval and schema validation cannot establish semantic correctness or causal truth. No exhaustive security claim is made: unrestricted native execution is intentional, and the publication exclusion scan is limited.

Publication is resumable at accepted handoffs and receipts. A hard OS crash can leave orphaned processes needing inspection. Exact-once external publication cannot be guaranteed across every service/network failure, although repository/PR discovery, content-based upload receipts, and collection existence checks cover ordinary retries. Public deployment, PDF layout, checkpoint loading and browser interactions require the separate final verification.
