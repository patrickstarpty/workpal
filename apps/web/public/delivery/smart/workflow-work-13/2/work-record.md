# SMART-13 — Agree attachment recovery scope

Revision: 2

## Accepted scope
- Resume retryable network interruptions using the existing upload identity.
- Preserve acknowledged progress and the selected local file while available.
- Show authorization expiry separately from a retryable interruption.
- Require file reselection when the local file is no longer available.

## Exclusions
No guarantee of recovery after loss of the local file; no silent overwrite of an accepted upload; no automatic production release.

## Acceptance boundaries
A retry does not duplicate acknowledged content. Cancelling prevents later retries. Authorization errors request user action.

## Review response
Authentication and unavailable-file handling are explicit scope boundaries. The owner accepts this planning outcome; delivery work remains independently tracked.

## Decision / remaining gate
Scope accepted. The downstream delivery ticket can reference this decision without requiring a new planning ticket.
