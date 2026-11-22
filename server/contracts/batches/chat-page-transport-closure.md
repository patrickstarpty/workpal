# Chat page transport closure

Finite 499-line page reviewed; dependency closure remains partial. `whole_source: true` applies to the page text, not its transitive dependency graph. Hashes and separate snapshots are in the JSON. Static evidence only.

Page 73-91: controller activity requires current chat route and live workspace equality. Pending/failure observers enabled:false, staleTime Infinity; no HTTP. Timeout uses absolute expiry, clears matching message only, clears timer on cleanup. Failure toast deduplicates nonce and clears only matching signal.

Page 100-138: composing reset reads live store. Both URL/store effects guard route and live workspace; URL effect sets session only on difference; store effect replaces chat URL with session or base using live state. No request is inherent in replace; downstream adapter destination execution is outside this proof.

Page 151-195: select/archive/new supersede pending agent intent. Active archive selects next on desktop or clears compact pane before archive callback; other archive leaves selection. Project equality skips; delegates controller, then marks compose for absent current session or nonnull target.

Page 199-219: fresh handler ref updated every effect; memoized chat context supplies archive/project callbacks. Register hook registers/unregisters token and unmount cleanup; chat context has no recent-visit recording branch.

Page 231-250: guarded agent intent resets consumed ref when absent, waits while unresolved, consumes once before start, replaces base route; settled denial toasts and consumes. Explicit back clears session and compose; unlike selection/archive/new it does not supersede agent intent.

Page 342-366: older messages delegates controller fetch; quick action sends action.prompt; regeneration requires session and passes message.id. Mutation optimistic pending marker has absolute expiry; HTTP error restores previous marker. No abort signal supplied by these adapters.

Annotations hook always observes nonempty-session infinite messages query even if annotation enabled=false. Query staleTime Infinity, limit 50, cursor from has_more/next_cursor; factory does not forward AbortSignal. Initial-page 404 falls back to legacy full list, cursor 404 propagates. Edit loads older pages with cancelRefetch:false until found/exhausted/page error; attempt nonce prevents stale continuation. Up to 30 animation frames reveal source; draft-key cleanup cancels retry, not HTTP.

Comment annotation hook is executed dependency: local draft store and DOM selection, highlights, MutationObserver, pointer/key/focus listeners; cleanup removes observers/listeners/highlights. Notes save/update/remove through draft store. Rendered AnnotationComposer/CommentSelectionBubble implementations are bounded descendants. Selection helpers and draft persistence internals remain separate edges.

Wakeup hook always observes session factory; empty session disables query and returns EMPTY; staleTime Infinity, no polling or signal forwarding here. API converts 404 to empty list and parses fallback. Strip mutation descendants are not implied by hook read.

Project planner: active session without resolved currentSession awaits; null target detaches current via mutation; nonnull target starts fresh with current agent and clears active session; absent session changes draft project. Mutation cancels session queries, snapshots and optimistically patches workspace session cache; error rolls back, settled invalidates sessions. Request body project_id:null for page detach path.

Navigation context returns provider adapter and throws if absent; provider wraps push/replace in React transition. Page pushes new-agent path; replaces chat path for synchronization/intent. No direct HTTP in page navigation statements; platform adapter and destination loaders remain separate.

Page 403-433 wires send/stop/restore/starter to controller, project wrapper and annotation object. Reuse chat-input/composer evidence for concrete send and stop only; no whole-controller assertion. Queue callbacks and archive callback are named remaining edges. Compact and desktop conditional descendants do not gate invocation of page-own hooks.

Remaining edges:

- Controller queue send-now/edit/remove/clear and archive/advance implementations require separate bounded callback proof; controller query fanout and project support/agent/project loading are not whole-controller covered.
- Navigation platform adapter, workspace path/platform/store internals and destination loaders not traced beyond inspected adapter context.
- Annotation selection helpers and draft persistence internals; rendered AnnotationComposer, CommentSelectionBubble and other descendant implementations.
- ChatThreadList, ChatSessionHeader, NewChatButton, message list, app requests, wakeup strip, queue, banners and shared layout descendant transports remain bounded exclusions.
- Legacy listChatMessages endpoint adapter is reused via prior composer evidence, not newly whole-source inspected. Global invalidation fanout, realtime producers, backend support and runtime behavior are not claimed.

Root accepted chat-queue-archive-transport-closure.json after independent hook read and hash/tuple verification. This closes the previously listed queue/archive branch gap. Context/annotation support remains pending. Root also read store setOpen, setActiveSession, dismissChatFromBar, setChatSize and setExpanded: injected StorageAdapter persistence plus local state; no direct HTTP. Native/custom adapters remain explicit host boundaries. No whole store or controller claim.

Root accepted chat-context-annotation-transport-closure.json after source/hash/tuple review. This supersedes the context and annotation helper gaps above. Annotation disabling does not disable the session message query; stale edit continuation is ignored but pagination requests are not aborted. Full invoked controller closure is still pending, so host ledger status is unchanged.

Root accepted bounded host target after controller proof integration, source hash checks, specific callback review and exact host adapter tuple normalization. Historical invoked-hook gaps are closed by the attached proofs. Descendant rendering, native host adapters, destination loaders and global runtime/backend coverage remain excluded. No whole supporting-module promotion.
