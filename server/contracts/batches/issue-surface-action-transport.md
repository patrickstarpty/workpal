# Issue surface action transport audit

Status: incomplete bounded union; root review required. No full controller/data closure.

Status branches: identity includes wsId/query/status group; initialize each status with null head, rebase on identity/new statuses. Enabled false produces no targets. Heads retain settled nonerror placeholders, cleared on workspace change. Rows deduplicate IDs per status and reject mismatched exact status. Head fetching hides tails; revision/fetch effect trims chains to null head. loadMore appends only nonempty unseen next_cursor for matching identity. Retry refetches active nonexact tableRows prefix, covering cursor pages. Facets own totals; global loading/refresh tracks heads, not tails.

Group branches: infinite groups factory starts null cursor, limit100, next_cursor; retry false. Descriptors flatten secondary groups with visible-status filtering. No row observer until loadMore installs null head; later appends unseen cursor. Rows limit50 hierarchy false parent null; descriptor matching validates actor/project/parent/property/status or secondary category and deduplicates per branch. Head revisions trim tails. Retry uses active row prefix; retryGroups invokes refetch; loadMoreGroups checks hasNextPage and !isFetchingNextPage. Group first page total authoritative. Identity includes query/group but excludes wsId; placeholder map has no workspace clear in this body.

Controller 600-780 read without truncation: constructs scope (team throws), date/filter/negation/search/sort query, omits unresolved working/unread membership IDs, stabilizes by content; facets status/active submenu and include_total; facet automatic enabled !membershipUnresolved && (status surface || table/group with active facet). 829-885 wires status/group hooks with !statusFilterUnresolved && !membershipUnresolved; swimlane removes statuses and status negation and uses compound secondary exact status; empty property/swimlane branches observable.

Actions: update forwards caller success/error/settled with revision-conflict toast; returned actions.moveIssue delegates ordinary update, while separately returned moveIssue strips anchors into move_intent. Create opens modal only. batchUpdate forwards ids/updates/ops; delete awaits mutation. Arbitrary injected callbacks are outside concrete production union.

Update mutation sends PUT or POST move (strips optimistic position); synchronous cancellation and coordinator patch excludes control/description metadata. Failure restores coordinator/parent snapshots and invalidates loaded owner prefixes. Success reconciles authoritative non-property fields only against lower revisions, then revision reconciliation and stale-key invalidation. Settled refreshes derivatives/table, optional attachments/duplicates/old+new children/progress/batched children. Agent done reports star prompt.

Batch update awaits cancellation; first-wins snapshots per hash across list/flat/table/sidebar/detail/inbox/children. Failure rollback; partial updated count also rollback and owner refetch; labels/properties force owner refetch. Settled derivative/table/stale-key/parent invalidation. Batch API throws unsupported ops if confirmed count lacks results.

Batch delete snapshots/prunes list/my/flat and discovered parent children; failure restores. Full success forgets recent context, cleans scoped caches, prunes inbox; partial count restores and invalidates all issues/dependencies/inbox summary. Settled list/flat/table/assignee/Gantt/sidebar/projects/parent invalidation.

Inbox update rereads are owed if interrupted, failed or in flight, paid at terminal mutation-cache event only when no workspace issue-write remains pending. Inbox refresh cancels then invalidates. Full delete prunes inbox and selection and refreshes summary/archive pages/lookup/facets, plus all inbox on interruption. No direct prefetch in reviewed mutation/coordinator/delete/inbox updater bodies.

Remaining closure:

- Complete indirect observer API-ID/route union for every invalidated cache prefix remains unclosed; do not equate invalidation with unconditional HTTP.
- Coordinator output was truncated at part of 531-549; membership/cache-helper dependencies, ws revision helper and star prompt bodies remain unreviewed.
- Modal/i18n/recent-context/recent-issues/inbox selection concrete helper bodies remain unreviewed.
- Store/date/filter/selection controller/data edges outside bounded task remain open; no full controller/data closure.

Hashes, reviewed ranges and matched concrete inventory entries are recorded in the companion JSON. No runtime, network, Git, inventory or data changes.
