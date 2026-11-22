# Upload recovery interaction specification
Revision: 1. Prepared by Codex during the current evidence repair. Review requested; no previous design approval is asserted.

## Scope and dependency
Defines the interaction consumed by SMART-7. It does not claim that byte-offset resume exists. A server must establish whether a transfer can continue before the UI offers Resume; otherwise offer Retry upload, which restarts the transfer without promising preserved progress.

## State model
| State | Entry condition | Visible content | Permitted actions | Exit |
| --- | --- | --- | --- | --- |
| Uploading | Request accepted and progress available | Filename, determinate progress only when known, Cancel | Cancel | Complete, interrupted, authorization required, file unavailable |
| Interrupted | Retryable connection failure | Upload interrupted. Check your connection and try again. | Resume only with valid server capability; otherwise Retry upload; Cancel | Uploading after one explicit request or Cancelled |
| Authorization required | Server rejects authorization | Sign in to continue this upload. | Sign in; Cancel | Revalidate access and transfer identity before retry |
| File unavailable | Local bytes cannot be read | Select the file again to continue. | Choose file; Cancel | Validate new selection before any request |
| Cancelled | User cancels before completion | Upload cancelled | Remove; start a new upload | New transfer requires explicit action |
| Complete | Server confirms persisted attachment | Filename and open/download action | Open; remove association if authorized | No retry action |

## Transition rules
A network reconnect alone does not authorize repeated requests. Disable retry while a retry request is pending. Cancel invalidates the active request generation so late success or progress from it cannot restore an Uploading state. Authentication failure never enters an automatic retry loop. If the server cannot prove transfer identity, do not merge partial data or present the old progress as current.

## Reselection
Validate filename, size and the server's required content identity before reusing an upload. A matching filename alone is insufficient. If identity cannot be established, explain that a fresh upload is required. Do not overwrite an already accepted attachment silently.

## Keyboard and announcements
Tab order follows filename/context, recovery action, Cancel. Use native buttons; Enter and Space activate once. On failure keep focus in the upload area; do not steal focus from another field. After retry preserve focus on the same action or its stable container while disabled. Announce state changes politely once; throttle progress updates rather than announcing every chunk. Authorization and file selection dialogs return focus to their triggering control.

## Narrow layout
At 390px the filename may wrap and controls occupy a separate row. Progress and failure text must not obscure actions; actions remain reachable without hover or horizontal scrolling.

## Acceptance cases
Disconnect once and repeatedly; expire authorization before retry; cancel during reconnect; return from authentication without access; reselect different bytes with the same name; lose the file on refresh; receive late success after cancellation. For each case capture actual browser behavior and request count. Expected behavior is defined above; execution is not recorded by this specification.

## Handoff and open decisions
SMART-7 must identify the actual resume API and supported identity checks. SMART-10 owns the regression report. Until those exist the Resume option is conditional, and acceptance remains open. No release authority is delegated by this document.
