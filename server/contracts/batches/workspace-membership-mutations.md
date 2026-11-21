# Workspace membership mutations

Source inspection only; no Go parity execution or runtime changes. Read root AGENTS, approved backend spec and plan Tasks 3/7, and auth-workspaces-health contract. Invitations are excluded.

PATCH and DELETE /api/workspaces/{id}/members/{memberId} require router owner/admin; POST /api/workspaces/{id}/leave requires membership. Global auth/CSRF still applies. Workspace middleware hides missing membership with 404; role denial is 403. Handler resolves target by member UUID and verifies workspace, returning 404 member not found for absent/cross-workspace target. Malformed member UUID is 400 invalid member id. PATCH decodes Go string role: omitted/null/blank => role is required; nonstring => invalid request body; trims whitespace but preserves case; only owner/admin/member accepted. Unknown object keys are ignored. Whole-body null likewise leaves role empty. Successful PATCH returns id, workspace_id, user_id, role, created_at, name, email, avatar_url (explicit null allowed), no pinned_at. Avatar resolves through handler resolver.

Only owner may modify an owner or promote anyone to owner. Admin may modify/remove another admin or self; member cannot use admin routes even on self. Any role may leave. Owner self-demotion/removal/leave requires another owner. Same-role owner update is allowed. Go countOwners check occurs before mutation, outside revocation transaction: do not claim concurrent last-owner safety. Python must serialize writer acquisition before actor/target/count reads and recheck inside transaction; race demote/remove/leave, invitation acceptance, runtime sharing and subscription insertion against that same boundary. Deleted target on retry is 404; no invented idempotent 204.

Removal and leave share revokeAndRemoveMember. Exact SQL dependencies are embedded in JSON. Transaction locks subscriber writes first, then runtime-share member removal; finds workspace-owned runtimes, archives agents on those runtimes, cancels tasks by runtime OR archived agent (including historical reassignment), withdraws supplements and settles terminal task state, forces runtimes offline and deletes workspace daemon tokens. Prunes channel bindings, invocation grants, private quick actions/views, view preferences, issue/autopilot subscriptions, pending app approvals; enqueues capacity release when enabled. Shared runtime lists remove departing user: public retains visibility; private access revocation cancels nonowner tasks, prepares deferred chat cancellation, unbinds agents and pauses autopilots. Removes project memberships/subscriptions then membership, commits. Other workspaces and shared workspace furniture survive. Do not substitute generic runtime deletion: membership revocation does not delete all historical chats or global user/session JWTs.

Postcommit: disconnect exact member realtime, settle capacity release, invalidate membership cache; revoke daemon token cache, broadcast task cancellations before agent:archived {agent}, shared teardown agent:status {agent} and autopilot:updated {autopilot}, finalize deferred cancelled chats; daemon:register {action: revoke} only if offline/shared runtime changes. Finally member:removed {member_id,workspace_id,user_id} and refresh removed user's daemon workspace list. PATCH invalidates cache and emits member:updated {member}; GetUser failure after role write returns 500 failed to load member in Go. Python atomic response/event policy must explicitly test this difference rather than copy a partial commit accidentally.

Python currently implements remove_membership using a writer UPDATE before ownership reads, caller-owned transaction and membership deletion only; no removal/leave/PATCH member HTTP route. This helper is not cascade parity. Existing session/realtime checks deny revoked memberships at send boundaries, but protocol project_event rejects member:updated/member:removed and revocation event types; consumer quarantines unsupported envelopes. Outbox append and durable stream bridge exist, not these producers. Extend strict projection/audience handling before exposing producers. Workspace audience must exclude strangers and cross-workspace listeners, reauthorize at actual send, disconnect removed member even while idle; never rely on removed socket receiving member:removed to enforce denial. No global logout or revocation of unrelated workspace sessions. Surviving members receive updates; daemon refresh is user-targeted control, not a fabricated browser event. Atomic SQLite outbox must carry stable IDs; Redis outage preserves committed mutation, retry/restart and duplicate delivery must not repeat destructive consumer effects.

SQLite: member UUIDs canonical TEXT, role CHECK(owner/admin/member), UNIQUE(workspace_id,user_id), UTC created_at TEXT, nullable pinned_at; preserve global user joins/null avatar. PostgreSQL UUID arrays/ANY become bounded parameterized IN or temporary relation; JSON/array shared_with needs validated JSON or normalized association, never raw PG array syntax. Translate advisory/FOR UPDATE locks into shared SQLite writer serialization, ordered application cleanup for no-FK tables and one transaction. Do not create placeholder agent/task/runtime rows or bypass pending routes because tables are absent. Full removal needs schema and service contracts for all embedded query dependencies plus SettleTerminalTaskState/PrepareRuntimeAccessCancellation and capacity release; explicit unsupported production operations remain blocked, not successful no-ops.

Next bounded slice: implement role PATCH only in NEW workspaces/membership_mutations.py and workspaces/membership_mutation_routes.py; mount through app.py; extend realtime/protocol.py for member:updated; use existing models/repository/outbox. Tests NEW tests/test_membership_role_mutations.py and tests/test_membership_mutation_events.py: exact fixtures/nulls, actor matrix/self, foreign IDs, same-role, rollback/user-load failure, two concurrent owner demotions, reopen, committed outbox, Redis outage/restart/stable-ID duplicates and audience denial. Removal/leave next slice is blocked on complete cascade dependency implementation, not permission to expose remove_membership. Proposed future NEW workspaces/membership_revocation.py and tests/test_membership_revocation.py must cover every query cleanup, cross-workspace preservation, rollback at every stage, idle socket removal and concurrent subscription/share writers. Migration filenames require parent allocation after current head review; none allocated or changed here.

## Source appendix

### server/go/internal/handler/workspace.go

```text
568: type MemberWithUserResponse struct {
569: 	ID          string  `json:"id"`
570: 	WorkspaceID string  `json:"workspace_id"`
571: 	UserID      string  `json:"user_id"`
572: 	Role        string  `json:"role"`
573: 	CreatedAt   string  `json:"created_at"`
574: 	Name        string  `json:"name"`
575: 	Email       string  `json:"email"`
576: 	AvatarURL   *string `json:"avatar_url"`
577: }
578: 
579: func (h *Handler) ListMembersWithUser(w http.ResponseWriter, r *http.Request) {
580: 	workspaceID := workspaceIDFromURL(r, "id")
581: 	wsUUID, ok := parseUUIDOrBadRequest(w, workspaceID, "workspace id")
582: 	if !ok {
583: 		return
584: 	}
585: 
586: 	members, err := h.Queries.ListMembersWithUser(r.Context(), wsUUID)
587: 	if err != nil {
588: 		writeError(w, http.StatusInternalServerError, "failed to list members")
589: 		return
590: 	}
591: 
592: 	resp := make([]MemberWithUserResponse, len(members))
593: 	for i, m := range members {
594: 		resp[i] = MemberWithUserResponse{
595: 			ID:          uuidToString(m.ID),
596: 			WorkspaceID: uuidToString(m.WorkspaceID),
597: 			UserID:      uuidToString(m.UserID),
598: 			Role:        m.Role,
599: 			CreatedAt:   timestampToString(m.CreatedAt),
600: 			Name:        m.UserName,
601: 			Email:       m.UserEmail,
602: 			AvatarURL:   h.resolveAvatarURLPtr(textToPtr(m.UserAvatarUrl)),
603: 		}
604: 	}
605: 
606: 	writeJSON(w, http.StatusOK, resp)
607: }
608: 
609: type CreateMemberRequest struct {
610: 	Email string `json:"email"`
611: 	Role  string `json:"role"`
612: }
613: 
614: func (h *Handler) memberWithUserResponse(member db.Member, user db.User) MemberWithUserResponse {
615: 	return MemberWithUserResponse{
616: 		ID:          uuidToString(member.ID),
617: 		WorkspaceID: uuidToString(member.WorkspaceID),
618: 		UserID:      uuidToString(member.UserID),
619: 		Role:        member.Role,
620: 		CreatedAt:   timestampToString(member.CreatedAt),
621: 		Name:        user.Name,
622: 		Email:       user.Email,
623: 		AvatarURL:   h.resolveAvatarURLPtr(textToPtr(user.AvatarUrl)),
624: 	}
625: }
626: 
627: func normalizeMemberRole(role string) (string, bool) {
628: 	if role == "" {
629: 		return "member", true
630: 	}
631: 
632: 	role = strings.TrimSpace(role)
633: 	switch role {
634: 	case "owner", "admin", "member":
635: 		return role, true
636: 	default:
637: 		return "", false
638: 	}
639: }
640: 
641: type UpdateMemberRequest struct {
642: 	Role string `json:"role"`
643: }
644: 
645: func (h *Handler) UpdateMember(w http.ResponseWriter, r *http.Request) {
646: 	workspaceID := workspaceIDFromURL(r, "id")
647: 	requester, ok := h.workspaceMember(w, r, workspaceID)
648: 	if !ok {
649: 		return
650: 	}
651: 
652: 	memberID := chi.URLParam(r, "memberId")
653: 	memberUUID, ok := parseUUIDOrBadRequest(w, memberID, "member id")
654: 	if !ok {
655: 		return
656: 	}
657: 	target, err := h.Queries.GetMember(r.Context(), memberUUID)
658: 	if err != nil || uuidToString(target.WorkspaceID) != uuidToString(requester.WorkspaceID) {
659: 		writeError(w, http.StatusNotFound, "member not found")
660: 		return
661: 	}
662: 
663: 	var req UpdateMemberRequest
664: 	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
665: 		writeError(w, http.StatusBadRequest, "invalid request body")
666: 		return
667: 	}
668: 	if strings.TrimSpace(req.Role) == "" {
669: 		writeError(w, http.StatusBadRequest, "role is required")
670: 		return
671: 	}
672: 
673: 	role, valid := normalizeMemberRole(req.Role)
674: 	if !valid {
675: 		writeError(w, http.StatusBadRequest, "invalid member role")
676: 		return
677: 	}
678: 
679: 	if (target.Role == "owner" || role == "owner") && requester.Role != "owner" {
680: 		writeError(w, http.StatusForbidden, "insufficient permissions")
681: 		return
682: 	}
683: 
684: 	if target.Role == "owner" && role != "owner" {
685: 		members, err := h.Queries.ListMembers(r.Context(), target.WorkspaceID)
686: 		if err != nil {
687: 			writeError(w, http.StatusInternalServerError, "failed to update member")
688: 			return
689: 		}
690: 		if countOwners(members) <= 1 {
691: 			writeError(w, http.StatusBadRequest, "workspace must have at least one owner")
692: 			return
693: 		}
694: 	}
695: 
696: 	updatedMember, err := h.Queries.UpdateMemberRole(r.Context(), db.UpdateMemberRoleParams{
697: 		ID:   target.ID,
698: 		Role: role,
699: 	})
700: 	if err != nil {
701: 		writeError(w, http.StatusInternalServerError, "failed to update member")
702: 		return
703: 	}
704: 
705: 	h.MembershipCache.Invalidate(r.Context(), uuidToString(target.UserID), workspaceID)
706: 
707: 	user, err := h.Queries.GetUser(r.Context(), updatedMember.UserID)
708: 	if err != nil {
709: 		writeError(w, http.StatusInternalServerError, "failed to load member")
710: 		return
711: 	}
712: 
713: 	userID := requestUserID(r)
714: 	h.publish(protocol.EventMemberUpdated, uuidToString(requester.WorkspaceID), "member", userID, map[string]any{
715: 		"member": h.memberWithUserResponse(updatedMember, user),
716: 	})
717: 
718: 	writeJSON(w, http.StatusOK, h.memberWithUserResponse(updatedMember, user))
719: }
720: 
721: func (h *Handler) DeleteMember(w http.ResponseWriter, r *http.Request) {
722: 	workspaceID := workspaceIDFromURL(r, "id")
723: 	requester, ok := h.workspaceMember(w, r, workspaceID)
724: 	if !ok {
725: 		return
726: 	}
727: 
728: 	memberID := chi.URLParam(r, "memberId")
729: 	memberUUID, ok := parseUUIDOrBadRequest(w, memberID, "member id")
730: 	if !ok {
731: 		return
732: 	}
733: 	target, err := h.Queries.GetMember(r.Context(), memberUUID)
734: 	if err != nil || uuidToString(target.WorkspaceID) != uuidToString(requester.WorkspaceID) {
735: 		writeError(w, http.StatusNotFound, "member not found")
736: 		return
737: 	}
738: 
739: 	if target.Role == "owner" && requester.Role != "owner" {
740: 		writeError(w, http.StatusForbidden, "insufficient permissions")
741: 		return
742: 	}
743: 
744: 	if target.Role == "owner" {
745: 		members, err := h.Queries.ListMembers(r.Context(), target.WorkspaceID)
746: 		if err != nil {
747: 			writeError(w, http.StatusInternalServerError, "failed to delete member")
748: 			return
749: 		}
750: 		if countOwners(members) <= 1 {
751: 			writeError(w, http.StatusBadRequest, "workspace must have at least one owner")
752: 			return
753: 		}
754: 	}
755: 
756: 	requesterUserID := requestUserID(r)
757: 	result, err := h.revokeAndRemoveMember(r.Context(), target.WorkspaceID, target.UserID, target.ID, parseUUID(requesterUserID))
758: 	if err != nil {
759: 		slog.Warn("delete member failed", append(logger.RequestAttrs(r), "error", err, "member_id", memberID, "workspace_id", workspaceID)...)
760: 		writeError(w, http.StatusInternalServerError, "failed to delete member")
761: 		return
762: 	}
763: 	h.Hub.DisconnectMember(uuidToString(target.WorkspaceID), uuidToString(target.UserID), uuidToString(target.ID))
764: 	h.settleMemberCapacityRelease(r.Context(), uuid.UUID(target.WorkspaceID.Bytes), uuid.UUID(target.ID.Bytes))
765: 
766: 	h.MembershipCache.Invalidate(r.Context(), uuidToString(target.UserID), workspaceID)
767: 
768: 	wsIDStr := uuidToString(requester.WorkspaceID)
769: 	logRevocation(result, wsIDStr, uuidToString(target.UserID))
770: 	h.publishRevocation(r.Context(), result, wsIDStr, "member", requesterUserID)
771: 
772: 	slog.Info("member removed", append(logger.RequestAttrs(r), "member_id", uuidToString(target.ID), "workspace_id", workspaceID, "user_id", uuidToString(target.UserID))...)
773: 	h.publish(protocol.EventMemberRemoved, wsIDStr, "member", requesterUserID, map[string]any{
774: 		"member_id":    uuidToString(target.ID),
775: 		"workspace_id": wsIDStr,
776: 		"user_id":      uuidToString(target.UserID),
777: 	})
778: 	h.notifyDaemonWorkspacesChanged(uuidToString(target.UserID))
779: 
780: 	w.WriteHeader(http.StatusNoContent)
781: }
782: 
783: func (h *Handler) LeaveWorkspace(w http.ResponseWriter, r *http.Request) {
784: 	workspaceID := workspaceIDFromURL(r, "id")
785: 	member, ok := h.workspaceMember(w, r, workspaceID)
786: 	if !ok {
787: 		return
788: 	}
789: 
790: 	if member.Role == "owner" {
791: 		members, err := h.Queries.ListMembers(r.Context(), member.WorkspaceID)
792: 		if err != nil {
793: 			writeError(w, http.StatusInternalServerError, "failed to leave workspace")
794: 			return
795: 		}
796: 		if countOwners(members) <= 1 {
797: 			writeError(w, http.StatusBadRequest, "workspace must have at least one owner")
798: 			return
799: 		}
800: 	}
801: 
802: 	result, err := h.revokeAndRemoveMember(r.Context(), member.WorkspaceID, member.UserID, member.ID, member.UserID)
803: 	if err != nil {
804: 		slog.Warn("leave workspace failed", append(logger.RequestAttrs(r), "error", err, "workspace_id", workspaceID)...)
805: 		writeError(w, http.StatusInternalServerError, "failed to leave workspace")
806: 		return
807: 	}
808: 	h.Hub.DisconnectMember(uuidToString(member.WorkspaceID), uuidToString(member.UserID), uuidToString(member.ID))
809: 	h.settleMemberCapacityRelease(r.Context(), uuid.UUID(member.WorkspaceID.Bytes), uuid.UUID(member.ID.Bytes))
810: 
811: 	h.MembershipCache.Invalidate(r.Context(), uuidToString(member.UserID), workspaceID)
812: 
813: 	userID := requestUserID(r)
814: 	logRevocation(result, workspaceID, uuidToString(member.UserID))
815: 	h.publishRevocation(r.Context(), result, workspaceID, "member", userID)
816: 
817: 	slog.Info("member removed", append(logger.RequestAttrs(r), "member_id", uuidToString(member.ID), "workspace_id", workspaceID, "user_id", uuidToString(member.UserID))...)
818: 	h.publish(protocol.EventMemberRemoved, workspaceID, "member", userID, map[string]any{
819: 		"member_id":    uuidToString(member.ID),
820: 		"workspace_id": workspaceID,
821: 		"user_id":      uuidToString(member.UserID),
822: 	})
823: 	h.notifyDaemonWorkspacesChanged(uuidToString(member.UserID))
824: 
825: 	w.WriteHeader(http.StatusNoContent)
826: }
827: 
828: // workspaceDeleteLockTimeout bounds every lock wait inside the workspace
829: // teardown transaction.
830: //
831: // The teardown waits on three kinds of lock: the workspace row (FOR UPDATE),
832: // every chat_session row in the workspace (FOR UPDATE), and the global
833: // advisory lock 4246 that serialises it against the task_usage_hourly rollup.
834: // The advisory lock is the dangerous one — it is global and batch-held. A
835: // rollup tick may hold it for as long as its 25 min scheduler RunTimeout, the
836: // backfill commands (cmd/backfill_task_usage_hourly, cmd/backfill_codex_usage_cache)
837: // hold it for an entire run, and before migration 272 a tick whose query was
838: // cancelled leaked it for the remaining life of its pooled connection.
839: //
840: // Waiting on that lock without a cap is what the user sees as "delete does
841: // nothing": the request never returns, and no layer above it times out — the
842: // browser/Electron fetch in packages/core/api/client.ts has no deadline and
843: // the delete dialog stays in its "Deleting…" state forever (MUL-5983). A
844: // bounded wait turns the same contention into a retryable error.
845: //
846: // 10 s is far above the millisecond-scale waits an uncontended teardown sees,
847: // and short enough to fail while the user is still watching the dialog.
848: const workspaceDeleteLockTimeout = 10 * time.Second
849: 
850: // workspaceDeleteLockTimeoutOverride, when non-zero, replaces
```

