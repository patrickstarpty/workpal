# Current proxy and analytics source refresh

Root review pending. New hashes prove current reviewed bytes, not historical identity. No global or backend completion claim.

## apps/web/proxy.ts

SHA-256: `2a25fa333d06a4ffc4a460194e1b0206ebec6ecbf1a5bb65a7cf927d43037a81`. Whole source reviewed in inclusive ranges [[1, 100], [101, 175]].

Routing boundary: runtimeRewriteDestination selects destination outside this body; rewrite preserves incoming query. NextResponse rewrite forwards a resource request; redirect causes browser navigation, not a fetch issued here. Locale header/cookie reads and URL manipulation are local. Matcher explicitly includes /v1, /api except upload-file subtree, /auth, /docs, /ws; helper support alone does not prove matcher activation (notably /health). Legacy redirects use session/slug cookies; missing slug clears query; root redirect excludes official marketing host. No wildcard backend endpoint mapping asserted.

## packages/core/analytics/exception-dedupe.ts

SHA-256: `5f48cbc3bb9cbcc64f3753b126602299e86dec008add952b6dbdbc5c48aa7242`. Whole source reviewed in inclusive ranges [[1, 100], [101, 193]].

Local exception fingerprint and sessionStorage read/JSON/write only. First three retained per fingerprint; cap 50 fingerprints; unavailable/corrupt storage and write failures keep events. Last stack frame fields and filenames are text, never requested. Returns a drop decision to caller; no transport.

## packages/core/analytics/index.ts

SHA-256: `c8f89eb97ee538a3168787f873702d35bea36696a50cfebf6014faebfb01538a`. Whole source reviewed in inclusive ranges [[1, 100], [101, 200], [201, 300], [301, 400], [401, 451]].

SDK interface boundary: browser and nonempty key gate init; initialized instance reused. host is config.host or https://us.i.posthog.com, potentially same-origin. posthog.init/identify/capture/captureException delegate possible traffic; methods, paths, assets and delivery are SDK-owned and not enumerated. before_send drops benign exceptions then redacts and dedupes; exceptions enabled, automatic pageviews/clicks/heatmaps, recordings and surveys disabled. Pending identity/operations and properties are local; reset/register manage SDK state, not independently proven requests. onCaptured runs after capture handoff, not delivery; sendInstantly is an SDK option. /api/config and /api/me occur only in comments here. Signup UTM/referrer-origin parsing and bounded 30-day SameSite=Lax cookie write are local; no referrer fetch.

## packages/views/runtimes/components/update-section.tsx

SHA-256: `b08c679773b22d6ebab5aa584bcfd0c5780db58861e18d119a9fe69512954ef1`. Whole source reviewed in inclusive ranges [[1, 100], [101, 200], [201, 300], [301, 321]].

Browser GET literal https://code-host.invalid/api/workpal/releases/latest with Accept header; non-OK/errors return null; nonempty cached tag reused for ten minutes. Mount fetch applies even managed/read-only/offline. initiateUpdate and getUpdateResult cross injected api boundary; exact inventory tuples below. Handler requires latestVersion/runtimeId; primary button additionally newer parseable release, online, unmanaged and no status; retry calls same handler. Poll every 2000ms after initiation; completion/failure/timeout and unmount clean interval; poll errors ignored. Version comparison, React state, timers and completion callback are local. Prop version change can mark completion without poll delivery; no binary download here.

## Existing inventory boundaries

- `{"id": "client:2930", "method": "POST", "path_expression": "/api/runtimes/${runtimeId}/update", "route": {"method": "POST", "path": "/api/runtimes/{runtimeId}/update"}}`
- `{"id": "client:2940", "method": "GET", "path_expression": "/api/runtimes/${runtimeId}/update/${updateId}", "route": {"method": "GET", "path": "/api/runtimes/{runtimeId}/update/{updateId}"}}`

Prior semantic evidence: external-transport-coverage.md/.json; missing historical hash evidence: transport-proof-pointer-reconciliation.md. Existing inventory status remains pending-reconciliation. No shared proof, inventory or runtime file changed.

Remaining scope:

- No target source ranges remain unread.
- Root review pending.
- SDK-owned endpoints, auxiliary browser resources and delivery remain unenumerated; no recursive third-party audit.
- Environment-selected proxy backend/docs destinations and injected ApiClient base URL, dynamic IDs, endpoint auth/implementation remain unresolved concrete application edges; prior helper dispositions reused, not refreshed helper-body proof.
- External release availability, response shape/redirect chain and runtime update execution are unverified.

JSON parsed; all four current SHA-256 hashes and continuous bounded reviewed ranges checked; both inventory tuples compared exactly. Static artifact validation only; no runtime/tests/network/model/integration calls.
