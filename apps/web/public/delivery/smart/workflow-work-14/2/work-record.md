# SMART-14 — Design empty inbox guidance

Revision: 2

## Accepted empty states
| Condition | Heading | Guidance | Action |
| --- | --- | --- | --- |
| Inbox has no messages | You're all caught up | New work will appear here. | No mandatory action |
| Filters exclude every message | No matching messages | Try changing your filters. | Clear filters |

## Keyboard behavior
Clear filters is reachable by Tab and activated by Enter or Space. Reset keeps focus on the filter control and announces the updated results. Empty states do not steal focus.

## Review response
Separated an empty inbox from an empty filtered result and defined a keyboard-operable reset. Design scope accepted; implementation is not implied.

## Decision / remaining gate
Design accepted. Close the design scope; implementation can start independently with this artifact.
