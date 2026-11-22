# Create issue transport audit

Status: finite static target closure; root review pending. No backend or runtime support claim.

Title and description editor shortcuts share handleSubmit: anchored create without preview returns; empty trimmed title focuses title; composer applies upload gate and single flight.

Submit flushes pending description before draft identity snapshot; only referenced attachments included. Anchored manual create sends capture_token and issue payload; ordinary create includes parent_issue_id. Stage only sent with parent. Optional labels and properties included only when populated.

After create child links run allSettled; failures toast without rollback. Labels attach only when selected and returned issue.labels is undefined; failures do not reject accepted create.

Source changed/deleted errors await injected preview refetch; unsupported/too-large errors reject. invalid_issue_property uses current cached catalog to focus valid property or remove unavailable property from current draft. Structured duplicate 409 provides navigation and returns false.

Accepted create persists assignee/mode, flushes late description and clears only identical submitted draft. Unmounted or changed draft prevents close/reset. keepOpen resets fields and starts batch continuation; cleanup ends untouched continuation.

Mode switch uses upload gate, persists shared values, seeds empty agent prompt/actor and carries parent identifier and explicit assignee clearing. Settings push closes; modifier navigation leaves dialog. Success and duplicate buttons navigate only on click.

Parent detail and children enabled only with parentIssueId. Property catalog unconditional. CreateRunHint preview enabled only agent/squad plus ID; WorkflowHandoffHint project list enabled only when workflow exists. Voice only inserts description, without send callback.

Create hooks share useIssueCreateMutation: success patches loaded list buckets, records recent visit, invalidates returned parent children/progress; settlement on either result invalidates list, flat, table, assignee/my-assignee groups, project Gantt, sidebar and project prefixes.

Queued child linkage invokes updateIssue with id and parent_issue_id only: PUT, never moveIssue. Optimistic coordinator patches projections and old-parent children; error rolls back and invalidates detail/list/my/flat/table. Success reconciles newer revisions, excludes properties, flushes stale keys. Settlement invalidates derivatives/table/stale keys and old/new parent children/progress/batched children. Attachment and duplicate predicates are false for this caller; status predicate false and project_id absent. Inbox status/priority write tracking is absent.

Label fallback POST sends label_id; on either settlement invalidates byIssue labels and entire workspace issue prefix. Active registered observers can refetch; cache cancellation/patching is not a request.

Status catalog enabled Boolean(wsId), includes archived=true; workflows enabled Boolean(wsId); projects enabled Boolean(wsId)&&Boolean(projectId). useProjectWorkflow delegates to same hook. Actor names read member/agent/squad options without added gates; plugin installations require feature flag and nonempty workspace. Step labels invoke actor hook even when no concrete handler, then resolve locally.

propertyListOptions uses properties list key with includeArchived=false and no enabled gate, selects properties; 404 returns empty catalog, other errors propagate. Source failure formatter performs no transport: deleted codes map to translations; too-large limits compare >256 comments, >1048576 text bytes, >100 attachments, >524288000 attachment bytes, otherwise generic translated limit error.

Custom property create branches first GET config and reject unless atomic create capability true. Both create responses must validate and preserve requested property snapshot. Manual sub-issue 404/405 maps to unsupported source context.

Concrete direct/query union (live client anchors):

- client:1648 POST const raw = await this.fetch<unknown>("/api/issues", {
- client:1714 POST const raw = await this.fetch<unknown>(`/api/comments/${anchorCommentId}/sub-issues`, {
- client:1771 PUT return this.fetch(`/api/issues/${id}`, {
- client:5032 POST const raw = await this.fetch<unknown>(`/api/issues/${issueId}/labels`, {
- client:3351 GET const raw = await this.fetch<unknown>("/api/config");
- client:4692 GET const raw = await this.fetch<unknown>(`/api/issue-workflows`);
- client:4821 GET const raw = await this.fetch<unknown>(`/api/issue-statuses${query}`);
- client:4884 GET raw = await this.fetch<unknown>(`/api/properties${suffix}`);
- client:3765 GET return this.fetch(`/api/workspaces/${workspaceId}/members`);
- client:2066 GET return this.fetch(`/api/agents?${search}`);
- client:5203 GET const raw = await this.fetch<unknown>(`/api/squads`);
- client:3425 GET raw = await this.fetch<unknown>(`/api/workspaces/${workspaceId}/plugins`);
- client:4517 GET const raw = await this.fetch<unknown>(`/api/projects?${search}`);

Observer refetch union inherits the finite issue-cache and issue-query proof records, constrained by the settlement predicates above. These are possible active-observer requests, not guaranteed requests.

Child rendering boundaries: ContentEditor, TitleEditor, ActorAvatar, SourceContextPreviewCard, CopyParentFields, IssuePickerModal, property/status/assignee/project/date/label/stage pickers, VoiceDialogFooter. Draft attachment and voice adapter proofs remain separately bounded. Reused proof snapshots and their declared source hashes were validated; metadata and live anchors are in JSON. Only these three Task1 artifacts changed.
