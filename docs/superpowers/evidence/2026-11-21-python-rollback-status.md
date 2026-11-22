# Isolated Python compatibility baseline rehearsal

Candidate: 9bbe7232384a5002fb9b0fe86c5594a7218fd093. Current application equals candidate: this is a compatibility baseline rehearsal, not a rollback across different business versions.

Command: WORKPAL_ROLLBACK_SHA=9bbe7232384a5002fb9b0fe86c5594a7218fd093 node scripts/python-persistence-qa.mjs
Exit: 0. git diff --check and node --check: exit 0. Prior aggregate check was not repeated.

Snapshot extracted with git archive into /var/folders/zn/dg1zfbv96p19qstvcpgsjvyr0000gn/T/workpal-persistence-TcmDl9/snapshot; npm start cwd is that snapshot, PYTHONPATH explicitly points to snapshot/server/src. Existing venv and node_modules reused by symlink. npm start invokes Python production launcher, never Node business backend. Build was copied from the previously verified current build (not tracked by Git); index SHA256 cb5f739fc368efa6aa62cd19fca6e608077a131fda3ccc2a630c95eb73451691.
Build tree SHA256 (relative paths + NUL + bytes): f422fb86e10a88fb9fbae4958c3c0ef8cde99e3cfde5f6f327f8ec5764f1715f.
Snapshot server/src tree SHA256: ff56349dbbac9ae7fc9ef892eccb35ba18652290290bfdf740d3940d9a908f20.
Build artifacts retained in temporary snapshot; future reconstruction must match this digest or be reverified.

Same absolute Python SQLite: /var/folders/zn/dg1zfbv96p19qstvcpgsjvyr0000gn/T/workpal-persistence-TcmDl9/python.sqlite; schema revision 0014.
Created issue b9228f77-5b87-4719-b1c6-8cc47a52b2e9, edited description and posted comment before shutdown. Snapshot read all three after restart, preserved TAP-029 deletion (404), then HTTP PUT and GET confirmed description 'Snapshot write b9228f77-5b87-4719-b1c6-8cc47a52b2e9' in same database.
Legacy isolated copy SHA256 unchanged: 817abc6d5d2c5dd29e3e15b634ad55a52a3779bb6cd855bc5daa6934bb22c89a.
Only owned process groups stopped. Source real database opened read-only for SQLite backup; never used as runtime database. No external service mutation/flush, push, PR, Node deletion or worktree.

Configuration: docs/python-environment.example; explicit absolute WORKPAL_DATABASE_URL, temporary uploads, random AUTH_SECRET (not recorded), development auth, loopback port 24374, existing Redis 26379 with random namespace. Logs/SQLite remain at artifact path, not committed.

Remaining release gates: coordinate real source/target writer shutdown and restart supervision, frozen backups and final source digest/target audit binding, release authorization, Node consumer cleanup/deletion and post-deletion checks. This isolated success does not authorize deletion; future incompatible schemas require a new baseline.

Exact baseline commit files:
```
README.md
apps/web/vite.config.mjs
docs/python-environment.example
docs/superpowers/evidence/2026-11-21-python-audit-status.md
docs/superpowers/evidence/2026-11-21-python-browser-status.md
docs/superpowers/evidence/2026-11-21-python-contract-realtime-status.md
docs/superpowers/evidence/2026-11-21-python-cutover-preflight.json
docs/superpowers/evidence/2026-11-21-python-cutover-status.md
docs/superpowers/evidence/2026-11-21-python-launcher-status.md
docs/superpowers/plans/2026-11-21-python-cutover-plan.md
docs/superpowers/specs/2026-11-21-python-cutover-design.md
evidence/2026-11-21-python-persistence-status.md
package.json
scripts/python-persistence-qa.mjs
scripts/python-web-dev.mjs
scripts/python-workspace-import-qa.mjs
scripts/workpal-start.mjs
scripts/workpal-start.test.mjs
server/src/workpal_backend/app.py
server/src/workpal_backend/cli.py
server/src/workpal_backend/config.py
server/src/workpal_backend/frontend.py
server/src/workpal_backend/legacy_audit.py
server/src/workpal_backend/workspace_content/routes.py
server/tests/test_frontend.py
server/tests/test_legacy_import.py
server/tests/test_realtime.py
server/tests/test_workspace_content.py
server/tools/audit_legacy_import.py
tests/python-web/auth.spec.ts
tests/python-web/capabilities.spec.ts
tests/python-web/launcher.test.mjs
tests/python-web/realtime.spec.ts
```

Execution output:
```
(node:88433) ExperimentalWarning: SQLite is an experimental feature and might change at any time
(Use `node --trace-warnings ...` to show where the warning was created)
IMMUTABLE SNAPSHOT 9bbe7232384a5002fb9b0fe86c5594a7218fd093 /var/folders/zn/dg1zfbv96p19qstvcpgsjvyr0000gn/T/workpal-persistence-TcmDl9/snapshot build index sha256 cb5f739fc368efa6aa62cd19fca6e608077a131fda3ccc2a630c95eb73451691
PASS before restart b9228f77-5b87-4719-b1c6-8cc47a52b2e9 TAP-029
PASS after same-database restart b9228f77-5b87-4719-b1c6-8cc47a52b2e9 TAP-029
SAME DATABASE /var/folders/zn/dg1zfbv96p19qstvcpgsjvyr0000gn/T/workpal-persistence-TcmDl9/python.sqlite schema [ [Object: null prototype] { version_num: '0014' } ] record b9228f77-5b87-4719-b1c6-8cc47a52b2e9 description Snapshot write b9228f77-5b87-4719-b1c6-8cc47a52b2e9
PASS snapshot continued write; legacy sha256 unchanged 817abc6d5d2c5dd29e3e15b634ad55a52a3779bb6cd855bc5daa6934bb22c89a
QA artifacts: /var/folders/zn/dg1zfbv96p19qstvcpgsjvyr0000gn/T/workpal-persistence-TcmDl9
```
