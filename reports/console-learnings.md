# Console implementation and validation notes

The scope and pass criteria for live inference were committed in [the prospective addendum](console-validation-preregistration.md) before either provider call. [Generated acceptance evidence](console-acceptance.md) reports saved outcomes; the earlier scientific validation and negative results remain unchanged. This work tests controller behavior, not autonomous scientific validity.

## Design and evidence

The console extends the existing controller instead of adding a second research agent. Dataclass field metadata supplies the settings schema, browser forms, validation and reference documentation. Native [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/) and durable SQLite event IDs provide streaming and reconnection. [SQLite transactions](https://docs.python.org/3/library/sqlite3.html#transaction-control) associate cycle outcomes with queue advancement; owned subprocesses retain the existing project lock. Source and license details are in [the source register](../docs/sources.md).

Fake CLIs exercise both provider wire formats and deliberately fail or interrupt at recovery boundaries. Browser acceptance used the actual local server, worker, streaming endpoints, settings forms and spec editor with those fake transports. It covered phase stepping, paused questions, queue duplication, finite completion, an unlimited-loop run stopped by active time, reload/reconnection, presets, saved defaults, and read-only artifact preview. Automated tests cover publication failure recovery, competing controllers, duplicate actions, pause/stop/interrupt, shuffle persistence and completion crashes.

The live observations used only Haiku and Luna, each in its own recorded run, with no fallback or retry. Both answered through an owned worker without advancing research phases. Haiku exposed a provider model identifier; Luna's stream did not, so its resolved identity remains unavailable. Luna logged an optional MCP connector startup HTTP failure while the requested answer still completed. That warning is preserved in the private stderr transcript and summarized in the saved acceptance record. These observations establish only the preregistered transport/accounting behavior.

## Issues found and corrections

- An empty spec selection was treated as an absent receipt. Distinguishing an absent receipt from a recorded empty selection now pauses empty queues consistently.
- The initial browser layout hid the queue editor on narrow screens. The responsive layout now keeps the editor accessible and wraps phase navigation.
- SSE tests initially assumed an event-field order. The wire protocol ends a record with a blank line; the test now parses that boundary, following the [EventSource specification](https://html.spec.whatwg.org/multipage/server-sent-events.html).
- Saved project defaults were not reflected in the new-run form, and a saved preset did not appear immediately in the list. Failing regression tests reproduced the default-resolution gap; the API now rereads project defaults with documented precedence, and the form/preset list refreshes. Browser verification confirmed both fixes.
- Chat recovery originally accepted a schema-valid message without requiring the provider's terminal marker. A truncated-turn regression reproduced this failure. Scientific phases and chat now share the terminal-event check; an incomplete recovered question fails visibly without another charged invocation.
- CLI resume originally used a separate configuration-history path, and OpenAPI exposed settings as an untyped dictionary. Reproducing tests now require the shared revision/timing audit and schema annotations, including the cycle-scoped override subset. CLI resume applies the same immutable-setting checks as HTTP patches while retaining its legacy history receipt.
- The live question context contained a phase index without its name. Both replies correctly avoided inventing a name. Subsequent prompt construction includes the controller's named next phase; the recorded live observations have not been replaced with a later result.
- Earlier-phase navigation and revised-cycle requests needed distinct recovery behavior. Current phase projections are invalidated transactionally, historical decisions remain retained, and an explicit revised cycle freezes the latest edited spec without rewriting the previous cycle snapshot.

The full CUDA-host suite and its individual results are saved in `console-tests.xml`. The paper's added harness paragraph was regenerated from the existing report script and visually inspected. It does not change the numerical scientific results. The UI screenshot is an explicit offline fixture illustration.

## Limits

Provider-reported identity, cost and hardware telemetry can be absent. Raw prompts and chat remain private; public smoke records include only status, counters, usage and a nonempty-reply flag. Hard crashes can lose elapsed time since the last heartbeat. The local interface is not a multi-user authentication service. Fixed benchmark data and existing scientific checks still limit any inference about research quality; new UI controls do not remove those limits.
