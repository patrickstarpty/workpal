# Workpal service

The root URL serves the connected English Workpal workspace interface. Sign in with a bootstrapped account, explicitly select a workspace, and read or rename it according to current permissions. Projects provides authorized lists/search, details, creation, editing, archive and restore through existing Registry actions. Issues provides creation, requirements editing, reassignment, archive/restore, current records and immutable requirements history. Product resources use an explicit `/app-assets/` allowlist with same-origin CSP and no-store responses. Project resources/workflows, delivery pages and Runtime execution are not connected to this interface yet. Run the browser checks documented in `apps/workpal-web/README.md`; they use isolated temporary SQLite databases.

Use the existing `.venv-workpal` from the repository root. Development defaults to `WORKPAL_ENV=development`, a fixed development secret, and loopback hosts only. Bind development HTTP only to loopback:

```sh
mkdir -p services/workpal/data
.venv-workpal/bin/python services/workpal/manage.py migrate
.venv-workpal/bin/python services/workpal/manage.py runserver 127.0.0.1:8000
```

Set `WORKPAL_DB_PATH` to override the default `services/workpal/data/workpal.sqlite3`. Ensure its parent directory exists and is writable. SQLite connections use WAL, foreign keys, a 5000 ms busy timeout and IMMEDIATE transactions.

Bootstrap the initial workspace and its owner using the interactive password prompt:

```sh
.venv-workpal/bin/python services/workpal/manage.py bootstrap_workspace --username admin --name "Local workspace"
```

The command refuses a second initialization. Automation can use `--password-stdin` with a protected input stream; never put passwords in command arguments or source files. There is no public registration endpoint.

```sh
.venv-workpal/bin/python services/workpal/manage.py test --noinput
.venv-workpal/bin/python services/workpal/manage.py check
```

The test runner creates an isolated temporary file database per invocation and removes it on teardown, including setup failure. `testserver` is enabled only by the runner.

Identity endpoints live under `/api/v1/auth/` (`csrf`, `login`, `logout`, `revoke-sessions`) and `/api/v1/workspaces/<id>/members`. Login and all mutations use POST with JSON and a valid CSRF token; GET is read-only. Workspace members have owner/admin/member roles, and removing a membership immediately removes access to that workspace. Failed logins are limited to five per username and direct source address within a five-minute inactivity window; concurrent failures remain recorded when another login succeeds.

Production requires `WORKPAL_ENV=production`, `WORKPAL_SECRET_KEY` of at least 50 characters (never the development value), and explicit comma-separated `WORKPAL_ALLOWED_HOSTS` without a wildcard. Supply the secret through deployment configuration, not source control. Production enables secure session/CSRF cookies, HTTPS redirects, one-year HSTS including subdomains, and content-type sniffing protection. Serve HTTPS and configure the deployment so Django sees the correct secure request scheme. Do not expose the development server publicly.

The service also contains internal source authorization, content-bound publication approvals, and an Action Registry. Registry mutations persist their result, audit event and outbox entry in one SQLite transaction. Replays recheck current permissions and the original source scope; read actions do not enqueue outbox entries. Publication approval is not an external send or an audience check. The shared HTTP transport is implemented; six identity actions are registered: workspace.read/rename and member.list/create/set_role/revoke. Resource aliases execute through the same Registry.

Actions requiring confirmation first return a persistent confirmation ID without running their handler. The caller resends the exact payload, revision and idempotency key with that ID; only a human actor can consume it. Confirmation expires after ten minutes and retries do not extend it. Prepare with a new key after expiration. Consumption and the action's database effects commit together; concurrent retries execute only once.

This service does not execute agents, call models, or send to external services.

### Session action transport

Fetch `GET /api/v1/auth/csrf`, log in using the existing session login route,
then retain the session and CSRF cookies and send the CSRF token in
`X-CSRFToken` for writes. `GET /api/v1/actions?workspace_id=1` returns the
current member's registered action descriptions with JSON schemas.

For example, an owner or admin can rename a workspace with
`POST /api/v1/actions/workspace.rename` and an application/json envelope
such as `{"workspace_id":1,"payload":{"name":"Example"},"expected_revision":1,"idempotency_key":"synthetic-request-1"}`.
Use the workspace's actual ID and current revision.
Resource writes require a caller-supplied `Idempotency-Key` header and optionally
`X-Confirmation-ID`. Resource body revision maps to expected_revision; path IDs
supply workspace_id and membership_id. Resource and generic envelopes share
idempotency results and confirmations. Member authorization changes require
explicit confirmation. Completed resource responses retain their safe data view;
waiting responses and generic responses return the full ActionResult.

