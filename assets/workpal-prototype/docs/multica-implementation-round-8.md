# Round 8 implementation record

Implemented in the existing offline entry point; existing unrelated working-tree changes retained.

## Delivered

- Search keeps input focus while arrows change active results; Enter opens the active result. Empty input shows creation actions and at most eight recent selections. Rows include icons, escaped match highlighting and categories.
- Shared searchable anchored picker for creator select fields and issue status, owner, priority and project. Escape/outside click dismisses; focus returns to the trigger. Owner/status transitions retain a separate confirmation form.
- Creator focuses the title, supports width expansion, retains draft storage and collapses additional workflow/acceptance details.
- Card assignee and priority buttons act independently. Space opens a side-sheet detail view. Dragging opens the smaller status confirmation instead of the complete issue editor.
- Issue title and description edit directly; title updates the background card. Delivery evidence is collapsed separately; existing notes remain.
- Projects, Agents and Skills use common compact rows with search, name sorting, detail visibility, row menus and selection. Skills analytics is behind an expandable entry.

## Verification

`npm run check`: 102 frontend tests, offline build and 2 backend tests passed.
`node scripts/round-8-qa.mjs`: isolated Chromium at 1440×900 and 390×900; search focus/continued typing, empty results, Escape/C recovery, creator draft retention and text escaping, picker viewport boundaries, collection search and selection, Space Peek, inline title propagation and card priority selection passed. No page errors in those paths. No real model calls.

## Outstanding acceptance at the end of round 8

Superseded by [round 9 implementation and evidence](multica-implementation-round-9.md). The list below is the historical handoff, not the current feature status.

This is an initial implementation, not one-to-one acceptance. Still outstanding: creator mode switching and complete draft indicators; custom date and label pickers; advanced picker focus semantics; drag preview/drop placement and conditional confirmation; Peek previous/next; full collection filter/column/bulk operations; Table/Swimlane; navigation tree, resizing and temporary expansion; Chat restructuring; unified tooltip and motion states; soft keyboard/device testing; same-data Multica screenshots and pixel comparison. Shared collection selection currently provides selection controls, not destructive bulk actions. Agent avatar editing remains available through other existing contexts, but its prior list-row entry needs restoring to the collection row menu.

Offline delivery: `dist/Workpal.html`. Agent runs remain local records; this work adds no production execution backend.
