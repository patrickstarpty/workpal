# Workpal

Workpal. Work together.

Open **[dist/Workpal.html](dist/Workpal.html)** in a browser for the English TAP workspace. Send the single HTML file to an advisor for offline review. Open **Ask Workpal** outside the Chat page or press Cmd/Ctrl + J. The interface uses Inter, compact navigation and table layouts; the font is embedded in the offline export.

## A five-minute review

1. Ask “Create issue titled Review citation coverage”. Enter acceptance criteria, choose a team and assignee, and save the issue directly in the conversation.
2. Assign an agent to a To do issue and leave the start option checked. Open its run from the issue detail, write a handoff note and submit for review. Approve the issue or return it for another attempt.
3. Ask “Generate execution report”. Inspect the issue, current run state and timestamped decision trail. Export a Markdown snapshot from the same card.
4. Ask “Chart quality team issues by project”. Change the grouping to assignee, then pin the panel to **Workspace insights**. Team totals and panels read the same issue records as the board.
5. Ask “Generate a quality team summary”. Review the saved snapshot under **Reports**. **Workspace actions** also exposes project and agent configuration, the skill directory, notes, reports and workspace settings.

The default data represents a simulated workspace. Issue edits, projects, agents, bookmarks, conversation cards, decisions, pinned panel configurations, notes and report snapshots persist in local browser storage. An existing v1 browser session is imported once on first use. User-authored text is preserved in its original language. For continued access to the earlier Chinese design, the source entry is review-v1.html.

## Agent application design

The local dispatcher understands supported intents and identifiers. A form supplies missing parameters, and the action catalog gives direct access to every workspace area. Chat and pages call the same model and rendering functions. Live dashboard cards query current records; documents capture the data at generation time.

The browser dispatches local workpal:agent-event events for run and tool-call lifecycle transitions. Tool results describe a named component and arguments inside a local ui://workpal resource. Allowlisted components render editable forms, team statistics, workflow handoffs and reports. Inspect **Tool events → Surface schema** on a response card. These are offline design adaptations of [AG-UI events](https://docs.ag-ui.com/concepts/events), [A2UI surfaces](https://a2ui.org/) and [MCP-UI resources](https://mcpui.dev/). Network transports, a live model, remote MCP servers and code execution are future integrations.

## Local development

Node.js 22 or newer. No dependencies required to use or build the prototype.

- npm run dev serves the source entry on 127.0.0.1:4173.
- npm run check checks syntax, runs tests and builds the offline artifact.
- node scripts/qa.mjs exercises the exported file with Playwright. Set WORKPAL_PLAYWRIGHT to a local @playwright/test installation if needed.
- node scripts/layout-qa.mjs checks sparse and long issue boards at five viewport sizes, including bottom-aligned horizontal scrolling, independent column scrolling, restored scroll positions, sticky headers, detail panes and mobile Chat.

The updated source consists of src/model.js, src/studio.js and src/studio.css. The old review entry retains its original scripts and styles.
