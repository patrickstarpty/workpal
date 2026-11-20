# Workpal

**Let’s work together.**

Open **[dist/Workpal.html](dist/Workpal.html)** in a browser to start on the Workpal welcome screen, then select **Enter workspace**. Send the single HTML file to an advisor for offline review. Open **Ask Workpal** outside the Chat page or press Cmd/Ctrl + J. The interface uses Inter, compact navigation and table layouts; the font is embedded in the offline export.

## Brand identity

The brand slogan is **Let’s work together.** Preserve this exact capitalization and punctuation. The Workpal wordmark uses sans-serif Inter with italic styling, paired with a lowercase **pal** mark. The mark reuses the wordmark’s embedded font, weight, italic styling and letter spacing, matching its final three letters. Scale the SVG as a whole to preserve those letterforms. Workspace controls and content retain upright Inter. The Inter font and its license are included in `assets/fonts/`.

The welcome screen pairs the deep-green **pal** logo in an orange square with the italic Workpal wordmark, with **Let’s work together.** on the next line in 18px bold foreground text. Keep the orange square close to the wordmark’s visible height and scale both together on smaller screens. The pal SVG occupies 84% of the square’s width and is centered with clear space around its letters. The **Enter workspace** control below combines a visible label with a right arrow. Its rectangular shape shares the logo’s corner radius; its accessible name comes from the visible label.

## Review a delivery and its rework

1. Create an issue with a goal and one acceptance criterion per line. Choose an agent, then open **Start run**. The delegation context previews the project, agent and selected skill. **Start workflow** records an offline attempt; it does not execute an agent.
2. In the run, supply a summary, an artifact (document, change excerpt or reference), evidence for each criterion, and limitations. Each evidence row can be provided, missing, not met, or not applicable with an explanation. **Submit for review** saves a versioned Delivery. You may submit gaps so a reviewer can request changes.
3. Review the actual artifact and evidence. Missing evidence or artifacts block approval. Choose **Request changes**, explain the gap, and start another attempt. Its input snapshot includes the prior delivery and review note.
4. Submit the revised content, expand **Compare v1 → v2**, and inspect both versions. Only the explicitly selected current delivery can be approved, with an explicit acknowledgement. Approval follows the current workflow's review destination; the control shows that destination. A finished run alone does not complete an issue.
5. Generate an execution report from the run and export Markdown. Reports retain the original issue requirements, agent, selected skill record/version label, project context, source run, delivery version and decision. Editing an issue later does not rewrite historical inputs.

## Follow the issue workflow and retain completed work

**Team → Workflows → Workflow overview** shows the main issue lifecycle, review return paths, manual blocking, and Done → Archived → Done. Select a project to use its configured review destinations and delivery requirements; select a stage for its handoff and rules. The map can be collapsed, scrolled on narrow screens, and operated with the keyboard. Starting work can skip To do; every current delivery still enters In review. Existing runs retain the completion requirements captured when they started.

Done displays 50 issues per page in both list and board layouts. **Archive this page** and **Archive all matching** show the exact selection size before applying the change. **Archived** supports search, pagination, historical details, and restoration of one issue or the current page. Archive is visibility metadata, not a new issue status: records stay Done, and existing comments, deliveries, relationships, and review notes remain intact. Restore before editing an archived issue.

All data still lives in browser local storage, subject to its capacity. Failed archive/restore saves roll back the batch and report the failure. Pagination limits rendered rows; it does not add a production database or unlimited storage.

The workspace is an offline research prototype. All run transitions, supplied evidence and decisions are local records, not real agent outputs or measured test results. Runtime availability is shown as Offline. Research and simulation labels are kept out of the product interface. Runtime connections, model calls, repository writes and background production scheduling are not implemented. Evidence presence is validated; correctness must be judged by the reviewer. The local reviewer identity is Patrick, without authentication or multi-user permissions.

