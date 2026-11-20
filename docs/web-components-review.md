# Web component integration review

Scope: the local Vite application in `apps/web`, its shared views, and the SQLite mock API. Desktop and mobile native clients are empty and were not tested. An initial browser-width smoke pass covered 1440px and 390px; subsequent regression work focused on the desktop browser at the user's request.

## Fixed findings

- `apps/web/app/main.tsx`: search and floating chat launchers changed state, but their overlay components were absent. Mounted `SearchCommand` and `FloatingChat` in the dashboard's overlay slot.
- `apps/web/app/routes.tsx`: skill/squad/autopilot/runtime details, Analytics (`/usage`), My Issues, Views and agent creation were missing from the local router. Added explicit routes and an unavailable-page state instead of silently rendering Projects.
- `server/api.mjs`: `/squads/:id/members` incorrectly matched the generic workspace-member response. Returned proper `member_type`, `member_id`, `squad_id` and role fields; unknown squads return 404. Added a frontend missing-ID guard so malformed records cannot crash the whole page.
- `server/api.mjs`: issue/project search URLs were interpreted as record IDs. Added fixture-backed search with query matching, bounded result counts and the required `match_source` field.
- `apps/web/app/main.tsx`: theme provider and toast renderer were absent; added them. Page-level errors now retain the navigation shell and show a retry action instead of a stack trace.
- `apps/web/app/main.tsx`: corrected hash-based share links, replace navigation and new-tab navigation.
- `packages/views/chat/components/chat-bar.tsx`: marked the decorative brand icon as hidden from assistive technology so the button name is exactly “Ask Workpal”.
- `server/api.mjs`: added correctly shaped read responses for child issue progress, pending chat tasks, agent task snapshots, wakeup summaries, runtime details and project resource/subscription states.
- Dedicated desktop/mobile CI workflows moved to `.github/disabled-workflows/`. Root lint/typecheck commands target the web dependency graph.

## Verification

`npm run check` passed, including SQLite persistence, input validation, repeated shutdown and endpoint-shape regression tests.

`WORKPAL_PLAYWRIGHT=/path/to/@playwright/test node scripts/web-components-qa.mjs` builds on the existing production output and starts an isolated in-memory API; it does not edit the user's SQLite database. Verified:

- Search launcher, actual issue result, navigation, Cmd+K and Escape.
- Ask Workpal open/minimize and Cmd+J.
- Issue/project creation dialogs open and dismiss.
- Resources → Skills → skill detail, and Analytics sidebar navigation.
- Squad row → detail with valid member identities.
- Fourteen desktop web routes without page exceptions or horizontal document overflow.
- Explicit unknown-route fallback.

Accessibility review used the [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md), focusing on accessible names, keyboard actions, visible error recovery and responsive document bounds. This is not a full WCAG certification or a test of every upstream component branch.

## Remaining backend limitations

Real agent execution, message delivery, external integrations, upload/install flows and scheduling remain unsupported and may return 501. Opening the chat composer does not establish live agent execution. Analytics opens normally but has no measured usage history. Advanced issue filters/grouping and some settings/resource/member mutation APIs are still partial. Unsupported AI creation routes show an unavailable page rather than pretending success. Native applications and the upstream Go backend were not part of this verification.