### server/go/internal/handler/workspace_revoke.go

```text
1: package handler
2: 
3: import (
4: 	"context"
5: 	"log/slog"
6: 	"slices"
7: 
8: 	"github.com/google/uuid"
9: 	"github.com/jackc/pgx/v5/pgtype"
10: 	"workpal.local/workpal/server/go/internal/service"
11: 	db "workpal.local/workpal/server/go/pkg/db/generated"
12: 	"workpal.local/workpal/server/go/pkg/protocol"
13: )
14: 
15: // revokeAndRemoveMember converges all server-side state that should follow a
16: // member leaving a workspace: every runtime they own becomes unusable, every
17: // agent pinned to one of those runtimes is archived, every in-flight task on
18: // those runtimes is cancelled (cancelled rather than failed so the daemon's
19: // per-task status poller interrupts the running agent gracefully), the
20: // member's durable subscriptions and daemon_token rows are deleted, and
21: // finally the member row itself is removed.
22: //
23: // All DB writes run inside a single transaction so a partial revocation never
24: // leaves the workspace half-converged — e.g. a member who is "gone" but whose
25: // runtime row is still active. Once the transaction commits, daemon_token
26: // cache entries are invalidated and events are published (see
27: // publishRevocation) so connected clients and other workspace members observe
28: // the new state immediately.
29: //
30: // Note on scope: this revokes every runtime whose owner_id matches userID,
31: // regardless of how the daemon authenticates. Today most daemons fall back to
32: // PAT/JWT and `daemon_token` rows are unused in production; deleting them is
33: // a no-op for those daemons but takes effect once the mdt_ flow is live.
34: // Either way the agent-archive + task-cancel + force-offline writes are the
35: // actual production safety net: even if the daemon races back online with a
36: // still-valid PAT, it finds no agent it can run for, no queued task to claim,
37: // and the dispatcher (which gates on agent.archived_at IS NULL) won't hand it
38: // new work — and the member-row deletion in the same tx means subsequent
39: // requireWorkspaceMember checks will reject the daemon's PAT-authenticated
40: // requests with 404.
41: //
42: // archivedBy is the actor who triggered the revocation. For DeleteMember it's
43: // the requester (the admin doing the kick); for LeaveWorkspace it's the leaver
44: // themselves.
45: func (h *Handler) revokeAndRemoveMember(ctx context.Context, workspaceID, userID, memberID, archivedBy pgtype.UUID) (revocationResult, error) {
46: 	var empty revocationResult
47: 
48: 	tx, err := h.TxStarter.Begin(ctx)
49: 	if err != nil {
50: 		return empty, err
51: 	}
52: 	defer tx.Rollback(ctx)
53: 
54: 	qtx := h.Queries.WithTx(tx)
55: 
56: 	// Taken FIRST, before this tx touches member or issue_subscriber. The
57: 	// delegated auto-subscribe rule takes the same (workspace, user) lock, so
58: 	// a run that is mid-decomposition cannot slip a new subscriber row in
59: 	// between this tx's membership delete and its subscription cleanup below.
60: 	// First also means every holder acquires it in the same order, so these
61: 	// paths cannot deadlock against each other (MUL-5483 review round 7).
62: 	if err := qtx.LockSubscriberWrites(ctx, db.LockSubscriberWritesParams{
63: 		WorkspaceID: workspaceID,
64: 		UserID:      userID,
65: 	}); err != nil {
66: 		return empty, err
67: 	}
68: 
69: 	if _, err := qtx.LockRuntimeShareMemberRemoval(ctx, db.LockRuntimeShareMemberRemovalParams{
70: 		WorkspaceID: workspaceID, UserID: userID,
71: 	}); err != nil {
72: 		return empty, err
73: 	}
74: 
75: 	runtimes, err := qtx.ListAgentRuntimesByOwner(ctx, db.ListAgentRuntimesByOwnerParams{
76: 		WorkspaceID: workspaceID,
77: 		OwnerID:     userID,
78: 	})
79: 	if err != nil {
80: 		return empty, err
81: 	}
82: 
83: 	result := revocationResult{Runtimes: runtimes}
84: 
85: 	if len(runtimes) > 0 {
86: 		runtimeIDs := make([]pgtype.UUID, len(runtimes))
87: 		daemonIDs := make([]string, 0, len(runtimes))
88: 		for i, rt := range runtimes {
89: 			runtimeIDs[i] = rt.ID
90: 			if rt.DaemonID.Valid && rt.DaemonID.String != "" {
91: 				daemonIDs = append(daemonIDs, rt.DaemonID.String)
92: 			}
93: 		}
94: 
95: 		result.ArchivedAgents, err = qtx.ArchiveAgentsByRuntime(ctx, db.ArchiveAgentsByRuntimeParams{
96: 			ArchivedBy: archivedBy,
97: 			RuntimeIds: runtimeIDs,
98: 		})
99: 		if err != nil {
100: 			return empty, err
101: 		}
102: 
103: 		// Cancel by runtime AND by archived agent. agent.runtime_id can be
104: 		// reassigned via UpdateAgent without rewriting the runtime_id on
105: 		// historical agent_task_queue rows, so an archived agent may still
106: 		// have queued/running tasks pinned to a different runtime — and
107: 		// ClaimAgentTask does not gate on agent.archived_at, so those tasks
108: 		// would otherwise stay claimable after the agent is gone.
109: 		archivedAgentIDs := make([]pgtype.UUID, len(result.ArchivedAgents))
110: 		for i, a := range result.ArchivedAgents {
111: 			archivedAgentIDs[i] = a.ID
112: 		}
113: 		result.CancelledTasks, err = qtx.CancelAgentTasksByRuntimeOrAgent(ctx, db.CancelAgentTasksByRuntimeOrAgentParams{
114: 			RuntimeIds: runtimeIDs,
115: 			AgentIds:   archivedAgentIDs,
116: 		})
117: 		if err != nil {
118: 			return empty, err
119: 		}
120: 		cancelledIDs := make([]pgtype.UUID, 0, len(result.CancelledTasks))
121: 		for _, task := range result.CancelledTasks {
122: 			cancelledIDs = append(cancelledIDs, task.ID)
123: 		}
124: 		if err = qtx.WithdrawChatTaskSupplementsByTasks(ctx, cancelledIDs); err != nil {
125: 			return empty, err
126: 		}
127: 		if err = service.SettleTerminalTaskState(ctx, qtx, result.CancelledTasks...); err != nil {
128: 			return empty, err
129: 		}
130: 
131: 		result.OfflineRuntimeIDs, err = qtx.ForceOfflineRuntimesByIDs(ctx, runtimeIDs)
132: 		if err != nil {
133: 			return empty, err
134: 		}
135: 
136: 		if len(daemonIDs) > 0 {
137: 			result.RevokedTokenHashes, err = qtx.DeleteDaemonTokensByWorkspaceAndDaemons(ctx, db.DeleteDaemonTokensByWorkspaceAndDaemonsParams{
138: 				WorkspaceID: workspaceID,
139: 				DaemonIds:   daemonIDs,
140: 			})
141: 			if err != nil {
142: 				return empty, err
143: 			}
144: 		}
145: 	}
146: 
147: 	// channel_user_binding used to carry a member FK with ON DELETE CASCADE, so
148: 	// a removed member's IM bindings vanished automatically. MUL-3515 §4 dropped
149: 	// every channel_* foreign key, moving that integrity rule to the application
150: 	// layer: prune the bindings here, in the same tx as the member-row delete.
151: 	// The inbound path also re-checks membership (see ChannelStore.IsWorkspaceMember),
152: 	// but pruning stops a stale binding from lingering across a remove/re-add.
153: 	if err := qtx.DeleteChannelUserBindingsByWorkspaceMember(ctx, db.DeleteChannelUserBindingsByWorkspaceMemberParams{
154: 		WorkspaceID:   workspaceID,
155: 		WorkpalUserID: userID,
156: 	}); err != nil {
157: 		return empty, err
158: 	}
159: 
160: 	// agent_invocation_target carries member-target grants with NO database FK
161: 	// (MUL-3963 keeps the new table FK-free, matching the MUL-3515 channel
162: 	// generalization). Prune this leaving member's grants in the same tx as the
163: 	// member-row delete so a re-invited user does not silently reclaim old
164: 	// invocation permission on agents that had allow-listed them. SCOPED to
165: 	// this workspace: the same user may belong to other workspaces, and
166: 	// removing them here must not touch their grants on agents elsewhere.
167: 	if err := qtx.DeleteAgentInvocationTargetsByMember(ctx, db.DeleteAgentInvocationTargetsByMemberParams{
168: 		WorkspaceID: workspaceID,
169: 		TargetID:    userID,
170: 	}); err != nil {
171: 		return empty, err
172: 	}
173: 
174: 	// A private quick action is visible and runnable ONLY by its creator
175: 	// (quick_action carries no FK, so nothing removes it implicitly). Once the
176: 	// creator is gone the row is unreachable by every remaining member while
177: 	// still consuming the workspace's active-action limit, so drop those in
178: 	// the same tx. Public actions are workspace furniture and survive.
179: 	if err := qtx.DeletePrivateQuickActionsByCreator(ctx, db.DeletePrivateQuickActionsByCreatorParams{
180: 		WorkspaceID: workspaceID,
181: 		CreatedByID: userID,
182: 	}); err != nil {
183: 		return empty, err
184: 	}
185: 
186: 	// Saved views follow the private-quick-action rule above: a departed
187: 	// member's PRIVATE views are invisible to everyone left yet still count
188: 	// against quota, and a re-invite must not resurrect them. Shared views
189: 	// stay — they are workspace furniture other members may rely on. The
190: 	// per-user view-bar preferences are meaningless without the member.
191: 	if err := qtx.DeletePrivateIssueViewsByOwner(ctx, db.DeletePrivateIssueViewsByOwnerParams{
192: 		WorkspaceID: workspaceID,
193: 		OwnerID:     userID,
194: 	}); err != nil {
195: 		return empty, err
196: 	}
197: 	if err := qtx.DeleteIssueViewPreferencesByUser(ctx, db.DeleteIssueViewPreferencesByUserParams{
198: 		WorkspaceID: workspaceID,
199: 		UserID:      userID,
200: 	}); err != nil {
201: 		return empty, err
202: 	}
203: 
204: 	// issue_subscriber carries no FK either (same MUL-3515 rule as the two
205: 	// prunes above), and MUL-5483 gave agents a path that writes member
206: 	// subscriber rows on their own initiative. Dropping them in this tx is what
207: 	// stops a departed member from accruing inbox rows, and stops a re-invite
208: 	// from silently restoring visibility of everything they used to watch.
209: 	if err := qtx.DeleteSubscriptionsByMember(ctx, db.DeleteSubscriptionsByMemberParams{
210: 		WorkspaceID: workspaceID,
211: 		UserID:      userID,
212: 	}); err != nil {
213: 		return empty, err
214: 	}
215: 
216: 	// autopilot_subscriber is another FK-free subscription template. Leaving
217: 	// stale rows here made the detail API return a user the member picker could
218: 	// no longer render; the next full-replace PATCH then failed membership
219: 	// validation, blocking every edit to that autopilot. Prune only templates in
220: 	// this workspace so the same user's subscriptions elsewhere survive.
221: 	if err := qtx.DeleteAutopilotSubscribersByMember(ctx, db.DeleteAutopilotSubscribersByMemberParams{
222: 		WorkspaceID: workspaceID,
223: 		UserID:      userID,
224: 	}); err != nil {
225: 		return empty, err
226: 	}
227: 
228: 	// App requests waiting on the member would otherwise let a later OAuth
229: 	// connect, or a stale tab, resume an agent in a workspace they left.
230: 	if _, err := qtx.CancelPendingAppActionRequestsForApprover(ctx, db.CancelPendingAppActionRequestsForApproverParams{
231: 		WorkspaceID: workspaceID, ApproverUserID: userID,
232: 	}); err != nil {
233: 		return empty, err
234: 	}
235: 
236: 	// Member row deletion lives inside the same tx so a successful revoke is
237: 	// never followed by a failed member-delete (which would leave the user
238: 	// still a member with a dead runtime), and a failed revoke never leaves
239: 	// the user out of the workspace with a still-online runtime.
240: 	if h.seatCapacityEnabled() {
241: 		if err := enqueueMemberCapacityRelease(ctx, qtx, uuid.UUID(workspaceID.Bytes), uuid.UUID(memberID.Bytes)); err != nil {
242: 			return empty, err
243: 		}
244: 	}
245: 	sharedRuntimes, err := qtx.ListSharedAgentRuntimesForUpdate(ctx, db.ListSharedAgentRuntimesForUpdateParams{
246: 		WorkspaceID: workspaceID, UserID: userID,
247: 	})
248: 	if err != nil {
249: 		return empty, err
250: 	}
251: 	result.SharedRuntimeCount = len(sharedRuntimes)
252: 	for _, rt := range sharedRuntimes {
253: 		rt.SharedWith = slices.DeleteFunc(rt.SharedWith, func(id pgtype.UUID) bool { return id == userID })
254: 		if rt.Visibility == "public" {
255: 			if _, err := qtx.UpdateAgentRuntimeVisibility(ctx, db.UpdateAgentRuntimeVisibilityParams{
256: 				ID: rt.ID, Visibility: rt.Visibility, SharedWith: rt.SharedWith,
257: 			}); err != nil {
258: 				return empty, err
259: 			}
260: 			continue
261: 		}
262: 		if _, err := lockRuntimeRevocationPlan(ctx, qtx, rt); err != nil {
263: 			return empty, err
264: 		}
265: 		_, teardown, readyChats, err := applyRuntimeAccessRevocation(ctx, qtx, rt)
266: 		if err != nil {
267: 			return empty, err
268: 		}
269: 		result.SharedTeardown.UnboundAgents = append(result.SharedTeardown.UnboundAgents, teardown.UnboundAgents...)
270: 		result.SharedTeardown.CancelledTasks = append(result.SharedTeardown.CancelledTasks, teardown.CancelledTasks...)
271: 		result.SharedTeardown.PausedAutopilots = append(result.SharedTeardown.PausedAutopilots, teardown.PausedAutopilots...)
272: 		result.ReadyChats = append(result.ReadyChats, readyChats...)
273: 	}
274: 
275: 	// No FK cascade (repo rule): a departing member leaves every private
276: 	// project in the workspace and stops watching every project.
277: 	if err := qtx.DeleteProjectMembersByUser(ctx, db.DeleteProjectMembersByUserParams{
278: 		WorkspaceID: workspaceID, UserID: userID,
279: 	}); err != nil {
280: 		return empty, err
281: 	}
282: 	if err := qtx.DeleteProjectSubscribersByUser(ctx, db.DeleteProjectSubscribersByUserParams{
283: 		WorkspaceID: workspaceID, UserID: userID,
284: 	}); err != nil {
285: 		return empty, err
286: 	}
287: 	if err := qtx.DeleteMember(ctx, memberID); err != nil {
288: 		return empty, err
289: 	}
290: 
291: 	if err := tx.Commit(ctx); err != nil {
292: 		return empty, err
293: 	}
294: 
295: 	return result, nil
296: }
297: 
298: // revocationResult captures everything revokeMemberRuntimes touched so the
299: // caller can fan out events and analytics after the transaction commits.
300: // Publishing inside the transaction would let subscribers observe a state the
301: // tx might still roll back (see TaskService.BroadcastCancelledTasks docstring).
302: type revocationResult struct {
303: 	Runtimes           []db.AgentRuntime
304: 	ArchivedAgents     []db.Agent
305: 	CancelledTasks     []db.AgentTaskQueue
306: 	OfflineRuntimeIDs  []db.ForceOfflineRuntimesByIDsRow
307: 	RevokedTokenHashes []string
308: 	SharedRuntimeCount int
309: 	SharedTeardown     service.RuntimeTeardownResult
310: 	ReadyChats         []pgtype.UUID
311: }
312: 
313: func (r revocationResult) isEmpty() bool {
314: 	return len(r.Runtimes) == 0 && r.SharedRuntimeCount == 0
315: }
316: 
317: // publishRevocation runs all post-commit side effects: invalidate daemon token
318: // cache, broadcast task:cancelled with per-agent reconciliation, broadcast
319: // agent:archived, and signal a runtime-list refresh. Safe to call on an empty
320: // result — it returns immediately.
321: func (h *Handler) publishRevocation(ctx context.Context, result revocationResult, workspaceIDStr, actorType, actorIDStr string) {
322: 	if result.isEmpty() {
323: 		return
324: 	}
325: 
326: 	for _, hash := range result.RevokedTokenHashes {
327: 		h.DaemonTokenCache.Invalidate(ctx, hash)
328: 	}
329: 
330: 	// Per-task cancellation: TaskService handles status reconciliation and
331: 	// per-task event broadcast. Run this before the agent:archived burst so
332: 	// subscribers see "task cancelled" before the parent agent disappears
333: 	// from active lists, matching the order ArchiveAgent uses.
334: 	if h.TaskService != nil && len(result.CancelledTasks) > 0 {
335: 		// Revocation only archives agents, so a per-task lookup would still
336: 		// resolve here; the workspace is passed for the same reason as
337: 		// everywhere else — it is known, and it is the one being revoked.
338: 		h.TaskService.BroadcastCancelledTasks(ctx, workspaceIDStr, result.CancelledTasks)
339: 	}
340: 
341: 	for _, agent := range result.ArchivedAgents {
342: 		h.publish(protocol.EventAgentArchived, workspaceIDStr, actorType, actorIDStr, map[string]any{
343: 			"agent": h.agentToResponse(agent),
344: 		})
345: 	}
346: 
347: 	h.PublishRuntimeTeardown(ctx, result.SharedTeardown, workspaceIDStr, actorType, actorIDStr, "revoke", false)
348: 	if h.TaskService != nil {
349: 		for _, taskID := range result.ReadyChats {
350: 			h.TaskService.FinalizeDeferredCancelledChat(ctx, taskID)
351: 		}
352: 	}
353: 
354: 	// Tell connected clients to refresh the runtime list. We piggyback on
355: 	// EventDaemonRegister with a "revoke" action — same channel the runtime
356: 	// delete handler uses — so the frontend invalidates its cached list
357: 	// without us having to introduce a new event type the desktop app would
358: 	// need a build to learn about.
359: 	if len(result.OfflineRuntimeIDs) > 0 || result.SharedRuntimeCount > 0 {
360: 		h.publish(protocol.EventDaemonRegister, workspaceIDStr, actorType, actorIDStr, map[string]any{
361: 			"action": "revoke",
362: 		})
363: 	}
364: }
365: 
366: // logRevocation emits a structured info line summarising the revocation. Kept
367: // separate from publish so the log is identical whether or not the bus is wired.
368: func logRevocation(result revocationResult, workspaceID, userID string, attrs ...any) {
369: 	if result.isEmpty() {
370: 		return
371: 	}
372: 	base := []any{
373: 		"workspace_id", workspaceID,
374: 		"user_id", userID,
375: 		"runtimes_revoked", len(result.Runtimes),
376: 		"agents_archived", len(result.ArchivedAgents),
377: 		"tasks_cancelled", len(result.CancelledTasks),
378: 		"runtimes_taken_offline", len(result.OfflineRuntimeIDs),
379: 		"daemon_tokens_revoked", len(result.RevokedTokenHashes),
380: 	}
381: 	slog.Info("member runtimes revoked", append(base, attrs...)...)
382: }
```

