# Editor preview transport coverage

Static source proof only; no runtime, network, data, shared inventory or Git changes.

## packages/views/editor/attachment-card.tsx

AttachmentCardChrome suppresses mouse propagation and invokes supplied preview/download/delete callbacks; upload state suppresses actions. AttachmentCard uses href only as a truthy capability sentinel, never an anchor. AttachmentFileCard selects preview before download, disables repeated downloads, formats supplied metadata locally; no metadata request or DELETE is selected here. useAttachmentDownloadState guards active keys, tracks thenables and clears on either settlement or synchronous exception. Concrete Attachment caller/download/preview closures reuse editor and draft-attachment evidence; arbitrary supplied callbacks remain a boundary.

## packages/views/editor/hooks/use-inline-media-url.ts

useResignedInlineMedia normalizes legacy local paths then extracts UUID download identity. Re-sign only for nonempty stable download URL with an id and nonempty API base or cross-origin HTTP URL. Metadata query has 20-minute stale/GC; accepts absolute HTTP(S) non-download-shaped fresh URL. Only blobFallback plus successful metadata without signed URL enables byte query. Authenticated metadata gates cached blob reuse; pending ends on failures. Stream hook requires enabled/id/url, always refreshes metadata on mount, zero GC, retries transient failures twice with exponential delay; permanent 4xx except 408/429 suppress retries. Proxy capability requires signed-download pathname, sig and positive exp seconds. Same-origin proxy PDF uses stable download resource; other proxy PDFs fetch authenticated bytes and slice MIME to application/pdf. Other capabilities use absolutized URL; signed storage uses fresh URL; otherwise picked URL. Expiry refresh runs only within five seconds of expiry and reports changed download_url. PDF URLs revoke on replacement/unmount. Image cache refcounts authenticated consumers and revokes five minutes after final unmount; reset test helper clears maps/timers without revoking. URL parsing, slicing, maps and timers are local standard-library operations.

## packages/views/editor/utils/iframe-fragment-nav.ts

Full embedded executable script reviewed: respects defaultPrevented, requires closest anchor and nontrivial leading #, decodes safely, resolves id then escaped named anchor, leaves missing targets alone, prevents default only for found target, replaces current fragment without adding history and smooth-scrolls. withFragmentNavShim appends verbatim script to html or empty string; exposed test constant adds no transport. No postMessage in this target.

## packages/views/editor/utils/preview.ts

All tables and executable functions reviewed. extOf/baseOf normalize path basename; MIME normalization removes parameters. Text whitelist and image-sequence predicate are local data/predicate imports. Dispatch priority PDF, video, audio, image, then text allowlist, markdown, HTML, table, structured, text. structured extension wins over MIME; delimiter picks TSV; file label uppercases extension; previewability wraps dispatch. canOpenPreview permits URL-only image/PDF/video/audio, otherwise needs record. wrapsByDefault uses extension language lookup; all helpers compute values without fetching. Comments about proxy describe consumers, not calls here.

## packages/views/editor/styles/attachment.css

CSS declarations, selectors, media condition and keyframes are layout/appearance only. Structural resource references: url() = []; @import = []. var(), min(), calc(), color-mix(), blur() and cubic-bezier() are CSS functions, not URL loads.

## packages/views/editor/use-lazy-editor.ts

All useLazyEditor callbacks/effect reviewed: resetKey render reset clears focus and queued Files; activation mounts editor, focuses immediately if ready or after ready commit; anchor focus wins over coordinate then generic focus. onReady changes state. uploadOrQueue invokes optional injected editorRef.uploadFile when ready or queues File objects and activates; effect drains queue once ready. No File bytes read and no request selected. Concrete editor upload contract reuses existing use-editor-upload/coordinated multipart evidence; arbitrary imperative ref remains boundary.

## packages/views/editor/index.ts

Entire barrel reviewed: static value/type re-exports only. Re-export evaluation may load modules and their dependencies according to bundler semantics; it does not call exported hooks/components. No dynamic import expression or lazy factory in this file or use-lazy-editor. Do not invent API records for module/chunk loads; exported downstream behavior is bounded by reused audits, not whole transitive module coverage.

Concrete closure and boundaries: attachment-url helpers strip query/fragment, parse HTTP pathname and validate UUID; legacy /uploads/workspaces/<uuid>/<uuid>.<ext> becomes stable /api/attachments/<id>/download then API-base prefix. These recognizers do not validate arbitrary hosts as trusted; unmatched URLs pass through. Protocol-relative URLs are not prefixed. Browser resources can use signed-download capabilities, arbitrary server/input storage hosts, relative URLs, data: or blob:; these are not authenticated ApiClient calls. Existing inventory API IDs are not assigned to arbitrary-host resource loads.

Download closure reuses use-download-attachment: click-time getAttachment client:4438 or markdown resolver getAttachmentForDownload client:4447, then injected desktopAPI.downloadURL or temporary web anchor with forced URL, signed capability, or workspace-qualified stable download. openExternal is native injection/web window.open. Card callbacks alone establish none of these endpoints. Preview modal text query uses client:4475 GET /api/attachments/{id}/content; blob uses client:4508; images/video/audio/PDF use native resources. No backend support is asserted.

HtmlPreviewBody composes fragment shim then location bridge and CodeBlockIframe srcDoc, sandbox allow-scripts without allow-same-origin. Location bridge is prepended after leading doctype, escapes < in JSON initial address, wraps pushState/replaceState, reports query/hash via postMessage(*), handles query-link reload requests and hash changes. Parent checks event.source against current frame window, marker/type/string length <=2048 and leading ?/#; navigate requests require active userActivation where available. Same-query nonempty hash posts to existing frame; other navigation/reload bumps frame key and recreates srcdoc. Frame script accepts hash messages only from parent. Width bridge separately reports bounded finite widths and document token; messages are local cross-window communication, not HTTP. Sandbox does not enumerate or prohibit all authored subresource/network requests: arbitrary uploaded HTML/scripts may reference arbitrary hosts; finite backend route union cannot describe them. Standard React/query hooks, URL/Blob/DOM/history/CSS APIs and injected callbacks are explicit library/browser boundaries, not invented application APIs.

Static module loading: no import() exists in the seven targets. Static barrel dependencies and bundler chunk loading are module loads; no request method/path is inferred from their names. This bounded proof does not claim every re-export implementation is exhaustively audited.


Exact current inventory mappings:

- client:4438 GET /api/attachments/${id} → /api/attachments/{id}
- client:4447 GET /api/attachments/${id}/download-metadata → /api/attachments/{id}/download-metadata
- client:4475 GET /api/attachments/${id}/content → /api/attachments/{id}/content
- client:4508 GET /api/attachments/${id}/download → /api/attachments/{id}/download

Reused evidence:

- server/contracts/batches/core-query-transport-coverage.json
- server/contracts/batches/editor-transport-coverage.json
- server/contracts/batches/draft-attachment-transport-coverage.json
- .superpowers/sdd/2026-11-21-python-go-backend/task1-direct-transports.md

Validation: all recorded SHA-256 values recomputed; paths and edge line bounds checked; inventory tuples compared exactly with current frontend-calls.json. CSS comments stripped before structural url/@import scan. No backend support conclusion.
