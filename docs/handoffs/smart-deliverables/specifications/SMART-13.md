# Attachment recovery requirements
Revision: 1. Prepared by Codex in the current evidence repair. Proposed requirements; historical acceptance is not confirmed.

## User outcome
A user knows whether an interrupted upload can continue, must restart, requires sign-in, or needs the local file selected again. No action creates duplicate accepted attachments or hides a failure behind a success message.

## Functional requirements
R1. Keep the filename and last confirmed server progress visible while the local file remains readable. Do not label estimated or restarted progress as acknowledged progress.
R2. Distinguish retryable connection failure, denied/expired authorization, unavailable file and explicit cancellation.
R3. Reuse transfer identity only when the backend validates that identity and continuation capability. Otherwise restart explicitly; do not claim byte-offset resume.
R4. An explicit retry starts at most one active request. Pending retries cannot be duplicated by repeated clicks.
R5. Cancelling prevents queued retries and ignores late completion for that request generation.
R6. Completion requires the server's durable attachment acknowledgement, not a client progress value of 100 percent.
R7. Every request rechecks workspace membership and attachment association. Switching workspaces must not transfer an attachment to another ticket implicitly.

## Acceptance matrix
| Requirement | Required evidence |
| --- | --- |
| R1/R3 | Server API contract, transfer identity and byte progress captured before/after interruption |
| R2 | Browser recordings/screenshots of each distinct error and available action |
| R4/R5 | Request trace proving single retry and no retry after cancellation |
| R6 | Persistence test and reload showing accepted attachment |
| R7 | Two-workspace and revoked-membership tests with no leaked metadata or content |

## Exclusions
No recovery promise after local bytes are lost; no automatic production release; no external-storage certification without an accessible test environment; no migration of attachments between workspaces; no inference that cleanup of expired upload intents proves partial-transfer resume.

## Inputs and downstream ownership
SMART-8 specifies interactions. SMART-7 must deliver implementation and review. SMART-10 supplies the measured regression report. SMART-17 requires a separate release decision. The current local upload verification confirms selected cleanup/HTTP behaviors only; its uncovered scope remains mandatory before full delivery acceptance.

## Open decisions
The backend continuation API and file identity algorithm have not been established in this audit. Product owner must decide whether explicit restart is sufficient for this scope or true byte-offset resume is required. This document does not record that decision on their behalf.
