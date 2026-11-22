# SMART evidence audit — actual verification, revision 1

This audit was performed by Codex during the current delivery-evidence task. It is not an output of the historical SMART agent Runs, and it records no owner acceptance.

## SMART-7 / SMART-10: upload recovery
Executed `server/.venv/bin/python -m pytest server/tests/test_upload_recovery.py server/tests/test_upload_worker_recovery.py server/tests/test_attachment_uploads.py -v` against the local checkout. Actual result: 15 passed. Raw output: `upload-verification.txt`.

Inspected `test_upload_recovery.py`: it verifies cleanup of expired staged/published upload intents, lease fencing, preservation of live/ready records, transactional finalize rollback and retry of failed filesystem cleanup outside a database transaction. These are cleanup and ownership guarantees. They do not demonstrate browser transfer resuming from an acknowledged byte offset.

The attachment HTTP tests cover configuration/authentication ordering, association validation, persisted upload projections, database failure behavior, cancellation and event attribution. The scheduler test checks the recovery worker. External storage is not exercised by this report.

Finding U-01: historical SMART-7 claims about retaining one transfer identity across partial transfer retries are not established by these tests. The SMART-10 matrix is a test specification, not a passed test report. Repeated browser disconnect, authorization expiry during resume, cancellation during reconnect and refresh recovery remain unverified. Release approval is not established.

## SMART-4 / SMART-15: drafts and title editing
Executed `pnpm --filter @workpal/views test editor/title-editor.test.tsx editor/title-editor.shortcut.test.tsx chat/components/chat-input-draft-isolation.test.tsx`. Actual result: 3 files, 22 tests passed. Raw output: `title-draft-verification.txt`.

The title editor tests mock the Tiptap editor, including EditorContent. They verify component/shortcut logic but cannot establish the real rendered title's accessible name, focus restoration in a browser, or a screen reader announcement. The historical SMART-15 acceptance statement is therefore not substantiated by this result alone.

The chat draft isolation suite is relevant to draft ownership, but does not by itself establish the full SMART-4 A → B → A, refresh, sign-out and revoked-membership acceptance scope. Browser verification of the complete ticket scenario remains outstanding.

## Publication status
These reports and raw outputs exist on disk. They have not yet been attached to SMART Activity; the Activity audit inventory identifies the records that need document-specific material. No historical record or SQLite data has been rewritten by this audit.