### server/go/internal/handler/runtime_sharing.go

```text
1: package handler
2: 
3: import (
4: 	"context"
5: 	"errors"
6: 	"fmt"
7: 	"net/http"
8: 	"slices"
9: 	"sort"
10: 
11: 	"github.com/jackc/pgx/v5/pgtype"
12: 	"workpal.local/workpal/server/go/internal/service"
13: 	db "workpal.local/workpal/server/go/pkg/db/generated"
14: 	"workpal.local/workpal/server/go/pkg/taskfailure"
15: )
16: 
17: var errRuntimeManagedByConnection = errors.New("runtime managed by connection")
18: 
19: var errInvalidRuntimeShare = errors.New("invalid runtime sharing")
20: 
21: func parseRuntimeSharedWith(w http.ResponseWriter, raw []string) ([]pgtype.UUID, bool) {
22: 	if len(raw) > 1000 {
23: 		writeError(w, http.StatusBadRequest, "shared_with has too many members")
24: 		return nil, false
25: 	}
26: 	ids := make([]pgtype.UUID, 0, len(raw))
27: 	for _, value := range raw {
28: 		id, ok := parseUUIDOrBadRequest(w, value, "shared_with")
29: 		if !ok {
30: 			return nil, false
31: 		}
32: 		ids = append(ids, id)
33: 	}
34: 	return ids, true
35: }
36: 
37: func runtimeAccessNarrows(previous, next db.AgentRuntime) bool {
38: 	if next.Visibility == "public" {
39: 		return false
40: 	}
41: 	if previous.Visibility == "public" {
42: 		return true
43: 	}
44: 	for _, id := range previous.SharedWith {
45: 		if id != next.OwnerID && !slices.Contains(next.SharedWith, id) {
46: 			return true
47: 		}
48: 	}
49: 	return false
50: }
51: 
52: func runtimeSharedWithStrings(ids []pgtype.UUID) []string {
53: 	result := make([]string, len(ids))
54: 	for i, id := range ids {
55: 		result[i] = uuidToString(id)
56: 	}
57: 	return result
58: }
59: 
60: func sameRuntimeAccess(a, b db.AgentRuntime) bool {
61: 	return a.Visibility == b.Visibility && slices.Equal(a.SharedWith, b.SharedWith)
62: }
63: 
64: // Resolve PATCH fields from the locked row. Explicit private/public requests
65: // without a recipient list clear grants, preserving old clients' privacy action.
66: func resolveRuntimeAccess(ctx context.Context, q *db.Queries, rt db.AgentRuntime, req UpdateAgentRuntimeRequest) (db.AgentRuntime, error) {
67: 	next := rt
68: 	if req.Visibility != nil {
69: 		next.Visibility = *req.Visibility
70: 		next.SharedWith = []pgtype.UUID{}
71: 	}
72: 	if req.SharedWith != nil {
73: 		next.SharedWith = []pgtype.UUID{}
74: 		for _, id := range req.sharedWithIDs {
75: 			if id == rt.OwnerID || slices.Contains(next.SharedWith, id) {
76: 				continue
77: 			}
78: 			next.SharedWith = append(next.SharedWith, id)
79: 		}
80: 		sort.Slice(next.SharedWith, func(i, j int) bool { return uuidToString(next.SharedWith[i]) < uuidToString(next.SharedWith[j]) })
81: 	}
82: 	if next.Visibility == "public" && len(next.SharedWith) > 0 {
83: 		return next, fmt.Errorf("%w: shared_with requires private visibility", errInvalidRuntimeShare)
84: 	}
85: 	if len(next.SharedWith) > 0 {
86: 		members, err := q.LockRuntimeShareMembers(ctx, db.LockRuntimeShareMembersParams{WorkspaceID: rt.WorkspaceID, UserIds: next.SharedWith})
87: 		if err != nil {
88: 			return next, err
89: 		}
90: 		if len(members) != len(next.SharedWith) {
91: 			return next, fmt.Errorf("%w: every recipient must be a workspace member", errInvalidRuntimeShare)
92: 		}
93: 	}
94: 	return next, nil
95: }
96: 
97: // Both explicit access changes and workspace departure use the same lock order
98: // and cancellation settlement, inside their caller's transaction.
99: func lockRuntimeRevocationPlan(ctx context.Context, qtx *db.Queries, next db.AgentRuntime) (runtimeWorkspaceAccessRevocationPlan, error) {
100: 	agents, err := qtx.ListNonOwnerAgentsByRuntimeForUpdate(ctx, db.ListNonOwnerAgentsByRuntimeForUpdateParams{
101: 		RuntimeID: next.ID, RuntimeOwnerID: next.OwnerID, SharedWith: next.SharedWith,
102: 	})
103: 	if err != nil {
104: 		return runtimeWorkspaceAccessRevocationPlan{}, err
105: 	}
106: 	if _, err := qtx.LockRuntimeRevocationChatSessions(ctx, db.LockRuntimeRevocationChatSessionsParams{
107: 		RuntimeID: next.ID, RuntimeOwnerID: next.OwnerID, SharedWith: next.SharedWith,
108: 	}); err != nil {
109: 		return runtimeWorkspaceAccessRevocationPlan{}, err
110: 	}
111: 	tasks, err := qtx.ListNonOwnerActiveTasksByRuntimeForUpdate(ctx, db.ListNonOwnerActiveTasksByRuntimeForUpdateParams{
112: 		RuntimeID: next.ID, RuntimeOwnerID: next.OwnerID, SharedWith: next.SharedWith,
113: 	})
114: 	return runtimeWorkspaceAccessRevocationPlan{Agents: agents, Tasks: tasks}, err
115: }
116: 
117: func applyRuntimeAccessRevocation(ctx context.Context, qtx *db.Queries, next db.AgentRuntime) (db.AgentRuntime, service.RuntimeTeardownResult, []pgtype.UUID, error) {
118: 	var result service.RuntimeTeardownResult
119: 	updated, err := qtx.UpdateAgentRuntimeVisibility(ctx, db.UpdateAgentRuntimeVisibilityParams{
120: 		ID: next.ID, Visibility: next.Visibility, SharedWith: next.SharedWith,
121: 	})
122: 	if err != nil {
123: 		return updated, result, nil, err
124: 	}
125: 	result.CancelledTasks, err = qtx.CancelNonOwnerTasksByRuntime(ctx, db.CancelNonOwnerTasksByRuntimeParams{
126: 		RuntimeID: next.ID, RuntimeOwnerID: next.OwnerID, SharedWith: next.SharedWith,
127: 		FailureReason: string(taskfailure.ReasonRuntimeAccessRevoked),
128: 	})
129: 	if err != nil {
130: 		return updated, result, nil, err
131: 	}
132: 	readyChats, err := service.PrepareRuntimeAccessCancellation(ctx, qtx, result.CancelledTasks)
133: 	if err != nil {
134: 		return updated, result, nil, err
135: 	}
136: 	result.UnboundAgents, err = qtx.UnbindNonOwnerAgentsFromRuntime(ctx, db.UnbindNonOwnerAgentsFromRuntimeParams{
137: 		RuntimeID: next.ID, RuntimeOwnerID: next.OwnerID, SharedWith: next.SharedWith,
138: 	})
139: 	if err != nil {
140: 		return updated, result, nil, err
141: 	}
142: 	ids := make([]pgtype.UUID, len(result.UnboundAgents))
143: 	for i, a := range result.UnboundAgents {
144: 		ids[i] = a.ID
145: 	}
146: 	result.PausedAutopilots, err = qtx.PauseAutopilotsByUnboundAgents(ctx, ids)
147: 	return updated, result, readyChats, err
148: }
```

### server/go/internal/handler/runtime.go

```text
1299: func (h *Handler) PublishRuntimeTeardown(ctx context.Context, res service.RuntimeTeardownResult, wsID, actorType, actorID, action string, publishRuntimeRefresh bool) {
1300: 	if h.TaskService != nil && len(res.CancelledTasks) > 0 {
1301: 		// The teardown deletes the runtime's system agents, and a system agent's
1302: 		// chat sessions go with it, so the workspace of a cancelled chat task is
1303: 		// no longer resolvable from the task row. It is this workspace.
1304: 		h.TaskService.BroadcastCancelledTasks(ctx, wsID, res.CancelledTasks)
1305: 	}
1306: 	for _, a := range res.UnboundAgents {
1307: 		// agent:status is the generic "this agent changed" broadcast the agent
1308: 		// update path already uses; subscribers refresh the row and see
1309: 		// runtime_bound=false. No agent:archived here — nothing was archived.
1310: 		h.publish(protocol.EventAgentStatus, wsID, actorType, actorID, map[string]any{
1311: 			"agent": broadcastAgentResponse(h.agentToResponse(a)),
1312: 		})
1313: 	}
1314: 	for _, a := range res.PausedAutopilots {
1315: 		h.publish(protocol.EventAutopilotUpdated, wsID, actorType, actorID, map[string]any{
1316: 			"autopilot": autopilotToResponse(a, nil),
1317: 		})
1318: 	}
1319: 	if publishRuntimeRefresh {
1320: 		h.PublishRuntimeRefresh(wsID, actorType, actorID, action)
1321: 	}
1322: }
1323: 
1324: // PublishRuntimeRefresh asks connected clients to refetch runtime state.
1325: func (h *Handler) PublishRuntimeRefresh(wsID, actorType, actorID, action string) {
1326: 	h.publish(protocol.EventDaemonRegister, wsID, actorType, actorID, map[string]any{"action": action})
1327: }
1328: 
1329: func (h *Handler) publishRuntimeTeardown(ctx context.Context, res service.RuntimeTeardownResult, wsID, userID string) {
1330: 	h.PublishRuntimeTeardown(ctx, res, wsID, "member", userID, "delete", true)
1331: }
1332: 
```

