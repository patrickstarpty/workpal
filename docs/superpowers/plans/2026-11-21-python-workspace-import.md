# Python Workspace Import Implementation Plan

> **For agentic workers:** Use subagent-driven-development or executing-plans task by task. The user authorized the Python migration directly.

**Goal:** Restore the existing TAP data in the Python-backed application.

**Architecture:** Import canonical identities and workspace membership into native tables. Store the remaining existing content in a workspace-scoped JSON table, retaining original bodies and an import manifest. Python HTTP handlers use the same native authentication and workspace membership boundary.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, SQLite, React, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-21-python-workspace-import-design.md`

## Constraints and review focus

- Never reset the source, target, existing sessions or unrelated workspace edits.
- Map structured identity references; preserve text and original JSON.
- Reruns must not overwrite edits or resurrect deleted content.
- Every content query must resolve a workspace slug and verify membership.
- Unknown backend operations must fail explicitly; preserve existing response shapes and encoded IDs.

## Tasks

- [x] Add migration 0014, `workspace_content.models.records`, import manifests, and the explicit legacy import CLI. Test count parity, deterministic mapping, owner access, transaction rollback, conflicts and idempotency.
- [x] Add content repository and routes for the existing local operations. Test CRUD, literal input, scoped access, issue table responses, details and unsupported operations.
- [x] Add analytics/contribution routes backed only by imported data. Test filters, date boundaries, write validation and workspace isolation.
- [x] Mount the routes after native identity/workspace endpoints, with analytics ahead of the content fallback.
- [x] Run the complete Python suite and `npm run check`; run browser acceptance for import, default login, capabilities, TAP project/task/comment views, reload and logout.
- [x] Stop the owned live Python launcher, back up source and target through SQLite, migrate and dry-run, import atomically, verify counts/references/source checksum, and restart the same Python service with the existing auth secret.
- [x] Verify the live entry path and document the backup paths and remaining local execution limitations.

## Baseline

Python suite before import changes: 573 passed, 30 subtests passed. Source read-only fingerprint: 1,225 records, SHA-256 `f47c838c6c1365e7fc5f2a61563b811e0f87e22818a651626a3d543190913146` over ordered `(kind,id,body)` JSON. Source includes TAP (`review`) and the historical Patrick account. The target initially contains the default development account and no workspaces.

## Delivery evidence

The backend directory was concurrently relocated from `server/python/` to `server/`; implementation and test paths follow that existing repository change. The database remains `server/data/python/workpal.sqlite`.

- Final Python suite: 643 passed, 30 subtests passed; `/tmp/workpal-python-import-final-suite.log`.
- `npm run check`: passed; `/tmp/workpal-python-import-check.log`.
- Isolated browser import and live browser acceptance both passed; `/tmp/workpal-python-import-browser.log` and `/tmp/workpal-python-import-live-browser.log`.
- Existing Playwright suite: 7 passed; `/tmp/workpal-python-import-existing-browser.log`. Existing optional APIs remain explicitly unsupported; the checks do not claim full upstream backend coverage.
- Source and target backups: `server/data/python/backups/pre-tap-import-20261121-191250/{legacy,python}.sqlite`.
- Retained original bodies match all 1,225 source `(kind,id,body)` rows exactly. Original source fingerprint is unchanged. Target SQLite integrity and foreign-key checks pass; schema is 0014. Repeated import is a no-op.
- Imported counts: 2 projects, 282 issues, 45 comments, 4 agents, 30 skills, 3 squads, 4 runtimes, 3 sessions, 849 stored analytics rows, 1 contribution record, 1 historical user and 1 workspace. Existing development identity and signing secret were preserved; development account is now an owner of TAP (`review`).
- Current service is Python on 4175 with Vite on 4174. Health confirms database/migrations/Redis readiness. No migration back to the Node service occurred.

The scoped review found no blockers for this source. Fixed the missing `created_by_id` actor mapping with a regression test. Deferred an optional legacy preference query-order fallback because this snapshot has no preferences. Embedded chat messages are stored but their previously unsupported read/execution endpoints were not expanded. No real model execution or production integration was added; existing analytics reflects imported local data.
