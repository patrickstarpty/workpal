# Empty inbox interaction and copy specification
Revision: 1. Prepared by Codex during evidence repair. Review requested; does not assert historical owner acceptance or implemented behavior.

## State selection
Only show an empty state after a successful response. Loading, request failure and permission denial are separate states and must not be rendered as an empty inbox.

| Condition | Heading | Supporting text | Action |
| --- | --- | --- | --- |
| Successful unfiltered result with zero messages | You're all caught up | New work will appear here. | None required |
| Successful filtered result with zero matches | No matching messages | Try changing your filters. | Clear filters |
| Loading | Loading messages… | Preserve existing results if revalidating | No empty-state action |
| Failed request | Unable to load messages | Try again. | Retry |

## Filter reset contract
Clear filters resets only the active inbox filters, not workspace, selected ticket or other saved views. Re-fetch or rederive the result using the same workspace. Announce the resulting count once after completion. Keep focus on a stable filter control after the clear action disappears; do not send focus to the document body. If results remain empty after reset, transition to the unfiltered empty state.

## Keyboard and semantics
Use a real button for Clear filters and Retry. Both are reachable using Tab and activate using Enter or Space. Heading order follows the inbox page heading. The empty illustration, if any, is decorative and has no duplicate accessible name. State updates use a polite status announcement without moving focus. Failure uses an appropriate error description linked to Retry.

## Layout
Use existing Workpal neutral surfaces and typography. At 390px, heading and guidance wrap within the content column, and the action remains below the message. No action is available only on hover; no horizontal overflow is introduced by long localized text.

## Verification and handoff
Verify empty data, filters hiding existing data, reset resulting in messages, reset still empty, failed fetch, background refresh and switching workspaces while loading. Record real rendered accessible names, focus after reset, Enter/Space behavior and narrow layout. Implementation and these measurements are not supplied by this design document. No owner has accepted this revision yet.