### server/go/pkg/db/queries/member.sql

```text
1: -- name: ListMembers :many
2: SELECT * FROM member
3: WHERE workspace_id = $1
4: ORDER BY created_at ASC;
5: 
6: -- name: ListWorkspaceManagerUserIDs :many
7: SELECT user_id FROM member
8: WHERE workspace_id = $1 AND role IN ('owner', 'admin')
9: ORDER BY created_at ASC;
10: 
11: -- name: GetMember :one
12: SELECT * FROM member
13: WHERE id = $1;
14: 
15: -- name: GetMemberByUserAndWorkspace :one
16: SELECT * FROM member
17: WHERE user_id = $1 AND workspace_id = $2;
18: 
19: -- name: GetRealtimeMemberships :many
20: SELECT m.user_id, m.workspace_id
21: FROM member m
22: JOIN (
23:     SELECT unnest(sqlc.arg(user_ids)::uuid[]) AS user_id,
24:            unnest(sqlc.arg(workspace_ids)::uuid[]) AS workspace_id
25: ) AS requested
26:     ON m.user_id = requested.user_id AND m.workspace_id = requested.workspace_id;
27: 
28: -- name: CreateMember :one
29: INSERT INTO member (workspace_id, user_id, role)
30: VALUES ($1, $2, $3)
31: RETURNING *;
32: 
33: -- name: UpdateMemberRole :one
34: UPDATE member SET role = $2
35: WHERE id = $1
36: RETURNING *;
37: 
38: -- name: DeleteMember :exec
39: DELETE FROM member WHERE id = $1;
40: 
41: -- name: ListMembersWithUser :many
42: SELECT m.id, m.workspace_id, m.user_id, m.role, m.created_at,
43:        u.name as user_name, u.email as user_email, u.avatar_url as user_avatar_url
44: FROM member m
45: JOIN "user" u ON u.id = m.user_id
46: WHERE m.workspace_id = $1
47: ORDER BY m.created_at ASC;
```

### server/go/internal/middleware/workspace.go

```text

```

### server/src/workpal_backend/workspaces/service.py

```text
1: """Caller owns commit/rollback. Invitations, deletion and runtime revocation pending."""
2: import re
3: from datetime import datetime, timezone
4: from uuid import uuid4
5: from sqlalchemy import select, delete, update, func
6: from sqlalchemy.exc import IntegrityError
7: from .models import workspaces, members, issue_status
8: from .repository import membership
9: from workpal_backend.infrastructure.outbox import append_event
10: 
11: class WorkspaceValidationError(ValueError): pass
12: class WorkspaceConflictError(ValueError): pass
13: class WorkspaceAccessError(PermissionError): pass
14: class WorkspaceRoleError(WorkspaceAccessError): pass
15: class UnsupportedIdentityError(WorkspaceAccessError): pass
16: class WorkspaceNotFoundError(LookupError): pass
17: 
18: RESERVED = {'lg', 'ba', 'ak', 'or', 'changelog', 'ga', 'admin', 'na', 'rw', 'vi', 'fy', 'billing', 'licensing', 'views', 'cli', 'healthz', 'ht', 'tokens', 'pt-br', 'an', 'kg', 'kl', 'az', 'ru', 'eu', 'mr', 'onboarding', 'solutions', 'ln', 'workpal', 'invite', 'mi', 'so', 'search', 'en', 'product', 'ms', 'es', 'my', 'fi', 'ro', 'security', 'www', 'health', 'sdk', 'af', 'password', 'ja', 'callback', 'pl', 'yo', 'zh-hant', 'ks', 'abuse', 'kj', 'hr', 'manifest.json', 'ng', 'ug', 'li', 'bg', 'wo', 'dingtalk', 'tg', 'wa', 'my-issues', 'pt', 'ti', 'account', 'nn', 'oc', 'ce', 'metrics', 'lv', 'xh', 'fr', 'io', 'hi', 'ch', 'nb', 'nv', 'sc', 'members', '_next', 'terms', 'lu', 'cu', 'robots.txt', 'sk', 'as', 'os', 'ps', 'bi', 'signout', 'br', 'qu', 'fj', 'mk', 'blog', 'bs', 'gv', 'hy', 'sv', 'tk', 'rn', 've', '.well-known', 'auth', 'lb', 'ha', 'docs', 'jv', 'kn', 'webhooks', 'bm', 'inbox', 'sm', 'eo', 'es-mx', 'projects', 'v1', 'ay', 'it', 'privacy', 'mh', 'pt-pt', 'sl', 'settings', 'public', 'help', 'gd', 'uk', 'en-gb', 'v2', 'ae', 'ab', 'sn', 'pi', 'dashboard', 'en-us', 'ka', 'noreply', 'verify', 'be', 'mg', 'press', 'sq', 'id', 'zh-hans', 'ws', 'ss', 'is', 'ig', 'et', 'sd', 'st', 'kv', 'signin', 'pa', 'profile', 'api', 'he', 'nl', 'oj', 'tl', 'cy', 'th', 'cdn', 'gn', 'ho', 'runtimes', 'hz', 'graphql', 'favicon.ico', 'sitemap.xml', 'tn', 'cv', 'hostmaster', 'rm', 'cs', 'ky', 'autopilots', 'sw', 'usage', 'am', 'status', 'oauth', 'issues', 'ii', 'kr', 'es-419', 'lark', 'aa', 'hu', 'om', 'vo', 'workspaces', 'la', 'customers', 'contact-sales', 'ia', 'kk', 'ping', 'mn', 'zu', 'reset', 'to', 'cr', 'invitations', 'squads', 'uz', 'lt', 'agents', 'notifications', 'logout', 'usecases', 'kw', 'teams', 'tt', 'dv', 'no', 'wecom', 'bo', 'homepage', 'ff', 'se', 'ty', 'mail', 'zh-hk', 'ie', 'uploads', 'ki', 'gu', 'webmaster', 'ku', 'te', 'tr', 'ca', 'ml', 'ta', 'zh-cn', 'nd', 'su', 'assets', 'pricing', 'fo', 'km', 'skills', 'static', 'fa', 'sg', 'careers', 'download', 'gl', 'legal', 'fr-ca', 'ftp', 'nr', 'readyz', 'signup', 'de', 'lo', 'yi', 'ne', 'ko', 'ts', 'slack', 'da', 'about', 'mt', 'ny', 'el', 'sa', 'ar', 'dz', 'iu', 'new', 'telegram', 'ik', 'si', 'tw', 'co', 'home', 'bn', 'login', 'zh', 'contact', 'postmaster', 'av', 'ee', 'sr', 'za', 'zh-tw', 'support', 'files', 'ur'}
19: STATUSES = [('backlog', 'Backlog', 'Parked. Assigning an issue here never starts an agent run.', 'unstarted', '#6b7280'), ('todo', 'Todo', 'Queued for work. Moving an issue here starts the assigned agent.', 'unstarted', '#6b7280'), ('in_progress', 'In Progress', 'Actively being worked on.', 'started', '#f59e0b'), ('in_review', 'In Review', 'Work delivered, waiting on human review. Finalizes the autopilot run.', 'started', '#22c55e'), ('done', 'Done', 'Completed.', 'done', '#3b82f6'), ('blocked', 'Blocked', 'Stalled on an external dependency.', 'started', '#ef4444'), ('cancelled', 'Cancelled', 'Decided not to do.', 'closed', '#6b7280')]
20: 
21: def response(row):
22:     return {k: row[k] for k in ('id','name','slug','description','context','settings','repos','issue_prefix','avatar_url','created_at','updated_at')}
23: 
24: def create_workspace(session, user_id, name, slug, issue_prefix=None):
25:     if not isinstance(name, str) or not isinstance(slug, str):
26:         raise WorkspaceValidationError('name and slug are required')
27:     name, slug = name.strip(), slug.strip().lower()
28:     if not name or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in RESERVED:
29:         raise WorkspaceValidationError('invalid or reserved slug, or empty name')
30:     if issue_prefix is not None and not isinstance(issue_prefix, str):
31:         raise WorkspaceValidationError('invalid issue prefix')
32:     prefix = (issue_prefix or '').strip().upper()
33:     if prefix and not re.fullmatch('[A-Z0-9]{1,10}', prefix):
34:         raise WorkspaceValidationError('invalid issue prefix')
35:     prefix = prefix or slug.replace('-', '')[:4].upper()
36:     now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
37:     wid = str(uuid4())
38:     # Ensure a real outer SQLite transaction before SAVEPOINT (legacy sqlite driver).
39:     conn = session.connection()
40:     if not conn.connection.driver_connection.in_transaction:
41:         conn.exec_driver_sql('BEGIN')
42:     try:
43:         with session.begin_nested():
44:             session.execute(workspaces.insert().values(id=wid,name=name,slug=slug,issue_prefix=prefix,created_at=now,updated_at=now))
45:             session.execute(members.insert().values(id=str(uuid4()),workspace_id=wid,user_id=user_id,role='owner',created_at=now))
46:             for key, label, description, category, color in STATUSES:
47:                 session.execute(issue_status.insert().values(id=str(uuid4()),workspace_id=wid,key=key,name=label,description=description,category=category,color=color,is_system=True,position=0,created_at=now,updated_at=now))
48:             return response(session.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one())
49:     except IntegrityError as exc:
50:         if 'workspaces.slug' in str(exc):
51:             raise WorkspaceConflictError('workspace slug already exists') from exc
52:         raise
53: 
54: def list_workspaces(session, user_id):
55:     rows = session.execute(select(workspaces, members.c.pinned_at).join(members).where(members.c.user_id == user_id).order_by(members.c.pinned_at.desc().nulls_last(),workspaces.c.created_at,workspaces.c.id)).mappings()
56:     return [dict(response(r), **({'pinned_at':r['pinned_at']} if r['pinned_at'] else {})) for r in rows]
57: 
58: def require_workspace_access(session, principal, workspace_id):
59:     def field(k):
60:         return principal.get(k) if isinstance(principal, dict) else getattr(principal,k,None)
61:     if field('identity_kind') != 'session':
62:         raise UnsupportedIdentityError('only session identities are supported')
63:     member = membership(session, field('user_id'), workspace_id)
64:     if member is None:
65:         raise WorkspaceAccessError('workspace access denied')
66:     return dict(member)
67: 
68: def get_workspace(session, principal, workspace_id):
69:     require_workspace_access(session, principal, workspace_id)
70:     return response(session.execute(select(workspaces).where(workspaces.c.id == workspace_id)).mappings().one())
71: 
72: def remove_membership(session, principal, workspace_id, member_id):
73:     # Acquire SQLite writer serialization BEFORE reading membership/owner count.
74:     # UPDATE also works inside an already active caller transaction; never commits it.
75:     session.execute(update(workspaces).where(workspaces.c.id == workspace_id).values(issue_counter=workspaces.c.issue_counter))
76:     actor = require_workspace_access(session, principal, workspace_id)
77:     target = session.execute(select(members).where(members.c.id == member_id, members.c.workspace_id == workspace_id)).mappings().one_or_none()
78:     if target is None:
79:         raise WorkspaceNotFoundError('member not found')
80:     if actor['id'] != member_id and actor['role'] not in ('owner','admin'):
81:         raise WorkspaceAccessError('workspace admin required')
82:     if target['role'] == 'owner':
83:         if actor['role'] != 'owner':
84:             raise WorkspaceAccessError('workspace owner required')
85:         count = session.scalar(select(func.count()).select_from(members).where(members.c.workspace_id == workspace_id,members.c.role == 'owner'))
86:         if count <= 1:
87:             raise WorkspaceValidationError('workspace must have at least one owner')
88:     session.execute(delete(members).where(members.c.id == member_id))
89: 
90: 
91: def update_workspace(session, principal, workspace_id, body):
92:     actor = require_workspace_access(session, principal, workspace_id)
93:     if actor['role'] not in ('owner', 'admin'):
94:         raise WorkspaceRoleError('insufficient permissions')
95:     stored = get_workspace(session, principal, workspace_id)
96:     values = {k:v for k,v in body.items() if v is not None}
97:     if 'name' in values:
98:         values['name'] = values['name'].strip()
99:         if not values['name']:
100:             raise WorkspaceValidationError('name is required')
101:     if 'issue_prefix' in values:
102:         prefix = values.pop('issue_prefix').strip().upper()
103:         if prefix and not re.fullmatch('[A-Z0-9]{1,10}', prefix):
104:             raise WorkspaceValidationError('issue prefix must be 1-10 uppercase letters or digits')
105:         if prefix:
106:             values['issue_prefix'] = prefix
107:     if 'avatar_url' in values:
108:         values['avatar_url'] = values['avatar_url'].strip()
109:     if 'repos' in values:
110:         from urllib.parse import urlsplit
111:         repos, seen = [], set()
112:         if not isinstance(values['repos'], list):
113:             raise WorkspaceValidationError('repos must be an array of repository objects')
114:         for i, item in enumerate(values['repos']):
115:             if not isinstance(item, dict) or any(item.get(k) is not None and not isinstance(item[k], str) for k in ('url','description')):
116:                 raise WorkspaceValidationError('repos must be an array of repository objects')
117:             url = (item.get('url') or '').strip()
118:             description = (item.get('description') or '').strip()
119:             if not url:
120:                 raise WorkspaceValidationError(f'repos[{i}]: url is required')
121:             try:
122:                 parsed = urlsplit(url)
123:                 valid = bool(parsed.netloc and parsed.scheme in ('http','https','ssh','git'))
124:             except ValueError:
125:                 valid = False
126:             colon, at = url.find(':'), url.find('@')
127:             valid = valid or (' ' not in url and '://' not in url and 0 < colon < len(url)-1 and at < colon and bool(url[at+1:colon]))
128:             if not valid:
129:                 raise WorkspaceValidationError(f'repos[{i}]: url must be a valid http(s) or ssh git URL')
130:             if url not in seen:
131:                 repos.append(dict(url=url, **({'description':description} if description else {})))
132:                 seen.add(url)
133:         values['repos'] = repos
134:     incoming = values.get('settings')
135:     if isinstance(incoming, dict):
136:         incoming = incoming.copy()
137:         key = 'pr_auto_complete_enabled'
138:         def legacy(s):
139:             return s.get(key) is None or s.get(key) is True
140:         old = stored['settings'] if isinstance(stored['settings'], dict) else {}
141:         if key in incoming and legacy(incoming) != legacy(old):
142:             incoming['pr_merge_status'] = 'done' if legacy(incoming) else 'none'
143:         raw = incoming.get('pr_merge_status')
144:         target = ('done' if legacy(incoming) else 'none') if raw is None else (raw.strip().lower() or 'none' if isinstance(raw,str) else 'none')
145:         if target == 'none':
146:             incoming[key] = False
147:         else:
148:             incoming.pop(key, None)
149:         values['settings'] = incoming
150:     values['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
151:     session.execute(update(workspaces).where(workspaces.c.id == workspace_id).values(**values))
152:     result = get_workspace(session, principal, workspace_id)
153:     append_event(session, dict(type="workspace:updated", workspaceID=workspace_id,
154:         actorType="member", actorID=actor["user_id"], payload={"workspace": result}))
155:     return result
156: 
157: 
158: def set_pinned(session, principal, workspace_id, pinned):
159:     actor = require_workspace_access(session, principal, workspace_id)
160:     if type(pinned) is not bool:
161:         raise WorkspaceValidationError('pinned must be a boolean')
162:     timestamp = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z') if pinned else None
163:     session.execute(update(members).where(members.c.id == actor['id']).values(pinned_at=timestamp))
164:     return {'pinned_at':timestamp}
165: 
166: 
167: def list_members(session, principal, workspace_id):
168:     from workpal_backend.auth.models import users
169:     require_workspace_access(session, principal, workspace_id)
170:     columns = [members.c[k] for k in ('id','workspace_id','user_id','role','created_at')]
171:     columns += [users.c[k] for k in ('name','email','avatar_url')]
172:     return [dict(r) for r in session.execute(select(*columns).join(users, users.c.id == members.c.user_id).where(members.c.workspace_id == workspace_id).order_by(members.c.created_at)).mappings()]
```

