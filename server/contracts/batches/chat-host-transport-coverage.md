# Chat host transport audit

Status: partial; root review required. `whole_source` is boolean false for both hosts; source snapshots are separate. No runtime, backend, integration or global coverage claim.

Page controller activity requires current chat route and live workspace slug equality. URL-to-store and store-to-URL effects repeat those guards and read live store state. Agent intent waits for permitted agent resolution, consumes settled denial, and explicit selection/archive/new-chat supersedes intent.

Page project callback skips identical project; delegates handleProjectChange, then preserves compact compose for new session/project choice. Controller inspected project switch has awaitSession, detachCurrent mutation, startFreshChat and setDraftProject branches; entire controller source remains separate.

Window controller isActive=isOpen; visibility is isOpen && (isExpanded || boundsReady) && contentReady. inert/aria-hidden and input hidden do not unmount host hooks. Only ChatWindowMessages is gated by isOpen. SessionDropdown pendingChatTasksOptions has no enabled/open gate and staleTime Infinity; no host interval polling.

Own annotation hook invokes chatMessagesPageOptions for nonempty session regardless of annotation enabled flag; enabled only gates useCommentAnnotations. Editing restored annotations may fetchNextPage repeatedly until source found/history exhausted/error; attempt nonce suppresses stale completion; 30 animation-frame reveal retries.

Window context hook parses issue/project/inbox route; current issue/project query enabled by route type; up to eight recent detail queries hydrate entries with staleTime 30000, with no isOpen gate. These executed own hooks are dependencies, not descendant exclusions.

Quick-actions pending/failure observers are enabled:false client caches. Timeout clears only matching message at absolute deadline; failure toast clears only matching nonce. Wakeup hook observes session wakeups independently of visibility.

Focus hook blurs contained active element when closed and bumps nonce on open transition/newChatRequest. Reveal uses 300ms fallback and cleanup. Resize/anchor/visual viewport hooks only DOM/store geometry; observers/listeners cleaned by effects. Formatting uses locale/date only.

Both hosts wire ChatInput send/stop/restore/starter callbacks directly to controller; page project uses wrapper, window direct. ChatQueue send-now/edit/remove/clear go to controller. Quick action sends prompt; page regeneration requires active session. Window agent pick delegates handleSelectAgent; new button handleNewChat; history selection handleSelectSession; archive advances then archiveSession.

SessionDropdown rename trims input and skips blank/unchanged before useUpdateChatSession. Running rows expose stop confirmation rather than rename/archive; stopping disables confirmation buttons. Stop optimistically removes pending task, empties pendingTask(session), invalidates messages and messagesPage, calls cancelTaskById, removes restored message when restore_to_input, then invalidates pendingTasks and pendingTask in finally.

Conservative invalidation union for history stop: messages(session), messagesPage(session), pendingTasks(workspace), pendingTask(session); requests listChatMessages/listChatMessagesPage (including fallback), listPendingChatTasks/getPendingChatTask can refetch active enabled observers. Rename additionally invalidates sessions via mutation. Do not narrow to currently visible host.

Descendant boundaries are distinct: ChatInput (reuse input/composer proofs), ChatMessageList, ChatWindowMessages, ChatQueue, ChatWakeupStrip, ChatAppRequests, ChatThreadList, ChatSessionHeader, NewChatButton, EmptyState and shared UI/avatar controls. Their entire implementations are not claimed by host coverage.

Open: Finish untruncated host review and own dependency closure including navigation/register context/comment annotations/query and mutation factories. Validate exact client method anchors against source; candidates are not request-edge closure. Entire use-chat-controller.ts proof remains separate; callback wiring alone does not cover it.
