> **2026-11-22：历史文档，暂停执行。** 用户要求重新按 Go 源码一比一复刻并先审核文档。以 [新设计](../specs/2026-11-22-go-parity-design.md) 和 [新实施计划](../plans/2026-11-22-go-parity-plan.md) 为待审核版本。下文原批准/进度不授权继续实施或删除 Node。

# Python Go Backend Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace this branch's default mock runtime with a verified Python implementation of the in-scope Go backend and current frontend contracts.

**Architecture:** FastAPI serves authenticated APIs with SQLite persistence and Docker Redis coordination. An independent worker dispatches durable events and background jobs; local upload bytes have a durable intent ledger. The frontend uses real sessions and workspace resolution, and default commands switch only after integration gates pass.

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, redis-py, pytest/httpx; React/Vite and Playwright. Resolve and lock compatible package versions in Task 2, recording the supported Python version.

**Spec:** `docs/superpowers/specs/2026-11-21-python-go-backend.md` (approved, including review corrections and default-command acceptance).

## Global Constraints

- Develop on feat/python-fastapi-backend.
- Actual model execution and production integrations remain out of scope under AGENTS.md.
- Treat skill input as data and do not execute installation commands.
- Keep the existing frontend contract and English product UI.
- Do not silently fall back to mock on errors.
- Preserve original branch history, mock source files and its database, but change the active web entry and npm dev/start to Python.
- Credentials: `dev@workpal.local` / `888888`; explicit development switch, loopback binding, production-mode rejection, normal signed sessions and permission checks.
- Preserve all pre-existing uncommitted work. Record a baseline before edits; stage explicit owned paths/hunks only. Never use blanket staging or reset unrelated changes.
- Do not alter Go sources, existing SQLite records or archived review notes. Tests use disposable databases/upload directories and unique Redis namespaces; never flush shared Redis.
- Completing scaffolding or returning unsupported for every route does not complete the migration.

## Review Focus

1. Default entrypoints differ from a dedicated launcher: both actual npm commands must pass browser and shutdown tests (Task 9).
2. Authentication expires or workspace access changes while a page/socket is open: clear private state and enforce authorization again (Tasks 3, 4, 7).
3. A crash occurs between storing bytes and committing metadata: recover through the intent ledger without deleting live uploads (Task 6).
4. SQLite lock contention and repeated dispatch produce duplicate mutations: bounded errors, transactional claims and idempotent effects (Tasks 2, 7).
5. Current frontend extensions are absent from Go: combined inventory and Contribution persistence are mandatory (Tasks 1, 5, 8).

## Execution structure

User-selected execution: implement sequentially in the current session. Do not dispatch implementation or review subagents.

Tasks 1–4 establish contracts and a working authenticated vertical slice. Tasks 5–8 migrate independently verifiable feature groups. Task 9 is the default-command cutover and release gate. Task 1 must expand the broad business groups into endpoint-sized work items in a companion checklist before their implementation; this plan does not pretend the large Go route surface has already been exhaustively inventoried.

Use repository-root-relative paths below. `PY` denotes the actual executable `server/.venv/bin/python`, not a global interpreter. Commands containing `PY` below mean substitute that executable. Each implementation task follows write test → observe failure → implement → rerun → review diff → narrowly scoped commit. Do not commit pre-existing user edits along with migration changes.

### Task 1: Combined contract inventory and protected baseline

**Files:** Create `server/contracts/routes.json`, `server/contracts/frontend-calls.json`, `server/contracts/schema-map.md`, `server/tools/check_contracts.py`, `server/tests/test_contract_inventory.py`, and `docs/superpowers/plans/2026-11-21-python-route-batches.md`.

**Interfaces:** `check_contracts(routes_path: Path, callers_path: Path, *, require_complete: bool) -> list[str]`. Each route records full method/path, origin, source locations, callers, auth/scope, request/response/error fixtures, persistence dependencies, batch, status, test references and exclusions. Each mutating operation also records event disposition (required or explicitly none with source-backed reason), producer service/function, event type and payload, scope, transaction boundary, consumer and commit/rollback/recovery test references. Include non-HTTP producers such as scheduled jobs; the completeness checker rejects missing event dispositions or missing evidence for required events. Frontend calls link to a route or an explicit retirement/capability decision.

