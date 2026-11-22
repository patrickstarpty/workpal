# Identity lookup contract

Source inspection only; no executed Go/Python parity claim. Task 3 identity lookup is authenticated `GET /api/me`, already registered in Python. Do not add another route. No evidence establishes a public user enumeration or email lookup API. Internal GetUserByEmail and GetUsersByIDs queries are not HTTP contracts. PATCH me and onboarding mutations are separate slices.

Go registration inherits Auth and RefreshCloudFrontCookies, with no workspace membership middleware. Auth strips actor/agent/task headers, prefers bearer credentials over cookies, checks distinct task/PAT/cloud branches and validates JWT claims. GET bypasses write CSRF. Handler obtains user id from trusted context and reads global user by primary key. Missing context is 401 user not authenticated; absent row 401 user not found; other SQL error 500 failed to load user. Handler errors are JSON objects; middleware http.Error bodies have a trailing newline and text content type. No query/body input validation exists for this GET: caller cannot choose the identity with an id/email parameter.

Success is the exact UserResponse field set in the JSON fixture. All nullable fields remain present; count remains present even at zero. Questionnaire defensively falls back to {}; it is JSON, not a JSON-encoded string. Avatar passes through resolveAvatarURLPtr (including nil/empty preservation); stored object references may be rewritten by the avatar resolver. Timestamp formatting follows Go timestamp helpers and needs executable precision fixtures before parity acceptance. GetUser performs SELECT * FROM user WHERE id=$1, with no writes or membership restriction. Middleware cookie renewal is distinct from handler effects; no business event/outbox is warranted.

Python already implements me -> get_user and require_principal -> validate_session. It returns the stored dictionary directly. The dependency checks development capability, session signature/revocation and persisted user; absent users fail 401 Unauthorized before the handler. A deletion race after that check can currently return null with 200. Database errors propagate instead of mapping to Go failed to load user. Stored avatar values are not passed through the Go resolver. These are source-observed gaps, not measured failures. Python session revocation is an explicit local behavior; do not assert Go logout revocation parity.

The approved local policy enables only explicit loopback development auth and the persisted dev@workpal.local user created by manual fixed-code login. Do not manufacture users, add a lookup-by-email API, enable production OAuth/mail/cloud integrations, or translate PAT/task/cloud credentials into interactive sessions. Preserve explicit rejection for unsupported credential kinds. Existing stored membership remains authoritative for subsequent workspace routes; me itself needs no workspace.

Frontend client getMe fetches /api/me and decodes User; auth store uses it for session establishment/refresh; login checks existing session and retries resolution. Preserve terminal 401 versus retryable transport/5xx distinction. Do not establish identity from local storage alone.

## Bounded next slice

Modify only the existing auth routes/service/dependency as needed, with new tests at server/tests/test_identity_lookup_contracts.py. Reuse models, tokens, sessions and app error handling; no duplicate route or new public capability. First test current route registration and persisted response. Then add serializer/error handling only for demonstrated gaps. Avatar resolution requires a separate explicit local capability decision before expanding file delivery.

Meaningful matrix: anonymous; malformed/expired/tampered/revoked session; disabled dev auth; bearer precedence over valid cookie; cookie GET without CSRF; forged identity headers; missing user before dependency and deletion between dependency and handler; injected database failure; exact zero/null/default fields; nondefault questionnaire/profile/timezone; timestamps; null/empty/stored avatar; query id/email ignored; no memberships succeeds; user read causes no user/workspace/event/outbox mutation; reopen preserves profile; near-expiry session cookie behavior; unsupported PAT/task/cloud fail explicitly without external calls. Assertions must include status, raw middleware body/content type versus handler JSON, exact key set and database effects. Do not seed another login identity to test isolation: use rejected credentials or authenticated-id parameter tampering.

## Source locations

- `server/go/cmd/server/router.go:1782`
- `server/go/internal/handler/auth.go:67`
- `server/go/internal/handler/auth.go:96`
- `server/go/internal/handler/auth.go:498`
- `server/go/internal/handler/handler.go:941`
- `server/go/internal/handler/avatar.go:173`
- `server/go/internal/middleware/auth.go:59`
- `server/go/pkg/db/queries/user.sql:1`
- `server/src/workpal_backend/auth/routes.py:90`
- `server/src/workpal_backend/auth/service.py:12`
- `server/src/workpal_backend/auth/dependencies.py:13`
- `server/src/workpal_backend/auth/sessions.py:13`
- `server/src/workpal_backend/auth/models.py:5`
- `packages/core/api/client.ts:1196`
- `packages/core/auth/store.ts:103`
- `packages/core/auth/store.ts:184`
- `packages/views/auth/login-page.tsx:138`
