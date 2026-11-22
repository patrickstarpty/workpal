# Portable business data and documents

Document files and execution claims are separate. Existing documents are now stored completely in workspace_records/attachment_contents. Text uses UTF-8 text; binary files use base64 JSON. Authenticated, workspace-scoped attachment endpoints serve the stored bytes. No delivery endpoint reads a local static file.

Imported 72 documents, including 6 TDS DOCX files. Original attachment metadata is retained in archived_attachments. Previously hidden documents receive a current “Document imported” activity attributed to the workspace owner on whose behalf the import was requested. Historical simulated comments, approvals, and runs remain filtered; import does not assert that their described work occurred. Existing real document submissions retain their original activities. All issue/project status values were preserved.

Migration: PYTHONPATH=server/src server/.venv/bin/python scripts/import-delivery-documents.py
It backs up the database, imports all documents transactionally, and skips already imported documents. Missing content fails the transaction explicitly.

Portability verification: PYTHONPATH=server/src server/.venv/bin/python scripts/verify-portable-workspace.py
It copies only SQLite into a temporary directory and starts the API without a frontend directory. It checked 131 distinct business records through their HTTP endpoints and downloaded all 72 documents with SHA-256 comparison and visible activity links. The temporary verification session does not alter the source database. Authentication coverage also includes rejecting foreign workspace requests.

Regression coverage includes binary downloads without source files, workspace access, repeat-import idempotence, retention of original metadata, unchanged ticket status, and keeping fictional execution claims out of the restored document activity.

Model execution and production integrations are still unavailable. Document presence does not establish execution or approval.

Validation completed: npm run check passed (1,941 Python tests, 30 subtests, Node and launcher tests, web build). SQLite-only HTTP verification passed for 131 distinct business records and 72 document downloads.
