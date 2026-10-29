# Preserve cited audits before controller rechecks

During the Sol replication, the model wrote a detailed non-training audit to `research/core-checks.json` and cited its hash. The controller successfully reran the declared core command, then replaced that file with its shorter receipt. Its later evidence snapshot correctly rejected the changed bytes, leaving the run resumable before core publication. This was a controller ordering defect, not a failed experiment or exhausted model budget.

A failing regression reproduced the collision with a real subprocess. `Controller.check_command` now snapshots cited evidence before either the repeat command or the controller's receipt can replace it. The full offline suite passes; counts are generated from `reports/offline-tests.xml`.

Sol's saved native CLI output contained the original audit's command records. The parent reconstructed a candidate using those outputs and unchanged environment metadata, accepted it only because its bytes matched the previously recorded hash, and saved it in the existing immutable evidence store. The controller's own receipt remains intact. [The recovery receipt](verification/sol-core-evidence-recovery.json) records both hashes. This is a disclosed parent repair outside the model clock, with no new inference or training. It must not be represented as untouched autonomous completion.

The original failed finalization and all consumed calls remain recorded. The fix uses the existing [evidence snapshot mechanism](../src/auto_eureka_scientist/science.py), whose file operations follow [pathlib](https://docs.python.org/3/library/pathlib.html) and whose ignored-file check follows [Git's documented interface](https://git-scm.com/docs/git-check-ignore).
