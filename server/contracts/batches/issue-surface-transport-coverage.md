# Issue surface static transport audit

Disposition: precise partial; root review required. No backend support claim.

Three target hashes and line anchors are recorded in the companion JSON. Repository wrapper transport is closed through the Gantt factory; controller and data remain partial because imported production adapters are not all traced.

- controller:293: propertyListOptions(wsId); active catalog select; no explicit enabled override
- controller:321; data:437,442; workflow-columns:29; issue-workflows/hooks:10-54: useColumnWorkflow always invokes workflow and project hooks even when hasStatusFilter returns null. Workflow enabled Boolean(wsId); project list enabled Boolean(wsId)&&Boolean(projectId). Same project ID reused from retry artifact.
- controller:756,802: Facet submenu/status request enabled !membershipUnresolved && (status surface || ((table || grouped) && active facet)); separate working_agents facet enabled !usesGantt && scope.type!==actor, without dependency gate. keepPreviousData.
- controller:1024: export invokes rows directly, ungrouped hierarchy disabled, limit100 cursor loop; rejects repeated cursors, missing/changed fingerprint, group/parent mismatch, duplicate issue IDs and final total mismatch. No query-cache write.
- repository:11-20; data:187; issues/queries:418-469: repository forwards ws/project and plan.queryFilter.assignee_types. Gantt enabled usesGantt overriding factory; scheduled=true listIssues offset loop bounded 10000; empty, short or total reached stops.
- data:384-426; issues/queries:556-569: child progress observer unconditional; select builds parent->done/total Map. Export Promise.all manually refetches requested projects/progress even if automatic projects query disabled; propagates errors and missing data.

Reuses the eight IDs and bounded retry closure in retry-callback-transport-coverage.json; this does not close other callers.

Remaining work:

- controller:829,873 useIssueStatusBranches/useIssueGroupBranches: Read entire branch helper bodies, retry/load-more/cursor state effects and all imported application helper bodies; no branch closure claimed.
- controller:1071; use-issue-surface-actions:45-154 useIssueSurfaceActions: Trace production useUpdateIssue/useBatchUpdateIssues/useBatchDeleteIssues mutation bodies, optimistic cache rollback/invalidation, prefetch and concrete adapters. Also translation hooks and modal store body.
- controller:245-292,384-390,967 workspace/auth/view/selection stores and pure app helpers: Trace concrete store adapters including persistence and selection reset; imported date/filter/query-plan/activity/status helpers have not all been body-read. Controller 381-780 aggregate output truncated; targeted 380-600 reread, 600-780 still needs bounded reread.

Local effects:

- controller:193 debounce schedules/clears window timer; React state for table search/facet; refs retain unread IDs until filter off
- controller:384-390 corrects view mode via injected store action; persistence implementation remains open
- data derives arrays/Sets/Maps; useQuery cache managed by standard TanStack contract; no direct storage write in target bodies
- selection membership key excludes sort and running set; concrete selection helper effects remain open
- No direct prefetch call observed in three targets; indirect mutation prefetch union remains unresolved

Validation: JSON parses, IDs/routes copied from current inventory, hashes computed from local bytes. No runtime or application checks run for these documentation-only artifacts.
