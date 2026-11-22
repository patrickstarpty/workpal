# SMART-11 — Review workspace release readiness

Revision: 2

## Release readiness checklist
- Scope: attach the accepted change list before release approval.
- Verification: link the accepted regression review and unresolved findings.
- Decision owner: workspace owner authorizes release separately from readiness review.
- Release owner: Release Engineer prepares the release and retains the preceding configuration.
- Rollback owner: Reliability Engineer checks restored configuration, workspace access and attachment availability.
- Stop condition: an unresolved acceptance blocker keeps release closed.

## Rollback handoff
Release Engineer supplies the preceding configuration reference and change list. Reliability Engineer confirms restored access and attachment availability before the owner closes recovery.

## Review response
Added rollback verification ownership and explicit recovery acceptance criteria. Awaiting the owner's readiness decision; no deployment is recorded.

## Decision / remaining gate
Await the workspace owner’s readiness decision; release execution remains a separate action.
