# Avatar, foreground and transcript transport coverage

Static coverage only. All six requested target bodies and avatar-crop.ts were read as executable source; standard React/canvas APIs terminate tracing. No backend capability is established. Root review remains pending.

- AvatarCropDialog creates/revokes one object URL per File, resets geometry, blocks confirmation on busy/error/missing crop, encodes a 512px square and hands a File to onCropped. avatar-crop loads that local object URL through Image, rotates into a bounding canvas, crops/resizes and toBlob encodes WebP quality .85 or JPEG with white background. The 1px toDataURL WebP probe returns local data; it performs no backend request. Null contexts, image and encoding failures reject.
- TextAvatarDialog normalizes up to two grapheme clusters, supports IME composition, prevents repeated encoding and hands renderTextAvatar's PNG File to onGenerated. Renderer awaits document.fonts.ready, reads computed font, measures/shrinks/centers text and fills a 256px canvas. Font readiness may depend on browser stylesheet resources; no API is selected. Empty text, context failure or null blob reject. Preview spans and color helpers are local.
- AvatarUploadControl reads first input File, clears input for reselection and rejects non-image MIME. Crop and text paths share uploadAndSave: useFileUpload(singleton api) checks size, multipart uploads without issue/comment/chat context, returns att.url as link, then awaits caller persistence. This is not presigned PUT. Reuse draft-attachment/editor evidence for upload/auth/download mechanics rather than duplicating those audits. No avatar download helper invocation exists here. Preview img loads resolvePublicFileUrl(value); resolver only prefixes API base for slash-leading strings. Emoji selection formats emoji: text and skips upload; clear is caller state, not DELETE. Lazy emoji picker is a module resource, not an API call.
- persistedByCaller returns false only on rejection. Account/workspace inline callbacks catch and toast without rethrow: failed saves can still close the dialog and show upload success. Agent inspector update delegates onUpdate(agent.id,data) to detail handleUpdate -> updateAgent (PUT); it rolls back and rethrows. Squad detail mutateAsync -> updateSquad (PUT). Creation controls stash avatarUrl locally; create-squad handleSubmit sends avatar_url through createSquad; agent configuration draft.avatarUrl reaches buildCreateAgentRequest -> createAgent. Optional squad membership additions are separate submit effects, not avatar uploads. Query/cache updates do not themselves prove requests.
- useAppForeground subscribes/unsubscribes visibilitychange/focus/blur; browser snapshot requires visible and hasFocus; SSR snapshot true. If both native functions exist, native result alone is authoritative, initially false. Subscribe precedes initial query; received events win over initial query, live guard rejects late query after cleanup, rejection leaves false, cleanup unsubscribes. Native implementations remain E1.
- TranscriptButton provided or already loaded items open without fetch. Terminal first click calls listTaskMessages, builds timeline and caches locally; failure opens empty items. Live mode requires valid persisted ID, latches for open session and mounts a disabled query observer. Explicit backfill calls the same GET on mount/task ID/isLive change, merges through cache structuralSharing by sequence; cancellation suppresses cache write but does not abort HTTP. Global navigation only closes. No new WebSocket is created by this button. Parent callbacks control opening/focus; descendant dialog is E3.

## Existing inventory mappings

- uploadFile: client:4078 POST `${this.baseUrl}/api/upload-file` (packages/views/common/avatar-upload-control.tsx:208).
- updateMe: client:1267 PATCH /api/me (packages/views/settings/components/account-tab.tsx:118).
- updateWorkspace: client:3416 PATCH /api/workspaces/${id} (packages/views/settings/components/workspace-tab.tsx:343).
- updateAgent: client:2191 PUT /api/agents/${id} (packages/views/agents/components/agent-detail-page.tsx:271).
- updateSquad: client:5233 PUT /api/squads/${id} (packages/views/squads/components/squad-detail-page.tsx:182).
- createSquad: client:5226 POST /api/squads (packages/views/modals/create-squad.tsx:97).
- createAgent: client:2075 POST /api/agents (packages/views/agents/create/use-create-agent-submit.ts:82).
- listTaskMessages: client:3095 GET /api/tasks/${taskId}/messages (packages/views/common/task-transcript/transcript-button.tsx:152).

## Exact open edges

- E1: window.desktopAPI.getWindowForeground/onWindowForegroundChanged are injected native methods; no implementation found under apps/packages. No HTTP route or backend support inferred.
- E2: img src is resolved raw value: relative API base, absolute remote, data or blob URL. Browser resource request and redirects depend on value; no fixed download endpoint inferred.
- E3: AgentTranscriptDialog downstream rendering/actions and supplied headerSlot remain outside this bounded button audit; no exhaustive descendant transport claim.
- E4: Arbitrary replacement onUploaded/onEmojiSelected/onClear callbacks remain caller-defined; finite production persistence paths listed. Query invalidation fanout not exhaustively enumerated.

No runtime, shared inventory, SQLite, Git or network changes. No children. JSON references existing inventory only; coverage remains bounded and pending root review.
