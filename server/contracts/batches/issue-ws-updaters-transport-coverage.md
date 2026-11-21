# Issue WS updater transport audit

Static draft for root review. Target: `packages/core/issues/ws-updaters.ts` (793 lines). JSON contains every own function/export anchor, helper calls/effects, separate bounded snapshots, reused proof hashes and explicit inventory tuples for a conservative possible-refetch union. Incoming WS has no invented HTTP route.

Revision and predicate rules are recorded in JSON semantics. Supporting coordinator/query/replay proofs are reused, not promoted to newly reviewed targets. No runtime or guaranteed-request claim.

Outstanding: independently confirm initially truncated target reads; close exact label, delete agent-dependent and archived-helper tuples; root review acceptance. No shared inventory or ledger changed.

Follow-up review: target lines 1–793 were semantically reviewed in eight independently returned chunks of at most 100 lines, without target-output truncation. Reused proof document hashes were recomputed in JSON. Remaining gaps: bounded delete-cache/helper closure; invoked agent query factories and their exact current frontend-calls tuples; archived refresh closure and tuples; recent-issues persistence closure. Existing conservative union remains an overbroad draft pending root review. No runtime or backend support claim.

Root review supersedes the draft gaps above. Read the complete delete helper and recent store, SSR-safe localStorage adapter, invoked agent factories, label query, archived refresh/cancellation and archive query/client bodies. Deletion collects parent IDs before pruning, removes issue-scoped caches, invalidates discovered parents and broader projections, then forgets the local recent ID. Snapshot/activity/run-count/task-page endpoints are now exact inventory tuples. Label archive refresh occurs before revision gating; it marks inactive entries stale and cancels requests before refetching active eligible observers. Archive pages/lookup/facets map to two GET endpoints, lookup requires groupId and all disable retries. No new direct mutation request is made by these event handlers.

Accepted bounded target only. Existing inherited query union is conservative and may contain unreachable members for individual handlers; it is not an exact request trace. Supporting modules are not globally certified. No runtime/backend support claim.
