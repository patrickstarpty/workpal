# Issue composer transport audit

Five complete source snapshots and SHA-256 hashes are retained in the companion JSON. Own callbacks are separated from delegated child surfaces. Concrete comment/reply submit hosts are reused from composer-submit coverage; both reach client:1876 and optionally client:3133. Upload binding delegates client:4078. Editor child unions are conditional possibilities, not requests made by composer callbacks.

**packages/views/issues/components/annotation-composer.tsx**

annotationsWithPending replaces by id or appends. save reads markdown and invokes onSave(note,true) when nonblank/canSave/not busy. send rejects absent controls, missing target, busy/inFlight or cannot save; commits onSave(note,false) before awaiting controls.submit; finally resets busy. Voice inserts only. onChange/onRemove/onSave/onBusyChange remain injected callbacks.

**packages/views/issues/components/comment-input.tsx**

Draft new:issueId persists updates and hidden/pagehide flush. External stored values hydrate. Submit normalizes current annotations, cancels only current signature-matching restart targets, snapshots flushed entry, filters attachment ids referenced by composed body, forwards routing arrays only when nonempty. Truthy acceptance clears only untouched draft and mounted editor; string id alone invokes onAccepted. Voice submits only without restart targets. Shell Enter/Space and attachment/drop activate lazy editor.

**packages/views/issues/components/reply-input.tsx**

Optional draftKey distinguishes persisted and local uploads. Preview parent may come from pending annotation; changed current reply target rejects before cancel/send. Missing target normalizes empty. Same routing/reference filters as comment. Acceptance retains changed persisted draft; local branch removes uploads only while mounted. Focus handle activates lazy editor; bindComposer also delegates voice ref. All shell/update/attach/send callbacks mirror comment.

**packages/views/issues/components/composer-frame.tsx**

Focus ignores idle tools; blur checks contains relatedTarget. Expanded state freezes while voice holds. FileUploadButton forwards each selected file to injected onAttach. keepFocus prevents default only on empty toolbar space. Voice and recipients/tools/send are child surfaces, no own HTTP.

**packages/views/issues/components/use-comment-uploads.ts**

Memoized keyed binding uses getState for every get/add/settle/fail/remove/body/append callback, registryKey comment:draftKey. No key supplies undefined binding and EMPTY_UPLOADS. Delegates context, editor gate and ref to useCoordinatedUploads; owns no direct HTTP or object URL operation.

Remaining descendant/host boundaries are listed in JSON; the earlier own-hook gaps are superseded by the live-hook supplement below. Global coverage remains incomplete.

Browser resources and evidence hashes are recorded in JSON. No backend support or execution claim. Root review pending.

## Live hook evidence supplement

Live hook supplement (bounded static trace):
useCommentTriggerPreview: signature is empty for blank or /note; deduplicates non-issue mentions. Nonempty signatures debounce 300ms with timeout cleanup. Query key includes issue,parent,editing and debounced signature; enabled only when both signatures nonempty. POST client:1890 uses current content ref and optional parent/edit ids, retry false, staleTime zero. Previous data retained only in same issue/parent/edit context; isCurrent requires matching signature, success and no placeholder. No AbortSignal is forwarded; timer cleanup does not cancel HTTP.
useRecipientActions: issueTasksOptions timeline observer enabled only for issueId plus nonempty agents; GET client:3116 uses view=timeline, no subtree, staleTime 30000 and focus refetch. Select keeps recipient agent ids and queued/deferred/dispatched/waiting_local_directory/running. Running wins over starting then queued; steering requires task-supplement-v1 and can_supplement. Attachments disable steer, allowSteer gates restart. Choices reset on resetKey and prune removed recipients. skip produces suppressAgentIds, steer exact running task ids, restart non-idle task ids. This hook has no mutation. Personal runningAgentReply preference is a store subscription.
useQuickActionMenu: nullable workspace id gates catalog observer; GET client:4917 with empty suffix (includeArchived=false), key quick-actions/wsId/list/false. Active catalog entries only; selection builds cached prompt/mention text, missing targets toast and return empty. No invocation mutation or preflight.
useStickyComposer: subscribes to persisted sticky preference, returns preferred && !isMobile. useIsMobile registers max-width:767px matchMedia change listener, samples innerWidth<768, removes listener on cleanup. Store defaults sticky=true, runningAgentReply=steer; persistence key workpal_comment_composer through defaultStorage. Platform storage adapter is a remaining boundary, not a remote transport claim.
Cancellation: useStopRunsBeforeSend awaits Promise.all exact restart ids through useCancelIssueRun, returns false and toast on any rejection. Success invalidates issueKeys.tasks(issueId). Within these four hook observers the finite possible refetch route union is client:1890, client:3116, client:4917; cancellation invalidation intersects only tasks observer (client:3116), gated as above. Library focus/reconnect/cache scheduling stops at TanStack boundary; arbitrary mounted observers and global mutation fanout are not certified.
Annotation host: use-comment-annotations.tsx renderComposer supplies onChange local editor/error state, onSave confirmNote (add/update draft annotation then optional close; onAdded callback for new entries), onRemove draft removal then close, onBusyChange guarded submitting ref. editAnnotation resolves source/range, optionally scrolls, invokes onOpen, sets editor/selection/focus state; absent source/range returns false. DOM listeners are removed, MutationObserver disconnected, CSS highlights deleted on cleanup. controls.submit remains the comment/reply send chain already recorded. onOpen/onAdded and selection/bubble helpers remain descendant boundaries.
Voice child scope reuses voice-transport-coverage.json only; no arbitrary descendant-tree certification.

Earlier unresolved-hook statements are superseded by this supplement only. Coverage remains incomplete; root review pending; no backend support claim.

Root accepted five bounded target bodies after source-snapshot validation and concrete live-hook spot checks. Normalized whole_source to a Boolean; preserved captured code under source_snapshot. Supporting modules remain unpromoted, and host/child boundaries remain.
