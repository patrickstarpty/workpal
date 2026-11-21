# Chat and inbox static transport audit

Bounded static frontend audit; no runtime or backend support claim; root review required.

All four target executable bodies were inspected in bounded source ranges. Whole-source flags remain false because the precise supporting edges below are intentionally unresolved. Standard TanStack, React and Zustand semantics end tracing; observer enumeration and node_modules are excluded.

## Request edges

| Source | API method | Existing inventory |
|---|---|---|
| packages/core/chat/queries.ts:83 | listChatSessions | client:4106 GET /api/chat/sessions${query} |
| packages/core/chat/queries.ts:131 | listChatPinnedAgents | client:4186 GET /api/chat/pinned-agents |
| packages/core/chat/queries.ts:139 | getChatSession | client:4115 GET /api/chat/sessions/${id} |
| packages/core/chat/queries.ts:148 | listChatMessages | client:4201 GET /api/chat/sessions/${sessionId}/messages |
| packages/core/chat/queries.ts:158 | listChatMessagesPage | client:4218 GET /api/chat/sessions/${sessionId}/messages/page?${query.toString()}; client:4201 GET /api/chat/sessions/${sessionId}/messages |
| packages/core/chat/queries.ts:175 | getPendingChatTask | client:4295 GET /api/chat/sessions/${sessionId}/pending-task |
| packages/core/chat/queries.ts:195 | listChatDraftRestores | client:4331 GET /api/chat/sessions/${sessionId}/draft-restores |
| packages/core/chat/queries.ts:205 | listChatSessionWakeups | client:4354 GET /api/chat/sessions/${sessionId}/wakeups |
| packages/core/chat/queries.ts:214 | listMyChatWakeups | client:4379 GET /api/chat/my-wakeups |
| packages/core/chat/queries.ts:228 | listTaskMessages | client:3095 GET /api/tasks/${taskId}/messages |
| packages/core/chat/queries.ts:364 | listPendingChatTasks | client:4390 GET /api/chat/pending-tasks |
| packages/core/chat/queries.ts:379 | hasAnyPendingChatTasks | client:4394 GET /api/chat/pending-tasks/has-any |
| packages/core/inbox/queries.ts:27 | listInbox | client:3196 GET /api/inbox |
| packages/core/inbox/queries.ts:38 | listSnoozedInbox | client:3255 GET /api/inbox/snoozed |
| packages/core/inbox/queries.ts:71 | listArchivedInboxPage | client:3232 GET /api/inbox/archived/page?${params} |
| packages/core/inbox/queries.ts:83 | listArchivedInboxPage | client:3232 GET /api/inbox/archived/page?${params} |
| packages/core/inbox/queries.ts:99 | getArchivedInboxFacets | client:3241 GET /api/inbox/archived/facets?${this.archivedInboxParams(filters)} |
| packages/core/inbox/queries.ts:136 | getInboxUnreadSummary | client:3278 GET /api/inbox/unread-summary |

listChatMessagesPage also falls back to listChatMessages on its compatibility error branch. Draft restores and wakeups handle 404 locally. These are frontend behaviors, not backend availability assertions.

## Invalidation closure

- **onInboxInvalidate / onInboxNew**: inboxKeys.all(wsId) prefix reaches listInbox, listArchivedInboxPage (pages and lookup), getArchivedInboxFacets, listSnoozedInbox; excludes account unread summary.
- **onInboxSummaryInvalidate**: getInboxUnreadSummary only
- **onInboxIssueDeleted**: local row prune + selection forgetRows; summary, pages, lookup, facets refresh
- **onInboxIssuesDeleted**: empty ids no-op; cancel all lists; prune local rows and selection; summary/pages/lookup/facets; if interrupted, full workspace invalidation
- **refreshArchivedInboxMatches**: pages/lookup/facets mark stale without refetch then cancel/invalidate each
- **patchInboxIssueProjection / patchInboxIssueStatus / onInboxIssueStatusChanged**: local main/archive cache row projection; preserve stale mark with exact refetchType none; no immediate request
- **cancelInboxLists / isInboxListRequestInFlight**: inspect fetch status and cancel; no new request

## Local effects and boundaries

- Chat quick-actions pending/failure queryFns return null with enabled false; no transport.
- Task message structuralSharing unions by seq; merge/union helpers and timeline-presence lookup are cache/local only.
- Inbox placeholder/pagination/select/enabled callbacks transform data or gate standard query behavior.
- Workspace rehydration registry invokes the store callback on queued workspace changes; cleanup registry stores reset callbacks which only set store slices.
- Selection forgetRows removes held/left rows through Zustand only; no notification delivery API.

## Open edges

