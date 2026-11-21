# Issue detail helper sections

Finished finite static section audit. Main IssueDetail body excluded; whole_source=false.

Source SHA-256: afbc077580392ae3b7ec41e28c087ee215dc3103c426f505fee9d96f5d8f9f1a

- 1-100: Imports only; imported main-body resources are not invoked helper requests.
- 101-200: Remaining imports; no observer activation from imports.
- 201-300: Memento key; subscriber search, member deduplication and active-agent filtering.
- 301-400: Subscriber callbacks pass current subscribed boolean; disabled until authoritative data; date/status/activity formatting.
- 401-500: Activity formatting handles assignment/date/duplicate/task/environment events without writes.
- 501-600: Duplicate link derivation and optional property visibility.
- 601-700: Stable stage grouping, identity equality and timeline flattening; jump callback.
- 701-800: Skeleton and ActivityBlock parent-owned expansion with latest-eight truncation.
- 801-900: Activity icons/text/chips/actor display are presentation; no mutation.
- 901-1000: SubIssueRow hooks, provider selection and update callback with toast failure.
- 1001-1100: Status/date/assignee pickers delegate updates; navigation and label/custom/progress presentation.
- 1101-1200: Assignee avatar; display preference store selectors and builtin toggles.
- 1201-1300: Custom preference toggle; props document injected host callbacks and nodes.
- 1301-1400: Notfound navigation and load error supplied retry; no own query.
- 1401-1485: Skeleton reads saved layout and initial sidebar state; no issue read.
- 4554-4580: Trailing actions adapt sidebar callback; workflow row mounts project workflow hook and conditional card.

- **SubscriberPopoverContent**: search state only; onSelect calls injected toggleSubscriber(id,type,isSubbed); no subscription endpoint owned here
- **ActivityBlock**: useWakeupText presentation; onToggle/onToggleShowOlder injected; ActivityText workspace navigation; TimelineHandoff descendant boundary
- **SubIssueRow**: useUpdateIssue; handleUpdate merges child.id and picker patch, reports error toast; selection provider owns toggle; useIssueStatuses workspace-gated observer; pickers/context menu/avatar/activity indicator descendants retain own proofs
- **SubIssueDisplayPopover**: global persisted Zustand workpal_sub_issue_display via defaultStorage; builtin boolean and custom ID membership toggles; merge preserves new defaults
- **IssueNotFound**: i18n/paths/header hooks; backOrReplace(paths.issues()); no failed query observer
- **IssueLoadError**: same navigation hooks; supplied onRetry promise invoked void; disabled/busy while retrying; request belongs to host
- **IssueDetailSkeleton**: useDefaultLayout(layoutId), initial sidebar open; host leading/trailing ReactNodes opaque
- **IssueDetailActionsDropdown**: useShowInSidebar(issue) callback supplied only when locateInSidebar; shared dropdown/menu proof owns actions
- **IssueWorkflowPropRow**: workspace context -> useProjectWorkflow -> workflows observer enabled wsId; projects observer enabled wsId && projectId; null suppresses IssueFlowCard; card descendants outside section

Exact inventory: PUT /api/issues/{id}; GET /api/projects; GET /api/issue-workflows; GET /api/issue-statuses. JSON preserves inventory IDs, gates and separate source snapshots. No move endpoint inferred from the shared hook. Callback-owned subscription and retry requests are excluded.

- IssueDetail main body 1486-4553 excluded; no whole-file completion claim
- Imports alone create no request inventory; comment-card/inline proof reused only as explicit imported boundaries
- Injected subscriber/retry/jump/expansion callbacks and leading/trailing nodes belong to parent/provider; no guessed requests
- useIssueSurfaceSelection requires ancestor provider; helper does not create it
- StatusPicker, DueDatePicker, AssigneePicker, ActorAvatar, IssueActionsContextMenu, IssueActionsDropdown, IssueAgentActivityIndicator, TimelineHandoff, IssueFlowCard and navigation/platform internals retain descendant/provider boundaries
- useUpdateIssue cache cancellation/optimism/rollback/reconciliation/invalidation reuse exact mutation proof; refetch superset is not an actual request tuple trace
- No runtime/tests/network/model/data/git or shared ledger changes
