# Web shell transport coverage

Bounded full-source static review of ten ledger files. Global coverage remains false. No backend support claim. Vite and retained Next entry evidence and exact existing call records are in the JSON. Static possible API union reuses active-web-auth-transport; runtime observer enumeration is not required.

## apps/web/app/(auth)/login/page.tsx

Status: full-source-static-disposition; full lines 1–261.

Retained Next login entry: invitation check only before onboarding; authenticated arrival ensures workspace query unless next/CLI/desktop branch; desktop branch issues CLI token then workpal:// callback (including retry button). LoginPage delegates send/verify, getMe, workspace list and CLI authorization; Google client ID gates OAuth browser navigation. Sanitized next and router navigation are pages, not API endpoints. Cache/cookie/state work is local.

Existing calls: client:1147 POST /auth/send-code, client:1154 POST /auth/verify-code, client:1197 GET /api/me, client:1267 PATCH /api/me, client:3391 GET /api/workspaces, client:3409 POST /api/workspaces.

Open edges: CLI validated loopback callback and workpal:// handoff are browser/native delivery, not backend support; external OAuth navigation is not a Python route.

## apps/web/app/(landing)/download/page.tsx

Status: full-source-static-disposition; full lines 1–23.

Retained Next server page: metadata helper plus parallel release helper, request-platform and searchParams; validates started key, passes release/platform to DownloadClient. Release helper GETs literal https://code-host.invalid/api/workpal/releases?per_page=5 with optional server GITHUB_TOKEN, 300s cache and 3s abort; filters draft/prerelease, picks complete or first stable, returns empty on error. Asset URLs are values passed to browser UI, not additional HTTP API calls here.

Existing calls: none directly mapped; see delegation/external disposition.

Open edges: DownloadClient/browser asset destinations depend on release payload; no invented backend download route. Metadata/platform helper transitive coverage not closed by this file.

## apps/web/app/api/upload-file/route.ts

Status: full-source-static-disposition; full lines 1–11.

Retained Next nodejs handler exports POST and OPTIONS only; both return proxyUpload(request), no parsing or second request.

Existing calls: upload-proxy:66:POST POST /api/upload-file, upload-proxy:66:OPTIONS OPTIONS /api/upload-file.

Open edges: OPTIONS is existing scope-decision under global CORS, not missing route support.

## apps/web/app/verification-login.tsx

Status: full-source-static-disposition; full lines 1–9.

Active Vite unauthenticated entry via python-session: config effect GET credentials include, development_auth strictly true seeds defaults; cancellation suppresses state updates but does not abort request; retry re-runs config. Form prevents default and delegates verifyCode; local error/busy state; no browser form endpoint.

Existing calls: client:1154 POST /auth/verify-code, client:3351 GET /api/config, verification-login:7 GET /api/config.

Open edges: None within this file’s bounded transport disposition.

## apps/web/components/web-providers.tsx

Status: full-source-static-disposition; full lines 1–113.

Retained Next layout provider: legacy localStorage token selects bearer versus cookie mode; passes optional apiBaseUrl and explicit wsUrl or same-origin ws/wss /ws to CoreProvider. Identity/version, cookie locale adapter and login/logout cookies configure shared client. CoreProvider creates ApiClient singleton, auth initialization, WSProvider, usage reporter and conditional token renewal; locale sync may call API. Development-only dynamic toolbar is conditional on devToolbarApiUrl. No direct fetch or native invocation in this file.

Existing calls: none directly mapped; see delegation/external disposition.

Open edges: Conservative shared CoreProvider/query union reused from active-web-auth-transport; dev toolbar transitive sources remain outside this ten-file closure. Native preload presence elsewhere does not establish native backend support.

## apps/web/config/google-analytics.ts

Status: full-source-static-disposition; full lines 1–162.

Pure config and URL transformations: validates opt-in GA ID, allowlists campaign query keys, redacts invite capability path, drops hash, rejects non-HTTP URLs, classifies sensitivity and emits fixed route titles. No request here. Next layout conditionally mounts GoogleAnalytics; installer queues gtag and creates external googletagmanager script, defers sensitive initial URL and permanently disables after sensitive post-load navigation/link/form interaction. Link/form observation does not issue their endpoint requests.

Existing calls: none directly mapped; see delegation/external disposition.

Open edges: Google SDK collection destinations remain external SDK-owned; no backend route or existing call ID is invented.

## apps/web/features/landing/components/contact-sales-page-client.tsx

Status: full-source-static-disposition; full lines 1–595.

Retained landing form: input/select/consent components update local state; preventDefault, busy/free-email guards then POST /api/contact-sales JSON with snake_case fields and default same-origin credentials; success resets state and scrolls; handles 429, error JSON and exceptions. Home Link is navigation; form has no action transport.

Existing calls: contact-sales:105 POST /api/contact-sales.

Open edges: SiteHeader/Footer transitive browser resources are outside this source closure.

## apps/web/features/landing/utils/parse-release-assets.ts

Status: full-source-static-disposition; full lines 1–138.

Pure full module: maps artifact filenames to twelve desktop keys, normalizes Linux aliases, skips auxiliary/CLI files, copies browser_download_url without fetching/validating it; sizes and any/complete checks are local. Returned URLs may later become browser downloads; neither route identity nor trusted origin follows from filename.

Existing calls: none directly mapped; see delegation/external disposition.

Open edges: Payload-selected browser resource destinations are intentionally dynamic, not unresolved HTTP API routes.

## apps/web/features/landing/utils/use-github-stars.ts

Status: full-source-static-disposition; full lines 1–51.

Full hook: module cache/inFlight coalesces helper call, caches number/null, clears promise, effect active flag protects state; reexports formatStarCount. Current packages/core/github/stars.ts fetchGithubStars returns null immediately; comments about live GitHub fetch do not describe current execution. No HTTP/native transport.

Existing calls: none directly mapped; see delegation/external disposition.

Open edges: None within this file’s bounded transport disposition.

## apps/web/platform/upload-proxy.ts

Status: full-source-static-disposition; full lines 1–84.

Full forwarding implementation: default fetchImpl=fetch is injectable; development resolver versus production resolver chooses configured HTTP API base, strips /api suffix in resolver; absent origin returns 503. Appends /api/upload-file to base path, preserves incoming search, forwards method/body/signal, manual redirect and duplex half. Preserves auth/cookie/CSRF except named connection/hop headers; strips length/expect, sets forwarded host/identity encoding. Streams response with status/headers; strips encoding/length; abort rethrows, other failures 502. No native branch or signed URL follow-up.

Existing calls: upload-proxy:66:POST POST /api/upload-file, upload-proxy:66:OPTIONS OPTIONS /api/upload-file.

Open edges: Injected fetch can implement arbitrary behavior; static default plus declared injection contract is sufficient, not runtime enumeration. Forwarded preflight semantics/Python parity remain unverified; existing OPTIONS middleware decision retained.


## Parent review

Login mapping corrected: `client:1172` POST `/api/cli-token` and `client:3806` GET `/api/invitations` were omitted from the copied list. Eight file dispositions accepted; download page and WebProviders remain pending their stated transitive edges. No runtime support claim.