Only workspace_id and payload are required envelope fields. Optional fields
are expected_revision, idempotency_key and confirmation_id. Writes require a
caller-supplied nonempty idempotency key. A waiting_confirmation response has
no completed business effect: resend the same inputs and key with the returned
confirmation_id to approve. The server never supplies approval automatically.
The request body limit is 1 MiB (or the lower Django configured limit).
Responses preserve ActionResult business states; errors use code, message,
request_id, retryable and details with the corresponding HTTP status.

### Project records

The catalog also exposes `project.create/read/list/update/archive/restore`.
Owners and admins manage projects; members can read projects allowed by their
current source grants. Use explicit `project_id` values, including for projects
with identical names. Changes require the current `expected_revision`.
Updating a name without `description` preserves the description; an explicit
empty description clears it. Archive hides a project from the default list
without deleting its record.

`project.list` accepts `query`, `include_archived`, `cursor` and `limit` (default
50, maximum 200). Pagination includes only currently authorized projects;
`next_cursor: 0` means there is no further visible page. Project operations
record business events and do not dispatch agent execution. Unverified GitHub
and Azure Repos bindings are available through `resource.create/read/list/update/remove/restore`;
see [resource contracts](workpal/work/README.md) for source inheritance and confirmation.
Workflow drafts and published snapshots are available through
`workflow.create/read/list/update/publish/version.read`. Owners and admins edit
and publish; members read currently authorized definitions. Draft changes and
publication require the current revision. Publication creates an immutable name
and definition snapshot with a SHA256 digest; it neither approves a delivery nor
executes workflow nodes. `project.set_workflow` binds a published version with
the project's current revision and human confirmation; version ID 0 restores
the built-in default. Previous source restrictions remain after replacement or
reset. `project.workflow.read` returns an independent full snapshot including
its origin, version ID, name, digest and definition. Reading the built-in default
creates no published version. Issue creation persists the complete snapshot;
later project bindings do not rewrite existing Issue workflows.

Issue persistence: `work.issues` owns records and immutable requirements history;
`issue.*` Registry actions expose it through the existing generic action HTTP endpoint.
See `workpal/work/README.md` for the interface. Collaboration now provides comment management, personal subscriptions and Inbox
through the same Registry; see `workpal/collaboration/README.md`. Default settings also
include Agent configuration, deferred Run admission/cancellation and Environment/Investigation
records. Chat, Worker, Squad configuration, Runtime and graph execution remain pending.
The A3 record and collaboration APIs have passed service and multiuser HTTP integration
checks; their connected UI coverage is documented in `apps/workpal-web/README.md`.

Issue transition and dependency actions persist local work facts only. They do not
invoke Runtime, models or external services. The `approved_delivery` completion policy
checks current human Review evidence; `approved_head_merged` still rejects completion
without the code-host merge evidence that B4 must provide.

Comment management: `comment.update`, `comment.remove`, and `comment.restore` require an idempotency key and expected revision. The current author or workspace owner/admin must retain write access to both the Issue and Comment sources, including during replay. Remove requires human confirmation and archives the row; restore retains body, mentions and notifications. Lists hide archived comments unless `include_archived` is true; authorized ID reads retain them. Updates preserve omitted fields, clear mentions with `[]`, and only append sources. Only newly added mentions receive revision-scoped notifications; existing notifications inherit appended source restrictions. Registry execution commits business changes, provenance, audit, outbox and replay results together. No external agent execution or notification delivery is performed.

A3-8b implementation adds transactional Issue assignment and blocked-owner Inbox
hooks. These store local notifications only, with no Worker, Run, model call or
external dispatch. Assignment and blocked notification behavior is verified in
service and multiuser HTTP integration tests.

Issue hierarchy actions support explicit parent creation, CAS attachment/detachment,
and authorized child lists. Relationships do not propagate workflow state or archive
changes. This remains local persistence; no Runtime or model integration is added.
Hierarchy verification includes current and historical source restrictions, assignee
visibility, inherited comment/Inbox privacy, rollback with same-key retry, and two
real SQLite connections racing attachments.

Issue Activity: `issue.activity.list` projects completed Issue and Comment changes
from stored audit events, with current source authorization before pagination.
It returns action/actor IDs, timestamps and authorized object references; it does
not expose request bodies or infer missing history. Signed cursors bind the
workspace and Issue. Reading Activity records an access audit, without an outbox
event or a new visible timeline entry. See `workpal/audit/README.md`.

Issue create and transition resource aliases are available; see
[Issue HTTP contracts](workpal/work/README.md). Both execute through the same
Registry as generic actions and require session authentication, CSRF and an
Idempotency-Key header. Cross-entry replay, source revocation, workflow completion
gates and rollback have been verified. A4 stores real immutable Delivery/Review
records and checks current approval; these routes do not fabricate Review or Run facts.

