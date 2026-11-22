# Search-index transport coverage

Static audit of every non-test TypeScript source under `packages/core/search-index`, including `testing.ts`. Closes the prior identity/workspace forget implementation gap; no runtime transport claim.

## packages/core/search-index/client.ts

Source: `packages/core/search-index/client.ts:1` (317 lines). attach starts channel and best-effort storage.persist; same target/slug is no-op. detach/poke/search/ping/close/pageshow are local messages. SharedWorker constructor failure falls through to dedicated Worker; unavailable platform/constructor failure yields null and failed flag. hello gates usability. Worker error resolves outstanding searches null. Search requires target/channel/serving, times out at 1500ms, null stops serving. runFetch dispatches only manifest/snapshot/changes to API then posts success or status-bearing failure. forget clears matching target/serving, posts forget only on usable channel, independently enumerates/deletes matching workspace databases swallowing rejection. It does not start a worker or await worker acknowledgment. wipe waits acknowledgment or 5s then deletes locally; prune posts or locally deletes excluding shown target.

## packages/core/search-index/engine.ts

Source: `packages/core/search-index/engine.ts:1` (594 lines). Pure in-memory maps, ranking, filtering, pagination, snippet/result construction and byte budget accounting; no transport. Does not fetch comment/issue/project resources.

## packages/core/search-index/hooks.ts

Source: `packages/core/search-index/hooks.ts:1` (70 lines). Truthy user/workspace/slug attaches, cleanup detaches. workspaceListOptions enabled iff userId -> listWorkspaces; available list prunes. WS on listed issue/comment/project events and reconnect only pokes; visibility visible pokes. Registers/unregisters listeners; does not open/send websocket. Observer-triggered sync coalesces and uses same bounded call union.

## packages/core/search-index/host.ts

Source: `packages/core/search-index/host.ts:1` (329 lines). connect sends hello. Message dispatch handles attach/detach/poke/ping/search/fetch-result/wipe/forget/prune/close locally. attach creates WorkspaceIndex with onChange -> broadcastServing (local port callbacks), updates slug and syncs. Last detach releases after 60s. forget destroys all matching workspace entries across users, clears release timers, nulls attached port targets, broadcasts serving:false, disposes(true) swallowing failure, then deletes matching databases swallowing failure. No HTTP delete. prune retains attached copies; wipe acknowledges after destruction. Search errors return null. fetcherFor delegates three ops to most recently active attached tab; PortGoneError/disconnect/60s timeout tries next candidate, other errors propagate. Silent ports swept after 10min; later messages restore suspended attachment. Pending requests are not explicitly cancelled by forget; disposal guards later sync iterations.

## packages/core/search-index/index.ts

Source: `packages/core/search-index/index.ts:1` (9 lines). Reexports only; no independent transport.

## packages/core/search-index/instance.ts

Source: `packages/core/search-index/instance.ts:1` (43 lines). Singleton injects bound api proxy and worker factory. forgetLocalSearchIndex -> client.forget; wipe -> client.wipe. searchIssues/searchProjects await local result then nullish server fallback; local rejection is not caught here. Readiness is local.

## packages/core/search-index/protocol.ts

Source: `packages/core/search-index/protocol.ts:1` (46 lines). Types for local port messages, three FetchOps and user:workspace key only. post is WorkerChannel.post/postMessage, never an HTTP POST.

## packages/core/search-index/store.ts

Source: `packages/core/search-index/store.ts:1` (338 lines). IndexedDB schema/meta/issues/comments/projects; atomic cursor+records writes; issue deletion also removes comments. open failure/blocked rejects and clears cached promise; versionchange closes connection. destroy marks store destroyed before closing and deleting (prevents reopening). deleteDatabase blocked waits, error rejects; enumerator absent indexedDB/databases returns without deletion. Prefix-matching unparsable names always deleted, selected valid owners deleted, individual delete errors swallowed. MemoryIndexStore and helpers are local, no network.

## packages/core/search-index/sync.ts

