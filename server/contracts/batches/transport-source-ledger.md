# Bounded transport source ledger

Global coverage remains false. Static closure is separate from runtime/backend support.

Original candidates: 165 closed, 0 pending. Expanded union: 210 sources, 0 pending. Exact search limitations and proof pointers remain in JSON.

## Original candidates with proof

- `apps/web/app/(auth)/login/page.tsx`
- `apps/web/app/(landing)/download/page.tsx`
- `apps/web/app/api/upload-file/route.ts`
- `apps/web/app/verification-login.tsx`
- `apps/web/components/web-providers.tsx`
- `apps/web/config/google-analytics.ts`
- `apps/web/features/landing/components/contact-sales-page-client.tsx`
- `apps/web/features/landing/utils/github-release.ts`
- `apps/web/features/landing/utils/parse-release-assets.ts`
- `apps/web/features/landing/utils/use-github-stars.ts`
- `apps/web/platform/upload-proxy.ts`
- `apps/web/proxy.ts`
- `packages/core/agents/queries.ts`
- `packages/core/agents/use-agent-activity.ts`
- `packages/core/agents/use-workspace-presence-prefetch.ts`
- `packages/core/analytics/exception-dedupe.ts`
- `packages/core/analytics/index.ts`
- `packages/core/api/client.ts`
- `packages/core/api/index.ts`
- `packages/core/api/realtime-observer.ts`
- `packages/core/api/request-observer.ts`
- `packages/core/api/schemas.ts`
- `packages/core/api/ws-client.ts`
- `packages/core/appearance/theme-css.ts`
- `packages/core/attachments/deliverables.ts`
- `packages/core/attachments/image-sequence.ts`
- `packages/core/auth/store.ts`
- `packages/core/billing/mutations.ts`
- `packages/core/chat/message-cache.ts`
- `packages/core/chat/queries.ts`
- `packages/core/chat/store.ts`
- `packages/core/connected-apps/queries.ts`
- `packages/core/dashboard/failure-class.ts`
- `packages/core/diagnostics/dev-recorder.ts`
- `packages/core/drafts/cleanup-registry.ts`
- `packages/core/drafts/draft-upload.ts`
- `packages/core/drafts/index.ts`
- `packages/core/drafts/upload-coordinator.ts`
- `packages/core/feature-flags/static-provider.ts`
- `packages/core/hooks/use-file-upload.ts`
- `packages/core/inbox/queries.ts`
- `packages/core/inbox/ws-updaters.ts`
- `packages/core/issue-statuses/queries.ts`
- `packages/core/issues/cache-coordinator.ts`
- `packages/core/issues/canonical-id.ts`
- `packages/core/issues/mutations.ts`
- `packages/core/issues/queries.ts`
- `packages/core/issues/status-category.ts`
- `packages/core/issues/stores/comment-draft-store.ts`
- `packages/core/issues/stores/draft-store.ts`
- `packages/core/issues/surface/filter-dependency.ts`
- `packages/core/issues/surface/repository.ts`
- `packages/core/issues/timeline-sort.ts`
- `packages/core/issues/ws-updaters.ts`
- `packages/core/notification-preferences/queries.ts`
- `packages/core/paths/paths.ts`
- `packages/core/paths/reserved-slugs.ts`
- `packages/core/platform/core-provider.tsx`
- `packages/core/platform/session-renewal.ts`
- `packages/core/platform/types.ts`
- `packages/core/realtime/hooks.ts`
- `packages/core/realtime/provider.tsx`
- `packages/core/realtime/use-realtime-sync.ts`
- `packages/core/search-index/client.ts`
- `packages/core/search-index/host.ts`
- `packages/core/search-index/protocol.ts`
- `packages/core/search-index/worker.ts`
- `packages/core/types/agent.ts`
- `packages/core/types/api.ts`
- `packages/core/types/attachment-url.ts`
- `packages/core/types/attachment.ts`
- `packages/core/types/chat.ts`
- `packages/core/types/events.ts`
- `packages/core/workspace/hooks.ts`
- `packages/ee/project-folders/data.ts`
- `packages/views/agents/components/agent-advanced-settings.tsx`
- `packages/views/agents/components/agent-detail-inspector.tsx`
- `packages/views/agents/components/tabs/activity-tab.tsx`
- `packages/views/agents/components/tabs/env-tab.tsx`
- `packages/views/agents/create/agent-configuration-panel.tsx`
- `packages/views/agents/create/use-builder-session.ts`
- `packages/views/attachments/attachment-preview-page.tsx`
- `packages/views/autopilots/components/autopilot-detail-page.tsx`
- `packages/views/chat/chat-page.tsx`
- `packages/views/chat/components/chat-add-menu.tsx`
- `packages/views/chat/components/chat-input.tsx`
- `packages/views/chat/components/chat-window.tsx`
- `packages/views/chat/components/use-chat-controller.ts`
- `packages/views/chat/components/use-chat-draft-restore.ts`
- `packages/views/common/avatar-crop-dialog.tsx`
- `packages/views/common/avatar-upload-control.tsx`
- `packages/views/common/task-transcript/transcript-button.tsx`
- `packages/views/common/text-avatar-dialog.tsx`
- `packages/views/common/text-avatar.ts`
- `packages/views/dashboard/components/contribution-tab.tsx`
- `packages/views/dashboard/components/dashboard-page.tsx`
- `packages/views/dashboard/components/leaderboard.tsx`
- `packages/views/dashboard/utils.ts`
- `packages/views/editor/attachment-card.tsx`
- `packages/views/editor/attachment-download-context.tsx`
- `packages/views/editor/attachment.tsx`
- `packages/views/editor/content-editor.tsx`
- `packages/views/editor/extensions/file-card.tsx`
- `packages/views/editor/extensions/file-upload.ts`
- `packages/views/editor/extensions/image-view.tsx`
- `packages/views/editor/extensions/index.ts`
- `packages/views/editor/hooks/use-inline-media-url.ts`
- `packages/views/editor/index.ts`
- `packages/views/editor/paste-as-file.ts`
- `packages/views/editor/preview-sequence-context.tsx`
- `packages/views/editor/styles/attachment.css`
- `packages/views/editor/use-composer-submit.ts`
- `packages/views/editor/use-coordinated-uploads.ts`
- `packages/views/editor/use-editor-upload.ts`
- `packages/views/editor/use-lazy-editor.ts`
- `packages/views/editor/use-upload-gate.ts`
- `packages/views/editor/utils/hash-string.ts`
- `packages/views/editor/utils/iframe-fragment-nav.ts`
- `packages/views/editor/utils/preview.ts`
- `packages/views/invitations/use-invitation-actions.ts`
- `packages/views/issues/actions/issue-actions-menu-items.tsx`
- `packages/views/issues/components/annotation-composer.tsx`
- `packages/views/issues/components/comment-card.tsx`
- `packages/views/issues/components/comment-input.tsx`
- `packages/views/issues/components/composer-frame.tsx`
- `packages/views/issues/components/deliverables/attachment-versions.tsx`
- `packages/views/issues/components/deliverables/deliverable-details.tsx`
- `packages/views/issues/components/deliverables/deliverable-link.tsx`
- `packages/views/issues/components/deliverables/deliverables-overview.tsx`
- `packages/views/issues/components/deliverables/version-badge.tsx`
- `packages/views/issues/components/infinite-scroll-sentinel.tsx`
- `packages/views/issues/components/inline-comment-run.tsx`
- `packages/views/issues/components/issue-chip.tsx`
- `packages/views/issues/components/issue-detail.tsx`
- `packages/views/issues/components/issue-hover-card.tsx`
- `packages/views/issues/components/issue-mention-card.tsx`
- `packages/views/issues/components/reply-input.tsx`
- `packages/views/issues/components/swimlane-view.tsx`
- `packages/views/issues/components/use-comment-uploads.ts`
- `packages/views/issues/hooks/use-issue-trigger-preview.ts`
- `packages/views/issues/surface/issue-surface.tsx`
- `packages/views/issues/surface/use-issue-surface-controller.ts`
- `packages/views/issues/utils/status-label.ts`
- `packages/views/issues/utils/status-options.ts`
- `packages/views/layout/tab-presentation.tsx`
- `packages/views/members/member-profile-card.tsx`
- `packages/views/modals/create-issue.tsx`
- `packages/views/modals/create-squad.tsx`
- `packages/views/modals/feedback.tsx`
- `packages/views/modals/quick-create-issue.tsx`
- `packages/views/modals/use-issue-create-uploads.ts`
- `packages/views/platform/scroll-restoration.tsx`
- `packages/views/plugins/surface-bridge.ts`
- `packages/views/rich-content/rich-content.tsx`
- `packages/views/runtimes/components/update-section.tsx`
- `packages/views/settings/components/account-tab.tsx`
- `packages/views/settings/components/lark-channel-authorization.tsx`
- `packages/views/settings/components/plugins-tab.tsx`
- `packages/views/settings/components/settings-layout.tsx`
- `packages/views/settings/components/workspace-tab.tsx`
- `packages/views/skills/components/create-skill-dialog.tsx`
- `packages/views/skills/lib/origin.ts`
- `packages/views/squads/components/squad-detail-page.tsx`
- `packages/views/test/shard-timings.json`
- `packages/views/voice/engine.ts`

