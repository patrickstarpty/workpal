# Issue menu transport coverage

1-104: imports and injected props; no transport execution.

105-199: status handoff opens modal when changed workflow step hands off, else updateField; deletion permission; unread hooks; task query enabled !sidebar overrides factory enabled; cached workdir and identifier clipboard with error/success toasts.

200-325: full rename/create/quick actions; both variants status and priority; assignee picker delegates updateField/onClose.

326-388: full start/due today,+1,+7 and conditional null clear updates.

389-480: navigation, pin, optional locate, inbox child, sidebar read/unread, copy callbacks; sidebar stop child requires callback.

481-545: full parent/set/add/duplicate (workflow allows cancelled), plugin children and permission-disabled delete confirmation passing fallback path.

546-639: ItemLabel local presentation; SubmenuPanel minHeight and propagation except Escape/Tab; AssigneeName actor hook; active quick-action catalog and runner; StopRunItems snapshot running selection and injected onStopRun(task).

Deletion: memberListOptions; agentListOptions enabled role == member. Status label/catalog hooks: issueStatusListOptions(true), enabled Boolean(wsId). Workflow list enabled Boolean(wsId), project list enabled Boolean(wsId)&&Boolean(projectId).

Unread key issue-unread/wsId, enabled sidebar issue.id (full empty string). Writes POST read/unread: cancel, snapshot, optimistic cache, rollback on error, settled invalidate same key; retry failures<2 on unknown/5xx, exponential capped delay.

Task query issueTasksOptions(issue.id,false,timeline): client:3116 view=timeline, stale30000/focus true. Quick-action catalog default includeArchived=false; active filter; runner mutateAsync POST then outcome toast, invocation_not_allowed or general error toast.

Actor names: member/agent/squad queries; plugin installations enabled feature flag && wsId.length>0. Agent catalog include_archived=true/workspace_id and conditional 30s online/unstable polling. StopRunItems snapshot stale30000/gc300000/focus true, selects running issue tasks, no own cancel write.

Conditional concrete useIssueActions provider: null guards; updateField run-confirm gate then surface update or useUpdateIssue (reused surface/cache/query evidence); ordinary field/removeParent writes PUT client:1771. removeParent clears parent_issue_id and stage. Rename/create/set-parent/add-child/duplicate/delete open modal only. Navigation/copy local. Pin mutations remain dependency boundary; arbitrary injected actions are not certified.

Boundaries: AssigneePickerPanel, InboxRestoreMenuItem, PluginHookMenuItems, PluginModalMenuItems, modal implementations, pin dependencies, injected onStopRun/onShowInSidebar, arbitrary actions implementations.

Quick-action settled refetch union: timeline GET, task-runs GET (including history suffix), quick-action catalog GET (including archived variant). Unread settled union: unread paginated GET. These are conditional observer candidates. Exact tuples and hashes are in JSON; captured code is separate. Full target read does not certify descendants. No comments used as proof. No backend/global claims.

Root accepted bounded menu source scope after quick-action runner/stop child checks. Resolved default provider pin dependency: togglePin :175 checks issueId then POST client:5184 or DELETE client:5191; create appends cache on success, delete snapshots/filters/rolls back, both settle invalidate user/workspace pin list GET client:5180. Reorder not invoked; arbitrary injected replacements remain unverified. Supporting hashes recorded.
