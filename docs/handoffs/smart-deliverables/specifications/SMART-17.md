# Upload recovery release handoff
Revision 1. Prepared by Codex during the current evidence repair. No historical agent execution or owner acceptance is asserted.

## Purpose
Receive SMART-7 implementation and SMART-10 verification only after their actual acceptance.

## Exact input versions
- SMART-7: revision `50a0e8a2-0742-44f0-a838-7a2aefd7358c`; producing Activity `b64fbc47-d124-444c-8126-6a0814e898cc`.
- SMART-8: revision `8f65bef3-9e57-4ec9-83aa-ee68b2649eca`; producing Activity `01b2d698-73e4-446a-a78d-ef23da769e31`.
- SMART-10: revision `dacdfc86-71cb-4215-bfe1-459e5e9a9674`; producing Activity `d447e988-25be-468b-91f8-75cec0691c48`.
- SMART-13: revision `457c753b-b581-4d35-bfdc-5d880268b703`; producing Activity `6f07ad4a-cdd1-44ed-961a-03a3a6fa37d2`.
- SMART-16: revision `1ee72f52-ebb6-4fbb-ad37-2d5aeef78943`; producing Activity `8c502da9-ebb2-4bce-9818-057a2b6d96d3`.

## Evidence gates
| Gate | Required material | Actual state |
| --- | --- | --- |
| Scope | Reviewed recovery requirements, exact version | SMART-13 revision 1 exists; review outstanding |
| Interaction | Recovery state and keyboard specification | SMART-8 revision 1 exists; review outstanding |
| Implementation | Scoped code diff and review/fix/recheck | No verified recovery feature diff identified |
| Regression | Executed transfer-recovery matrix | SMART-10 has 15 passing local cleanup/HTTP tests; browser resume cases remain uncovered |
| External storage | Isolated adapter verification | SMART-16 protocol exists; external cases not run |
| Release | Named operator, target and owner decision | No actual approval or deployment record |

## Rollback prerequisites and procedure
Before any release, the authorized operator must identify the exact previous application/configuration version and a tested database backup. Record backup digest, schema compatibility and restoration owner. Quiesce writes before a database restore, retain the current database as an incident artifact, restore only with explicit authorization, and validate workspace membership, attachment associations and a known content digest before reopening writes. Never treat the backups created for evidence publication as a tested production rollback package.

Stop the release if any gate is absent, the rollback has not been verified, or ownership is unacknowledged. These instructions have not been executed.

## Responsibility and acceptance ledger
Proposed preparer: Release Engineer. Proposed rollback verifier: Reliability Engineer. Decision authority: workspace owner. These are role assignments for the proposed process, not proof that a person accepted the handoff. Actual reviewer: none recorded. Accepted version: none. Open issues: resume API/implementation, browser regression, external storage verification and release/rollback authorization.

