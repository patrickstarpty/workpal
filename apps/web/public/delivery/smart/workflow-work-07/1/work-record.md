# SMART-7 — Deliver upload interruption recovery

Revision: 1

## Input
Uploads can be interrupted after the server has accepted part of the file.

## Proposed work
Keep one upload identity across retries. Preserve the user’s selected file and show a resumable interruption state.

## Acceptance
Accept the recovery interaction, implementation, regression checks and release decision.