- [ ] Record branch/HEAD, changed paths and content hashes of existing tracked modifications; record protected mock/Go source hashes. Record `npm run check` baseline output without editing failures unrelated to migration. Do not checkpoint raw database contents in git.
- [ ] Write `test_unmapped_frontend_call_fails`, `test_duplicate_method_path_fails`, `test_incomplete_route_fails_release_gate`: respectively assert a diagnostic for an unmapped call, duplicate route and pending route in completion mode. Run with available Python test tooling; observe failure before implementing the checker.
- [ ] Read composed Go registrations, middleware, handlers, SQL and relevant tests; cross-check current frontend API clients and mock extensions. Record Go-only, shared, local-extension and retired-bootstrap routes. Resolve dynamic paths and conditional registrations manually where static scanning is insufficient.
- [ ] Fill schema map with required fields, relations, uniqueness, deletion policy and PostgreSQL-specific translations for every migration batch. Record real contracts rather than guessing field names or errors.
- [ ] Implement the checker and generate the companion route-batch checklist: exact source/destination files, fixtures, signatures and test commands for each coherent feature group. Explicitly include all remaining in-scope routes, not just the first visible pages. The checklist is a prerequisite for Task 5/8, not permission to reduce scope.
- [ ] Run inventory tests; require zero unmapped frontend calls and explicit decisions for every registration. Review and commit only Task 1 artifacts.

### Task 2: Runnable Python foundation and isolated persistence

**Files:** Create `server/pyproject.toml`, lockfile, `README.md`, `src/workpal_backend/{app,config,cli}.py`, `src/workpal_backend/infrastructure/{database,redis}.py`, `alembic.ini`, `migrations/env.py`, first versioned migration, `tests/{conftest,test_config,test_database,test_health}.py`.

**Interfaces:** `create_app(settings: Settings) -> FastAPI`; `Database.transaction()` yields a SQLAlchemy session with commit/rollback; `RedisResources` owns client lifecycle and namespaced keys. CLI commands `python -m workpal_backend.cli migrate`, `serve`, and later `worker` share settings.

- [ ] Establish isolated venv and locked dependencies. Write tests for rejecting mock DB aliases/symlinks, invalid development binding/production flag, FK enforcement, rollback, reopen persistence, lock timeout and readiness with unavailable Redis.
- [ ] Run `PY -m pytest server/tests/test_config.py server/tests/test_database.py server/tests/test_health.py`; observe missing implementation failures.
- [ ] Implement settings, application lifecycle, explicit migrations, database and Redis resources. Resolve paths from repo root, enforce local WAL/FKs and bounded waits; no automatic migration of arbitrary existing files. Add liveness/readiness endpoints using inventoried Go contracts.
- [ ] Inspect Docker Redis endpoint without exposing credentials; use a unique test prefix. Verify Redis failure with an unreachable test endpoint, never by stopping someone else's container.
- [ ] Rerun tests and CLI migration twice against a fresh disposable DB; require no schema duplication, no leaked connections and truthful readiness. Document setup and narrowly commit.

### Task 3: Real identity, workspace access and development login

**Files:** Create `src/workpal_backend/auth/{routes,schemas,service,tokens}.py`, `workspaces/{routes,schemas,service,repository}.py`, corresponding migrations, `tests/{test_auth,test_workspace_permissions}.py` under `server/`.

**Interfaces:** Authentication dependencies yield `Principal` with identity kind and user/actor ID; `require_workspace_access(session, principal, workspace_id)` resolves stored membership. HTTP request/response fixtures come from Task 1, including config, identity lookup, send-code, verify-code, logout and workspace operations.

- [ ] Write tests accepting only normalized `dev@workpal.local` plus `888888`, reusing the same persisted user on repeated login, rejecting other credentials, rejecting disabled/production development auth, and preventing PAT/task identity exchange into an interactive session. Add cookie, JWT expiry/renewal and CSRF assertions from Go tests.
- [ ] Write workspace tests for zero/one/multiple memberships, owner creation atomicity, removal and cross-workspace/private-resource denial. Run both files to observe failures.
- [ ] Implement schema and auth/workspace services, normal signed sessions and explicit development capability. No global owner bypass or mock identity. Keep external email/Google execution explicitly unsupported.
- [ ] Rerun tests, including database reopen and membership invalidation. Verify errors match inventoried contracts; commit only task files.

### Task 4: Frontend authentication and workspace vertical slice

