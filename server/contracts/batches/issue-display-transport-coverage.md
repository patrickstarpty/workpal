# Issue display transport audit

packages/views/issues/components/infinite-scroll-sentinel.tsx: Observer captures node, observes with rootMargin, disconnects on cleanup/rebuild; ref updated each render. Each intersecting callback invokes latest injected onVisible. No loading gate, explicit debounce or fetch exists; loading/label only render spinner text.

packages/views/issues/components/issue-chip.tsx: useChipIssue observes list then enables detail only absent list match; focus callback suppresses ApiError 404 only. Status hook still runs before children override or fallback; override does not suppress queries. Chip renders text/status, no link/media.

packages/views/issues/components/issue-hover-card.tsx: Hover wrapper delegates mount timing to UI library. Body detail pending skeleton; error or absent data terminal label; success mounts Details. Details observes status twice through label hook, actor directories, conditional plugin installations, workspace child progress and task snapshot; projects only with project_id, parent only with parent id; PR query with issue id. selectIssueTasks filters snapshot locally; running assignee beats queued. Description flattened to text, first open/draft PR else first; labels capped at three, date/progress conditional. Avatar children explicitly disable hover/profile links; no direct media element or navigation callback in target.

packages/views/issues/components/issue-mention-card.tsx: Provider/hover/link are child components. Loaded issue enables context callback: stop propagation then yield to editor/selected text else openMenu(issue,event). Peek host adds handlers: primary shift without meta/control/alt prevents selection on mousedown and prevents navigation then toggle(issueId) on click. Other clicks delegated AppLink. Current issue overrides chip content but does not skip chip queries. AppLink prefetch on hover/focus is independent of hover-card opening.

packages/views/layout/tab-presentation.tsx: All inbox active/archive/page/lookup, project/autopilot/skill, actor directories, runtime and chat observers explicitly disabled. Canonical issue enabled only fetch and direct issue or known issue-backed inbox row, internally workspace/id gated; identifier resolution seeds UUID initialData and mirrors identifier cache without replacing existing row. Status fetch only fetch + workspace + direct issue. No retry callback returned by canonical hook is invoked here. Title/visual switches and pending fallbacks local. Actor visual falls back before workspace, otherwise child avatar profileLink=false with hover/dot absent; project icon is text, not URL.

Remaining bounded edges:

- InfiniteScrollSentinel.onVisibleRef.current: arbitrary supplied () => void; caller pagination/fetch behavior is outside five targets.
- IssueMentionLink peek.toggle(issueId): injected IssuePeekActionsContext provider implementation and resulting panel descendants outside scope.
- IssueMentionLink openMenu(issue,event): sidebar context-menu child/provider action descendants outside scope; target opens menu, does not select a mutation.
- AppLink navigation push/openInNewTab/getShareableUrl/prefetch and RouteDataPrefetchContext(href): injected adapters/providers; concrete AppLink dispatch reviewed, provider transport union not certified here.
- ActorAvatar child resolves directory avatar_url through resolvePublicFileUrl: leading slash concatenated with trimmed API base, other strings preserved. Native image resource URLs may be relative, arbitrary-host, data or blob; no inventory API tuple inferred. Entire avatar/UI descendant trees not certified.
- useActorName feature flag provider and plugin installation gate depend on existing plugin evidence; no whole descendant closure asserted.

Validated JSON and exact inventory tuples; current target hashes recorded. Static audit only; no runtime/network/model calls or backend support claim.

Root accepted bounded target scope after sentinel/chip body review and tab/hover query gate checks. PR read remains subject to pr-view-refresh-event.json obligations; GET does not imply no backend event. Injected host/descendant exceptions remain.
