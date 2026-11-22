# ApiClient core wrappers

Bounded static review of client.ts lines 1146–2056. No runtime, backend or whole-client claim. Shared execution reuses the accepted execution closure.

| Declaration | Lines | Requests |
|---|---|---|
| sendCode (implementation) | 1146–1151 | client:1147 |
| verifyCode (implementation) | 1153–1158 | client:1154 |
| googleLogin (implementation) | 1160–1165 | client:1161 |
| logout (implementation) | 1167–1169 | client:1168 |
| issueCliToken (implementation) | 1171–1173 | client:1172 |
| refreshSession (implementation) | 1184–1194 | client:1185 |
| getMe (implementation) | 1196–1201 | client:1197 |
| markOnboardingComplete (implementation) | 1203–1214 | client:1207 |
| joinCloudWaitlist (implementation) | 1216–1227 | client:1220 |
| patchOnboarding (implementation) | 1229–1239 | client:1232 |
| markWhatsNewSeen (implementation) | 1241–1249 | client:1242 |
| claimStarPromptShowing (implementation) | 1252–1257 | client:1253 |
| markStarPromptStarred (implementation) | 1259–1264 | client:1260 |
| updateMe (implementation) | 1266–1274 | client:1267 |
| listIssues (implementation) | 1277–1353 | client:1329; client:1344 |
| listGroupedIssues (implementation) | 1355–1399 | client:1392 |
| listIssueTableGroups (implementation) | 1401–1413 | client:1402 |
| listIssueTableRows (implementation) | 1415–1427 | client:1416 |
| listIssueTableFacets (implementation) | 1429–1441 | client:1430 |
| searchIssues (implementation) | 1443–1455 | client:1448 |
| searchProjects (implementation) | 1457–1470 | client:1463 |
| getSearchIndexManifest (implementation) | 1476–1482 | client:1477 |
| getSearchIndexSnapshot (implementation) | 1484–1497 | client:1492 |
| getSearchIndexChanges (implementation) | 1499–1512 | client:1505 |
| listWorkspaceWakeups (implementation) | 1531–1537 | client:1533 |
| listIssueWakeups (implementation) | 1539–1544 | client:1540 |
| listIssueWakeupSummaries (implementation) | 1546–1551 | client:1547 |
| enableIssueWakeup (implementation) | 1553–1555 | client:1554 |
| editIssueWakeupInstruction (implementation) | 1557–1559 | client:1558 |
| createIssueWakeup (implementation) | 1561–1563 | client:1562 |
| listIssueSystemWakeups (implementation) | 1565–1570 | client:1566 |
| listIssueWakeupRuns (implementation) | 1572–1577 | client:1573 |
| listPausedWakeups (implementation) | 1579–1582 | client:1580 |
| triggerIssueWakeup (implementation) | 1584–1586 | client:1585 |
| deleteIssueWakeup (implementation) | 1588–1590 | client:1589 |
| updateIssueSystemWakeup (implementation) | 1592–1594 | client:1593 |
| listWorkspaceSystemWakeups (implementation) | 1596–1601 | client:1597 |
| updateWorkspaceSystemWakeup (implementation) | 1603–1605 | client:1604 |
| disableIssueWakeup (implementation) | 1607–1609 | client:1608 |
| getIssue (implementation) | 1611–1624 | client:1612 |
| createIssue (implementation) | 1626–1661 | client:1648 |
| quickCreateIssue (implementation) | 1663–1677 | client:1673 |
| getCommentSubIssuePreview (implementation) | 1679–1689 | client:1680 |
| createCommentSubIssue (overload signature) | 1691–1694 | none |
| createCommentSubIssue (overload signature) | 1695–1698 | none |
| createCommentSubIssue (implementation) | 1699–1745 | client:1714 |
| createFeedback (implementation) | 1747–1761 | client:1754 |
| upsertClientUsage (implementation) | 1763–1768 | client:1764 |
| updateIssue (implementation) | 1770–1775 | client:1771 |
| moveIssue (implementation) | 1777–1782 | client:1778 |
| listIssueDuplicates (implementation) | 1784–1792 | client:1785 |
| listChildIssues (implementation) | 1794–1799 | client:1795 |
| listChildrenByParents (implementation) | 1805–1812 | client:1806 |
| getChildIssueProgress (implementation) | 1814–1824 | client:1817 |
| deleteIssue (implementation) | 1826–1828 | client:1827 |
| batchUpdateIssues (implementation) | 1830–1849 | client:1835 |
| batchDeleteIssues (implementation) | 1851–1856 | client:1852 |
| listComments (implementation) | 1859–1865 | client:1861 |
| createComment (implementation) | 1867–1887 | client:1876 |
| previewCommentTriggers (implementation) | 1889–1902 | client:1890 |
| previewIssueTrigger (implementation) | 1908–1923 | client:1909 |
| listTimeline (implementation) | 1925–1932 | client:1926 |
| getAssigneeFrequency (implementation) | 1934–1936 | client:1935 |
| updateComment (implementation) | 1938–1949 | client:1939 |
| deleteComment (implementation) | 1957–1962 | client:1961, client:1961:keep-replies |
| resolveComment (implementation) | 1964–1966 | client:1965 |
| unresolveComment (implementation) | 1968–1970 | client:1969 |
| addReaction (implementation) | 1972–1977 | client:1973 |
| removeReaction (implementation) | 1979–1984 | client:1980 |
| addIssueReaction (implementation) | 1986–1991 | client:1987 |
| removeIssueReaction (implementation) | 1993–1998 | client:1994 |
| listIssueSubscribers (implementation) | 2001–2006 | client:2002 |
| subscribeToIssue (implementation) | 2008–2016 | client:2012 |
| unsubscribeFromIssue (implementation) | 2018–2027 | client:2023 |
| unsubscribeFromIssueSubtree (implementation) | 2041–2050 | client:2046 |

Exact source bodies, local builders, conditional branches, parsing/assertions, this-method calls and endpoint tuples are recorded in the JSON. Snapshots are separate from reviewed source files.

Missing transport mappings: none.

Helper gaps:
- getConfig is outside this bounded range; capability request closure must be supplied by its own wrapper proof.
- requestedIssueCreateProperties, assertIssueCreatePropertiesSnapshot, workspaceHeader, subscriberTarget, parseSearchIndexResponse and schema/fallback definitions are outside this range; exact call expressions and supplied values are recorded, not independently whole-helper reviewed here.
