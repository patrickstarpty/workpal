# Bounded queue/archive transport closure

Static frontend evidence for root review. Only use-chat-task-actions.ts is fully audited; snapshots are separate from audit scope. No whole controller/page/window or backend/runtime claim.

Controller:187 selects activeSessionId from chat store; 247-255 supplies that ID and enqueueLocalRestore from foreground/isActive-gated draft restore to useChatTaskActions. Queue callbacks themselves gate only on session ID, not foreground.

Cancel: cancel pending query and snapshot before optimistic remove. Explicit edit/remove carry queue_action plus expected_status=queued and chat_session_id. Derived edit applies only restore requested, matching queued head, supports_queue=true. Only derived edit retries ApiError 409 without queue options; explicit edit/remove do not retry.

Cancel success removes returned message from both message caches. Local restore requires restore_to_input, no queuedAction, requested restore and matching session; explicit edit instead invalidates durable draft-restores. Failure restores pending snapshot and returns null. Both paths invalidate message caches; finally invalidates pending, edit draft-restores and workspace aggregate when wsId exists. Pre-try cancelQueries rejection bypasses this settlement.

Edit/remove return without session; call cancel with restore true/edit or false/remove; null result produces failure toast.

Clear awaits DELETE before cache changes; removes message IDs from cached queued_tasks and reduces removePendingChatTask over queue. Failure logs/toasts, no optimistic rollback needed. Finally invalidates pending, both messages and workspace aggregate. cancelQueries precedes try.

Send-now cancels pending query, snapshots and optimistically moves selected queued task first. POST response must match task_id. Only before successful prioritize does failure restore snapshot. Successful prioritize optionally cancels active_task_id with restore requested; failure stopping it preserves prioritized state. ApiError 409 selects steer-unavailable toast; finally invalidates pending. Nested cancel supplies its own settlement.

Pending helper remove: absent head returns empty; nonhead filters queue; head promotes first deduplicated remaining queue task preserving supports_queue. Prioritize returns empty without head, unchanged if task absent, otherwise selected queue entry first; no transport.

Local restore callback 169-175 invokes enqueuePendingSendRestore. Store 580-592 rejects missing session/id and duplicate session-local id, appends, persists then sets state. writePendingSendRestores 233-244 prunes empty arrays, removes empty storage key else JSON serializes; wsKey 432-435 adds current slug. No HTTP in these actions. Composer application/dequeue and durable restore reconciliation reuse chat-input proof.

Archive controller 845-848 invokes mutate archived=true. Mutation 406-450: PATCH JSON archived; cancel workspace sessions query, snapshot, optimistic status/updated_at patch sorted by sortChatSessions; archive zeroes unread_count/has_unread; unarchive does not restore unread. Error restores truthy previous sessions; settled invalidates sessions. No store action in mutation; selection advancement is separate and not rolled back by mutation.

Remove-message wrapper 443-453 filters flat messages then invokes page-cache removal; existing cache/query evidence reused for page bookkeeping, keys and refetch adapters. No new transport introduced by local cache/store operations.

Exact inventory tuples:

- client:4178: PATCH `/api/chat/sessions/${id}/archive` → `/api/chat/sessions/{sessionId}/archive`
- client:4305: POST `/api/chat/sessions/${sessionId}/queued-tasks/${taskId}/prioritize` → `/api/chat/sessions/{sessionId}/queued-tasks/{taskId}/prioritize`
- client:4318: DELETE `/api/chat/sessions/${sessionId}/queued-tasks` → `/api/chat/sessions/{sessionId}/queued-tasks`
- client:4417: POST `/api/tasks/${taskId}/cancel${query}` → `/api/tasks/{taskId}/cancel`

Reuses hashed chat input, draft, cache and query evidence recorded in JSON. Inventory and shared ledgers remain untouched. Root review remains required.
