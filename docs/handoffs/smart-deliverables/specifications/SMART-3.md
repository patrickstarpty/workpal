# Resumable attachment upload implementation contract
Revision 1. Prepared by Codex for scope and engineering review. This is a requirements contract, not an implemented diff.

## Completion boundary
True resume means preserving a server-recognized transfer identity and continuing from an acknowledged offset. Restarting an upload request is a different capability. Before implementation, establish which behavior the backend actually supports and expose the corresponding action honestly.

## Required server contract
Initiation returns a workspace-bound transfer identity, expiry and continuation capability. Status returns authoritative acknowledged progress. Each write validates access, expected offset and transfer generation. Repeated identical writes must not append duplicated bytes. Finalization verifies integrity and atomically associates exactly one durable attachment with the ticket. These are proposed semantics, not existing endpoints claimed by this document.

## Client and cancellation
Retain local file access only while available. Treat progress as confirmed only after a server response. Serialize retries and ignore stale responses after cancellation or replacement. Authorization failure requires user action. On refresh, recover only if both transfer status and readable local bytes are available; otherwise ask for reselection or restart.

## Failure cases and required proof
| Case | Required proof |
| --- | --- |
| Disconnect after partial acknowledgement | Same identity, correct offset, unchanged accepted bytes |
| Duplicate retry | No duplicate bytes or attachment record |
| Expired transfer | Explicit restart/reselect path; no false Resume promise |
| Cancel during reconnect | No queued request proceeds after cancellation |
| Workspace switch or access revoked | No cross-workspace association or content leak |
| Finalization response lost | Reconciliation finds one existing durable result |

## Dependencies and open work
SMART-13 defines accepted scope once actually reviewed; SMART-8 defines interaction; SMART-10 defines regression expectations. Existing local cleanup tests do not prove this protocol. A matching implementation diff, independent review, corrected findings, executed regression report and explicit release decision remain missing. The ticket was not started by writing this contract and no agent execution is asserted.
