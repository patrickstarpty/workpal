# Workpal web client

Dependency-free English workspace interface and ES module transport. Start Django from the repository root with `.venv-workpal/bin/python services/workpal/manage.py runserver 127.0.0.1:8000`, then open http://127.0.0.1:8000/. Migrate and bootstrap an account using the service README first. Supports session login/logout, explicit workspace selection, reading and authorized renaming, project management, and Issue creation, requirements editing, reassignment, archive/restore and reading with requirements history. No browser storage is used. Project resources/workflows, delivery pages and Runtime execution remain outside this interface.

Run `node apps/workpal-web/scripts/qa.mjs --suite shell` from the repository root for an isolated SQLite/browser check using the existing virtualenv and Playwright (WORKPAL_PLAYWRIGHT can override its module location). Screenshots go under outputs/workpal-web. Only shell is supported.

Run `node apps/workpal-web/scripts/qa.review.mjs` for the browser failure cases:
invalid credentials and input, two-user revision conflicts, committed response
loss with exact-intent retry, revoked membership, late workspace responses,
unconfirmed logout and long account names. These use real Django writes; response
loss tests discard an actual server response rather than inventing a success.
Both runners own an isolated temporary SQLite database and an ephemeral loopback
port, enforce development-only test settings, and close their processes and files
on exit. `npm --prefix apps/workpal-web run qa:shell` also works.

Project checks use the same isolated fixture:

- `node apps/workpal-web/scripts/qa.projects.mjs`: creation, durable reload, edit, archive/restore, keyboard and responsive layouts.
- `node apps/workpal-web/scripts/qa.projects.review.mjs`: authorization before pagination, duplicate names, member and workspace isolation, grant revocation, real commit followed by response loss, revision conflict, delayed responses and long text.

The project Module owns filters, cursor pagination, selected records and edit
intents behind `showProjects({client,content,current,onError})`. Navigation and
internal request ordering both guard responses. Refreshing the list cannot prove
whether an unknown create finished, so it preserves the original request key and
frozen payload until an explicit retry resolves it. Lists never expose a count of
hidden records. Owners and admins manage projects; members read currently
authorized projects. The server checks every action again.

Known validation failures leave the draft editable. Unknown write outcomes retain
the original request for an explicit retry; current permission failures clear the
view. Neither a stale response nor a pending result is shown as a successful save.

Run: `node --test apps/workpal-web/tests/*.test.mjs`

Responses are validated before they reach callers. Authentication requests are
serialized, and a session refresh follows the latest authentication intent.
Catalog schema bounds may describe server integers wider than JavaScript's safe
integer range; treat those bounds as descriptive metadata, not client validation
rules. Actual request and response IDs still require safe integers.

The transport has been checked against actual Django session, catalog and action
responses in an isolated temporary database. It does not provide Runtime execution.

Issue reading supports authorized lists, title search, archived filtering, pagination, current details and on-demand immutable requirements history. Project names and saved workflow labels come from real reads. Issue creation includes optional assignment. Current blocking facts and on-demand status history are read-only, with saved workflow labels, lazy person labels and authorized pagination. Run `node apps/workpal-web/scripts/qa.issue-status-history.mjs` for the isolated real-data journey. Status writes and collaboration pages remain subsequent work. Run `node apps/workpal-web/scripts/qa.issues.mjs` for the reading/offline journey and `node apps/workpal-web/scripts/qa.issues.review.mjs` for independent current/history permissions, revoked access, saved workflow labels, delayed responses, read-only effects and long content. Permission failure clears previous content; it never falls back to an earlier visible version.

Issue creation uses real project and people directories, stable criteria keys and idempotent submission. Run node apps/workpal-web/scripts/qa.issue-create.mjs from the repository root for the isolated database creation journey and desktop/mobile checks. Creation does not start agent execution. Run `node apps/workpal-web/scripts/qa.issue-create.review.mjs` for the 13 independent creation checks: filtered directories, revocation, real conflicts, original-request retries, delayed responses and accessible narrow layouts. Discarded responses release their unread body streams; a context change never interprets an old response as a new result.

Issue requirements editing shares the creation form and supports revision conflicts with explicit reload and review, and original-request retries for unknown outcomes. `createRequirementsForm(value)` exposes `{element, read(), replace(value)}`; replacement retains keys consumed during this draft, including deleted criteria. Each editor keeps its original write intent across dialog closure, while request validity and busy state belong to each opened dialog. Only changed fields are submitted. A conflict reload merges untouched fields from the current saved requirements and preserves local changes for explicit review.