### server/src/workpal_backend/workspaces/routes.py

```text
1: """Workspace HTTP boundary; production mounting belongs to the application owner."""
2: from uuid import UUID
3: from fastapi import APIRouter, Depends, HTTPException, Request
4: from fastapi.responses import JSONResponse
5: from workpal_backend.auth.dependencies import Principal, require_principal
6: from workpal_backend.infrastructure.database import DatabaseBusy
7: from .schemas import CreateWorkspace, UpdateWorkspace
8: from . import service
9: 
10: router = APIRouter()
11: 
12: def creation_policy(request: Request, principal: Principal):
13:     """Explicit integration option until Settings gains creation configuration.
14: 
15:     app.state.workspace_creation_enabled (bool, default True) and
16:     workspace_creation_allowlist (user IDs, default None) are server-owned.
17:     """
18:     settings = request.app.state.settings
19:     if settings.disable_workspace_creation or not getattr(request.app.state, 'workspace_creation_enabled', True):
20:         raise HTTPException(403, 'workspace creation is disabled')
21:     emails = {email.strip().lower() for email in settings.workspace_creation_allowed_emails.split(',') if email.strip()}
22:     if emails:
23:         from workpal_backend.auth.service import get_user
24:         with request.app.state.database.transaction() as session:
25:             user = get_user(session, principal.user_id)
26:         if not user or user['email'].strip().lower() not in emails:
27:             raise HTTPException(403, 'workspace creation is restricted to selected users on this instance')
28:     allowed = getattr(request.app.state, 'workspace_creation_allowlist', None)
29:     if allowed is not None and principal.user_id not in allowed:
30:         raise HTTPException(403, 'workspace creation is not allowed')
31: 
32: def execute(request, operation):
33:     try:
34:         with request.app.state.database.transaction() as session:
35:             return operation(session)
36:     except DatabaseBusy:
37:         return JSONResponse({'error':'Database is busy; retry later','retryable':True}, status_code=503, headers={'Retry-After':'1'})
38:     except service.WorkspaceValidationError as exc:
39:         raise HTTPException(400, str(exc))
40:     except service.WorkspaceConflictError as exc:
41:         raise HTTPException(409, str(exc))
42:     except service.WorkspaceRoleError:
43:         raise HTTPException(403, 'insufficient permissions')
44:     except service.WorkspaceAccessError:
45:         raise HTTPException(404, 'workspace not found')
46: 
47: @router.get('/api/workspaces')
48: def list_workspaces(request: Request, principal: Principal = Depends(require_principal)):
49:     return execute(request, lambda session: service.list_workspaces(session, principal.user_id))
50: 
51: @router.post('/api/workspaces', status_code=201)
52: def create_workspace(body: CreateWorkspace, request: Request, principal: Principal = Depends(require_principal)):
53:     creation_policy(request, principal)
54:     return execute(request, lambda session: service.create_workspace(session, principal.user_id, body.name, body.slug, body.issue_prefix))
55: 
56: @router.get('/api/workspaces/{workspace_id}')
57: def get_workspace(workspace_id: str, request: Request, principal: Principal = Depends(require_principal)):
58:     try:
59:         workspace_id = str(UUID(workspace_id))
60:     except ValueError:
61:         raise HTTPException(400, 'invalid workspace_id')
62:     return execute(request, lambda session: service.get_workspace(session, principal, workspace_id))
63: 
64: 
65: def workspace_uuid(value):
66:     try:
67:         return str(UUID(value))
68:     except ValueError:
69:         raise HTTPException(400, 'invalid workspace id')
70: 
71: 
72: @router.put('/api/workspaces/{workspace_id}')
73: @router.patch('/api/workspaces/{workspace_id}')
74: def update_workspace(workspace_id: str, body: UpdateWorkspace, request: Request, principal: Principal = Depends(require_principal)):
75:     workspace_id = workspace_uuid(workspace_id)
76:     return execute(request, lambda session: service.update_workspace(session, principal, workspace_id, body.model_dump()))
77: 
78: 
79: @router.put('/api/workspaces/{workspace_id}/pin')
80: async def pin_workspace(workspace_id: str, request: Request, principal: Principal = Depends(require_principal)):
81:     workspace_id = workspace_uuid(workspace_id)
82:     try:
83:         body = await request.json()
84:     except ValueError:
85:         body = None
86:     pinned = body.get('pinned') if isinstance(body, dict) else None
87:     return execute(request, lambda session: service.set_pinned(session, principal, workspace_id, pinned))
88: 
89: 
90: @router.get('/api/workspaces/{workspace_id}/members')
91: def list_members(workspace_id: str, request: Request, principal: Principal = Depends(require_principal)):
92:     workspace_id = workspace_uuid(workspace_id)
93:     return execute(request, lambda session: service.list_members(session, principal, workspace_id))
```

### server/src/workpal_backend/realtime/protocol.py

```text
1: """Go hub.go wire semantics, with private subscriptions denied until implemented."""
2: from copy import deepcopy
3: from dataclasses import dataclass
4: import json
5: 
6: MAX_FRAME_BYTES = 65536
7: 
8: @dataclass(frozen=True)
9: class FrameResult:
10:     reply: dict | None = None
11:     action: tuple[str, str, str] | None = None
12:     close_code: int | None = None
13: 
14: 
15: def parse_frame(raw: str | bytes, workspace_id: str, user_id: str) -> FrameResult:
16:     """Return reply and proposed hub operation; caller authenticates identity first.
17: 
18:     Oversize means close 1009, ignored input means an empty result. Unsubscribe
19:     mirrors Go: it removes an existing room without authorizing a new audience.
20:     No room operation is performed here. Task/chat subscribe always fails closed.
21:     """
22:     if len(raw.encode('utf-8') if isinstance(raw, str) else raw) > MAX_FRAME_BYTES:
23:         return FrameResult(close_code=1009)
24:     try:
25:         frame = json.loads(raw)
26:     except (ValueError, UnicodeError):
27:         return FrameResult()
28:     if not isinstance(frame, dict) or not isinstance(frame.get('type'), str):
29:         return FrameResult()
30:     kind = frame['type']
31:     if kind == 'ping':
32:         return FrameResult(reply={'type': 'pong'})
33:     if kind not in ('subscribe', 'unsubscribe'):
34:         return FrameResult()
35:     payload = frame.get('payload')
36:     scope = payload.get('scope') if isinstance(payload, dict) else None
37:     room = payload.get('id') if isinstance(payload, dict) else None
38:     valid = isinstance(scope, str) and isinstance(room, str) and scope != '' and room != ''
39:     scope = scope if isinstance(scope, str) else ''
40:     room = room if isinstance(room, str) else ''
41:     error = None
42:     if not valid:
43:         error = 'invalid payload'
44:     elif kind == 'subscribe':
45:         if scope in ('workspace', 'user'):
46:             if room != {'workspace': workspace_id, 'user': user_id}[scope]:
47:                 error = 'forbidden'
48:         elif scope in ('task', 'chat'):
49:             error = 'forbidden'
50:         else:
51:             error = 'unknown_scope'
52:     response = {'scope': scope, 'id': room}
53:     if error:
54:         response['error'] = error
55:     return FrameResult(
56:         reply={'type': kind + ('_error' if error else '_ack'), 'payload': response},
57:         action=None if error else (kind, scope, room),
58:     )
59: 
60: 
61: class ProjectionError(ValueError):
62:     """Reject/quarantine this event; caller must never broadcast on failure."""
63: 
64: 
65: def project_event(event: dict, workspace_id: str) -> dict:
66:     """Project only a complete workspace response for the specified audience.
67: 
68:     Membership/session checks remain mandatory at the hub content-write boundary.
69:     Internal eventID is deliberately absent from browser frames.
70:     """
71:     allowed = {'eventID', 'type', 'workspaceID', 'actorID', 'actorType', 'payload'}
72:     if not isinstance(event, dict) or set(event) - allowed:
73:         raise ProjectionError('unsupported envelope fields or private audience hints')
74:     if event.get('type') in ('invitation:accepted', 'invitation:declined', 'member:added'):
75:         return project_conclusion(event, workspace_id)
76:     if event.get('type') in ('invitation:created', 'invitation:revoked'):
77:         return project_invitation(event, workspace_id)
78:     if event.get('type') != 'workspace:updated':
79:         raise ProjectionError('unsupported event type')
80:     if not workspace_id or event.get('workspaceID') != workspace_id:
81:         raise ProjectionError('foreign workspace')
82:     if any(not isinstance(event.get(k), str) for k in ('actorID', 'actorType')):
83:         raise ProjectionError('invalid actor metadata')
84:     payload = event.get('payload')
85:     if not isinstance(payload, dict) or set(payload) != {'workspace'}:
86:         raise ProjectionError('invalid workspace payload')
87:     ws = payload['workspace']
88:     strings = {'id', 'name', 'slug', 'issue_prefix', 'created_at', 'updated_at'}
89:     nullable = {'description', 'context', 'avatar_url'}
90:     required = strings | nullable | {'settings', 'repos'}
91:     if not isinstance(ws, dict) or not required <= set(ws) or set(ws) - required - {'pinned_at'}:
92:         raise ProjectionError('incomplete or unknown workspace fields')
93:     if ws['id'] != workspace_id or any(not isinstance(ws[k], str) for k in strings):
94:         raise ProjectionError('invalid workspace identity or strings')
95:     if any(ws.get(k) is not None and not isinstance(ws[k], str) for k in nullable | {'pinned_at'}):
96:         raise ProjectionError('invalid nullable workspace strings')
97:     try:
98:         json.dumps(payload, allow_nan=False)
99:     except (TypeError, ValueError) as exc:
100:         raise ProjectionError('non JSON workspace response') from exc
101:     return {'type': 'workspace:updated', 'payload': deepcopy(payload),
102:             'actor_id': event['actorID'], 'actor_type': event['actorType']}
103: 
104: 
105: def project_invitation(event, workspace_id):
106:     if not isinstance(workspace_id, str) or not workspace_id or event.get('workspaceID') != workspace_id:
107:         raise ProjectionError('foreign workspace')
108:     if any(not isinstance(event.get(k), str) for k in ('actorID', 'actorType')):
109:         raise ProjectionError('invalid actor metadata')
110:     payload = event.get('payload')
111:     if not isinstance(payload, dict):
112:         raise ProjectionError('invalid invitation payload')
113:     if event['type'] == 'invitation:created':
114:         if ('invitation' not in payload or set(payload) - {'invitation', 'workspace_name'}
115:                 or not isinstance(payload['invitation'], dict)):
116:             raise ProjectionError('invalid invitation payload')
117:         if 'workspace_name' in payload and not isinstance(payload['workspace_name'], str):
118:             raise ProjectionError('invalid invitation workspace name')
119:         row = payload['invitation']
120:         strings = {'id', 'workspace_id', 'inviter_id', 'invitee_email', 'role', 'status', 'created_at', 'updated_at', 'expires_at'}
121:         optional = {'inviter_name', 'inviter_email', 'workspace_name'}
122:         if not strings | {'invitee_user_id'} <= set(row) or set(row) - strings - optional - {'invitee_user_id'}:
123:             raise ProjectionError('incomplete or unknown invitation fields')
124:         if row['workspace_id'] != workspace_id or row['role'] not in ('admin', 'member') or row['status'] != 'pending':
125:             raise ProjectionError('invalid invitation identity or state')
126:     else:
127:         row = payload
128:         strings = {'invitation_id', 'invitee_email'}
129:         optional = set()
130:         if set(row) != strings | {'invitee_user_id'}:
131:             raise ProjectionError('incomplete or unknown revocation fields')
132:     if any(not isinstance(row[k], str) or not row[k] for k in strings | (optional & set(row))):
133:         raise ProjectionError('invalid invitation strings')
134:     recipient = row['invitee_user_id']
135:     if recipient is not None and (not isinstance(recipient, str) or not recipient):
136:         raise ProjectionError('invalid invitation recipient')
137:     return dict(type=event['type'], payload=deepcopy(payload), actor_id=event['actorID'], actor_type=event['actorType'])
138: 
139: 
140: def resolve_audience(event):
141:     """Validate before resolving an explicit workspace or personal user room.
142: 
143:     A null invitee intentionally has no audience; never fall back to workspace.
144:     """
145:     project_event(event, event.get('workspaceID'))
146:     if event['type'] in ('invitation:accepted', 'invitation:declined', 'member:added'):
147:         recipient = event['payload']['member']['user_id'] if event['type'] == 'member:added' else event['actorID']
148:         return frozenset({('workspace', event['workspaceID'])} | ({('user', recipient)} if recipient else set()))
149:     if event['type'] == 'workspace:updated':
150:         return ('workspace', event['workspaceID'])
151:     row = event['payload']['invitation'] if event['type'] == 'invitation:created' else event['payload']
152:     recipient = row['invitee_user_id']
153:     return ('user', recipient) if recipient is not None else None
154: 
155: 
156: def project_conclusion(event, workspace_id):
157:     if not isinstance(workspace_id, str) or not workspace_id or event.get('workspaceID') != workspace_id:
158:         raise ProjectionError('foreign workspace')
159:     if any(not isinstance(event.get(k), str) for k in ('actorID', 'actorType')):
160:         raise ProjectionError('invalid actor metadata')
161:     payload = event.get('payload')
162:     kind = event['type']
163:     required = {'invitation_id', 'invitee_email'} if kind == 'invitation:declined' else ({'member'} if kind == 'member:added' else {'invitation_id', 'member'})
164:     optional = {'workspace_name'} if kind == 'member:added' else set()
165:     if not isinstance(payload, dict) or not required <= set(payload) or set(payload) - required - optional:
166:         raise ProjectionError('invalid conclusion payload')
167:     for key in (required - {'member'}) | (optional & set(payload)):
168:         if not isinstance(payload[key], str):
169:             raise ProjectionError('invalid conclusion string')
170:     if 'member' in payload:
171:         member = payload['member']
172:         strings = {'id', 'workspace_id', 'user_id', 'role', 'created_at', 'name', 'email'}
173:         if not isinstance(member, dict) or set(member) != strings | {'avatar_url'}:
174:             raise ProjectionError('incomplete or unknown member fields')
175:         if any(not isinstance(member[k], str) for k in strings) or member['workspace_id'] != workspace_id or member['role'] not in ('owner', 'admin', 'member'):
176:             raise ProjectionError('invalid member')
177:         if member['avatar_url'] is not None and not isinstance(member['avatar_url'], str):
178:             raise ProjectionError('invalid avatar')
179:     return dict(type=kind, payload=deepcopy(payload), actor_id=event['actorID'], actor_type=event['actorType'])
```

### server/src/workpal_backend/realtime/hub.py