- packages/core/chat/store.ts:420: ChatStoreOptions.storage: StorageAdapter getItem/setItem/removeItem are injected synchronous calls; concrete adapter not audited here.
- packages/core/inbox/queries.ts:3: archivedInboxQuery, groupInboxItemsByIssue, isInboxItemSnoozed supporting implementations not semantically closed in this batch.
- packages/core/chat/store.ts:14: createLogger implementation not traced; logger methods are application callbacks, not proven transport-free here.
- packages/core/inbox/queries.ts:113: mapArchivedInboxCache and patchArchivedInboxCaches invoke caller-supplied patch(items): InboxItem[]; arbitrary caller behavior excluded, exact injection contract retained.

## Per-export evidence and hashes

### packages/core/chat/queries.ts

SHA-256 `7cf8eac14be017406936c6b0eb46dba319db13095a41077c5ff6527cc9c62f3d`; whole_source: false.

- packages/core/chat/queries.ts:24 `QUICK_ACTIONS_PENDING_TIMEOUT_MS`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:31 `chatKeys`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:76 `isTaskMessageTaskId`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:80 `chatSessionsOptions`: Query callback calls listChatSessions. See request edges.
- packages/core/chat/queries.ts:101 `sortChatSessions`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:124 `countUnreadChatSessions`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:128 `chatPinnedAgentsOptions`: Query callback calls listChatPinnedAgents. See request edges.
- packages/core/chat/queries.ts:136 `chatSessionOptions`: Query callback calls getChatSession. See request edges.
- packages/core/chat/queries.ts:145 `chatMessagesOptions`: Query callback calls listChatMessages. See request edges.
- packages/core/chat/queries.ts:154 `chatMessagesPageOptions`: Query callback calls listChatMessagesPage. See request edges.
- packages/core/chat/queries.ts:172 `pendingChatTaskOptions`: Query callback calls getPendingChatTask. See request edges.
- packages/core/chat/queries.ts:192 `chatDraftRestoresOptions`: Query callback calls listChatDraftRestores. See request edges.
- packages/core/chat/queries.ts:202 `chatWakeupsOptions`: Query callback calls listChatSessionWakeups. See request edges.
- packages/core/chat/queries.ts:211 `myChatWakeupsOptions`: Query callback calls listMyChatWakeups. See request edges.
- packages/core/chat/queries.ts:225 `taskMessagesOptions`: Query callback calls listTaskMessages. See request edges.
- packages/core/chat/queries.ts:244 `useTaskMessages`: useQuery(taskMessagesOptions); mount/focus always refetch; effect refetches when enabled becomes true or live becomes false, guarded by UUID; same listTaskMessages request.
- packages/core/chat/queries.ts:275 `mergeTaskMessagesBySeq`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:306 `unionTaskMessagesBySeq`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:349 `isTaskMessageTimelineHeld`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:361 `pendingChatTasksOptions`: Query callback calls listPendingChatTasks. See request edges.
- packages/core/chat/queries.ts:376 `hasPendingChatTasksOptions`: Query callback calls hasAnyPendingChatTasks. See request edges.
- packages/core/chat/queries.ts:390 `chatQuickActionsPendingOptions`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/queries.ts:404 `chatQuickActionsFailureOptions`: Local keys, types, derivation or cache transformation; no direct API request.
### packages/core/chat/store.ts

SHA-256 `ce5d288e91bbf6783e19280a9380f9055694fbbb45bdd24b724bae8c9a363b9f`; whole_source: false.

- packages/core/chat/store.ts:53 `DRAFT_NEW_SESSION`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:320 `CHAT_MIN_W`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:321 `CHAT_MIN_H`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:322 `CHAT_DEFAULT_W`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:323 `CHAT_DEFAULT_H`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:330 `ChatTimelineItem`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:345 `PendingSendRestore`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:353 `ChatState`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:425 `ChatStoreOptions`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/chat/store.ts:429 `createChatStore`: All actions persist injected storage and update Zustand state; draft upload actions only record supplied metadata. Four cleanup callbacks reset slices; workspace callback rereads storage and resets workspace state. No upload/send/consume API call.
### packages/core/inbox/queries.ts

SHA-256 `4612025ba86f4e32cb272acb366861d824988ba6fa7648df230e425072a4454d`; whole_source: false.

