# WS client transport audit

Single target: `packages/core/api/ws-client.ts` (303 lines), fully read in bounded ranges 1–155 and 156–303. Static audit only; root review pending. No backend or global support claim.

## Transport inventory

`{"id": "ws-client:106", "method": "GET", "path_expression": "baseUrl with workspace_slug and client identity query parameters", "route": {"method": "GET", "path": "/ws"}}`

This is the existing upgrade inventory, not an HTTP request per frame. The supplied URL is not constrained to /ws by this class. Authentication and generic outbound messages are frames.

## Whole-source disposition

Lines 1–38: Imports/types/constants and bounded log summarizer: type-only event contract; logger and observer are helper boundaries. Non-string malformed input uses String; log truncates beyond 200 characters, conversion/logger errors are not caught.

Lines 39–88: State, constructor defaults and setAuth: stores credentials/workspace and optional identity/token reader/logger. No request or automatic connect; setAuth does not reconnect.

Lines 89–118: connect resets malformed-frame suppression, sets connecting/reconnecting, parses supplied absolute URL; truthy workspace/identity values replace corresponding query values, absent values leave supplied query intact. Does not sanitize preexisting token parameters or enforce /ws; inventory route describes configured application URL. Native WebSocket is upgrade boundary. onopen reads getToken at open time with nullish fallback to stored token; token mode sends auth frame then waits for ack; cookie mode or missing token immediately marks authenticated. URL/constructor/reader/send exceptions uncaught.

Lines 120–162: JSON.parse failure warns every occurrence and returns. Falsy values or non-string type drop with one warning per connect; no enum/payload/actor/schema validation. auth_ack unconditionally authenticates and is not dispatched; no timeout, ack correlation or duplicate-ack guard. Other frames log, optionally observer.onEvent(false) and synchronous causes, then dispatch; observer/logger exceptions propagate.

Lines 164–185: close always schedules retry regardless close code; error is suppressed. dispatch exact-type handlers in Set order with payload/actor fields, then onAny full message. Subscriber exceptions propagate and stop later callbacks; no await or payload validation.

Lines 187–212: Retry indefinitely: min(1000*2^attempt,30000), +/-20% jitter then upper cap/round; increments attempt, status/log, schedules connect. No deduplication or cancellation of earlier timers in connect/scheduleReconnect; timer reference remains after firing. No heartbeat, resume cursor, queue or replay buffer.

Lines 214–237: Authenticated logs, determines recovery from prior connection or attempts, resets attempt and sets connected. Recovery callbacks run synchronously with per-callback synchronous catch, optionally observer reconnect cause; rejected promises are not awaited/caught. hasConnectedBefore set afterward; repeated ack can invoke recovery callbacks. No server resume/replay request.

Lines 239–265: drop closes current socket, preserving normal retry. disconnect clears recorded timer, detaches close/error before close/null, resets history/attempt and clears all subscriber sets. Does not reset status/auth/identity or detach open/message; no generation guard for stale socket events or repeated connect. Native close scheduling is boundary.

Lines 267–294: getStatus returns local status; status and exact/onAny subscription Sets deduplicate and return deletion closures. setStatus skips same value, invokes listeners without catch. No wire subscribe/unsubscribe frame.

Lines 296–303: onReconnect uses local Set and deletion closure. send only serializes/sends when current native readyState is OPEN, otherwise silently drops; no auth-status gate, buffer, retry, return acknowledgement or outbound schema validation; stringify/send errors propagate.

## Reused proof and remaining boundaries

Realtime replay coverage resolves its concrete central dispatch, query/cache union, observer/recorder, notification and reconnect invalidation behavior. Its replay target is separate from WSClient dispatch and excludes arbitrary external subscribers. Platform-session coverage resolves concrete provider storage/current credentials, renewal and notification host wiring. Both proofs and all listed source hashes were validated against current disk. Their existing HTTP effects remain indirect consumer effects.

Native WebSocket and arbitrary caller callbacks remain explicit boundaries. No infinite library recursion or exhaustive caller claim. JSON records exact proof hashes, source anchors and inventory tuple. No runtime checks were run under the static-only authorization.

Root accepted transport source disposition after independently reading all 303 lines and validating hashes/tuple. Lifecycle limitations (stale events and timer/generation handling) remain recorded for runtime review; static closure does not certify race safety.
