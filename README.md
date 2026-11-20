# Workpal

This repository follows Multica's top-level layout. Its tracked top-level directories and files are present here, with the additional `assets/` directory retaining the previous Workpal prototype. Upstream revision and local adaptations are recorded in [docs/UPSTREAM.json](docs/UPSTREAM.json).

The default application is the Workpal-branded Multica frontend with a local mock HTTP backend and SQLite. Go server sources, CLI, CI and deployment files are retained as source; non-web app directories are empty; the local commands below do not run those production services.

## Local web app

Node >=22.22 and pnpm 10.28.2 are required.

```sh
pnpm install --filter @multica/web... --frozen-lockfile --ignore-scripts
npm run postinstall
npm run dev
```

Open http://127.0.0.1:4174. The local development API listens on 127.0.0.1:4175.

```sh
npm run check
npm run build
npm start
```

Stop the development server before running `npm start`, which serves the build and API together on port 4174. `npm run dev:web` also starts the local web app and mock service. The Vite web entry is `apps/web/index.html` and `apps/web/app/main.tsx`. Upstream Next.js files are retained alongside it; `build:next`/`dev:next` in the web package are separate upstream entry points, not the validated local application.

## Layout

- `apps/web/`: active web application. `apps/desktop/`, `apps/mobile/`, `apps/docs/` and `apps/storybook/` are empty placeholders. Git does not track empty directories; `pnpm install` recreates these directory names through the root postinstall script.
- `packages/`: shared UI, views, core, enterprise and supporting packages.
- `server/`: local mock service (`*.mjs`) and upstream Go backend/CLI sources.
- `server/data/workpal.sqlite`: existing SQLite database, preserved during migration and ignored by Git.
- `scripts/`, `e2e/`, `docs/`, `examples/`: tooling, tests, documentation and examples.
- `deploy/`, `docker/`, `.github/`, root Docker/Compose/Makefile configs: upstream deployment and automation sources, not configured or validated for the SQLite mock service.
- `assets/workpal-prototype/`: all previous offline prototype sources, scripts, assets, review notes, historical docs and outputs.

## Data and supported behavior

SQLite is seeded once from authored fixtures. Project, issue, agent, skill, squad and autopilot record CRUD and preferences persist across restarts. `WORKPAL_DB=/absolute/path.sqlite` selects a different database. To reset, stop the service and move `server/data/` aside before restarting.

The local backend is single-user and single-workspace. It does not implement real authentication, model/agent execution, skill installation, external integrations, scheduling, billing, uploads or realtime execution. Unsupported operations return HTTP 501. Advanced issue filters/grouping remain partial. Keep the service bound to loopback. Empty fixture collections are not measured results.

## Verification and archive

`npm run check` runs local server checks/tests and builds the active web entry. With the app running and Playwright installed:

```sh
WORKPAL_PLAYWRIGHT=/path/to/@playwright/test node scripts/qa.mjs
```

This checks 20 desktop/mobile page loads and project title editing with reload persistence. The copied upstream CI, Go server and Next.js applications are outside this local validation. Dependency peer-version and large bundle warnings are inherited from the upstream frontend stack; Node 22 labels its SQLite API experimental.

`npm run prototype:check` checks and rebuilds the archived dependency-free HTML app. Historical reference scripts may still reference their original sibling repositories and temporary tooling paths.
