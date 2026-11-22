# Folders and rich content transport audit

Bounded static audit, pending root review. No runtime, network, model, integration or authored-content execution.

Folder list query key [ee, project-folders, wsId], enabled wsId.length > 0. list parses fallback empty folders/filed; create and rename parse FolderSchema; remove/file await request. JSON body uses JSON.stringify; no content execution.

Create success appends only when existing cache and nonduplicate id. Rename onMutate cancels prefix, snapshots, updates names, rolls back truthy prev on error. Delete success removes folder and matching filing rows locally; server behavior is not inferred from its comment. File onMutate cancels/snapshots/removes prior filing and adds only truthy folderId; failure restores truthy prev and toasts Error.message/fallback. All four onSettled invalidate [ee,project-folders,wsId]. Matching factory union within this bounded target is projectFolderListOptions -> GET /api/project-folders, including nested matching keys if supplied elsewhere; no other factory certified.

RichContent memo preprocesses using subscribed cdnDomain and autolink identifiers then highlights. Closed fence offsets derive from processed string. Density is CSS and phase data attribute, neither gates upgrades. Static components map routes links/images/fileCards/tables/code/pre; raw HTML passes rehypeRaw then sanitize then KaTeX, URL transform separately. No direct api.request in renderer; api.getBaseUrl only reads configuration.

Identifier resolution enabled only workspace id, identifier shape, prefix unknown or matching case-insensitively. Miss/loading preserves supplied fallback. Issue mention wrappers stop propagation; reused issue-display proof retains hover/peek/menu/AppLink boundaries. Project card and ProjectChip both invoke useChipProject: list query then detail enabled !listProject (overrides factory enabled gate); observer duplication is not measured request count. Right-click with resolved project stops propagation, yields to text menu otherwise opens menu; selected ProjectMenu descendants remain boundary.

Link slash skill renders span. member/agent/all mention renders span; issue identifier resolves then UUID chip; project mention chip. Bare entity unfurl requires exact visible href and parsed entity route, same workspace or slugless, parser origin rules. Attachment id requires recognized download URL, single-leading-slash relative or credential-free absolute origin matching appOrigin/API base/attachmentPublicUrl. Unmodified primary attachment click invokes download hook; modifier clicks remain native on web; desktop regular/middle click delegates openLink with intent. Missing href prevents default. Hook promises are voided, not awaited by renderer.

Images delegate URL + forceKind=image; fileCards use allowed href or empty string. AttachmentDownloadProvider receives surrounding attachments. Download/hover/native media and preview child resource closure reuse editor-preview; HTML sandbox permits scripts and arbitrary authored subresources, no finite backend API union or no-network conclusion. No authored content was executed.

Rich code upgrades require multiline node, matching source offset closed fence and html/mermaid language. RichPre unwrap requires closed matching rich token; otherwise code shell. RichFenceBlock delegates lazy viewport shell then MermaidBlock or HtmlBlockPreview. Static highlighting and clipboard are library/browser boundaries; dynamic child module/resource behavior is not equated to API routes.

## Remaining edges

Root reconciled five source-observed folder calls as project-folders:39/44/47/50/53 against extension Mount routes at handler.go:52–57. Backend support is not claimed. Child resource and host boundaries remain explicit in JSON.

Exact reused tuples were compared with current frontend-calls.json; source/proof/inventory SHA-256 values are recorded in the JSON. Only assigned artifacts were written.

Root accepted bounded target scope; five mappings added after full folder module and route-registration review. Existing composed route source-reference noise remains separate inventory debt.
