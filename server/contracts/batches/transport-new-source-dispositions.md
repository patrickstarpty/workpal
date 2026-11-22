# Three-source transport disposition

Finite own-body audit complete; root review pending. No whole-application or backend completion claim.

All three files were read in bounded source chunks. JSON files[] records exact SHA256 and whole_source=true; edges contains application API, external resources, local helpers and exclusions.

- `persist:349` → `client:3416`: `PATCH /api/workspaces/{id}`. workspace required; saving state; saveDraft requires draft/nonblank URL/no duplicate; removal confirmation; import skips archived/duplicate/invalid identities and persists only nonempty additions. Updates workspaceKeys.list cache, no invalidation/refetch.
- `useCurrentMember:145 -> memberListOptions` → `client:3765`: `GET /api/workspaces/{id}/members`. No enabled override in memberListOptions; selects current auth user membership.
- `githubInstallationsOptions:176` → `client:5487`: `GET /api/workspaces/{id}/github/installations`. enabled !!wsId && owner/admin
- `githubInstallationRepositoriesOptions:189` → `client:5507`: `GET /api/workspaces/{id}/github/installations/{installationId}/repositories`. Own enabled override: picker open && canManageGitHub && browse configured && selected installation truthy; overrides helper wsId gate. page=1 initially, per_page=100; next_page ?? undefined. Automatic fetchNextPage when preselecting selected repository set && hasNextPage && !isFetchingNextPage && !isError. Manual fetchNextPage shown with hasNextPage, disabled while fetching.
- `connectGitHub callback:477 -> supplied connection.connect` → `client:5475`: `GET /api/workspaces/{id}/github/connect`. UI canManageGitHub; disabled connecting or !configured. Supplied callback provenance use-connect-github.ts: getGitHubConnectURL(wsId,{desktop:isDesktopShell()}); desktop=1 only desktop; opens returned URL only configured && url; desktop begins connection store. Prop callback is not created here.

External logo construction: https://logos.composio.dev/api/ plus encoded trimmed lowercase slug; optional ?theme=dark. Caller fallback URL remains opaque. Independent light/dark img failure chains and CSS visibility do not imply network suppression.

Analytics construction: https://www.googletagmanager.com/gtag/js?id= plus encoded measurement ID. Sensitive URL deferral, once-per-ID sentinel and permanent stop gates are recorded in JSON; queued gtag calls do not establish downstream network endpoints. Config URL/title helpers are local transforms. Third-party internals excluded.

Repository URLs are stored/displayed and normalized for identity, never fetched or executed by this body. Child components excluded. No explicit refetch/invalidation in this source; query defaults remain library behavior. Static hashes, unique existing exact tuples and JSON parsing validated; no runtime or tests run. Shared evidence was read only.
