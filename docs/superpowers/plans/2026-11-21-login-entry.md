# Login Entry Implementation Plan

**Goal:** Bring the archived welcome/login screen into the active React app.
**Architecture:** A standalone entry component renders at the default hash route and /landing or /welcome, outside the workspace shell. Existing workspace deep links remain valid. Enter Workpal opens /review/projects.
**Tech Stack:** React, existing Workpal icons and branding, scoped CSS, Playwright.
**Spec:** User requested the prototype's login page: background photograph, centered brand card, slogan and entry action.
**Constraints:** English UI; no invented authentication; preserve SQLite and archive sources.
**Review focus:** Keyboard entry, small screens, direct workspace URLs, back navigation, successful image loading.

- [x] Copy the original background and adapt the welcome markup and responsive CSS.
- [x] Route default entry and login aliases outside DashboardLayout; preserve workspace routes.
- [x] Run npm run check and Playwright entry/navigation tests at desktop and mobile sizes.
