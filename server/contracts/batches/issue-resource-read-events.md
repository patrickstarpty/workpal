# Issue resource GET event audit

Scope: six upstream Go router handlers; source audit only. No runtime integrations were executed. `required` means a reachable conditional event producer, not an event on every request.

Shared issue access: server/go/internal/handler/handler.go:1083 resolves identifiers or GetIssueInWorkspace and enforces project visibility. Authorization/read-selector telemetry is outside business-event disposition.

## GET /api/issues/{id}/usage

loadIssueForUser → GetIssueUsageSummary → response. SELECT aggregates task/task_usage token, cost and coverage counts; no lazy write or producer.

Route and SQL leaves (only this route’s named operations):

- `server/go/cmd/server/router.go:2226`
- `server/go/internal/handler/daemon.go:6820`
- `server/go/internal/handler/handler.go:1083`
- `server/go/pkg/db/queries/task_usage.sql:84`

## GET /api/issues/{id}/metadata

loadIssueForUser → parseIssueMetadata → response. Metadata comes from the loaded issue JSON; no metadata mutation or event.

Route and SQL leaves (only this route’s named operations):

- `server/go/cmd/server/router.go:2235`
- `server/go/internal/handler/issue_metadata.go:148`
- `server/go/internal/handler/handler.go:1083`

## GET /api/issues/{id}/environments

loadIssueForUser → three snapshot/control/config SELECTs → environmentControlChecker (membership and runtime reads) → response projections. Time-derived unreachable/timeout state is presentation only; this GET does not start/stop an environment or enqueue a command.

Route and SQL leaves (only this route’s named operations):

- `server/go/cmd/server/router.go:2240`
- `server/go/internal/handler/issue_environment.go:293`
- `server/go/internal/handler/handler.go:1083`
- `server/go/pkg/db/queries/issue_environment.sql:50`
- `server/go/pkg/db/queries/issue_environment.sql:116`
- `server/go/pkg/db/queries/issue_environment.sql:141`

## GET /api/issues/{id}/environment-commands/{commandId}

loadIssueForUser → UUID validation → issue/workspace-scoped GetIssueEnvironmentCommand SELECT → issueEnvironmentCommandToResponse(time.Now). Expiry is projected, not persisted; no claim/result write.

Route and SQL leaves (only this route’s named operations):

- `server/go/cmd/server/router.go:2245`
- `server/go/internal/handler/issue_environment_control.go:364`
- `server/go/internal/handler/handler.go:1083`
- `server/go/pkg/db/queries/issue_environment.sql:112`

## GET /api/issues/{id}/pull-requests

loadIssueForUser → workspace and linked GitHub SELECTs → MaybeEnqueueOnView for each GitHub row → VCS SELECT → decidePRAutoComplete (linked states, disabled flag, status catalog and project workflow reads) → response. Missing/stale/head-mismatched snapshots enqueue a deduplicated background refresh when enabled. worker → process → FetchPRSnapshot (external GitHub) → address lookup → applySnapshot transaction: head-guarded snapshot UPDATE, check-run DELETE/INSERT, commit → onApplied → broadcastPRSnapshotApplied → PR/link SELECTs → EventPullRequestUpdated publish. Current response can be stale; enqueue occurs before later VCS/decision errors. VCS rows have no view refresh here. Decision computation does not apply auto-completion.

Route and SQL leaves (only this route’s named operations):

- `server/go/cmd/server/router.go:2246`
- `server/go/internal/handler/github.go:1125`
- `server/go/internal/handler/handler.go:1083`
- `server/go/pkg/db/queries/workspace.sql:28`
- `server/go/pkg/db/queries/github.sql:146`
- `server/go/pkg/db/queries/vcs.sql:105`
- `server/go/pkg/db/queries/pr_automation.sql:44`
- `server/go/pkg/db/queries/pr_automation.sql:5`
- `server/go/pkg/db/queries/github_snapshot.sql:10`
- `server/go/pkg/db/queries/github_snapshot.sql:19`
- `server/go/pkg/db/queries/github_snapshot.sql:34`
- `server/go/pkg/db/queries/github_snapshot.sql:39`
- `server/go/pkg/db/queries/github_snapshot.sql:147`
- `server/go/pkg/db/queries/github.sql:263`
- `server/go/internal/integrations/ghsnapshot/refresh.go:204`
- `server/go/internal/integrations/ghsnapshot/refresh.go:236`
- `server/go/internal/integrations/ghsnapshot/refresh.go:410`
- `server/go/internal/handler/handler.go:579`
- `server/go/internal/handler/github.go:1249`
- `server/go/internal/handler/github.go:1263`
- `server/go/internal/handler/pr_auto_complete.go:173`

## GET /api/comments/{commentId}/sub-issue-preview

workspace membership → commentInHiddenProject → BuildSourceContext → anchor SELECT → BuildSourceIssueSnapshot (issue/workspace/attachment SELECTs) → recursive ancestor/history SELECTs → buildSourceContextCommentSnapshots (attachment SELECT and author user/agent SELECTs) → limits, canonical digest and capture token → response. No capture persistence, object cloning, model execution or task enqueue; creation is a separate POST.

Route and SQL leaves (only this route’s named operations):

- `server/go/cmd/server/router.go:2436`
- `server/go/internal/handler/source_context.go:430`
- `server/go/internal/handler/handler.go:1083`
- `server/go/pkg/db/queries/comment.sql:481`
- `server/go/pkg/db/queries/issue.sql:97`
- `server/go/pkg/db/queries/workspace.sql:28`
- `server/go/pkg/db/queries/attachment.sql:59`
- `server/go/pkg/db/queries/comment.sql:846`
- `server/go/pkg/db/queries/comment.sql:874`
- `server/go/pkg/db/queries/attachment.sql:70`
- `server/go/pkg/db/queries/user.sql:1`
- `server/go/pkg/db/queries/agent.sql:46`
- `server/go/internal/service/source_context.go:404`
- `server/go/internal/service/source_context.go:271`
- `server/go/internal/service/source_context.go:204`

## Residual limits

Static source conclusions cover handler-level business effects. Shared authentication, access checks, status/workflow resolution and runtime read selection may perform additional SELECTs and telemetry; their full middleware query inventory is not reproduced. Background refresh requires an enabled manager, running worker, accepted queue entry, successful GitHub fetch, matching head and committed write; callback lookup failures can suppress publication. No claim of live external behavior or measured results.

## Parent review
Parent verified snapshot enqueue, enabled/TTL gates, head-guarded transactional updates and callback publication after commit, as well as the other five handler paths. Integrated six dispositions without changing route status. Required-event producer/consumer fields and implementation evidence remain open for the conditional PR refresh; external integration is not enabled by this audit. Found checker gap: GET required-event metadata currently bypasses validation; separate regression/fix assigned.
