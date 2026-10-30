# Console acceptance evidence

Generated from saved offline test and live smoke records. These are engineering checks, not estimates of scientific competence. Fake CLIs create explicit fixture artifacts; they do not train or invoke provider models.

| Suite | Tests | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| pytest | 90 | 0 | 0 | 0 |

The saved JUnit file includes individual cases and execution times.

| Check | Recorded outcome |
|---|---|
| Finite queue completion | complete; 2 completed loops, 2 started cycles, 17 charged calls |
| Ask while paused, then phase step/resume | Question states: answered; UI retained accepted phases and charged the question |
| Indefinite loops with active-time bound | max_loops=None; max_minutes=0.01; budget_exhausted; 0 completed loops |
| Settings and presets | Search, changed-only view, configuration diff, theme, preset duplication and project defaults exercised; refreshed new-run form displayed saved max_loops=2 |
| Future queue and snapshots | Duplicated and edited future spec; active revision remained frozen; next loop selected the edited queued spec |
| Reload and server reconnection | Browser reconnected and retained completed phases, counters, chat and selected run |
| Artifact inspection | Read-only final.md preview rendered saved fixture text |
| Responsive interface | Desktop panels and narrow-screen queue controls inspected; saved screenshot docs/images/console.png |

| Live model | Status | Calls | Phase before / after | Reported identity |
|---|---|---:|---|---|
| haiku | answered | 1 | 0 / 0 | claude-haiku-5-5 |
| gpt-6-luna | answered | 1 | 0 / 0 | Not exposed |

gpt-6-luna: Optional MCP connector startup returned HTTP 403; the requested Q&A still completed.

[Implementation issues, corrections and limitations](console-learnings.md) describe the observed failures without replacing earlier observations.


Live checks follow [the prospective console addendum](console-validation-preregistration.md). No earlier Sonnet or Sol result is relabeled as validation of this interface. Prior scientific findings remain unchanged.

Known limits: telemetry depends on host access and provider reporting; process CPU samples need more than one observation. A hard crash can lose up to one configured heartbeat interval of active-time accounting. External publication services can fail and need recovery. The console is a local operator interface, not an authentication boundary for a hostile local user.
