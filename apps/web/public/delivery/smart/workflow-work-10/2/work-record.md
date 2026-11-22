# SMART-10 — Review upload retry regression coverage

Revision: 2

## Regression matrix
| Case | Setup / action | Expected outcome | Review state |
| --- | --- | --- | --- |
| Reconnect | Interrupt an upload after a partial acknowledgement, then reconnect | Resume the same upload identity; do not duplicate acknowledged data | Awaiting owner review |
| Repeated interruption | Disconnect again during a resumed transfer | Preserve progress and offer another retry | Awaiting owner review |
| Authorization expiry | Expire authorization before retry | Request authorization; do not loop automatic retries | Awaiting owner review |
| Cancel during reconnect | Cancel while a reconnect is pending | Stop retry scheduling and preserve an explicit cancelled state | Added in v2; awaiting owner review |

## Review response
Added the missing cancel-during-reconnect boundary with a distinct expected outcome. This matrix specifies acceptance behavior; it is not a measured execution report.

## Decision / remaining gate
Owner should review the regression matrix. Do not treat this review as permission to deploy SMART-17.
