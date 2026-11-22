# Search index storage current-source refresh

Bounded static review complete; root review pending. Five whole sources, 1,498 lines, 17 separate reads of at most 100 lines. No unread ranges. JSON contains NEW SHA-256 hashes and complete read ranges; the old unhashed semantic audit cannot establish historical identity.

Current engine, store, sync, testing and worker bodies support the earlier file-local descriptions. Engine performs local ranking/snippets and byte accounting; server parity and comment performance figures were not verified. IndexedDB transactions persist records with metadata; blocked deletion waits and enumeration errors can propagate. Memory store destruction clears data but does not guard future writes. Sync uses injected manifest/snapshot/changes, resumable bootstrap, cursor catch-up, budgets and retry state; disposal does not cancel already awaited work. FakeServer is local fixture logic. Worker wires local host messages, IndexedDB and optional native locks.

Six inherited transport tuples were checked exactly against frontend-calls.json, including id, method, path_expression and route. Client fetch dispatch is an inherited interface, distinct from worker messages and IndexedDB. Workspace pending-deletion, cache and session effects remain local effects in inherited workspace/active-web evidence, distinct from API calls. Imported application, storage and native providers are explicit interfaces; no descendant recursion or unrelated whole-source claims.

Only the three requested new artifacts were written. No git, application runtime, tests, network, model, data, inventory or shared-ledger edits. No global/backend completion. JSON, current hashes, ranges, counts and exact inventory tuples validated by static artifact checks.
