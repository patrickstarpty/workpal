# Dashboard surface transport closure

Static source audit only. Root review required; no measured outputs or runtime support asserted.

Six rollups enabled iff wsId; 60s stale, 300s polling; previous data only if keys match except days index 3. All six mounted independent of tab.

chartFetchDays=max(1,ceil(days/7))*7; daily rows trimmed to viewer calendar cutoff; per-agent uses selected days. Invalid or all-project selection becomes null.

Project list includes archived; no status input. Agent list includes archived and workspace_id iff truthy; polling 30s only for unarchived online/unstable agents. Neither list factory adds enabled guard.

Tab URL errors/contribution accepted, others usage; replace URL locally. Refresh invalidates dashboard/wsId prefix including contribution, spinner/freshness only six rollups.

Usage loading OR four usage queries; empty iff all four arrays empty after loading. Errors loading OR two failure queries. Failed rollups default empty arrays; no dedicated page error branch.

Contribution pending skeleton; error Retry refetch; success rows/nonrows; zero totals safe percentages; calendar focus/click only status; ticket navigation encoded locally.

Import no file returns; >900000 bytes throws; file.text then JSON.parse locally; PUT JSON commits; count schema parse; await contribution prefix invalidation; error status; finally importing false; input reset. No download/export handler in targets.

Leaderboard tokens/cost/time/tasks stable descending sort; show first ten or all; toggle only >10; empty branch; synthetic deleted/restricted no ActorAvatar; deleted time/tasks dash; real row name fallback UUID. Unavailable totals dash; incomplete prefix ≥; coverage pending/unreported branches local.

Local aggregation/pricing/date/format/schema parse is not transport; schema-data closure reused.

React Query scheduling/cache invalidation is library boundary; does not introduce new route.

Native File.text and browser file picker parse text only; no installation/execution. Navigation push/replace are platform adapter boundaries.

Leaderboard agent hover closure (bounded supporting slices)

leaderboard.tsx:269–274 passes agent type/id and enableHoverCard, with no showStatusDot, avatar override or live variant. actor-avatar.tsx:87–181 defaults profileRequiresDirectoryEntry=false and hoverCardVariant=profile; therefore real rows reach AgentAvatarHoverCard:278–300 and AgentProfileCard, never live peek, member or squad hover payloads. Synthetic rows bypass this wrapper. Shell:343–385 supplies content to the local HoverCard adapter; ui/components/ui/hover-card.tsx delegates mounting/open behavior to Base UI PreviewCard (library boundary), without a custom fetch callback.

useActorName (workspace/hooks.ts:94–220) registers members and agents without enabled guards, squads with !!wsId, and plugin installations only when pluginsEnabled && wsId.length>0. These queries run even for agent-only name/avatar lookup; passing a name would not remove them. Agent URL comes from matching directory agent.avatar_url. Profile card:31–174 registers agent/member/runtime lists before loading/missing-agent returns; runtime list has no enabled guard. Existing nonarchived agent mounts AgentAvailabilityLine:156–177 -> useAgentPresenceDetail:119–179: agents, runtimes and task snapshot each enabled=!!wsId. Archived/missing agents skip that presence child. Presence errors substitute empty arrays, missing data stays loading, missing agent yields fallback; tick/memo derivation is local.

Reuse core-query-transport-coverage query audit: snapshot key is workspaces/wsId/agent-task-snapshot/list, stale 30s, gc 5min, focus refetch true (agents/queries.ts:57–65). Agent-list key workspaces/wsId/agents polls every 30s iff an unarchived online/unstable row exists; member key workspaces/wsId/members, squad key workspaces/wsId/squads, plugin key workspaces/wsId/plugins/installed, runtime key runtimes/wsId/list. No additional interval in these list factories. Refetch union for this caller is listAgents/listMembers/listSquads/listPluginInstallations/listRuntimes/getAgentTaskSnapshot, subject to those gates and standard TanStack cache/focus/reconnect observer behavior; no request counts asserted. Dashboard refresh dashboard/wsId prefix does not match these keys. No card mutation or invalidation callback; detail/settings/profile navigation terminates at platform adapter.

Avatar resources: workspace/avatar-url.ts:3–12 returns null for empty, prefixes trimmed API base for slash-leading values, otherwise preserves value. ui/components/common/actor-avatar.tsx:26–113 uses parseAvatarEmoji (ui/lib/avatar-emoji.ts:19–24), renders nonempty emoji locally, otherwise truthy URL as img src until onError fallback; URL change resets error. Both directory avatar and profile-card avatar use this path; profile uses base avatar directly, so no recursive hover. Browser image loading/redirects for arbitrary remote/data/blob/relative values are resource boundaries, with no fixed download endpoint inferred (reuse avatar-foreground E2). React/Base UI/TanStack and browser resource semantics terminate tracing. Only these concrete agent caller branches are closed; supporting modules have no whole-module coverage claim, unrelated member/squad hover payloads excluded. Static evidence only; no backend support claim.


ApiClient request delegates fetch → fetchRaw; GET default or explicit PUT; auth/workspace/CSRF/identity headers, credentials include; observer refusal before send; network errors throw; replayable 403 CSRF rejection retries once; 401 unauthorized handling; non-ok ApiError; 204 undefined otherwise JSON. No method promotion to POST.

Exact current frontend-calls tuples and full source hashes are in the companion JSON. Supporting client methods were read at 2062–2067, 2824–2925, 4513–4522; shared request transport at 960–974 and 1028–1143. No shared inventory was changed.

Root accepted bounded target-source coverage after hash/tuple validation and source spot checks of concrete parent update rollback/cache writes and agent profile hover/presence gates. Supporting child boundaries remain; no full descendant or runtime support claim.
