# Workpal

Multica's React frontend source is copied into `packages/` with its license and revision in `UPSTREAM.json`. The local Vite entry uses its original page components and shared UI, with Workpal branding and English text. It does not import the sibling Multica repository. The previous offline prototype and its documentation, scripts, assets and outputs are archived under `assets/workpal-prototype/`.

## Run

Requires Node >=22.22 and pnpm 10.

```sh
pnpm install
pnpm dev
```

Open http://127.0.0.1:4174. The development API listens on loopback port 4175.

```sh
pnpm build
pnpm start
pnpm test
```

Production mode serves the built frontend and API on loopback port 4174. Stop the development server before starting production mode. Root commands: `npm run dev`, `npm run build`, `npm start`, `npm test`, `npm run check`.

## Data and limits

`data/workpal.sqlite` is a real SQLite database (Node's built-in `node:sqlite`). It is seeded once from authored fixtures. Project, issue, agent, skill, squad and autopilot record CRUD and preferences persist across restarts. `WORKPAL_DB=/absolute/path.sqlite` selects another database. To reset, stop the server and move `data/` aside, then start again. The database and generated bundles are ignored by Git.

This is a local mock backend, not Multica's production backend. No real login, model calls, agent execution, skill installation, external integrations, scheduling, billing, uploads or WebSocket execution are implemented. Unsupported endpoints return HTTP 501. Read-only empty collections represent absence of local records, not measured results. Advanced issue filters and grouping beyond status are not implemented. The app is single-workspace and single-user; it binds to loopback and should not be exposed publicly.

The included page routes cover projects, issues, agents, skills, squads, autopilots, inbox, chat, settings and dashboard, with project/issue/agent details. Some upstream controls depend on unsupported backend operations and show an error. This is a separate server-based app; use the archived prototype `npm --prefix assets/workpal-prototype run build` for the dependency-free offline Workpal export.

## Source changes

Copied `core`, `views`, `ui` and their supporting config/test/plugin packages. Modified English product copy, the wordmark/icon components, and allowed an empty WebSocket URL to disable realtime transport. `app/` contains the local navigation/auth bootstrap; `server/` contains the mock HTTP API and SQLite persistence. Upstream code retains its existing package names and license.

## Verification

Validated: root `npm run check`, `pnpm build`, SQLite HTTP CRUD/restart/input tests, and Playwright page loading at 1440px and 390px plus project title editing and reload persistence. To rerun browser checks with a running app:

```sh
WORKPAL_PLAYWRIGHT=/path/to/@playwright/test node scripts/qa.mjs
```

The production build reports large bundle warnings. Node 22 reports its built-in SQLite API as experimental. Dependency installation reports upstream peer-version warnings; the build and exercised browser flows pass.

## Repository layout

- `app/`, `packages/`, `public/`: active Multica frontend and Workpal entry.
- `server/`, `data/`: local mock API and SQLite database.
- `scripts/`: active app browser verification.
- `assets/workpal-prototype/`: archived offline prototype, including historical docs, reports, reference outputs and original assets.

Run `npm run prototype:check` to check and rebuild the archived offline app. Historical comparison scripts may reference their original sibling repositories and temporary browser installations; they are retained as archival material.
