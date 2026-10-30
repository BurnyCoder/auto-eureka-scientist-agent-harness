# Console acceptance evidence

Generated from saved offline test and live smoke records. These are engineering checks, not estimates of scientific competence. Fake CLIs create explicit fixture artifacts; they do not train or invoke provider models.

| Suite | Tests | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| pytest | 84 | 0 | 0 | 0 |

The saved JUnit file includes individual cases and execution times.


Live checks follow [the prospective console addendum](console-validation-preregistration.md). No earlier Sonnet or Sol result is relabeled as validation of this interface. Prior scientific findings remain unchanged.

Known limits: telemetry depends on host access and provider reporting; process CPU samples need more than one observation. A hard crash can lose up to one configured heartbeat interval of active-time accounting. External publication services can fail and need recovery. The console is a local operator interface, not an authentication boundary for a hostile local user.
