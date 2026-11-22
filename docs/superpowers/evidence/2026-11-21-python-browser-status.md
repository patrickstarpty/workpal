# Task 4 fresh browser evidence — incomplete

2026-11-21. Node retained; no freeze, rollback SHA, commit, push or PR. Real SQLite opened read-only only to make an online SQLite backup into a temporary QA directory. No Node mock initialization is used by import QA anymore. Existing assertions and historical counts are unchanged.

Fresh commands:
- `node scripts/python-workspace-import-qa.mjs`: exit 1. Login and import ran, then expected `#/review/projects` but received `#/review/issues`. Evidence `/tmp/workpal-task4-import.log`; retained service/database artifacts `/var/folders/zn/dg1zfbv96p19qstvcpgsjvyr0000gn/T/workpal-import-browser-g6YaIf`. No assertion weakened.
- `npx playwright test --config playwright.python.config.ts`: exit 1, explicit REDIS_URL required.
- Retried with `REDIS_URL=redis://127.0.0.1:26379`; result log `/tmp/workpal-task4-playwright.log` (running at this checkpoint).
- `npm run check`: `/tmp/workpal-task4-check.log` (running at this checkpoint); Node tests 9 passed before Python tests started.

Observed real integration gaps requiring diagnosis: chat sessions and pending tasks requested without X-Workspace-Slug (400); autopilots response is array where frontend expects object; properties, working-agents, agent-activity-30d, search-index/manifest and inbox/snoozed return 404. These are observations, not a completed contract inventory or approved unsupported-feature policy.

Not yet verified: representative CRUD/detail/comment paths, restart persistence, build-mode npm start browser path, websocket subscription denial/reconnect, complete contract inventory and UI recovery. Existing browser suite contains keyboard/narrow-screen and realtime/logout coverage but its fresh aggregate result is pending. No Task 4 checkbox is marked complete based on partial evidence. Real freeze is unrelated to these outstanding isolated checks.

## Completed background results

`npm run check` exited 1: Python 665 passed, 1 failed, 30 subtests passed (101.77s). Failure: `test_authorized_delivery_and_failed_fanout[context2]`, dispatch returned 0 instead of 1 while publishing the large Unicode context. Build stage was not reached. A focused realtime rerun was started with log `/tmp/workpal-task4-realtime-recheck.log`; this does not supersede the failed full check.

Playwright completed exit 1: 2 passed / 5 failed (1.2m). Auth/session/realtime tests failed expecting the workspace chooser; capability test failed focus on `#stage-detail-title`. Traces retained under `test-results/`. These failures remain unresolved and must not be counted as browser acceptance.

## Follow-up diagnosis (2026-11-21 23:01)

The prior focused realtime rerun finished: `/tmp/workpal-task4-realtime-recheck.log`, 6 passed in 1.40s. This is not a root-cause determination or replacement for the failed aggregate check.

Compared browser error-context with current frontend: workspace navigation now exposes a `Switch workspace` button rather than the former Workspace combobox. Existing capability component test explicitly requires stage selection to retain trigger focus. Updated the stale browser stage-focus assertion accordingly; no product behavior change retained.

A focused capability run exited 1 (`/tmp/workpal-task4-focus-fix.log`), timing out waiting for `Back to skills` after reaching skill details. Its run began before the final assertion edit; it does not verify the final test file. Task 4 remains incomplete; no acceptance checkbox changed. No real database writes, freeze, Node deletion, push, or PR performed.

## Scoped regression completed — 2026-11-21 23:17

This supersedes earlier incomplete results only for the existing seven browser cases and import QA. Task 4 remains incomplete.

Fresh final commands and observed results:
- `REDIS_URL=redis://127.0.0.1:26379 npx playwright test --config playwright.python.config.ts`: exit 0, **7 passed (1.1m)**; `/tmp/workpal-task4-browser-final2.log`.
- `REDIS_URL=redis://127.0.0.1:26379 node scripts/python-workspace-import-qa.mjs`: exit 0; `/tmp/workpal-task4-import-final.log`. Preserved original source counts, projects/issues/comments/catalog/analytics assertions, reload, narrow layout and logout. Source copied through read-only SQLite backup.
- `REDIS_URL=redis://127.0.0.1:26379 server/.venv/bin/python -m pytest server/tests/test_workspace_content.py -q`: exit 0, **19 passed**; `/tmp/workpal-task4-contract-green.log`. New focused contract first failed with 400 (`/tmp/workpal-task4-contract-red.log`). Test fixture uses temporary SQLite and unavailable localhost Redis, so it does not write to shared Redis.
- `git diff --check`: exit 0.

Browser/import launchers used separate temporary SQLite/upload directories, ports 24174/24175 and 24274/24275, random Redis namespaces, and no flush. The pre-existing launcher PID 39410 (web port 4174) was left untouched. Owned launchers shut down through their existing cleanup paths. No real database mutation, external process termination, model call, installation, Node removal, worktree, commit, push or PR.

Changes: refreshed stale combobox selectors to the workspace switcher/menu with route identity checks; default workspace navigation is issues; current capability return link is AI Hub; skill detail replaces the grid; role return goes directly to Agent Team with trigger focus restored. Mobile navigation is explicitly opened, including the multi-workspace chooser branch exposed by aggregate execution. Keyboard focus, composition, narrow layouts, theme contrast, membership denial, session expiration, websocket delivery and logout assertions remain active. Per-action timeout now catches stale locators in 10 seconds.

Real integration fixes: chat requests explicitly send X-Workspace-ID with empty slug. Backend now resolves that ID with membership enforcement, while nonempty slug retains precedence; unknown IDs return 404. Autopilots list returns `{autopilots,total}` matching frontend schema. No records or outputs synthesized.

Remaining observed gaps: properties, working-agents, agent-activity-30d, search-index/manifest and inbox/snoozed return 404; inbox/unread-summary returns an object where the frontend expects an array. These do not block the scoped regressions and remain explicit follow-up contract work. Representative CRUD, restart persistence, rollback, production/build browser path, websocket denial/reconnect, broader contract inventory and final `npm run check` were not run in this scope. Parent owns final aggregate check; no Task 4 completion checkbox changed.
