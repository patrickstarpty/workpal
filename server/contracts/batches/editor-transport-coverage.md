# Editor transport coverage

Finite semantic ledger for exactly six sources. Global frontend source coverage remains **false**. No runtime requests or model calls were made.

## packages/views/editor/attachment.tsx

- `packages/views/editor/attachment.tsx:325`: indirect authenticated API → GET /api/attachments/{id}; GET /api/attachments/{id}/download. Inventory: client:4438, client:4508. useResignedInlineMedia: metadata only for auth-gated cross-origin/API-base URLs; bytes only image fallback without signed storage URL
- `packages/views/editor/attachment.tsx:382`: indirect metadata + native download → GET /api/attachments/{id}; attachment_download_url or proxy signed-download or /api/attachments/{id}/download?workspace_slug=.... Inventory: client:4438. useDownloadAttachment default workspace mode; browser anchor or injected desktopAPI.downloadURL
- `packages/views/editor/attachment.tsx:384`: resolver or external navigation → matched attachment metadata/download as above; unmatched input URL via desktopAPI.openExternal or window.open. Inventory: client:4438. attachment-download-context resolves records locally before download; absent provider opens supplied URL
- `packages/views/editor/attachment.tsx:589`: native img src → GET /api/attachments/{id}/download; GET /api/attachments/{id}/signed-download?exp=...&sig=...; server-provided signed HTTP(S) storage/CDN URL; input HTTP(S)/relative URL; blob: or data: (local bytes). Inventory: proposed record in JSON. src from :423; selection :247-258 prefers signed download, legacy local API, unsigned configured CDN, markdown_url, storage, fallback; :219 absolutizes relative paths
- `packages/views/editor/attachment.tsx:347`: delegated preview → GET /api/attachments/{id}/download; GET /api/attachments/{id}/signed-download?exp=...&sig=...; server-provided signed HTTP(S) storage/CDN URL; input HTTP(S)/relative URL; blob: or data: (local bytes); GET /api/attachments/{id}; GET /api/attachments/{id}/content. Inventory: client:4438, client:4475, client:4508. also :357 and :345 sequence dispatch; modal text query, inline/stream refresh, browser image/video/audio/PDF resources
- Local: packages/views/editor/attachment.tsx:470 — AttachmentCard href is a capability/visibility prop, not a DOM anchor; attachment-card.tsx:170 uses it to compute canPreview and :178 canDownload. Clipboard :484 copies text; normalize/ID helpers only compute strings.

## packages/views/editor/use-editor-upload.ts

- `packages/views/editor/use-editor-upload.ts:31`: injected ApiClient upload → POST baseUrl/api/upload-file. Inventory: client:4078. use-file-upload.ts:76 invokes uploadFile; multipart file plus optional context; cookies and authHeaders; no presign PUT
- Local: packages/views/editor/use-editor-upload.ts:23 — Failure toast/state only outside delegated upload.

## packages/views/editor/paste-as-file.ts

- Local: packages/views/editor/paste-as-file.ts:24 — Only executable export is numeric PASTE_AS_FILE_THRESHOLD=4000; no upload, File creation or transport.

## packages/views/editor/use-composer-submit.ts

- `packages/views/editor/use-composer-submit.ts:161`: injected async callback → caller-defined onSubmit(content). Inventory: proposed record in JSON. No endpoint selected in this source; opaque parameter, exception E1
- Local: packages/views/editor/use-composer-submit.ts:98 — State, markdown normalization, gate check, animation frame and DOM focus are local; onAccepted/normalize/afterAccepted are caller callbacks, not identified API implementations.

## packages/views/editor/preview-sequence-context.tsx

- `packages/views/editor/preview-sequence-context.tsx:308`: delegated preview → GET /api/attachments/{id}/download; GET /api/attachments/{id}/signed-download?exp=...&sig=...; server-provided signed HTTP(S) storage/CDN URL; input HTTP(S)/relative URL; blob: or data: (local bytes); GET /api/attachments/{id}; GET /api/attachments/{id}/content. Inventory: client:4438, client:4475, client:4508. toPreviewSource :136 forwards record or URL; same modal path as attachment
- `packages/views/editor/preview-sequence-context.tsx:367`: indirect image prefetch → GET /api/attachments/{id}/download; GET /api/attachments/{id}/signed-download?exp=...&sig=...; server-provided signed HTTP(S) storage/CDN URL; input HTTP(S)/relative URL; blob: or data: (local bytes); GET /api/attachments/{id}. Inventory: client:4438, client:4508. also :373; PreviewImagePrefetch :410 uses re-sign hook then :420 probe.src; blob fallback may GET download
- Local: packages/views/editor/preview-sequence-context.tsx:214 — Sequence snapshot/index/broken-image tracking and callbacks update local state; imported image-sequence collection parses/matches content, no bytes fetched by collection. describeItem/onOpened/onClosed/locate/overview callbacks are host-defined.

## packages/views/modals/use-issue-create-uploads.ts

- `packages/views/modals/use-issue-create-uploads.ts:109`: coordinated upload → POST baseUrl/api/upload-file. Inventory: client:4078. use-coordinated-uploads.ts:415 injects singleton api; upload-coordinator.ts:78 uploadFile; empty context {} so no issue/comment/chat binding yet
- Local: packages/views/modals/use-issue-create-uploads.ts:49 — Binding mutates draft store, filters/maps attachment records and appends markdown; removal is local draft removal, not DELETE attachment.

## Explicit exceptions

- E1: Injected onSubmit has no implementation in this module; endpoint varies by host. Caller enumeration outside these six sources is not asserted.
- E2: Input/server-returned URLs and host callbacks are runtime values; concrete origins and callback side effects cannot be statically enumerated. Native resource loads may follow server redirects; arbitrary HTML preview subresources are content-defined.

Helper evidence: packages/core/api/client.ts:4078 (multipart upload), :4438 (metadata), :4447 (download metadata for markdown-link resolver), :4475 (text), :4508 (blob); hooks/use-inline-media-url.ts resolves metadata, signed stream URLs and local object URLs; attachment-preview-modal.tsx:420 is detached image prefetch. Object URL creation/revocation manages renderer memory and is not a backend request. API singleton forwards to configured ApiClient; fetchRaw :1071 uses baseUrl + path, auth headers and credentials. Dynamic browser paths require separate inventory records even where the same route is already represented by an API call.

## Parent review
Validated upload wrappers, local paste constant, raw image src and refreshed media/blob paths. Added known native image download/signed-download branches and upload-wrapper source references to frontend-calls.json. Removed proposed CALLBACK pseudo-HTTP record; six useComposerSubmit hosts need tracing. Runtime URL branches remain documented rather than assigned invented routes. Global source coverage remains false.