**Files:** Modify `apps/web/app/main.tsx`, `apps/web/app/routes.tsx`, `apps/web/vite.config.mjs`; create `apps/web/app/python-session.tsx`, `apps/web/app/verification-login.tsx`, `apps/web/app/python-session.test.tsx`, `apps/web/app/routes.test.tsx`, `scripts/python-web-dev.mjs`, `tests/python-web/auth.spec.ts`, `playwright.python.config.ts`. Reuse existing core auth initializer/provider and workspace APIs rather than introducing a second session store.

**Interfaces:** Python session boundary renders resolving, unauthenticated, workspace-selection/creation, authenticated or retryable-error states. Dedicated pre-cutover launcher starts Python plus Vite with disposable-state overrides; config proxies `/api`, `/auth`, `/ws` and inventoried content routes, including WS upgrades.

- [ ] Write tests proving no `/api/bootstrap`, no locally fabricated authentication, no auto-submit, editable capability-gated prefill, 401-to-login, transport-failure-to-retry, persisted session refresh, and inaccessible remembered-workspace rejection. Add route tests for a non-review slug, deep-link refresh, workspace switching, malformed URL encoding and a slug outside the authenticated membership set.
- [ ] Run component tests and browser auth spec against the incomplete slice; confirm failures describe missing behavior.
- [ ] Replace startup bootstrap/Seed and hardcoded workspace slug with real session/workspace resolution. Implement login submission, workspace creation/selection, deep-link gating and logout cleanup. Change LocalPage to accept the resolved authorized workspace slug and match the first URL segment against it, removing the review-only guard. Generate MissingPage recovery links from the resolved slug. Resolve deep-link workspace membership before rendering, and update route, platform workspace context, query state and subscriptions together when switching; never reinterpret an old workspace resource ID under a new workspace. Preserve visual system and keyboard access.
- [ ] Add dedicated launcher and proxy routes. Do not change default npm commands yet. Start WS only when authentication is resolved; complete protocol verification in Task 7.
- [ ] Run component tests and `pnpm exec playwright test --config playwright.python.config.ts tests/python-web/auth.spec.ts`. Verify refresh, invalid credentials, missing capability and zero/multiple workspaces. Commit owned edits without absorbing existing main.tsx changes.

### Task 5: Core resources and current frontend extensions

**Files:** Create feature-owned `{routes,schemas,service,repository}.py` for `projects`, `issues`, `comments`, `agents`, `chats`, `contribution`, with migrations and `tests/test_<feature>_contracts.py`; exact ancillary feature files come from the Task 1 route-batch checklist. Update contract statuses only with evidence.

**Interfaces:** Routes consume Task 3 principals/access guards and Task 2 transactions. Serialization follows recorded HTTP fixtures; never return raw ORM objects. Contribution exposes GET/PUT `/api/dashboard/contribution` with existing response shapes and explicit workspace scope.

- [ ] For each batch, write contract cases for successful CRUD, bad inputs, nulls, pagination, relationship constraints, unauthorized/private access and reopen persistence. Run its test file and observe failures.
- [ ] Implement the batch and SQL translations from schema-map; enforce permissions inside services. Cover all corresponding schema dependencies, not just fields visible in a single page.
- [ ] For Contribution, test atomic replacement, repeat import, malformed import rollback, owner/admin requirement, private-project filtering, `days`/`tz`/`project_id` behavior and cross-workspace isolation. Empty data returns truthful empty aggregates.
- [ ] Rerun each batch's tests, add evidence to inventory and commit each independently reviewable batch. No fixture-derived agent outputs or fabricated metrics.

### Task 6: Durable attachment bytes and authorized downloads

**Files:** Create `files/{routes,schemas,service,repository,storage,reconcile}.py`, upload-ledger migration, `tests/test_files.py`, `tests/test_upload_recovery.py`, `tests/python-web/files.spec.ts`.

**Interfaces:** `LocalBlobStore` operates on server-generated opaque keys under `WORKPAL_UPLOAD_DIR`; upload service maintains pending/ready/deleting states and leases. Downloads resolve permissions before byte access. Reconciler claims expired intents transactionally and performs idempotent cleanup.

