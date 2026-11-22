# Deliverable transport coverage

Finite five-target static source audit. No runtime, network, model, integration, data or Git operations. No backend-support claim.

## packages/views/issues/components/deliverables/attachment-versions.tsx

Read all 39 lines in bounded source outputs (any initial truncated aggregate was reread). SHA-256: `89dc2f3c59eaf6d7e36a39c9bc4532a985992186210e0cece285f8e7db8365cd`.

Context builds attachment id to one-based version map only for multi-version files. children is an opaque render boundary; no upload or resource operation.

## packages/views/issues/components/deliverables/deliverable-details.tsx

Read all 367 lines in bounded source outputs (any initial truncated aggregate was reread). SHA-256: `7d9716f8f763a3e2f8d4bce9264461fd36eceef57f97b2c02eecac8d908d1b45`.

Origin resolves description, known comment, or none. locate closes controls before injected onLocate; copy exists only for deliverable plus supplied onCopyLink. Version menu newest first disables absent session ids then controls.goTo; sibling button goes to sibling key. DeliverableInfo and UploaderName call useActorName, which subscribes member/agent/squad directories and feature-gated plugin installations. ActorAvatar descendant receives profileLink=false, no hover or presence opt-in; avatar resource remains descendant boundary. DeliverableThumbnail descendant loads images only; nonimages render local icons. Formatting, descriptions, grouping and lookup are local.

## packages/views/issues/components/deliverables/deliverable-link.tsx

Read all 225 lines in bounded source outputs (any initial truncated aggregate was reread). SHA-256: `21a49f933d0793a61c6dddbe472a4854cfebec3ab5beca4e48c45e02fa223e52`.

Copy requires issueRef; paths.issueDeliverable plus navigation.getShareableUrl computes address, copyText clipboard promise selects success/error toast. No HTTP inferred from share URL. Fresh read skips undefined name, fetchQuery issueTimelineOptions staleTime=0 retry=1; cancellation suppresses settlement; failed stays failed; ready waits dataUpdatedAt >= recorded cache timestamp. Session off/viewer/overview transitions call onDone only at finish; overview close microtask lets synchronous viewer handoff win. Open-on-load skips pending/already handled; failed toast retains link; missing file calls onDone; ready latest file openAt(stayOnError=true) succeeds into viewer, else useOpenAttachment then onDone. Helper tries sequence, standalone tryOpen(full attachment), finally download(id). No upload.

## packages/views/issues/components/deliverables/deliverables-overview.tsx

Read all 426 lines in bounded source outputs (any initial truncated aggregate was reread). SHA-256: `10182455ff84dcc49e8db239ac28e72bf0594b8f92fb22559b30e2cf10c4a169`.

Immersive hook invokes optional desktop setImmersiveMode(true) only while open, false on cleanup; native boundary. G handler only while open and returnKey present, ignores modifiers, closes then openAt(returnKey). Dialog close calls onClose. Tile closes then opens selected displayed latest via useOpenAttachment; locate closes then injected origin callback; copy optional filename callback. Filter state/count/group sorting local: images expanded per version, other files latest; comment fallback uploader. CommentGroup useActorName introduces directory queries. DeliverableThumbnail and ActorAvatar are descendant resource boundaries; VersionBadge local. No upload.

## packages/views/issues/components/deliverables/version-badge.tsx

Read all 29 lines in bounded source outputs (any initial truncated aggregate was reread). SHA-256: `be018c9958a1bfd36de8cbd04b12ce59f188296d6f890f24f3b6951901369002`.

Class composition and translated decorative version label only; no transport.

## Transport anchors

- packages/views/issues/components/deliverables/deliverable-details.tsx:198 — useActorName -> memberListOptions/agentListOptions/squadListOptions; pluginInstallationsOptions enabled only plugins flag and nonempty wsId. Reuse identity-workspace and issue-query audits. Inventory: client:3765, client:2066, client:5203, client:3425.
- packages/views/issues/components/deliverables/deliverable-details.tsx:281 — Descendant boundary: image only -> useResignedInlineMedia(metadata then conditional blob fallback); img src browser resource. Reuse editor-preview audit; not own direct request. Inventory: client:4438, client:4508.
- packages/views/issues/components/deliverables/deliverables-overview.tsx:310 — useActorName -> memberListOptions/agentListOptions/squadListOptions; pluginInstallationsOptions enabled only plugins flag and nonempty wsId. Reuse identity-workspace and issue-query audits. Inventory: client:3765, client:2066, client:5203, client:3425.
- packages/views/issues/components/deliverables/deliverables-overview.tsx:411 — Descendant boundary: image only -> useResignedInlineMedia(metadata then conditional blob fallback); img src browser resource. Reuse editor-preview audit; not own direct request. Inventory: client:4438, client:4508.
- packages/views/issues/components/deliverables/deliverable-link.tsx:89 — issueTimelineOptions -> api.getIssueTimeline; retry and cache timestamp branches preserved in file disposition. Inventory: client:1926.
- packages/views/issues/components/deliverables/deliverable-link.tsx:198 — useOpenAttachment -> sequence openAt, standalone tryOpen, download fallback. Preview metadata/content/bytes and native media resources reuse editor-preview; download getAttachment and web anchor/native downloadURL reuse draft-attachment. No markdown resolver input here, so client:4447 not selected by this helper. Inventory: client:4438, client:4475, client:4508.
- packages/views/issues/components/deliverables/deliverables-overview.tsx:78 — useOpenAttachment -> sequence openAt, standalone tryOpen, download fallback. Preview metadata/content/bytes and native media resources reuse editor-preview; download getAttachment and web anchor/native downloadURL reuse draft-attachment. No markdown resolver input here, so client:4447 not selected by this helper. Inventory: client:4438, client:4475, client:4508.

## Boundaries and validation

Injected onLocate/onDone/onClose/onCopyLink and controls: caller contracts, arbitrary replacements not enumerated.

Browser image/media/PDF/avatar resources use supplied or server URLs, signed capabilities, blob/data URLs; no invented API inventory tuple for arbitrary URL.

React, TanStack query scheduling, UI primitives, DOM listeners, microtasks and clipboard terminate as library/browser operations.

Descendant preview modal can render authored HTML with arbitrary subresources as recorded in editor-preview; finite API union does not enumerate those hosts.

Reuses editor-preview, draft-attachment, issue-query and identity-workspace evidence. Exact method/path_expression/route objects are preserved in JSON. No remaining unresolved own transport edges within these five targets; injected and descendant boundaries are explicit above. Global coverage remains incomplete. Hashes, source anchors and every mapped inventory tuple validated locally. Shared inventories and ledger untouched.

Root accepted bounded target-source scope after exact anchor validation and spot checks of timeline freshness and fallback ordering. Fully read useOpenAttachment and DeliverableThumbnail; supporting hashes recorded. No runtime verification.
