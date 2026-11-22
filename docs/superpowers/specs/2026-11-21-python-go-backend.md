> **2026-11-22：历史文档，暂停执行。** 用户要求重新按 Go 源码一比一复刻并先审核文档。以 [新设计](../specs/2026-11-22-go-parity-design.md) 和 [新实施计划](../plans/2026-11-22-go-parity-plan.md) 为待审核版本。下文原批准/进度不授权继续实施或删除 Node。

# Python replacement for the original Go backend

## Scope
Replace the HTTP backend rooted at server/go/cmd/server with a separately runnable Python FastAPI service. Preserve all Go sources, Node mock source files, existing mock SQLite records and existing uncommitted work. Develop on feat/python-fastapi-backend. The Go CLI and local runtime executables are not rewritten as part of the HTTP service migration.

## Architecture
Add server with FastAPI routing, explicit request/response models, application services and SQLite repositories. Use a new Python-service database file, separate from server/data/workpal.sqlite. Preserve the existing Go HTTP contracts, authorization behavior and logical data relationships; adapt PostgreSQL-specific types, SQL and locking semantics explicitly rather than copying SQL verbatim. Keep persistence behind repository interfaces to allow a later PostgreSQL implementation. Use Redis from a Docker-hosted service for migrated functionality that requires shared ephemeral state, pub/sub or coordination. Configure its connection through REDIS_URL; do not hardcode credentials or expose them in logs. Namespace application keys and pub/sub channels, with separate test namespaces and cleanup limited to test-owned keys; never flush a shared Redis database. Required Redis operations must fail explicitly when Redis is unavailable. Start with a single application worker; design background work and event delivery for this local deployment, without claiming multi-instance coordination. Use versioned schema migrations for the new database only; verification uses disposable SQLite databases.

## Migration method
Inventory routes and dependencies before implementation. Migrate coherent feature groups, beginning with configuration, SQLite schema and database lifecycle, authentication and workspace access, then business resources, events and background scheduling. Maintain a route coverage inventory that distinguishes implemented, pending and intentionally unsupported operations. Pending operations must fail explicitly; a running skeleton does not constitute a completed replacement.

## Project constraints
Actual model execution and production integrations remain out of scope under AGENTS.md. Return explicit unsupported-operation errors and never fabricate model output. Treat skill input as data and do not execute installation commands. Keep the existing frontend contract and English product UI.

## Validation
Use disposable SQLite databases, never the existing mock SQLite store. Run Redis integration checks against the Docker service with isolated test namespaces, including unavailable-service behavior; do not modify unrelated container data. Verify foreign-key enforcement, transaction rollback, concurrent-write handling and database reopen persistence. Review PostgreSQL-specific JSON, array, search and locking behavior during each module migration. Test authentication, tenant isolation, permissions, persistence, malformed input and relevant event behavior. Compare migrated HTTP contracts against Go definitions and fixtures. Run Python checks and npm run check, reporting pre-existing failures separately. Document startup, configuration, route coverage and remaining limitations honestly.

## Detailed design — proposed for review

### Source of truth and compatibility
- Route composition: server/go/cmd/server/router.go, including middleware groups and delegated plugin route registration. Build the full method/path inventory from these registrations and cross-check it against current frontend calls and local mock extensions; neither source alone establishes frontend compatibility.
- Business behavior: server/go/internal/handler and server/go/internal/service, with existing tests as behavioral evidence.
- Authentication: server/go/internal/auth and middleware. Preserve token-kind separation, JWT verification, session renewal, cookie attributes and CSRF binding; do not simplify these into a fixed development user.
- Persistence: server/go/pkg/db/queries and server/go/migrations define logical entities and constraints, not executable SQLite migrations.
- Real-time behavior: server/go/internal/realtime and event listeners in server/go/cmd/server. Inventory payloads, authorization, ordering, retention and reconnect behavior before selecting Redis structures per event type.

Each route inventory entry records method, full path, auth requirements, request/response and error contract, dependencies, migration group, implementation state and verification evidence. Do not report full Go parity until all in-scope entries pass. Preserve 401/403/404 distinctions, pagination, nullable fields, timestamps and identifier formatting. Adapt FastAPI validation errors to the original API contract where necessary. Unknown paths remain 404; known pending operations return an explicit documented not-implemented response after applicable authentication checks.

### Module layout
Use server/pyproject.toml with a locked dependency set and a src/workpal_backend package:
- app.py and config.py: application factory, lifecycle, validated environment settings, health/readiness.
- infrastructure/: SQLite connection/transaction lifecycle, Redis client lifecycle, migrations and durable event dispatch.
- auth/: identity, token validation, CSRF and session renewal.
- workspaces/, projects/, issues/, agents/, chats/, files/, automation/: feature-owned API schemas, routes, business operations and repository implementation. Add modules as their route groups migrate; avoid empty scaffolding for every Go file.
- realtime/: authenticated subscriptions and the existing wire protocol.
- tests/: contract, integration and permission tests with isolated state.

