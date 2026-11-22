# Swimlane bounded transport trace

Target: `packages/views/issues/components/swimlane-view.tsx`, 1902 lines. Static analysis only. Independent root review remains required. No runtime, tests, network, model, data, Git or shared inventory changes.

## Query and cache gates

At 729–806, batch candidates exist only for parent grouping without enabled server branches. Visible parent references and visible issues with positive child progress enter a sorted deduplicated set only when their per-parent cache is undefined. The memo intentionally omits cache/workspace dependencies; cache updates alone do not guarantee recomputation. childrenByParentsOptions enables on nonempty parent IDs, without an additional workspace gate. Its helper chunks 200 IDs, waits for all responses, groups children and hydrates missing or empty per-parent caches; existing nonempty caches survive. Rejection prevents post-Promise.all hydration. Empty parents do not get empty cache entries.

Subscriptions accumulate parent IDs and batch keys until leaving parent grouping or enabling server grouping. Per-parent observers have enabled:false and a local empty queryFn: they do not invoke listChildIssues. They can observe batch hydration, mutation writes and websocket cache updates. Merge prefers observed parent lists over batch lists and deduplicates issue IDs, applying filters only to extra children. Status visibility is enforced by columns. Supplied running/unread sets are inputs, not requests initiated here.

Server descriptors replace legacy discovery when enabled. Descriptor secondary status counts determine visible lanes; unavailable parents are pinned orphan lanes with no target payload. Legacy parent metadata uses unfiltered issues, project metadata uses supplied maps, and assignee names use the shared actor hook. No extra request follows merely from computing these maps.

## Drag and settlement

At 1081–1337, drag start freezes the issue snapshot. Drag-over edits local cell arrays only, rejecting missing targets, archived status changes, orphan moves and self-parenting. Lane reorder merges visible reordered IDs into persisted view order while retaining hidden entries; it emits no issue mutation. Pinned lanes are excluded.

Card drop resets on missing targets and guard failures. It computes edge/midpoint position and before/after anchors, omits unchanged status and returns for unchanged membership/position. The supplied onMoveIssue gets grouping payload, position and anchors. Production surface move action converts anchors to move_intent; useUpdateIssue selects api.moveIssue, POST /api/issues/{id}/move, rather than the adjacent PUT updateIssue body. Shared mutation evidence supplies optimistic rollback, conflict/error and invalidation behavior. The target holds a settlement lock until the supplied callback releases it and increments settleVersion, allowing current cache-derived cells to resync. There is no target try/finally: a custom callback that throws or never settles can retain the lock. Drag cancellation releases the drag lock and restores cells without a request.

## Other handlers and branches

Collapse and lane ordering mutate view state. Hide status is disabled for baseline statuses; otherwise hideStatus changes the view filter, which can change controller query keys and refetch even though the handler has no direct HTTP call. Peek publishes visible status columns excluding collapsed lanes and clears them on cleanup; this is navigation state, with no selection mutation in the target. Scroll restoration, animation-frame throttle, overlay, virtualization and sorting are local effects.

Group footer calls loadMoreGroups only for enabled branches with more groups; empty-error UI calls retryGroups. Cells forward page.loadMore/page.retry with loading/error flags. These are supplied branch callbacks whose shared surface proof governs group/row transport. Cell create sends defaults through onCreateIssue, suppressing orphan/archived affordances and giving page projectId precedence. Opening the create UI does not itself create an issue. Parent links navigate to detail. Rendered descendants are excluded, including their independent interactions.

## Acceptance boundary

The JSON records current source and proof hashes separately from the frontend inventory snapshot. Shared proof source hashes are validated individually; mismatches, if any, must be resolved by root. No arbitrary rendered descendant or third-party internals are recursively included. The target body trace is supplied, but supporting local helper closure and independent root acceptance are not claimed. This artifact must not promote global coverage or backend support.

Root review closes the supporting-local-helper gap above: reviewed sort/filter predicates, move anchors, view hide/order/collapse and local storage persistence, plus drop guards and settlement. Added omitted actor-name member/agent/squad/plugin request tuples; plugin observer requires its flag and workspace. Peek/scroll/navigation providers and supplied branch/create callbacks remain explicit bounded host seams. Callback failure can retain the settle lock; this is a source finding, not a reproduced runtime failure. Source/reused hashes and exact tuples validated. Accepted bounded target only.
