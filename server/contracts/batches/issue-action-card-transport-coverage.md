# Issue action/card transport audit

Partial static evidence; root review pending. Full target-body coverage is explicitly false.

Menu issueTasksOptions is enabled for full variant; sidebar StopRunItems observes workspace task snapshot and passes task to injected onStopRun. Full quick actions query active catalog and invoke useQuickActionRunner; settled invalidates timeline, tasks, catalog.

Menu actions object is injected: updateField, pin, relation, delete-confirm, rename and navigation effects require caller proof; handoff opens modal instead of immediate status update. Clipboard handlers use cached workdir or issue text.

Edit state uses edit:issueId:commentId draft, upload gate, trigger preview and recipient actions with allowSteer false. Preview debounces mention signature 300ms, disables empty/note, retries false, same-context placeholder only. Recipient task observer enabled only with issueId and preview agents.

Edit submit checks cancelled flag; collects body referenced and retained standalone attachment ids; unchanged trimmed content and id set accepts without write. Calls injected onEdit with contentBase and suppression ids. revision_conflict retains draft; accepted cleanup consumes only unchanged submitted draft; unmounted cleanup preserves newer edits.

Comment menus delegate reply, reaction, resolution, subissue and copy-link callbacks. Delete uses confirmation. AttachmentList filters referenced attachments, orders standalone groups and passes attachment objects to renderer and download provider; native resource and renderer descendants remain boundaries.

TaskCommentRetryButton directly calls rerunIssue with pending guard and toast; no explicit cache invalidation in that callback. Inline cancel/retry hooks invalidate issue task key on success.

Inline transcript loads for running status, expanded inline presentation or full log. useTaskMessages additionally validates task id; mount/focus always refetch, enabled transition or live-to-ended causes refetch(cancelRefetch:false). Error buttons call refetch. Timeline steer observer enabled false reads cache only. Active elapsed timer is local.

Remaining: Complete bounded reads of all three target bodies, direct own-hook closure, concrete observer tuples and per-prefix refetch union remain required. ActorAvatar, ContentEditor, ReadonlyContent, AttachmentRenderer, ReplyInput, plugin menus, assignee picker and transcript StepBody descendant trees are not certified here. Injected parent callbacks require concrete caller reconciliation; reused cache proof supplies conservative refetch candidates, not proof every candidate is reachable.

Validated source snapshot SHA-256 values and exact current inventory tuples for enumerated edges. No application runtime, Git, database, network, model or integration operations performed.
