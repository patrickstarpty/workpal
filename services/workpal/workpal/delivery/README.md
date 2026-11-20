# Upload drafts and verified artifacts

`artifacts.begin(actor, metadata)`, `status(actor, upload_id)` and
`append(actor, upload_id, offset, chunk)` persist private upload drafts and binary
chunks in SQLite. Each append transaction rechecks current membership and source
write permissions. Reads require the uploader and current source read permissions.
Registry actions `artifact.upload.begin/read` expose draft metadata; append is an
internal interface. No grants are created.

Repeated begin keys return the original creation result. Use upload read/status
for the current resume offset. Repeating a stored block at its original offset
requires current write permission and returns the latest received offset, without
another chunk. Other workspace owners cannot read or append another user's draft.
IDs are bounded by SQLite's supported positive integer range. File metadata and
blocks are validated before writes; partial chunk/source/audit failures roll back
their complete local transaction. Two distinct SQLite connections verify duplicate
and conflicting offset behavior.

Drafts report `status=open` and `artifact_id=0`. `finish(actor, upload_id, sha256)`
requires all declared bytes, consecutive stored blocks and their actual SHA256.
It atomically creates an Artifact, inherits the upload's sources, marks the upload
completed and removes staged chunks. Wrong hashes or incomplete content retain
the draft. Any later transaction failure restores its staged bytes and offset.
Completed uploads reject append; finishing the same upload/hash returns its existing
Artifact after current authorization checks. `artifact.upload.finish` uses Registry
idempotency and commits publication, audit and outbox together.

Each upload creates an independent immutable Artifact identity, owner and source
scope. Equal bytes may share an internal Blob within the same workspace, after
checking actual content, without sharing logical access or exposing reuse metadata.
Other workspaces store separate Blobs. Blob and owner deletion are protected by
published references.

`read(actor, artifact_id)` and Registry `artifact.read` return authorized metadata.
Published content is readable by current members with all applicable source read
permissions, including members who cannot write; owning an Artifact does not bypass
those permissions. `read_chunk(actor, artifact_id, offset, length=262144)` rechecks
authorization on every call and fetches only the SQLite byte range. End of file,
including an empty Artifact, returns empty bytes. Metadata reads do not load content.
Limits are 25 MiB per Artifact and 256 KiB per block/range. Bytes never enter an
ActionResult, cached action result or audit field.

Run quotas, log retention and cleanup are not
implemented yet. Migration from upload-only schema preserves existing metadata,
source links, bytes and resume offset; a continued upload can subsequently publish.

Binary chunks use session-authenticated PUT /api/v1/artifact-uploads/{id}/chunks
(workspace_id, offset) and GET /api/v1/artifacts/{id}/chunks (workspace_id,
offset, optional length). Blocks are bounded to 256 KiB; PUT requires CSRF.
GET returns octet-stream with Content-Length, X-Artifact-Size, X-Artifact-SHA256
and X-Next-Offset. Clients assemble by size and verify the whole SHA256.
Metadata audit and bounded read commit together; appends add no audit/outbox.
Responses, including middleware CSRF rejections, disable caching. These routes
do not establish download completion.

Manual Delivery exposes `service.submit(actor, SubjectRef, submission)` and
`service.read(actor, id)`, plus `delivery.submit/read` Registry adapters.
Only human actors submit; immutable requirements/workflow/artifact snapshots
and canonical SHA256 accompany protected Artifact links. Authorization follows
all inherited sources on every read and replay. Registry supplies transactional
idempotency, audit and outbox; direct submit participates in atomic writes.
Direct submission validates subject types, bounded IDs and source references;
returned snapshots are independent of the caller's mutable input collections.
Attachment links themselves prevent Artifact deletion. Late source registration,
attachment insertion or audit failures roll back the complete submission and permit
retrying its original key. An archived Issue retains historical read and completed
replay access while rejecting new submissions. Original Artifact sources are not
changed by its consumption in a Delivery.
`service.list_deliveries(actor, SubjectRef, cursor=0, limit=50)` and `delivery.list`
return authorized summaries, with a maximum page size of 200. Hidden submissions
do not consume page slots or disclose counts. Only summary columns and the saved
requirements number are queried; subject authorization does not scan the history.
The output references and access audit retain the displayed submissions' sources.
Reads allow authorized executor actors and require no source write permission;
authorization service failures remain errors rather than empty pages.

Two distinct SQLite connections verify one submission for a shared key and unique,
consecutive versions for different keys. Membership removal, user deactivation,
requirement-specific provenance changes and post-audit idempotency-save rollback
are covered. Project workflow rebinding leaves historical Issue/Delivery snapshots
unchanged. Submission and selection do not create Runs or mutate Issues.

