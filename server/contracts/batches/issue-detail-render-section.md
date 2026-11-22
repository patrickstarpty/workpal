# Issue detail render section audit

Scope: issue-detail.tsx lines 3495–4553. All eleven captured chunks were read individually, at most 100 source lines per call. Snapshots preserved and checked against source. whole_source remains false; root review pending. No runtime/backend support claim.

The JSON records callback prop anchors, own edges, exact inventory tuples, finite refetch proof references and source-hash validation. Inbox Done calls onSaved on mutation success; standalone Done immediately calls parent onDone after starting the write; archive only calls parent onDone. Pin resolves through createPin/deletePin and invalidates the finite pin list. Imported children and parent callbacks are bounded interfaces.

Closure is incomplete at these specific interfaces:

- issue-detail.tsx:4004 -> handleDescriptionUpload:2841-2854 -> uploadWithToast: upload hook transport interface still requires validation.
- issue-detail.tsx:3495-3594 timeline callback mappings and 4185-4294 subscription callback mappings require individual interface-to-proof reconciliation.
- issue-detail.tsx:3738-3762 sidebar/scroll/context menu callbacks; 4087 select-all; 4345-4346 timeline measurement callbacks; 4390/4409 latest jump; 4418 annotation edit; 4451-4490 preview callbacks; 4520/4535 layout/resize callbacks need exact defining anchors and effect reconciliation.

## Root upload closure

Read complete useEditorUpload and useFileUpload bodies. The description callback supplies no contextual IDs, sends the existing client:4078 upload, catches failures into a toast/null result, and appends success to local pending attachments. The later description mutation binds attachment IDs. This hook adds no refetch request. Source hashes and exact tuple recorded in JSON.

## Bounded callback reconciliation (3495–3594; 4185–4294)

The JSON bounded_callback_reconciliation enumerates supplied timeline and subscription callbacks, distinguishing local effects from request-capable hooks. Request handlers trace to useCreateComment, useUpdateComment, useDeleteComment, useResolveComment, useToggleCommentReaction, useToggleIssueSubscriber and useUnsubscribeFromIssueSubtree, with existing query-section mutation edges and finite mutation/query proof references. No new tuple was inferred or copied.

Precise remaining definitions: actions.copyCommentLink returned by useIssueActions (binding at issue-detail.tsx:2863); getActorName and resolveStatusLabel/Category/Color/Icon returned resolver bodies and bindings. Final branch-specific exact tuple reconciliation remains pending. This bounded mapping is not accepted as complete. Root review remains pending and whole_source false. Root upload closure and prior records are preserved.

## Root resolver definition review

Resolved copyCommentLink and actor/status returned callback definitions through direct source reads. Copy uses local clipboard plus injected URL builder. Name/status callbacks read captured directories/catalog; they do not issue a request per invocation. Hook-level directory/catalog queries remain separately accounted. This closes these two definition gaps only; branch-specific request reconciliation and other render gaps remain.

## Root render acceptance

Matched timeline create/edit/delete/reaction/resolve and subscription callbacks to exact client branches. Follow-all always subscribes; ordinary toggles choose subscribe/unsubscribe from current state; subtree is separate. Comment delete preserves both capability-gated endpoints. Refetch union reuses existing finite mutation/query proofs with observer gates. Together with local-render and resolver review, finite3495–4553 section is accepted; whole IssueDetail remains unaccepted.
