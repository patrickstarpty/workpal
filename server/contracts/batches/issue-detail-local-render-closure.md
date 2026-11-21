# Issue detail local render callback audit

Status: root accepted finite named callback transport scope. Whole source: false. Earlier checkpoint limitations below are superseded by the root review additions.

The companion JSON records exact defining anchors read in issue-detail.tsx. Render anchors differ slightly from the requested historical lines: select-all is invoked at 4084; latest buttons at 4391 and 4410. The checkbox ref at 4081–4083 assigns the DOM indeterminate property.

Layout onLayoutChanged is supplied by react-resizable-panels useDefaultLayout at 1535–1537. Desktop resize is supplied by useAnimatedRightSidebarState at 1544–1550. Neither provider implementation has been closed here. Context menu is supplied by useIssuePageMenu at 2867. Annotation edit at 4418 calls descriptionAnnotations.editAnnotation(annotationId, true), from useCommentAnnotations at 1752.

Preview wiring at 4464–4492 includes describeDeliverable, session opened/closed callbacks, fresh timeline read, injected completion, overview locate and clipboard-link callbacks. These must not be classified collectively as local without the existing deliverable/editor/preview proofs and hash checks. No inventory tuples have been copied or validated.

Main render artifact and existing proofs remain untouched. No runtime, tests, network, model, database, or git operations were performed. This artifact does not establish finite callback closure or backend completion.

## Root review progress

Verified point-menu, local selection, sidebar animation, scroll-ref adapter and deliverable session bodies. Fresh deliverable timeline read is a real GET (client:1926), staleTime zero and one retry; cleanup suppresses state updates without aborting the request. Validated source hashes in three reused proofs. Remaining jump, preview and annotation binding checks are explicit in JSON; no full closure claim.

## Root finite closure

Confirmed jump/measurement/selection/menu/annotation callbacks use local state and DOM; description annotation binding has no onOpen callback. Deliverable origin selection can trigger the existing conditional comment-thread GET (client:1861), while opening a named deliverable refreshes timeline (client:1926). Preview descriptors invoke host locate/copy callbacks; clipboard is local. Third-party layout, injected host APIs and separately audited descendants remain explicit boundaries. Source hashes and exact tuples recorded. This closes only the named callback scope, not IssueDetail as a whole.