Issue edits, projects, agents, deliveries, bookmarks, conversation cards, decisions, pinned panels, notes and report snapshots persist in local browser storage. Existing workspace records and review notes are retained. Historical runs without original inputs explicitly show that the input snapshot is unavailable; they cannot be approved against reconstructed requirements. They can be returned and replaced by a new attempt. User-authored text is escaped and preserved in its original language. The earlier Chinese design remains at review-v1.html.

The behavior consistency update adds explicit current/candidate deliveries, one dispatch decision per issue edit, manual completion reasons, draft persistence and conflict-aware local saving. Parallel or late results remain candidates until a person selects them with a reason; cancelling another attempt does not revoke the current delivery. Independent changes across tabs merge; conflicting edits to the same record stay unsaved with export and recovery actions.

**Squads → Assign work** opens a compact issue composer with the squad preassigned. Backlog and the unchecked queue option create no run. A queued leader receives the squad's members, roles and instructions in its captured context. Click a member avatar to choose or paste an emoji; it is shared across the member's appearances in the workspace. This does not implement autonomous multi-agent coordination.

Chat report requests now open confirmation forms. Autopilot templates capture acceptance criteria before queuing; schedule checks only occur while that workspace is selected and the page is open. Missed triggers are not replayed. Skill publishing/reuse, real execution and production scheduling remain outside this update. See [behavior consistency implementation notes](docs/behavior-consistency-implementation.md).

## Investigate an environment in Chat

Open **Chat** in TAP to review three authored six-turn conversations: DEV request-contract mismatch, UAT duplicate uploads after retry, and PRD search timeouts after deployment. These are fictional review scenarios requested for the prototype, not connected logs, actual Agent responses or verified incidents. The data retains `fixtureSource: "environment-chat-v1"`; no measured usage, runs or resolved issues are generated from the preset histories. Existing conversations, drafts and review notes are preserved, and custom workspaces do not receive these examples.

**New chat → Environment support** selects a project, environment and agent. DEV defaults to Architecture partner, UAT to Quality partner and PRD to Engineering partner; any existing agent can be selected explicitly. Each environment thread keeps its context; choosing another environment starts a separate thread. New messages are saved as offline queued requests with captured history and project/agent settings, with a Cancel action. No live analysis is performed.

**Create issue** saves a linked Backlog issue with the conversation history and environment, without starting another run. Reopening the thread shows the existing issue link. Its context is a snapshot at handoff; later chat messages do not rewrite it. Fixture provenance remains in record metadata, rather than labels in the interface.

## Agent application design

The local dispatcher understands supported intents and identifiers. A form supplies missing parameters, and the action catalog gives direct access to every workspace area. Chat and pages call the same model and rendering functions. Live dashboard cards query current records; documents capture the data at generation time.

The browser dispatches local workpal:agent-event events for run and tool-call lifecycle transitions. Tool results describe a named component and arguments inside a local ui://workpal resource. Allowlisted components render editable forms, team statistics, workflow handoffs and reports. Inspect **Tool events → Surface schema** on a response card. These are offline design adaptations of [AG-UI events](https://docs.ag-ui.com/concepts/events), [A2UI surfaces](https://a2ui.org/) and [MCP-UI resources](https://mcpui.dev/). Network transports, a live model, remote MCP servers and code execution are future integrations.

## Workspace connections

Settings follows the local Multica implementation: **Code** contains Code hosting, Repositories, and Pull requests & issues; **Connected apps** contains Team accounts and My accounts. Jira uses the app catalog account flow, not a custom Jira URL/token/project-mapping form. The repository catalog supports HTTPS/SSH URLs, optional descriptions, editing, confirmed removal, and deduplication across clone protocols. Project resources can select a saved workspace repository; deleting a catalog entry preserves existing project resources and delivery history.

