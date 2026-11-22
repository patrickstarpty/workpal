# Platform session transport coverage

Static Task1 audit; four target bodies read in full. No backend support or global closure claim.

CoreProvider initCore is module singleton and useMemo reads boot inputs once. Configures shortcuts locally, registers ApiClient/auth/chat stores and schema logger. Token mode hydrates workpal_token and reads storage on every credential lookup; cookie mode omits reader and renewal creation. defaultStorage is SSR-safe localStorage, not HTTP. Injected storage implementations remain host boundaries.

Provider renewal effect subscribes every auth-store update to maybeRenew, installs activity listeners, immediately checks, and cleans subscription/listeners on unmount. Visibility only when visible; focus/pointerdown/keydown trigger checks; SSR watcher no-op. No interval. Freeze watchdog is a child helper, not renewal transport.

renewNow collapses inFlight; skips unauthenticated, missing token and non-three-part base64url-shaped token. Shape check does not validate JWT signature/expiry. maybeRenew obeys deadline; renewNow bypasses deadline. Success cadence floors at 5s. Invalid/zero cadence and rejection schedule 1/2/4/8/16/30s capped backoff; no automatic retry timer. renewed plus token may apply even with invalid cadence, only if still authenticated and stored credential unchanged. Storage write precedes setToken. reset clears deadline/failures/inFlight and does not cancel an outstanding request.

refreshSession -> fetch -> fetchRaw -> standard fetch(baseUrl + /api/auth/refresh), POST, credentials include, JSON content type, request id, current bearer/workspace/CSRF/client identity headers. Observer may refuse before send. Replayable-body CSRF rejection retries once with rebuilt headers. Non-ok throws ApiError; 401 compares current credential with captured credential, ignores replaced credentials, otherwise clears client token and calls CoreProvider onUnauthorized -> authStore.sessionExpired. That removes stored token before idempotence guard; token mode clears workspace, resets analytics, invokes onSessionExpired ?? onLogout, marks unauthenticated and expired according to prior credential. This hook does not call logout HTTP. Active web omits all three auth callbacks.

Refresh schema defaults renewed false/cadence zero and fallback preserves existing credential; response JSON decoding and validation remain helper boundaries as reused auth evidence. Renewal catch backs off, does not itself clear auth; 401 teardown already occurred upstream. Storage/logger callback throws also enter promise catch; early storage reads are before promise catch.

Notification desktop showNotification injection takes precedence, without permission gate or catch; native focus suppression delegated to host. Browser support requires window.Notification function; unsupported returns sentinel, permission request only for default and catches to current permission. Granted construction uses title/body/tag only: no icon/image/resource URL. Constructor failure silently returns. Click best-effort focuses, closes then invokes registered singleton handler; close/handler exceptions are not swallowed. Null registration removes handler.

systemNotificationPath requires slug, prioritizes chatSessionId over issueKey, encodes slug through paths.workspace and selector with encodeURIComponent. Missing selectors returns null. These are navigation paths, not API routes. Retained WebNotificationBridge keeps latest navigation push in ref, registers path builder callback, cleans to null; mounted in retained Next dashboard layout. Active Vite main does not mount it, so do not infer that click routing is active there.

CoreProvider renders QueryProvider/AuthInitializer/ClientUsageReporter/WSProvider and optional LocaleAdapterProvider/UserLocaleSync; these child components are not target callbacks. Reuse active-web-auth and realtime replay coverage for their own query/socket unions rather than attributing every descendant request to provider. Desktop suppresses usage reporter; locale sync requires adapter and syncUserLocale. Active web adapter returns en/preferences en and persist no-op, sync false, same-origin API and WS, defaultStorage, no identity/auth callback injection.

Types.ts declares identity and provider inputs only; opaque callback/adapter declarations are not transport. Browser Notification, DOM events, localStorage, React/Zustand subscription semantics and standard fetch are stopping boundaries. No backend support, runtime results or global closure asserted.

Exact inventory tuple: `{"id": "client:1185", "method": "POST", "path_expression": "/api/auth/refresh", "route": {"method": "POST", "path": "/api/auth/refresh"}}`.

Unresolved: native desktop showNotification and alternative host implementations of injected storage/auth/locale adapters. Active web implementations are explicit above.

Root review accepted bounded active-web scope. Read complete renewal/notification bodies and checked provider wiring plus Vite cookieAuth configuration. Alternative native host injections remain explicitly unverified. No runtime tests run.
