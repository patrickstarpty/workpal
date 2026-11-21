# Issue GET event audit

Scope: approved Task 1 source inventory only. Exactly eight routes; no runtime parity claim. Inherited authentication/session behavior is outside the issue-domain producer decision.

## Shared chain

Registrations and issue loading: server/go/cmd/server/router.go:2165, server/go/internal/handler/handler.go:1083, server/go/internal/handler/handler.go:1234, server/go/internal/handler/project_access.go:18, server/go/internal/issuestatus/issuestatus.go:583. Identifier/workspace/project checks and prefix lookup read stored state. GET does not imply read-only; the reachable issue-domain chains below contain no event publication or domain mutation.

Status resolver lazily loads an in-memory catalog (ListIssueStatusEntries), not persistent seeding. Ensure at server/go/internal/issuestatus/issuestatus.go:370 is a separate writer; these handlers do not call it. Subscriber delivery preferences and owner hydration are reads; absent preferences are defaults, not inserts. Source-context detail rebuilds comparison snapshots in memory, not capture persistence. Attachment responses construct URLs; they do not upload, link or delete objects. Thread completion fetches missing rows; it does not repair stored comments.

## GET /api/issues

Handler: server/go/internal/handler/issue.go:1347 through line 1931. Event disposition: none.

## GET /api/issues/{id}

Handler: server/go/internal/handler/issue.go:2576 through line 2641. Event disposition: none.

## GET /api/issues/{id}/comments

Handler: server/go/internal/handler/comment.go:349 through line 1095. Event disposition: none.

## GET /api/issues/{id}/timeline

Handler: server/go/internal/handler/activity.go:156 through line 332. Event disposition: none.

## GET /api/issues/{id}/subscribers

Handler: server/go/internal/handler/subscriber.go:45 through line 137. Event disposition: none.

## GET /api/issues/{id}/attachments

Handler: server/go/internal/handler/file.go:676 through line 739. Event disposition: none.

## GET /api/issues/{id}/children

Handler: server/go/internal/handler/issue.go:2643 through line 2690. Event disposition: none.

## GET /api/issues/{id}/duplicates

Handler: server/go/internal/handler/issue_duplicate.go:167 through line 225. Event disposition: none.

## Helper and SQL source index

The following exact locations identify enrichment and query calls. SQL definitions are indexed below, including generated query bodies; list endpoint also executes dynamic SELECT/count SQL at server/go/internal/handler/issue.go:1846 and :1901. Existing issues-core, comments and files contracts remain transport references.

- server/go/internal/handler/issue.go:440: ListIssueRefsInWorkspace

- server/go/internal/handler/issue.go:564: ListLabelsForIssues

- server/go/internal/handler/issue.go:1456: ListOpenIssues

- server/go/internal/handler/issue.go:2596: ListIssueReactions

- server/go/internal/handler/issue.go:2608: ListAttachmentsByIssue

- server/go/internal/handler/issue.go:2649: ListChildIssues

- server/go/internal/handler/issue.go:2737: ListChildrenByParents

- server/go/internal/handler/issue.go:2923: GetSquadInWorkspace

- server/go/internal/handler/issue.go:2963: GetAgentInWorkspace

- server/go/internal/handler/issue.go:3028: GetProjectInWorkspace

- server/go/internal/handler/issue.go:3056: GetIssueInWorkspace

- server/go/internal/handler/issue.go:3435: GetIssueInWorkspace

- server/go/internal/handler/issue.go:3477: GetIssueInWorkspace

- server/go/internal/handler/issue.go:3613: GetAgentTask

- server/go/internal/handler/issue.go:4158: GetIssueInWorkspace

- server/go/internal/handler/issue.go:4172: GetIssue

- server/go/internal/handler/issue.go:4193: GetProjectInWorkspace

- server/go/internal/handler/issue.go:4312: GetIssueInWorkspace

- server/go/internal/handler/issue.go:4485: GetMemberByUserAndWorkspace

- server/go/internal/handler/issue.go:4493: GetAgentInWorkspace

- server/go/internal/handler/issue.go:4518: GetSquadInWorkspace

- server/go/internal/handler/issue.go:4528: GetAgent

- server/go/internal/handler/issue.go:4564: GetAgent

- server/go/internal/handler/issue.go:4607: GetAgentTask

- server/go/internal/handler/issue.go:4905: GetProjectInWorkspace

- server/go/internal/handler/issue.go:4968: GetIssueInWorkspace