- [ ] Write upload/download digest and restart tests plus invalid size, traversal/symlink, anonymous/cross-workspace/private access, range authorization and expired capability tests.
- [ ] Write crash-boundary cases before/after rename, failed DB finalization, active-upload lease protection, disk failure and failed-delete retry; run both files and observe failures.
- [ ] Implement the approved staged-write/fsync/rename/finalize protocol without a write transaction across file I/O. Persist cleanup work and handle orphaned bytes through the ledger. Never serve staging/internal files or mount the uploads directory publicly.
- [ ] Run Python file tests and browser file spec, restarting the API between upload and digest-verified download. At this stage invoke the reconciler directly in recovery tests; worker registration and actual scheduled recovery are verified in Task 7, after the worker exists. Add backup/restore guidance covering both database and upload bytes. Commit task files.

### Task 7: Realtime and background-worker consistency

**Files:** Create `infrastructure/outbox.py`, `realtime/{routes,protocol,subscriptions}.py`, `worker.py`, job/outbox migrations, `tests/{test_realtime,test_worker,test_event_producers,test_upload_worker_recovery}.py`, `tests/python-web/realtime.spec.ts`.

**Additional modified files:** Task 3 auth/workspace services and Task 5 feature services identified as event producers in the Task 1 inventory; Task 6 files/service.py and files/reconcile.py. Enumerate their exact paths in the companion route-batch checklist before edits.

**Interfaces:** `append_event(session, event)` appends a stable-ID outbox row using the caller's existing transaction and never commits independently. Business transactions append stable-ID outbox events; worker claims durable jobs and dispatches to Redis using the inventoried Go protocol. `python -m workpal_backend.cli worker` owns scheduling; API processes do not each start a scheduler.

- [ ] Write tests for committed mutation + Redis outage, duplicate delivery, worker restart, expired claims, stale-worker fencing and SQLite contention. Assert committed writes are not reported as rolled back just because publication fails.
- [ ] Write WebSocket tests for handshake authentication, unauthorized scope, membership removal, logout/expiry and reconnect contract. Run tests to observe failures.
- [ ] Backfill every required event producer from Tasks 3/5/6 using append_event inside the same business transaction. For each inventory operation, parameterize tests asserting successful commit saves both mutation and correctly scoped event; injected rollback leaves neither; Redis publication failure retains pending delivery and recovery publishes the same stable event ID. Include repeat-delivery consumer idempotency. Record the test references per operation; a single representative WebSocket event is insufficient.
- [ ] Register files.reconcile as the upload-reconciliation job in the worker job registry. Persist its schedule/claim in SQLite, poll due work with a bounded interval, reclaim only expired intents, and retry failed cleanup. Add an integration test that leaves a pending upload, restarts API and worker, and observes cleanup from actual scheduling without directly calling the reconciler; assert ready and live leased uploads survive. Keep this out of API startup to prevent duplicate schedulers.
- [ ] Implement durable claims, idempotency, event dispatch, subscription authorization and bounded shutdown. Implement only permitted scheduling; external execution fails explicitly.
- [ ] Run Python tests with isolated Redis namespace and browser realtime spec; verify an actual authorized mutation event, not merely an HTTP upgrade. Clean only test-owned state and commit.

### Task 8: Remaining routes and whole-application completion

**Files:** Feature files and test paths enumerated by Task 1 companion checklist, including search/inbox/settings/remaining supported automation and file routes; update contracts and `server/README.md`.

**Interfaces:** Same principal/transaction/serialization interfaces; unsupported capabilities have explicit UI states and backend errors after appropriate auth.

- [ ] Work through every remaining route batch using failing contract tests, implementation, passing tests and a narrowly scoped commit per batch. Cover search semantics, private-resource filtering and every reachable current frontend call.
- [ ] Verify each exclusion follows approved scope; missing implementation is pending, not an exclusion. Ensure current pages do not endlessly retry a generic 404 for deliberately unavailable features.
- [ ] Run `PY server/tools/check_contracts.py --require-complete`, complete Python suite and full Playwright suite via dedicated launcher. The completion checker must also require event dispositions for all mutating operations/jobs and commit, rollback and recovery evidence for each required producer. Require no unmapped calls, pending in-scope routes or missing test evidence.
- [ ] Review protected-source hashes and confirm no mock/Go/data modifications; record all compatibility limitations honestly. The dedicated launcher passing is only permission to attempt Task 9, not final acceptance.

### Task 9: Default command cutover and actual-entrypoint acceptance

**Files:** Create `server/start-python.mjs`, `server/src/workpal_backend/static.py`, `scripts/python-entrypoints-qa.mjs`, `tests/python-web/entrypoints.spec.ts`; modify root `package.json`, Vite configuration as needed and Python README. Keep `server/start.mjs`, mock API/store and Go sources intact.