## core-transport-and-state



## editor-and-attachments



## enterprise



## issues-and-composers



## remaining-view-surfaces



## web-shell-and-proxies



## Hash evidence qualification

Root verified6 recovered prior hash pointers.42 earlier semantic source dispositions still lack prior hash evidence and require fresh source review or original snapshots. No stale bytes were demonstrated. The zero semantic-pending count must not be read as all hashes verified or whole-application coverage complete.

Added3 root-reviewed fresh-search sources (repository settings, external logos, retained analytics loader); enumerated union213. Global coverage and42prior-hash gaps remain incomplete.

Fresh current-source auth/onboarding review covers9actual files (earlier ten-count corrected); outstanding prior-hash/current-review gaps now33. Historical byte identity not asserted.

Added6root-reviewed wrapper/support sources; union219. Global coverage remains incomplete.

Voice8 current-source evidence accepted; remaining earlier-source evidence refresh gaps25. Global coverage remains incomplete.

## Current-source refresh review: workspace and search index

Accepted 16 bounded source refreshes from workspace-helper-source-refresh, search-index-runtime-refresh and search-index-storage-refresh. Root recomputed hashes, checked exact inventory tuples and reviewed critical source excerpts; implementer full-body reads remain attributed. Of the originally flagged hash-evidence set, 9 current-source refresh gaps remain. Historical byte identity is unknown. Whole-application coverage remains false; no runtime or backend completion is claimed.

Plugin bridge current-source refresh accepted with rejected task-message candidate separated. Eight originally flagged current-source hash refresh gaps remain; global coverage remains false.

## Original hash-evidence gap refresh completed

Accepted the final eight current-source refreshes from transport-proxy-analytics-refresh and editor-coordination-source-refresh. All 42 originally missing prior-hash records now have new current-source review evidence; six other pointers were reconciled earlier. This does not establish historical byte identity. Root validated hashes, exact tuples and range partitions and reviewed critical source excerpts; implementer full-body reads are attributed. Broader source discovery and interface coverage remain incomplete; coverage_complete remains false. No runtime or backend completion is claimed.
