# Deploy — Release Checklist

Revision: 2
Ticket: TAP-288
Owner: Release Engineer

## Release gates
- QA acceptance completed.
- Security review completed.
- Workspace owner approved release after reviewing v2.
- Previous configuration snapshot retained.

## Rollback
Pause edits, retain the current SQLite file, restore the pre-release snapshot and verify workspace membership and role references.

## Handoff
Reliability Engineer owns source drift review, broken-reference checks and the next maintenance checkpoint.
