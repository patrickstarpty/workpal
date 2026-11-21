# Inline run transport audit

All 396 target lines inspected in chunks 1–110, 111–220, 221–330, 331–396. Captured code is separate; supporting whole_source flags remain bounded.

1–40 imports/thinkingPreview: formatting and redaction.

42–63 disclosure, keyboard focus origin, log state and placement gate: local; placement can skip mounting.

65–119 own hooks: actor directories, messages and labels; timeline observer enabled:false selects cached delivered steers.

120–180 active elapsed timer and summaries local; full log uses supplied items, error refetch; stop confirmation invokes cancel(task.id).

181–260 identity/avatar and status UI; retry only failed/cancelled and (!hasReply || replacesFailureNotice), pending/success disabled; ReadonlyContent output; expanded error refetch, local row limit.

261–329 receipt filtering by task and delivered status, timestamp sorting/interleaving local; InlineSteer repeats actor hook.

330–396 recursive row disclosure; StepBody only when open; indicators/summary local.

Messages target:108 → chat/queries.ts:244: UUID task id AND loadTranscript (running OR inline-expanded OR fullLogOpen). active is live-transition input, not enabled. Infinity staleTime, always mount/focus refetch; enabled transition and live→ended refetch(cancelRefetch:false); manual error refetch same endpoint; seq-union sharing; no hook polling/socket.

Labels target:110 → use-trace-issue-labels.ts:9: current UUID plus tool_use input.issue_id and workpal issue get/update/comment list/add positional UUIDs in command/cmd; lowercase dedup; text parsing only. Per-id issueDetailOptions: GET encoded id; enabled loadTranscript && !!wsId; staleTime 60000; retry:false.

Actor target:80 and InlineSteer: member and include_archived=true agent directory queries no local enabled gate; agents poll 30000 only if nonarchived online/unstable present. Squads enabled !!wsId. Plugins feature flag && nonempty wsId. Duplicate observers share keys.

Cancel target:161 → mutations:1281; retry target:228 → mutations:1301. Both success invalidate only [issues,tasks,issueId]. Retry body {task_id: task.id}. Failure only toast; no optimistic writes. No timeline/messages invalidation.

Invalidation prefix may refetch external enabled task-run observers including subtree and view=timeline; target owns none. Disabled timeline observer does not fetch.

Own possible union: client:3095, client:1612, client:3765, client:2066, client:5203, client:3425, client:3133, client:3144. Timeline is disabled; task-run requests are conditional external invalidation candidates. All ten inventory tuples checked against current client expressions; multiline fetch anchors resolved to expression lines.

Remaining edges:

- ActorAvatar retains avatar-foreground hover/image resource boundaries.
- ReadonlyContent, StepBody and AgentTranscriptDialog bounded via editor/editor-preview and agent-settings transcript proof. Dynamic rich content/media/links, context-receipt/run details and host callbacks remain descendant boundaries; transcript supporting source whole_source:false is not upgraded.
- Local timeline/steps stop at existing agent-settings inspected helper contracts, no recursive import closure.
- External task-prefix observer population, global defaults and realtime synchronization remain outside single-source scope.

Prior partial action-card audit unchanged. Static evidence only; no backend/global support claim. Child self-check completed; independent root review recorded below.

Root accepted bounded target scope after independent checks of messages hook, trace label query and cancel/retry mutation bodies plus hash/tuple validation. External observer and descendant limits retained.