- server/go/internal/handler/issue.go:5063: GetIssueInWorkspace

- server/go/internal/handler/issue.go:5075: GetIssue

- server/go/internal/handler/issue.go:5347: GetIssueInWorkspace

- server/go/internal/handler/comment.go:359: Get

- server/go/internal/handler/comment.go:369: Get

- server/go/internal/handler/comment.go:370: Get

- server/go/internal/handler/comment.go:371: Get

- server/go/internal/handler/comment.go:372: Get

- server/go/internal/handler/comment.go:373: Get

- server/go/internal/handler/comment.go:376: Get

- server/go/internal/handler/comment.go:379: Get

- server/go/internal/handler/comment.go:382: Get

- server/go/internal/handler/comment.go:403: Get

- server/go/internal/handler/comment.go:424: Get

- server/go/internal/handler/comment.go:733: ListThreadCommentsForIssuePaged

- server/go/internal/handler/comment.go:835: ListThreadCommentsForIssuePaged

- server/go/internal/handler/comment.go:899: ListRecentThreadCommentsForIssue

- server/go/internal/handler/comment.go:993: ListRootCommentsSinceForIssue

- server/go/internal/handler/comment.go:1030: ListRootCommentsForIssue

- server/go/internal/handler/comment.go:1069: ListCommentsSinceForIssue

- server/go/internal/handler/comment.go:1084: ListCommentsForIssue

- server/go/internal/handler/comment.go:1197: ListCommentsByIDsForIssue

- server/go/internal/handler/comment.go:1298: ListChildCommentsForParents

- server/go/internal/handler/comment.go:1567: GetCommentInWorkspace

- server/go/internal/handler/comment.go:1596: GetComment

- server/go/internal/handler/comment.go:1714: GetComment

- server/go/internal/handler/comment.go:1839: GetThreadRoot

- server/go/internal/handler/comment.go:2793: GetAgentInWorkspace

- server/go/internal/handler/comment.go:2850: GetAgentTask

- server/go/internal/handler/comment.go:2854: GetSquadInWorkspace

- server/go/internal/handler/comment.go:2883: GetAgentTask

- server/go/internal/handler/comment.go:2892: GetAgentTask

- server/go/internal/handler/comment.go:2915: GetThreadRoot

- server/go/internal/handler/comment.go:2939: ListConversationRootOwners

- server/go/internal/handler/comment.go:2974: GetSquadInWorkspace

- server/go/internal/handler/comment.go:2992: GetAgentInWorkspace

- server/go/internal/handler/comment.go:3008: GetSquadInWorkspace

- server/go/internal/handler/comment.go:3053: GetSquadInWorkspace

- server/go/internal/handler/comment.go:3064: GetAgentInWorkspace

- server/go/internal/handler/comment.go:3218: GetSquadInWorkspace

- server/go/internal/handler/comment.go:3242: GetAgentInWorkspace

- server/go/internal/handler/comment.go:3295: GetAgentInWorkspace

- server/go/internal/handler/comment.go:3325: GetAgentTask

- server/go/internal/handler/comment.go:3370: GetCommentInWorkspace

- server/go/internal/handler/comment.go:3465: GetIssue

- server/go/internal/handler/comment.go:3579: GetCommentInWorkspace

- server/go/internal/handler/comment.go:3604: GetComment

- server/go/internal/handler/comment.go:3654: GetCommentInWorkspace

- server/go/internal/handler/comment.go:3678: GetIssue

- server/go/internal/handler/comment.go:3983: GetComment

- server/go/internal/handler/comment.go:4023: GetComment

- server/go/internal/handler/comment.go:4076: GetCommentInWorkspace

- server/go/internal/handler/activity.go:164: ListCommentsForIssue

- server/go/internal/handler/activity.go:173: ListActivitiesForIssue

- server/go/internal/handler/activity.go:183: Get, Get

- server/go/internal/handler/activity.go:184: Get, Get

- server/go/internal/handler/activity.go:241: Get

- server/go/internal/handler/activity.go:376: GetUsersByIDs

- server/go/internal/handler/activity.go:420: CountAssigneeChangesByActor

- server/go/internal/handler/activity.go:437: CountCreatedIssueAssignees

- server/go/internal/handler/subscriber.go:52: ListIssueSubscribers

- server/go/internal/handler/subscriber.go:61: ListProjectSubscribersForIssue

- server/go/internal/handler/subscriber.go:153: ListSubscribedIssueIDs

- server/go/internal/handler/subscriber.go:362: ListProjectSubscribersForIssue