Explicit selection is exposed through `selection.current(actor, SubjectRef)` and
`selection.select_current(actor, delivery_id, revision, reason)`, with thin
`delivery.current.read` / `delivery.select_current` Registry adapters. Empty current
has CAS revision 1 without persisting a pointer; the first human selection creates
revision 2. Submissions remain candidates and never change current. Selection
requires current write permission on subject, target and previous delivery;
replays retain their original result and source scope. Immutable selection records
protect actor/reason and before/after provenance; mutable pointers are not sources.
Current reads query only Delivery identity and version metadata. They disclose
neither the former target nor its private reason after switching to another target;
the immutable events and cached selection results retain their original provenance.
Rework may inherit an earlier Selection without forming a mutable-pointer cycle.
Archived subjects permit current reads and completed retries but reject new choices.

Two independent SQLite connections verify one committed action for a shared key,
and exactly one winner when competing choices use the same initial or existing CAS
revision. Failures after source registration, history, audit or idempotency writes
roll back the pointer and all accompanying facts. Selection events protect former
Deliveries even after the pointer moves.

`delivery.selections.list` reads immutable selection history with subject authorization and per-event source authorization. Cursor pagination excludes inaccessible events; event provenance and reasons retain their original scope. This read creates no pointer or outbox entry.

History remains available to authorized read-only/executor actors after archive,
even if the current target is private. Hidden prefix, middle and tail events do not
consume page slots or enter the access audit's displayed scope. Switching back to a
public target does not expose earlier private reasons. Workspace/subject isolation,
strict inputs and rollback after the actual access-audit write are verified.

A4-4a adds immutable human Review decisions through `review.review` and
`review.read`, exposed as `delivery.review` and `review.read` Registry actions.
The write requires an idempotency key and the current DeliveryCurrent revision.
Snapshot reviewer roles and current source write access apply even to replay.
Approve requires current requirements and real artifact evidence for every
criterion; request_changes preserves a reason for incomplete or stale work.
Only Current.revision advances. Review provenance excludes the mutable pointer.
These decisions do not establish tool execution, merged heads, or Issue completion.
Approval validity and completion gates remain subsequent work.

Review checks cover missing criteria, incomplete per-criterion evidence, attachment
metadata mismatches and changed requirements. Snapshot reviewer roles apply without
an owner bypass; private decision sources protect both reasons and cached retries
without narrowing the original Delivery. Archived Reviews and review-derived rework
retain their original facts. Review reads use saved snapshots without loading the
Delivery's duplicate content, and the action catalog exposes bounded positive IDs.
Two real SQLite connections verify one same-key decision, one winner between two
human reviewers and the shared revision gate between review and current selection.
Failures after Review insertion, provenance, audit or idempotency persistence restore
the complete prior state. Historical approval is not an effective-completion result.

`review.list` / `review.list_reviews` reads immutable review summaries after subject
and complete review-source authorization. Hidden rows do not consume page slots;
only visible review IDs form cursors. Requirements revision is projected from the
saved review JSON. Historical approval is not a current approval gate.
Cross-Delivery and requirements-version histories retain their original facts.
Private latest decisions or targets do not hide accessible older history or grant
access to private reasons after a pointer change. Archived read-only/executor reads,
workspace/subject isolation and authorization failures during pagination lookahead
are verified; a 503 returns no partial page and leaves no access-audit entry.

`comparison.compare(actor, before_delivery_id, after_delivery_id)` and read-only
`delivery.compare` compare two saved Delivery snapshots for one subject after
current authorization of both complete source scopes. Text and keyed collection
changes preserve logical Artifact identity and order; workflow comparison uses
saved snapshots. This does not evaluate approval validity or tool results.

Current approval is available through `approval.inspect(actor, subject)` and the
read-only `delivery.approval.read` action. Reads use one local transaction, authorize
current requirements and exact Delivery/Review sources, and return metadata only.
Historical approval cannot substitute for the exact current revision. Issue
completion remains unchanged; no execution or merge evidence is inferred.

`resource_http.py` supplies two POST aliases over Registry: issue deliveries map
to `delivery.submit`, delivery reviews to `delivery.review`. URL IDs exclusively
supply subject/delivery identity. Review `revision` is the Current CAS revision;
`version` is Delivery.number. Optional submission fields retain omission semantics
for cross-entry-point idempotency. Transport rejects query parameters, unknown
fields and body identity overrides; strict JSON is bounded at 1 MiB. Responses
are no-store, errors use the shared serialization, and unexpected failures are
redacted. The existing `http.py` remains binary artifact transport. AutomationRun
has no resource route because execution is not implemented.