```text
1: """Bounded local fanout seam; deliberately has no internal stream consumer."""
2: import asyncio
3: import anyio
4: from starlette.websockets import WebSocketDisconnect
5: from starlette.concurrency import run_in_threadpool
6: 
7: async def authorize(check):
8:     with anyio.fail_after(1):
9:         return await anyio.to_thread.run_sync(check, abandon_on_cancel=True)
10: from .protocol import project_event, resolve_audience
11: 
12: class Hub:
13:     def __init__(self):
14:         self.connections = set()
15: 
16:     async def publish(self, event):
17:         frame = project_event(event, event.get('workspaceID'))
18:         audience = resolve_audience(event)
19:         def receives(connection):
20:             if isinstance(audience, frozenset):
21:                 # Go personal fallback excludes the bound workspace, even after
22:                 # that connection explicitly unsubscribes its workspace room.
23:                 return any(room in connection.rooms and
24:                            (room[0] == 'workspace' or connection.workspace_id != event['workspaceID'])
25:                            for room in audience)
26:             return audience is not None and audience in connection.rooms
27: 
28:         await asyncio.gather(*(c.send(frame) for c in tuple(self.connections) if receives(c)))
29: 
30:     async def close(self):
31:         await asyncio.gather(*(c.close() for c in tuple(self.connections)))
32: 
33: class Connection:
34:     def __init__(self, ws, check, workspace, user):
35:         self.ws, self.check = ws, check
36:         self._workspace_id = workspace
37:         self.rooms = {('workspace', workspace), ('user', user)}
38:         self.lock = asyncio.Lock()
39:         self.closed = False
40: 
41:     @property
42:     def workspace_id(self):
43:         return self._workspace_id
44: 
45:     async def close(self):
46:         if not self.closed:
47:             self.closed = True
48:             try:
49:                 await asyncio.wait_for(self.ws.close(code=1008), 1)
50:             except (WebSocketDisconnect, RuntimeError, OSError, asyncio.TimeoutError, anyio.ClosedResourceError, anyio.BrokenResourceError):
51:                 pass
52: 
53:     async def send(self, frame):
54:         async with self.lock:
55:             if self.closed:
56:                 return
57:             try:
58:                 await authorize(self.check)
59:                 await asyncio.wait_for(self.ws.send_json(frame), 1)
60:             except Exception:
61:                 await self.close()
```

### server/src/workpal_backend/realtime/consumer.py

```text
1: """Single API process internal-stream bridge; at-least-once snapshot fanout."""
2: import asyncio
3: import json
4: import logging
5: from sqlalchemy import Column, MetaData, String, Table, select
6: from redis.exceptions import RedisError
7: from starlette.concurrency import run_in_threadpool
8: from ..infrastructure.database import DatabaseBusy
9: from .protocol import project_event, ProjectionError
10: 
11: metadata = MetaData()
12: checkpoints = Table('realtime_consumer_checkpoint', metadata,
13:     Column('consumer', String, primary_key=True), Column('stream_id', String, nullable=False))
14: receipts = Table('realtime_consumer_receipt', metadata,
15:     Column('consumer', String, primary_key=True), Column('event_id', String, primary_key=True))
16: quarantine = Table('realtime_consumer_quarantine', metadata,
17:     Column('consumer', String, primary_key=True), Column('stream_id', String, primary_key=True),
18:     Column('reason', String, nullable=False))
19: log = logging.getLogger(__name__)
20: 
21: class RealtimeConsumer:
22:     def __init__(self, database, resources, hub, *, consumer='api', timeout=1, retry_delay=.1):
23:         if not 0 < timeout <= 5 or not 0 < retry_delay <= 5:
24:             raise ValueError('Invalid consumer bounds')
25:         self.database, self.client, self.hub = database, resources.client, hub
26:         self.channel = resources.key('events:stream')
27:         self.consumer = consumer
28:         self.timeout, self.retry_delay = timeout, retry_delay
29:         self._stop = asyncio.Event()
30:         self._running = False
31: 
32:     def stop(self):
33:         self._stop.set()
34: 
35:     def _position(self):
36:         with self.database.transaction() as s:
37:             return s.execute(select(checkpoints.c.stream_id).where(checkpoints.c.consumer == self.consumer)).scalar_one_or_none() or '0-0'
38: 
39:     def _commit(self, stream_id, event_id=None, reason=None):
40:         with self.database.transaction() as s:
41:             s.execute(checkpoints.delete().where(checkpoints.c.consumer == self.consumer))
42:             s.execute(checkpoints.insert().values(consumer=self.consumer, stream_id=stream_id))
43:             if event_id:
44:                 s.execute(receipts.insert().values(consumer=self.consumer, event_id=event_id))
45:             if reason:
46:                 s.execute(quarantine.insert().values(consumer=self.consumer, stream_id=stream_id, reason=reason))
47: 
48:     def _seen(self, event_id):
49:         with self.database.transaction() as s:
50:             return s.execute(select(receipts.c.event_id).where(receipts.c.consumer == self.consumer, receipts.c.event_id == event_id)).first() is not None
51: 
52:     async def tick(self):
53:         """Read at most one entry. No SQL transaction spans any await."""
54:         if self._stop.is_set():
55:             return False
56:         position = await run_in_threadpool(self._position)
57:         rows = await asyncio.wait_for(self.client.xread({self.channel: position}, count=1), self.timeout)
58:         if not rows or self._stop.is_set():
59:             return False
60:         stream_id, fields = rows[0][1][0]
61:         if isinstance(stream_id, bytes):
62:             stream_id = stream_id.decode('ascii')
63:         try:
64:             raw = fields.get(b'envelope', fields.get('envelope'))
65:             if not isinstance(raw, (str, bytes)) or len(raw) > 65536:
66:                 raise ValueError('envelope bound')
67:             if isinstance(raw, str) and len(raw.encode('utf-8')) > 65536:
68:                 raise ValueError('envelope bound')
69:             event = json.loads(raw)
70:             event_id = event.get('eventID') if isinstance(event, dict) else None
71:             if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 256:
72:                 raise ValueError('event identity')
73:             project_event(event, event.get('workspaceID'))
74:         except (ValueError, UnicodeError, TypeError, RecursionError, ProjectionError):
75:             await run_in_threadpool(self._commit, stream_id, reason='invalid_or_unsupported_envelope')
76:             log.warning('Realtime entry quarantined: invalid_or_unsupported_envelope')
77:             return True
78:         seen = await run_in_threadpool(self._seen, event_id)
79:         if not seen:
80:             await asyncio.wait_for(self.hub.publish(event), self.timeout)
81:         await run_in_threadpool(self._commit, stream_id, event_id=None if seen else event_id)
82:         return True
83: 
84:     async def run(self):
85:         if self._running:
86:             raise RuntimeError('Consumer already running')
87:         self._running = True
88:         try:
89:             while not self._stop.is_set():
90:                 try:
91:                     progressed = await self.tick()
92:                 except (RedisError, OSError, asyncio.TimeoutError, DatabaseBusy):
93:                     log.warning('Realtime bridge unavailable; retrying')
94:                     progressed = False
95:                 if not progressed:
96:                     try:
97:                         await asyncio.wait_for(self._stop.wait(), self.retry_delay)
98:                     except asyncio.TimeoutError:
99:                         pass
100:         finally:
101:             self._running = False
```

### docs/superpowers/plans/2026-11-21-python-go-backend.md

