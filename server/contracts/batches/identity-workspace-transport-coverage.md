# Identity/workspace transport source coverage

Bounded to every non-test source in the three named directories. Existing call mappings supply identities, not semantic proof. See the adjacent JSON for each source site, client declaration, existing call IDs and route identities.

## packages/core/auth/index.ts:1

Reexports store/utils; registration and Proxy forward injected Zustand store; no independent request.

## packages/core/auth/store.ts:1

sendCode, verifyCode, Google and token login follow API methods. cookieAuth suppresses token persistence for code/Google; token login always persists. Cookie logout alone sends logout (errors swallowed). Expiry clears credentials, skips duplicate teardown, clears workspace only in token mode. onLogin/onLogout/onSessionExpired are injected callbacks with unknown shell effects. identify/reset analytics use PostHog when initialized, otherwise identify buffers. StorageAdapter is injected, not inherently HTTP. setCurrentWorkspace queues subscriber and rehydrate callbacks on slug change; subscriber transports remain external dependencies.

## packages/core/auth/utils.ts:1

Pure relative redirect validation; returns text, does not navigate or fetch.

## packages/core/onboarding/index.ts:1

Reexports store, predicates, queries, bootstrap and constants; no independent transport.

## packages/core/onboarding/mika.ts:1

Pure system_key and session.last_message predicates; no provisioning occurs here.

## packages/core/onboarding/needs-backfill.ts:1

Pure user/dismiss-count predicate; handles legacy string source and array source; no request.

## packages/core/onboarding/queries.ts:1

listIssues asks done category, agent/squad assignees, limit 1; reads total. Key under issue prefix permits mutation/realtime refetch; stale 30s; consumer controls enabled.

## packages/core/onboarding/step-order.ts:1

Runtime array of persisted step names only.

## packages/core/onboarding/store.ts:1

Questionnaire PATCH then local setUser; conditional nonempty source/role/use-case sends PostHog person properties (buffered before initialization). Completion sends optional body iff completionPath or workspaceId truthy, then refreshMe -> getMe. Waitlist sends interest only; no completion or runtime provisioning.

## packages/core/onboarding/types.ts:1

Type declarations only; no executable runtime source.

## packages/core/onboarding/use-bootstrap-mika.ts:1

Sequential createMikaAgent with explicit workspaceSlug -> require onboarding_session or throw -> startMikaOnboarding same slug. No fabricated session or runtime response. Success invalidates agent list, chat sessions, messages and paginated messages. Runtime-backed execution/provisioning unsupported for this audit; existing parse fallback started:false is not evidence of execution.

## packages/core/workspace/avatar-url.ts:1

Pure resource URL resolver: absent -> null; non-slash unchanged; slash prefixed with trimmed API base. getBaseUrl local accessor. Returned dynamic avatar URL may later cause browser image fetch; no authenticated API request or fixed route can be inferred.

## packages/core/workspace/hooks.ts:1

useWorkspaceList enabled option gates list query and exposes refetch. useActorName subscribes member/agent/squad queries plus plugin installations only when feature flag and nonempty workspace. Names/initials/hasActor are local projections; member/agent/squad avatars use resource resolver. Feature flag reads config state; no direct config request here.

## packages/core/workspace/index.ts:1

Reexports queries/mutations/hooks; no independent transport.

## packages/core/workspace/mutations.ts:1

Create seeds list on success; failure invalidates list. Leave/delete invalidate list on settled; success forgets local search index; delete clears slug storage only after success, pending mark removed on error. MCP create invalidates library; update/delete invalidate library plus agents prefix; assignment writes invalidate agent MCP key. Pin cancels list queries, optimistic local sort, restores on error, invalidates settled. Invalidations can refetch active matching observers; they are not unconditional sends.

## packages/core/workspace/pending-delete.ts:1

Per-tab Set suppresses self-delete realtime echo; no websocket connection or send.

## packages/core/workspace/queries.ts:1

Query factories only execute through consumers. Slug lookup shares list request. Agent list polls 30s only for unarchived online/unstable agents. Agent detail requires workspace+agent, retry false. Squads/involved require workspace; status requires workspace+squad and focus refetch, stale30s. Skill detail/versions require skill; version detail also non-null version and infinite stale. Invitations focus refetch stale30s. Share links enabled argument AND workspace. MCP list requires nonempty workspace; assignment list requires agent. cacheAgentResponse and selectSkillAssignments are local folds/writes.

## packages/core/workspace/sort-workspaces.ts:1

Pure copy/sort by pin time then creation; no I/O.

## packages/core/workspace/workspace-url.ts:1

Pure display host parsing with brand fallback; new URL parses text only; config mentioned in comments is not fetched here.

## Remaining closure

- Injected AuthStoreOptions storage and shell callbacks are arbitrary implementations; no exhaustive shell audit claimed.
- Workspace slug subscribers/rehydration callbacks can reconnect external WS providers; registration closure outside scope.
- PostHog configured host and SDK delivery are external, not authenticated backend routes.
- Dynamic avatar values and eventual browser resource consumers do not have fixed route identities.
- Search-index forget worker/IndexedDB implementation and broad agents/chat/issue invalidation observer closure require further callee evidence.
- Runtime provisioning and kickoff support not exercised or proven by route mapping.

## Parent follow-up reconciliation

For the active Web entry, the callback and WS registration gaps above are closed by active-web-auth-transport.json; search-index cleanup and concrete fallback/sync transports are closed by search-index-transport-coverage.json. These supersede the corresponding unresolved items for this entry only. Runtime observer execution, dynamic asset values and backend feature support remain distinct from static endpoint enumeration; no global source coverage claim follows.
