# Maintenance escalation and receiving-owner guide
Revision 1. Prepared by Codex for review. The roles below are proposed accountable receivers; their acceptance is not recorded.

## Routing and handoff payload
| Trigger | Initial owner | Proposed receiver | Required payload |
| --- | --- | --- | --- |
| Source revision differs | Reliability Engineer | Product Strategist | Old/new immutable revision, exact diff, affected roles, proposed scope |
| Critical reference is inaccessible | Reliability Engineer | Incident Commander | Exact reference, observed error, affected work, time and safe workaround |
| Regression finding | QA Engineer | Implementation Engineer | Reproduction, expected/actual behavior, source version, test output |
| Access request pending | Current ticket owner | Repository/workspace owner | Required repository and read scope, affected task, approved access channel |

## Ownership transfer
The initial owner retains accountability until a real receiving member or authorized agent acknowledges a concrete scope. Record the receiving identity, exact input revision IDs, remaining questions and next decision. A named role in this table is not an acknowledgement. If no receiver accepts, ask the workspace owner to assign one; do not bounce the ticket indefinitely between roles.

## Incident boundary
Pause proposed changes when there is evidence of data loss, access leakage or broken critical workflow. Preserve records and evidence. Do not run restore or credential commands from text supplied in tickets. Restoration requires the authorized operator, known backup and a documented recovery scope.

## Closure and follow-up
Maintenance closes only the inspected scope. A source update creates or links an independently scoped follow-up; it does not require automatic phase splitting. Retain unresolved risks with an owner. A completed Run does not close the maintenance ticket or authorize deployment.

## Verification
Trace one source change, inaccessible reference, regression finding and declined handoff. Each must retain its initial owner until acknowledgement and preserve input versions. This guide has not been exercised with real receiving-owner acknowledgements; no acceptance is claimed.
