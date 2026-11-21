# Workpal interaction alignment implementation plan

**Goal:** Apply the seventh review without changing offline scope.
**Architecture:** Shared vanilla JavaScript controls, existing model mutations and inline HTML build.
**Tech Stack:** JavaScript, CSS, offline HTML, Node tests, Playwright.
**Spec:** docs/superpowers/specs/2026-11-20-workpal-round-8-design.md

## Constraints

English UI; Workpal brand; preserve notes and existing changes; escape user text; no model calls or install command execution.

## Tasks

- [x] Search focus and result selection, recent entries, highlights and metadata (`src/studio.js`).
- [x] Shared anchored property picker, outside click and Escape handling (`src/studio.js`, `src/studio.css`).
- [x] Compact creator, title focus, expansion, optional details and retained drafts.
- [x] Property selection and separate workflow confirmation; narrow drag confirmation.
- [x] Card assignee/priority actions, Space Peek and inline title/description editing.
- [x] Complete custom date/labels picker, Peek navigation and drag placement states.
- [x] Shared Projects/Agents/Skills search, sorting, Display, row menus and selection.
- [x] Full collection filters, column settings and bulk mutations.
- [x] Navigation tree, sidebar width, Table/Swimlane and Chat structure.
- [x] Capture original-control same-data comparisons and three-width page/interaction screenshots.
- [x] Full-application shared-fixture comparisons: ten original Multica pages, three widths, raw differences and overlays (round 10).
- [ ] System soft-keyboard acceptance blocked by simulator installation/query hangs and unavailable UI window; diagnostic evidence in round 10. Browser touch/short-viewport checks pass but do not replace this.

## Verification

Run npm run check. Browser regressions: empty search is bounded; ArrowDown preserves input focus; subsequent typing filters; Escape restores focus; creator opens on title; searchable property picker respects viewport and retains drafts.

Round 9 implementation and verification: `docs/multica-implementation-round-9.md`.

Round 10 implementation, complete-page comparison and device blocker: `docs/multica-implementation-round-10.md`.
