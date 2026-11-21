# Editor coordination current-source refresh

Finite four-file full-body review complete; root review pending. No global frontend or backend completion claim. Hashes attest current bytes only and do not establish historical identity. Each source was read in individually bounded ranges of at most 100 lines.

## packages/views/editor/attachment.tsx

SHA-256: `ef13ff980fbd2466ceac8853dd161738906280f506d065d30799f6c6adad922e`

Reviewed ranges: [[1, 100], [101, 200], [201, 300], [301, 400], [401, 500], [501, 600], [601, 657]]

Normalizes record/URL inputs and selects signed, CDN, markdown or legacy URLs; api.getBaseUrl is configuration access, not HTTP. Native img src is a browser resource load; HTTP(S)/relative resources differ from local blob/data. useResignedInlineMedia delegates metadata/byte fallback. Download extracts identity then delegates download or resolver/external opening. Preview first tries sequence then full/URL modal. Clipboard copy and toast are local/browser interfaces; onDelete is injected, not an attachment DELETE. Cards receive callbacks, not transport instructions.

## packages/views/editor/paste-as-file.ts

SHA-256: `2718abe4f5e36b1d5e5b5618e9d89b9d7abca24ff42439ef4d754c2e13bed5f7`

Reviewed ranges: [[1, 23]]

Exports only PASTE_AS_FILE_THRESHOLD=4000. Comments describe consumers; no File construction, paste handling, upload or HTTP occurs in this module.

## packages/views/editor/preview-sequence-context.tsx

SHA-256: `c7321ab6181aa9ac65a6b0822175b55a3d979a43204cfb9a337ad68a17117efe`

Reviewed ranges: [[1, 100], [101, 200], [201, 300], [301, 380]]

Collects previewable sequence via imported pure collector. openAt freezes an array snapshot, tracks index/pinned key and resets broken set. Navigation skips broken keys without wrapping; pinned failures remain, others advance forward then reverse. goTo can explicitly select a known key. Closing retains session until modal exit. describeItem and lifecycle/locate/copy/overview actions are host interfaces. Modal and immediate image-neighbor PreviewImagePrefetch mounts can initiate downstream resource/metadata work; state navigation itself is local, not a new route.

## packages/views/editor/use-composer-submit.ts

SHA-256: `17c5930a144fc9ffda4a27c213c247f87b9ab404d5bcc785ce8c7039bc7780a0`

Reviewed ranges: [[1, 100], [101, 176]]

Reads markdown and normalizes before empty/single-flight/upload-gate guards. Locks ref/state, awaits injected onSubmit, invokes onAccepted only on truthy acceptance, catches failures and unlocks in finally. No send endpoint selected here. Focus mode resolved from latest options after acceptance; animation frame uses latest editor/container refs, ownership check for refocus, mount guard and cancellation on unmount. Draft clearing is caller responsibility, not performed by hook; custom normalization, gate and editor methods remain interfaces.

## Edges and evidence

Exact inventory tuples are embedded in the JSON. API-shaped native image loads are distinguished from authenticated API methods. Generic callbacks carry no invented route mapping. Downstream conditional unions reuse existing proofs, rather than implying every mount calls every endpoint.

React, UI/query libraries and browser clipboard/DOM/animation/resource machinery are interfaces; third-party implementations not recursively audited.

Concrete application edges outside refreshed bodies: inline-media hook; download hook/resolver and web/native adapters; AttachmentPreviewModal and PreviewImagePrefetch implementations; host describeItem/lifecycle/locate/copy/overview callbacks; composer host normalization, gate, editor and submit/acceptance callbacks. Existing proofs are reused, not a current-byte re-audit of these implementations.

Unresolved concrete scope: current downstream host/adapter hashes and query invalidation fanout; runtime URL origins, signatures, redirects and native adapter behavior; authored HTML subresources in downstream viewers. No invented inventory mapping for these branches.

Existing proofs inspected: server/contracts/batches/editor-transport-coverage.json, server/contracts/batches/editor-preview-transport-coverage.json, server/contracts/batches/composer-submit-coverage.json, server/contracts/batches/draft-attachment-transport-coverage.json. Composer prior parent resolution supersedes the old modal source_context_refetch exception; unrelated query fanout remains incomplete.

Validation: JSON parsed, four complete line-range partitions and current hashes checked, all embedded inventory tuples compared exactly. No runtime checks requested or executed.
