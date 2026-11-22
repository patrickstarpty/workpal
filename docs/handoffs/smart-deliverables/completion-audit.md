# SMART Activity deliverables — final audit

## What was delivered
All 21 SMART tickets now carry concrete materials in the Activity that submitted them: 23 immutable documents plus four source-snapshot attachments. Requirements/designs are full specifications; verification reports contain actual commands/results and uncovered scope; development reviews contain inspected comparisons and explicit missing historical basis; handoffs reference exact document revisions. Historical comments link to the later evidence Activity without falsely claiming it was produced by the original Run.

This completes the requested evidence repair and inspection path. It does **not** complete the underlying upload feature, establish historical owner approval, or certify external integrations. Where source evidence does not exist, the document identifies what is missing instead of inventing a diff, review, test result or acceptance.

## Requirement checks
| Requirement | Actual evidence |
| --- | --- |
| Every SMART ticket inspectable | `browser-verification.json`: all 21 tickets, 23 document previews opened from producing Activity |
| Full requirements and design | SMART-1/2/3/8/13/14 published specifications; content hashes checked against stored attachment text |
| Development/change/review | SMART-9 actual working-tree diff and source; SMART-7/15 exact comparisons and claim-specific findings, explicitly no recovered original fix/review/acceptance |
| Test method/results/failures/uncovered | SMART-4/7/10/15 reports: 15 upload tests, 22 title/draft tests; SMART-9 one boundary test; source snapshots and original output included |
| External storage | SMART-16 complete protocol and explicit NOT RUN result; no passing result invented |
| Handoff exact versions | SMART-5/11/17 each reference five existing immutable input revisions; all input records resolved |
| Reviewer/acceptance honesty | Actual preparer named Codex; no owner decision forged; documents state review outstanding or specific missing original approval |
| Activity/Run/ticket association | Original source-task IDs retained; reports identify the historical claims being inspected; no invented producing model Run for this local audit |
| Historical traceability | Browser clicked historical-comment links to all 23 later material Activities |
| Preservation | `preservation.txt`: 347 original historical records unchanged byte-for-byte |
| Narrow screen | Browser check at 390px verifies sidebar evidence entry |

## Implementation verification
- Evidence/workspace-content regression: 36 passed before final link bridge adjustment; evidence suite then 7 passed.
- Local link navigation: 2 tests passed, including exact Activity fragment and modified-click navigation.
- Browser: all 23 Activity attachment previews and historical links passed, covering 21 tickets.
- `npm run check`: 1 failed, 1937 passed, 30 subtests passed. Failure: `test_realtime_consumer.py::test_authorized_delivery_and_failed_fanout[context2]` expected dispatch 1, got 0. No realtime code changed by this task.
- Realtime test file alone: 6 passed. This does not erase the full-suite failure.
- Final `npm run build`: passed. `git diff --check`: passed.

## Access
Open SMART ticket → Activity. The new document card opens its full contents. Historical authored comments contain **Later evidence review** links to the relevant new Activity. Delivery evidence in the sidebar provides all revisions and expanded handoff inputs. Original Runs retain their original provenance; new audit documents do not impersonate them.
