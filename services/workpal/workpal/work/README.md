Project resources store unverified GitHub or Azure Repos repository references only.
They perform no network, filesystem, Git, model or agent execution. Connectivity
and identity verification belong to B4. References accept HTTPS URLs without
userinfo, queries or fragments, or provider identifiers; credentials are never
accepted. checkout_ref is optional text: omission preserves it; empty clears it.

resource.create/read/list/update/remove/restore require explicit project_id;
selection also requires resource_id. Owners/admins manage; current members read,
with current source grants required for everyone. remove requires human
confirmation and only archives; archived records remain readable and restorable.
Archived projects remain readable but reject new resources (project_archived).

source_refs is a JSON array of at most 50 closed {kind,id} objects. Sources must
already exist and be authorized in the same workspace. Parent project provenance
is always registered. Source relationships only accumulate: omission and [] both
preserve historical restrictions. Configuration updates reset verification to
unverified. Workspace/project identity cannot change. Lists filter authorization
before stable ID pagination (default 50, maximum 200, terminal next_cursor=0).
Registry writes persist ordinary audit/outbox records, never execution dispatch.

Project workflow selection uses confirmed project.set_workflow with the project's
expected revision. workflow_version_id=0 restores the built-in configuration.
Bindings accept published versions only; provenance is appended to the project
and retained after replacement or reset. Direct service.set_workflow checks
current owner/admin membership and project/version write grants.

service.snapshot_workflow(actor, project_id) and project.workflow.read return
independent {origin, version_id, name, sha256, definition} values. Published
values come from immutable versions; built-in values use Default and canonical
SHA256 of {name, definition} with sorted keys, compact separators, UTF-8 and no
NaN. Built-in reads create no publication records. Issue creation persists the
whole returned value, including built-in definitions. Later project bindings do
not rewrite that snapshot. Registry writes record local business audit/outbox
events only; workflow execution is not implemented here.

Issue records are owned by `work.issues`: create/read/update/list_issues/archive/restore/read_requirements.
Registry actions are issue.create/read/list/update/archive/restore/requirements.read.
Writes require idempotency keys; update/archive/restore require expected_revision.
Explicit project IDs select projects; duplicate titles are allowed. Requirements are
append-only numbered canonical JSON hashes. Empty description/criteria and assignee 0
clear values; omitted update fields retain values. Source references only accumulate.
Issue creation stores the complete workflow snapshot, including built-in definitions.
Assignees must be active human workspace members with current read access.
List returns Issue fields except workflow_snapshot, filters current authorization before
pagination, defaults to 50 (maximum 200), and has no total. Requirements reads require
issue_id and number and dynamically authorize against the Issue's current provenance.
Runs, delivery, comments, notifications, Agent/Squad configuration, runtime execution
and graph execution are not implemented by this module.

Issue facts: `transitions.transition` is the sole ordinary status writer and uses
only the Issue's persisted workflow snapshot. `list_transitions` retains history
through archive/restore and authorizes each history record before pagination.
Reasons accept up to 4000 valid UTF-8 characters. Block ownership requires a
current readable human member.
Completion requires a human snapshot reviewer and manual policy; delivery and
merged-head policies return completion_not_ready until real Delivery/Review/provider
facts are integrated in A4/B4. Human identity and current reviewer role are also
checked when replaying a completed Done action. No transition dispatches execution
or approves delivery.

`dependencies.add/remove/list_dependencies` own active edges and preserve historical
provenance on removal. The limit is 100 active dependencies per Issue. Completion
checks `unresolved_dependencies` against current categories; cancelled and archived
unfinished targets remain unresolved. List filters include status_key and optional
assignee_user_id (0 means unassigned). Writes use the Registry transaction and CAS.

Issue hierarchy: nullable protected parent pointers are changed by `issue.set_parent`
with child CAS; `issue.create` accepts an optional parent. Parent provenance is
append-only, including after detach. Children use independent requirements and
workflow snapshots. `issue.children.list` reuses authorized Issue pagination;
`issue.list` accepts a parent filter (0 selects roots). No execution is dispatched.
Reparenting and detachment retain all prior source restrictions. Attaching checks
the existing assignee's current read access after adding the parent source; failure
rolls back the relationship, revision and source links. Existing comments and
notifications inherit the restriction. Archived parents reject new attachment,
while current-authorized replay of completed actions remains valid.

`issue.activity.list` is a thin adapter to audit's authorized history projection.
Issue events belong to their primary output Issue; Comment events belong to the
Comment's actual Issue, including archived comments. Parent, dependency and source
references do not copy an event into those other Issues' timelines.

Issue HTTP aliases: POST `/api/v1/workspaces/{workspace_id}/issues` accepts the
ordinary `issue.create` payload without workspace_id. POST
`/api/v1/issues/{issue_id}/transitions` accepts workspace_id, revision, target
and optional reason/blocked_owner_user_id; issue_id must not occur in the body.
Both require a logged-in active session, CSRF and Idempotency-Key, and accept
optional X-Confirmation-ID. Completed responses contain the business DTO; other
states retain ActionResult. They share Registry authorization, replay and CAS
with generic actions. No Runtime dispatch or additional resource routes exist.

Issue completion with `approved_delivery` checks the current human approval inside the transition transaction. Completion retains a protected Review reference and an immutable approval snapshot. Evidence roots are appended to Issue provenance; the transition retains full approval provenance. Cached completion results recheck current access. `approved_head_merged` remains unavailable without verified merge facts; completion dispatches no execution.

Issue content authorization checks both the Issue and the exact requirements version. Lists filter content access before pagination. Internal `view(row, actor)` authorizes returned content inside the caller's write transaction. Historical reads authorize only the requested version.

`result_refs(actor, result)` resolves saved DTO versions and validates Issue/workspace ownership. Registry appends these references in stable order for audit, outbox and cache scope, and resolves them again during replay, including cache rows written before requirements references were recorded. Missing or mismatched saved versions fail closed without rerunning handlers. Content edits require read/write access to the previous version and propagate its source roots without linking the Issue back to its own requirements.

Content references also validate the version number and immutable title/description/
criteria against the saved requirement, and bind the Issue to the result's original
object references. Missing content fields cannot opt a cached response out of
authorization. Metadata-only dependency/transition lists do not use this resolver.
An executed content edit retains both its output version and the previous version
it read; replay checks these saved identities without resolving today's version.