A4-1a adds private SQLite upload drafts through `workpal.delivery.artifacts`
(begin/status/append) and metadata Registry actions `artifact.upload.begin/read`.
Chunks are SQLite BLOBs; current uploader, membership and source permissions are
checked on every operation. Drafts start open with artifact_id=0. `artifact.upload.finish`
publishes only complete bytes with a verified SHA256, commits their source restrictions
and clears staging atomically. `artifact.read` exposes metadata; the internal
`read_chunk` interface provides bounded authorized SQLite reads. Equal bytes can share
physical storage within a workspace while Artifact identities and permissions remain
independent. Run quotas and cleanup remain pending.

Binary chunks use session-authenticated PUT /api/v1/artifact-uploads/{id}/chunks
(workspace_id, offset) and GET /api/v1/artifacts/{id}/chunks (workspace_id,
offset, optional length). Blocks are bounded to 256 KiB; PUT requires CSRF.
GET returns octet-stream with Content-Length, X-Artifact-Size, X-Artifact-SHA256
and X-Next-Offset. Clients assemble by size and verify the whole SHA256.
Metadata audit and bounded read commit together; appends add no audit/outbox.
Responses disable caching. These routes do not establish download completion.

A4-3a1 adds persisted human Delivery submit/read through the Registry and the
small delivery Interface. It preserves pinned requirements, workflow and
published artifact metadata with protected artifact references. It does not
execute agents. `delivery.list`
adds authorized summary pagination without loading full snapshots or exposing hidden
counts. Parent review verifies attachment protection, independent snapshots,
archived replay, complete submission rollback and two-connection idempotency/version
competition. Current membership and source permissions govern all reads and retries.

Delivery current selection now uses explicit human intent and CAS via
`delivery.select_current` (required expected_revision, reason and idempotency key).
Use `delivery.current.read` for the live pointer; replay returns the original
selection snapshot. Parent checks cover before/after permissions, private history,
archive behavior, full rollback and real two-connection CAS competition. This local
backend invokes no model or Runtime and creates no Run; selection does not
transition Issues.

`delivery.selections.list` reads immutable selection history with subject authorization and per-event source authorization. Cursor pagination excludes inaccessible events; event provenance and reasons retain their original scope. This read creates no pointer or outbox entry.

History authorization is independent of the live target: accessible older events
remain readable when the current target is private. Archived/read-only executor
reads, private-event pagination, cross-workspace isolation and late audit rollback
are covered. Completion gates are still pending.

A4-4a: `delivery.review` records a human approve/request_changes decision for the
selected Delivery using its Current revision; `review.read` retrieves that fixed
fact with current source permissions. Decisions preserve requirements and workflow
snapshots and increment only Current.revision. Approval checks published attachment
metadata and per-criterion evidence, without claiming tool execution or merging.
Completion gates and HTTP aliases remain subsequent work.

Review validation includes snapshot roles, full source authorization, real evidence
metadata, changed requirements, immutable archived history and complete transaction
rollback. Two-connection tests cover same-key retries, competing human reviewers and
review versus current-selection competition. Approval validity and Issue completion
are separate gates, described below.

Review history is available through `review.list` with subject, cursor (default 0),
and limit (default 50, maximum 200). Read-only members and executors may read
source-authorized history, independently of current delivery selection.
History preserves the original submission and requirements versions. Private latest
decisions do not make older visible approvals effective; permission filtering is
separate from approval validity. Cross-workspace reads and partial pages after
authorization failures are rejected without recording a successful access.

Delivery comparison is available through read-only `delivery.compare`, using two
strict positive Delivery IDs in the current workspace and the same subject.
It compares saved snapshots only, without BLOB reads, execution or approval claims.

`delivery.approval.read` reads current human approval validity against the exact
selection revision and current requirements. It does not complete Issues or claim
execution, test, or merge evidence.

Issue completion with `approved_delivery` checks the current human approval inside the transition transaction. Completion retains a protected Review reference and an immutable approval snapshot. Evidence roots are appended to Issue provenance; the transition retains full approval provenance. Cached completion results recheck current access. `approved_head_merged` remains unavailable without verified merge facts; completion dispatches no execution.

Delivery resource aliases: session-authenticated, CSRF-protected `POST
/api/v1/issues/{issue_id}/deliveries` accepts `workspace_id`,
`requirements_revision`, `summary`, and optional `limitations`, `artifact_ids`,
`evidence`, `source_refs`. `POST /api/v1/deliveries/{delivery_id}/reviews`
accepts `workspace_id`, `revision`, `version`, `decision`. Both require a nonblank
`Idempotency-Key`; optional `X-Confirmation-ID` passes through existing action
confirmation rules. Completed responses are business DTOs; other states retain
ActionResult. These aliases execute the same Registry actions and authorization;
they do not select a delivery, mark an issue Done, or execute an agent.

