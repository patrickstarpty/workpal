# Draft and attachment transport coverage

Bounded full-source semantic audit of eleven requested files. Global coverage remains incomplete; source coverage is not backend support. Static possible API union is sufficient.

Reuses transport source ledger, editor transport and composer submit batches; no shared ledger or inventory changed.

## packages/core/drafts/cleanup-registry.ts

Reviewed all 106 lines. Registry registration and key enumeration are local. Workspace cleanup invokes injected StorageAdapter.removeItem; reset aborts coordinator requests before invoking registered in-memory resets. Neither cleanup nor abort deletes server attachments. Adapter/store implementation is a boundary, not an HTTP endpoint.

## packages/core/drafts/draft-upload.ts

Reviewed all 147 lines. Types, uploaded filtering, upload gate predicate and legacy normalization only. attachmentToDraftUpload clears both ephemeral signed URL fields while preserving durable URL/markdown URL; already-shaped uploaded records are accepted after shape checks. Reload drops uploading records because File bytes are not persisted; failed/interrupted legacy records remain. No resume, retry or resource load.

## packages/core/drafts/index.ts

Reviewed all 30 lines. Re-export barrel only. create-draft-store is exported, not invoked here; coordinator and cleanup exports retain the dispositions in this batch. No transport on barrel evaluation established.

## packages/core/drafts/upload-coordinator.ts

Reviewed all 131 lines. Injected api.uploadFile receives File, optional issue/comment/chat context and AbortSignal. Active coordinated caller supplies singleton api, resolving to client:4078 multipart POST. Map owns controller lifetime independently of editor mount. Success invokes onSettled; abort errors suppress settlement; other errors settle failed. Finally removes only matching controller. abortUpload/abortAll cancel locally, no DELETE or server cancellation route. A successful promise resolving after abort is not separately signal-guarded in success branch; caller generation guards matter.

## packages/core/hooks/use-file-upload.ts

Reviewed all 101 lines. Injected ApiClient uploadFile resolves to multipart client:4078 in active editor evidence. Rejects oversized File before call; in-flight counter increments/decrements in finally. uploadWithToast invokes supplied onError then returns null. toUploadResult preserves raw url as link and selects markdown_url, durable attachment-ID download path, then raw url. Computing links loads no bytes; no File is constructed or persisted here.

## packages/core/attachments/deliverables.ts

Reviewed all 167 lines. Pure grouping and lookup: normalize MIME/filename, deduplicate attachment IDs, sort versions by date/id, newest-first deliverables. Inventory synthesizes comment entries only with complete origin; timeline comments override inventory including tombstones. No listing/fetch is performed despite inventory terminology.

## packages/core/attachments/image-sequence.ts

Reviewed all 520 lines. Pure URL matching, Markdown AST/reference definitions, HTML img attribute parsing/entity decode and file-card scanning excluding code ranges; bounded LRU stores content refs only. Match stable download/local upload IDs then normalized URL equality ignoring query/fragment. Select standalone excludes referenced duplicates; order images before files; collect walks inline then standalone, applies injected inclusion predicate and deduplicates keys. URL priority download_url, markdown_url, url, reference; collectImageSequence supplies local image predicate. No Image, fetch, DOM or resource load; later preview consumers load resources as existing editor evidence describes.

## packages/views/editor/use-coordinated-uploads.ts

Reviewed all 522 lines. Singleton api is injected into startUpload, finite target client:4078. File limit checked before placeholder/request. Snapshots draft target and context; local or persisted placeholders share editor upload ID. Registry acts as local editor ownership lease with identity-checked cleanup and loaded-key matching. Generation checks prevent stale write-back; unmounted success delivers markdown through editor replacement/insert or store append with bounded timer retries. Rebuild retries create local placeholders only. Failure removes placeholder and restores pasted source text; no resumable bytes. removeUpload aborts tracked uploading request then removes local record; gate combines document truth with current store/ref placeholders. No attachment DELETE. Aborted coordinator does not settle the returned wrapper Promise.

## packages/views/editor/use-download-attachment.ts

Reviewed all 201 lines. Every invocation refetches metadata directly: workspace getAttachment client:4438 or markdown-link getAttachmentForDownload client:4447, bypassing stale query data. Desktop prefers fresh attachment_download_url then download_url, resolves API-relative URL and invokes injected downloadURL; missing URL/errors toast. Web prefers forced attachment_download_url, then only site-relative /api/attachments/ signed-download capability from download_url, else requires workspace slug and clicks unified /download?workspace_slug=... . Temporary anchor uses download attribute and is removed. Absolute inline download_url is deliberately excluded from web capability fallback. No renderer blob buffering here. Server-returned forced URL is passed through resolver without canonical-route inference.

## packages/views/editor/use-upload-gate.ts

Reviewed all 61 lines. React state exposes reactive uploading; imperative isBlocked reads editorRef.hasActiveUploads at invocation. No submission/upload operation. Host submit semantics reused from composer-submit coverage.

## packages/views/editor/attachment-download-context.tsx

Reviewed all 93 lines. Context memoizes local matchAttachmentByURL. Known record invokes default workspace download hook; unmatched nonempty URL or absent provider invokes openExternal. Resolve methods only return data. openExternal active web adapter window.open with noopener/noreferrer; SSR no-op; injected desktop openExternal boundary is external/native, not backend support.

## API and resource union

- client:4438 GET /api/attachments/{id}
- client:4447 GET /api/attachments/{id}/download-metadata
- client:4078 POST /api/upload-file

- GET /api/attachments/{id}/download?workspace_slug=<encoded slug>
- Server-returned /api/attachments/<id>/signed-download capability with query preserved
- Server-returned attachment_download_url (relative API capability or absolute storage/CDN URL); concrete path/query are data, not invented canonical routes
- Unmatched input URL opened externally; origins and redirects are input/server-defined

Preview-only downstream union reuses client:4438, client:4475 and client:4508; local blob/data and object URL memory management are not API routes. Metadata is refreshed on every download click; retries for editor readiness are local timers, not API refetch.

## Exact boundaries

- Arbitrary injected ApiClient, StorageAdapter, registered cleanup, binding, editor and inclusion callbacks: Declared contracts and finite active adapter evidence covered; arbitrary replacement implementations are not globally enumerated.
- Native downloadURL/openExternal implementations and server-selected redirect/storage origins: Renderer boundary resolved; native operation and external resource behavior are outside backend support and were not executed.
- Global frontend coverage and unrelated query invalidation fanout: Unchanged and incomplete; click-time download refetch union is fully resolved above.

Validation: JSON round-trip, eleven source paths/full-line bounds and exact anchor text, adapter source line bounds, reused evidence paths, existing frontend call IDs and exact route objects checked locally. No runtime/model/upload/network execution.
