# Creation dialog transport coverage

Finite three-target static host closure; root integration/review pending. No runtime or backend support claim.

Squad: nonempty trimmed name, leader and !creating gate. POST create then unawaited squads-prefix invalidation. Selected members POST concurrently with per-member warning and allSettled; member-prefix invalidation follows even failures. Close/toast/navigation follow. Outer failure resets creating. Close does not abort request; clear avatar only changes local state.

Feedback: initial message merges incoming text unless already included; editor updates persist draft. Submit rejects pending/uploading/empty/>10000 latest trimmed markdown. POST includes share URL/workspace/kind/context; success clears draft and closes, failure toasts and retains draft. Mutation has no invalidation. Close does not abort upload or mutation.

Quick-create: member/agent/runtime/squad/project queries; actor resolution, visibility and project stale-id sweep are local. Version, source preview, cloud attachments and upload gates reject locally. Referenced attachment IDs only; anchored agent POST or ordinary quick-create POST. Structured source errors can await injected preview refetch. No explicit query invalidation after success. Preferences update; identity snapshot and mounted guard preserve newer drafts; untouched draft clears, then keep-open resets editor/refocus or closes.

Quick-create switch: upload gate blocks mode change; shared fields and optional manual assist-init persist locally; parent carry goes to injected shell callback. Settings saves prompt before navigation. Voice inserts text or invokes same submit. Close does not cancel create; RAF cleanup cancels focus only.

Issue upload binding: shared pool deduplicates client IDs, settles only extant rows, strips signed URLs, records failure/removal locally; mode-captured body append survives mode switch. Empty issue context passed to coordinated engine; cancellation semantics reused from draft-attachment audit.

Query closure: memberListOptions -> listMembers client:3765; agentListOptions -> listAgents client:2066 with workspace_id and include_archived=true, polling 30s only for nonarchived online/unstable cached agents; projectListOptions -> listProjects client:4517 with include_archived=true and selects projects; runtimeListOptions -> listRuntimes client:2276 with workspace_id, optional owner and workspace header override. Runtime response uses schema fallback to []; project list uses schema fallback. These helpers establish frontend calls only.

CLI guards are local: metadata.cli_version must be string; trimmed empty/unparsable is missing, numeric semver below 0.2.21 is too_old; explicit priority or due date additionally needs 0.4.3. git-describe development shape passes. Host blocks only with a visible selected runtime bound to the agent and provider other than qoder_cloud; absent row defers precheck. No server behavior verified.

Feedback context validator accepts only object kind desktop_route_error, string trigger, object error with string name/message and absent-or-string stack; extra fields are not stripped. Invalid context omitted by host. Draft factory merges patches into fresh draft objects, clones defaults on clear, persists via workspace-aware JSON storage by default, merges defaults on rehydration, registers workspace rehydration and cleanup callbacks. Storage adapters and lifecycle callback invocation are boundary dependencies, not independently verified here.

Residual boundaries:

- Squads-prefix factory union from issue-query: listSquads, listInvolvedSquadIds, getSquadMemberStatus; member key is members, distinct from members-status. Other mounted observer fanout and navigation destination are outside host closure.
- Injected preview refetch reused composer parent resolution client:1680; arbitrary injected replacements are boundary. Standard React/Tanstack/browser libraries stop traversal.
- Avatar upload/crop/text and browser resource behavior reuse avatar-foreground proof; editor upload/composer/attachment and voice behavior reuse named batches. Property picker internals, ActorAvatar resources, navigation destinations, arbitrary injected callback replacements and mounted observer fanout remain explicit child/caller boundaries; no entire descendant-tree claim.
- Draft persistence adapters (workspace-storage, defaultStorage, cleanup-registry), Zustand persistence internals, React/Tanstack and browser standard libraries terminate this bounded trace. No adapter lifecycle or storage runtime claim.

Evidence: JSON records exact current inventory tuples, validated source hashes, separate inventory snapshot hash, and hashed reused proofs. Supporting client slices and editor-upload proof do not claim whole-source review. No git, runtime, data, network, model, integration, shared inventory or ledger operations.

Root accepted bounded three-target host scope after concrete validator/runtime client/draft factory checks and hash/tuple validation. No runtime or full descendant-tree claim.
