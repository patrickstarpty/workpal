# Workpal


The default application is the Workpal-branded React frontend with the Python backend and SQLite. The Node mock backend remains available separately for demos. Go server sources, CLI, CI and deployment files are retained as source; desktop and mobile app directories are empty; the local commands below do not run those production services.

## Local web app

Node >=22.22 and pnpm 10.28.2 are required.

```sh
pnpm install --filter @workpal/web... --frozen-lockfile --ignore-scripts
npm run postinstall
npm run dev
```

Open http://127.0.0.1:4174. The local development API listens on 127.0.0.1:4175.

```sh
npm run check
npm run build
npm start
```

Stop the development server before running `npm start`, which serves the build and Python API together on port 4174. `npm run dev:web` starts the local web app and Python service. The Vite web entry is `apps/web/index.html` and `apps/web/app/main.tsx`. Upstream Next.js files are retained alongside it; `build:next`/`dev:next` in the web package are separate upstream entry points, not the validated local application.

## Layout

- `apps/web/`: active web application. `apps/docs/` contains the documentation site and `apps/storybook/` the component explorer. `apps/desktop/` and `apps/mobile/` are empty placeholders. Git does not track empty directories; `pnpm install` recreates these directory names through the root postinstall script.
- `packages/`: shared UI, views, core, enterprise and supporting packages.
- `server/`: active Python backend (`src/workpal_backend`), Node mock service (`*.mjs`), and upstream Go reference sources.
- `server/data/workpal.sqlite`: existing SQLite database, preserved during migration and ignored by Git.
- `scripts/`, `e2e/`, `docs/`, `examples/`: tooling, tests, documentation and examples.
- `deploy/`, `docker/`, `.github/`, root Docker/Compose/Makefile configs: upstream deployment and automation sources, not configured or validated for the SQLite mock service.
- `assets/workpal-prototype/`: all previous offline prototype sources, scripts, assets, review notes, historical docs and outputs.

## Node mock data and supported behavior

SQLite is seeded once from authored fixtures. Project, issue, agent, skill, squad and autopilot record CRUD and preferences persist across restarts. `WORKPAL_DB=/absolute/path.sqlite` selects a different database. To reset, stop the service and move `server/data/` aside before restarting.

The local backend is single-user and single-workspace. It does not implement real authentication, model/agent execution, skill installation, external integrations, scheduling, billing, uploads or realtime execution. Unsupported operations return HTTP 501. Advanced issue filters/grouping remain partial. Keep the service bound to loopback. Empty fixture collections are not measured results.

## Verification and archive

`npm run check` runs local server checks/tests and builds the active web entry. With the app running and Playwright installed:

```sh
WORKPAL_PLAYWRIGHT=/path/to/@playwright/test node scripts/qa.mjs
```

This checks 20 desktop/mobile page loads and project title editing with reload persistence. The copied upstream CI, Go server and Next.js applications are outside this local validation. Dependency peer-version and large bundle warnings are inherited from the upstream frontend stack; Node 22 labels its SQLite API experimental.

`npm run prototype:check` checks and rebuilds the archived dependency-free HTML app. Historical reference scripts may still reference their original sibling repositories and temporary tooling paths.

## Documentation and components

Install all workspace dependencies with `pnpm install`. Start the documentation site with `npm run dev:docs` (port 4000), or the component explorer with `npm run storybook` (port 6006). Build them with `npm run build:docs` and `npm run build:storybook`. Desktop and mobile directories remain empty.

## Branding

Active source packages use `@workpal/*`; the Go module is `workpal.local/workpal/server`. No public service domain is configured. `.invalid` addresses in templates are non-resolving placeholders. Website/GitHub promotion entries are removed. Storage keys are copied to the Workpal namespace without overwriting existing values. The historical prototype archive is unchanged.

### Python application entrypoints

Prepare the Python environment as described in `server/README.md`, provision Redis,
and put the settings documented in `docs/python-environment.example` in the root
`.env`. Generate AUTH_SECRET once with `openssl rand -hex 32` and keep that value
in `.env` across restarts. The npm start/dev commands load this file automatically;
explicit shell variables take precedence. `.env` is ignored by Git; keep its
permissions at 600. The example contains no secret. The launcher applies schema migrations, without importing
legacy content or creating demo business records.

`npm run dev` and `npm run dev:web` start Python, its worker and Vite (web port
4174, API port 4175). `npm run build` builds the frontend; `npm start` serves that
build with Python on port **4174**, preserving the previous user-facing port.
`WORKPAL_PORT` overrides the Python port in either mode; `WORKPAL_WEB_PORT`
controls Vite. FRONTEND_ORIGIN defaults to the corresponding user-facing origin.
Ports must be free: the launcher never stops their existing owners. Redis and
explicit database configuration are required; failures do not fall back to Node.
Use `npm run dev:docs` for the independent documentation application.

## Independent mock demo (keep an existing 4174 running)

After `npm run build`, run the mock on a separate port with an isolated SQLite
database. This does not switch the existing Vite proxy or use the Python API:

```sh
WORKPAL_DB=/tmp/workpal-demo.sqlite node --input-type=module -e 'import {createServer} from "./server/api.mjs"; createServer().listen(4184, "127.0.0.1")'
```

Open http://127.0.0.1:4184/#/home and choose **Enter Workspace**. Keep this
process running during the demo. The temporary database retains demo edits until
it is removed or the system clears `/tmp`. Existing records in `server/data/`
are not imported by this command. Real model execution and production integrations
remain unsupported; this demo does not certify Python backend parity.
