# Issue surface/controller closure evidence

Root review pending. Both target bodies are completely recorded in separate <=100-line snapshots. This is a static evidence artifact, not a claim of complete transitive application-helper closure.

## Executed hooks and transport

- issue-surface.tsx:113 -> useActiveIssueView -> issueViewListOptions: workspace/my/project scope and nonempty wsId; explicit-store variant bypasses this hook Tuples: client:5096.
- issue-surface.tsx:247 -> workspaceWakeupSummariesOptions: nonempty workspaceId; staleTime 10000; surface refetchInterval 10000; malformed payload throws Tuples: client:1547.
- controller:293: property catalog factory; no caller enabled override Tuples: client:4884.
- controller:316; data:437,442 -> useColumnWorkflow: workflow enabled Boolean(wsId); projects Boolean(wsId)&&Boolean(projectId); both hooks execute before hasStatusFilter early return Tuples: client:4692, client:4517.
- controller:340-354: agents and involved squads only usesMyAgents; subscribed ids only usesSubscribed; scope my removes stored relation filters Tuples: client:2066, client:5210, client:3178.
- controller:551-563: working projection usesGantt||agentRunningFilter; task snapshot agentIdleFilter; my all becomes any Tuples: client:3071, client:3046.
- controller:586 -> useIssueUnreadIds: unreadFilter && !!wsId; only expose error when not fetching and data undefined Tuples: client:3167.
- controller:764,795: membership resolved AND (status surface OR ((table OR grouped) AND active facet)); independent working_agents facet !usesGantt && scope.type!=actor, drops working/idle filters, include_total false; no membership/status gate on independent facet Tuples: client:1430.
- controller:829,873: status/group mode && !statusFilterUnresolved && !membershipUnresolved; status pages vs compound/project/property/assignee group pages; accepted bounded action evidence for cursor/loadMore/retry Tuples: client:1402, client:1416.
- controller:947 -> data: scheduled Gantt only usesGantt; project catalog loadProjects; child progress observer unconditional; workflow observers also execute Tuples: client:1344, client:4517, client:1817.
- controller:1021-1068: callback invocation only; ungrouped, hierarchy false,parent null,limit100; cursor loop rejects repeated cursor, empty/changed fingerprint, nonnull group/parent,duplicate IDs,final count mismatch; no cache write Tuples: client:1416.
- data:390-426 resolveTableExportLookups: Promise.all only requested lookup flags; manual project refetch works despite automatic disabled; throw query error or missing requested data Tuples: client:4517, client:1817.
- useUpdateIssue: Only invoked through useIssueSurfaceActions callbacks, never automatic mutation on render Tuples: client:1771, client:1778.
- useBatchUpdateIssues: Only invoked through useIssueSurfaceActions callbacks, never automatic mutation on render Tuples: client:1835.
- useBatchDeleteIssues: Only invoked through useIssueSurfaceActions callbacks, never automatic mutation on render Tuples: client:1852.
- surface actions -> update/batchUpdate/batchDelete -> accepted mutation/cache/revision invalidations: Superset inherited from accepted bounded helper audits, including unrelated factories under broad prefixes. Not guaranteed HTTP, not exact mounted observers, not arbitrary supplied query keys. No mutation endpoints are inferred from nearby client methods. Tuples: client:1344, client:1402, client:1416, client:1430, client:1612, client:1680, client:1785, client:1795, client:1806, client:1817, client:1861, client:1890, client:1926, client:1935, client:2002, client:2066, client:2070, client:3028, client:3046, client:3079, client:3087, client:3095, client:3116, client:3129, client:3167, client:3178, client:3196, client:3232, client:3241, client:3255, client:3278, client:3391, client:3425, client:3441, client:3493, client:3765, client:3796, client:3806, client:3836, client:3876, client:3891, client:3967, client:3977, client:4427, client:4517, client:4524, client:4561, client:4569, client:4602, client:4692, client:4821, client:4917, client:5025, client:5180, client:5203, client:5210, client:5264, client:5536.

## Callback and local effects

