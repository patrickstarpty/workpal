# Observer and local state transport coverage

Static source audit only. Global transport coverage remains false; no runtime or backend support claim.

## packages/core/api/index.ts

Full source: 50 lines; SHA-256 `318285b11b1ddb79f3df0b87e0b895110c7e178b16c6086c2084b619178133c2`.

Singleton assignment/getter and property-forwarding Proxy; binds functions to injected ApiClient. Reexports are not dispatch. Actual calls depend on selected member; search-index-transport-coverage.md documents concrete ApiClient common transport seam.

## packages/core/api/realtime-observer.ts

Full source: 94 lines; SHA-256 `263a345c1465247c71012631228e5d125dc7c5eee2969b2d119a4b8a9fe57996`.

Observer/target registration and synchronous callback dispatch only. Cause context restored in finally; hold deduplicates and caps merged causes at 20; context does not follow await. replay invokes observer then registered target; drop delegates to target. Neither is intrinsically network-free at application boundary.

## packages/core/api/request-observer.ts

Full source: 30 lines; SHA-256 `dff8a70c65aeabc4f2ba9b796ef4a03d9c22f5791843693b2864a078bfb82247`.

Optional refusal plus start/end notification interface and singleton setter/getter only. No request dispatch here; common ApiClient transport owns invocation and refusal handling (search-index-transport-coverage.md). Arbitrary consumer callbacks need no recursive listener inventory.

## packages/core/diagnostics/dev-recorder.ts

Full source: 697 lines; SHA-256 `b579f809c6dad7282facc157df2be0fafe5aadbd339d3d10ac8a399fc175fe6f`.

In-memory bounded recording, redaction, pruning, timers, PerformanceObserver, console/error listeners and query-cache subscription. Known request observer records metadata and refuses replay writes; realtime observer records frames/reconnects. Subscriber notification invokes callbacks; application use-dev-metrics.ts uses useSyncExternalStore to reread recording. Replay checks workspace and retained raw message then delegates; drop delegates. No fetch, IndexedDB, localStorage write or debug download implementation in this file. Refusal permits GET/HEAD/readOnly and only protects synchronous active replay causes; it is not a global no-network guarantee.

## packages/core/issues/stores/comment-draft-store.ts

Full source: 307 lines; SHA-256 `699c6270150453b38cc68e957c1dea05c4997a96e0228f3ff1b91a7842c46fa6`.

Local Zustand draft CRUD, annotation validation/deduplication, upload metadata transitions and WeakMap derived attachment cache. No upload bytes dispatched. Rehydrate normalizes uploads and annotations, prunes 30-day stale/empty entries. Workspace-aware defaultStorage persists workpal_comment_drafts:<slug> to localStorage, not IndexedDB. Empty namespace merges empty drafts. Cleanup resets local drafts.

## packages/core/issues/stores/draft-store.ts

Full source: 399 lines; SHA-256 `b16a27715fa629d73f242314117ae394a9a115d36bde133d461cc676760339a7`.

Local shared/manual/agent draft updates, legacy migration, upload metadata normalization and recoverable-intent comparisons. Isolated draft backup and continuation baseline are in-memory; partialize persists ordinary backup and normalizes untouched continuation status. workpal_issue_draft:<slug> uses localStorage. Workspace rehydrate and registered cleanup are local state operations, not create-issue requests.

## packages/core/chat/message-cache.ts

Full source: 135 lines; SHA-256 `0c7e56ec61551df34a26a7bc554d0dd4d84a9856e4f0eb8cc4b915e15f623429`.

Only setQueryData to flat and paged chat caches. Identity by id; existing defined fields win, incoming fills undefined fields. New messages append to page zero; optional missing-cache seeding defaults false. No invalidation/refetch/send performed by this helper. Generic cache subscriber execution is outside its direct transport disposition.

## Application boundaries and precise remaining edges

Known application target: packages/core/realtime/use-realtime-sync.ts:896 registers replay: ws.replay and drop: () => client.drop(). Replay can execute invalidations/refetch handlers; refreshMap at 901 includes inbox invalidation and agent query invalidation. Full handler-to-request union is not closed by this batch; do not label replay local-only transport.

Connection drop reaches WSClient reconnect behavior; authenticated /ws handshake, subscriptions and reconnect refetch are described in existing realtime.md/json. No new endpoint or backend support follows.

Exact active-query request union after replay/reconnect depends on registered application query options. Remaining edge: enumerate only concrete application sync handler producers if a complete replay HTTP union is required; do not recursively audit React/Zustand/node_modules listeners.

IndexedDB belongs to search-index/store.ts, already dispositioned in search-index-transport-coverage.md; neither draft store nor message-cache uses IndexedDB. Draft upload producer/submit transport is separately covered by draft-attachment-transport-coverage and composer-submit-coverage; metadata mutation does not imply dispatch.

No debug download producer found in named sources or packages/views/dev-toolbar search for Blob/createObjectURL/download. Any external debug exporter is outside this proof and must be traced before assigning a transport disposition.

Verification: full executable bodies read in bounded source output, including rereads of truncated sections. No runtime tests required for these new audit documents. Root review remains pending.
