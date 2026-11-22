# Capability Frontend Implementation Plan

> **For agentic workers:** Use executing-plans for the integration, with independent data, theme and Agent Team tasks delegated in parallel.

**Goal:** Make the approved capability home the signed-in entry to Workpal while preserving workspace routes.

**Architecture:** Typed local capability metadata feeds React Overview, Skill Hub and Agent Team views. The existing auth/session boundary gates entry; Workspace stays behind an explicit navigation action. Use Workpal appearance state and scoped chart styles.

**Tech Stack:** React, TypeScript, Vite, Workpal UI, Zustand appearance, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-21-capability-frontend-design.md`

## Global Constraints

- English UI; Workpal branding, Inter typography and existing theme tokens.
- No model execution, skill installation, fabricated outputs or measured results.
- Preserve SQLite, existing workspace features, dirty unrelated edits and archived notes.
- Work in the user's active feature checkout so the integration includes their uncommitted Python session changes. Do not create commits or alter branch state.

## Review Focus

- A single membership must not bypass the capability entry; deep links still resolve normally.
- Query typing, IME composition and caret must survive filtering.
- Detail navigation must focus and reveal its heading and restore trigger focus.
- All catalog and role references must resolve across the three views.
- Theme changes must persist across entry/workspace, retain readable narrow layouts and expose exactly two themes.

### Task 1: Stable metadata and theme contract
- [x] Add typed runtime data under `apps/web/app/capabilities/data.ts` and `data/`, with reference and filter tests.
- [x] Restrict selectable themes and safely normalize retired preferences; verify store/UI tests.

### Task 2: React views
- [x] Add meaningful view tests for search/IME, details, chart navigation and squad drilldowns.
- [x] Add `capability-hub.tsx`, `overview.tsx`, `skill-hub.tsx`, `agent-team.tsx`, scoped styles and shared focus handling.
- [x] Use existing Workpal Button, Input, brand and appearance controls, without raw HTML injection.
- [x] Verify view tests and referenced data.

### Task 3: Entry and workspace integration
- [x] Add routing/session tests for capability entry, explicit workspace transition and preserved deep links.
- [x] Integrate routes in `main.tsx` and `python-session.tsx` and add a workspace return link.
- [x] Verify authentication, multiple/zero membership handling, history navigation and theme continuity.

### Task 4: Verification and review
- [x] Run `npm run check`, focused frontend tests and browser flows against isolated backend data.
- [x] Check narrow layouts, light/dark modes, console errors and detail focus in Playwright.
- [x] Perform an independent review, fix material findings, and record verification evidence.

## Implementation record

- Canonical capability routes use the reserved `/home` namespace; existing `/landing/skills` workspace links remain accessible.
- A persistent app appearance boundary prevents theme reset during workspace selection. DashboardLayout keeps its existing default sync for other hosts.
- Focus restoration covers cross-page teasers, same-skill reopening, lower list details, squad handoffs and role collaborators.
- Workspace toolbar and dashboard share one viewport; scoped CSS avoids interfering with other pages.
- No commits or branch changes were made. Existing user edits and persistent data were preserved.

## Verification — 2026-11-21

- `npm run check`: passed (9 backend tests and production frontend build). Existing large-chunk and mixed static/dynamic import warnings remain.
- Focused frontend Vitest: 35 tests passed across capability data, Overview, Skill Hub, Agent Team, session entry and routes.
- Targeted appearance tests: 223 passed across core appearance, settings, account menu, appearance sync and command search.
- `REDIS_URL=redis://127.0.0.1:24379 pnpm exec playwright test --config playwright.python.config.ts`: all 7 passed. Used a new temporary SQLite database and a disposable Redis container; no real model or skill-installation calls.
- Browser coverage: login/capability/workspace layers; sole and multiple memberships; workspace return and refresh; preserved workspace slug `landing`; cross-page focus; sequential typing/caret and Chromium IME; lower-list and repeated detail selection; squad and role return focus; FWD/Default × light/dark × 320/390/728/1440 widths; primary button contrast; workspace viewport height; logout/session expiry and realtime updates.
- Capability files ESLint and `git diff --check`: passed. Desktop light, desktop dark and narrow dark screenshots inspected under `outputs/capability-frontend/`.

### Existing limits outside this change

The capability catalog and squad lineups are source-linked definitions. They do not install skills, launch agents, execute models or claim runtime results. The current Python backend supports the authentication/workspace paths exercised here; existing unsupported Workspace API calls still return explicit 404 responses. Existing user databases and archive notes were not changed.

The full web TypeScript command still fails at `apps/web/lib/use-cases-source.ts:4` because generated `@/.source/server` is absent. No errors were reported for the changed frontend files.

Exploratory broader suites also exposed pre-existing failures outside this feature:
- Web `brand-variant-cascade`, `font-stacks` and `text-contrast`: missing desktop placeholder source/styles.
- Web `use-case-locale-fallback`: missing generated `.source/server`.
- Web `public-host`: two `workpal.invalid` expectations.
- Core `github/repo-ref`: “splits a browse URL into clone URL and ref”, “keeps a multi-segment branch together”, and “drops a .git suffix before /tree and a trailing slash after the ref”. Other core results: 3409 passed, 1 skipped.

Concurrent in-progress capability/theme failures in those exploratory runs were subsequently resolved and covered by the final focused and browser runs. The unrelated failures above were not altered.

### Follow-up: workspace-only settings and email-only development login

- Removed Appearance controls and unused menu styles from capability pages; shared appearance preferences still come from Workspace settings/account menu.
- Capability tab switches retain scroll position. Explicit bottom-page teasers return to the top, while skill/role details retain focused reveal behavior.
- Temporarily hid the verification-code field. The login page contains only email and submits the existing development credential only when `/api/config` explicitly enables development authentication. Backend verification and unsupported-operation behavior remain intact.
- Verification: `npm run check` passed; 34 focused frontend tests passed; all 7 Playwright scenarios passed. Browser coverage now changes themes through Workspace and checks tab scroll position and header visibility. Login coverage checks the absent code field, manual submission, unsupported configuration, logout and expiry.
