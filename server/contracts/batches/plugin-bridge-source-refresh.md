# Plugin bridge current-source refresh

Current-source review covers all 154 lines, read as 1–100 and 101–154. The SHA-256 proves the bytes reviewed now only; it does not recover or establish historical source identity. Root review remains pending. No global or backend completion is claimed.

Lines 1–44 define the API import, protocol and request union, six path regex families and resize limit. Lines 45–79 validate request shape and expose installation/token/issue/resize and connect/theme/close interfaces. Lines 81–116 implement local resize, rejection and the sole outbound application API delegation. Lines 118–154 implement window identity/version/challenge/first-port acceptance, port messages, theme delivery and cleanup.

The action boundary at 102 delegates method, raw path, optional body and mounted issueId to api.callPluginAction with installationId. The inspected client.ts 3648–3682 fragment confirms HTTP delegation through this.fetch, installation header, defined-body JSON serialization, and encoded issue_id only for exact /context. This refresh does not audit the client implementation as a whole. Exact inventory tuples are preserved, including top-level methods that differ from route.method. Canonical task-message inventory variants are excluded by the bridge allowlist; direct invokePluginHook and launch calls are separate interfaces, not calls made here.

All five allowed verbs pass independently for each of six regex families; acceptance does not prove server support. Prior plugin-surface-transport-coverage.json matrix and companion Markdown retain semantic dispositions for supported versus unsupported combinations. transport-source-ledger.json target entry explicitly lacks historical hash proof. These are contextual prior proofs, not freshly revalidated server implementations.

Window listeners, MessagePort start/postMessage/close, connected/closed state, theme function evaluation and onResize are local browser operations or caller callbacks, not HTTP. No iframe src assignment, hosted resource navigation, fetch, WebSocket or EventSource is present here. Launch and hosted document resource effects described by prior proofs belong to adjacent sources. Handshake checks expected frame window, protocol 2, challenge and a first transferred port; it does not validate origin here. Invalid shapes are ignored; invalid paths return local 400. Success reports local 200; failures forward numeric status or 500 and an error message.

Concrete unresolved application edges: caller-supplied onResize and theme getter bodies and frame/document provenance are outside this file; no recursive callback or third-party audit was performed. Numeric resize accepts NaN and infinities (NaN survives clamp). Repeated connect calls retain listeners until close, though connected prevents another accepted port. In-flight API work is not cancelled by close and can attempt replies to a closed port; asynchronous requests can overlap. No runtime outcome is asserted. Raw dynamic segments permit query/hash/percent/dot characters; canonical inventory mappings do not settle URL normalization or encoded-path routing. Unsupported verb/family combinations have no invented inventory mapping. Server authorization, backend compatibility, hosted plugin networking and concrete callback side effects remain outside this finite review.

Remaining target source review: none. Remaining acceptance: root review and the explicit adjacent application boundaries above. No runtime/tests, network/model/integration calls, data edits or shared inventory/ledger edits were performed.

Current SHA-256: `550c96b4caa8c2443410b45eec25e94a9fe9e97421f657dfa5201f973d4e035a`.

## Root review

Accepted finite current-source refresh after independently reading all target lines and API delegation. Checked current source hash and 21 original inventory tuples. Moved the rejected task-message tuple to `excluded_inventory`; 20 canonical candidates remain. Dynamic routing and adjacent callback limitations remain open. No runtime or global completion claim.
