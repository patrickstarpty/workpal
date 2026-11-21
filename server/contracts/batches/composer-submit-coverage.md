# Composer submit coverage

Six useComposerSubmit hosts; source audit only

packages/views/editor/use-composer-submit.ts:161 awaits callback; upload gate rejects before submission; normalization, focus and draft effects are local. Upload transport is separately client:4078 POST /api/upload-file, already covered by editor ledger.

## packages/views/chat/components/chat-input.tsx:500

Annotation composition and page mention prefix are local. Main chat creates a session when necessary then posts message; builder forwards to useBuilderSession.send. Message endpoint may execute/steer/queue model work. commitInput clears only untouched sent draft and annotations; focus callback local.

Chain: packages/views/chat/components/chat-input.tsx:508 → packages/views/chat/components/chat-input.tsx:629 → packages/views/chat/chat-page.tsx:405 → packages/views/chat/components/chat-window.tsx:422 → packages/views/chat/components/use-chat-controller.ts:425 → packages/core/chat/mutations.ts:171 → packages/views/chat/components/use-chat-controller.ts:556 → packages/views/agents/create/builder-conversation.tsx:143 → packages/views/agents/create/builder-workspace.tsx:325 → packages/views/agents/create/use-builder-session.ts:211

Existing HTTP: client:4129 POST /api/chat/sessions, client:4260 POST /api/chat/sessions/{sessionId}/messages

## packages/views/modals/quick-create-issue.tsx:441

Agent/squad quick create or anchored agent sub-issue starts model work. Actor/version/source and cloud attachment guards reject locally. Acceptance stores preferences and conditionally clears draft, closes or refocuses locally.

Chain: packages/views/modals/quick-create-issue.tsx:464 → packages/views/modals/quick-create-issue.tsx:479 → packages/views/modals/quick-create-issue.tsx:563

Existing HTTP: client:1714 POST /api/comments/{commentId}/sub-issues, client:1673 POST /api/issues/quick-create

## packages/views/modals/create-issue.tsx:534

Title normalization permits title-only creation; description read separately. Manual issue/sub-issue write, queued child parent updates, legacy label attach only if response labels absent. Custom properties require config capability read. Acceptance preference/draft/reset/close effects local; no explicit model execution request in manual branch.

Chain: packages/views/modals/create-issue.tsx:537 → packages/views/modals/create-issue.tsx:553 → packages/core/issues/mutations.ts:190 → packages/views/modals/create-issue.tsx:576 → packages/core/issues/mutations.ts:180 → packages/views/modals/create-issue.tsx:606 → packages/core/issues/mutations.ts:199 → packages/views/modals/create-issue.tsx:645 → packages/core/labels/mutations.ts:234 → packages/views/modals/create-issue.tsx:814

Existing HTTP: client:1648 POST /api/issues, client:1714 POST /api/comments/{commentId}/sub-issues, client:1771 PUT /api/issues/{id}, client:5032 POST /api/issues/{id}/labels, client:3351 GET /api/config

## packages/views/issues/components/comment-input.tsx:174

Compose annotations locally; filter referenced uploads. Current matching restart preview optionally cancels runs before comment POST; cancellation failure rejects send. Reply passes current target parent_id and rejects missing/changed target. Comment trigger routing may cause server model execution. Acceptance clears unchanged draft/editor and recipients; issue-detail acceptance scrolls locally.

Chain: packages/views/issues/components/comment-input.tsx:205 → packages/views/issues/components/issue-detail.tsx:4415 → packages/views/issues/hooks/use-issue-timeline.ts:344 → packages/core/issues/mutations.ts:903 → packages/views/issues/components/use-stop-runs-before-send.ts:20 → packages/core/issues/mutations.ts:1284

Existing HTTP: client:1876 POST /api/issues/{id}/comments, client:3133 POST /api/issues/{id}/tasks/{taskId}/cancel

## packages/views/issues/components/reply-input.tsx:193

Compose annotations locally; filter referenced uploads. Current matching restart preview optionally cancels runs before comment POST; cancellation failure rejects send. Reply passes current target parent_id and rejects missing/changed target. Comment trigger routing may cause server model execution. Acceptance clears unchanged draft/editor and recipients; issue-detail acceptance scrolls locally.

Chain: packages/views/issues/components/reply-input.tsx:230 → packages/views/issues/components/comment-card.tsx:1718 → packages/views/issues/hooks/use-issue-timeline.ts:363 → packages/core/issues/mutations.ts:903 → packages/views/issues/components/use-stop-runs-before-send.ts:20 → packages/core/issues/mutations.ts:1284

Existing HTTP: client:1876 POST /api/issues/{id}/comments, client:3133 POST /api/issues/{id}/tasks/{taskId}/cancel

## packages/views/issues/components/comment-card.tsx:484

Cancelled edit rejects; unchanged body and attachment set accepts without write. Otherwise PUT comment with suppression and content base; conflicts retain edit. Acceptance clears unchanged local draft/edit state. Server trigger outcomes may include model work; no separate execution HTTP call here.

Chain: packages/views/issues/components/comment-card.tsx:511 → packages/views/issues/components/issue-detail.tsx:3559 → packages/views/issues/hooks/use-issue-timeline.ts:389 → packages/core/issues/mutations.ts:974

Existing HTTP: client:1939 PUT /api/comments/{commentId}

## Remaining limits

- Modal source_context_refetch injected callback on rejection: quick-create-issue.tsx:536 and create-issue.tsx:708; implementation not established in this bounded audit. No HTTP record invented.
- Builder encodeInput callback may transform content; not classified as HTTP. Query invalidation/refetch fanout is not exhaustively enumerated.
- No HTTP/model calls invoked. Global frontend coverage remains false. Parent review required.

## Parent review
Checked create/manual branches, comment edit and create callbacks, chat/builder send paths. Linked host evidence into existing calls. Resolved modal source_context_refetch via create-issue-dialog.tsx:101 → core/issues/queries.ts:225 → client:1680 GET sub-issue-preview; the earlier unresolved refetch note is superseded. Query invalidation fanout remains incomplete; no runtime/model call was made.
