# Status helper transport audit

Static audit only. Global coverage remains false. The JSON records current SHA-256 hashes and export anchors for all five fully read target files. Closed means the bounded helper chain described there, not global transport coverage or backend implementation.

## Concrete chains

- Catalog: `issue-statuses/hooks.ts:12` → `issue-statuses/queries.ts:28` → `api/client.ts:4819`, GET `/api/issue-statuses?include_archived=true`, inventory `client:4821`.
- Workflow: `issue-workflows/hooks.ts:12,24` → `issue-workflows/queries.ts:40` → `api/client.ts:4691`, GET `/api/issue-workflows`, `client:4692`. Enabled for nonempty workspace even without a project. Project observer uses `projects/queries.ts:21` → `api/client.ts:4513`, GET `/api/projects?include_archived=true`, `client:4517`; enabled only for nonempty workspace and project.
- Canonical and read-state: `issues/queries.ts:507` → `api/client.ts:1611`, GET `/api/issues/${encodeURIComponent(id)}`, `client:1612`. Inventory route is `/api/issues/{id}` and remains pending-reconciliation; source comments use `:id`. Malformed parsed issue throws. `issues/read-state.ts` was fully read. Its other production caller is `views/issues/components/issue-detail.tsx:1734-1748`, whose existing detail observer uses conditional refetchOnMount and list-cache initialData. Manual retry reuses that observer; it does not create another endpoint.

## Precise remaining callback closure

`filter-dependency.ts` is locally closed but production transport closure remains partial. Identified production consumers are `views/issues/surface/use-issue-surface-controller.ts` and `use-issue-surface-data.ts`; tests are excluded. Bounded caller windows read: controller 465–490 and 525–595; data 170–235. These show catalog retry, project query retry, workspaceWorkingAgentsOptions (running filter or Gantt), agentTaskSnapshotOptions (idle filter), useIssueUnreadIds (unread filter), and injected relationSources. They do not establish complete transport closure for those factories/hooks or relationSources construction. Required follow-up: read their complete small bodies, trace relationSources construction (agents/squads/subscriptions), inspect concrete client methods, map inventory IDs/routes, and audit downstream dependency.retry composition and query gating. Controller composition at 1082 was located but not read in context. Do not promote this file to closed transport coverage.

Generic retry contracts are recorded exactly in JSON. No arbitrary injected refetch is classified as HTTP solely because its name is refetch. No runtime request count, successful backend behavior, or cache invalidation is inferred from helper comments. Pure status-category helpers do not themselves transport; their downstream production cache effects are outside the bounded local closure.

## Evidence and validation

All five targets were read in one bounded, untruncated output. Catalog hooks/queries, workflow hooks/queries and read-state were read fully in a second bounded output. Query/client bodies were read in bounded windows. Shared ApiClient.fetch was not re-audited. Inventory IDs, normalized routes, existing source references and target hashes were checked locally. No tests or runtime were run. Only the three owned new artifacts were written.
