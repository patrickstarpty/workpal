# Task 3 launcher evidence

Scope: unified Python entrypoints and lifecycle only. Node files retained. No real database writes, model calls, external process termination, archive/output modifications, commits, pushes or PRs. This does not certify the full cutover, browser acceptance, data audit or rollback.

Changes: npm dev/dev:web/start now use Python lifecycle; npm start retains user-facing port 4174 (development web 4174/API 4175). Explicit WORKPAL_PORT is passed consistently to Python and Vite. All Vite modes proxy API/auth/WS/v1/plugin-surfaces. check retains nine Node comparison tests, adds Python and launcher suites, then builds frontend. README and docs/python-environment.example explain explicit configuration, secret provisioning, schema-only migration and independent docs command. Production frontend rejects an index symlink escaping its build root.

Fresh evidence:
- Redis configuration TDD: node --test scripts/workpal-start.test.mjs: exit 1, 1 passed/1 failed before implementation.
- Static index symlink TDD: pytest server/tests/test_frontend.py: exit 1, 2 passed/1 failed; after fix exit 0, 3 passed.
- npm run check first run: exit 1, Node 9 passed; Python 645 passed/1 failed, 30 subtests. Failure test_invitation_conclusion_pipeline[False-decline]: Redis socket timeout. No test was skipped or weakened.
- npm run test:launcher initial expanded run: exit 0, 12 passed. Next run exposed kill EPERM during process-group existence probes (12 passed/2 failed); inaccessible groups are now excluded from signalling.
- npm run test:launcher after probe fix: exit 0, 14 passed.
- npm run check second run: exit 0; Node 9 passed, Python 646 passed plus 30 subtests, launcher 15 passed; frontend built in 7.70s. Collection preceded the additional symlink test; separate fresh static suite above covers it.
- Final `npm run check` after adding unavailable-Redis coverage: exit 0; Node 9 passed, Python 647 passed and 30 subtests, launcher 16 passed, frontend built in 6.51s. Log: `/tmp/workpal-task3-final.log`. Redis-unavailable test observed HTTP 503 readiness and confirmed port release. `git diff --check` exit 0.

Real lifecycle tests use temporary SQLite paths, independent ports 24984/24985, 24994/24995 and 25085, random Redis prefixes on the existing Redis endpoint 26379, and test-only random authentication tokens. Development frontend HTTP and production frontend/API health/unknown API are checked. SIGINT/SIGTERM release owned ports; worker crash, API early exit, readiness timeout, migration failure, nonexistent executable, occupied external listener preservation, and exited-worker descendants including TERM-resistant descendants are covered. No shared Redis flush is used. Readiness timeout is injectable for deterministic failure tests.

Remaining full-cutover gates belong to parent review: browser flows, audit strengthening, final freeze/reconciliation, rollback rehearsal and Node deletion authorization. Original Node files remain present.
