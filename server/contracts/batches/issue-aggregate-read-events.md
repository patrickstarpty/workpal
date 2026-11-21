# Issue aggregate read business-event audit

Scope: seven registered Go handlers only; Task 1 source audit. No runtime/parity execution, Python implementation, middleware-wide event audit, or database mutation is claimed. Registration is server/go/cmd/server/router.go:2169–2179. All seven dispositions are **none**, based on reachable operations, not HTTP method.

## Shared reachable helpers

`requestHiddenProjects` (server/go/internal/handler/project_access.go:71) → hiddenProjects (:21) → resolveActor (server/go/internal/handler/handler.go:898); optional GetAgent/GetAgentTask reads terminate at server/go/pkg/db/queries/agent.sql:26 and :764. Agent-run visibility additionally reads ListPrivateProjectIDs and the same task/agent rows. ForMember/ForPrincipals (server/go/internal/projectaccess/projectaccess.go:104, :122) read private/hidden project IDs and membership: server/go/pkg/db/queries/project_member.sql:1, :7 and member.sql:15. Hidden sets and RunPrincipals are memory-only.

`resolveWorkspaceID` (server/go/internal/handler/handler.go:957) → ResolveWorkspaceIDFromRequest (server/go/internal/middleware/workspace.go:68): context/header/query selection or GetWorkspaceBySlug SELECT (server/go/pkg/db/queries/workspace.sql:32). `getIssuePrefix` (handler.go:1234) → GetWorkspace SELECT (workspace.sql:28).

`terminalIssueStatusKeys` (server/go/internal/handler/issue_status.go:49) → ExpandCategories (server/go/internal/issuestatus/issuestatus.go:700) → ListIssueStatusKeysByCategories SELECT (server/go/pkg/db/queries/issue_status.sql:134). Resolver.Category/Name lazily load an in-memory catalog via Resolver.load (:583) → ListIssueStatusEntries SELECT (issue_status.sql:20); they never call Ensure (:370). Thus lazy loading is not lazy creation.

`labelsByIssue` (server/go/internal/handler/issue.go:559) → ListLabelsForIssues SELECT (server/go/pkg/db/queries/issue_label.sql:166). newStatusCategoryFiller (:376) → loadDuplicateOriginals (:430) / fillDuplicateOf (:456) → ListIssueRefsInWorkspace SELECT (server/go/pkg/db/queries/issue.sql:390), plus the read-only status resolver. Missing originals are omitted from response, not repaired in storage.

## GET /api/issues/search

Registered handler `SearchIssues` at server/go/internal/handler/issue.go:1156. Search SELECT builder → runSearchQuery (search.go:111), transaction-local timeout/work_mem/read-only settings, Query and Commit; terminalIssueStatusKeys → ExpandCategories; prefix and status/duplicate enrichment. SQL terminal: server/go/internal/handler/issue.go:813. All routes traverse the visibility helpers above.

Write/read-marker/lazy-create check: Search SELECT builder → runSearchQuery (search.go:111), transaction-local timeout/work_mem/read-only settings, Query and Commit; terminalIssueStatusKeys → ExpandCategories; prefix and status/duplicate enrichment. Reachable helpers only read or construct response data; no business writes, read-marker updates, lazy creation, publish, enqueue, or service event producer.

## GET /api/issues/child-progress

Registered handler `ChildIssueProgress` at server/go/internal/handler/issue.go:2777. terminalIssueStatusKeys → ExpandCategories → ListIssueStatusKeysByCategories; ChildIssueProgress SELECT aggregates issue counts by parent. SQL terminal: server/go/pkg/db/queries/issue.sql:736. All routes traverse the visibility helpers above.

Write/read-marker/lazy-create check: terminalIssueStatusKeys → ExpandCategories → ListIssueStatusKeysByCategories; ChildIssueProgress SELECT aggregates issue counts by parent. Reachable helpers only read or construct response data; no business writes, read-marker updates, lazy creation, publish, enqueue, or service event producer.

