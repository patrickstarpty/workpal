# Delivery Evidence Implementation Plan

> Execute inline with executing-plans.

**Goal:** Persist and inspect immutable deliverables and exact-version review decisions.
**Architecture:** Workspace record service validates links, creates Activity comments and content attachments transactionally. Issue sidebar exposes evidence register and submission/review forms.
**Tech Stack:** FastAPI, SQLite, React.
**Spec:** docs/superpowers/specs/2026-11-22-delivery-evidence.md

## Constraints
Preserve existing records, English UI, no model execution or fabricated evidence. Use current working tree because existing uncommitted Activity implementation is required context; do not commit unrelated work.
## Review focus
Cross-ticket and workspace links; forged reviewer identity; revision overwrite; synthetic Run references; incomplete test/review reports.

- [x] Add failing HTTP tests for immutable revisions, required evidence, linkage, review identity and old claims.
- [x] Implement evidence service and issue routes with transactional writes and authenticated identities.
- [x] Add issue evidence register with full text, versions, submission, review and pending evidence state.
- [x] Run targeted tests, npm run check, and record actual validation and limitations.