```text
1: # Python Go Backend Replacement Implementation Plan
2: 
3: > **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
4: 
5: **Goal:** Replace this branch's default mock runtime with a verified Python implementation of the in-scope Go backend and current frontend contracts.
6: 
7: **Architecture:** FastAPI serves authenticated APIs with SQLite persistence and Docker Redis coordination. An independent worker dispatches durable events and background jobs; local upload bytes have a durable intent ledger. The frontend uses real sessions and workspace resolution, and default commands switch only after integration gates pass.
8: 
9: **Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, redis-py, pytest/httpx; React/Vite and Playwright. Resolve and lock compatible package versions in Task 2, recording the supported Python version.
10: 
11: **Spec:** `docs/superpowers/specs/2026-11-21-python-go-backend.md` (approved, including review corrections and default-command acceptance).
12: 
13: ## Global Constraints
14: 
15: - Develop on feat/python-fastapi-backend.
16: - Actual model execution and production integrations remain out of scope under AGENTS.md.
17: - Treat skill input as data and do not execute installation commands.
18: - Keep the existing frontend contract and English product UI.
19: - Do not silently fall back to mock on errors.
20: - Preserve original branch history, mock source files and its database, but change the active web entry and npm dev/start to Python.
21: - Credentials: `dev@workpal.local` / `888888`; explicit development switch, loopback binding, production-mode rejection, normal signed sessions and permission checks.
22: - Preserve all pre-existing uncommitted work. Record a baseline before edits; stage explicit owned paths/hunks only. Never use blanket staging or reset unrelated changes.
23: - Do not alter Go sources, existing SQLite records or archived review notes. Tests use disposable databases/upload directories and unique Redis namespaces; never flush shared Redis.
24: - Completing scaffolding or returning unsupported for every route does not complete the migration.
25: 
26: ## Review Focus
27: 
28: 1. Default entrypoints differ from a dedicated launcher: both actual npm commands must pass browser and shutdown tests (Task 9).
29: 2. Authentication expires or workspace access changes while a page/socket is open: clear private state and enforce authorization again (Tasks 3, 4, 7).
30: 3. A crash occurs between storing bytes and committing metadata: recover through the intent ledger without deleting live uploads (Task 6).
31: 4. SQLite lock contention and repeated dispatch produce duplicate mutations: bounded errors, transactional claims and idempotent effects (Tasks 2, 7).
32: 5. Current frontend extensions are absent from Go: combined inventory and Contribution persistence are mandatory (Tasks 1, 5, 8).
33: 
34: ## Execution structure
35: 
36: User-selected execution: implement sequentially in the current session. Do not dispatch implementation or review subagents.
37: 
38: Tasks 1–4 establish contracts and a working authenticated vertical slice. Tasks 5–8 migrate independently verifiable feature groups. Task 9 is the default-command cutover and release gate. Task 1 must expand the broad business groups into endpoint-sized work items in a companion checklist before their implementation; this plan does not pretend the large Go route surface has already been exhaustively inventoried.
39: 
40: Use repository-root-relative paths below. `PY` denotes the actual executable `server/.venv/bin/python`, not a global interpreter. Commands containing `PY` below mean substitute that executable. Each implementation task follows write test → observe failure → implement → rerun → review diff → narrowly scoped commit. Do not commit pre-existing user edits along with migration changes.
41: 
42: ### Task 1: Combined contract inventory and protected baseline
43: 
44: **Files:** Create `server/contracts/routes.json`, `server/contracts/frontend-calls.json`, `server/contracts/schema-map.md`, `server/tools/check_contracts.py`, `server/tests/test_contract_inventory.py`, and `docs/superpowers/plans/2026-11-21-python-route-batches.md`.
45: 
46: **Interfaces:** `check_contracts(routes_path: Path, callers_path: Path, *, require_complete: bool) -> list[str]`. Each route records full method/path, origin, source locations, callers, auth/scope, request/response/error fixtures, persistence dependencies, batch, status, test references and exclusions. Each mutating operation also records event disposition (required or explicitly none with source-backed reason), producer service/function, event type and payload, scope, transaction boundary, consumer and commit/rollback/recovery test references. Include non-HTTP producers such as scheduled jobs; the completeness checker rejects missing event dispositions or missing evidence for required events. Frontend calls link to a route or an explicit retirement/capability decision.
47: 
48: - [ ] Record branch/HEAD, changed paths and content hashes of existing tracked modifications; record protected mock/Go source hashes. Record `npm run check` baseline output without editing failures unrelated to migration. Do not checkpoint raw database contents in git.
49: - [ ] Write `test_unmapped_frontend_call_fails`, `test_duplicate_method_path_fails`, `test_incomplete_route_fails_release_gate`: respectively assert a diagnostic for an unmapped call, duplicate route and pending route in completion mode. Run with available Python test tooling; observe failure before implementing the checker.
50: - [ ] Read composed Go registrations, middleware, handlers, SQL and relevant tests; cross-check current frontend API clients and mock extensions. Record Go-only, shared, local-extension and retired-bootstrap routes. Resolve dynamic paths and conditional registrations manually where static scanning is insufficient.
51: - [ ] Fill schema map with required fields, relations, uniqueness, deletion policy and PostgreSQL-specific translations for every migration batch. Record real contracts rather than guessing field names or errors.
52: - [ ] Implement the checker and generate the companion route-batch checklist: exact source/destination files, fixtures, signatures and test commands for each coherent feature group. Explicitly include all remaining in-scope routes, not just the first visible pages. The checklist is a prerequisite for Task 5/8, not permission to reduce scope.
53: - [ ] Run inventory tests; require zero unmapped frontend calls and explicit decisions for every registration. Review and commit only Task 1 artifacts.
54: 
55: ### Task 2: Runnable Python foundation and isolated persistence
56: 
57: **Files:** Create `server/pyproject.toml`, lockfile, `README.md`, `src/workpal_backend/{app,config,cli}.py`, `src/workpal_backend/infrastructure/{database,redis}.py`, `alembic.ini`, `migrations/env.py`, first versioned migration, `tests/{conftest,test_config,test_database,test_health}.py`.
58: 
59: **Interfaces:** `create_app(settings: Settings) -> FastAPI`; `Database.transaction()` yields a SQLAlchemy session with commit/rollback; `RedisResources` owns client lifecycle and namespaced keys. CLI commands `python -m workpal_backend.cli migrate`, `serve`, and later `worker` share settings.
60: 
61: - [ ] Establish isolated venv and locked dependencies. Write tests for rejecting mock DB aliases/symlinks, invalid development binding/production flag, FK enforcement, rollback, reopen persistence, lock timeout and readiness with unavailable Redis.
62: - [ ] Run `PY -m pytest server/tests/test_config.py server/tests/test_database.py server/tests/test_health.py`; observe missing implementation failures.
63: - [ ] Implement settings, application lifecycle, explicit migrations, database and Redis resources. Resolve paths from repo root, enforce local WAL/FKs and bounded waits; no automatic migration of arbitrary existing files. Add liveness/readiness endpoints using inventoried Go contracts.
64: - [ ] Inspect Docker Redis endpoint without exposing credentials; use a unique test prefix. Verify Redis failure with an unreachable test endpoint, never by stopping someone else's container.
65: - [ ] Rerun tests and CLI migration twice against a fresh disposable DB; require no schema duplication, no leaked connections and truthful readiness. Document setup and narrowly commit.
66: 
67: ### Task 3: Real identity, workspace access and development login
68: 
69: **Files:** Create `src/workpal_backend/auth/{routes,schemas,service,tokens}.py`, `workspaces/{routes,schemas,service,repository}.py`, corresponding migrations, `tests/{test_auth,test_workspace_permissions}.py` under `server/`.
70: 
71: **Interfaces:** Authentication dependencies yield `Principal` with identity kind and user/actor ID; `require_workspace_access(session, principal, workspace_id)` resolves stored membership. HTTP request/response fixtures come from Task 1, including config, identity lookup, send-code, verify-code, logout and workspace operations.
72: 
73: - [ ] Write tests accepting only normalized `dev@workpal.local` plus `888888`, reusing the same persisted user on repeated login, rejecting other credentials, rejecting disabled/production development auth, and preventing PAT/task identity exchange into an interactive session. Add cookie, JWT expiry/renewal and CSRF assertions from Go tests.
74: - [ ] Write workspace tests for zero/one/multiple memberships, owner creation atomicity, removal and cross-workspace/private-resource denial. Run both files to observe failures.
75: - [ ] Implement schema and auth/workspace services, normal signed sessions and explicit development capability. No global owner bypass or mock identity. Keep external email/Google execution explicitly unsupported.
76: - [ ] Rerun tests, including database reopen and membership invalidation. Verify errors match inventoried contracts; commit only task files.
77: 
78: ### Task 4: Frontend authentication and workspace vertical slice
79: 
80: **Files:** Modify `apps/web/app/main.tsx`, `apps/web/app/routes.tsx`, `apps/web/vite.config.mjs`; create `apps/web/app/python-session.tsx`, `apps/web/app/verification-login.tsx`, `apps/web/app/python-session.test.tsx`, `apps/web/app/routes.test.tsx`, `scripts/python-web-dev.mjs`, `tests/python-web/auth.spec.ts`, `playwright.python.config.ts`. Reuse existing core auth initializer/provider and workspace APIs rather than introducing a second session store.
81: 
82: **Interfaces:** Python session boundary renders resolving, unauthenticated, workspace-selection/creation, authenticated or retryable-error states. Dedicated pre-cutover launcher starts Python plus Vite with disposable-state overrides; config proxies `/api`, `/auth`, `/ws` and inventoried content routes, including WS upgrades.
83: 
84: - [ ] Write tests proving no `/api/bootstrap`, no locally fabricated authentication, no auto-submit, editable capability-gated prefill, 401-to-login, transport-failure-to-retry, persisted session refresh, and inaccessible remembered-workspace rejection. Add route tests for a non-review slug, deep-link refresh, workspace switching, malformed URL encoding and a slug outside the authenticated membership set.
85: - [ ] Run component tests and browser auth spec against the incomplete slice; confirm failures describe missing behavior.
86: - [ ] Replace startup bootstrap/Seed and hardcoded workspace slug with real session/workspace resolution. Implement login submission, workspace creation/selection, deep-link gating and logout cleanup. Change LocalPage to accept the resolved authorized workspace slug and match the first URL segment against it, removing the review-only guard. Generate MissingPage recovery links from the resolved slug. Resolve deep-link workspace membership before rendering, and update route, platform workspace context, query state and subscriptions together when switching; never reinterpret an old workspace resource ID under a new workspace. Preserve visual system and keyboard access.
87: - [ ] Add dedicated launcher and proxy routes. Do not change default npm commands yet. Start WS only when authentication is resolved; complete protocol verification in Task 7.
88: - [ ] Run component tests and `pnpm exec playwright test --config playwright.python.config.ts tests/python-web/auth.spec.ts`. Verify refresh, invalid credentials, missing capability and zero/multiple workspaces. Commit owned edits without absorbing existing main.tsx changes.
89: 
90: ### Task 5: Core resources and current frontend extensions
91: 
92: **Files:** Create feature-owned `{routes,schemas,service,repository}.py` for `projects`, `issues`, `comments`, `agents`, `chats`, `contribution`, with migrations and `tests/test_<feature>_contracts.py`; exact ancillary feature files come from the Task 1 route-batch checklist. Update contract statuses only with evidence.
93: 
94: **Interfaces:** Routes consume Task 3 principals/access guards and Task 2 transactions. Serialization follows recorded HTTP fixtures; never return raw ORM objects. Contribution exposes GET/PUT `/api/dashboard/contribution` with existing response shapes and explicit workspace scope.
95: 
96: - [ ] For each batch, write contract cases for successful CRUD, bad inputs, nulls, pagination, relationship constraints, unauthorized/private access and reopen persistence. Run its test file and observe failures.
97: - [ ] Implement the batch and SQL translations from schema-map; enforce permissions inside services. Cover all corresponding schema dependencies, not just fields visible in a single page.
98: - [ ] For Contribution, test atomic replacement, repeat import, malformed import rollback, owner/admin requirement, private-project filtering, `days`/`tz`/`project_id` behavior and cross-workspace isolation. Empty data returns truthful empty aggregates.
99: - [ ] Rerun each batch's tests, add evidence to inventory and commit each independently reviewable batch. No fixture-derived agent outputs or fabricated metrics.
100: 
101: ### Task 6: Durable attachment bytes and authorized downloads
102: 
103: **Files:** Create `files/{routes,schemas,service,repository,storage,reconcile}.py`, upload-ledger migration, `tests/test_files.py`, `tests/test_upload_recovery.py`, `tests/python-web/files.spec.ts`.
104: 
105: **Interfaces:** `LocalBlobStore` operates on server-generated opaque keys under `WORKPAL_UPLOAD_DIR`; upload service maintains pending/ready/deleting states and leases. Downloads resolve permissions before byte access. Reconciler claims expired intents transactionally and performs idempotent cleanup.
106: 
107: - [ ] Write upload/download digest and restart tests plus invalid size, traversal/symlink, anonymous/cross-workspace/private access, range authorization and expired capability tests.
108: - [ ] Write crash-boundary cases before/after rename, failed DB finalization, active-upload lease protection, disk failure and failed-delete retry; run both files and observe failures.
109: - [ ] Implement the approved staged-write/fsync/rename/finalize protocol without a write transaction across file I/O. Persist cleanup work and handle orphaned bytes through the ledger. Never serve staging/internal files or mount the uploads directory publicly.
110: - [ ] Run Python file tests and browser file spec, restarting the API between upload and digest-verified download. At this stage invoke the reconciler directly in recovery tests; worker registration and actual scheduled recovery are verified in Task 7, after the worker exists. Add backup/restore guidance covering both database and upload bytes. Commit task files.
111: 
112: ### Task 7: Realtime and background-worker consistency
113: 
114: **Files:** Create `infrastructure/outbox.py`, `realtime/{routes,protocol,subscriptions}.py`, `worker.py`, job/outbox migrations, `tests/{test_realtime,test_worker,test_event_producers,test_upload_worker_recovery}.py`, `tests/python-web/realtime.spec.ts`.
115: 
116: **Additional modified files:** Task 3 auth/workspace services and Task 5 feature services identified as event producers in the Task 1 inventory; Task 6 files/service.py and files/reconcile.py. Enumerate their exact paths in the companion route-batch checklist before edits.
117: 
118: **Interfaces:** `append_event(session, event)` appends a stable-ID outbox row using the caller's existing transaction and never commits independently. Business transactions append stable-ID outbox events; worker claims durable jobs and dispatches to Redis using the inventoried Go protocol. `python -m workpal_backend.cli worker` owns scheduling; API processes do not each start a scheduler.
119: 
120: - [ ] Write tests for committed mutation + Redis outage, duplicate delivery, worker restart, expired claims, stale-worker fencing and SQLite contention. Assert committed writes are not reported as rolled back just because publication fails.
121: - [ ] Write WebSocket tests for handshake authentication, unauthorized scope, membership removal, logout/expiry and reconnect contract. Run tests to observe failures.
122: - [ ] Backfill every required event producer from Tasks 3/5/6 using append_event inside the same business transaction. For each inventory operation, parameterize tests asserting successful commit saves both mutation and correctly scoped event; injected rollback leaves neither; Redis publication failure retains pending delivery and recovery publishes the same stable event ID. Include repeat-delivery consumer idempotency. Record the test references per operation; a single representative WebSocket event is insufficient.
123: - [ ] Register files.reconcile as the upload-reconciliation job in the worker job registry. Persist its schedule/claim in SQLite, poll due work with a bounded interval, reclaim only expired intents, and retry failed cleanup. Add an integration test that leaves a pending upload, restarts API and worker, and observes cleanup from actual scheduling without directly calling the reconciler; assert ready and live leased uploads survive. Keep this out of API startup to prevent duplicate schedulers.
124: - [ ] Implement durable claims, idempotency, event dispatch, subscription authorization and bounded shutdown. Implement only permitted scheduling; external execution fails explicitly.
125: - [ ] Run Python tests with isolated Redis namespace and browser realtime spec; verify an actual authorized mutation event, not merely an HTTP upgrade. Clean only test-owned state and commit.
126: 
127: ### Task 8: Remaining routes and whole-application completion
128: 
129: **Files:** Feature files and test paths enumerated by Task 1 companion checklist, including search/inbox/settings/remaining supported automation and file routes; update contracts and `server/README.md`.
130: 
131: **Interfaces:** Same principal/transaction/serialization interfaces; unsupported capabilities have explicit UI states and backend errors after appropriate auth.
132: 
133: - [ ] Work through every remaining route batch using failing contract tests, implementation, passing tests and a narrowly scoped commit per batch. Cover search semantics, private-resource filtering and every reachable current frontend call.
134: - [ ] Verify each exclusion follows approved scope; missing implementation is pending, not an exclusion. Ensure current pages do not endlessly retry a generic 404 for deliberately unavailable features.
135: - [ ] Run `PY server/tools/check_contracts.py --require-complete`, complete Python suite and full Playwright suite via dedicated launcher. The completion checker must also require event dispositions for all mutating operations/jobs and commit, rollback and recovery evidence for each required producer. Require no unmapped calls, pending in-scope routes or missing test evidence.
136: - [ ] Review protected-source hashes and confirm no mock/Go/data modifications; record all compatibility limitations honestly. The dedicated launcher passing is only permission to attempt Task 9, not final acceptance.
137: 
138: ### Task 9: Default command cutover and actual-entrypoint acceptance
139: 
140: **Files:** Create `server/start-python.mjs`, `server/src/workpal_backend/static.py`, `scripts/python-entrypoints-qa.mjs`, `tests/python-web/entrypoints.spec.ts`; modify root `package.json`, Vite configuration as needed and Python README. Keep `server/start.mjs`, mock API/store and Go sources intact.
141: 
142: **Interfaces:** Root `dev` and `dev:web` run the Python supervisor with `--dev`; root `start` runs it without that flag. Development starts Python API at 4175, Vite at 4174 and preserves the current docs launch behavior. Built-app startup serves `apps/web/dist` from Python at 4174 with same-origin auth/API/content/WS. Static fallback must never swallow `/api`, `/auth`, `/ws` or content errors. The supervisor starts one worker, propagates failures, forwards signals and reaps all children. `npm start` means serving the built app; it does not implicitly enable development authentication or override an explicitly configured production environment.
143: 
144: - [ ] Write supervisor tests for missing Python, occupied port, failed child startup, unexpected API/worker exit and SIGINT/SIGTERM. Assert a nonzero failure exit where applicable, sibling cleanup, no mock process and no remaining listeners. Run and observe failures.
145: - [ ] Implement built static serving and supervisor; add explicit Python test/check commands to package scripts while preserving existing verification. Switch root defaults only now. No import of mock createServer and no automatic fallback. Startup errors are actionable and redact secrets.
146: - [ ] Build with `npm run build`, then run `npm run check` and the Python checks. Separate pre-existing failures using the baseline; never waive a migration regression.
147: - [ ] Execute `node scripts/python-entrypoints-qa.mjs`. This harness MUST spawn the actual root `npm run dev` and, in a separate run, actual root `npm start`, with `reuseExistingServer: false`; it must not substitute the dedicated launcher or call uvicorn directly. Use disposable SQLite/upload paths, unique Redis prefixes and explicit development-auth settings for this local acceptance run.
148: - [ ] For EACH actual command, confirm process ownership/readiness, prefilled manual login, rejected wrong code, authenticated refresh, workspace initialization, upload real bytes, authenticated digest-checked download and rejected unauthorized download. Receive an actual scoped WebSocket mutation event, reject unauthorized subscription and test logout disconnect.
149: - [ ] For EACH command, stop and restart using the same test database/upload directory, log in or recover the valid session, and verify the prior attachment bytes remain downloadable. Re-establish and verify WebSocket delivery after restart.
150: - [ ] For EACH command, exercise SIGINT and SIGTERM in separate runs; require clean shutdown within the documented bound, no live API/worker/Vite/docs child, closed WS and released 4174/4175/4000 ports where that run owned them. Confirm a new run can immediately bind again. Verify unavailable Redis/startup failure produces an explicit error and never launches mock; use bad test configuration, not interruption of the shared service.
151: - [ ] Separately verify production-mode rejection with development auth enabled. In production mode without the flag, verify prefill is absent and built static/auth routes behave without an auth bypass; local fixture login does not establish production identity-provider support.
152: - [ ] Capture command, environment profile (no secrets), exit status, process cleanup, browser trace and assertions for both runs in `docs/verification/python-backend-entrypoints.md`. Recheck protected files, inventory completeness and owned diff. Commit the cutover only after these actual-entrypoint checks pass.
153: 
154: ## Final acceptance and handoff
155: 
156: - [ ] No pending in-scope route, no unexplained frontend call and no fabricated integration/model output.
157: - [ ] Python persistence, Redis, file recovery, permissions and browser checks pass.
158: - [ ] Actual root `npm run dev` AND `npm start` pass login, restart/download, realtime and process-exit checks after default command changes.
159: - [ ] Existing records, Go/mock sources and original branch history are preserved; runtime faults never fall back to mock.
160: - [ ] README includes install/migrate/start/worker configuration, Docker endpoint guidance, local credentials and limits, backup/restore and verification commands.
161: 
162: ## Plan self-review
163: 
164: Spec coverage maps to Tasks 1–9: dual contract sources (1/5/8), SQLite/Redis (2/7), authentication and frontend bootstrap (3/4), files (6), default runtime and final command validation (9). All five review-focus failures have explicit tests. Endpoint-specific batches intentionally require the completed inventory before implementation; a generic module checklist alone is not an executable replacement for those batches. No service implementation or verification result is claimed by this plan.
165: 
166: ## Plan review corrections
167: 
168: - Task 4 now owns routes.tsx, dynamic authorized slugs, generated recovery links and deep-link/workspace-switch tests.
169: - Task 6 verifies API restart and direct reconciler behavior; Task 7 owns actual worker registration, scheduling and API/worker restart recovery.
170: - Task 1 records producer-level event contracts; Task 7 explicitly modifies earlier business services and tests commit/rollback/recovery per producer; Task 8 enforces complete evidence.
171: - Task 9 actual npm dev/start acceptance remains mandatory and unchanged.
```

### docs/superpowers/specs/2026-11-21-python-go-backend.md

