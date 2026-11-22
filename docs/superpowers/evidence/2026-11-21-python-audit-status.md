# Python legacy audit — preflight only

Scope: Task 1 audit strengthening and Task 5 isolated checksum invalidation tests. No launcher/browser changes, imports into real databases, process stops, backup operations, Node deletion, commits or PRs were performed by this worker.

The audit reads both databases with read-only SQLite connections and query_only transactions. It checks manifest counts against source kinds, deterministic workspace/source selection, user/member mappings, native workspace/user existence, membership identity/workspace association and valid roles/current ownership, every source record's retained source_body and position. Current body changes are reported separately and preserved; native display names and roles need not equal historical import values. Missing rows remain unproven deletions and block acceptance; importer idempotence and snapshots are unchanged.

Strict JSON parsing rejects duplicate fields, non-finite values and malformed data; unknown source schema and unsupported target data fail nonzero with a generic nonsecret error. CLI exposes identifiers, mappings, counts and checksums, never bodies/emails or traceback details for handled invalid data.

Reusable baseline check:
```sh
server/.venv/bin/python server/tools/audit_legacy_import.py --source SOURCE --target TARGET --expected-checksum BASELINE_SHA256
```
A mismatch fails even after a prior successful comparison. Isolated tests cover subsequent additions, edits and deletions; calling the comparator again is required after any renewed writes. An expected checksum is not proof that writers stopped. Every report remains preflight_only, including successful baseline comparisons.

Fresh TDD: initial expanded tests returned exit 1 (8 failed, 16 passed); implementation then passed. Final focused command: server/.venv/bin/python -m pytest server/tests/test_legacy_import.py -q — exit 0, 35 passed. Includes original 12→11 deletion, retained later edits, native display/role changes, manifest/mapping/member/position corruption, malformed source and target JSON, CLI failure and logical read-only checks.

Real database read-only command (with expected-checksum): exit 0, 1225 source and target rows, no missing rows, original-body differences, current-body edits or integrity errors. Source/manifest/baseline checksum: 590e97cdb68e1ed408647d545c01a5d67307376be2fbbb22ab1e7b53b6998028. Report: /tmp/workpal-audit-real-preflight.json. This is NOT final freeze evidence: no stopped-writer evidence, consistent frozen backup, bound application rollback SHA or browser acceptance was obtained. It does not authorize deletion.

Final full suite: server/.venv/bin/python -m pytest server/tests -q — exit 0, 666 passed, 30 subtests passed, no skips, 1 existing Starlette/httpx deprecation warning, 72.41s. Log: /tmp/workpal-audit-python-final.log. git diff --check — exit 0. npm run check was not run by this scoped worker (no active frontend/launcher changes).