- server/go/internal/handler/file.go:305: Get

- server/go/internal/handler/file.go:345: ListAttachmentsByCommentIDs

- server/go/internal/handler/file.go:370: ListAttachmentsByChatMessageIDs

- server/go/internal/handler/file.go:486: GetIssueInWorkspace

- server/go/internal/handler/file.go:504: GetComment

- server/go/internal/handler/file.go:559: GetAgentTaskInWorkspace

- server/go/internal/handler/file.go:633: GetCommentInWorkspace

- server/go/internal/handler/file.go:683: ListAttachmentsByIssue

- server/go/internal/handler/file.go:727: ListCommentOriginsForIssue

- server/go/internal/handler/file.go:853: GetAttachment

- server/go/internal/handler/file.go:890: GetAttachmentByIDOnly

- server/go/internal/handler/file.go:1487: GetAttachment

- server/go/internal/handler/file.go:1541: GetCommentInWorkspace

- server/go/internal/handler/source_context.go:253: GetIssueSourceContextByIssue

- server/go/internal/handler/source_context.go:269: GetCommentInWorkspace

- server/go/internal/handler/source_context.go:287: GetIssueProjectID

- server/go/internal/handler/source_context.go:394: GetMemberByUserAndWorkspace

- server/go/internal/handler/source_context.go:397: GetUser

- server/go/internal/handler/source_context.go:410: GetAgentInWorkspace

- server/go/internal/handler/source_context.go:514: GetIssueInWorkspace

- server/go/internal/handler/source_context.go:578: GetIssueSourceContextByID

- server/go/internal/handler/source_context.go:829: GetSquadInWorkspace

- server/go/internal/handler/source_context.go:845: GetAgentInWorkspace

- server/go/internal/handler/source_context.go:894: GetProjectInWorkspace

- server/go/internal/handler/reaction.go:71: GetCommentInWorkspace

- server/go/internal/handler/reaction.go:126: GetIssue

- server/go/internal/handler/reaction.go:164: GetCommentInWorkspace

- server/go/internal/handler/reaction.go:232: ListReactionsByCommentIDs

- server/go/internal/handler/task_supplement.go:33: ListTaskSupplementMetadata

- server/go/internal/handler/task_supplement.go:67: GetAgentInWorkspace

- server/go/internal/handler/task_supplement.go:117: ListTaskSupplementsByCommentIDs

- server/go/internal/handler/task_supplement.go:196: GetAgentTask

- server/go/internal/handler/task_supplement.go:208: GetRunningTaskForAgentOnIssue

- server/go/internal/handler/task_supplement.go:289: GetAgentTask

- server/go/internal/handler/task_supplement.go:294: GetAgentInWorkspace

- server/go/internal/handler/task_supplement.go:338: GetTaskSupplementByRequest

- server/go/internal/handler/task_supplement.go:350: GetTaskSupplementCapability

- server/go/internal/handler/task_supplement.go:365: GetTaskSupplementByRequest

- server/go/internal/handler/task_supplement.go:418: GetCommentInWorkspace

- server/go/internal/handler/task_supplement.go:443: GetTaskSupplementForRun

- server/go/internal/handler/task_supplement.go:617: GetCommentInWorkspace

- server/go/internal/handler/project_access.go:44: ListPrivateProjectIDs

- server/go/internal/handler/project_access.go:52: GetAgentTask

- server/go/internal/handler/project_access.go:59: GetAgent

- server/go/internal/handler/project_access.go:116: GetIssueProjectID

- server/go/internal/handler/project_access.go:162: GetCommentIssueProjectID

- server/go/internal/handler/project_access.go:199: GetSquadInWorkspace

- server/go/internal/handler/project_access.go:207: GetProjectInWorkspace

- server/go/internal/handler/project_access.go:211: GetAgent

- server/go/internal/handler/project_access.go:238: GetIssueProjectID

- server/go/internal/handler/project_access.go:240: GetCommentIssueProjectID

- server/go/internal/handler/project_access.go:290: ListAttachmentsByIDs

- server/go/internal/handler/project_access.go:324: GetAgent

- server/go/internal/handler/property.go:326: GetMemberByUserAndWorkspace

- server/go/internal/handler/property.go:411: ListIssueProperties

- server/go/internal/handler/property.go:437: GetIssueProperty

- server/go/internal/handler/property.go:491: CountActiveIssueProperties

- server/go/internal/handler/property.go:560: GetIssueProperty

