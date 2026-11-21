# Shared chat controller transport audit

Root independent review pending. Whole controller source (915 lines) closes the invoked controller boundary for page/window review; this is not backend or global coverage.

Whole controller lines 1-915 audited. No direct user fetch: user is an auth-store selector. Agents, members, sessions(status=all), projects(include_archived) are mounted without controller enabled/visibility gates; project select extracts data.projects. Duplicate availability observers use the same keys. Agent list polls every 30 seconds only with a nonarchived online/unstable row.

Messages page requires activeSessionId AND isActive; limit 50, reverse pages, cursor next only when has_more; initial page 404 fallback is flat messages. Pending requires session only, independent of visibility. Both staleTime Infinity. fetchOlderMessages is returned to callers, not executed at mount.

Availability hook uses isFetched (including errors), whereas agentsSettled requires BOTH isSuccess; user/member role and archive/permission filter resolve available agents. Session agent resolves from full list including archived before selected preference and first available. URL-agent intent is supplied by page: controller exposes agentsSettled and selection callbacks, performs no URL parsing/navigation.

Presence executes agents/runtimes/task-snapshot observers gated by workspace, even absent agent; errors degrade to empty data. Snapshot stale 30 seconds and focus refetch; 30-second presence interval is local recomputation and cleans up. Project-context support executes workspace-gated runtime list independent of agent; missing bound runtime returns unknown, version support is advisory, not send gate.

Auto-read requires active surface, app foreground, session and unread. Zero-delay timer rechecks live active session and cleans up; read mutation cancels/snapshots session list, optimistically clears unread, rolls back on error, invalidates on settle. Foreground uses DOM listeners or native focus promise/subscription, disposed on cleanup; no HTTP.

ensureSession trusts active ID until list succeeds or while pending task cached; otherwise creates lazily with active agent/project. Shared promise prevents concurrent creates, finally resets. Creation invalidates sessions on either settlement. Dangling session and stale project cleanup require current workspace identity; query errors do not authorize cleanup.

Send rejects missing/archived/access-revoked agent, unsupported follow-up queue and unbound runtime. No additional isActive/foreground/archive-session/project-version guard in callback. Ensure/create and send errors return false and preserve input; reason codes choose toast. Queue option passed only when requested. Accepted response primes message caches then pending unless steered, invalidates pending, and cancels/refetches sessions after commit if ID changed. Live active-session equality controls publishing and editor clearing; commitInput receives extra session draft key. Deferred stop cancels accepted task and returns false. Attachment binding mismatch toasts; ordinary completion invalidates flat/page messages and returns true.

Stop without pending/session is no-op; non-server task ID sets deferred-stop ref; real ID invokes shared cancel. Queue/cancel/archive settlement and finite aggregate refetch are inherited from queue/archive proof, including derived edit 409 retry and pre-try cancelQueries rejection caveat.

Project change equal-ID no-op; unloaded active row waits. Detach PATCHes project_id=null optimistically with snapshot rollback and sessions settlement invalidation. Different nonnull project starts local fresh chat bound to old session agent; no active session only updates persisted preference. Deleted project normalized only after list success. isProjectUpdating includes active row not yet loaded.

New/start/agent/session actions are local store selection and focus nonce changes, not create calls. Agent switch preserves explicit unsent project but clears historical context; same active agent no-op. Session selection synchronizes cross-agent preference. Conversation starter increments local request ID and focus nonce; applied clears request.

Archive advance only affects active target: sorted nonarchived history next, previous, null; handleSelectSession preserves cross-agent preference. Archive PATCH is separate; selection is not rolled back on mutation error.

Restore executes only session plus active/foreground; local queue has priority, off-session offer released, disabled offer released without consume. Applied durable IDs recorded before consume, in-flight Set prevents duplicate reconcile; successful consume forgets ledger, settle releases Set. Failed consume retained for future reconciliation. Local applied restore dequeues persisted session queue. Cache/store helpers reuse scoped proofs, do not introduce HTTP.

No arbitrary rendered descendants, third-party query internals, global realtime subscriptions or backend implementation claims are included. Invalidation is a possible active-observer refetch, not an unconditional request.

Exact current frontend-calls tuples, source hashes, separate source snapshot and bounded refetch union are in the companion JSON. Accepted scoped proofs are referenced with hashes rather than expanding descendants. No runtime or tests were run.
