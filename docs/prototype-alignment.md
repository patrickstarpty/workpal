# Web prototype interaction alignment

Align the offline English Workpal prototype with Multica's compact frontend controls while retaining Workpal branding, local review notes and delivery records.

The changes cover the compact issue creator and drafts, continuous creation and keyboard submission; anchored searchable properties, labels and dates; independent card actions, drag placement, Peek and inline editing; Table and Swimlane controls; common resource collections with filtering, sorting, columns and selection; global search focus and recent results; sidebar resizing and project trees; and conversation-first Chat navigation.

The shared controls live in `src/ui.js` and `src/ui.css`. The build embeds them in the dependency-free `dist/Workpal.html`. No agent execution or backend service is introduced by this commit.

Acceptance scope is the Web application. The user explicitly excluded mobile interaction and system software-keyboard acceptance on 2026-11-20. Existing responsive behavior remains, but device/simulator verification is not a completion gate. Full-product pixel identity is not claimed.

Verification: `npm run check` and the browser suites `scripts/round-8-qa.mjs`, `scripts/round-9-qa.mjs`, `scripts/round-9-states-qa.mjs`, `scripts/round-10-qa.mjs`, and `scripts/round-11-qa.mjs`. Browser suites require Playwright in the development environment; it is not part of the offline deliverable.