Source: `packages/core/search-index/sync.ts:1` (385 lines). WorkspaceIndex loads schema-compatible local meta or resets. Bootstrap fetches manifest unless resuming progress, rejects over budget, snapshots 200/page until done, persists resumable afterNumber and original cursor then changes 500/page until has_more false. Reloads if another context advances cursor. Uses lock, coalesced rerun, 2s debounce and 5min polling. onChange only broadcasts serving. dispose clears timers/engine and optionally destroys store. Search reads local records and snippets; no per-hit API hydration. Budget 500MiB, recheck 24h. 410 resets and immediate retry; 403/404 reset and unavailable for 1h; other errors incl network/503/no tab/schema/IDB back off 5s exponential capped 5min times jitter 0.5..1.5. Failed catchup can serve last good copy for <10min; otherwise fallback. Too-large reset errors swallowed; no fabricated empty sync pages.

## packages/core/search-index/testing.ts

Source: `packages/core/search-index/testing.ts:1` (140 lines). Non-.test source included: FakeServer fixtures and in-memory log implementation of IndexFetcher; manifest/snapshot/changes are local fake methods, not production network.

## packages/core/search-index/worker.ts

Source: `packages/core/search-index/worker.ts:1` (41 lines). Creates host with IndexedDB factory and database-deletion callback. navigator.locks serializes sync if available, else direct callback. Shared and dedicated worker entrypoints wire postMessage/onmessage, not HTTP.

## Concrete API call union

- `packages/core/search-index/instance.ts:21` → `searchIssues` → `packages/core/api/client.ts:1448`, existing `client:1448`: GET `/api/issues/search`.
- `packages/core/search-index/instance.ts:27` → `searchProjects` → `packages/core/api/client.ts:1463`, existing `client:1463`: GET `/api/projects/search`.
- `packages/core/search-index/client.ts:236` → `getSearchIndexManifest` → `packages/core/api/client.ts:1477`, existing `client:1477`: GET `/api/search-index/manifest`.
- `packages/core/search-index/client.ts:239` → `getSearchIndexSnapshot` → `packages/core/api/client.ts:1492`, existing `client:1492`: GET `/api/search-index/snapshot`.
- `packages/core/search-index/client.ts:242` → `getSearchIndexChanges` → `packages/core/api/client.ts:1505`, existing `client:1505`: POST `/api/search-index/changes`.
- `packages/core/search-index/hooks.ts:45` → `listWorkspaces` → `packages/core/api/client.ts:3391`, existing `client:3391`: GET `/api/workspaces`.

Sync calls explicitly override X-Workspace-Slug; snapshot sends after_number/limit query, changes sends cursor/limit JSON. API proxy binds the boot-injected singleton (api/index.ts). ApiClient.fetch → fetchRaw (client.ts:1033) adds base URL, credentials include, auth/CSRF/identity/request-ID headers; observer refusal can stop before send. Replayable-body CSRF rejection retries once with refreshed headers; 401 invokes credential-aware session-expiry callback, then ApiError propagates. JSON/204 decoding precedes strict sync schema validation (rejects malformed bodies); server search uses safe-empty parse fallback. No automatic generic network or 401 retry here. Callback effects outside this static union remain bounded external dependencies.

## Resource decision

No response-derived download endpoint, pull transport, searchchunk or signed resource consumer exists in this module. Snapshot/changes JSON records go directly to IDB/engine. Worker URL is a bundler-resolved module asset, not an API endpoint. No fixed download route inferred.

## Remaining bounded gaps

- External injected API observers/loggers/session-expiry callbacks and application bootstrap implementation are outside this module; narrow union uses concrete ApiClient methods, not arbitrary injected implementations.
- WS connection transport and broad query invalidation observer closure remain external; hooks only subscribe/poke and list workspaces.
- Runtime scheduling, browser worker asset resolution, actual IDB availability/deletion completion and server behavior were not exercised.

Verification: source/file-set, JSON parsing, existing call IDs and route equality, and source anchor bounds checked locally. No integration, network, model, child, git or data operations.
