# External transport coverage

Bounded semantic audit of exactly five sources. Global coverage remains **false**. Source review only: no requests, integration setup, model execution, runtime changes or inventory edits. Proposed records below exist only in this ledger.

## packages/core/analytics/index.ts

- `packages/core/analytics/index.ts:113` — external analytics SDK. Targets: config.host || https://us.i.posthog.com. Mapping: proposed:external:posthog-sdk. Browser only; nonempty config.key required; initialized instance reused. posthog-js owns methods, paths, batching and auxiliary requests: no concrete ingestion endpoint is asserted. before_send at :148 drops benign exceptions, redacts then deduplicates; auto pageview/click/heatmap, recording and surveys disabled; exception autocapture enabled.
- `packages/core/analytics/index.ts:291` — external analytics SDK handoff. Targets: configured PostHog SDK instance. Mapping: same SDK proposal above. captureNow sends event with optional send_instantly; callback confirms handoff only. identify :184/:219, queued exceptions :196, explicit exceptions :321, person $set :346 also delegate. Pre-init operations buffer; reset :231 and register :178/:236 manage SDK state. No /api/config or /api/me request occurs here; those appear only in comments.
- `packages/core/analytics/index.ts:398` — UTM/referrer parsing and bounded signup cookie write :429 are local; referrer URL parsing does not fetch. SDK reset/register are not independently asserted HTTP calls.

## packages/core/analytics/exception-dedupe.ts

- `packages/core/analytics/exception-dedupe.ts:40` — Full module performs fingerprint hashing, JSON and sessionStorage get/set only (:66/:83/:186). Keeps first three per fingerprint; caps 50 distinct; storage failures fail open. Stack filenames are text, never fetched.

## apps/web/features/landing/utils/github-release.ts

- `apps/web/features/landing/utils/github-release.ts:84` — server-side external release fetch. Targets: GET https://code-host.invalid/api/workpal/releases?per_page=5. Mapping: proposed:external:landing-releases. Literal URL at :43; no substitution to api.github.com. Accept and API-version headers :63; optional server GITHUB_TOKEN :73; 300-second revalidation :46/:85; 3000ms abort :51/:78. Filter draft/prerelease :98; choose first complete asset set, otherwise first stable release :130. Returned html_url and browser_download_url are values, not fetched here.
- `apps/web/features/landing/utils/github-release.ts:130` — Release/asset selection and empty fallback are local; imported apps/web/features/landing/utils/parse-release-assets.ts:98 maps asset names to returned browser_download_url strings without transport or origin validation.

## packages/views/runtimes/components/update-section.tsx

- `packages/views/runtimes/components/update-section.tsx:27` — browser external release fetch. Targets: GET https://code-host.invalid/api/workpal/releases/latest. Mapping: proposed:external:runtime-latest-release. Literal :15; Accept header only; successful nonempty tag cached 10 minutes :17/:23/:32. Mount :134 calls even for managed/read-only/offline runtime. Errors/non-OK return null. No GitHub installation/connect backend endpoint.
- `packages/views/runtimes/components/update-section.tsx:169` — backend API via injected singleton. Targets: POST baseUrl/api/runtimes/{runtimeId}/update. Mapping: client:2930. api proxy packages/core/api/index.ts:44 binds injected instance. packages/core/api/client.ts:2930 sends JSON target_version=latestVersion. Handler guard :160 requires latestVersion/runtimeId. Main UI additionally requires newer parseable release, online, no status, unmanaged; failed retry :309 uses same handler. IDs interpolated without encoding by wrapper. Empty baseUrl is same-origin; injected nonempty base selects deployment backend, not release host.
- `packages/views/runtimes/components/update-section.tsx:173` — backend API polling. Targets: GET baseUrl/api/runtimes/{runtimeId}/update/{updateId}. Mapping: client:2940. packages/core/api/client.ts:2940; updateId from initiation response; 2000ms interval :193; completed/failed/timeout clears interval, polling exceptions ignored; cleanup on unmount and before update :124/:131/:161. packages/core/api/client.ts:1071 concatenates baseUrl+path with credentials include and shared auth headers.
- `packages/views/runtimes/components/update-section.tsx:50` — Version parsing/comparison, React state, timers and display are local. No binary download is performed by this component.

## apps/web/proxy.ts

- `apps/web/proxy.ts:97` — middleware forwarding. Targets: configured backend + incoming /v1, /api, /ws, /health or eligible /auth path; DOCS_URL + incoming /docs path. Mapping: proposed:forwarding:runtime-proxy. apps/web/config/runtime-urls.ts:110 selects only known prefixes/exact paths; :57 prefers valid HTTP(S) REMOTE_API_URL then NEXT_PUBLIC_API_URL; :66 DOCS_URL. Trim trailing slash, strip terminal /api from API base (:32), preserve other prefixes; no runtime localhost fallback. :143 excludes /auth/callback and /auth/hg-sso/callback subtrees. apps/web/proxy.ts:100 copies incoming query. Matcher :165 excludes /api/upload-file subtree; helper support does not imply matcher activation. Incoming methods/resources are forwarded, not a new enumerated API call.
- `apps/web/proxy.ts:54` — Locale rewrites use cloned incoming URL; redirects :116/:146 use same origin and cookie-derived pathname. nextWithLocale :41 forwards headers locally. These are navigation/routing decisions, not HTTP fetch calls.

## Scope decisions

- External literal release requests and configurable PostHog SDK traffic are excluded from same-origin Python backend route coverage; proposed records are ledger-only, not inventory mutations.
- Runtime update requests remain backend API calls even though target_version originates in external release metadata. Existing IDs remain pending reconciliation; this audit does not implement or validate operations.
- Forwarding rules do not create wildcard endpoint claims; docs forwarding is a separately configured service.

## Residual dynamic targets

- E1: PostHog config.host and SDK-owned methods, endpoint paths, auxiliary assets and runtime delivery are not enumerated by these sources; configured host may be same-origin or external.
- E2: Injected ApiClient baseUrl, runtime/update IDs, environment backend/docs bases and incoming paths/query remain dynamic. No environment values or live destinations were inspected.
- E3: Release response html_url and browser_download_url values are unvalidated dynamic strings; no resource request for them occurs in the audited fetcher. Consumers and redirect chains outside scope are not claimed covered.

Validation: JSON parsed; all ledger source references checked against existing file line counts; existing frontend-call IDs checked against frontend-calls.json. No active application changes; npm run check is outside this documentation-only audit.

## Parent review
Verified release URL literals, runtime update/poll wrappers, analytics initialization gates and proxy prefix/matcher behavior. Added runtime caller references to shared inventory. Corrected analytics scope: configurable host can be same-origin, so unknown SDK endpoints are not a blanket external exclusion. Null/incoming-method proposals are non-route ledger entries, not HTTP inventory records. No network or runtime verification claimed.
