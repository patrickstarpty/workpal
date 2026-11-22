# Workpal interaction design

Workpal is an English workspace for people, agents and software delivery. TAP is the preconfigured workspace for developing TAP. Additional workspaces have independent projects, issues, configurations, conversations and reports.

## Visual system

The product uses a neutral application frame, with a 56px primary rail, 280px contextual navigation, 48px page headers and 36px issue rows. Inter is bundled with the offline export. Controls share 24/28/32px heights and a 6/8/12px radius scale. White overlays use a restrained floating shadow; the workspace itself uses hairline boundaries and quiet selected states. Team collections are tables, and the floating and full-page conversations share their typography and input controls.

## Navigation

Work contains Inbox, issue views, projects and workspace insights. Team contains agents, squads, Skill Hub, runtimes and execution records. Chat contains conversations with individually selected agents. Auto contains recurring runbooks and their delivery history.

Ask Workpal starts a conversation from the lower-right edge of workspace pages. Floating chat and full Chat use the same conversation record. The launcher is hidden on Chat. Cmd/Ctrl+J toggles the floating window, Shift+Cmd/Ctrl+J starts a conversation, and Cmd/Ctrl+K opens workspace search.

## Work and execution

An issue owns its description, properties, discussion, children and delivery history. An assignee may be Patrick, an agent or a squad. Assigning a squad queues its leader. Backlog preserves the assignment without automatically starting work.

Runs have independent histories. Completing execution preserves the issue's status. Delivering work records the handoff and moves the issue into the project's next step. A shared workflow defines the assignee, instructions, next status and rejection destination for each step. Switching a project's workflow changes configuration without dispatching agents.

Workspace records retain the issue context during handoffs. A queued handoff snapshots its instructions. Explicit agent and squad mentions select their recipients. Human mentions suppress automatic assignee dispatch.

## Conversations

Each conversation stores its recipient, title, project context, messages and drafts. Conversations can be pinned, renamed or archived. Agent-specific starters populate the composer and can be edited before sending. Replies and generated action cards remain in their originating conversation.

Supported workspace commands create forms, charts or report cards through the trusted component catalog. Plain messages enter an offline queue and retain a run record with cancellation. A live language model and runtime transport are future integrations.

## Reusable work

Skill Hub has source links, install commands, saved entries, agent attachments and workspace usage. Shared workflow definitions configure project handoffs. Quick Actions post saved requests from the issue sidebar or insert an editable draft from the comment composer’s slash menu. Replies reopen resolved discussions and follow the same agent routing rules as comments. Wakeups watch for a comment, completed children or a chosen time. Autopilots can create an issue or record a skipped run-only delivery while the runtime is offline.

## Persistence and boundaries

The exported HTML works offline. Browser storage retains independent workspace records and imports earlier single-workspace data. It does not synchronize across devices.

The interface implements local interactions. Multi-user permissions, server-side schedules, actual CLI execution, streaming model replies, repository access, hosted webhooks and runtime registration with a server require backend services. Runtime entries currently store device configuration and remain offline. Time-based triggers are evaluated while the page is open.

Unit tests cover transitions, per-agent deduplication, workspace isolation and migrations. Browser checks exercise the public user paths in the self-contained HTML at desktop and phone widths.