- packages/core/inbox/queries.ts:11 `inboxKeys`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:24 `inboxListOptions`: Query callback calls listInbox. See request edges.
- packages/core/inbox/queries.ts:35 `snoozedInboxOptions`: Query callback calls listSnoozedInbox. See request edges.
- packages/core/inbox/queries.ts:43 `findSnoozedInboxIssue`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:67 `archivedInboxPagesOptions`: Query callback calls listArchivedInboxPage. See request edges.
- packages/core/inbox/queries.ts:79 `archivedInboxLookupOptions`: Query callback calls listArchivedInboxPage. See request edges.
- packages/core/inbox/queries.ts:96 `archivedInboxFacetsOptions`: Query callback calls getArchivedInboxFacets. See request edges.
- packages/core/inbox/queries.ts:106 `ArchivedInboxCache`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:108 `mapArchivedInboxCache`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:114 `patchArchivedInboxCaches`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:133 `inboxUnreadSummaryOptions`: Query callback calls getInboxUnreadSummary. See request edges.
- packages/core/inbox/queries.ts:153 `inboxUnreadSummaryEnabled`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:166 `hasOtherWorkspaceUnread`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:179 `unreadWorkspaceIds`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:188 `unreadCountForWorkspace`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:210 `useInboxUnreadCount`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:228 `deduplicateInboxItems`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/queries.ts:241 `deduplicateArchivedInboxItems`: Local keys, types, derivation or cache transformation; no direct API request.
### packages/core/inbox/ws-updaters.ts

SHA-256 `710af5cdd2f59c397d6f9a1b16146b923d08f70c0f619181074503db0f81c175`; whole_source: false.

- packages/core/inbox/ws-updaters.ts:34 `onInboxNew`: See invalidation closure table; cancellation then invalidation may invoke existing query factories under standard TanStack semantics.
- packages/core/inbox/ws-updaters.ts:71 `InboxIssueProjectionPatch`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/ws-updaters.ts:81 `patchInboxIssueProjection`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/ws-updaters.ts:127 `patchInboxIssueStatus`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/ws-updaters.ts:136 `onInboxIssueStatusChanged`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/ws-updaters.ts:157 `onInboxIssueDeleted`: See invalidation closure table; cancellation then invalidation may invoke existing query factories under standard TanStack semantics.
- packages/core/inbox/ws-updaters.ts:184 `onInboxIssuesDeleted`: See invalidation closure table; cancellation then invalidation may invoke existing query factories under standard TanStack semantics.
- packages/core/inbox/ws-updaters.ts:212 `refreshArchivedInboxMatches`: See invalidation closure table; cancellation then invalidation may invoke existing query factories under standard TanStack semantics.
- packages/core/inbox/ws-updaters.ts:219 `isInboxListRequestInFlight`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/ws-updaters.ts:240 `cancelInboxLists`: Local keys, types, derivation or cache transformation; no direct API request.
- packages/core/inbox/ws-updaters.ts:257 `onInboxInvalidate`: See invalidation closure table; cancellation then invalidation may invoke existing query factories under standard TanStack semantics.
- packages/core/inbox/ws-updaters.ts:268 `onInboxSummaryInvalidate`: See invalidation closure table; cancellation then invalidation may invoke existing query factories under standard TanStack semantics.
### packages/core/api/client.ts

SHA-256 `779bb65b5b7ead815836f7c704ec3c370bafae203e4f92119fadce93e982a4d7`; whole_source: false.

### packages/core/platform/workspace-storage.ts

SHA-256 `86f0f2ab838823d3c5dd10de0126c5095e815cb8c34a000e0ba04b8d015cf5bb`; whole_source: false.

### packages/core/drafts/cleanup-registry.ts

SHA-256 `1d97d67851082ea0459f61276d19bb149a79253386e755dbf456b6af40875e5b`; whole_source: false.

### packages/core/drafts/draft-upload.ts

SHA-256 `2eb1bc0101d2757978ce69da585bfc058372766e5e81c718d13a54ef8a0fd11d`; whole_source: false.

### packages/core/inbox/selection-store.ts

SHA-256 `daafdb4b3fa2a194290e4a750c72dc97c5afa3e8ae7d25631b1b727bad7fecaf`; whole_source: false.


## Parent closure review

Parent closed remaining bounded edges: main.tsx:49 omits storage; CoreProvider defaults to defaultStorage and passes it to createChatStore. defaultStorage is localStorage. logger.ts complete body is timestamp formatting plus console methods. archivedInboxQuery uses local sorted strings, dimension lookup and local date helpers; groupInboxItemsByIssue/groupInboxRows/withCommentAnchor use arrays/maps and snooze/date ordering. All production map/patchArchivedInboxCache callbacks found in inbox mutations and ws-updaters are local find/map/projection transformations; mutation API dispatch is outside those patch callbacks. Existing listed invalidation/refetch union retained. Generic injected implementations beyond the active-web adapter remain an explicit interface contract, not an inferred request.

Four target whole_source flags are now true; earlier open-edge text is historical. Supporting modules remain partial as whole files. This is bounded static transport closure, not implementation or runtime verification.