Jira and GitHub account setups are local records with **Authorization required / Not connected** status. Hosted OAuth, GitHub App installation, fetching authorized repositories, Jira access, PR webhooks, and credential storage are not implemented in this offline artifact. No remote authorization is attempted, no tokens are collected, and saved setup does not imply a connection. The Pull Request sidebar preference affects issue display; code preferences are captured with run context. Automatic PR linking and commit attribution still need a real runtime/backend. Existing manual merge/completion rules remain in force.

The default TAP workspace receives a one-time set of five repository entries, two GitHub account setups and three Jira account setups. These are authored review data, not fetched account or repository records; the four `git.example.com` URLs are placeholders. All account setups remain pending authorization. The additive migration deduplicates equivalent clone URLs, preserves existing configurations and notes, leaves other workspaces empty, and does not restore examples after deletion. Project resources and captured run contexts are not changed.

Reference source: `../multica/packages/views/settings/components/{code-tab,repositories-section,apps-settings,add-app-dialog}.tsx` and the Jira entry in `../multica/server/internal/connectedapps/catalog.go`.

## Local development

**Team → Analytics** provides Usage, Errors and Teams views. Period, project and team filters share the same scope; trend metrics, chart intervals and leaderboard sorting remain independent. Teams shows current issue status and opens team issues and usage. Pinned panels remain available below the analytics content.

TAP's usage history is authored display data, stored separately in `analyticsHistory` with `source: "fixture"`. It is not observed token consumption, billing or agent execution, and never changes issues, run records or review evidence. Dates are anchored on first opening Analytics and retained across reloads. Symphony and newly created workspaces start with empty usage history. Team issue counts read the current workspace records.

Node.js 22 or newer. No dependencies required to use or build the prototype.

- npm run dev serves the source entry on 127.0.0.1:4173.
- npm run check checks syntax, runs tests and builds the offline artifact.
- node scripts/workflow-qa.mjs checks project-specific review routes, completion gates, keyboard access, collapse behavior, and responsive bounds.
- node scripts/archive-qa.mjs checks 10,000 Done issues with 50 rendered per page, batch archive/restore, persistence, filtering, and preserved notes.
- node scripts/integrations-qa.mjs checks repository CRUD, Jira/GitHub setup states, persistence, isolation, keyboard access, escaping and offline behavior at desktop/narrow widths.
- node scripts/qa.mjs exercises the exported file with Playwright. Set WORKPAL_PLAYWRIGHT to a local @playwright/test installation if needed.
- node scripts/delivery-qa.mjs checks offline delivery → missing evidence → return → v2 → approval, historical reports, text safety, local notes and export at desktop and narrow widths.
- node scripts/squads-qa.mjs checks compact delegation and shared emoji avatars at desktop/narrow widths.
- node scripts/lifecycle-qa.mjs checks workflow dispatch, manual completion and parallel/late delivery selection.
- node scripts/drafts-qa.mjs checks drafts, two-tab notes, conflict export/recovery and workspace isolation.
- node scripts/environment-chat-qa.mjs checks the preset histories, routing, offline queue/cancel, text safety, draft persistence and issue handoff at desktop/narrow widths.
- node scripts/consistency-qa.mjs checks Chat, saved layouts, Inbox, review notes and Autopilot acceptance templates.
- node scripts/layout-qa.mjs checks sparse and long issue boards at five viewport sizes, including bottom-aligned horizontal scrolling, independent column scrolling, restored scroll positions, sticky headers, detail panes and mobile Chat.
- node scripts/analytics-qa.mjs checks analytics filters, tabs, chart controls, rankings, team drilldown, workspace isolation and responsive layouts.

The updated source consists of src/model.js, src/studio.js and src/studio.css. The old review entry retains its original scripts and styles.

Environment Chat validation: `npm run check` passes, as do `environment-chat-qa.mjs` at 1440px and 390px and `consistency-qa.mjs`. The floating chat path also preserves typed text when choosing an environment and expanding into full Chat. The older all-in-one `qa.mjs` is not fully passing: after scoping its issue-property assertions to the properties sidebar, its Quality dashboard assertion still expects issue content that the current Analytics surface does not render.
