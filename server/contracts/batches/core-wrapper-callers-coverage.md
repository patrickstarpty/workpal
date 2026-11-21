# Core wrapper callers coverage

Root review pending. Bounded current-source static review only; no global or backend claim. Hashes identify current reviewed bytes, not historical identity. API transport proof reused from api-client-section-reconciliation.json; candidate references reused with concrete branch narrowing.

## packages/core/billing/workspace-subscription-queries.ts

Workspace summary/prices options are enabled only for nonempty wsId; keys include workspace. Summary stale 30s, focus refetch. Prices truthy data stale 10min, null/undefined zero; focus refetch and retry false. No billing implementation inferred.

## packages/core/projects/access.ts

Access helpers: missing user denies; owner/admin allowed; otherwise private managerId or nullish member-lead fallback must match. Nonprivate lead changes allowed. Manager query uses injected projectMembersOptions with enabled private+user+known nonprivileged role, returns manager_id or null. No recursive query review. Mutation always network mode, retry false; offline throws before mutually exclusive visibility/update, add singleton, remove branches. onSettled awaits project invalidation then issue invalidation even on mutation failure; first invalidation rejection prevents second. No optimistic update or permission gate inside mutation.

## packages/core/whats-new/index.ts

Version helpers parse numeric prefix, sort/filter releases by server cap; unknown cap unrestricted. Unread requires user and defined marker; parsed seen compares version, else release date strictly after creation day. mark seen no user returns; optimistic marker only on current requester account. Await API, apply response only matching id. Failure rolls back only if current marker still requested version, with account guard, then rethrows. No cache invalidation or cancellation.

## packages/core/star-prompt/index.ts

Due predicate requires recorded count, unstarred, count<2, finite creation >=3 days and finite previous showing >=30 days. This predicate and done threshold 3 are not enforced by claim function. Moment store reports/clears locally. Done query workspace+agent key, stale zero, limit 1 done category agent filter, returns total; no enabled gate. No ids or created_by_user_id means GET only; POST and compatibility recursion unreachable here. claim without user false; awaited response updates only matching current/requester id, success true even if account changed; any failure false. Starred without user returns; optimistic timestamp then awaited response with same identity guards; rejection propagates with no rollback.

## packages/views/agents/create/use-builder-draft-sync.ts

Injected stored/storedSettled/runtimeId/draft/setDraft interface, no fetch of stored here. Restore once when session present, not restored, settled; stored seeds markers/saved ref and converts with server runtime; sets restored even absent stored. Autosave only session+restored, converts draft and markers, skips equality to saved. Pending ref and 800ms timer; cleanup clears timer only, no request abort. Save eagerly records saved and clears pending, fires PUT; catch clears saved for next edit, no immediate retry/error UI. Latest callback ref used by unmount cleanup to flush pending. Restore state/refs are not reset on sessionId change within same mounted hook; teardown assumptions belong to caller. No serialization or stale-response guard on overlapping failures.

Validation: JSON parsed, five source hashes matched, reused client hash matched, exact existing inventory tuples preserved. No runtime, tests, network, models, data, git, children, shared inventory or ledger edits.

## Root acceptance

Corrected projectMembersOptions to concrete client:4561 GET. Read supporting query module and recorded five possible project-prefix query endpoints. Root checked original hashes/tuples and independently reviewed mutation/gate semantics. Accepted five targets plus supporting query source; no runtime/backend claim.