Use FastAPI and Pydantic for HTTP boundaries, SQLAlchemy for explicit transactions and database access, Alembic for Python-owned migrations, and redis-py for Docker Redis connectivity. Pin compatible versions during implementation. Business operations own transaction boundaries; routes do not expose ORM objects directly. Repositories encapsulate SQL dialect differences without introducing a generic CRUD abstraction that hides permissions.

### SQLite storage
Default proposed path: server/data/python/workpal.sqlite; reject accidental configuration pointing at the existing mock database. Enable foreign keys on every connection, WAL on local storage and a bounded busy timeout. Keep write transactions short; never hold a write transaction across Redis, HTTP or file I/O. Translate lock contention into a documented retryable service error; retry writes only when their operation is safely idempotent.

Represent identifiers as text while preserving API formats. Specify UTC timestamp precision and serialization centrally. Store structured values as JSON only when relational constraints and query requirements permit it; use relation tables for membership and relationships. Translate PostgreSQL arrays, JSON operators, search, casts, generated values and lock-based claims individually, backed by tests. Do not assume SQLite FTS or case folding matches PostgreSQL search.

Multiple API processes on one host may share this local database, subject to SQLite's single-writer limit. Initial supported deployment is one API process and one background worker. Multi-process support requires contention and subscription tests; cross-host shared-file deployment is outside this design. Redis does not remove the SQLite write limit.

### Redis and background work
Connect to the existing Docker service using REDIS_URL. A host-run API uses the published host port; a container-run API uses the Docker network service name. Do not assume localhost refers to the Redis container. Inspect existing containers and ports before supplying a concrete local configuration; do not recreate an existing service or publish it externally.

Use REDIS_KEY_PREFIX for keys and channels, with unique prefixes for test runs. Cache entries have bounded TTLs; authorization cache invalidation must preserve permission changes. Durable business records and authoritative job claims belong in SQLite. Redis may provide notifications, short-lived coordination and compatible stream transport, but is not the sole store of business state.

For newly migrated database mutations that emit durable events, record an outbox entry in the same SQLite transaction. A separate worker dispatches committed events and retries delivery. Delivery is at least once: use stable event IDs and idempotent consumers; never promise exactly once. Map existing Go event contracts and retention requirements before implementing reconnection behavior. Existing Pub/Sub-only semantics can remain ephemeral where the Go contract allows this.

Run scheduling in the separate worker, not independently in every API process. Use transactional job claims and idempotency constraints; if Redis leases are used, release by owner token and guard stale-worker writes with database checks. Redis interruption must not silently authorize requests or report successful dispatch. A committed database mutation with pending outbox delivery remains committed; avoid returning a misleading failure that invites duplicate writes.

### Authentication and unsupported integrations
Preserve human, personal-access-token and runtime/task identity boundaries for implemented routes. Apply workspace and private-project access checks in business operations and subscription authorization, not only route middleware. Test membership removal and cross-workspace resource IDs.

The Go login entry points include email-code and Google authentication. Production email/OAuth integrations remain unsupported under the project constraints. User-approved approach: hardcode one development email and verification code. Proposed default values are dev@workpal.local and 888888. Enable this only with WORKPAL_DEV_AUTH=true in development mode on a loopback listener; production-mode startup must reject that flag. Preserve the existing /auth/send-code and /auth/verify-code request/response contracts. For the configured development email, send-code performs no email delivery; verify-code accepts only the exact fixed email/code pair after the existing email normalization rules. Reject all other identities or codes using the existing authentication error contract. Create or reuse one persisted development user through an idempotent transaction; do not insert duplicate users on repeated login. Issue normal signed sessions and enforce the existing cookie, CSRF, session-renewal and resource authorization rules. Workspace access still derives from stored membership, never a global authorization bypass. Keep Google and actual email delivery explicitly unsupported. Tests cover accepted credentials, wrong email/code, repeated login, disabled development mode and production-mode rejection. These credentials are intentionally public local-development fixtures, not production secrets.

Keep runtime/model execution and external provider operations explicitly unsupported. CRUD for configuration may be supported without claiming the underlying integration is connected or executable. Do not execute skill commands or generate fabricated task results. Decide endpoint-specific unsupported status and error shape in the contract inventory rather than returning a generic success response.