Run `node apps/workpal-web/scripts/qa.issue-edit.mjs` for the isolated browser journey and `node apps/workpal-web/scripts/qa.issue-edit.review.mjs` for 11 independent checks covering immutable history, exact retries, dialog and navigation races, permissions, conflict merging, stable keys and narrow layouts. Editing does not start agent execution. Use the installed `node` executable or existing `npm run` scripts; do not use `npm exec`/`npx`, which can download packages.

Issue detail supports Registry-backed archive and restore for catalog-authorized users. Archiving changes visibility without changing workflow or requirements. Unknown outcomes retain the original request for retry; revision conflicts require an explicit reload and decision. Run `node apps/workpal-web/scripts/qa.issue-archive.mjs` for the core journey and `node apps/workpal-web/scripts/qa.issue-archive.review.mjs` for 12 independent permission, retry, conflict, pagination and navigation checks. Current visibility read during conflict recovery remains visible after closing and reopening the dialog. No external model or runtime calls are involved.

Issue assignment: issue details resolve the current person by ID. Change assignee shares the searchable, paginated people picker with creation, supports Unassigned, and saves through issue.update with revision and idempotency protection. Unknown outcomes retain the original request; conflicts require explicit reload and save.

Assignment verification: `node apps/workpal-web/scripts/qa.issue-assignee.review.mjs` runs 16 independent browser scenarios. These cover exact ownership/history/notification changes, separate-session persistence, explicit conflict recovery, original-request retry after a newer reassignment, membership/source revocation, local person-label recovery, directory and navigation races, and long usernames at 1440/390 widths. Person labels wrap long names without rendering user input as HTML. The current assignment UI has no agent execution side effects.

Status editing is isolated in `issue-transition.js`, using saved workflow edges,
current workspace reviewer roles, explicit conflict reads and retained request
intents. `qa:issue-transition` exercises the real member entry and status writes.
Completion evidence remains enforced by the backend. The six-scenario review matrix is covered by the dedicated review script below.

`qa:issue-transition-review` runs six real HTTP/isolated SQLite acceptance
scenarios: Blocked ownership and persistence, published manual completion and
reviewer roles, completion/dependency gates, both conflict reload branches,
lost-response idempotent replay after a newer transition, and dialog/navigation
response isolation. Screenshots cover populated Blocked forms at 1440/390.
These checks do not establish Runtime or external completion evidence support.

Dependency core QA: `npm run qa:issue-dependencies` uses isolated SQLite/HTTP and member browser contexts to check reads, add/remove persistence, candidate search races, keyboard access and narrow layouts. Screenshots are written to `outputs/workpal-web/a54d1-dependencies-{desktop,mobile}.png`. `npm run qa:issue-dependencies-review` covers six groups of conflicts, lost responses, current authorization and late-response isolation. The isolated threaded test server uses a connection queue of 128; `scripts/qa.startup.mjs` checks six bursts of six independent contexts without retrying failures.

Dependency recovery checks: `node apps/workpal-web/scripts/qa.issue-dependencies.review.mjs` from the repository root exercises real session HTTP and isolated SQLite facts for conflicts, lost responses, revocation, and stale dialog/context results. No model calls.

Hierarchy reader: `qa:issue-hierarchy` and `qa:issue-hierarchy-review` exercise real local member sessions and SQLite data. Coverage includes authorized parent/subtask navigation, current-parent refresh, private and archived children, 20-item pagination, independent permission loss, read-only table snapshots, held real responses across Issue/workspace/logout and filter changes, and keyboard focus through pagination and parent/child navigation. Keyboard checks also verify that an old navigation response cannot reclaim focus. Long markup-like titles remain text at 1440px and 390px. Parent and subtask reading only; reparenting and child creation are not included. These checks use the local backend with no model calls.

Feature-owned reads may pass a synchronous `current: () => boolean` option to `client.perform`. The callback stays local and is checked before dispatch and before processing responses or reporting access loss. Hierarchy reads combine page, detail and loading generations; obsolete results are discarded without clearing a newer detail. Current permission errors retain the existing access-loss behavior. This does not cancel server work or replace authorization.

Parent editor vertical acceptance: `npm run qa:issue-parent` uses isolated SQLite,
real HTTP/CSRF and two independently authenticated member browser contexts to
reparent across projects and explicitly detach. It checks persisted revisions,
unchanged business facts, append-only sources and exactly two write records.
Candidate pagination and conflict/lost-response matrices remain separate follow-up work.

`qa:issue-parent-review` checks real candidate pagination, query response isolation, keyboard selection, readonly facts and responsive text rendering; permission/CAS acceptance remains separate.
