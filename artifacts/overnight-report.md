# Overnight verification

Run 2026-09-13 21:49 UTC · 2.2 minutes · **FAILED**

A fresh clone, installed from the lockfile, driven through the HTTP API the interface calls. This checks the endpoints behind every button on real papers with a real model; it does not click the interface itself.

| | Step | Detail |
|---|---|---|
| ✓ | clone | 31 tracked files |
| ✓ | clone is clean | no .env, no config, no data |
| ✓ | uv sync --frozen | 1s |
| ✓ | unit tests in the clone | OK |
| ✗ | run aborted | server never answered: 8900 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:38910 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:38924 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:35934 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:35950 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:35964 - "GET /api/status HTTP/1.1 |

## Failures

- **run aborted** — server never answered: 8900 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:38910 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:38924 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:35934 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:35950 - "GET /api/status HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:35964 - "GET /api/status HTTP/1.1
