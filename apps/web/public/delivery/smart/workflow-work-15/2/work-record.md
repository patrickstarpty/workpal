# SMART-15 — Deliver accessible ticket titles

Revision: 2

## Accepted title behavior
- Reading state exposes one accessible ticket title.
- Editing state has a labelled text input and explicit save/cancel actions.
- Save retains the new title and returns focus to the title control.
- Cancel retains the previous title and returns focus to the same control.
- Narrow layouts wrap titles without clipping the edit action.

## Review checklist
Check reading and editing names separately; check focus after save and cancel; verify wrapped text leaves controls reachable.

## Review response
Removed the proposed duplicate reading label and separated the input label from the displayed title. The owner acceptance concerns this scoped delivery record; no production deployment or measured test result is asserted.

## Decision / remaining gate
The scoped delivery is accepted. Keep the phase decisions and reviewed handoff on this same ticket.