- server/go/internal/handler/property.go:595: CountIssuesUsingPropertyOptions

- server/go/internal/handler/property.go:614: CountActiveIssueProperties

- server/go/internal/handler/property.go:690: GetIssueProperty

- server/go/internal/handler/property.go:771: GetIssueProperty

- server/go/internal/handler/property.go:1226: GetIssueProperty

- server/go/internal/handler/issue_status.go:118: ListIssueStatusEntries

- server/go/internal/handler/issue_status.go:523: GetIssueStatusEntryByID

- server/go/internal/inbox/tier.go:89: GetAgent

- server/go/internal/inbox/registry.go:160: ListNotificationPreferencesByUsers

- server/go/internal/service/source_context.go:207: GetUser

- server/go/internal/service/source_context.go:213: GetAgentInWorkspace

- server/go/internal/service/source_context.go:266: GetIssueInWorkspace

- server/go/internal/service/source_context.go:273: GetWorkspace

- server/go/internal/service/source_context.go:277: ListSourceContextIssueAttachments

- server/go/internal/service/source_context.go:310: ListSourceContextCommentAttachments

- server/go/internal/service/source_context.go:392: ListCommentThreadHistory

- server/go/internal/service/source_context.go:405: GetCommentInWorkspace

- server/go/internal/service/source_context.go:422: ListCommentAncestorPath

- server/go/internal/service/source_context.go:446: ListCommentThreadHistory

- server/go/internal/issuestatus/issuestatus.go:389: GetIssueStatusEntryByKey

- server/go/internal/issuestatus/issuestatus.go:430: GetIssueStatusEntryByKey

- server/go/internal/issuestatus/issuestatus.go:457: GetIssueStatusEntryByKey

- server/go/internal/issuestatus/issuestatus.go:496: ListIssueStatusEntries

- server/go/internal/issuestatus/issuestatus.go:528: ListIssueStatusEntries

- server/go/internal/issuestatus/issuestatus.go:588: ListIssueStatusEntries

- server/go/internal/issuestatus/issuestatus.go:725: ListIssueStatusKeysByCategories

- server/go/internal/issuestatus/issuestatus.go:766: ListIssueStatusEntries

## SQL definitions (read-query terminals)

- server/go/pkg/db/queries/activity.sql:1: ListActivitiesForIssue

- server/go/pkg/db/queries/activity.sql:47: CountAssigneeChangesByActor

- server/go/pkg/db/queries/agent.sql:26: GetAgent

- server/go/pkg/db/queries/agent.sql:46: GetAgentInWorkspace

- server/go/pkg/db/queries/agent.sql:764: GetAgentTask

- server/go/pkg/db/queries/agent.sql:800: GetAgentTaskInWorkspace

- server/go/pkg/db/queries/attachment.sql:30: ListAttachmentsByIssue

- server/go/pkg/db/queries/attachment.sql:40: GetAttachment

- server/go/pkg/db/queries/attachment.sql:44: GetAttachmentByIDOnly

- server/go/pkg/db/queries/attachment.sql:54: ListAttachmentsByCommentIDs

- server/go/pkg/db/queries/attachment.sql:59: ListSourceContextIssueAttachments

- server/go/pkg/db/queries/attachment.sql:70: ListSourceContextCommentAttachments

- server/go/pkg/db/queries/attachment.sql:187: ListAttachmentsByChatMessageIDs

- server/go/pkg/db/queries/attachment.sql:292: ListAttachmentsByIDs

- server/go/pkg/db/queries/comment.sql:1: ListCommentsForIssue

- server/go/pkg/db/queries/comment.sql:27: ListCommentsByIDsForIssue

- server/go/pkg/db/queries/comment.sql:43: ListCommentOriginsForIssue

- server/go/pkg/db/queries/comment.sql:52: ListChildCommentsForParents

- server/go/pkg/db/queries/comment.sql:70: ListCommentsSinceForIssue

- server/go/pkg/db/queries/comment.sql:78: ListRootCommentsForIssue

- server/go/pkg/db/queries/comment.sql:142: ListRootCommentsSinceForIssue

- server/go/pkg/db/queries/comment.sql:202: ListThreadCommentsForIssuePaged

- server/go/pkg/db/queries/comment.sql:281: ListRecentThreadCommentsForIssue

- server/go/pkg/db/queries/comment.sql:477: GetComment

- server/go/pkg/db/queries/comment.sql:481: GetCommentInWorkspace

- server/go/pkg/db/queries/comment.sql:485: GetThreadRoot

