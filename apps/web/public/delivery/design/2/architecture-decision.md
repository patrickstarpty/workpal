# Design — Architecture Decision

Revision: 2
Ticket: TAP-285
Owner: Software Architect

## Decision
Use stable role IDs across the role catalog and workspace. Display names may change without changing identity.

## Boundaries
Catalog describes capability; workspace owns membership and task assignment. Runtime availability is independent of role identity.

## Recovery
Back up SQLite before imports. Validate every role and leader reference before commit.

## Rejected option
Generating agent IDs from display names causes duplicate agents after renames.
