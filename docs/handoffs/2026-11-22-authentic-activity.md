# Ticket activity authenticity correction

The issue API now excludes records explicitly marked with _fixture or fixture_source from comments, timeline events, task runs, and attachments. Direct reads of marked runs and attachments return 404. Raw SQLite history is retained. The generated evidence disclaimer and later-review links have been removed; they did not make synthetic history suitable for a product activity feed.

Authenticated status changes now append an activity with the actor, timestamp, and old/new status in the same transaction. Repeating an unchanged status creates no duplicate event. Comments and document submissions retain their existing authenticated persistence. A manual status change is not a claim of model execution or independent delivery verification.

scripts/reset-authored-progress.py defaults to a rollback-only preview. With --apply it first creates an online SQLite backup, then resets seeded issue progress to backlog and seeded projects to planned. Prior status and completion counters are retained in _archived_progress. It skips tickets with real status-change events and records already corrected. Applied to server/data/python/workpal.sqlite: 28 issues and 2 projects; second preview reports zero changes.

Demonstrable local capabilities: ticket editing, assignment, comments, document submission/download, revision-specific human review, and persisted status activity. Model execution and production integrations remain unavailable. Existing human-written documents are submissions, not proof that an agent executed their contents.

Verification: regression coverage checks fixture exclusion, blocked direct reads, retained raw history, real comment/status persistence, no-op status changes, document downloads, and revision-specific review. Frontend evidence-register tests cover the empty state. No browser walkthrough was performed in this change.

Final validation: npm run check passed, including 1,939 Python tests and 30 subtests, launcher tests, Node tests, and the web production build. Evidence-register Vitest: 2 passed. A read-only comparison with the backup confirmed identical record keys and exactly 30 changed bodies, with non-progress fields preserved. The first full check had loaded an obsolete history-display test before its update; the complete rerun passed.

Correction requested by the user: restored all 28 ticket columns and 2 project states from _archived_progress, including the previous completion counters. Verified every restored field after commit. Removed the reset script. Cleaning synthetic activity must not change board placement. The earlier progress reset described above is reverted.
