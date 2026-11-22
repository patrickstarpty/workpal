# Shared inbox ownership and escalation policy
Revision 1. Prepared by Codex for review; no organizational acceptance is recorded.

## Responsibility contract
Each incoming item has one accountable triage owner until a named receiver acknowledges it. Assignment to a squad makes the squad responsible for coordination, not every member responsible for the response. The triage owner checks workspace, source, existing related work and urgency before creating or linking a ticket.

## Routing table
| Input | Initial action | Receiver | Acceptance evidence |
| --- | --- | --- | --- |
| Ordinary question | Check existing answer and clarify missing context | Relevant domain agent or member | Receiver acknowledges the question and response scope |
| Reproducible defect | Capture expected/actual behavior and reproduction | Delivery squad | Linked ticket with reproducible input and owner |
| Suspected incident | Preserve impact and timestamps; stop speculative changes | Incident Commander | Incident scope and named responding owner |
| Unclear request | Ask for the missing decision; retain ownership | Original requester | Clarified outcome, not automatic escalation |
| Duplicate | Link the existing item without losing requester context | Current ticket owner | Existing owner confirms coverage |

## Escalation rules
Escalate immediately when current evidence indicates access leakage, loss of user records or interruption of a critical workflow. For ordinary questions, the workspace owner must set a response target before overdue escalation can be automated; this document supplies no invented service-level commitment. If a receiver declines or does not acknowledge, the triage owner remains accountable and asks the workspace owner to assign a receiver.

## Response acceptance
A response must cite the relevant deliverable/version or explicitly state that the requested work remains unperformed. A closed inbox message does not automatically close its ticket. Acceptance records identify the accepting member, scope accepted and unresolved work. Do not infer acceptance from a read receipt, emoji reaction or completed Run.

## Verification and open decisions
Exercise an ordinary question, duplicate, urgent report, declined handoff and a resolved response with an open follow-up. Confirm each retains one accountable owner and links its ticket. Actual roster acceptance, response targets and production inbox integration remain unverified.
