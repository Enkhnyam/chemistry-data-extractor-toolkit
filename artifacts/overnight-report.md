# Overnight verification

Run 2026-09-13 22:00 UTC · 1.8 minutes · **passed**

A fresh clone, installed from the lockfile, driven through the HTTP API the interface calls. This checks the endpoints behind every button on real papers with a real model; it does not click the interface itself.

| | Step | Detail |
|---|---|---|
| ✓ | clone | 34 tracked files from GitHub, at 3ce400d Ready the repository for people who did not write  |
| ✓ | clone is clean | no .env, no config, no data |
| ✓ | uv sync --frozen | 0s |
| ✓ | unit tests in the clone | OK |
| ✓ | server starts | port 8399 |
| ✓ | starts empty | no model, no schema, no prompts, no papers |
| ✓ | blockers are named | 3 things to do, each with a route |
| ✓ | unconfigured run is refused | 400 before any call is made |
| ✓ | configured | 9 fields, both prompts, one model |
| ✓ | keys never leave the server | the key is not present in /api/models |
| ✓ | readiness clears | extract and judge both unblocked |
| ✓ | fetched papers | 2 open-access PDFs from Europe PMC |
| ✓ | parse indole_dearomatization.pdf | 50 chunks in 34s |
| ✓ | parse nitroalkane_coupling.pdf | 86 chunks in 28s |
| ✓ | chunks render as HTML | markdown tables survive into the review pane |
| ✓ | a corrupt PDF fails alone | ConversionError: Conversion failed for: not-a-7ceea113.pdf with status: failure. Errors: d |
| ✓ | extract indole-dearomatization-7 | 17 records, 17.5s, 11,299 tokens |
| ✓ | extract nitroalkane-coupling-e45 | 0 records, 1.2s, 8,134 tokens |
| ✓ | judge indole-dearomatization-7 | 17 verdicts, 7.6s |
| · | judge nitroalkane-coupling-e45 | no records to judge |
| ✓ | records extracted | 17 across 2 papers |
| ✓ | a correction keeps the original | model_records still holds what the model said |
| ✓ | a stale save is refused | 409, so one tab cannot overwrite another |
| ✓ | report builds | 17 records, 9 fields, verdicts {'correct': 17} |
| ✓ | CSV exports | 17 rows |
| ✓ | static assets | page, script and stylesheet all served |
| ✓ | delete removes a paper | and everything derived from it |