- Surface key selects view:<id> or caller/scope key; first saved-view seed only absent local registry entry. Store memo depends resolvedSurfaceKey. wsId/scope/view content key remounts data window; explicit store remount uses wsId.
- keepFixedFilters patches running=true/idle=false and exact baseline relations, removes relation negation only if baseline relations nonempty; subscribe reapplies missing baseline. setState only when patch nonempty.
- Surface stores are module Map entries; registry subscription persists partialized state with updatedAt through workspace-aware defaultStorage into localStorage workpal_issue_surface_views:<slug>. No slug means reads null and writes dropped. Rehydration resets cached stores under suppression then releases in finally. Active-view map is not persisted.
- Controller subscribes view/auth/workspace inputs; disallowed view mode effect writes fallbackMode and normalizes grouping sort via store action. Search timer trims after250ms and clears on change/unmount; table search is local. Date endpoints reorder and end advances one day; invalid endpoints omit interval.
- Property catalog settled removes inactive/empty flat filters, prunes inactive advanced property conditions and fixed project/my relation conditions; invalid property sort becomes position and invalid select grouping becomes status. No direct persistence of derived pruning.
- Unread ref accumulates IDs while enabled, retains read IDs, resets off. Working IDs deduplicate; idle snapshot derives active IDs. Membership key excludes sort and changing live running IDs. Surface selection resets synchronously on resetKey change; toggle/select/deselect/clear clone Sets; no global selection write from this hook.
- Facet callback accepts facet only server-facet modes; effect clears otherwise. Requested facets deduplicate status/property identity; total requested only status surfaces. Query spec pinned by hashKey content.
- Loaded table issue callback preserves array identity if item references equal; leaving table clears it. Client filters affect displayed issue arrays; batch toolbar uses loaded table rows in table mode. No network inferred from arbitrary rendered children.
- Filter dependency considers only sources with data undefined; errors with cached data do not block. Retry only failed unresolved sources; combine retries failed states. Reporting precedence status+project, working, unread, relation. Rendering precedence dependency error, loading, empty/client empty, content.
- Filtered-empty clear invokes clearFilters or resetFiltersTo(baseline.raw) plus setDateFilter(null); baseline equality hides clear. clearFilters resets filter arrays/booleans/tree/date but not search/display toggles. Create and add-existing only write modal/data state; modal contents excluded.
- actions.moveIssue delegates updateIssue; controller.moveIssue instead strips before/after anchors into move_intent. Update callback forwards success/error/settled; revision-conflict-specific toast. Batch update forwards ops; delete awaits mutateAsync. Caller callbacks excluded.
- Accepted update/batch mutation evidence: cancel/snapshot/optimistic coordinator patches; failure rollback and owner invalidation; authoritative revision reconciliation; settle derivative/table/parent refresh. Batch partial counts rollback/refetch; delete full success cleanup/recent/inbox pruning vs partial restore. Cache writes/invalidation are conditional, never unconditional requests.

## Remaining boundaries

- Pure application helpers filter-tree/definition/builtin baseline/date/activity and applyIssueFilters are not independently whole-source audited in this artifact. Their exact predicate semantics remain outside the claimed helper closure.
- view-store sanitizer/partialize/normalizeSortForGrouping and auth/workspace/i18n adapters not whole-source audited; storage path and directly invoked setters reviewed, no global adapter closure claimed.
- Arbitrary rendered descendants (including modal bodies, toolbar, table internals, peek/menu providers) and caller-injected render/filter/mutation callbacks.
- Third-party React/Zustand/TanStack internals, concrete runtime observer set, global retry defaults, server behavior/backend support and actual requests.
- Arbitrary caller-supplied cache prefixes and stale keys beyond accepted finite conservative union.

All reused source hashes and exact inventory tuples were compared with current local bytes. Files marked whole_source describe source reads, not transitive closure. No runtime, tests, network, model, data or Git operations; only the three owned documents were created.

Root partial review corrected three swapped query mappings by reading the actual factories and controller gates; also added omitted status catalog GET client:4821. Tuple self-consistency alone did not establish the original source-to-request mapping. Helper closure remains pending; no ledger promotion.

Root attached accepted surface-local-helper-closure proof and added GET workspace list from invoked identity hook. Earlier pure/helper gaps are superseded by exact function effect and adapter review. Both bounded target bodies accepted with explicit descendant/provider/runtime exclusions; no backend completion claim.