## GET /api/issues/pull-requests

Registered handler `ListIssuePullRequestSummaries` at server/go/internal/handler/github.go:1209. ListIssuePullRequestSummaries SELECT UNION ALL joins GitHub and VCS PR/link/issue tables; serialization only; no snapshot refresh callback. SQL terminal: server/go/pkg/db/queries/github.sql:206. All routes traverse the visibility helpers above.

Write/read-marker/lazy-create check: ListIssuePullRequestSummaries SELECT UNION ALL joins GitHub and VCS PR/link/issue tables; serialization only; no snapshot refresh callback. Reachable helpers only read or construct response data; no business writes, read-marker updates, lazy creation, publish, enqueue, or service event producer.

## GET /api/issues/children

Registered handler `ListChildrenByParents` at server/go/internal/handler/issue.go:2699. Empty parent input returns immediately; otherwise ListChildrenByParents SELECT → filterVisibleIssues → getIssuePrefix → labelsByIssue → Resolver.Category. SQL terminal: server/go/pkg/db/queries/issue.sql:697. All routes traverse the visibility helpers above.

Write/read-marker/lazy-create check: Empty parent input returns immediately; otherwise ListChildrenByParents SELECT → filterVisibleIssues → getIssuePrefix → labelsByIssue → Resolver.Category. Reachable helpers only read or construct response data; no business writes, read-marker updates, lazy creation, publish, enqueue, or service event producer.

## GET /api/issues/grouped

Registered handler `ListGroupedIssues` at server/go/internal/handler/issue.go:2086. Dynamic ranked SELECT with window counts and row numbers → DB.Query → labelsByIssue → getIssuePrefix → newStatusCategoryFiller; optional category filter uses ExpandCategories. SQL terminal: server/go/internal/handler/issue.go:2484. All routes traverse the visibility helpers above.

Write/read-marker/lazy-create check: Dynamic ranked SELECT with window counts and row numbers → DB.Query → labelsByIssue → getIssuePrefix → newStatusCategoryFiller; optional category filter uses ExpandCategories. Reachable helpers only read or construct response data; no business writes, read-marker updates, lazy creation, publish, enqueue, or service event producer.

## GET /api/issues/unread

Registered handler `ListIssueUnread` at server/go/internal/handler/issue_unread.go:29. requireUserID/context workspace → ListIssueUnread SELECT with lateral latest live comment and cursor pagination; does not call setIssueUnread or MarkIssueRead. SQL terminal: server/go/pkg/db/queries/issue_unread.sql:23. All routes traverse the visibility helpers above.

Write/read-marker/lazy-create check: requireUserID/context workspace → ListIssueUnread SELECT with lateral latest live comment and cursor pagination; does not call setIssueUnread or MarkIssueRead. Reachable helpers only read or construct response data; no business writes, read-marker updates, lazy creation, publish, enqueue, or service event producer.

## GET /api/issues/subscribed

Registered handler `ListSubscribedIssueIDs` at server/go/internal/handler/subscriber.go:139. requireUserID/context workspace → ListSubscribedIssueIDs SELECT active member subscriptions joined to issues; does not call SubscribeToIssue or create subscribers. SQL terminal: server/go/pkg/db/queries/subscriber.sql:302. All routes traverse the visibility helpers above.

Write/read-marker/lazy-create check: requireUserID/context workspace → ListSubscribedIssueIDs SELECT active member subscriptions joined to issues; does not call SubscribeToIssue or create subscribers. Reachable helpers only read or construct response data; no business writes, read-marker updates, lazy creation, publish, enqueue, or service event producer.

## Parent review
Parent checked all seven handlers, the unread SELECT versus separate marker mutation, search transaction-local read-only settings, grouped ranked SELECT and enrichment, and bulk child/PR response paths. Integrated seven event records into routes.json; statuses remain pending. No Go/Python differential execution claimed.
