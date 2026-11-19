# Workpal

**Let’s work together.**

Open **[dist/Workpal.html](dist/Workpal.html)** in a browser to start on the Workpal welcome screen, then select **Enter workspace**. Send the single HTML file to an advisor for offline review. Open **Ask Workpal** outside the Chat page or press Cmd/Ctrl + J. The interface uses Inter, compact navigation and table layouts; the font is embedded in the offline export.

## Brand identity

The brand slogan is **Let’s work together.** Preserve this exact capitalization and punctuation. The Workpal wordmark uses sans-serif Inter with italic styling, paired with a prominent **W.** mark in the bold serif tradition of newspaper mastheads. The mark uses fixed SVG outlines, so it stays consistent in the offline export without an additional font. Workspace controls and content retain upright Inter. The Inter font and its license are included in `assets/fonts/`.

The welcome screen pairs the **W.** logo in an orange square with the italic Workpal wordmark, with **Let’s work together.** on the next line. Keep the orange square close to the wordmark’s visible height and scale both together on smaller screens. Keep the dot close to the W and the mark spacious inside its square. The **Enter workspace** control below combines a visible label with a right arrow. Its rectangular shape shares the logo’s corner radius; its accessible name comes from the visible label.

## Review a delivery and its rework

1. Create an issue with a goal and one acceptance criterion per line. Choose an agent, then open **Start run**. The delegation context previews the project, agent and selected skill. **Start workflow** records an offline attempt; it does not execute an agent.
2. In the run, supply a summary, an artifact (document, change excerpt or reference), evidence for each criterion, and limitations. Each evidence row can be provided, missing, not met, or not applicable with an explanation. **Submit for review** saves a versioned Delivery. You may submit gaps so a reviewer can request changes.
3. Review the actual artifact and evidence. Missing evidence or artifacts block approval. Choose **Request changes**, explain the gap, and start another attempt. Its input snapshot includes the prior delivery and review note.
4. Submit the revised content, expand **Compare v1 → v2**, and inspect both versions. Only the explicitly selected current delivery can be approved, with an explicit acknowledgement. Approval follows the current workflow's review destination; the control shows that destination. A finished run alone does not complete an issue.
5. Generate an execution report from the run and export Markdown. Reports retain the original issue requirements, agent, selected skill record/version label, project context, source run, delivery version and decision. Editing an issue later does not rewrite historical inputs.

The workspace is an offline research prototype. All run transitions, supplied evidence and decisions are local records, not real agent outputs or measured test results. Runtime availability is shown as Offline. Research and simulation labels are kept out of the product interface. Runtime connections, model calls, repository writes and background production scheduling are not implemented. Evidence presence is validated; correctness must be judged by the reviewer. The local reviewer identity is Patrick, without authentication or multi-user permissions.

Issue edits, projects, agents, deliveries, bookmarks, conversation cards, decisions, pinned panels, notes and report snapshots persist in local browser storage. Existing workspace records and review notes are retained. Historical runs without original inputs explicitly show that the input snapshot is unavailable; they cannot be approved against reconstructed requirements. They can be returned and replaced by a new attempt. User-authored text is escaped and preserved in its original language. The earlier Chinese design remains at review-v1.html.

The behavior consistency update adds explicit current/candidate deliveries, one dispatch decision per issue edit, manual completion reasons, draft persistence and conflict-aware local saving. Parallel or late results remain candidates until a person selects them with a reason; cancelling another attempt does not revoke the current delivery. Independent changes across tabs merge; conflicting edits to the same record stay unsaved with export and recovery actions.

**Squads → Assign work** opens a compact issue composer with the squad preassigned. Backlog and the unchecked queue option create no run. A queued leader receives the squad's members, roles and instructions in its captured context. Click a member avatar to choose or paste an emoji; it is shared across the member's appearances in the workspace. This does not implement autonomous multi-agent coordination.

Chat report requests now open confirmation forms. Autopilot templates capture acceptance criteria before queuing; schedule checks only occur while that workspace is selected and the page is open. Missed triggers are not replayed. Skill publishing/reuse, real execution and production scheduling remain outside this update. See [behavior consistency implementation notes](docs/behavior-consistency-implementation.md).

## Agent application design

The local dispatcher understands supported intents and identifiers. A form supplies missing parameters, and the action catalog gives direct access to every workspace area. Chat and pages call the same model and rendering functions. Live dashboard cards query current records; documents capture the data at generation time.

The browser dispatches local workpal:agent-event events for run and tool-call lifecycle transitions. Tool results describe a named component and arguments inside a local ui://workpal resource. Allowlisted components render editable forms, team statistics, workflow handoffs and reports. Inspect **Tool events → Surface schema** on a response card. These are offline design adaptations of [AG-UI events](https://docs.ag-ui.com/concepts/events), [A2UI surfaces](https://a2ui.org/) and [MCP-UI resources](https://mcpui.dev/). Network transports, a live model, remote MCP servers and code execution are future integrations.

## Local development

**Team → Analytics** provides Usage, Errors and Teams views. Period, project and team filters share the same scope; trend metrics, chart intervals and leaderboard sorting remain independent. Teams shows current issue status and opens team issues and usage. Pinned panels remain available below the analytics content.

TAP's usage history is authored display data, stored separately in `analyticsHistory` with `source: "fixture"`. It is not observed token consumption, billing or agent execution, and never changes issues, run records or review evidence. Dates are anchored on first opening Analytics and retained across reloads. Symphony and newly created workspaces start with empty usage history. Team issue counts read the current workspace records.

Node.js 22 or newer. No dependencies required to use or build the prototype.

- npm run dev serves the source entry on 127.0.0.1:4173.
- npm run check checks syntax, runs tests and builds the offline artifact.
- node scripts/qa.mjs exercises the exported file with Playwright. Set WORKPAL_PLAYWRIGHT to a local @playwright/test installation if needed.
- node scripts/delivery-qa.mjs checks offline delivery → missing evidence → return → v2 → approval, historical reports, text safety, local notes and export at desktop and narrow widths.
- node scripts/squads-qa.mjs checks compact delegation and shared emoji avatars at desktop/narrow widths.
- node scripts/lifecycle-qa.mjs checks workflow dispatch, manual completion and parallel/late delivery selection.
- node scripts/drafts-qa.mjs checks drafts, two-tab notes, conflict export/recovery and workspace isolation.
- node scripts/consistency-qa.mjs checks Chat, saved layouts, Inbox, review notes and Autopilot acceptance templates.
- node scripts/layout-qa.mjs checks sparse and long issue boards at five viewport sizes, including bottom-aligned horizontal scrolling, independent column scrolling, restored scroll positions, sticky headers, detail panes and mobile Chat.
- node scripts/analytics-qa.mjs checks analytics filters, tabs, chart controls, rankings, team drilldown, workspace isolation and responsive layouts.

The updated source consists of src/model.js, src/studio.js and src/studio.css. The old review entry retains its original scripts and styles.
