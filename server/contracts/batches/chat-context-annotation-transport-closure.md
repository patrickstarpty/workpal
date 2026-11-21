# Chat context and annotation bounded closure

- packages/views/chat/components/use-chat-context-items.ts:69-100: route parser decodes issue/project IDs or inbox issue search parameter; malformed percent encoding can throw. useNavigation reads context and throws without provider (packages/views/navigation/context.tsx:77). No push/replace invoked. Current detail queries enabled only by route type; no workspace/nonempty-ID or visibility gate.

- packages/views/chat/components/use-chat-context-items.ts:101-125: at most eight recent entries use detail factories with staleTime 30000 and no enabled override. No mutation, invalidation or explicit refetch. Current item deduplicates recent by type:id. Query errors are not surfaced here; missing recent data uses stored label/status metadata.

- packages/core/issues/queries.ts:507-512 and packages/core/projects/queries.ts:29-34: workspace-partitioned detail keys, queryFn calls getIssue/getProject; no signal consumed, no factory enabled gate. API issue malformed payload throws (client.ts:1611-1624); project malformed payload uses EMPTY_PROJECT (client.ts:4523-4526). Requests reject through query state.

- packages/core/chat/recent-context-store.ts:36-115: persisted workpal_recent_contexts byWorkspace; selector returns empty for absent workspace. recordVisit deduplicates, timestamps, caps 20 entries and 50 workspaces; forget/prune local only. This hook only reads. defaultStorage (platform/storage.ts:4-17) accesses localStorage, SSR reads null/writes no-op; storage exceptions are not caught in adapter.

- packages/views/chat/components/use-chat-annotations.ts:46-76: messages query enabled by nonempty session only, independently of annotation enabled. Sources are nonfailed assistant non-no_response nonblank persisted messages; draftKey chat:session. Annotation enabled additionally requires session. chat/queries.ts:154-165 uses Infinity staleTime, limit 50 and cursor pagination, no signal forwarding.

- packages/views/chat/components/use-chat-annotations.ts:32-40,78-121: scroll edit may fetchNextPage(cancelRefetch:false) repeatedly until found/exhausted/page error. No mutation/invalidation. Missing source or 30-frame timeout toasts. New attempts/draft-key cleanup increment attempt and cancel RAF; stale promise continuation suppressed. Network is not aborted; pagination loop itself has no attempt check; .then has no rejection catch.

- packages/views/issues/components/use-comment-annotations.tsx:75-142: selection gated by enabled/card/not busy; draftKey/enabled reset editor. Pointer/Escape/focus dismiss with IME/overlay ownership guards; focus microtask rechecks ownership. Document listeners removed on effect cleanup.

- packages/views/issues/components/use-comment-annotations.tsx:149-210: local DOM quote anchoring; MutationObserver updates content ranges, disconnects on cleanup; CSS highlights deleted. edit scrolls locally. comment-annotation-selection.ts:9-75 indexes visible text and creates DOM ranges using pure locateReplyAnnotation; no transport.

- packages/views/issues/components/use-comment-annotations.tsx:213-332: add validates source/quote and duplicate; confirm requires nonblank note, writes add/updateAnnotation; remove writes local store. Busy blocks edits/dismissal. Count 20/quote 4000 errors are local; pending highlight removed on cleanup. Composer receives issueId undefined in chat and optional host controls, not a newly asserted mutation endpoint.

- packages/core/issues/stores/comment-draft-store.ts:112-167,245-319: getAnnotations stable empty; add validates key/note/quote, deduplicates and caps; update blank removes; remove preserves other draft content/uploads, deletes empty drafts. writeDraft timestamps meaningful changes. Persist workpal_comment_drafts:<slug>; merge empty namespace clears drafts; hydrate normalizes and prunes 30-day stale drafts. Registers workspace rehydration and local cleanup reset; no HTTP.

- packages/core/platform/workspace-storage.ts:34-63,109-121: workspace switch coalesces subscriber/rehydration microtasks; storage resolves slug at call time, absent slug returns null/drops writes. Registration is module lifetime, no unregister exposed. No hook-induced network cleanup.

- packages/core/api/client.ts:4207-4243: messages page sends limit and optional before_created_at/before_id; malformed page fallback empty terminal page. Initial cursorless ApiError 404 falls back to listChatMessages; cursor 404 and other errors rethrow. No AbortSignal supplied by these factories.

Reused proofs and exact copied inventory records, source SHA-256 values and validation inputs are recorded in the companion JSON. All recorded reused file hashes matched. No whole chat page/window/controller closure is claimed.

External boundary: third-party scheduling/persistence/query internals, configured server/auth, and caller-defined send controls; rendered editor/composer paths reuse existing proofs. Queue/archive excluded.