### Configuration and operations
Proposed settings: WORKPAL_DATABASE_URL, REDIS_URL, REDIS_KEY_PREFIX, AUTH_SECRET, WORKPAL_HOST and WORKPAL_PORT. Keep existing Go environment names where compatibility matters, and document any deliberate differences. No built-in signing secret. Provide explicit migration, API and worker commands in the Python README; switch npm dev/start and frontend routing to Python after the end-to-end readiness gates pass, as authorized by the user. Retain mock source files and data without a default runtime fallback.

Health distinguishes process liveness from readiness. Readiness checks schema version, SQLite access and required Redis connectivity with bounded timeouts. Graceful shutdown closes subscriptions and clients and releases owned work safely. Logs include request IDs and operation context, never tokens, passwords or database credentials.

### Migration sequence and completion gates
1. Contract inventory and SQLite schema mapping: list all route groups and exclusions, PostgreSQL-specific behavior and corresponding tests.
2. Runnable foundation: configuration, migrations, health, Redis connectivity and isolated test harness.
3. Identity and access: fixed-email/code development login, session/token checks, CSRF, workspaces, membership and private-resource permissions.
4. Core business resources: projects, issues, comments, labels, agents and chats, following dependency order from the inventory.
5. Files, search, inbox, realtime and permitted scheduling: preserve access checks, transaction/event consistency and reconnect behavior.
6. Remaining in-scope routes and full verification: audit every inventory entry, document unsupported operations, run Python tests and npm run check, and provide startup/cutover instructions then switch this development branch to Python by default.

For every feature group, require real persistence across restart, malformed-input tests, permission tests and HTTP contract tests. Exercise SQLite contention, rolled-back writes, Redis outages, repeated job delivery and subscription authorization. Use existing Go tests to derive expectations; use differential tests only for safe local operations against isolated Go dependencies. Passing a small smoke suite does not establish whole-backend equivalence.

### Deliberate limits
This design does not migrate existing PostgreSQL production records, replace the Go CLI/runtime executables, enable model calls or production integrations. Those changes need separate scope. All implementation remains pending; this document records design decisions, not measured performance or completed compatibility.


### Development login form prefill — user requirement
When the frontend is explicitly configured to target the Python backend with development authentication enabled, prefill the email with dev@workpal.local and the six-digit verification code with 888888. For a multi-step login flow, prefill each value when its corresponding field appears. Keep the values visible and editable, preserve keyboard access, and require the user to submit the form; prefill must not trigger automatic login or email delivery. Gate this behavior on an explicit development-auth capability from the Python backend, never merely on a hostname or a failed configuration request. A missing or false capability disables credential prefill; it never restores mock authentication. Preserve Node mock source files and records; the active frontend on this branch will use Python by default after verification. Add verification for both enabled Python development login and absent/disabled capability, including no automatic submission.


## Review corrections and authorized frontend cutover

### Frontend authentication and startup
Code inspection confirms apps/web/app/main.tsx currently fetches /api/bootstrap before rendering, seeds an authenticated user and a fixed review workspace, and disables WebSocket with an empty URL. LoginEntry is not a verification-code authentication form. These behaviors must be replaced for Python; adding a backend URL alone is insufficient.

The user explicitly authorizes replacing the default mock runtime on this development branch once Python works. Do not introduce a permanent mock/Python mode switch. Preserve original branch history, mock source files and its database, but change the active web entry and npm dev/start to Python. Do not silently fall back to mock on errors. Before cutover, run Python verification through a dedicated development launcher against disposable data.

Implement a real login form using the existing English Workpal visual system. Start with an unresolved authentication state, fetch Python configuration, and resolve the existing session through the Go-compatible authenticated identity endpoint. Only a successful server identity response establishes authentication. A 401 shows login; transport errors and 5xx show a retryable error rather than creating an identity. Prefill dev@workpal.local and 888888 only when Python explicitly advertises enabled development authentication. Submission calls the compatible /auth/send-code and /auth/verify-code flow, issues normal cookies and CSRF state, then resolves the authenticated identity. Never auto-submit. Retain the development flag, loopback binding requirement and production rejection.

After authentication, list authorized workspaces. Restore a remembered workspace only if membership still permits it; select the sole workspace, show a selector for multiple workspaces, or show workspace creation for an empty account. Persist workspace and owner membership atomically on creation. Set the actual workspace ID and slug in the existing platform providers; fetch its projects normally. Do not seed fabricated projects or use /api/bootstrap. Protect deep links until authentication and workspace resolution complete. Logout/session expiration clears identity and workspace-scoped query state and disconnects realtime. Refresh restores an existing valid session without requiring another code submission.

