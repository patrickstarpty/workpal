# Autopilot detail transport audit

Single target: `packages/views/autopilots/components/autopilot-detail-page.tsx`. Static source evidence only; root review pending. No backend or global closure claim.

Page:1053 detail and runs mount before loading/not-found returns; factories have no workspace/id enabled gate and no custom interval. Run detail:147 mounts through transcript header for webhook task rows; factory defaults enabled true. Query keys partition workspace, autopilot and run IDs.

Permissions:1132 can_write !== false; can_manage_access ?? canWrite passed to edit child. Controls hide on explicit read-only; handlers do not independently enforce authorization. Run requires active and !pending. Archived disables status switch only; other write controls remain governed by canWrite. Pause reason banners only navigate.

TriggerRow:361 delete/rotate use autopilotId and trigger.id; success toast/close, errors toast; delete finally resets busy. Rotation pending blocks repeat UI/close. Schedule/webhook editors are imported children; API kind has no edit action. Disabled triggers hide next_run_at.

AddTriggerDialog:609 exists only while open. Schedule requires !submitting, scheduleValid, await ensureAccepted(config), then nonempty trimmed cron. Sends cron, timezone || undefined, trimmed label || undefined. Webhook sends kind/trimmed label. Success closes/resets; rejection preserves fields; finally clears submitting. Schedule edits clear rejection and are disabled during submit.

Subscribers:760 create_issue only; member query enabled canWrite, independent of picker open. Draft starts from member subscriber IDs; close compares length/membership, resets draft/filter and replaces entire list only when changed. Nonmember subscribers are not preserved in this write. Error toast; no local retry.

Properties:858 project detail enabled Boolean(projectId), independent of canWrite; updates status, assignee pair, execution_mode, project_id with equality guards except status. Query loading/unavailable project fallbacks. Actor name hooks also register directory queries (reuse core-query evidence).

Update hook: optimistic list/detail fields exclude subscribers; snapshots separate from source hashes. Cancel list query without awaiting; snapshot list/detail, restore existing snapshots on error; invalidate detail and list on settled. Subscriber authoritative payload arrives through invalidation.

Delete hook: await cancel list, snapshot list, remove row/decrement total and remove detail query. Error restores list only, not removed detail. Settled invalidates list. Page success navigates list; error resets deleting and toasts.

Trigger create/delete/rotate invalidate detail on settled with no optimistic patch. Manual trigger invalidates runs/detail on settled. Shared run-now helper distinguishes issue_created/running success, skipped warning and other statuses error; classified dispatch errors or client error fallback.

StopRunButton:166 POST cancellation by taskId without queued options; busy guard, failure resets busy/toast; success stays busy, no local patch/invalidation. Source comment relies on run_done refetch; event delivery is not proven here. Render only canWrite, task_id, no issue_id, running.

Run rows split skipped into collapsible group with no stop permission; issue rows navigate. Synthetic AgentTask is display input, not execution. Transcript content is child-owned. Runs error defaults empty; detail failure without data appears not found; no explicit refresh action in target.

Dynamic resources: webhook URL built from trigger, API base, window origin and passed to WebhookUrlField; not invoked as webhook here. Share URL uses navigation adapter then copyText. ActorAvatar and ReadonlyContent can own dynamic image/link resources; do not infer fixed resource endpoints from URL values. Navigation/clipboard are platform boundaries.

Child boundaries

AutopilotDialog and EditScheduleTriggerDialog/EditWebhookTriggerDialog: creation evidence reused; no child mutation attributed to this file

ScheduleEditor/useScheduleSubmitGate: validation and preview delegated; no child route closure claimed

WebhookDeliveriesSection: receives hasWebhookTrigger; list/detail/replay remain child-owned

TranscriptButton: voice evidence reused; transcript transport remains child-owned

ActorAvatar, AgentPicker, ProjectPicker, ReadonlyContent, command context and ObjectPage: supporting boundaries; no whole-module closure claimed

Exact inventory tuples and source/evidence SHA-256 values are recorded in the companion JSON. Mutation cache snapshots are recorded separately. Existing query, voice, editor, creation and avatar evidence is reused without expanding its scope.

Root correction: useScheduleSubmitGate is an own executed hook, not only a child boundary. findScheduleRejection fetches cronPreviewOptions -> client:5393 GET cron-preview (30s stale, retry false). Only explicit ApiError 400 rejects; transport/other failures permit attempting the write. Root read hook/query/client and added edge. Bounded target scope accepted; no runtime/scheduler support claim.