Authenticated session context: GET /api/v1/auth/session returns the current active user id/username and current memberships as workspaces (id, name, revision, role), ordered by workspace id. No query parameters are accepted. Responses are no-store; this read does not enter the business Registry or write audit/outbox records.

Issue reading UI supports authorized lists, title search, archived filtering, pagination, current details and on-demand immutable requirements history. Project names and saved workflow labels come from real reads. Issue creation includes optional assignment. Current blocking facts and on-demand status history use saved workflow labels, lazy person labels and authorized pagination. Run `node apps/workpal-web/scripts/qa.issue-status-history.mjs` for the isolated real-data journey. `Change status` supports blocking and explicit human completion through the existing evidence/permission gates; `qa.issue-transition.mjs` and its review/permissions scripts cover the real write paths. Collaboration pages remain subsequent work. Run `qa.issues.mjs` and `qa.issues.review.mjs` in `apps/workpal-web/scripts/` for current/history permissions, source revocation, delayed responses, saved workflow labels, offline retry and read-only behavior. Issue content and cached results authorize their exact requirements versions; history never falls back on a denied read.

Workspace people directory: `workspace.people.list` is available to owner, admin,
and member through the shared action endpoint. Optional query (literal substring,
up to 150 characters), exclusive User-ID cursor (default 0), and limit (default
50, maximum 200) return only current active workspace users as user_id/username,
plus next_cursor (0 at end). Membership is checked in the same SQLite transaction.
Directory visibility grants no Issue or requirement access or assignment rights.
Directory reads audit pagination metadata only; usernames and authentication fields
are not copied into the audit event. All `/api/v1/` responses use `no-store`,
including common action reads, resource aliases and errors returned before a view
executes (such as a failed CSRF check).

Issue creation uses real project and people directories, stable criteria keys and idempotent submission. Run node apps/workpal-web/scripts/qa.issue-create.mjs from the repository root for the isolated database creation journey and desktop/mobile checks. Creation does not start agent execution. Run `node apps/workpal-web/scripts/qa.issue-create.review.mjs` for the 13 independent creation checks: filtered directories, revocation, real conflicts, original-request retries, delayed responses and accessible narrow layouts. Discarded responses release their unread body streams; a context change never interprets an old response as a new result.

Issue requirements editing shares the creation form and supports revision conflicts with explicit reload and review, and original-request retries for unknown outcomes. Run `node apps/workpal-web/scripts/qa.issue-edit.mjs` for the isolated browser journey and `qa.issue-edit.review.mjs` for independent history, permission and concurrency checks. The UI sends only changed requirements fields; the existing Registry remains responsible for authorization, CAS and immutable history. Editing does not start agent execution.

Issue detail supports Registry-backed archive and restore for catalog-authorized users. Archiving changes visibility without changing workflow or requirements. Unknown outcomes retain the original request for retry; revision conflicts require an explicit reload and decision. Run `node apps/workpal-web/scripts/qa.issue-archive.mjs` for the core journey and `node apps/workpal-web/scripts/qa.issue-archive.review.mjs` for 12 independent permission, retry, conflict, pagination and navigation checks. Current visibility read during conflict recovery remains visible after closing and reopening the dialog. No external model or runtime calls are involved.


Current-person directory: `read_person(actor, user_id)` and Registry
`workspace.people.read` accept an exact positive integer through SQLite's maximum.
An active current workspace member returns only
`{"person": {"user_id": id, "username": username}}`; unavailable targets return
`{}` (HTTP 200). Invalid requesters remain 404. This read grants no business
access, creates no business references or notifications, and audits only the
requested user_id. HTTP uses session/CSRF/Host checks and no-store.

Issue assignment: issue details resolve the current person by ID. Change assignee shares the searchable, paginated people picker with creation, supports Unassigned, and saves through issue.update with revision and idempotency protection. Unknown outcomes retain the original request; conflicts require explicit reload and save.

Assignment verification: `node apps/workpal-web/scripts/qa.issue-assignee.review.mjs` runs 16 independent browser scenarios. These cover exact ownership/history/notification changes, separate-session persistence, explicit conflict recovery, original-request retry after a newer reassignment, membership/source revocation, local person-label recovery, directory and navigation races, and long usernames at 1440/390 widths. Person labels wrap long names without rendering user input as HTML. The current assignment UI has no agent execution side effects.

Default settings register the Agent, Run and Environment/Investigation modules.
The execution and investigation lane settings remain compatible imports without duplicate registrations.
Authenticated action HTTP supports Agent configuration, deferred Run records and cancellation,
Environment/Service configuration, upload-source configuration and Investigation records.
Runs report `runtime_unavailable`: no Runtime or model executes. Upload sources save configuration;
they do not collect evidence. Network collection and Jira mutations remain unimplemented.