Configure the Vite development proxy for /api, /auth and /ws, with WebSocket upgrade enabled. Route any attachment content paths identified by the contract inventory to Python too. Use same-origin cookie authentication; derive ws/wss from the current page scheme. Connect realtime only after session resolution, subscribe only to authorized scopes, and reconnect using the existing wire contract. A built production frontend requires equivalent HTTP/upgrade routing, not reliance on Vite's dev proxy. Define that routing in the Python launcher/deployment documentation before cutover. All browser-facing listeners remain loopback-only while development authentication is enabled.

Acceptance: unauthenticated direct URL, prefilled manual login, wrong code, refresh session recovery, expired session, logout, no/multiple workspaces, inaccessible remembered workspace, authorized WebSocket subscription and unauthorized denial. Confirm that no /api/bootstrap request or fabricated authenticated state remains in the Python application flow. Test the actual browser workflow with Playwright when available.

### Combined contract inventory and local extensions
Cross-check server/go/cmd/server/router.go and nested registrations against calls in apps/web, packages/core and packages/views, plus server/api.mjs extensions. Record each endpoint's origin (Go, local extension, or mock-only startup), callers, scope, shape, error behavior and explicit support decision. Frontend completion requires all reachable calls to have supported behavior or a deliberate capability-gated unavailable state; passing Go-only tests is insufficient.

Support GET and PUT /api/dashboard/contribution as a local extension. Derive schemas, filtering and aggregation behavior from contribution-tab.tsx, server/contribution.mjs and its tests. Persist actual user-imported commit records in the Python SQLite database, partitioned by workspace. Resolve workspace context using the existing client transport contract and verify membership; reject missing or ambiguous scope rather than selecting the first workspace. PUT requires an owner/admin role and validates the complete import before atomically replacing that workspace's contribution data, matching the current replacement model. Validate referenced projects/issues within the permitted scope and filter private-project data on reads. Preserve days, tz and project_id semantics, response fields and count response. Empty data yields truthful empty aggregates, never mock fixture metrics. Repeated imports, invalid input, restart persistence and workspace isolation need coverage.

Retire /api/bootstrap from the active frontend rather than reimplementing its authentication bypass. Other mock-only extensions must receive a support/exclusion decision in the inventory before their pages count as ready. Any excluded operation must have an explicit UI capability state and backend error; generic 404 pages are not acceptance.

### File content persistence and compensation
Use WORKPAL_UPLOAD_DIR with repository-root-resolved default server/data/python/uploads, separate from Go and mock storage. Store metadata, ownership, size, digest and server-generated opaque storage keys in SQLite; store bytes under this directory. Never use an uploaded filename as a filesystem path. Do not expose the directory as an unauthenticated static mount. Include this directory with SQLite in a coordinated backup procedure.

Upload lifecycle: authorize and validate limits; persist a pending upload intent with a unique object key; stream bytes into a uniquely owned staging file on the same filesystem with bounded size; flush and fsync; atomically rename to the final key and sync the directory; then commit ready metadata and the owning attachment association in a short transaction. Only ready records can be downloaded. Do not keep a SQLite write transaction open while streaming. Pending intents carry owner/lease information so reconciliation cannot delete an active upload.

On streaming or rename failure, mark the intent failed and clean up owned temporary bytes. If metadata finalization fails after rename, the persisted pending intent remains the recovery record; retry finalization only when ownership and validation can be re-established, otherwise reclaim bytes after the lease expires. A reconciler handles crashed/expired pending uploads and retries cleanup without deleting ready or active files. Deletion first makes the attachment unavailable and records durable cleanup work, then idempotently deletes bytes; failed deletion remains retryable. A ready record with missing bytes returns an explicit unavailable-content error, never an empty successful download.

Downloads resolve metadata first and enforce current workspace/private-resource permissions. If the original endpoint uses signed capabilities, preserve its scope, expiry and revocation/access policy rather than treating a storage key as authorization. Prevent traversal and symlink escapes; sanitize download filenames and headers and block staging/internal files. Inventory upload/download URL formats and proxy every required route. Authorization precedes byte access, including range requests.

Acceptance: upload real bytes, restart API and worker, download with identical digest; deny anonymous/cross-workspace/private-resource access; test expired signed access, traversal, size overflow, disk-write failure, metadata-commit failure, crashes before/after rename, active-upload reconciliation safety and failed deletion retry. Merely checking an attachment row is insufficient.

### Revised completion ordering
Contract inventory includes both Go and current frontend calls. Implement storage and identity foundation, then real frontend login/workspace bootstrap and core resources. Add local extensions, durable files and realtime before the full browser acceptance run. Only after these gates and npm run check pass (or unrelated baseline failures are explicitly identified) switch default development/start commands on this branch to Python. Original Go and mock sources and existing SQLite records remain preserved throughout.