- server/go/pkg/db/queries/comment.sql:846: ListCommentAncestorPath

- server/go/pkg/db/queries/comment.sql:874: ListCommentThreadHistory

- server/go/pkg/db/queries/conversation_root.sql:1: ListConversationRootOwners

- server/go/pkg/db/queries/issue.sql:68: GetIssue

- server/go/pkg/db/queries/issue.sql:97: GetIssueInWorkspace

- server/go/pkg/db/queries/issue.sql:390: ListIssueRefsInWorkspace

- server/go/pkg/db/queries/issue.sql:527: ListOpenIssues

- server/go/pkg/db/queries/issue.sql:686: ListChildIssues

- server/go/pkg/db/queries/issue.sql:697: ListChildrenByParents

- server/go/pkg/db/queries/issue.sql:722: CountCreatedIssueAssignees

- server/go/pkg/db/queries/issue_label.sql:166: ListLabelsForIssues

- server/go/pkg/db/queries/issue_property.sql:1: ListIssueProperties

- server/go/pkg/db/queries/issue_property.sql:16: GetIssueProperty

- server/go/pkg/db/queries/issue_property.sql:20: CountActiveIssueProperties

- server/go/pkg/db/queries/issue_property.sql:79: CountIssuesUsingPropertyOptions

- server/go/pkg/db/queries/issue_reaction.sql:39: ListIssueReactions

- server/go/pkg/db/queries/issue_status.sql:20: ListIssueStatusEntries

- server/go/pkg/db/queries/issue_status.sql:42: GetIssueStatusEntryByKey

- server/go/pkg/db/queries/issue_status.sql:47: GetIssueStatusEntryByID

- server/go/pkg/db/queries/issue_status.sql:134: ListIssueStatusKeysByCategories

- server/go/pkg/db/queries/member.sql:15: GetMemberByUserAndWorkspace

- server/go/pkg/db/queries/notification_preference.sql:21: ListNotificationPreferencesByUsers

- server/go/pkg/db/queries/project.sql:29: GetProjectInWorkspace

- server/go/pkg/db/queries/project_member.sql:1: ListPrivateProjectIDs

- server/go/pkg/db/queries/project_member.sql:88: GetIssueProjectID

- server/go/pkg/db/queries/project_member.sql:92: GetCommentIssueProjectID

- server/go/pkg/db/queries/project_subscriber.sql:23: ListProjectSubscribersForIssue

- server/go/pkg/db/queries/reaction.sql:39: ListReactionsByCommentIDs

- server/go/pkg/db/queries/source_context.sql:15: GetIssueSourceContextByIssue

- server/go/pkg/db/queries/source_context.sql:21: GetIssueSourceContextByID

- server/go/pkg/db/queries/squad.sql:9: GetSquadInWorkspace

- server/go/pkg/db/queries/subscriber.sql:297: ListIssueSubscribers

- server/go/pkg/db/queries/subscriber.sql:302: ListSubscribedIssueIDs

- server/go/pkg/db/queries/supplement.sql:92: GetTaskSupplementByRequest

- server/go/pkg/db/queries/supplement.sql:153: GetRunningTaskForAgentOnIssue

- server/go/pkg/db/queries/supplement.sql:174: GetTaskSupplementForRun

- server/go/pkg/db/queries/supplement.sql:184: GetTaskSupplementCapability

- server/go/pkg/db/queries/supplement.sql:187: ListTaskSupplementsByCommentIDs

- server/go/pkg/db/queries/supplement.sql:197: ListTaskSupplementMetadata

- server/go/pkg/db/queries/user.sql:1: GetUser

- server/go/pkg/db/queries/user.sql:9: GetUsersByIDs

- server/go/pkg/db/queries/workspace.sql:28: GetWorkspace

## Resolution and limits

No pending unresolved helper in the eight issue-domain producer decisions. This audit does not certify runtime parity, middleware parity, or execution of acceptance tests. No issue read marker is written by these GET handlers; the separate POST /read registration is server/go/cmd/server/router.go:2204.

## Parent review and inventory integration
Parent inspected the handler calls for all eight endpoints, including timeline thread completion, source-context snapshot comparison, subscriber preference/owner hydration, attachment origin enrichment and status resolution. Merged the eight event dispositions into routes.json without changing route status. Middleware side effects remain separately scoped; this is source evidence, not executed Go/Python parity. The broad helper index above includes neighboring functions and must not be interpreted as an exact per-route call graph.
