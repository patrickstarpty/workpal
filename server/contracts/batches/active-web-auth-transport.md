# Active web auth and workspace callback closure

Scope: main.tsx → CoreProvider → PythonSession and actual WSProvider. Supplements identity-workspace-transport-coverage; does not replace its wider limitations.

The web entry omits storage and all three auth callbacks. CoreProvider defaults storage to the localStorage adapter; onLogin/onLogout/onSessionExpired are undefined, including AuthInitializer’s optional login callback. Cookie mode suppresses token renewal construction. These are closed injections, not unknown shell implementations.

PythonSession owns workspace resolution, cancellation/removal of cached queries and setCurrentWorkspace. Workspace-storage coalesces slug subscriber notification and rehydration in microtasks. WSProvider registers both slug and UUID snapshots; user plus slug gates connection, and effect cleanup disconnects the previous client. WSClient opens same-origin /ws with workspace_slug; cookie mode sends no token frame. Reconnect and replacement invalidate query prefixes, conditionally causing HTTP through observers. The JSON supplies a conservative static query-factory union with existing call IDs/routes and source evidence; it does not require runtime observer enumeration.

Registered rehydrators are listed in JSON. Persist callbacks read namespaced browser storage; chat reads its injected adapter and replaces memory; surface view registry rehydrates then resets local stores. AuthInitializer’s unauthenticated cleanup resets drafts, removes browser storage/cookie state, wipes the worker search index and clears QueryClient. Cache clearing is not HTTP.

WSProvider also mounts useLocalSearchIndexSync: attach/event/reconnect/visibility pokes can reach the worker bridge in search-index/client.ts:229, which dispatches manifest, snapshot and changes API methods with workspaceSlug. Their existing IDs and routes are recorded. Worker prune/detach/wipe are local operations.

Arbitrary avatar/resource URLs are source-backed browser-resource candidates, not fabricated API routes. Analytics SDK host delivery is external. No unresolved injected active-web auth callbacks remain; no claim of global coverage, runtime execution or backend support is made.
