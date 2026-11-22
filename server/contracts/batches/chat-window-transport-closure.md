# Chat window bounded transport audit

81-110: controller isActive=isOpen; quick pending cache observer, timeout, failure toast and wakeups called regardless of isOpen; annotations gate excludes archived/revoked/unbound/noAgent but does not include isOpen.

130-160: minimize setOpen(false); close also dismisses current session chip using chatActivity; archive advances selection then archiveSession. Resize hook supplies expand/drag and bounds; isVisible=isOpen && (isExpanded || boundsReady) && contentReady.

161-257: mobile/keyboard/anchor geometry and pointerEvents gate; inert and aria-hidden depend on isOpen, opacity on isVisible. Desktop resize handles invoke startDrag; desktop expand invokes toggleExpand.

258-400: new/select/archive callbacks delegated; messages mounted only isOpen; quick actions disabled for pending task or archived/revoked/unbound/noAgent; prompt delegates handleSend. Banner priority noAgent, revoked, archived, runtime, offline.

401-462: requests/wakeup/queue remain mounted; queue send-now disabled only revoked here. Input hidden=!isOpen; send/stop/restore/starter/queue callbacks delegated. Project props forward controller activeProjectId, handleProjectChange and updating state; input proof supplies submit/project gates.

481-613: agent filter local; pick calls onSelect then closes picker; runtime-unbound item disabled. No active agent renders text.

641-720: history excludes archived; aggregate pending query has no window visibility enabled override. Completion flash only disappeared tasks with unread session; timers cleared on unmount.

737-800: rename trims, closes editor, skips blank/unchanged then mutate title. History stop optimistically removes task, empties pending cache, invalidates messages; direct cancelTaskById; restore_to_input removes message cache; failure logged; finally invalidates pending caches and clears confirmation.

801-1059: running rows offer stop, otherwise rename/archive; confirmation blocks row selection; keyboard uses handleRowActivationKey; stopping task disables confirmation buttons; history selection closes popover.

Resize: parent ResizeObserver bounds, local pointer listeners and store size/expand setters; pointerup removes listeners. Viewport: resize/scroll listeners, 100px keyboard threshold, zoom exclusion and cleanup. Anchor: open-gated DOM measurements, click RAF and container/bar observers, cleanup; width clamps during drag. No direct HTTP in these hooks; store implementations remain separate.

Timeout: absolute expires_at timer, message-scoped cache clear, cleanup; no HTTP.

Context items: route-selected issue/project detail observers plus at most eight recent detail queries (30s staleTime); current duplicate filtered; no isOpen gate.

Annotations: message-page observer enabled by session ID independently of annotation enabled flag; assistant nonfailure nonempty sources; older-page fetchNextPage loop joins active fetch, stops on error; attempt nonce and 30 RAF retries prevent stale edit; useCommentAnnotations is an invoked dependency still open.

Wakeups: session-ID-enabled query, empty fallback, no isOpen gate. Aggregate pending list: workspace header, GET /api/chat/pending-tasks, Infinity staleTime, no enabled override.

Rename/project mutations: cancel session queries, snapshot cache, optimistic title/project patch, restore snapshot on error, invalidate on settled. Project no-op if unchanged; missing current session awaits; null detaches current via mutation; nonnull starts fresh draft retaining agent; no active session sets draft project; focus requested after change.

New clears project/session and focuses; select-agent no-ops for same active agent, otherwise preserves only unsent draft project, clears session and focuses. Select-session switches agent when needed then active ID. Archive advances only active selection to next/previous nonarchived sorted session, then archive mutation.

Exact remaining invoked edges:

- useChatContextItems: issueDetailOptions/projectDetailOptions adapter and invoked navigation/recent-context store implementations require exact supporting proof.
- useChatAnnotations: invoked useCommentAnnotations and comment-draft store internals require bounded closure; page transport inventory reused above.
- Controller queue callbacks delegate to queue hook: edit/remove/clear/send-now concrete branch and cache/error closure still requires existing proof reconciliation; archive setArchived lifecycle likewise remains open.
- Store implementations for setChatSize/setExpanded/setOpen/dismissChatFromBar/setActiveSession and shared fetch/cache helper internals remain unproven here.

Arbitrary descendant trees excluded: ChatWindowMessages, ChatAppRequests, ChatWakeupStrip rendering/actions, ChatQueue rendering, banners, avatar hover cards, picker/history primitives.

Static source inspection and SHA-256 validation only; snapshot, prior reused proof and root helper hashes match. No application/runtime, data, network, model, integration or backend claim.

Root accepted chat-queue-archive-transport-closure.json after independent hook read and hash/tuple verification. This closes the previously listed queue/archive branch gap. Context/annotation support remains pending. Root also read store setOpen, setActiveSession, dismissChatFromBar, setChatSize and setExpanded: injected StorageAdapter persistence plus local state; no direct HTTP. Native/custom adapters remain explicit host boundaries. No whole store or controller claim.

Root accepted chat-context-annotation-transport-closure.json after source/hash/tuple review. This supersedes the context and annotation helper gaps above. Annotation disabling does not disable the session message query; stale edit continuation is ignored but pagination requests are not aborted. Full invoked controller closure is still pending, so host ledger status is unchanged.

Root accepted bounded host target after controller proof integration, source hash checks, specific callback review and exact host adapter tuple normalization. Historical invoked-hook gaps are closed by the attached proofs. Descendant rendering, native host adapters, destination loaders and global runtime/backend coverage remain excluded. No whole supporting-module promotion.
