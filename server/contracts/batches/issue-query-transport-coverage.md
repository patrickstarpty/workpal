# Issue query transport coverage

Parent completed bounded static review: four full query modules,45 factories and40 distinct client methods. Whole-source closure is not backend support.

| Factory | Inventory ID | Method | Route |
|---|---|---|---|
| issueTasksOptions | client:3116 | GET | `/api/issues/{id}/task-runs` |
| sourceContextPreviewOptions | client:1680 | GET | `/api/comments/{commentId}/sub-issue-preview` |
| issueTableGroupsOptions | client:1402 | POST | `/api/issues/table/groups` |
| issueTableRowPageOptions | client:1416 | POST | `/api/issues/table/rows` |
| issueTableFacetsOptions | client:1430 | POST | `/api/issues/table/facets` |
| issueListOptions | client:1344 | GET | `/api/issues` |
| projectGanttIssuesOptions | client:1344 | GET | `/api/issues` |
| sidebarIssuesOptions | client:1416 | POST | `/api/issues/table/rows` |
| issueDetailOptions | client:1612 | GET | `/api/issues/{id}` |
| issueIdentifierOptions | client:1612 | GET | `/api/issues/{id}` |
| childIssueProgressOptions | client:1817 | GET | `/api/issues/child-progress` |
| issueDuplicatesOptions | client:1785 | GET | `/api/issues/{id}/duplicates` |
| childIssuesOptions | client:1795 | GET | `/api/issues/{id}/children` |
| childrenByParentsOptions | client:1806 | GET | `/api/issues/children` |
| issueTimelineOptions | client:1926 | GET | `/api/issues/{id}/timeline` |
| issueCommentThreadOptions | client:1861 | GET | `/api/issues/{id}/comments` |
| issueReactionsOptions | client:1612 | GET | `/api/issues/{id}` |
| issueSubscribersOptions | client:2002 | GET | `/api/issues/{id}/subscribers` |
| issueEnvironmentsOptions | client:5536 | GET | `/api/issues/{id}/environments` |
| issueUsageOptions | client:3129 | GET | `/api/issues/{id}/usage` |
| issueAttachmentsOptions | client:4427 | GET | `/api/issues/{id}/attachments` |
| projectListOptions | client:4517 | GET | `/api/projects` |
| projectDetailOptions | client:4524 | GET | `/api/projects/{id}` |
| projectMembersOptions | client:4561 | GET | `/api/projects/{id}/members` |
| privateProjectOverviewOptions | client:4602 | GET | `/api/projects/private` |
| projectSubscriptionOptions | client:4569 | GET | `/api/projects/{id}/subscription` |
| workspaceListOptions | client:3391 | GET | `/api/workspaces` |
| workspaceBySlugOptions | client:3391 | GET | `/api/workspaces` |
| memberListOptions | client:3765 | GET | `/api/workspaces/{id}/members` |
| agentListOptions | client:2066 | GET | `/api/agents` |
| agentDetailOptions | client:2070 | GET | `/api/agents/{id}` |
| squadListOptions | client:5203 | GET | `/api/squads` |
| involvedSquadIdsOptions | client:5210 | GET | `/api/squads/involved` |
| squadMemberStatusOptions | client:5264 | GET | `/api/squads/{id}/members/status` |
| skillListOptions | client:3876 | GET | `/api/skills` |
| skillDetailOptions | client:3891 | GET | `/api/skills/{id}` |
| skillVersionsOptions | client:3967 | GET | `/api/skills/{id}/versions` |
| skillVersionDetailOptions | client:3977 | GET | `/api/skills/{id}/versions/{version}` |
| invitationListOptions | client:3796 | GET | `/api/workspaces/{id}/invitations` |
| shareLinkListOptions | client:3836 | GET | `/api/workspaces/{id}/share-links` |
| myInvitationListOptions | client:3806 | GET | `/api/invitations` |
| assigneeFrequencyOptions | client:1935 | GET | `/api/assignee-frequency` |
| workspaceMcpServersOptions | client:3441 | GET | `/api/workspaces/{id}/mcp-servers` |
| agentMcpServersOptions | client:3493 | GET | `/api/agents/{id}/mcp-servers` |
| issueStatusListOptions | client:4821 | GET | `/api/issue-statuses` |

## Parent branch and helper review

Both ordinary issueListOptions (empty filter plus declared sort) and Gantt use GET. Generic client listIssues separately uses POST when ids is truthy, including empty arrays; creator compatibility retry clears created_by_user_id, so does not recurse indefinitely. Table groups/rows/facets use readOnly POST. Earlier table claiming Gantt POST and generic factory POST is superseded.

All client methods were read completely in two bounded extracted-method outputs. Only generic listIssues has the recursive compatibility branch among these methods. Project-subscription parser projects a boolean; parseWithFallback validates and invokes the configured logger, which current platform implements with console. Schema/status transformations were already independently reviewed. WorkspaceBySlug shares list query then selects locally; cacheAgentResponse, skill assignments and status catalog build only local maps/cache. Catalog retry is an explicit injected query retry contract already mapped by retry-callback audit.

Prefix union is the union of every matching full query key above, including nested keys; no runtime observer enumeration.

issues/ws excludes timeline, tasks, reactions, subscribers, usage, attachments and source-context; environments ARE included. tableAll includes groups rows facets; timeline includes comment threads; projects/detail includes members and subscription; workspaces/agents includes detail; squads includes involved and member status; skills includes versions.

Key-only flat, my and assignee-group prefixes have no query factory in the fully reviewed issue target: empty factory union here. Trigger preview keys likewise have no factory here.

Inbox union is reused from chat-inbox-transport-coverage edges whose source is inbox/queries.ts; agents activity union is reused from core-query; auth fetch boundary evidence reused from active-web-auth.

React/Tanstack/Zod are library boundaries; callbacks are preserved verbatim in factories. No initialData in these four files.
