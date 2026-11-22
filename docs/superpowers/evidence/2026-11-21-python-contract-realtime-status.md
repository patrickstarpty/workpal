# Remaining contracts and realtime acceptance — 2026-11-21

Scope: remaining read contracts, ordinary comment/identifier regression, reconnect and subscription denial. No model calls, real database writes, external process stops, Node deletion, commits, rollback SHA, push, PR, worktree or child agents. Existing backups and archived outputs retained.

| Path | Active client / old Node | Supported local result |
| --- | --- | --- |
| `/api/inbox/unread-summary` | client validates array; Node returned `{}` | 200 `[]`: no local inbox delivery/unread subsystem |
| `/api/inbox/snoozed` | client validates array; Node had no matching handler | 200 `[]`: no supported local snooze writes |
| `/api/properties` | propertyListOptions selects `properties`; Node had no matching handler | 200 `{properties:[]}`: no local property definitions/import kind; mutations remain 501 |
| `/api/working-agents` | client expects running-task projection; Node had no matching handler | explicit 501: execution projection unavailable |
| `/api/agent-activity-30d` | client expects measured daily buckets; Node had no matching handler | explicit 501: no measured execution history |
| `/api/search-index/manifest` | client requires versioned sync manifest; Node had no matching handler | explicit 501: local sync protocol unavailable; existing sync catches failure and falls back |

All six routes authenticate and enforce workspace membership before returning data/errors. Unknown routes retain 404. This is a bounded contract correction, not an implementation of inbox delivery, custom property mutations, execution metrics or search sync. Existing persistent issue/project/comment reads remain unchanged. Client query error states and search sync failure handling are retained; browser continued through workspace mutation, reconnect and logout despite explicit 501 responses.

Fresh tests:
- Red: `server/.venv/bin/python -m pytest server/tests/test_workspace_content.py -q`, exit 1: 1 failed / 20 passed, unread-summary shape mismatch. `/tmp/workpal-contract-red.log`.
- Focused contracts + realtime + stream consumer: 39 passed, exit 0 (6.88s). `/tmp/workpal-contract-focused.log`.
- Final updated contracts/protocol: `server/.venv/bin/python -m pytest server/tests/test_workspace_content.py server/tests/test_realtime.py -q`, exit 0, 34 passed (6.05s). `/tmp/workpal-contract-final-focused.log`. Covers restart persistence of ordinary comments, literal text, unsupported fields/attachments/replies 501, CSRF 403, nonmember 404, identifier lookup restricted to workspace. Protocol verifies nonmember workspace handshake denial and foreign-room subscribe_error without data delivery.
- `REDIS_URL=redis://127.0.0.1:26379 npx playwright test --config playwright.python.config.ts tests/python-web/realtime.spec.ts`, exit 0, 1 passed (19.7s). `/tmp/workpal-contract-browser.log`. Instrumented actual built-in WebSocket, explicitly closed it, observed a replacement connection and exact second committed workspace event, then logout closure. Temporary SQLite/uploads and random Redis namespace through existing launcher; no shared Redis flush. Unrelated layout/theme/import/persistence browser suites not rerun.

Final aggregate check recorded below. Earlier 39-test run preceded the added nonmember handshake case; the final 34-test run includes it. One existing Starlette/httpx deprecation warning, no skips in focused runs.

Final `npm run check` (one invocation): **exit 0**. Node comparison 9 passed; Python **670 passed + 30 subtests**, 1 existing warning, 67.56s; launcher 16 passed; frontend build passed (5.46s), existing CSS highlight/minification and chunk-size warnings. `/tmp/workpal-contract-check.log`. Large Unicode context publication passed in this aggregate; previous intermittent failure was not reproduced, and no speculative timeout change or retry was introduced. The final membership assertion additions were independently covered by the final focused run. `git diff --check`: exit 0.

This scoped acceptance is complete. Full Task 4 still includes broader inventory/CRUD and parent-owned rollback gates; final freeze/deletion remains unauthorized. Existing import and persistence evidence is referenced rather than rerun.
