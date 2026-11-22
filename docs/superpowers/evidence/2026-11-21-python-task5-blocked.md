# Task 5 preparation — blocked before maintenance

2026-11-21. Parent authorization permits deletion only after frozen reconciliation. No service stopped, database changed, backup claimed, or Node module deleted in this run.

## Recovery configuration gate

Reconfirmed PID 39410: ppid 1, Node scripts/python-web-dev.mjs, cwd /Users/patrick/Desktop/Workspace/ai-native/workpal. Its children 39414/39415 are Python CLI worker/serve. This identifies the owned launcher; ppid 1 alone does not prove absence of restart supervision. That gate remains unproven and must be checked immediately before maintenance.

Presence-only inspection of this execution shell: AUTH_SECRET, WORKPAL_DATABASE_URL, REDIS_URL, REDIS_KEY_PREFIX, WORKPAL_DEV_AUTH all absent. Repository has .env.example and docs/python-environment.example, no local .env recovery configuration. No process environment/memory, unrelated credential store or secret value was read. Existing service remains running. Supply an authorized recovery environment/configuration path, including the existing AUTH_SECRET and explicit same Python database/Redis/auth settings; do not put secrets in this report or chat. A fresh process/cwd/ownership and supervisor check is still required before stopping anything.

## Independent preparation

Consumer inventory (excluding historical docs, archive, outputs and Go): package.json test/check references Node tests/API/store; scripts/avatar-channels-qa.mjs, contribution-qa.mjs, login-entry-qa.mjs, mock-data-qa.mjs and web-components-qa.mjs import Node API. web-components also imports fixtures. Internal dependency chain: API -> store/contribution/mock-content; store -> fixtures/contribution; fixtures -> seed/mock-content; contribution -> seed. server/mock-content.test.mjs and contribution.test.mjs exercise old implementation.

Retain migration tools, Python fixtures/tests, Go, original databases and historical contract provenance (routes.json, protected-baseline.json and batch source references). No tracked files were found under server/python/tests; no cleanup justified there.

QA disposition prepared: login behavior belongs in tests/python-web/auth.spec.ts; avatar/channel and component navigation need explicit Python coverage comparison before retiring their scripts; contribution aggregation belongs in Python contribution tests; mock-data fixture assertions are not product guarantees, but retained navigation/persistence checks must be mapped explicitly. Do not delete all QA merely because it imports Node. Python import QA already uses an independent fixture per prior accepted evidence.

Fresh isolated verification: server/.venv/bin/python -m pytest server/tests/test_legacy_import.py -q: exit 0, 35 passed in 6.54s. This validates audit/import and checksum-change blocking without freezing or writing real business databases. No post-deletion aggregate/browser acceptance is claimed because deletion has not occurred.

## Required continuation

With authorized recovery configuration and confirmed lack of restart supervision: recheck owned processes, stop only launcher and its children, verify both databases have no writers, SQLite backup API to timestamped server/data/python/backups directory, freeze audit with expected checksum 590e97cdb68e1ed408647d545c01a5d67307376be2fbbb22ab1e7b53b6998028, bind target snapshot/schema 0014/current SHA/time. Any unexplained difference blocks deletion; restore Python with original configuration, never reimport/overwrite. Preserve and seal old DB with documented reversible permissions. Only then apply prepared source retirement and run complete check, seven browser cases, import QA and persistence QA. Restore same real Python database and verify health/frontend/read-only business access.

Prior Python compatibility baseline: 9bbe7232384a5002fb9b0fe86c5594a7218fd093; prior evidence commit 80f5a491. Refer to python-rollback-status for immutable archive/build hashes and same-database rehearsal. These are inherited pre-freeze evidence, not fresh final reconciliation. Backups/frozen snapshot/post-deletion evidence: not created. Task 5 remains incomplete.
