# Overnight verification

Run 2026-09-15 00:00 UTC · 0.3 minutes · **FAILED**

A fresh clone, installed from the lockfile, driven through the HTTP API the interface calls. This checks the endpoints behind every button on real papers with a real model; it does not click the interface itself.

| | Step | Detail |
|---|---|---|
| ✓ | clone | 35 tracked files from GitHub, at 55e2564 Fix typo in illustration of the pipeline |
| ✓ | clone is clean | no .env, no config, no data |
| ✓ | uv sync --frozen | 1s |
| ✓ | unit tests in the clone | OK |
| ✓ | server starts | port 8399 |
| ✓ | starts empty | no model, no schema, no prompts, no papers |
| ✓ | blockers are named | 3 things to do, each with a route |
| ✓ | unconfigured run is refused | 400 before any call is made |
| ✓ | configured | 9 fields, both prompts, one model |
| ✓ | keys never leave the server | the key is not present in /api/models |
| ✓ | readiness clears | extract and judge both unblocked |
| ✗ | run aborted | HTTPError: HTTP Error 403: Forbidden |

## Failures

- **run aborted** — HTTPError: HTTP Error 403: Forbidden
