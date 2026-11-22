# Issue cache coordinator static coverage

Whole target reviewed (746 lines). Root review pending. No direct HTTP, model, integration or backend support claim.

Exports and anchors are enumerated in JSON, including both cache aliases, result interface, five shape-filtered readers, apply/rollback and six invalidation helpers. Reader callbacks only select cached shapes; issueArrayEntries accepts an arbitrary caller prefix.

applyIssueChange normalizes status once. Bucketed loaded rows are admitted per acceptCurrent, patched or removed on definite membership loss, with unknown membership marked stale. Unknown status categories require reconcile. Off-window definite members move category totals or decrement on exit; entering/unknown membership marks stale without speculative insertion. Totals clamp at zero. Helper position insertion preserves ascending position; same-category plain edits preserve slots.

Flat windows patch admitted loaded rows and independently evaluate reconcile for filter dependencies, search title, status/priority/assignee/project/top-level filters, date ordering and title/status/priority/created/updated/activity/start/due/position sorting. Custom property ordering is caller-owned. Table and sidebar patch loaded entity snapshots only. Detail is patched only if present and accepted. prevIssue prefers supplied base, otherwise first accepted loaded snapshot.

Inbox projection runs for supplied status/priority/project/assignee/due fields; captures main/archive snapshots, marks existing archive descendants and facets stale when relevant values change, and patches mirrored fields through patchInboxIssueProjection. That helper preserves invalidated state with exact refetchType none, respects older-backend field capability and maps plain/page/infinite archive shapes. It does not apply acceptCurrent.

rollback replays saved list/flat/table/sidebar/detail/inbox/archive snapshots; undefined detail/main snapshots are skipped. It has no overlapping-write arbitration. No children or Gantt arrays are patched by applyIssueChange itself.

Derivative invalidation always targets workspace and My assignee groups plus Gantt; projects depend on statusOrProjectChanged, sidebar on refreshSidebar ?? statusOrProjectChanged. Targeted sidebar predicate includes all view/builtin sources, old/new project sources (null maps to no-project; undefined ignored), and cached lists containing the issue. Sort predicates inspect object key parts for sort_by or nested sort.field. Stale keys deduplicate by hash per call; inbox keys cancel exact requests before exact invalidation via an unawaited promise chain.

No built-in retry/revision policy exists here. acceptCurrent defaults true and is invoked on loaded bucket/flat/table/sidebar/detail snapshots. Caller realtime evidence describes non-increasing revision rejection; mutation evidence describes optimistic settlement and rollback. Neither turns this module into a concurrency lock. Invalidation can cause active observer refetch or later inactive fetch; local reads/writes and cancellation are not HTTP. No guaranteed request counts.

The JSON preserves exact inherited inventory tuples from corrected 45-factory query evidence plus concrete archive page/facets tuples. Each invalidation edge intentionally uses a conservative superset; prefix/predicate restrictions are explicit. Generic caller keys, injected callbacks and unenumerated observers remain open. Earlier issue-surface evidence's truncated coordinator range is covered by this full target read; its other remaining edges stay open.

Validation: source hashes, export anchors, JSON parse, and inherited transport tuples checked statically. No application/runtime/network/Git/data operations.

Root accepted bounded coordinator scope after source checks of rollback and invalidation helper tail. Predicate restrictions and conservative inherited request union remain explicit; no runtime or overlapping-write safety claim.
