Latest scoped contract/WS acceptance: [contract and realtime status](2026-11-21-python-contract-realtime-status.md): six observed read gaps classified, comment/identifier regressions and reconnect/nonmember checks passed; final npm run check exit 0 (670 Python tests + 30 subtests, Node 9, launcher 16, build). Full rollback/freeze/deletion remains pending.

Latest Task 4 checkpoint: [browser status](2026-11-21-python-browser-status.md). Import QA no longer loads Node store; fresh browser failure and integration gaps recorded. Task 4 remains incomplete; Node retained.

Latest audit status: see [2026-11-21-python-audit-status.md](2026-11-21-python-audit-status.md). Task 1 audit and Task 5 isolated checksum blocking are implemented; real data was audited read-only as preflight only. Earlier statements below about missing audit checks and unimplemented freeze mutation tests are historical and superseded. Final maintenance freeze, browser acceptance, rollback SHA and Node deletion remain pending.

Current launcher status: see [2026-11-21-python-launcher-status.md](2026-11-21-python-launcher-status.md). The entrypoint/check statements below describe earlier snapshots and are superseded by that report. Full cutover and Node deletion remain unapproved.

# Python cutover implementation evidence — incomplete

Node deletion is NOT authorized by this evidence. No source or target business data was written. No external process was stopped. No rollback commit has been established.

Changes: `server/src/workpal_backend/legacy_audit.py`, `server/tools/audit_legacy_import.py`, and `server/tests/test_legacy_import.py`.

Fresh TDD run: `server/.venv/bin/python -m pytest server/tests/test_legacy_import.py -q` first produced 1 failed / 15 passed (missing audit module), then 16 passed in 3.82s, pytest exit 0. These are fresh executions, not inherited 15/15 evidence. Test covers 12→11 deletion with unchanged manifest and importer still reporting 12.

Read-only audit command: `server/.venv/bin/python server/tools/audit_legacy_import.py --source server/data/workpal.sqlite --target server/data/python/workpal.sqlite`, exit 0. Source and target contain 1225 imported rows, no missing rows, original content differences or current content edits. Logical checksum and manifest match: `590e97cdb68e1ed408647d545c01a5d67307376be2fbbb22ab1e7b53b6998028`. JSON retained alongside this report. This is preflight only, not a frozen snapshot or deletion permit.

Freeze not established: lsof observed Python PIDs 39414 and 39415 holding target database open. Ownership and restart supervision were not established; these processes were not killed. No backups or final freeze reconciliation were performed.

Task 1 remains incomplete: audit needs broader relationship/canonical-row checks, source-change/edits/CLI exit/read-only tests and manifest consistency checks. Current audit validates imported workspace records against source and reports edits separately; it does not yet prove canonical identity/workspace/member integrity.

Tasks 2–5 remain unimplemented/unverified in this handoff. npm run check, full Python suite, launcher lifecycle, Playwright, freeze mutation tests and rollback rehearsal have NOT been run. No skips are being counted as passes. npm start still points to Node. No compatibility rollback SHA exists. Do not delete Node files or claim the cutover complete.

Existing untracked archives, outputs, design and plan were preserved. No commit, push or PR was made.

Implementation continuation: added confined optional Python frontend hosting and serve --frontend-dir. TDD: frontend test collection failed exit 2 (missing module), then 2 passed exit 0. Covers SPA, assets, HEAD, API exclusions, encoded traversal and missing build. Full Python suite: 646 passed, 30 subtests passed, one deprecation warning, exit 0 (70.70s); log /tmp/workpal-python-cutover-tests.log.

Launcher production mode now reuses development lifecycle and serves frontend via Python; missing-build test first failed exit 1, then passed exit 0. New workpal-start.mjs exists but package entrypoints intentionally not switched before lifecycle and browser verification. npm run check launched separately; result pending. No rollback SHA, browser evidence, final freeze or Node deletion. Tasks 1, 3–5 remain incomplete; these are implementation gaps, not exclusively a real-database freeze blocker.

npm run check completed exit 0: existing Node regression tests 9/9 and frontend build passed (chunk-size warnings). Current check still lacks Python integration; passing it does not certify cutover. node --check scripts/python-web-dev.mjs exit 0. No commit made.
