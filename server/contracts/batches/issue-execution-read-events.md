# Issue execution read events
Source-only Go router audit of the six requested GET endpoints. No execution integration or parity claim. Event disposition concerns domain events produced by these request chains, not concurrent scheduler work.
All routes first call `loadIssueForUser` (`server/go/internal/handler/handler.go:1083`): identity/workspace resolution, identifier or UUID issue lookup and project visibility checks. These authorize/read; they do not update the issue.

## GET /api/issues/{id}/workflow-handoff
PreviewWorkflowHandoff → applyIssueWorkflow → issueworkflow.ForProject/ForProjectRow → GetProjectInWorkspace, GetIssueWorkflow or DefaultFor/GetDefaultIssueWorkflow; OutsideProject also only reads the default. DefaultFor uses built-in steps on missing rows, never EnsureDefault. Parameters and copied issue are modified in memory. workflowHandoffBrief → workflowBriefInput → status/name lookups; assigneeActiveRuns → ListAssigneeRunsForHandoff. No dispatch or cancellation is called.

Event: `none`. No reachable event producer; writes and scheduler/reconciliation entry points are absent from this chain.

Evidence: `server/go/cmd/server/router.go:2198`, `server/go/internal/handler/issue_workflow.go:1397`, `server/go/internal/handler/handler.go:1083`, `server/go/internal/handler/issue_workflow_entry.go:48`, `server/go/internal/handler/issue_workflow_entry.go:247`, `server/go/internal/handler/issue_workflow_entry.go:332`, `server/go/internal/issueworkflow/issueworkflow.go:532`, `server/go/internal/issueworkflow/issueworkflow.go:545`, `server/go/internal/issueworkflow/issueworkflow.go:564`, `server/go/internal/issueworkflow/issueworkflow.go:581`, `server/go/pkg/db/queries/project.sql:29`, `server/go/pkg/db/queries/issue_workflow.sql:55`, `server/go/pkg/db/queries/issue_workflow.sql:11`, `server/go/pkg/db/queries/workflow_handoff.sql:18`.

## GET /api/issues/{id}/wakeups
ListIssueWakeups → workspaceMember → resolveActor → accessibleAgentIDs → ListAllAgents and visibility/invocation-target reads → ListIssueWakeups SQL. SQL joins agent, creator, filter actor and last task; no scheduler synchronization, expiry processing or reconciliation.

Event: `none`. No reachable event producer; writes and scheduler/reconciliation entry points are absent from this chain.

Evidence: `server/go/cmd/server/router.go:2206`, `server/go/internal/handler/issue_wakeup.go:132`, `server/go/internal/handler/handler.go:1083`, `server/go/internal/handler/agent_access.go:297`, `server/go/pkg/db/queries/wakeup.sql:4`.

## GET /api/issues/{id}/wakeups/{wakeupID}/runs
ListIssueWakeupRuns → GetIssueWakeup; validates workspace and issue ownership → ListWakeupRuns. SQL reads last ten task rows, JSON evidence/check-in note and comment existence; does not check in, trigger or reconcile a run.

Event: `none`. No reachable event producer; writes and scheduler/reconciliation entry points are absent from this chain.

Evidence: `server/go/cmd/server/router.go:2215`, `server/go/internal/handler/issue_wakeup.go:442`, `server/go/internal/handler/handler.go:1083`, `server/go/pkg/db/queries/wakeup.sql:56`, `server/go/pkg/db/queries/wakeup.sql:267`.

## GET /api/issues/{id}/system-wakeups
ListIssueSystemWakeups → listSystemWakeups → childDoneSystemWakeup → status category reads, ListChildIssues, workspace/prefix reads, GetSystemWakeup, optional assignee name reads. Missing rule returns computed workspace defaults and empty ID/revision. No EnsureChildDoneRule, BackfillChildDoneRules, UpdateChildDoneRule or child-event processing is reached.

Event: `none`. No reachable event producer; writes and scheduler/reconciliation entry points are absent from this chain.

Evidence: `server/go/cmd/server/router.go:2216`, `server/go/internal/handler/issue_system_wakeup.go:177`, `server/go/internal/handler/handler.go:1083`, `server/go/internal/handler/issue_system_wakeup.go:165`, `server/go/internal/handler/issue_system_wakeup.go:62`, `server/go/pkg/db/queries/issue.sql:686`, `server/go/pkg/db/queries/system_wakeup.sql:1`, `server/go/pkg/db/queries/workspace.sql:28`.

## GET /api/issues/{id}/active-task
GetActiveTaskForIssue → ListActiveTasksByIssue → taskToResponse → hydrateTaskAttributions → GetUsersByIDs and avatar URL formatting. Query failure becomes empty task list. No runtime refresh, stale-task reconciliation or scheduler sync.

Event: `none`. No reachable event producer; writes and scheduler/reconciliation entry points are absent from this chain.

Evidence: `server/go/cmd/server/router.go:2218`, `server/go/internal/handler/daemon.go:6310`, `server/go/internal/handler/handler.go:1083`, `server/go/internal/handler/agent.go:716`, `server/go/pkg/db/queries/agent.sql:2462`, `server/go/pkg/db/queries/user.sql:9`.

## GET /api/issues/{id}/task-runs
ListTasksByIssue validates view/scope/active. family → ListActiveTasksByIssueFamily (cap+1), in-memory summaries and truncation header, immediate return. subtree → ListTasksByIssueSubtree; issue → ListActiveTasksByIssue or ListTasksByIssue. Other paths → visibleTaskHistory/taskToResponse → hydrateTaskSupplementMetadata (ListTaskSupplementMetadata, actor/originator and invocation permission reads only) → hydrateTaskAttributions/GetUsersByIDs. Non-active history → hydrateTaskUsage/ListIssueTaskUsage or hydrateSubtreeTaskUsage/ListTaskUsageByIDs. Subtree → redactHiddenProjectTasks → hiddenProjects and projectaccess.TasksProjects reads; timeline trims response fields in memory. No supplement delivery, usage recording or task-service mutation.

Event: `none`. No reachable event producer; writes and scheduler/reconciliation entry points are absent from this chain.

Evidence: `server/go/cmd/server/router.go:2225`, `server/go/internal/handler/daemon.go:6437`, `server/go/internal/handler/handler.go:1083`, `server/go/internal/handler/task_supplement.go:20`, `server/go/internal/handler/agent.go:716`, `server/go/internal/handler/daemon.go:6587`, `server/go/internal/handler/daemon.go:6628`, `server/go/internal/handler/task_project_privacy.go:18`, `server/go/pkg/db/queries/agent.sql:2745`, `server/go/pkg/db/queries/agent.sql:2750`, `server/go/pkg/db/queries/agent.sql:2462`, `server/go/pkg/db/queries/agent.sql:2472`, `server/go/pkg/db/queries/supplement.sql:197`, `server/go/pkg/db/queries/task_usage.sql:27`, `server/go/pkg/db/queries/task_usage.sql:55`.

## Parent review
Checked preview versus workflow dispatch, missing system-wakeup defaults versus persistent rule creation, wakeup list/run SELECTs, active task rendering and history enrichment branches. Integrated six event dispositions; route statuses unchanged. Source audit does not claim Python support or Go differential parity.