**Interfaces:** Root `dev` and `dev:web` run the Python supervisor with `--dev`; root `start` runs it without that flag. Development starts Python API at 4175, Vite at 4174 and preserves the current docs launch behavior. Built-app startup serves `apps/web/dist` from Python at 4174 with same-origin auth/API/content/WS. Static fallback must never swallow `/api`, `/auth`, `/ws` or content errors. The supervisor starts one worker, propagates failures, forwards signals and reaps all children. `npm start` means serving the built app; it does not implicitly enable development authentication or override an explicitly configured production environment.

- [ ] Write supervisor tests for missing Python, occupied port, failed child startup, unexpected API/worker exit and SIGINT/SIGTERM. Assert a nonzero failure exit where applicable, sibling cleanup, no mock process and no remaining listeners. Run and observe failures.
- [ ] Implement built static serving and supervisor; add explicit Python test/check commands to package scripts while preserving existing verification. Switch root defaults only now. No import of mock createServer and no automatic fallback. Startup errors are actionable and redact secrets.
- [ ] Build with `npm run build`, then run `npm run check` and the Python checks. Separate pre-existing failures using the baseline; never waive a migration regression.
- [ ] Execute `node scripts/python-entrypoints-qa.mjs`. This harness MUST spawn the actual root `npm run dev` and, in a separate run, actual root `npm start`, with `reuseExistingServer: false`; it must not substitute the dedicated launcher or call uvicorn directly. Use disposable SQLite/upload paths, unique Redis prefixes and explicit development-auth settings for this local acceptance run.
- [ ] For EACH actual command, confirm process ownership/readiness, prefilled manual login, rejected wrong code, authenticated refresh, workspace initialization, upload real bytes, authenticated digest-checked download and rejected unauthorized download. Receive an actual scoped WebSocket mutation event, reject unauthorized subscription and test logout disconnect.
- [ ] For EACH command, stop and restart using the same test database/upload directory, log in or recover the valid session, and verify the prior attachment bytes remain downloadable. Re-establish and verify WebSocket delivery after restart.
- [ ] For EACH command, exercise SIGINT and SIGTERM in separate runs; require clean shutdown within the documented bound, no live API/worker/Vite/docs child, closed WS and released 4174/4175/4000 ports where that run owned them. Confirm a new run can immediately bind again. Verify unavailable Redis/startup failure produces an explicit error and never launches mock; use bad test configuration, not interruption of the shared service.
- [ ] Separately verify production-mode rejection with development auth enabled. In production mode without the flag, verify prefill is absent and built static/auth routes behave without an auth bypass; local fixture login does not establish production identity-provider support.
- [ ] Capture command, environment profile (no secrets), exit status, process cleanup, browser trace and assertions for both runs in `docs/verification/python-backend-entrypoints.md`. Recheck protected files, inventory completeness and owned diff. Commit the cutover only after these actual-entrypoint checks pass.

## Final acceptance and handoff

- [ ] No pending in-scope route, no unexplained frontend call and no fabricated integration/model output.
- [ ] Python persistence, Redis, file recovery, permissions and browser checks pass.
- [ ] Actual root `npm run dev` AND `npm start` pass login, restart/download, realtime and process-exit checks after default command changes.
- [ ] Existing records, Go/mock sources and original branch history are preserved; runtime faults never fall back to mock.
- [ ] README includes install/migrate/start/worker configuration, Docker endpoint guidance, local credentials and limits, backup/restore and verification commands.

## Plan self-review

Spec coverage maps to Tasks 1–9: dual contract sources (1/5/8), SQLite/Redis (2/7), authentication and frontend bootstrap (3/4), files (6), default runtime and final command validation (9). All five review-focus failures have explicit tests. Endpoint-specific batches intentionally require the completed inventory before implementation; a generic module checklist alone is not an executable replacement for those batches. No service implementation or verification result is claimed by this plan.

## Plan review corrections

- Task 4 now owns routes.tsx, dynamic authorized slugs, generated recovery links and deep-link/workspace-switch tests.
- Task 6 verifies API restart and direct reconciler behavior; Task 7 owns actual worker registration, scheduling and API/worker restart recovery.
- Task 1 records producer-level event contracts; Task 7 explicitly modifies earlier business services and tests commit/rollback/recovery per producer; Task 8 enforces complete evidence.
- Task 9 actual npm dev/start acceptance remains mandatory and unchanged.
