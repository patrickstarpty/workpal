# Python backend foundation

Supported Python: 3.11. Install locked dependencies with `uv sync --project server --locked`.
From the repository root:

```
server/.venv/bin/python -m workpal_backend.cli migrate
server/.venv/bin/python -m workpal_backend.cli serve
server/.venv/bin/python -m pytest server/tests/test_config.py server/tests/test_database.py server/tests/test_health.py
```

Migrations are explicit and idempotent. Unknown pre-existing schemas are rejected. Default database: `server/data/python/workpal.sqlite`; relative paths resolve from repository root. Mock database paths, symlinks and hardlink aliases are rejected. SQLite uses WAL, foreign keys and a 250 ms busy timeout. `DatabaseBusy` is retryable only when the caller can safely repeat the operation. Transactions commit on success and roll back on exceptions. Back up SQLite using its backup API with writers coordinated; future upload bytes must be backed up consistently too.

Settings: WORKPAL_DATABASE_URL (SQLite file URL), REDIS_URL, REDIS_KEY_PREFIX, WORKPAL_HOST, WORKPAL_PORT, WORKPAL_ENV, WORKPAL_DEV_AUTH and AUTH_SECRET. No signing secret is built in. Development auth requires development mode and loopback binding. Redis URLs are never included in health responses. Use unique test prefixes; never flush shared Redis. Host processes use published Docker ports; containers use their network service names. Inspection found Redis published at 127.0.0.1:26379 and :6379; authentication requirements must be supplied by the operator.

`/health` reports process liveness; `/readyz` and `/healthz` require database access, current migration revision and Redis ping. API startup never migrates automatically; `scripts/python-web-dev.mjs` explicitly migrates before starting the API, worker and Vite. Lifespan shutdown closes Redis and SQLAlchemy pools. Development authentication, native workspaces/membership, event infrastructure and the migrated local content APIs are available. Model execution, installation and production integrations remain unsupported. Root npm defaults remain unchanged; use the Python launcher with its documented environment to run the Python-backed application.

## Import the previous local workspace

Keep the source at `server/data/workpal.sqlite`; do not point Python directly at that file. Stop writers and back up both databases through SQLite's backup API before a real import. The destination account must already exist (the local default account is `workpal@fwd.com`). With `WORKPAL_DATABASE_URL` set to the intended Python database:

```sh
server/.venv/bin/python -m workpal_backend.cli import-legacy --source server/data/workpal.sqlite --owner-email workpal@fwd.com --dry-run
server/.venv/bin/python -m workpal_backend.cli migrate
server/.venv/bin/python -m workpal_backend.cli import-legacy --source server/data/workpal.sqlite --owner-email workpal@fwd.com
```

Dry-run makes no changes and can report that migration 0014 is still needed. The import requires the source's single-workspace schema, runs atomically, retains all original JSON bodies, maps historical identities to native UUIDs, and grants the existing destination account owner access. An identical rerun skips the import, preserving later edits/deletions; a changed source or conflicting destination is rejected. Projects, tasks, comments, skills, squads, runtimes, stored analytics and contribution records are read from the Python database after import.

Run `node scripts/python-workspace-import-qa.mjs` for an isolated database/browser acceptance check (requires the configured local Redis). Set `WORKPAL_QA_URL=http://127.0.0.1:4174` to validate an already migrated running service without importing or modifying its workspace records. This check signs in and out in its own browser context.

Imported history is the existing local dataset, not new measured model output. Session records and their embedded messages are preserved, while chat-message execution/history endpoints that were unsupported by the old local backend remain unsupported. Legacy preference rows with noncanonical query parameter order may need reconciliation if a future source contains them; the migrated TAP snapshot has none.

## Repository layout

Python lives directly in `server/` (`src/`, `tests/`, `migrations/`, `contracts/`, `tools/`). Original Go sources and migrations are archived in `server/go/`. Node mock files and `seed.json` remain in `server/`; existing records remain in `server/data/`.

## Local workflow team catalog

`apps/web/app/capabilities/data/role-profiles.json` records the original workflow
URL and author for each Workpal role. Job titles and squad compositions are
Workpal adaptations, not claims that the authors published those exact squads.
The sources are Lauren Tan's pstack, Garry Tan's gstack, Matt Pocock's skills and
Andrej Karpathy's autoresearch. Every source URL identifies a repository revision.

With the same environment as the local service, run
`server/.venv/bin/python scripts/register-workflow-team.py` to register the catalog
in the `review` workspace for `workpal@fwd.com`. It requires development auth,
backs up SQLite first, inserts missing `workflow-*` records and preserves existing
records on reruns. It registers offline role descriptions and squad membership;
it does not install skills, execute agents or produce experimental results.

## Recorded lifecycle delivery

`server/.venv/bin/python scripts/register-lifecycle.py`, using the service's
environment, registers the `Workflow team delivery` project and six linked stage
tickets after the workflow team is registered. It requires a healthy local API
and a successful source-team check log, retained in
`server/data/lifecycle-evidence/source-team-check.log` (or the initial
`/tmp/workpal-sourced-team-check.log`). It backs up SQLite first and preserves
existing ticket and comment records on reruns. Source skills are registered as
instruction references, not installed executable integrations.

Stages 01–05 describe observed local configuration work; 06 is pending upkeep.
Evidence notes identify setup tooling, record their actual insertion time, and
never impersonate an agent run. Earlier `fixture_source` discussions are labelled
as authored historical references on read; their stored text is preserved.