```text
1: # Python replacement for the original Go backend
2: 
3: ## Scope
4: Replace the HTTP backend rooted at server/go/cmd/server with a separately runnable Python FastAPI service. Preserve all Go sources, Node mock source files, existing mock SQLite records and existing uncommitted work. Develop on feat/python-fastapi-backend. The Go CLI and local runtime executables are not rewritten as part of the HTTP service migration.
5: 
6: ## Architecture
7: Add server/python with FastAPI routing, explicit request/response models, application services and SQLite repositories. Use a new Python-service database file, separate from server/data/workpal.sqlite. Preserve the existing Go HTTP contracts, authorization behavior and logical data relationships; adapt PostgreSQL-specific types, SQL and locking semantics explicitly rather than copying SQL verbatim. Keep persistence behind repository interfaces to allow a later PostgreSQL implementation. Use Redis from a Docker-hosted service for migrated functionality that requires shared ephemeral state, pub/sub or coordination. Configure its connection through REDIS_URL; do not hardcode credentials or expose them in logs. Namespace application keys and pub/sub channels, with separate test namespaces and cleanup limited to test-owned keys; never flush a shared Redis database. Required Redis operations must fail explicitly when Redis is unavailable. Start with a single application worker; design background work and event delivery for this local deployment, without claiming multi-instance coordination. Use versioned schema migrations for the new database only; verification uses disposable SQLite databases.
8: 
9: ## Migration method
10: Inventory routes and dependencies before implementation. Migrate coherent feature groups, beginning with configuration, SQLite schema and database lifecycle, authentication and workspace access, then business resources, events and background scheduling. Maintain a route coverage inventory that distinguishes implemented, pending and intentionally unsupported operations. Pending operations must fail explicitly; a running skeleton does not constitute a completed replacement.
11: 
12: ## Project constraints
13: Actual model execution and production integrations remain out of scope under AGENTS.md. Return explicit unsupported-operation errors and never fabricate model output. Treat skill input as data and do not execute installation commands. Keep the existing frontend contract and English product UI.
14: 
15: ## Validation
16: Use disposable SQLite databases, never the existing mock SQLite store. Run Redis integration checks against the Docker service with isolated test namespaces, including unavailable-service behavior; do not modify unrelated container data. Verify foreign-key enforcement, transaction rollback, concurrent-write handling and database reopen persistence. Review PostgreSQL-specific JSON, array, search and locking behavior during each module migration. Test authentication, tenant isolation, permissions, persistence, malformed input and relevant event behavior. Compare migrated HTTP contracts against Go definitions and fixtures. Run Python checks and npm run check, reporting pre-existing failures separately. Document startup, configuration, route coverage and remaining limitations honestly.
17: 
18: ## Detailed design — proposed for review
19: 
20: ### Source of truth and compatibility
21: - Route composition: server/go/cmd/server/router.go, including middleware groups and delegated plugin route registration. Build the full method/path inventory from these registrations and cross-check it against current frontend calls and local mock extensions; neither source alone establishes frontend compatibility.
22: - Business behavior: server/go/internal/handler and server/go/internal/service, with existing tests as behavioral evidence.
23: - Authentication: server/go/internal/auth and middleware. Preserve token-kind separation, JWT verification, session renewal, cookie attributes and CSRF binding; do not simplify these into a fixed development user.
24: - Persistence: server/go/pkg/db/queries and server/go/migrations define logical entities and constraints, not executable SQLite migrations.
25: - Real-time behavior: server/go/internal/realtime and event listeners in server/go/cmd/server. Inventory payloads, authorization, ordering, retention and reconnect behavior before selecting Redis structures per event type.
26: 
27: Each route inventory entry records method, full path, auth requirements, request/response and error contract, dependencies, migration group, implementation state and verification evidence. Do not report full Go parity until all in-scope entries pass. Preserve 401/403/404 distinctions, pagination, nullable fields, timestamps and identifier formatting. Adapt FastAPI validation errors to the original API contract where necessary. Unknown paths remain 404; known pending operations return an explicit documented not-implemented response after applicable authentication checks.
28: 
29: ### Module layout
30: Use server/pyproject.toml with a locked dependency set and a src/workpal_backend package:
31: - app.py and config.py: application factory, lifecycle, validated environment settings, health/readiness.
32: - infrastructure/: SQLite connection/transaction lifecycle, Redis client lifecycle, migrations and durable event dispatch.
33: - auth/: identity, token validation, CSRF and session renewal.
34: - workspaces/, projects/, issues/, agents/, chats/, files/, automation/: feature-owned API schemas, routes, business operations and repository implementation. Add modules as their route groups migrate; avoid empty scaffolding for every Go file.
35: - realtime/: authenticated subscriptions and the existing wire protocol.
36: - tests/: contract, integration and permission tests with isolated state.
37: 
38: Use FastAPI and Pydantic for HTTP boundaries, SQLAlchemy for explicit transactions and database access, Alembic for Python-owned migrations, and redis-py for Docker Redis connectivity. Pin compatible versions during implementation. Business operations own transaction boundaries; routes do not expose ORM objects directly. Repositories encapsulate SQL dialect differences without introducing a generic CRUD abstraction that hides permissions.
39: 
40: ### SQLite storage
41: Default proposed path: server/data/python/workpal.sqlite; reject accidental configuration pointing at the existing mock database. Enable foreign keys on every connection, WAL on local storage and a bounded busy timeout. Keep write transactions short; never hold a write transaction across Redis, HTTP or file I/O. Translate lock contention into a documented retryable service error; retry writes only when their operation is safely idempotent.
42: 
43: Represent identifiers as text while preserving API formats. Specify UTC timestamp precision and serialization centrally. Store structured values as JSON only when relational constraints and query requirements permit it; use relation tables for membership and relationships. Translate PostgreSQL arrays, JSON operators, search, casts, generated values and lock-based claims individually, backed by tests. Do not assume SQLite FTS or case folding matches PostgreSQL search.
44: 
45: Multiple API processes on one host may share this local database, subject to SQLite's single-writer limit. Initial supported deployment is one API process and one background worker. Multi-process support requires contention and subscription tests; cross-host shared-file deployment is outside this design. Redis does not remove the SQLite write limit.
46: 
47: ### Redis and background work
48: Connect to the existing Docker service using REDIS_URL. A host-run API uses the published host port; a container-run API uses the Docker network service name. Do not assume localhost refers to the Redis container. Inspect existing containers and ports before supplying a concrete local configuration; do not recreate an existing service or publish it externally.
49: 
50: Use REDIS_KEY_PREFIX for keys and channels, with unique prefixes for test runs. Cache entries have bounded TTLs; authorization cache invalidation must preserve permission changes. Durable business records and authoritative job claims belong in SQLite. Redis may provide notifications, short-lived coordination and compatible stream transport, but is not the sole store of business state.
51: 
52: For newly migrated database mutations that emit durable events, record an outbox entry in the same SQLite transaction. A separate worker dispatches committed events and retries delivery. Delivery is at least once: use stable event IDs and idempotent consumers; never promise exactly once. Map existing Go event contracts and retention requirements before implementing reconnection behavior. Existing Pub/Sub-only semantics can remain ephemeral where the Go contract allows this.
53: 
54: Run scheduling in the separate worker, not independently in every API process. Use transactional job claims and idempotency constraints; if Redis leases are used, release by owner token and guard stale-worker writes with database checks. Redis interruption must not silently authorize requests or report successful dispatch. A committed database mutation with pending outbox delivery remains committed; avoid returning a misleading failure that invites duplicate writes.
55: 
56: ### Authentication and unsupported integrations
57: Preserve human, personal-access-token and runtime/task identity boundaries for implemented routes. Apply workspace and private-project access checks in business operations and subscription authorization, not only route middleware. Test membership removal and cross-workspace resource IDs.
58: 
59: The Go login entry points include email-code and Google authentication. Production email/OAuth integrations remain unsupported under the project constraints. User-approved approach: hardcode one development email and verification code. Proposed default values are dev@workpal.local and 888888. Enable this only with WORKPAL_DEV_AUTH=true in development mode on a loopback listener; production-mode startup must reject that flag. Preserve the existing /auth/send-code and /auth/verify-code request/response contracts. For the configured development email, send-code performs no email delivery; verify-code accepts only the exact fixed email/code pair after the existing email normalization rules. Reject all other identities or codes using the existing authentication error contract. Create or reuse one persisted development user through an idempotent transaction; do not insert duplicate users on repeated login. Issue normal signed sessions and enforce the existing cookie, CSRF, session-renewal and resource authorization rules. Workspace access still derives from stored membership, never a global authorization bypass. Keep Google and actual email delivery explicitly unsupported. Tests cover accepted credentials, wrong email/code, repeated login, disabled development mode and production-mode rejection. These credentials are intentionally public local-development fixtures, not production secrets.
60: 
61: Keep runtime/model execution and external provider operations explicitly unsupported. CRUD for configuration may be supported without claiming the underlying integration is connected or executable. Do not execute skill commands or generate fabricated task results. Decide endpoint-specific unsupported status and error shape in the contract inventory rather than returning a generic success response.
62: 
63: ### Configuration and operations
64: Proposed settings: WORKPAL_DATABASE_URL, REDIS_URL, REDIS_KEY_PREFIX, AUTH_SECRET, WORKPAL_HOST and WORKPAL_PORT. Keep existing Go environment names where compatibility matters, and document any deliberate differences. No built-in signing secret. Provide explicit migration, API and worker commands in the Python README; switch npm dev/start and frontend routing to Python after the end-to-end readiness gates pass, as authorized by the user. Retain mock source files and data without a default runtime fallback.
65: 
66: Health distinguishes process liveness from readiness. Readiness checks schema version, SQLite access and required Redis connectivity with bounded timeouts. Graceful shutdown closes subscriptions and clients and releases owned work safely. Logs include request IDs and operation context, never tokens, passwords or database credentials.
67: 
68: ### Migration sequence and completion gates
69: 1. Contract inventory and SQLite schema mapping: list all route groups and exclusions, PostgreSQL-specific behavior and corresponding tests.
70: 2. Runnable foundation: configuration, migrations, health, Redis connectivity and isolated test harness.
71: 3. Identity and access: fixed-email/code development login, session/token checks, CSRF, workspaces, membership and private-resource permissions.
72: 4. Core business resources: projects, issues, comments, labels, agents and chats, following dependency order from the inventory.
73: 5. Files, search, inbox, realtime and permitted scheduling: preserve access checks, transaction/event consistency and reconnect behavior.
74: 6. Remaining in-scope routes and full verification: audit every inventory entry, document unsupported operations, run Python tests and npm run check, and provide startup/cutover instructions then switch this development branch to Python by default.
75: 
76: For every feature group, require real persistence across restart, malformed-input tests, permission tests and HTTP contract tests. Exercise SQLite contention, rolled-back writes, Redis outages, repeated job delivery and subscription authorization. Use existing Go tests to derive expectations; use differential tests only for safe local operations against isolated Go dependencies. Passing a small smoke suite does not establish whole-backend equivalence.
77: 
78: ### Deliberate limits
79: This design does not migrate existing PostgreSQL production records, replace the Go CLI/runtime executables, enable model calls or production integrations. Those changes need separate scope. All implementation remains pending; this document records design decisions, not measured performance or completed compatibility.
80: 
81: 
82: ### Development login form prefill — user requirement
83: When the frontend is explicitly configured to target the Python backend with development authentication enabled, prefill the email with dev@workpal.local and the six-digit verification code with 888888. For a multi-step login flow, prefill each value when its corresponding field appears. Keep the values visible and editable, preserve keyboard access, and require the user to submit the form; prefill must not trigger automatic login or email delivery. Gate this behavior on an explicit development-auth capability from the Python backend, never merely on a hostname or a failed configuration request. A missing or false capability disables credential prefill; it never restores mock authentication. Preserve Node mock source files and records; the active frontend on this branch will use Python by default after verification. Add verification for both enabled Python development login and absent/disabled capability, including no automatic submission.
84: 
85: 
86: ## Review corrections and authorized frontend cutover
87: 
88: ### Frontend authentication and startup
89: Code inspection confirms apps/web/app/main.tsx currently fetches /api/bootstrap before rendering, seeds an authenticated user and a fixed review workspace, and disables WebSocket with an empty URL. LoginEntry is not a verification-code authentication form. These behaviors must be replaced for Python; adding a backend URL alone is insufficient.
90: 
91: The user explicitly authorizes replacing the default mock runtime on this development branch once Python works. Do not introduce a permanent mock/Python mode switch. Preserve original branch history, mock source files and its database, but change the active web entry and npm dev/start to Python. Do not silently fall back to mock on errors. Before cutover, run Python verification through a dedicated development launcher against disposable data.
92: 
93: Implement a real login form using the existing English Workpal visual system. Start with an unresolved authentication state, fetch Python configuration, and resolve the existing session through the Go-compatible authenticated identity endpoint. Only a successful server identity response establishes authentication. A 401 shows login; transport errors and 5xx show a retryable error rather than creating an identity. Prefill dev@workpal.local and 888888 only when Python explicitly advertises enabled development authentication. Submission calls the compatible /auth/send-code and /auth/verify-code flow, issues normal cookies and CSRF state, then resolves the authenticated identity. Never auto-submit. Retain the development flag, loopback binding requirement and production rejection.
94: 
95: After authentication, list authorized workspaces. Restore a remembered workspace only if membership still permits it; select the sole workspace, show a selector for multiple workspaces, or show workspace creation for an empty account. Persist workspace and owner membership atomically on creation. Set the actual workspace ID and slug in the existing platform providers; fetch its projects normally. Do not seed fabricated projects or use /api/bootstrap. Protect deep links until authentication and workspace resolution complete. Logout/session expiration clears identity and workspace-scoped query state and disconnects realtime. Refresh restores an existing valid session without requiring another code submission.
96: 
97: Configure the Vite development proxy for /api, /auth and /ws, with WebSocket upgrade enabled. Route any attachment content paths identified by the contract inventory to Python too. Use same-origin cookie authentication; derive ws/wss from the current page scheme. Connect realtime only after session resolution, subscribe only to authorized scopes, and reconnect using the existing wire contract. A built production frontend requires equivalent HTTP/upgrade routing, not reliance on Vite's dev proxy. Define that routing in the Python launcher/deployment documentation before cutover. All browser-facing listeners remain loopback-only while development authentication is enabled.
98: 
99: Acceptance: unauthenticated direct URL, prefilled manual login, wrong code, refresh session recovery, expired session, logout, no/multiple workspaces, inaccessible remembered workspace, authorized WebSocket subscription and unauthorized denial. Confirm that no /api/bootstrap request or fabricated authenticated state remains in the Python application flow. Test the actual browser workflow with Playwright when available.
100: 
101: ### Combined contract inventory and local extensions
102: Cross-check server/go/cmd/server/router.go and nested registrations against calls in apps/web, packages/core and packages/views, plus server/api.mjs extensions. Record each endpoint's origin (Go, local extension, or mock-only startup), callers, scope, shape, error behavior and explicit support decision. Frontend completion requires all reachable calls to have supported behavior or a deliberate capability-gated unavailable state; passing Go-only tests is insufficient.
103: 
104: Support GET and PUT /api/dashboard/contribution as a local extension. Derive schemas, filtering and aggregation behavior from contribution-tab.tsx, server/contribution.mjs and its tests. Persist actual user-imported commit records in the Python SQLite database, partitioned by workspace. Resolve workspace context using the existing client transport contract and verify membership; reject missing or ambiguous scope rather than selecting the first workspace. PUT requires an owner/admin role and validates the complete import before atomically replacing that workspace's contribution data, matching the current replacement model. Validate referenced projects/issues within the permitted scope and filter private-project data on reads. Preserve days, tz and project_id semantics, response fields and count response. Empty data yields truthful empty aggregates, never mock fixture metrics. Repeated imports, invalid input, restart persistence and workspace isolation need coverage.
105: 
106: Retire /api/bootstrap from the active frontend rather than reimplementing its authentication bypass. Other mock-only extensions must receive a support/exclusion decision in the inventory before their pages count as ready. Any excluded operation must have an explicit UI capability state and backend error; generic 404 pages are not acceptance.
107: 
108: ### File content persistence and compensation
109: Use WORKPAL_UPLOAD_DIR with repository-root-resolved default server/data/python/uploads, separate from Go and mock storage. Store metadata, ownership, size, digest and server-generated opaque storage keys in SQLite; store bytes under this directory. Never use an uploaded filename as a filesystem path. Do not expose the directory as an unauthenticated static mount. Include this directory with SQLite in a coordinated backup procedure.
110: 
111: Upload lifecycle: authorize and validate limits; persist a pending upload intent with a unique object key; stream bytes into a uniquely owned staging file on the same filesystem with bounded size; flush and fsync; atomically rename to the final key and sync the directory; then commit ready metadata and the owning attachment association in a short transaction. Only ready records can be downloaded. Do not keep a SQLite write transaction open while streaming. Pending intents carry owner/lease information so reconciliation cannot delete an active upload.
112: 
113: On streaming or rename failure, mark the intent failed and clean up owned temporary bytes. If metadata finalization fails after rename, the persisted pending intent remains the recovery record; retry finalization only when ownership and validation can be re-established, otherwise reclaim bytes after the lease expires. A reconciler handles crashed/expired pending uploads and retries cleanup without deleting ready or active files. Deletion first makes the attachment unavailable and records durable cleanup work, then idempotently deletes bytes; failed deletion remains retryable. A ready record with missing bytes returns an explicit unavailable-content error, never an empty successful download.
114: 
115: Downloads resolve metadata first and enforce current workspace/private-resource permissions. If the original endpoint uses signed capabilities, preserve its scope, expiry and revocation/access policy rather than treating a storage key as authorization. Prevent traversal and symlink escapes; sanitize download filenames and headers and block staging/internal files. Inventory upload/download URL formats and proxy every required route. Authorization precedes byte access, including range requests.
116: 
117: Acceptance: upload real bytes, restart API and worker, download with identical digest; deny anonymous/cross-workspace/private-resource access; test expired signed access, traversal, size overflow, disk-write failure, metadata-commit failure, crashes before/after rename, active-upload reconciliation safety and failed deletion retry. Merely checking an attachment row is insufficient.
118: 
119: ### Revised completion ordering
120: Contract inventory includes both Go and current frontend calls. Implement storage and identity foundation, then real frontend login/workspace bootstrap and core resources. Add local extensions, durable files and realtime before the full browser acceptance run. Only after these gates and npm run check pass (or unrelated baseline failures are explicitly identified) switch default development/start commands on this branch to Python. Original Go and mock sources and existing SQLite records remain preserved throughout.
```
