# Local research console

Install and launch from the harness checkout:

```powershell
uv sync --locked --extra ui --extra research --extra cuda
uv run --extra ui --extra research --extra cuda eureka ui --project workspaces/my-study --port 8765
```

The exact minimal UI launch is `uv run --extra ui eureka ui --project PATH --port 8765`. Install/retain the `research` extra for scientific figures and reports and `cuda` on the CUDA host. The browser uses existing CLI logins. Credentials never appear as configurable fields. `--no-open-browser` keeps the server in the terminal. The server binds to loopback, accepts same-origin mutations with a session token, and restricts artifact paths to this project.

Create a run with a spec, selected backend/model, completed-loop limit and/or active-minute limit. Indefinite repetition removes the loop limit; any other configured limit still applies. One loop completes all eight phases, final verification and required publication. Negative scientific findings can complete a loop; skipped, failed, abandoned and interrupted cycles cannot. The separate started-cycle limit counts those cycles too. Restoring defaults or importing a preset never restores spent time or calls.

The left panel navigates runs and edits the future spec queue. Duplicate/reorder/enable specs and add per-spec cycle settings or structured research requests. The active snapshot remains frozen, with its recorded revision visible. Research parameters are requests to the agent; only registered controller settings enforce behavior directly. Changed registered research needs a revised cycle. Ordered queues wrap; seeded shuffles persist the selected order. Empty enabled queues pause. Skip-on-failure advances after bounded repairs and pauses after the configured number of complete queue passes without a completed loop.

The center shows limits, current phase, accepted phases and chat. Research stages and objectives are the latest recorded handoff with its timestamp, not an inferred live mental state. Details expose provider events, tool/command output, checks, usage, process telemetry, artifacts, source ledgers, saved figures, read-only file diffs and publication receipts. Unavailable cost, identity and hardware measurements are explicitly unavailable. Machine GPU statistics are labeled as machine measurements, not attributed to a particular model process.

## Controls and chat

Resume, pause now, pause after phase, single-phase execution and immediate stop are direct controls. More controls include stop after a loop, retry, skip, revised cycle, earlier-phase request, artifact rechecking, report regeneration and publication recovery. Revisit requests go through a verified agent handoff; they do not bypass scientific checks. Pauses before selected phases/publication are persistent gates: an explicit resume crosses the current gate once. Stop-after-phase/cycle stays configured until cleared.

Ask queues a separate Q&A invocation using the same selected backend/model and budget. It is serial with research and does not accept a phase. Ask on an idle run launches a maintenance worker and returns to the prior run status. Steer supplies instructions at the next invocation, current cycle or rest of run. Interrupt-now first terminates the owned invocation; that interrupted call stays charged. Delivery and answer/failure states remain recorded. The UI never edits research files directly; ask the agent for changes and inspect the resulting diff. Q&A requests instruct the agent to inspect/explain without changing files.

Browser disconnection leaves the owned worker running. Normal server shutdown stops its own worker resumably. A replacement controller rejects competing live owners and uses PID plus creation time when retiring recorded orphan processes. Complete raw transcripts stay in private `.eureka` files; the browser keeps a bounded window with replayable, paginated event history. Do not place secrets into research text or ask the agent to print credentials.

## Configuration and timing

Search Basic/Advanced settings, inspect descriptions, view only changed fields, review a diff, reset defaults, or inspect worker-applied values and history. Save/duplicate named presets, import/export versioned JSON, or save project defaults. These live privately under `.eureka`; exports omit machine-specific project/executable fields and accept only registered keys. Unsupported backend options are disabled with an explanation. Model availability still depends on the installed CLI and account.

New-run precedence is built-in/profile defaults → saved project defaults → named preset → project `.env` → process environment → explicit CLI/UI/API values. Explicit values include imported config and typed overrides. Resume uses its recorded settings plus explicit changes, without rereading environment defaults. Existing environment variable names remain supported. The current console form shows explicit values; loading a preset edits those values before submission.

Immediate settings affect the active controller at its next heartbeat/control poll. Next-invocation and next-cycle values stay pending until their boundary. Model/backend and publication identity require a new run. Server port/browser-opening changes are saved for the next server launch. Per-spec overrides only accept cycle-scoped keys. No setting disables canonical policy, evidence retention, required verification or model isolation. The [generated reference](settings.md) and [JSON Schema](settings.schema.json) list every field, units, scope, defaults and timing.

```powershell
# Repeat two specs until three completed loops or twenty active minutes.
uv run --extra research eureka run --project workspaces/my-study --backend claude --model haiku --task first.md --task second.md --max-loops 3 --max-minutes 20 --failure-policy skip
# Repeat indefinitely, retaining explicit operational limits if present in defaults.
uv run --extra research eureka run --project workspaces/my-study --backend codex --model gpt-6-luna --task first.md --mode continuous --set max_loops=null
# Clear permitted total limits explicitly; counters remain consumed.
uv run --extra research eureka resume --project workspaces/my-study --set max_calls=null --set max_minutes=null
# Load a versioned export, preset, and typed override.
uv run --extra research eureka run --project workspaces/my-study --backend claude --task first.md --config settings.json --preset "Local research" --set repair_retries=1
```

## API and verification

Interactive API documentation is at `/docs`. `/api/meta` serves settings metadata and the local mutation token. `/api/runs` creates/lists runs; run routes expose snapshots, events, SSE streams, messages, actions, specs, settings and artifacts. Presets and project defaults have separate endpoints. Use a stable `request_id` when retrying a message/action/create request. Settings PATCH requires the current revision; stale edits conflict. Spec edits include their recorded revisions. SSE supports durable IDs and `Last-Event-ID`; events accept `after`, `before` and `limit`. Raw log endpoints are local/private and are never part of the public results site.

Run `uv run --extra ui --extra research --extra cuda pytest -q`. For a browser-only offline fixture, run `uv run --extra ui --extra research --extra cuda python tests/console_fixture.py --project tmp/console --serve` and open its loopback address. This test entry point substitutes fake CLI/publication behavior; production has no fake-backend flag. [Acceptance evidence](../reports/console-acceptance.md) separates fake transport tests, observed browser controls and the Haiku/Luna live smoke. Regenerate settings and acceptance documents with `uv run python scripts/console_reference.py`.

`uv run --extra ui --extra research --extra cuda python scripts/summarize_validation.py` regenerates the existing scientific tables, figures and paper together with the settings and console acceptance reference. It reads saved records and does not invoke provider models. The [validation notes](../reports/console-learnings.md) retain implementation failures, corrections and live-transport limitations.
