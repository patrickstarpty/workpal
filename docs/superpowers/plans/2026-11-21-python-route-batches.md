> **2026-11-22：历史文档，暂停执行。** 用户要求重新按 Go 源码一比一复刻并先审核文档。以 [新设计](../specs/2026-11-22-go-parity-design.md) 和 [新实施计划](../plans/2026-11-22-go-parity-plan.md) 为待审核版本。下文原批准/进度不授权继续实施或删除 Node。

# Python endpoint migration checklist

All unchecked endpoints remain pending. Source handler bodies and inherited registration middleware are in routes.json. Each endpoint needs exact executable success, validation, permission, persistence/reopen and error fixtures before implementation acceptance. Do not treat embedded source as passing tests.

## agent-activity-30d

Destination: `server/src/workpal_backend/agent_activity_30d/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_agent_activity_30d_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/agent-activity-30d` → `h.GetWorkspaceAgentActivity30d`; evidence: server/go/cmd/server/router.go:2620, server/go/internal/handler/agent.go:3324.

## agent-builder

Destination: `server/src/workpal_backend/agent_builder/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_agent_builder_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/agent-builder/sessions` → `h.ListAgentBuilderSessions`; evidence: server/go/cmd/server/router.go:2502, server/go/internal/handler/agent_builder.go:207.

- [ ] `POST /api/agent-builder/sessions` → `h.CreateAgentBuilderSession`; evidence: server/go/cmd/server/router.go:2503, server/go/internal/handler/agent_builder.go:61.

- [ ] `PATCH /api/agent-builder/sessions/{sessionId}/runtime` → `h.SwitchAgentBuilderRuntime`; evidence: server/go/cmd/server/router.go:2504, server/go/internal/handler/agent_builder.go:423.

- [ ] `PUT /api/agent-builder/sessions/{sessionId}/draft` → `h.SaveAgentBuilderDraft`; evidence: server/go/cmd/server/router.go:2507, server/go/internal/handler/agent_builder.go:271.

## agent-run-counts

Destination: `server/src/workpal_backend/agent_run_counts/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_agent_run_counts_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/agent-run-counts` → `h.GetWorkspaceAgentRunCounts`; evidence: server/go/cmd/server/router.go:2623, server/go/internal/handler/agent.go:3283.

## agent-task-snapshot

Destination: `server/src/workpal_backend/agent_task_snapshot/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_agent_task_snapshot_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/agent-task-snapshot` → `h.ListWorkspaceAgentTaskSnapshot`; evidence: server/go/cmd/server/router.go:2606, server/go/internal/handler/agent.go:3377.

## agents

Destination: `server/src/workpal_backend/agents/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_agents_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/agents` → `h.ListAgents`; evidence: server/go/cmd/server/router.go:2454, server/go/internal/handler/agent.go:1204.

- [ ] `POST /api/agents` → `h.CreateAgent`; evidence: server/go/cmd/server/router.go:2455, server/go/internal/handler/agent.go:1473.

- [ ] `POST /api/agents/mika` → `h.CreateMikaAgent`; evidence: server/go/cmd/server/router.go:2460, server/go/internal/handler/mika_agent.go:82.

- [ ] `GET /api/agents/{id}` → `h.GetAgent`; evidence: server/go/cmd/server/router.go:2462, server/go/internal/handler/agent.go:1317, server/go/internal/integrations/lark/outcome_replier_test.go:122, server/go/internal/integrations/lark/outbound_test.go:100.

- [ ] `PUT /api/agents/{id}` → `h.UpdateAgent`; evidence: server/go/cmd/server/router.go:2463, server/go/internal/handler/agent.go:2015.

- [ ] `GET /api/agents/{id}/apps` → `h.ListAgentApps`; evidence: server/go/cmd/server/router.go:2464, server/go/internal/handler/connected_apps.go:826.

- [ ] `PUT /api/agents/{id}/apps` → `h.UpdateAgentApps`; evidence: server/go/cmd/server/router.go:2465, server/go/internal/handler/connected_apps.go:849.

- [ ] `POST /api/agents/{id}/archive` → `h.ArchiveAgent`; evidence: server/go/cmd/server/router.go:2466, server/go/internal/handler/agent.go:2848.

- [ ] `POST /api/agents/{id}/restore` → `h.RestoreAgent`; evidence: server/go/cmd/server/router.go:2467, server/go/internal/handler/agent.go:2906.

- [ ] `POST /api/agents/{id}/cancel-tasks` → `h.CancelAgentTasks`; evidence: server/go/cmd/server/router.go:2468, server/go/internal/handler/agent.go:2958.

- [ ] `GET /api/agents/{id}/tasks` → `h.ListAgentTasks`; evidence: server/go/cmd/server/router.go:2469, server/go/internal/handler/agent.go:2987.

- [ ] `GET /api/agents/{id}/dingtalk/groups` → `h.ListDingTalkGroupsForAgent`; evidence: server/go/cmd/server/router.go:2470, server/go/internal/handler/dingtalk.go:251.

- [ ] `GET /api/agents/{id}/skills` → `h.ListAgentSkills`; evidence: server/go/cmd/server/router.go:2471, server/go/internal/handler/skill.go:2723.

- [ ] `PUT /api/agents/{id}/skills` → `h.SetAgentSkills`; evidence: server/go/cmd/server/router.go:2472, server/go/internal/handler/skill.go:2747.

- [ ] `POST /api/agents/{id}/skills/add` → `h.AddAgentSkills`; evidence: server/go/cmd/server/router.go:2473, server/go/internal/handler/skill.go:2806.

- [ ] `GET /api/agents/{id}/labels` → `h.ListLabelsForAgent`; evidence: server/go/cmd/server/router.go:2474, server/go/internal/handler/label.go:572.

- [ ] `POST /api/agents/{id}/labels` → `h.AttachLabelToAgent`; evidence: server/go/cmd/server/router.go:2475, server/go/internal/handler/label.go:587.

- [ ] `DELETE /api/agents/{id}/labels/{labelId}` → `h.DetachLabelFromAgent`; evidence: server/go/cmd/server/router.go:2476, server/go/internal/handler/label.go:616.

- [ ] `PUT /api/agents/{id}/skills/{skillId}/enabled` → `h.SetAgentSkillEnabled`; evidence: server/go/cmd/server/router.go:2477, server/go/internal/handler/skill.go:2859.

- [ ] `PUT /api/agents/{id}/runtime-skills/enabled` → `h.SetAgentRuntimeSkillEnabled`; evidence: server/go/cmd/server/router.go:2478, server/go/internal/handler/agent_runtime_skills.go:84.

- [ ] `DELETE /api/agents/{id}/skills/{skillId}` → `h.RemoveAgentSkill`; evidence: server/go/cmd/server/router.go:2479, server/go/internal/handler/skill.go:2897.

- [ ] `GET /api/agents/{id}/mcp-servers` → `h.ListAgentMcpServers`; evidence: server/go/cmd/server/router.go:2484, server/go/internal/handler/workspace_mcp_api.go:338.

- [ ] `POST /api/agents/{id}/mcp-servers` → `h.AddAgentMcpServer`; evidence: server/go/cmd/server/router.go:2485, server/go/internal/handler/workspace_mcp_api.go:395.

- [ ] `PUT /api/agents/{id}/mcp-servers/{serverId}/enabled` → `h.SetAgentMcpServerEnabled`; evidence: server/go/cmd/server/router.go:2486, server/go/internal/handler/workspace_mcp_api.go:459.

- [ ] `DELETE /api/agents/{id}/mcp-servers/{serverId}` → `h.RemoveAgentMcpServer`; evidence: server/go/cmd/server/router.go:2487, server/go/internal/handler/workspace_mcp_api.go:497.

- [ ] `GET /api/agents/{id}/env` → `h.GetAgentEnv`; evidence: server/go/cmd/server/router.go:2493, server/go/internal/handler/agent_env.go:141.

- [ ] `PUT /api/agents/{id}/env` → `h.UpdateAgentEnv`; evidence: server/go/cmd/server/router.go:2494, server/go/internal/handler/agent_env.go:190.

## app-calls

Destination: `server/src/workpal_backend/app_calls/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_app_calls_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/app-calls` → `h.ListIssueAppCalls`; evidence: server/go/cmd/server/router.go:2699, server/go/internal/handler/connected_apps.go:792.

## app-requests

Destination: `server/src/workpal_backend/app_requests/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_app_requests_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/app-requests` → `h.ListAppRequests`; evidence: server/go/cmd/server/router.go:2702, server/go/internal/handler/connected_apps.go:1014.

- [ ] `POST /api/app-requests/{id}/approve` → `h.ApproveAppRequest`; evidence: server/go/cmd/server/router.go:2703, server/go/internal/handler/connected_apps.go:1117.

- [ ] `POST /api/app-requests/{id}/reject` → `h.RejectAppRequest`; evidence: server/go/cmd/server/router.go:2704, server/go/internal/handler/connected_apps.go:1147.

## apps

Destination: `server/src/workpal_backend/apps/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_apps_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/apps/mcp` → `h.AppsGateway`; evidence: server/go/cmd/server/router.go:1673, server/go/internal/handler/connected_apps.go:1178.

- [ ] `GET /api/apps` → `h.GetAppsOverview`; evidence: server/go/cmd/server/router.go:2686, server/go/internal/handler/connected_apps.go:205.

- [ ] `GET /api/apps/catalog` → `h.ListAppCatalog`; evidence: server/go/cmd/server/router.go:2687, server/go/internal/handler/connected_apps.go:277.

- [ ] `PUT /api/apps/settings` → `h.UpdateAppSettings`; evidence: server/go/cmd/server/router.go:2688, server/go/internal/handler/connected_apps.go:478.

- [ ] `POST /api/apps/team/connect` → `h.ConnectTeamApp`; evidence: server/go/cmd/server/router.go:2689, server/go/internal/handler/connected_apps.go:347.

- [ ] `GET /api/apps/team/impact` → `h.GetTeamAppImpact`; evidence: server/go/cmd/server/router.go:2690, server/go/internal/handler/connected_apps.go:427.

- [ ] `DELETE /api/apps/team/connections/{id}` → `h.DisconnectTeamApp`; evidence: server/go/cmd/server/router.go:2691, server/go/internal/handler/connected_apps.go:395.

- [ ] `POST /api/apps/personal/connect` → `h.ConnectPersonalApp`; evidence: server/go/cmd/server/router.go:2692, server/go/internal/handler/connected_apps.go:373.

- [ ] `GET /api/apps/rules` → `h.GetAppRules`; evidence: server/go/cmd/server/router.go:2693, server/go/internal/handler/connected_apps.go:562.

- [ ] `PUT /api/apps/rules` → `h.UpdateAppRules`; evidence: server/go/cmd/server/router.go:2694, server/go/internal/handler/connected_apps.go:587.

- [ ] `GET /api/apps/activity` → `h.ListAppActivity`; evidence: server/go/cmd/server/router.go:2695, server/go/internal/handler/connected_apps.go:656.

- [ ] `GET /api/apps/tools` → `h.ListAppTools`; evidence: server/go/cmd/server/router.go:2696, server/go/internal/handler/connected_apps.go:703.

- [ ] `PUT /api/apps/tools/class` → `h.UpdateAppToolClass`; evidence: server/go/cmd/server/router.go:2697, server/go/internal/handler/connected_apps.go:741.

## assignee-frequency

Destination: `server/src/workpal_backend/assignee_frequency/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_assignee_frequency_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/assignee-frequency` → `h.GetAssigneeFrequency`; evidence: server/go/cmd/server/router.go:2152, server/go/internal/handler/activity.go:409.

## attachments

Destination: `server/src/workpal_backend/attachments/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_attachments_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/attachments/{id}/signed-download` → `h.DownloadAttachmentWithCapability`; evidence: server/go/cmd/server/router.go:1594, server/go/internal/handler/attachment_capability.go:196.

- [ ] `GET /api/attachments/{id}/download` → `h.DownloadAttachment`; evidence: server/go/cmd/server/router.go:1821, server/go/internal/handler/file.go:938.

- [ ] `GET /api/attachments/{id}/download-metadata` → `h.GetAttachmentForDownload`; evidence: server/go/cmd/server/router.go:1825, server/go/internal/handler/file.go:753.

- [ ] `GET /api/attachments/{id}` → `h.GetAttachmentByID`; evidence: server/go/cmd/server/router.go:2425, server/go/internal/handler/file.go:741.

- [ ] `GET /api/attachments/{id}/content` → `h.GetAttachmentContent`; evidence: server/go/cmd/server/router.go:2431, server/go/internal/handler/file.go:1391.

- [ ] `DELETE /api/attachments/{id}` → `h.DeleteAttachment`; evidence: server/go/cmd/server/router.go:2432, server/go/internal/handler/file.go:1464.

## auth

Destination: `server/src/workpal_backend/auth/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_auth_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /auth/send-code` → `h.SendCode`; evidence: server/go/cmd/server/router.go:1621, server/go/internal/handler/auth.go:320.

- [ ] `POST /auth/verify-code` → `h.VerifyCode`; evidence: server/go/cmd/server/router.go:1622, server/go/internal/handler/auth.go:412.

- [ ] `POST /auth/google` → `h.GoogleLogin`; evidence: server/go/cmd/server/router.go:1623, server/go/internal/handler/auth.go:571.

- [ ] `POST /auth/logout` → `h.Logout`; evidence: server/go/cmd/server/router.go:1624, server/go/internal/handler/auth.go:797.

- [ ] `POST /api/auth/refresh` → `h.RefreshSession`; evidence: server/go/cmd/server/router.go:1798, server/go/internal/handler/session.go:50.

## autopilots

Destination: `server/src/workpal_backend/autopilots/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_autopilots_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/autopilots` → `h.ListAutopilots`; evidence: server/go/cmd/server/router.go:2376, server/go/internal/handler/autopilot.go:447.

- [ ] `POST /api/autopilots` → `h.CreateAutopilot`; evidence: server/go/cmd/server/router.go:2377, server/go/internal/handler/autopilot.go:837.

- [ ] `GET /api/autopilots/cron-preview` → `h.CronPreview`; evidence: server/go/cmd/server/router.go:2378, server/go/internal/handler/autopilot_cron_preview.go:26.

- [ ] `GET /api/autopilots/usage` → `h.GetAutopilotQuotaUsage`; evidence: server/go/cmd/server/router.go:2379, server/go/internal/handler/autopilot.go:2491.

- [ ] `GET /api/autopilots/{id}` → `h.GetAutopilot`; evidence: server/go/cmd/server/router.go:2381, server/go/internal/handler/autopilot.go:546, server/go/cmd/server/private_project_realtime_test.go:102.

- [ ] `PATCH /api/autopilots/{id}` → `h.UpdateAutopilot`; evidence: server/go/cmd/server/router.go:2382, server/go/internal/handler/autopilot.go:1072.

- [ ] `DELETE /api/autopilots/{id}` → `h.DeleteAutopilot`; evidence: server/go/cmd/server/router.go:2383, server/go/internal/handler/autopilot.go:1386.

- [ ] `POST /api/autopilots/{id}/trigger` → `h.TriggerAutopilot`; evidence: server/go/cmd/server/router.go:2384, server/go/internal/handler/autopilot.go:2418.

- [ ] `GET /api/autopilots/{id}/runs` → `h.ListAutopilotRuns`; evidence: server/go/cmd/server/router.go:2385, server/go/internal/handler/autopilot.go:2309.

- [ ] `GET /api/autopilots/{id}/runs/{runId}` → `h.GetAutopilotRun`; evidence: server/go/cmd/server/router.go:2386, server/go/internal/handler/autopilot.go:2359.

- [ ] `GET /api/autopilots/{id}/deliveries` → `h.ListAutopilotDeliveries`; evidence: server/go/cmd/server/router.go:2387, server/go/internal/handler/webhook_delivery.go:164.

- [ ] `GET /api/autopilots/{id}/deliveries/{deliveryId}` → `h.GetAutopilotDelivery`; evidence: server/go/cmd/server/router.go:2388, server/go/internal/handler/webhook_delivery.go:212.

- [ ] `POST /api/autopilots/{id}/deliveries/{deliveryId}/replay` → `h.ReplayAutopilotDelivery`; evidence: server/go/cmd/server/router.go:2389, server/go/internal/handler/webhook_delivery.go:240.

- [ ] `POST /api/autopilots/{id}/triggers` → `h.CreateAutopilotTrigger`; evidence: server/go/cmd/server/router.go:2390, server/go/internal/handler/autopilot.go:1564.

- [ ] `PATCH /api/autopilots/{id}/triggers/{triggerId}` → `h.UpdateAutopilotTrigger`; evidence: server/go/cmd/server/router.go:2392, server/go/internal/handler/autopilot.go:1926.

- [ ] `DELETE /api/autopilots/{id}/triggers/{triggerId}` → `h.DeleteAutopilotTrigger`; evidence: server/go/cmd/server/router.go:2393, server/go/internal/handler/autopilot.go:2098.

- [ ] `POST /api/autopilots/{id}/triggers/{triggerId}/rotate-webhook-token` → `h.RotateAutopilotTriggerWebhookToken`; evidence: server/go/cmd/server/router.go:2394, server/go/internal/handler/autopilot.go:2175.

- [ ] `PUT /api/autopilots/{id}/triggers/{triggerId}/signing-secret` → `h.SetAutopilotTriggerSigningSecret`; evidence: server/go/cmd/server/router.go:2395, server/go/internal/handler/autopilot.go:2244.

- [ ] `POST /api/autopilots/{id}/collaborators` → `h.AddAutopilotCollaborator`; evidence: server/go/cmd/server/router.go:2397, server/go/internal/handler/autopilot.go:1470.

- [ ] `DELETE /api/autopilots/{id}/collaborators/{userId}` → `h.RemoveAutopilotCollaborator`; evidence: server/go/cmd/server/router.go:2398, server/go/internal/handler/autopilot.go:1529.

## avatars

Destination: `server/src/workpal_backend/avatars/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_avatars_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/avatars/{sig}/*` → `h.ServeAvatar`; evidence: server/go/cmd/server/router.go:1603, server/go/internal/handler/avatar.go:335.

## chat

Destination: `server/src/workpal_backend/chat/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_chat_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/chat/sessions` → `h.CreateChatSession`; evidence: server/go/cmd/server/router.go:2626, server/go/internal/handler/chat.go:40, server/go/internal/integrations/channel/engine/session.go:95, server/go/internal/integrations/channel/engine/session_test.go:150.

- [ ] `GET /api/chat/sessions` → `h.ListChatSessions`; evidence: server/go/cmd/server/router.go:2627, server/go/internal/handler/chat.go:158.

- [ ] `GET /api/chat/sessions/{sessionId}` → `h.GetChatSession`; evidence: server/go/cmd/server/router.go:2629, server/go/internal/handler/chat.go:324, server/go/internal/integrations/lark/outbound_test.go:94, server/go/internal/integrations/channel/engine/session.go:131, server/go/internal/integrations/channel/engine/router_test.go:462, server/go/internal/integrations/channel/engine/session_test.go:208, server/go/cmd/server/scope_authorizer_test.go:34, server/go/cmd/server/scope_authorizer_test.go:201, server/go/cmd/server/scope_authorizer_test.go:218.

- [ ] `PATCH /api/chat/sessions/{sessionId}` → `h.UpdateChatSession`; evidence: server/go/cmd/server/router.go:2630, server/go/internal/handler/chat.go:358.

- [ ] `PATCH /api/chat/sessions/{sessionId}/pin` → `h.SetChatSessionPinned`; evidence: server/go/cmd/server/router.go:2631, server/go/internal/handler/chat.go:484.

- [ ] `PATCH /api/chat/sessions/{sessionId}/archive` → `h.SetChatSessionArchived`; evidence: server/go/cmd/server/router.go:2632, server/go/internal/handler/chat.go:553.

- [ ] `DELETE /api/chat/sessions/{sessionId}` → `h.DeleteChatSession`; evidence: server/go/cmd/server/router.go:2633, server/go/internal/handler/chat.go:694.

- [ ] `POST /api/chat/sessions/{sessionId}/messages` → `h.SendChatMessage`; evidence: server/go/cmd/server/router.go:2634, server/go/internal/handler/chat.go:850.

- [ ] `POST /api/chat/sessions/{sessionId}/onboarding` → `h.StartMikaOnboarding`; evidence: server/go/cmd/server/router.go:2635, server/go/internal/handler/mika_onboarding.go:58.

- [ ] `POST /api/chat/sessions/{sessionId}/quick-actions/regenerate` → `h.RegenerateChatQuickActions`; evidence: server/go/cmd/server/router.go:2638, server/go/internal/handler/chat.go:1171, server/go/internal/service/task.go:2258.

- [ ] `GET /api/chat/sessions/{sessionId}/messages` → `h.ListChatMessages`; evidence: server/go/cmd/server/router.go:2639, server/go/internal/handler/chat.go:1247, server/go/internal/integrations/lark/http_client.go:686, server/go/internal/integrations/lark/outcome_replier_test.go:90, server/go/internal/integrations/lark/client.go:472, server/go/internal/integrations/lark/outbound_test.go:212, server/go/internal/integrations/lark/inbound_enricher_test.go:59, server/go/internal/integrations/lark/typing_indicator_test.go:63, server/go/internal/integrations/lark/inbound_enricher_budget_test.go:23.

- [ ] `GET /api/chat/sessions/{sessionId}/messages/page` → `h.ListChatMessagesPage`; evidence: server/go/cmd/server/router.go:2640, server/go/internal/handler/chat.go:1280.

- [ ] `GET /api/chat/sessions/{sessionId}/pending-task` → `h.GetPendingChatTask`; evidence: server/go/cmd/server/router.go:2641, server/go/internal/handler/chat.go:1685.

- [ ] `DELETE /api/chat/sessions/{sessionId}/queued-tasks` → `h.ClearQueuedChatTasks`; evidence: server/go/cmd/server/router.go:2642, server/go/internal/handler/chat.go:1838.

- [ ] `POST /api/chat/sessions/{sessionId}/queued-tasks/{taskId}/prioritize` → `h.PrioritizeQueuedChatTask`; evidence: server/go/cmd/server/router.go:2643, server/go/internal/handler/chat.go:1761.

- [ ] `POST /api/chat/sessions/{sessionId}/read` → `h.MarkChatSessionRead`; evidence: server/go/cmd/server/router.go:2644, server/go/internal/handler/chat.go:1402.

- [ ] `GET /api/chat/sessions/{sessionId}/draft-restores` → `h.ListChatDraftRestores`; evidence: server/go/cmd/server/router.go:2647, server/go/internal/handler/chat.go:1452.

- [ ] `DELETE /api/chat/sessions/{sessionId}/draft-restores/{restoreId}` → `h.ConsumeChatDraftRestore`; evidence: server/go/cmd/server/router.go:2648, server/go/internal/handler/chat.go:1514.

- [ ] `GET /api/chat/sessions/{sessionId}/wakeups` → `h.ListChatSessionWakeups`; evidence: server/go/cmd/server/router.go:2649, server/go/internal/handler/chat_wakeup.go:263.

- [ ] `POST /api/chat/sessions/{sessionId}/wakeups/{wakeupId}/cancel` → `h.CancelChatSessionWakeup`; evidence: server/go/cmd/server/router.go:2650, server/go/internal/handler/chat_wakeup.go:303.

- [ ] `POST /api/chat/sessions/{sessionId}/wakeups/{wakeupId}/retry` → `h.RetryChatSessionWakeup`; evidence: server/go/cmd/server/router.go:2651, server/go/internal/handler/chat_wakeup.go:317.

- [ ] `GET /api/chat/pending-tasks` → `h.ListPendingChatTasks`; evidence: server/go/cmd/server/router.go:2654, server/go/internal/handler/chat.go:1569.

- [ ] `GET /api/chat/pending-tasks/has-any` → `h.HasPendingChatTasks`; evidence: server/go/cmd/server/router.go:2655, server/go/internal/handler/chat.go:1639.

- [ ] `GET /api/chat/my-wakeups` → `h.ListMyChatWakeups`; evidence: server/go/cmd/server/router.go:2656, server/go/internal/handler/chat_wakeup.go:332.

- [ ] `GET /api/chat/pinned-agents` → `h.ListChatPinnedAgents`; evidence: server/go/cmd/server/router.go:2659, server/go/internal/handler/chat_pinned_agent.go:40.

- [ ] `POST /api/chat/pinned-agents` → `h.PinChatAgent`; evidence: server/go/cmd/server/router.go:2660, server/go/internal/handler/chat_pinned_agent.go:73.

- [ ] `DELETE /api/chat/pinned-agents/{agentId}` → `h.UnpinChatAgent`; evidence: server/go/cmd/server/router.go:2661, server/go/internal/handler/chat_pinned_agent.go:149.

- [ ] `GET /api/chat/history` → `h.GetChatChannelHistory`; evidence: server/go/cmd/server/router.go:2668, server/go/internal/handler/chat_history.go:65.

- [ ] `GET /api/chat/thread` → `h.GetChatThread`; evidence: server/go/cmd/server/router.go:2669, server/go/internal/handler/chat_history.go:210.

- [ ] `GET /api/chat/wakeups` → `h.ListChatTurnWakeups`; evidence: server/go/cmd/server/router.go:2673, server/go/internal/handler/chat_wakeup.go:155.

- [ ] `POST /api/chat/wakeups` → `h.CreateChatTurnWakeup`; evidence: server/go/cmd/server/router.go:2674, server/go/internal/handler/chat_wakeup.go:172.

- [ ] `PUT /api/chat/wakeups/{wakeupId}` → `h.UpdateChatTurnWakeup`; evidence: server/go/cmd/server/router.go:2675, server/go/internal/handler/chat_wakeup.go:198.

- [ ] `POST /api/chat/wakeups/{wakeupId}/cancel` → `h.CancelChatTurnWakeup`; evidence: server/go/cmd/server/router.go:2676, server/go/internal/handler/chat_wakeup.go:215.

- [ ] `POST /api/chat/wakeups/{wakeupId}/finish` → `h.FinishChatTurnWakeup`; evidence: server/go/cmd/server/router.go:2677, server/go/internal/handler/chat_wakeup.go:228.

- [ ] `POST /api/chat/wakeups/{wakeupId}/checkin` → `h.CheckInChatTurnWakeup`; evidence: server/go/cmd/server/router.go:2678, server/go/internal/handler/chat_wakeup.go:241.

## cli-token

Destination: `server/src/workpal_backend/cli_token/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_cli_token_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/cli-token` → `h.IssueCliToken`; evidence: server/go/cmd/server/router.go:1794, server/go/internal/handler/auth.go:767.

## client-usage

Destination: `server/src/workpal_backend/client_usage/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_client_usage_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/client-usage` → `h.UpsertClientUsage`; evidence: server/go/cmd/server/router.go:1801, server/go/internal/handler/client_usage.go:49.

## cloud-billing

Destination: `server/src/workpal_backend/cloud_billing/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_cloud_billing_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/cloud-billing/balance` → `h.GetCloudBillingBalance`; evidence: server/go/cmd/server/router.go:2113, server/go/internal/handler/cloud_billing.go:356.

- [ ] `GET /api/cloud-billing/transactions` → `h.ListCloudBillingTransactions`; evidence: server/go/cmd/server/router.go:2114, server/go/internal/handler/cloud_billing.go:366.

- [ ] `GET /api/cloud-billing/batches` → `h.ListCloudBillingBatches`; evidence: server/go/cmd/server/router.go:2115, server/go/internal/handler/cloud_billing.go:377.

- [ ] `GET /api/cloud-billing/topups` → `h.ListCloudBillingTopups`; evidence: server/go/cmd/server/router.go:2116, server/go/internal/handler/cloud_billing.go:385.

- [ ] `GET /api/cloud-billing/price-tiers` → `h.ListCloudBillingPriceTiers`; evidence: server/go/cmd/server/router.go:2117, server/go/internal/handler/cloud_billing.go:399.

- [ ] `POST /api/cloud-billing/checkout-sessions` → `h.CreateCloudBillingCheckoutSession`; evidence: server/go/cmd/server/router.go:2118, server/go/internal/handler/cloud_billing.go:410.

- [ ] `GET /api/cloud-billing/checkout-sessions/{sessionId}` → `h.GetCloudBillingCheckoutSession`; evidence: server/go/cmd/server/router.go:2119, server/go/internal/handler/cloud_billing.go:421.

- [ ] `POST /api/cloud-billing/portal-sessions` → `h.CreateCloudBillingPortalSession`; evidence: server/go/cmd/server/router.go:2120, server/go/internal/handler/cloud_billing.go:476.

## cloud-runtime

Destination: `server/src/workpal_backend/cloud_runtime/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_cloud_runtime_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/cloud-runtime` → `h.GetCloudRuntimeService`; evidence: server/go/cmd/server/router.go:2587, server/go/internal/handler/cloud_runtime.go:26.

- [ ] `GET /api/cloud-runtime/healthz` → `h.GetCloudRuntimeHealth`; evidence: server/go/cmd/server/router.go:2588, server/go/internal/handler/cloud_runtime.go:32.

- [ ] `GET /api/cloud-runtime/readyz` → `h.GetCloudRuntimeReady`; evidence: server/go/cmd/server/router.go:2589, server/go/internal/handler/cloud_runtime.go:36.

- [ ] `GET /api/cloud-runtime/nodes` → `h.ListCloudRuntimeNodes`; evidence: server/go/cmd/server/router.go:2590, server/go/internal/handler/cloud_runtime.go:40.

- [ ] `POST /api/cloud-runtime/nodes` → `h.CreateCloudRuntimeNode`; evidence: server/go/cmd/server/router.go:2591, server/go/internal/handler/cloud_runtime.go:47.

- [ ] `DELETE /api/cloud-runtime/nodes` → `h.DeleteCloudRuntimeNode`; evidence: server/go/cmd/server/router.go:2592, server/go/internal/handler/cloud_runtime.go:61.

- [ ] `POST /api/cloud-runtime/nodes/start` → `h.StartCloudRuntimeNode`; evidence: server/go/cmd/server/router.go:2593, server/go/internal/handler/cloud_runtime.go:68.

- [ ] `POST /api/cloud-runtime/nodes/stop` → `h.StopCloudRuntimeNode`; evidence: server/go/cmd/server/router.go:2594, server/go/internal/handler/cloud_runtime.go:75.

- [ ] `POST /api/cloud-runtime/nodes/reboot` → `h.RebootCloudRuntimeNode`; evidence: server/go/cmd/server/router.go:2595, server/go/internal/handler/cloud_runtime.go:82.

- [ ] `POST /api/cloud-runtime/nodes/status` → `h.GetCloudRuntimeNodeStatus`; evidence: server/go/cmd/server/router.go:2596, server/go/internal/handler/cloud_runtime.go:89.

- [ ] `POST /api/cloud-runtime/nodes/exec` → `h.ExecCloudRuntimeNode`; evidence: server/go/cmd/server/router.go:2597, server/go/internal/handler/cloud_runtime.go:96.

## cloud-subscriptions

Destination: `server/src/workpal_backend/cloud_subscriptions/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_cloud_subscriptions_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/cloud-subscriptions/summary` → `h.GetCloudWorkspaceSubscriptionSummary`; evidence: server/go/cmd/server/router.go:2134, server/go/internal/handler/cloud_billing.go:169.

- [ ] `GET /api/cloud-subscriptions/prices` → `h.GetCloudWorkspaceSubscriptionPrices`; evidence: server/go/cmd/server/router.go:2135, server/go/internal/handler/cloud_billing.go:185.

- [ ] `POST /api/cloud-subscriptions/checkout-sessions` → `h.CreateCloudWorkspaceSubscriptionCheckout`; evidence: server/go/cmd/server/router.go:2139, server/go/internal/handler/cloud_billing.go:197.

- [ ] `POST /api/cloud-subscriptions/seats/purchase-preview` → `h.PreviewCloudWorkspaceSubscriptionSeatPurchase`; evidence: server/go/cmd/server/router.go:2140, server/go/internal/handler/cloud_billing.go:260.

- [ ] `POST /api/cloud-subscriptions/seats/purchases` → `h.PurchaseCloudWorkspaceSubscriptionSeats`; evidence: server/go/cmd/server/router.go:2141, server/go/internal/handler/cloud_billing.go:290.

- [ ] `POST /api/cloud-subscriptions/seats/reconcile` → `h.ReconcileCloudWorkspaceSubscriptionSeats`; evidence: server/go/cmd/server/router.go:2142, server/go/internal/handler/cloud_billing.go:249.

- [ ] `POST /api/cloud-subscriptions/portal-sessions` → `h.CreateCloudWorkspaceSubscriptionPortal`; evidence: server/go/cmd/server/router.go:2143, server/go/internal/handler/cloud_billing.go:341.

## comments

Destination: `server/src/workpal_backend/comments/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_comments_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/comments/{commentId}/sub-issue-preview` → `h.PreviewCommentSubIssue`; evidence: server/go/cmd/server/router.go:2436, server/go/internal/handler/source_context.go:430.

- [ ] `POST /api/comments/{commentId}/sub-issues` → `h.CreateCommentSubIssue`; evidence: server/go/cmd/server/router.go:2437, server/go/internal/handler/source_context.go:470.

- [ ] `PUT /api/comments/{commentId}` → `h.UpdateComment`; evidence: server/go/cmd/server/router.go:2438, server/go/internal/handler/comment.go:3351.

- [ ] `DELETE /api/comments/{commentId}` → `h.DeleteComment`; evidence: server/go/cmd/server/router.go:2439, server/go/internal/handler/comment.go:3634.

- [ ] `DELETE /api/comments/{commentId}/keep-replies` → `h.DeleteComment`; evidence: server/go/cmd/server/router.go:2445, server/go/internal/handler/comment.go:3634.

- [ ] `POST /api/comments/{commentId}/resolve` → `h.ResolveComment`; evidence: server/go/cmd/server/router.go:2446, server/go/internal/handler/comment.go:4092.

- [ ] `DELETE /api/comments/{commentId}/resolve` → `h.UnresolveComment`; evidence: server/go/cmd/server/router.go:2447, server/go/internal/handler/comment.go:4179.

- [ ] `POST /api/comments/{commentId}/reactions` → `h.AddReaction`; evidence: server/go/cmd/server/router.go:2448, server/go/internal/handler/reaction.go:53.

- [ ] `DELETE /api/comments/{commentId}/reactions` → `h.RemoveReaction`; evidence: server/go/cmd/server/router.go:2449, server/go/internal/handler/reaction.go:146.

## config

Destination: `server/src/workpal_backend/config/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_config_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/config` → `h.GetConfig`; evidence: server/go/cmd/server/router.go:1627, server/go/internal/handler/config.go:130.

## contact-sales

Destination: `server/src/workpal_backend/contact_sales/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_contact_sales_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/contact-sales` → `h.CreateContactSales`; evidence: server/go/cmd/server/router.go:1628, server/go/internal/handler/contact_sales.go:121.

## contribution

Destination: `server/src/workpal_backend/contribution/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_contribution_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/dashboard/contribution` → `local extension`; evidence: server/api.mjs, server/contribution.mjs.

- [ ] `PUT /api/dashboard/contribution` → `local extension`; evidence: server/api.mjs, server/contribution.mjs.

## daemon

Destination: `server/src/workpal_backend/daemon/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_daemon_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/daemon/register` → `h.DaemonRegister`; evidence: server/go/cmd/server/router.go:1679, server/go/internal/handler/daemon.go:594.

- [ ] `POST /api/daemon/deregister` → `h.DaemonDeregister`; evidence: server/go/cmd/server/router.go:1680, server/go/internal/handler/daemon.go:1360.

- [ ] `POST /api/daemon/heartbeat` → `h.DaemonHeartbeat`; evidence: server/go/cmd/server/router.go:1681, server/go/internal/handler/daemon.go:1510.

- [ ] `GET /api/daemon/ws` → `h.DaemonWebSocket`; evidence: server/go/cmd/server/router.go:1682, server/go/internal/handler/daemon_ws.go:13.

- [ ] `GET /api/daemon/workspaces` → `h.ListDaemonWorkspaces`; evidence: server/go/cmd/server/router.go:1683, server/go/internal/handler/daemon_workspace.go:27.

- [ ] `GET /api/daemon/workspaces/{workspaceId}/repos` → `h.GetDaemonWorkspaceRepos`; evidence: server/go/cmd/server/router.go:1684, server/go/internal/handler/daemon.go:1330.

- [ ] `GET /api/daemon/workspaces/{workspaceId}/runtime-profiles` → `h.DaemonListRuntimeProfiles`; evidence: server/go/cmd/server/router.go:1685, server/go/internal/handler/runtime_profile.go:714.

- [ ] `POST /api/daemon/tasks/{id}/plugin-hooks` → `h.InvokeAgentPluginHook`; evidence: server/go/cmd/server/router.go:1690, server/go/internal/handler/plugin_agent_hook.go:29, server/go/internal/daemon/client.go:1557.

- [ ] `GET /api/daemon/tasks/{id}/plugin-mcp/{contributionId}/credential` → `h.ResolvePluginMCPCredential`; evidence: server/go/cmd/server/router.go:1693, server/go/internal/handler/plugin_mcp.go:134.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/tasks/claim` → `h.ClaimTaskByRuntime`; evidence: server/go/cmd/server/router.go:1695, server/go/internal/handler/daemon.go:4415.

- [ ] `POST /api/daemon/tasks/claim` → `h.ClaimTasksByRuntime`; evidence: server/go/cmd/server/router.go:1699, server/go/internal/handler/daemon.go:2127.

- [ ] `POST /api/daemon/claim` → `h.ClaimTasksByRuntime`; evidence: server/go/cmd/server/router.go:1700, server/go/internal/handler/daemon.go:2127.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/tasks/{taskId}/prepare-lease` → `h.ExtendTaskPrepareLease`; evidence: server/go/cmd/server/router.go:1701, server/go/internal/handler/daemon.go:4749, server/go/internal/daemon/client.go:468, server/go/internal/service/task.go:4707.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/tasks/{taskId}/skill-bundles/resolve` → `h.ResolveTaskSkillBundles`; evidence: server/go/cmd/server/router.go:1702, server/go/internal/handler/daemon.go:4617.

- [ ] `GET /api/daemon/runtimes/{runtimeId}/tasks/pending` → `h.ListPendingTasksByRuntime`; evidence: server/go/cmd/server/router.go:1703, server/go/internal/handler/daemon.go:4722.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/update/{updateId}/result` → `h.ReportUpdateResult`; evidence: server/go/cmd/server/router.go:1704, server/go/internal/handler/runtime_update.go:290, server/go/internal/daemon/client.go:909.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/models/{requestId}/result` → `h.ReportModelListResult`; evidence: server/go/cmd/server/router.go:1705, server/go/internal/handler/runtime_models.go:481, server/go/internal/daemon/client.go:914.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/local-skills/{requestId}/result` → `h.ReportLocalSkillListResult`; evidence: server/go/cmd/server/router.go:1706, server/go/internal/handler/runtime_local_skills.go:737, server/go/internal/daemon/client.go:919.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/local-skills/import/{requestId}/result` → `h.ReportLocalSkillImportResult`; evidence: server/go/cmd/server/router.go:1707, server/go/internal/handler/runtime_local_skills.go:803, server/go/internal/daemon/client.go:924.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/environment-commands/claim` → `h.ClaimEnvironmentCommands`; evidence: server/go/cmd/server/router.go:1708, server/go/internal/handler/issue_environment_control.go:425, server/go/internal/daemon/client.go:793, server/go/internal/daemon/environment_commands_unix_test.go:28.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/environment-commands/{commandId}/result` → `h.ReportEnvironmentCommandResult`; evidence: server/go/cmd/server/router.go:1709, server/go/internal/handler/issue_environment_control.go:456, server/go/internal/daemon/client.go:803, server/go/internal/daemon/environment_commands_unix_test.go:36.

- [ ] `GET /api/daemon/tasks/{taskId}/status` → `h.GetTaskStatus`; evidence: server/go/cmd/server/router.go:1711, server/go/internal/handler/daemon.go:5739, server/go/internal/daemon/client.go:876.

- [ ] `POST /api/daemon/tasks/{taskId}/start` → `h.StartTask`; evidence: server/go/cmd/server/router.go:1712, server/go/internal/handler/daemon.go:4777, server/go/internal/daemon/client.go:515, server/go/internal/service/task.go:4613.

- [ ] `POST /api/daemon/tasks/{taskId}/supplements/claim` → `h.ClaimTaskSupplement`; evidence: server/go/cmd/server/router.go:1713, server/go/internal/handler/task_supplement.go:469, server/go/internal/daemon/client.go:479.

- [ ] `POST /api/daemon/tasks/{taskId}/supplements/{commentId}/ack` → `h.AckTaskSupplement`; evidence: server/go/cmd/server/router.go:1714, server/go/internal/handler/task_supplement.go:512, server/go/internal/daemon/client.go:492.

- [ ] `POST /api/daemon/tasks/{taskId}/wait-local-directory` → `h.MarkTaskWaitingLocalDirectory`; evidence: server/go/cmd/server/router.go:1715, server/go/internal/handler/daemon.go:4909, server/go/internal/daemon/client.go:574, server/go/internal/service/task.go:4734.

- [ ] `POST /api/daemon/tasks/{taskId}/progress` → `h.ReportTaskProgress`; evidence: server/go/cmd/server/router.go:1716, server/go/internal/handler/daemon.go:4942.

- [ ] `POST /api/daemon/tasks/{taskId}/complete` → `h.CompleteTask`; evidence: server/go/cmd/server/router.go:1717, server/go/internal/handler/daemon.go:5019, server/go/internal/daemon/client.go:672, server/go/internal/service/task.go:4833.

- [ ] `POST /api/daemon/tasks/{taskId}/fail` → `h.FailTask`; evidence: server/go/cmd/server/router.go:1718, server/go/internal/handler/daemon.go:5803, server/go/internal/daemon/client.go:817, server/go/internal/service/task.go:5279.

- [ ] `POST /api/daemon/tasks/{taskId}/usage` → `h.ReportTaskUsage`; evidence: server/go/cmd/server/router.go:1719, server/go/internal/handler/daemon.go:5632, server/go/internal/daemon/client.go:699.

- [ ] `POST /api/daemon/tasks/{taskId}/environments` → `h.ReportTaskEnvironments`; evidence: server/go/cmd/server/router.go:1720, server/go/internal/handler/issue_environment.go:168, server/go/internal/daemon/client.go:733, server/go/internal/daemon/environments_test.go:32.

- [ ] `POST /api/daemon/tasks/{taskId}/environment-configs` → `h.ReportTaskEnvironmentConfigs`; evidence: server/go/cmd/server/router.go:1721, server/go/internal/handler/issue_environment_control.go:555, server/go/internal/daemon/client.go:745, server/go/internal/daemon/environment_commands_unix_test.go:43.

- [ ] `POST /api/daemon/tasks/{taskId}/context-receipt` → `h.ReportTaskContextReceipt`; evidence: server/go/cmd/server/router.go:1722, server/go/internal/handler/task_context_receipt.go:88, server/go/internal/daemon/client.go:757.

- [ ] `POST /api/daemon/tasks/{taskId}/rate-limits` → `h.ReportTaskRateLimits`; evidence: server/go/cmd/server/router.go:1723, server/go/internal/handler/runtime_rate_limit.go:117, server/go/internal/daemon/client.go:766.

- [ ] `POST /api/daemon/tasks/{taskId}/messages` → `h.ReportTaskMessages`; evidence: server/go/cmd/server/router.go:1724, server/go/internal/handler/daemon.go:5894, server/go/internal/daemon/client.go:666.

- [ ] `GET /api/daemon/tasks/{taskId}/messages` → `h.ListTaskMessages`; evidence: server/go/cmd/server/router.go:1725, server/go/internal/handler/daemon.go:6267.

- [ ] `POST /api/daemon/tasks/{taskId}/cancel-ack` → `h.AckTaskCancelled`; evidence: server/go/cmd/server/router.go:1726, server/go/internal/handler/daemon.go:6088, server/go/internal/daemon/client.go:615.

- [ ] `POST /api/daemon/workspaces/{workspaceId}/issues/gc-check` → `h.BatchIssueGCCheck`; evidence: server/go/cmd/server/router.go:1728, server/go/internal/handler/daemon.go:6902.

- [ ] `GET /api/daemon/issues/{issueId}/gc-check` → `h.GetIssueGCCheck`; evidence: server/go/cmd/server/router.go:1729, server/go/internal/handler/daemon.go:7004, server/go/internal/daemon/client.go:1126.

- [ ] `GET /api/daemon/chat-sessions/{sessionId}/gc-check` → `h.GetChatSessionGCCheck`; evidence: server/go/cmd/server/router.go:1730, server/go/internal/handler/daemon.go:7052, server/go/internal/daemon/client.go:1144.

- [ ] `GET /api/daemon/autopilot-runs/{runId}/gc-check` → `h.GetAutopilotRunGCCheck`; evidence: server/go/cmd/server/router.go:1731, server/go/internal/handler/daemon.go:7079, server/go/internal/daemon/client.go:1163.

- [ ] `GET /api/daemon/tasks/{taskId}/gc-check` → `h.GetTaskGCCheck`; evidence: server/go/cmd/server/router.go:1732, server/go/internal/handler/daemon.go:7110, server/go/internal/daemon/client.go:1180.

- [ ] `POST /api/daemon/runtimes/{runtimeId}/recover-orphans` → `h.RecoverOrphanedTasks`; evidence: server/go/cmd/server/router.go:1734, server/go/internal/handler/task_lifecycle.go:28.

- [ ] `POST /api/daemon/tasks/{taskId}/session` → `h.PinTaskSession`; evidence: server/go/cmd/server/router.go:1735, server/go/internal/handler/task_lifecycle.go:71, server/go/internal/daemon/client.go:852.

## dashboard

Destination: `server/src/workpal_backend/dashboard/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_dashboard_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/dashboard/usage/daily` → `h.GetDashboardUsageDaily`; evidence: server/go/cmd/server/router.go:2537, server/go/internal/handler/dashboard.go:193.

- [ ] `GET /api/dashboard/usage/by-agent` → `h.GetDashboardUsageByAgent`; evidence: server/go/cmd/server/router.go:2538, server/go/internal/handler/dashboard.go:280.

- [ ] `GET /api/dashboard/agent-runtime` → `h.GetDashboardAgentRunTime`; evidence: server/go/cmd/server/router.go:2539, server/go/internal/handler/dashboard.go:405.

- [ ] `GET /api/dashboard/runtime/daily` → `h.GetDashboardRunTimeDaily`; evidence: server/go/cmd/server/router.go:2540, server/go/internal/handler/dashboard.go:498.

- [ ] `GET /api/dashboard/failures/daily` → `h.GetDashboardFailuresDaily`; evidence: server/go/cmd/server/router.go:2541, server/go/internal/handler/dashboard.go:566.

- [ ] `GET /api/dashboard/failures/by-agent` → `h.GetDashboardFailuresByAgent`; evidence: server/go/cmd/server/router.go:2542, server/go/internal/handler/dashboard.go:616.

## dingtalk

Destination: `server/src/workpal_backend/dingtalk/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_dingtalk_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/dingtalk/binding/redeem` → `h.RedeemDingTalkBindingToken`; evidence: server/go/cmd/server/router.go:2045, server/go/internal/handler/dingtalk.go:737.

## feedback

Destination: `server/src/workpal_backend/feedback/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_feedback_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/feedback` → `h.CreateFeedback`; evidence: server/go/cmd/server/router.go:1800, server/go/internal/handler/feedback.go:66.

## files

Destination: `server/src/workpal_backend/files/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_files_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/bootstrap` → `local extension`; evidence: server/api.mjs, server/contribution.mjs.

- [ ] `GET /api/files/{id}` → `local extension`; evidence: server/api.mjs, server/contribution.mjs.

## github

Destination: `server/src/workpal_backend/github/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_github_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/github/setup` → `h.GitHubSetupCallback`; evidence: server/go/cmd/server/router.go:1644, server/go/internal/handler/github.go:488.

## health

Destination: `server/src/workpal_backend/health/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_health_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /health` → `health.liveHandler`; evidence: server/go/cmd/server/router.go:1555, server/go/cmd/server/health.go:85.

- [ ] `GET /health/realtime` → `realtimeMetricsHandler(os.Getenv("REALTIME_METRICS_TOKEN"`; evidence: server/go/cmd/server/router.go:1568.

## healthz

Destination: `server/src/workpal_backend/healthz/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_healthz_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /healthz` → `health.readyHandler`; evidence: server/go/cmd/server/router.go:1557, server/go/cmd/server/health.go:93.

## inbox

Destination: `server/src/workpal_backend/inbox/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_inbox_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/inbox` → `h.ListInbox`; evidence: server/go/cmd/server/router.go:2709, server/go/internal/handler/inbox.go:200.

- [ ] `GET /api/inbox/archived` → `h.ListArchivedInbox`; evidence: server/go/cmd/server/router.go:2713, server/go/internal/handler/inbox.go:304.

- [ ] `GET /api/inbox/archived/page` → `h.ListArchivedInboxPage`; evidence: server/go/cmd/server/router.go:2714, server/go/internal/handler/inbox_archive.go:143.

- [ ] `GET /api/inbox/archived/facets` → `h.GetArchivedInboxFacets`; evidence: server/go/cmd/server/router.go:2715, server/go/internal/handler/inbox_archive.go:244.

- [ ] `GET /api/inbox/unread-count` → `h.CountUnreadInbox`; evidence: server/go/cmd/server/router.go:2716, server/go/internal/handler/inbox.go:503.

- [ ] `GET /api/inbox/unread-summary` → `h.UnreadInboxSummary`; evidence: server/go/cmd/server/router.go:2719, server/go/internal/handler/inbox.go:549.

- [ ] `POST /api/inbox/mark-all-read` → `h.MarkAllInboxRead`; evidence: server/go/cmd/server/router.go:2720, server/go/internal/handler/inbox.go:579.

- [ ] `POST /api/inbox/archive-all` → `h.ArchiveAllInbox`; evidence: server/go/cmd/server/router.go:2721, server/go/internal/handler/inbox.go:652.

- [ ] `POST /api/inbox/archive-all-read` → `h.ArchiveAllReadInbox`; evidence: server/go/cmd/server/router.go:2722, server/go/internal/handler/inbox.go:681.

- [ ] `POST /api/inbox/archive-completed` → `h.ArchiveCompletedInbox`; evidence: server/go/cmd/server/router.go:2723, server/go/internal/handler/inbox.go:710.

- [ ] `GET /api/inbox/snoozed` → `h.ListSnoozedInbox`; evidence: server/go/cmd/server/router.go:2725, server/go/internal/handler/inbox_snooze.go:29.

- [ ] `POST /api/inbox/issues/{issueId}/read` → `h.MarkIssueInboxRead`; evidence: server/go/cmd/server/router.go:2728, server/go/internal/handler/inbox.go:614.

- [ ] `POST /api/inbox/{id}/read` → `h.MarkInboxRead`; evidence: server/go/cmd/server/router.go:2729, server/go/internal/handler/inbox.go:349.

- [ ] `POST /api/inbox/{id}/unread` → `h.MarkInboxUnread`; evidence: server/go/cmd/server/router.go:2730, server/go/internal/handler/inbox.go:379.

- [ ] `POST /api/inbox/{id}/archive` → `h.ArchiveInboxItem`; evidence: server/go/cmd/server/router.go:2731, server/go/internal/handler/inbox.go:427.

- [ ] `POST /api/inbox/{id}/unarchive` → `h.UnarchiveInboxItem`; evidence: server/go/cmd/server/router.go:2732, server/go/internal/handler/inbox.go:469.

- [ ] `POST /api/inbox/{id}/snooze` → `h.SnoozeInboxItem`; evidence: server/go/cmd/server/router.go:2733, server/go/internal/handler/inbox_snooze.go:77.

- [ ] `POST /api/inbox/{id}/unsnooze` → `h.UnsnoozeInboxItem`; evidence: server/go/cmd/server/router.go:2734, server/go/internal/handler/inbox_snooze.go:141.

- [ ] `DELETE /api/inbox/{id}` → `h.DeleteInboxItem`; evidence: server/go/cmd/server/router.go:2735, server/go/internal/handler/inbox.go:402.

## integrations

Destination: `server/src/workpal_backend/integrations/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_integrations_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/integrations/composio/callback` → `h.ComposioCallback`; evidence: server/go/cmd/server/router.go:1670, server/go/internal/handler/integrations_composio.go:112.

- [ ] `POST /api/integrations/composio/connect/init` → `h.ComposioConnectInit`; evidence: server/go/cmd/server/router.go:2061, server/go/internal/handler/integrations_composio.go:66.

- [ ] `GET /api/integrations/composio/toolkits` → `h.ListComposioToolkits`; evidence: server/go/cmd/server/router.go:2062, server/go/internal/handler/integrations_composio.go:179.

- [ ] `GET /api/integrations/composio/connections` → `h.ListComposioConnections`; evidence: server/go/cmd/server/router.go:2063, server/go/internal/handler/integrations_composio.go:140.

- [ ] `DELETE /api/integrations/composio/connections/{id}` → `h.DeleteComposioConnection`; evidence: server/go/cmd/server/router.go:2064, server/go/internal/handler/integrations_composio.go:208.

## invitations

Destination: `server/src/workpal_backend/invitations/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_invitations_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/invitations` → `h.ListMyInvitations`; evidence: server/go/cmd/server/router.go:2068, server/go/internal/handler/invitation.go:397.

- [ ] `GET /api/invitations/{id}` → `h.GetMyInvitation`; evidence: server/go/cmd/server/router.go:2069, server/go/internal/handler/invitation.go:352.

- [ ] `POST /api/invitations/{id}/accept` → `h.AcceptInvitation`; evidence: server/go/cmd/server/router.go:2070, server/go/internal/handler/invitation.go:443.

- [ ] `POST /api/invitations/{id}/decline` → `h.DeclineInvitation`; evidence: server/go/cmd/server/router.go:2071, server/go/internal/handler/invitation.go:626.

## issue-statuses

Destination: `server/src/workpal_backend/issue_statuses/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_issue_statuses_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/issue-statuses` → `h.ListIssueStatuses`; evidence: server/go/cmd/server/router.go:2294, server/go/internal/handler/issue_status.go:99.

- [ ] `POST /api/issue-statuses` → `h.CreateIssueStatus`; evidence: server/go/cmd/server/router.go:2295, server/go/internal/handler/issue_status.go:140.

- [ ] `PATCH /api/issue-statuses/reorder` → `h.ReorderIssueStatuses`; evidence: server/go/cmd/server/router.go:2296, server/go/internal/handler/issue_status.go:574.

- [ ] `PATCH /api/issue-statuses/{id}` → `h.UpdateIssueStatus`; evidence: server/go/cmd/server/router.go:2298, server/go/internal/handler/issue_status.go:301.

- [ ] `DELETE /api/issue-statuses/{id}` → `h.ArchiveIssueStatus`; evidence: server/go/cmd/server/router.go:2299, server/go/internal/handler/issue_status.go:401.

## issue-view-preferences

Destination: `server/src/workpal_backend/issue_view_preferences/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_issue_view_preferences_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/issue-view-preferences` → `h.GetIssueViewPreference`; evidence: server/go/cmd/server/router.go:2411, server/go/internal/handler/issue_view_preference.go:64.

- [ ] `PUT /api/issue-view-preferences` → `h.PutIssueViewPreference`; evidence: server/go/cmd/server/router.go:2412, server/go/internal/handler/issue_view_preference.go:112.

## issue-views

Destination: `server/src/workpal_backend/issue_views/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_issue_views_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/issue-views` → `h.ListIssueViews`; evidence: server/go/cmd/server/router.go:2414, server/go/internal/handler/issue_view.go:265.

- [ ] `POST /api/issue-views` → `h.CreateIssueView`; evidence: server/go/cmd/server/router.go:2415, server/go/internal/handler/issue_view.go:150.

- [ ] `GET /api/issue-views/{id}` → `h.GetIssueViewByID`; evidence: server/go/cmd/server/router.go:2417, server/go/internal/handler/issue_view.go:355.

- [ ] `GET /api/issue-views/{id}/issues` → `h.ListIssueViewIssues`; evidence: server/go/cmd/server/router.go:2418, server/go/internal/handler/issue_view_issues.go:525.

- [ ] `PATCH /api/issue-views/{id}` → `h.UpdateIssueView`; evidence: server/go/cmd/server/router.go:2419, server/go/internal/handler/issue_view.go:401.

- [ ] `DELETE /api/issue-views/{id}` → `h.DeleteIssueView`; evidence: server/go/cmd/server/router.go:2420, server/go/internal/handler/issue_view.go:503.

## issue-wakeup-paused

Destination: `server/src/workpal_backend/issue_wakeup_paused/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_issue_wakeup_paused_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/issue-wakeup-paused` → `h.ListPausedWakeups`; evidence: server/go/cmd/server/router.go:2609, server/go/internal/handler/issue_wakeup.go:478.

## issue-wakeup-summaries

Destination: `server/src/workpal_backend/issue_wakeup_summaries/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_issue_wakeup_summaries_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/issue-wakeup-summaries` → `h.ListWorkspaceWakeupSummaries`; evidence: server/go/cmd/server/router.go:2607, server/go/internal/handler/issue_wakeup.go:163.

## issue-wakeups

Destination: `server/src/workpal_backend/issue_wakeups/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_issue_wakeups_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/issue-wakeups` → `h.ListWorkspaceWakeups`; evidence: server/go/cmd/server/router.go:2608, server/go/internal/handler/issue_wakeup.go:18.

## issue-workflows

Destination: `server/src/workpal_backend/issue_workflows/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_issue_workflows_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/issue-workflows` → `h.ListIssueWorkflows`; evidence: server/go/cmd/server/router.go:2308, server/go/internal/handler/issue_workflow.go:212.

- [ ] `POST /api/issue-workflows` → `h.CreateIssueWorkflow`; evidence: server/go/cmd/server/router.go:2309, server/go/internal/handler/issue_workflow.go:478.

- [ ] `GET /api/issue-workflows/{id}` → `h.GetIssueWorkflow`; evidence: server/go/cmd/server/router.go:2311, server/go/internal/handler/issue_workflow.go:255.

- [ ] `PATCH /api/issue-workflows/{id}` → `h.UpdateIssueWorkflow`; evidence: server/go/cmd/server/router.go:2312, server/go/internal/handler/issue_workflow.go:657.

- [ ] `DELETE /api/issue-workflows/{id}` → `h.DeleteIssueWorkflow`; evidence: server/go/cmd/server/router.go:2313, server/go/internal/handler/issue_workflow.go:827.

- [ ] `PUT /api/issue-workflows/{id}/handoffs/{status}` → `h.SetIssueWorkflowHandoff`; evidence: server/go/cmd/server/router.go:2314, server/go/internal/handler/issue_workflow.go:1096.

- [ ] `POST /api/issue-workflows/{id}/brief` → `h.PreviewIssueWorkflowBrief`; evidence: server/go/cmd/server/router.go:2315, server/go/internal/handler/issue_workflow.go:1283.

## issues

Destination: `server/src/workpal_backend/issues/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_issues_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/issues/table/groups` → `h.ListIssueTableGroups`; evidence: server/go/cmd/server/router.go:2166, server/go/internal/handler/issue_table_group.go:899.

- [ ] `POST /api/issues/table/rows` → `h.ListIssueTableRows`; evidence: server/go/cmd/server/router.go:2167, server/go/internal/handler/issue_table_rows.go:233.

- [ ] `POST /api/issues/table/facets` → `h.ListIssueTableFacets`; evidence: server/go/cmd/server/router.go:2168, server/go/internal/handler/issue_table_facets.go:372.

- [ ] `GET /api/issues/search` → `h.SearchIssues`; evidence: server/go/cmd/server/router.go:2169, server/go/internal/handler/issue.go:1156.

- [ ] `GET /api/issues/child-progress` → `h.ChildIssueProgress`; evidence: server/go/cmd/server/router.go:2170, server/go/internal/handler/issue.go:2777.

- [ ] `GET /api/issues/pull-requests` → `h.ListIssuePullRequestSummaries`; evidence: server/go/cmd/server/router.go:2171, server/go/internal/handler/github.go:1209.

- [ ] `GET /api/issues/children` → `h.ListChildrenByParents`; evidence: server/go/cmd/server/router.go:2172, server/go/internal/handler/issue.go:2699.

- [ ] `GET /api/issues/grouped` → `h.ListGroupedIssues`; evidence: server/go/cmd/server/router.go:2173, server/go/internal/handler/issue.go:2086.

- [ ] `GET /api/issues/unread` → `h.ListIssueUnread`; evidence: server/go/cmd/server/router.go:2176, server/go/internal/handler/issue_unread.go:29.

- [ ] `GET /api/issues/subscribed` → `h.ListSubscribedIssueIDs`; evidence: server/go/cmd/server/router.go:2179, server/go/internal/handler/subscriber.go:139.

- [ ] `GET /api/issues` → `h.ListIssues`; evidence: server/go/cmd/server/router.go:2180, server/go/internal/handler/issue.go:1347.

- [ ] `POST /api/issues/query` → `h.QueryIssues`; evidence: server/go/cmd/server/router.go:2183, server/go/internal/handler/issue.go:1333.

- [ ] `POST /api/issues` → `h.CreateIssue`; evidence: server/go/cmd/server/router.go:2184, server/go/internal/handler/issue.go:3363.

- [ ] `POST /api/issues/quick-create` → `h.QuickCreateIssue`; evidence: server/go/cmd/server/router.go:2185, server/go/internal/handler/issue.go:2861.

- [ ] `POST /api/issues/preview-trigger` → `h.PreviewIssueTrigger`; evidence: server/go/cmd/server/router.go:2186, server/go/internal/handler/issue_trigger.go:150.

- [ ] `POST /api/issues/batch-update` → `h.BatchUpdateIssues`; evidence: server/go/cmd/server/router.go:2187, server/go/internal/handler/issue.go:4804.

- [ ] `POST /api/issues/batch-delete` → `h.BatchDeleteIssues`; evidence: server/go/cmd/server/router.go:2188, server/go/internal/handler/issue.go:5306.

- [ ] `GET /api/issues/{id}` → `h.GetIssue`; evidence: server/go/cmd/server/router.go:2190, server/go/internal/handler/issue.go:2576, server/go/cmd/server/scope_authorizer_test.go:28, server/go/cmd/server/scope_authorizer_test.go:198, server/go/cmd/server/scope_authorizer_test.go:215.

- [ ] `PUT /api/issues/{id}` → `h.UpdateIssue`; evidence: server/go/cmd/server/router.go:2191, server/go/internal/handler/issue.go:4002.

- [ ] `POST /api/issues/{id}/move` → `h.MoveIssue`; evidence: server/go/cmd/server/router.go:2192, server/go/internal/handler/issue_move.go:37.

- [ ] `DELETE /api/issues/{id}` → `h.DeleteIssue`; evidence: server/go/cmd/server/router.go:2193, server/go/internal/handler/issue.go:4617.

- [ ] `POST /api/issues/{id}/comments/trigger-preview` → `h.PreviewCommentTriggers`; evidence: server/go/cmd/server/router.go:2194, server/go/internal/handler/comment.go:1542.

- [ ] `POST /api/issues/{id}/comments` → `h.CreateComment`; evidence: server/go/cmd/server/router.go:2195, server/go/internal/handler/comment.go:1659.

- [ ] `GET /api/issues/{id}/comments` → `h.ListComments`; evidence: server/go/cmd/server/router.go:2196, server/go/internal/handler/comment.go:349.

- [ ] `GET /api/issues/{id}/timeline` → `h.ListTimeline`; evidence: server/go/cmd/server/router.go:2197, server/go/internal/handler/activity.go:156.

- [ ] `GET /api/issues/{id}/workflow-handoff` → `h.PreviewWorkflowHandoff`; evidence: server/go/cmd/server/router.go:2198, server/go/internal/handler/issue_workflow.go:1397.

- [ ] `GET /api/issues/{id}/subscribers` → `h.ListIssueSubscribers`; evidence: server/go/cmd/server/router.go:2199, server/go/internal/handler/subscriber.go:45.

- [ ] `POST /api/issues/{id}/subscribe` → `h.SubscribeToIssue`; evidence: server/go/cmd/server/router.go:2200, server/go/internal/handler/subscriber.go:171.

- [ ] `POST /api/issues/{id}/unsubscribe` → `h.UnsubscribeFromIssue`; evidence: server/go/cmd/server/router.go:2201, server/go/internal/handler/subscriber.go:229.

- [ ] `POST /api/issues/{id}/unsubscribe/subtree` → `h.UnsubscribeFromIssueSubtree`; evidence: server/go/cmd/server/router.go:2202, server/go/internal/handler/subscriber.go:245.

- [ ] `POST /api/issues/{id}/unsubscribe/undo` → `h.UndoUnsubscribeFromIssue`; evidence: server/go/cmd/server/router.go:2203, server/go/internal/handler/subscriber.go:340.

- [ ] `POST /api/issues/{id}/read` → `h.MarkIssueRead`; evidence: server/go/cmd/server/router.go:2204, server/go/internal/handler/issue_unread.go:84.

- [ ] `POST /api/issues/{id}/unread` → `h.MarkIssueUnread`; evidence: server/go/cmd/server/router.go:2205, server/go/internal/handler/issue_unread.go:89.

- [ ] `GET /api/issues/{id}/wakeups` → `h.ListIssueWakeups`; evidence: server/go/cmd/server/router.go:2206, server/go/internal/handler/issue_wakeup.go:132.

- [ ] `POST /api/issues/{id}/wakeups` → `h.CreateIssueWakeup`; evidence: server/go/cmd/server/router.go:2207, server/go/internal/handler/issue_wakeup.go:200.

- [ ] `PUT /api/issues/{id}/wakeups/{wakeupID}` → `h.CreateIssueWakeup`; evidence: server/go/cmd/server/router.go:2208, server/go/internal/handler/issue_wakeup.go:200.

- [ ] `POST /api/issues/{id}/wakeups/{wakeupID}/disable` → `h.DisableIssueWakeup`; evidence: server/go/cmd/server/router.go:2209, server/go/internal/handler/issue_wakeup.go:247.

- [ ] `POST /api/issues/{id}/wakeups/{wakeupID}/enable` → `h.EnableIssueWakeup`; evidence: server/go/cmd/server/router.go:2210, server/go/internal/handler/issue_wakeup.go:280.

- [ ] `PATCH /api/issues/{id}/wakeups/{wakeupID}/instruction` → `h.EditIssueWakeupInstruction`; evidence: server/go/cmd/server/router.go:2211, server/go/internal/handler/issue_wakeup.go:311.

- [ ] `DELETE /api/issues/{id}/wakeups/{wakeupID}` → `h.DeleteIssueWakeup`; evidence: server/go/cmd/server/router.go:2212, server/go/internal/handler/issue_wakeup.go:375.

- [ ] `POST /api/issues/{id}/wakeups/{wakeupID}/trigger` → `h.TriggerIssueWakeup`; evidence: server/go/cmd/server/router.go:2213, server/go/internal/handler/issue_wakeup.go:354.

- [ ] `POST /api/issues/{id}/wakeups/{wakeupID}/checkin` → `h.CheckInIssueWakeup`; evidence: server/go/cmd/server/router.go:2214, server/go/internal/handler/issue_wakeup.go:398.

- [ ] `GET /api/issues/{id}/wakeups/{wakeupID}/runs` → `h.ListIssueWakeupRuns`; evidence: server/go/cmd/server/router.go:2215, server/go/internal/handler/issue_wakeup.go:442.

- [ ] `GET /api/issues/{id}/system-wakeups` → `h.ListIssueSystemWakeups`; evidence: server/go/cmd/server/router.go:2216, server/go/internal/handler/issue_system_wakeup.go:177.

- [ ] `PUT /api/issues/{id}/system-wakeups/{rule}` → `h.UpdateIssueSystemWakeup`; evidence: server/go/cmd/server/router.go:2217, server/go/internal/handler/issue_system_wakeup.go:212.

- [ ] `GET /api/issues/{id}/active-task` → `h.GetActiveTaskForIssue`; evidence: server/go/cmd/server/router.go:2218, server/go/internal/handler/daemon.go:6310.

- [ ] `POST /api/issues/{id}/tasks/{taskId}/cancel` → `h.CancelTask`; evidence: server/go/cmd/server/router.go:2219, server/go/internal/handler/daemon.go:6337, server/go/internal/service/task.go:2991.

- [ ] `POST /api/issues/{id}/tasks/{taskId}/supplements` → `h.CreateTaskSupplement`; evidence: server/go/cmd/server/router.go:2220, server/go/internal/handler/task_supplement.go:312.

- [ ] `POST /api/issues/{id}/tasks/{taskId}/supplements/{commentId}/retry` → `h.RetryTaskSupplement`; evidence: server/go/cmd/server/router.go:2221, server/go/internal/handler/task_supplement.go:430.

- [ ] `POST /api/issues/{id}/rerun` → `h.RerunIssue`; evidence: server/go/cmd/server/router.go:2222, server/go/internal/handler/task_lifecycle.go:158, server/go/internal/service/task.go:6150.

- [ ] `POST /api/issues/{id}/quick-actions/{quickActionId}/run` → `h.RunQuickAction`; evidence: server/go/cmd/server/router.go:2223, server/go/internal/handler/quick_action.go:829.

- [ ] `POST /api/issues/{id}/quick-actions/{quickActionId}/render` → `h.RenderQuickAction`; evidence: server/go/cmd/server/router.go:2224, server/go/internal/handler/quick_action.go:780.

- [ ] `GET /api/issues/{id}/task-runs` → `h.ListTasksByIssue`; evidence: server/go/cmd/server/router.go:2225, server/go/internal/handler/daemon.go:6437.

- [ ] `GET /api/issues/{id}/usage` → `h.GetIssueUsage`; evidence: server/go/cmd/server/router.go:2226, server/go/internal/handler/daemon.go:6820.

- [ ] `POST /api/issues/{id}/reactions` → `h.AddIssueReaction`; evidence: server/go/cmd/server/router.go:2227, server/go/internal/handler/issue_reaction.go:50.

- [ ] `DELETE /api/issues/{id}/reactions` → `h.RemoveIssueReaction`; evidence: server/go/cmd/server/router.go:2228, server/go/internal/handler/issue_reaction.go:108.

- [ ] `GET /api/issues/{id}/attachments` → `h.ListAttachments`; evidence: server/go/cmd/server/router.go:2229, server/go/internal/handler/file.go:676.

- [ ] `GET /api/issues/{id}/children` → `h.ListChildIssues`; evidence: server/go/cmd/server/router.go:2230, server/go/internal/handler/issue.go:2643.

- [ ] `GET /api/issues/{id}/duplicates` → `h.ListIssueDuplicates`; evidence: server/go/cmd/server/router.go:2231, server/go/internal/handler/issue_duplicate.go:167.

- [ ] `GET /api/issues/{id}/labels` → `h.ListLabelsForIssue`; evidence: server/go/cmd/server/router.go:2232, server/go/internal/handler/label.go:393.

- [ ] `POST /api/issues/{id}/labels` → `h.AttachLabel`; evidence: server/go/cmd/server/router.go:2233, server/go/internal/handler/label.go:417.

- [ ] `DELETE /api/issues/{id}/labels/{labelId}` → `h.DetachLabel`; evidence: server/go/cmd/server/router.go:2234, server/go/internal/handler/label.go:499.

- [ ] `GET /api/issues/{id}/metadata` → `h.ListIssueMetadata`; evidence: server/go/cmd/server/router.go:2235, server/go/internal/handler/issue_metadata.go:148.

- [ ] `PUT /api/issues/{id}/metadata/{key}` → `h.SetIssueMetadataKey`; evidence: server/go/cmd/server/router.go:2236, server/go/internal/handler/issue_metadata.go:157.

- [ ] `DELETE /api/issues/{id}/metadata/{key}` → `h.DeleteIssueMetadataKey`; evidence: server/go/cmd/server/router.go:2237, server/go/internal/handler/issue_metadata.go:252.

- [ ] `PUT /api/issues/{id}/properties/{propertyId}` → `h.SetIssueProperty`; evidence: server/go/cmd/server/router.go:2238, server/go/internal/handler/property.go:656.

- [ ] `DELETE /api/issues/{id}/properties/{propertyId}` → `h.DeleteIssueProperty`; evidence: server/go/cmd/server/router.go:2239, server/go/internal/handler/property.go:751.

- [ ] `GET /api/issues/{id}/environments` → `h.ListIssueEnvironments`; evidence: server/go/cmd/server/router.go:2240, server/go/internal/handler/issue_environment.go:293.

- [ ] `POST /api/issues/{id}/environments/start` → `h.StartIssueEnvironment`; evidence: server/go/cmd/server/router.go:2241, server/go/internal/handler/issue_environment_control.go:289.

- [ ] `POST /api/issues/{id}/environments/{environmentId}/stop` → `h.StopIssueEnvironment`; evidence: server/go/cmd/server/router.go:2242, server/go/internal/handler/issue_environment_control.go:206.

- [ ] `POST /api/issues/{id}/environments/{environmentId}/restart` → `h.RestartIssueEnvironment`; evidence: server/go/cmd/server/router.go:2243, server/go/internal/handler/issue_environment_control.go:210.

- [ ] `POST /api/issues/{id}/environments/{environmentId}/logs` → `h.ReadIssueEnvironmentLogs`; evidence: server/go/cmd/server/router.go:2244, server/go/internal/handler/issue_environment_control.go:214.

- [ ] `GET /api/issues/{id}/environment-commands/{commandId}` → `h.GetIssueEnvironmentCommand`; evidence: server/go/cmd/server/router.go:2245, server/go/internal/handler/issue_environment_control.go:364.

- [ ] `GET /api/issues/{id}/pull-requests` → `h.ListPullRequestsForIssue`; evidence: server/go/cmd/server/router.go:2246, server/go/internal/handler/github.go:1125.

- [ ] `POST /api/issues/{id}/pull-requests` → `h.LinkIssuePullRequest`; evidence: server/go/cmd/server/router.go:2247, server/go/internal/handler/pr_auto_complete.go:475.

- [ ] `DELETE /api/issues/{id}/pull-requests/{prId}` → `h.UnlinkIssuePullRequest`; evidence: server/go/cmd/server/router.go:2248, server/go/internal/handler/pr_auto_complete.go:537.

- [ ] `PUT /api/issues/{id}/pr-auto-complete` → `h.SetIssuePRAutoComplete`; evidence: server/go/cmd/server/router.go:2249, server/go/internal/handler/pr_auto_complete.go:612.

- [ ] `POST /api/issues/{id}/squad-evaluated` → `h.RecordSquadLeaderEvaluation`; evidence: server/go/cmd/server/router.go:2372, server/go/internal/handler/squad.go:1021.

## labels

Destination: `server/src/workpal_backend/labels/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_labels_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/labels` → `h.ListLabels`; evidence: server/go/cmd/server/router.go:2281, server/go/internal/handler/label.go:140.

- [ ] `POST /api/labels` → `h.CreateLabel`; evidence: server/go/cmd/server/router.go:2282, server/go/internal/handler/label.go:192.

- [ ] `GET /api/labels/{id}` → `h.GetLabel`; evidence: server/go/cmd/server/router.go:2284, server/go/internal/handler/label.go:166.

- [ ] `PUT /api/labels/{id}` → `h.UpdateLabel`; evidence: server/go/cmd/server/router.go:2285, server/go/internal/handler/label.go:240.

- [ ] `DELETE /api/labels/{id}` → `h.DeleteLabel`; evidence: server/go/cmd/server/router.go:2286, server/go/internal/handler/label.go:309.

## lark

Destination: `server/src/workpal_backend/lark/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_lark_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/lark/binding/redeem` → `h.RedeemLarkBindingToken`; evidence: server/go/cmd/server/router.go:2036, server/go/internal/handler/lark.go:212.

## me

Destination: `server/src/workpal_backend/me/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_me_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/me` → `h.GetMe`; evidence: server/go/cmd/server/router.go:1782, server/go/internal/handler/auth.go:498, server/go/internal/integrations/telegram/api.go:326.

- [ ] `PATCH /api/me` → `h.UpdateMe`; evidence: server/go/cmd/server/router.go:1783, server/go/internal/handler/auth.go:802.

- [ ] `PATCH /api/me/onboarding` → `h.PatchOnboarding`; evidence: server/go/cmd/server/router.go:1784, server/go/internal/handler/onboarding.go:226.

### Onboarding PATCH reconciliation (2026-11-21)

`PATCH /api/me/onboarding` remains pending. Exact source-derived fixtures are `server/contracts/batches/onboarding.json#/fixtures/0` through `/fixtures/18`; `test_onboarding_http.py:test_onboarding_http` executes these sequentially, not with the documented seed reset for each case. The Markdown batch contract remains a source specification, not proof of exact Go/Postgres parity.

Go evidence: `server/go/internal/handler/onboarding.go:226` authenticates, decodes one bounded JSON value, reads prior state, then calls `PatchUserOnboarding`; `server/go/pkg/db/queries/user.sql:55` uses COALESCE and UPDATE RETURNING. Prior read failure is ignored for analytics. There is no encompassing Go transaction, realtime publish or business outbox append. Conditional obsmetrics calls are analytics, distinct from realtime. Python disables analytics; event disposition is `none`, not an assertion that Go has no analytics.

Local evidence: `auth/models.py:8` defines the existing users table and QuestionnaireJSON column; no migration is needed. `auth/onboarding.py:update_onboarding` establishes a real SQLite outer transaction when needed and a nested savepoint, changes only questionnaire and updated_at, and returns the row. `auth/onboarding_routes.py:persist` commits via the caller transaction and maps SQL errors; missing row is 500. There is no prior read because analytics is disabled. No workspace, membership, invitation, provisioning, email, model execution or production integration is performed.

Real tests under `server/tests/`: `test_onboarding_http.py` covers source fixture statuses, replacement/preservation, field casing, body boundaries, CSRF, reopen, caller rollback and SQL/missing-row errors. `test_onboarding_boundaries.py` covers revoked bearer, mounted busy 503, update fault, caught post-write failure with unrelated commit, bounded ASGI receive, unchanged related tables and empty outbox. `test_onboarding_json_edges.py` covers nested JSON, duplicates, precise decimals and explicitly uncertain JSONB inputs. `test_questionnaire_serialization.py` covers exact numbers across user responses, rejected input preserving the row and scalar storage/reopen. Root reports independently passing 22 tests after review; that is prior review evidence, not a new test run in this reconciliation.

Limitations: no executed Go/Postgres differential oracle or exact parity claim. Development sessions/CSRF do not implement production PAT/task/cloud credential verification. Completion and cloud waitlist are separate unsupported capabilities. Analytics projection, transitions, delivery and ignored-prior-read behavior are not implemented or verified locally. Invalid UTF-8 normalization remains a gap (surrogateescape/replacement is not demonstrated equivalent to Go). Decimal preservation is locally tested, but Postgres numeric normalization, exponent/scale limits and error timing remain source-based, not oracle-verified; local invalid JSONB text/range rejection is 400 and may differ from Go SQL-error behavior. SQLite busy handling deliberately returns retryable 503. Local raw questionnaire storage uses BLOB binding to avoid SQLite numeric affinity; legacy scalar reads cannot recover already lost precision.

Checker evidence (both commands executed 2026-11-21): `server/.venv/bin/python server/tools/check_contracts.py` exits 1 with 532 global diagnostics; exact route diagnostics: none. With `--require-complete`, exits 1 with 2286 global diagnostics; exact route diagnostic: `PATCH /api/me/onboarding: pending route`. Global inventory remains unresolved and was not repaired. No runtime/source/data changes or git mutations were made for this reconciliation.


- [ ] `POST /api/me/onboarding/complete` → `h.CompleteOnboarding`; evidence: server/go/cmd/server/router.go:1785, server/go/internal/handler/onboarding.go:69.

- [ ] `POST /api/me/onboarding/cloud-waitlist` → `h.JoinCloudWaitlist`; evidence: server/go/cmd/server/router.go:1786, server/go/internal/handler/onboarding.go:321.
  - Local persistence/production-mounted HTTP evidence is reconciled in `.superpowers/sdd/2026-11-21-python-go-backend/task3-waitlist-reconciliation.md`; retain pending. Migration0011 adds nullable private interest fields; caller transaction/savepoint commits before serialization, preserves questionnaire/onboarded_at and populated workspace/member/outbox snapshots. No provisioning or email delivery.
  - `event:none` concerns business realtime only: Go analytics (`events.go:606`, `business_events.go:276`) remains separate and locally disabled. SQL evidence: `server/go/pkg/db/queries/user.sql:104`. No waitlist capability flag is advertised.
  - Parent reported 18 boundary and earlier 24 decoder/HTTP passes; not rerun here. Null fixture now expects `email is required`. Python mailbox CFWS/domain-literal/encoded-word grammar, private Python 3.11 API, production auth and executed Go oracle gaps remain. Streaming >16KiB/413 is intentional local hardening.
  - Both checker modes executed here exit 1 globally: 530 default / 2284 complete diagnostic lines. Default has no waitlist diagnostic; complete reports only this route's pending status. Global failures remain outside this section.


- [ ] `POST /api/me/whats-new/seen` → `h.MarkWhatsNewSeen`; evidence: server/go/cmd/server/router.go:1787, server/go/internal/handler/whats_new.go:24.

- [ ] `POST /api/me/star-prompt/claim` → `h.ClaimStarPromptShowing`; evidence: server/go/cmd/server/router.go:1788, server/go/internal/handler/star_prompt.go:25.

- [ ] `POST /api/me/star-prompt/starred` → `h.MarkStarPromptStarred`; evidence: server/go/cmd/server/router.go:1789, server/go/internal/handler/star_prompt.go:51.

## notification-preferences

Destination: `server/src/workpal_backend/notification_preferences/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_notification_preferences_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/notification-preferences` → `h.GetNotificationPreferences`; evidence: server/go/cmd/server/router.go:2740, server/go/internal/handler/notification_preference.go:59.

- [ ] `PATCH /api/notification-preferences` → `h.PatchNotificationPreferences`; evidence: server/go/cmd/server/router.go:2741, server/go/internal/handler/notification_preference.go:179.

- [ ] `PUT /api/notification-preferences` → `h.UpdateNotificationPreferences`; evidence: server/go/cmd/server/router.go:2742, server/go/internal/handler/notification_preference.go:147.

## pins

Destination: `server/src/workpal_backend/pins/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_pins_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/pins` → `h.ListPins`; evidence: server/go/cmd/server/router.go:2404, server/go/internal/handler/pin.go:58.

- [ ] `POST /api/pins` → `h.CreatePin`; evidence: server/go/cmd/server/router.go:2405, server/go/internal/handler/pin.go:102.

- [ ] `PUT /api/pins/reorder` → `h.ReorderPins`; evidence: server/go/cmd/server/router.go:2406, server/go/internal/handler/pin.go:235.

- [ ] `DELETE /api/pins/{itemType}/{itemId}` → `h.DeletePin`; evidence: server/go/cmd/server/router.go:2407, server/go/internal/handler/pin.go:199.

## plugin-bridge

Destination: `server/src/workpal_backend/plugin_bridge/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_plugin_bridge_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/plugin-bridge/v1/hooks/{key}` → `h.InvokePluginHook`; evidence: server/go/cmd/server/router.go:1762, server/go/internal/handler/plugin_hook.go:32.

## plugin-surfaces

Destination: `server/src/workpal_backend/plugin_surfaces/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_plugin_surfaces_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /plugin-surfaces/{token}` → `h.ServePluginSurface`; evidence: server/go/cmd/server/router.go:1609, server/go/internal/handler/plugin_surface.go:220.

## plugins

Destination: `server/src/workpal_backend/plugins/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_plugins_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /v1/context` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:270.

- [ ] `GET /v1/issues/{issue_ref}` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:330.

- [ ] `PATCH /v1/issues/{issue_ref}` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:351.

- [ ] `GET /v1/issues/{issue_ref}/comments` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:574.

- [ ] `POST /v1/issues/{issue_ref}/comments` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:625.

- [ ] `GET /v1/tasks/{task_id}/messages` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:425.

- [ ] `GET /v1/storage/{scope}` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:756.

- [ ] `GET /v1/storage/{scope}/{key}` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:780.

- [ ] `PUT /v1/storage/{scope}/{key}` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:798.

- [ ] `DELETE /v1/storage/{scope}/{key}` → `delegated`; evidence: server/go/cmd/server/router.go:1746, server/go/internal/handler/plugin_action.go:820.

- [ ] `GET /api/plugin-bridge/v1/context` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:270.

- [ ] `GET /api/plugin-bridge/v1/issues/{issue_ref}` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:330.

- [ ] `PATCH /api/plugin-bridge/v1/issues/{issue_ref}` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:351.

- [ ] `GET /api/plugin-bridge/v1/issues/{issue_ref}/comments` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:574.

- [ ] `POST /api/plugin-bridge/v1/issues/{issue_ref}/comments` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:625.

- [ ] `GET /api/plugin-bridge/v1/tasks/{task_id}/messages` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:425.

- [ ] `GET /api/plugin-bridge/v1/storage/{scope}` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:756.

- [ ] `GET /api/plugin-bridge/v1/storage/{scope}/{key}` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:780.

- [ ] `PUT /api/plugin-bridge/v1/storage/{scope}/{key}` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:798.

- [ ] `DELETE /api/plugin-bridge/v1/storage/{scope}/{key}` → `delegated`; evidence: server/go/cmd/server/router.go:1759, server/go/internal/handler/plugin_action.go:820.

## project-folders

Destination: `server/src/workpal_backend/project_folders/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_project_folders_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/project-folders` → `s.List`; evidence: server/go/ee/projectfolder/handler.go:52, server/go/internal/integrations/weixin/install.go:373, server/go/internal/daemon/localenv/manager.go:334, server/go/ee/projectfolder/handler.go:138.

- [ ] `POST /api/project-folders` → `s.Create`; evidence: server/go/ee/projectfolder/handler.go:53, server/go/internal/handler/runtime_update.go:96, server/go/internal/handler/runtime_local_skills.go:253, server/go/internal/handler/runtime_local_skills.go:362, server/go/internal/handler/runtime_update_error_classification_test.go:20, server/go/internal/handler/runtime_local_skills_redis_store.go:82, server/go/internal/handler/runtime_local_skills_redis_store.go:276, server/go/internal/handler/runtime_models.go:222, server/go/internal/handler/runtime_update_redis_store.go:46, server/go/internal/handler/runtime_models_redis_store.go:52, server/go/internal/handler/request_cancellation_test.go:240, server/go/internal/integrations/lark/install_session_redis_store.go:106, server/go/internal/integrations/lark/install_session_store.go:117, server/go/internal/integrations/wecom/inbound_media_bind_db_test.go:148, server/go/internal/integrations/wecom/inbound_media_bind_db_test.go:451, server/go/internal/integrations/channel/engine/router_test.go:313, server/go/internal/maintenance/job.go:173, server/go/internal/service/chat_wakeup.go:252, server/go/internal/service/issue_wakeup.go:267, server/go/internal/service/issue.go:233, server/go/ee/projectfolder/handler.go:172.

- [ ] `POST /api/project-folders/file` → `s.File`; evidence: server/go/ee/projectfolder/handler.go:54, server/go/ee/projectfolder/handler.go:308.

- [ ] `PATCH /api/project-folders/{id}` → `s.Rename`; evidence: server/go/ee/projectfolder/handler.go:56, server/go/ee/projectfolder/handler.go:211.

- [ ] `DELETE /api/project-folders/{id}` → `s.Delete`; evidence: server/go/ee/projectfolder/handler.go:57, server/go/internal/handler/file_test.go:87, server/go/internal/storage/local.go:109, server/go/internal/storage/s3.go:354, server/go/internal/integrations/dingtalk/media_test.go:45, server/go/internal/integrations/lark/feishu_channel_test.go:69, server/go/internal/service/issue_wakeup_manage.go:108, server/go/ee/projectfolder/handler.go:253.

## projects

Destination: `server/src/workpal_backend/projects/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_projects_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/projects/search` → `h.SearchProjects`; evidence: server/go/cmd/server/router.go:2324, server/go/internal/handler/project.go:1015.

- [ ] `GET /api/projects/private` → `h.ListPrivateProjectsForOwner`; evidence: server/go/cmd/server/router.go:2328, server/go/internal/handler/project_owner_recovery.go:81.

- [ ] `GET /api/projects` → `h.ListProjects`; evidence: server/go/cmd/server/router.go:2329, server/go/internal/handler/project.go:197.

- [ ] `POST /api/projects` → `h.CreateProject`; evidence: server/go/cmd/server/router.go:2330, server/go/internal/handler/project.go:339.

- [ ] `GET /api/projects/{id}` → `h.GetProject`; evidence: server/go/cmd/server/router.go:2332, server/go/internal/handler/project.go:277.

- [ ] `PUT /api/projects/{id}` → `h.UpdateProject`; evidence: server/go/cmd/server/router.go:2333, server/go/internal/handler/project.go:627.

- [ ] `DELETE /api/projects/{id}` → `h.DeleteProject`; evidence: server/go/cmd/server/router.go:2334, server/go/internal/handler/project.go:768.

- [ ] `POST /api/projects/{id}/join` → `h.JoinPrivateProject`; evidence: server/go/cmd/server/router.go:2335, server/go/internal/handler/project_owner_recovery.go:135.

- [ ] `POST /api/projects/{id}/archive` → `h.ArchiveProject`; evidence: server/go/cmd/server/router.go:2336, server/go/internal/handler/project_archive.go:82.

- [ ] `POST /api/projects/{id}/restore` → `h.RestoreProject`; evidence: server/go/cmd/server/router.go:2337, server/go/internal/handler/project_archive.go:147.

- [ ] `POST /api/projects/{id}/workflow` → `h.SetProjectWorkflow`; evidence: server/go/cmd/server/router.go:2338, server/go/internal/handler/issue_workflow.go:955.

- [ ] `GET /api/projects/{id}/members` → `h.ListProjectMembers`; evidence: server/go/cmd/server/router.go:2339, server/go/internal/handler/project_member.go:444.

- [ ] `POST /api/projects/{id}/members` → `h.AddProjectMembers`; evidence: server/go/cmd/server/router.go:2340, server/go/internal/handler/project_member.go:466.

- [ ] `DELETE /api/projects/{id}/members/{userId}` → `h.RemoveProjectMember`; evidence: server/go/cmd/server/router.go:2341, server/go/internal/handler/project_member.go:528.

- [ ] `GET /api/projects/{id}/subscription` → `h.GetProjectSubscription`; evidence: server/go/cmd/server/router.go:2342, server/go/internal/handler/project_subscriber.go:46.

- [ ] `PUT /api/projects/{id}/subscription` → `h.SubscribeToProject`; evidence: server/go/cmd/server/router.go:2343, server/go/internal/handler/project_subscriber.go:55.

- [ ] `DELETE /api/projects/{id}/subscription` → `h.UnsubscribeFromProject`; evidence: server/go/cmd/server/router.go:2344, server/go/internal/handler/project_subscriber.go:72.

- [ ] `GET /api/projects/{id}/resources` → `h.ListProjectResources`; evidence: server/go/cmd/server/router.go:2345, server/go/internal/handler/project_resource.go:539.

- [ ] `POST /api/projects/{id}/resources` → `h.CreateProjectResource`; evidence: server/go/cmd/server/router.go:2346, server/go/internal/handler/project_resource.go:557.

- [ ] `PUT /api/projects/{id}/resources/{resourceId}` → `h.UpdateProjectResource`; evidence: server/go/cmd/server/router.go:2347, server/go/internal/handler/project_resource.go:643.

- [ ] `DELETE /api/projects/{id}/resources/{resourceId}` → `h.DeleteProjectResource`; evidence: server/go/cmd/server/router.go:2348, server/go/internal/handler/project_resource.go:898.

## properties

Destination: `server/src/workpal_backend/properties/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_properties_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/properties` → `h.ListProperties`; evidence: server/go/cmd/server/router.go:2271, server/go/internal/handler/property.go:404.

- [ ] `POST /api/properties` → `h.CreateProperty`; evidence: server/go/cmd/server/router.go:2272, server/go/internal/handler/property.go:450.

- [ ] `GET /api/properties/{id}` → `h.GetProperty`; evidence: server/go/cmd/server/router.go:2274, server/go/internal/handler/property.go:427.

- [ ] `PATCH /api/properties/{id}` → `h.UpdateProperty`; evidence: server/go/cmd/server/router.go:2275, server/go/internal/handler/property.go:527.

## quick-actions

Destination: `server/src/workpal_backend/quick_actions/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_quick_actions_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/quick-actions` → `h.ListQuickActions`; evidence: server/go/cmd/server/router.go:2261, server/go/internal/handler/quick_action.go:469.

- [ ] `POST /api/quick-actions` → `h.CreateQuickAction`; evidence: server/go/cmd/server/router.go:2262, server/go/internal/handler/quick_action.go:504.

- [ ] `PATCH /api/quick-actions/{id}` → `h.UpdateQuickAction`; evidence: server/go/cmd/server/router.go:2264, server/go/internal/handler/quick_action.go:581.

- [ ] `DELETE /api/quick-actions/{id}` → `h.DeleteQuickAction`; evidence: server/go/cmd/server/router.go:2265, server/go/internal/handler/quick_action.go:705.

## readyz

Destination: `server/src/workpal_backend/readyz/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_readyz_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /readyz` → `health.readyHandler`; evidence: server/go/cmd/server/router.go:1556, server/go/cmd/server/health.go:93.

## runtimes

Destination: `server/src/workpal_backend/runtimes/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_runtimes_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/runtimes` → `h.ListAgentRuntimes`; evidence: server/go/cmd/server/router.go:2547, server/go/internal/handler/runtime.go:1244.

- [ ] `PATCH /api/runtimes/{runtimeId}` → `h.UpdateAgentRuntime`; evidence: server/go/cmd/server/router.go:2549, server/go/internal/handler/runtime.go:513.

- [ ] `GET /api/runtimes/{runtimeId}/usage` → `h.GetRuntimeUsage`; evidence: server/go/cmd/server/router.go:2550, server/go/internal/handler/runtime.go:118.

- [ ] `GET /api/runtimes/{runtimeId}/usage/by-agent` → `h.GetRuntimeUsageByAgent`; evidence: server/go/cmd/server/router.go:2551, server/go/internal/handler/runtime.go:230.

- [ ] `GET /api/runtimes/{runtimeId}/usage/by-hour` → `h.GetRuntimeUsageByHour`; evidence: server/go/cmd/server/router.go:2552, server/go/internal/handler/runtime.go:303.

- [ ] `GET /api/runtimes/{runtimeId}/rate-limits` → `h.GetRuntimeRateLimits`; evidence: server/go/cmd/server/router.go:2553, server/go/internal/handler/runtime_rate_limit.go:161.

- [ ] `GET /api/runtimes/{runtimeId}/activity` → `h.GetRuntimeTaskActivity`; evidence: server/go/cmd/server/router.go:2554, server/go/internal/handler/runtime.go:172.

- [ ] `POST /api/runtimes/{runtimeId}/update` → `h.InitiateUpdate`; evidence: server/go/cmd/server/router.go:2555, server/go/internal/handler/runtime_update.go:210.

- [ ] `GET /api/runtimes/{runtimeId}/update/{updateId}` → `h.GetUpdate`; evidence: server/go/cmd/server/router.go:2556, server/go/internal/handler/runtime_update.go:260.

- [ ] `POST /api/runtimes/{runtimeId}/models` → `h.InitiateListModels`; evidence: server/go/cmd/server/router.go:2557, server/go/internal/handler/runtime_models.go:343.

- [ ] `GET /api/runtimes/{runtimeId}/models/{requestId}` → `h.GetModelListRequest`; evidence: server/go/cmd/server/router.go:2558, server/go/internal/handler/runtime_models.go:458.

- [ ] `POST /api/runtimes/{runtimeId}/local-skills` → `h.InitiateListLocalSkills`; evidence: server/go/cmd/server/router.go:2559, server/go/internal/handler/runtime_local_skills.go:595.

- [ ] `GET /api/runtimes/{runtimeId}/local-skills/{requestId}` → `h.GetLocalSkillListRequest`; evidence: server/go/cmd/server/router.go:2560, server/go/internal/handler/runtime_local_skills.go:622.

- [ ] `POST /api/runtimes/{runtimeId}/local-skills/import` → `h.InitiateImportLocalSkill`; evidence: server/go/cmd/server/router.go:2561, server/go/internal/handler/runtime_local_skills.go:650.

- [ ] `GET /api/runtimes/{runtimeId}/local-skills/import/{requestId}` → `h.GetLocalSkillImportRequest`; evidence: server/go/cmd/server/router.go:2562, server/go/internal/handler/runtime_local_skills.go:715.

- [ ] `DELETE /api/runtimes/{runtimeId}` → `h.DeleteAgentRuntime`; evidence: server/go/cmd/server/router.go:2563, server/go/internal/handler/runtime.go:1333.

- [ ] `POST /api/runtimes/{runtimeId}/unbind-agents-and-delete` → `h.UnbindAgentsAndDeleteRuntime`; evidence: server/go/cmd/server/router.go:2571, server/go/internal/handler/runtime.go:1545.

- [ ] `POST /api/runtimes/{runtimeId}/revoke-workspace-access` → `h.RevokeRuntimeWorkspaceAccess`; evidence: server/go/cmd/server/router.go:2576, server/go/internal/handler/runtime.go:1111.

- [ ] `POST /api/runtimes/{runtimeId}/archive-agents-and-delete` → `h.UnbindAgentsAndDeleteRuntime`; evidence: server/go/cmd/server/router.go:2580, server/go/internal/handler/runtime.go:1545.

## search-index

Destination: `server/src/workpal_backend/search_index/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_search_index_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/search-index/manifest` → `h.GetSearchIndexManifest`; evidence: server/go/cmd/server/router.go:2159, server/go/internal/handler/search_index.go:298.

- [ ] `GET /api/search-index/snapshot` → `h.GetSearchIndexSnapshot`; evidence: server/go/cmd/server/router.go:2160, server/go/internal/handler/search_index.go:343.

- [ ] `POST /api/search-index/changes` → `h.ListSearchIndexChanges`; evidence: server/go/cmd/server/router.go:2161, server/go/internal/handler/search_index.go:455.

## share-links

Destination: `server/src/workpal_backend/share_links/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_share_links_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/share-links/{code}` → `h.GetShareLinkInfo`; evidence: server/go/cmd/server/router.go:1635, server/go/internal/handler/share_link.go:240.

- [ ] `POST /api/share-links/join` → `h.JoinByShareLink`; evidence: server/go/cmd/server/router.go:2072, server/go/internal/handler/share_link.go:264.

## site

Destination: `server/src/workpal_backend/site/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_site_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/site/star` → `h.GetSiteStar`; evidence: server/go/cmd/server/router.go:1631, server/go/internal/handler/site_star.go:34.

- [ ] `POST /api/site/star/turns` → `h.AddSiteStarTurns`; evidence: server/go/cmd/server/router.go:1632, server/go/internal/handler/site_star.go:44.

## skills

Destination: `server/src/workpal_backend/skills/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_skills_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/skills` → `h.ListSkills`; evidence: server/go/cmd/server/router.go:2512, server/go/internal/handler/skill.go:339.

- [ ] `POST /api/skills` → `h.CreateSkill`; evidence: server/go/cmd/server/router.go:2513, server/go/internal/handler/skill.go:518.

- [ ] `GET /api/skills/search` → `h.SearchSkills`; evidence: server/go/cmd/server/router.go:2514, server/go/internal/handler/skill.go:403.

- [ ] `POST /api/skills/import` → `h.ImportSkill`; evidence: server/go/cmd/server/router.go:2515, server/go/internal/handler/skill.go:2318.

- [ ] `GET /api/skills/{id}` → `h.GetSkill`; evidence: server/go/cmd/server/router.go:2517, server/go/internal/handler/skill.go:458.

- [ ] `PUT /api/skills/{id}` → `h.UpdateSkill`; evidence: server/go/cmd/server/router.go:2518, server/go/internal/handler/skill.go:602.

- [ ] `DELETE /api/skills/{id}` → `h.DeleteSkill`; evidence: server/go/cmd/server/router.go:2519, server/go/internal/handler/skill.go:737.

- [ ] `POST /api/skills/{id}/refresh` → `h.RefreshSkill`; evidence: server/go/cmd/server/router.go:2520, server/go/internal/handler/skill_refresh.go:121.

- [ ] `GET /api/skills/{id}/labels` → `h.ListLabelsForSkill`; evidence: server/go/cmd/server/router.go:2521, server/go/internal/handler/label.go:635.

- [ ] `POST /api/skills/{id}/labels` → `h.AttachLabelToSkill`; evidence: server/go/cmd/server/router.go:2522, server/go/internal/handler/label.go:650.

- [ ] `DELETE /api/skills/{id}/labels/{labelId}` → `h.DetachLabelFromSkill`; evidence: server/go/cmd/server/router.go:2523, server/go/internal/handler/label.go:679.

- [ ] `GET /api/skills/{id}/files` → `h.ListSkillFiles`; evidence: server/go/cmd/server/router.go:2524, server/go/internal/handler/skill.go:2488.

- [ ] `PUT /api/skills/{id}/files` → `h.UpsertSkillFile`; evidence: server/go/cmd/server/router.go:2525, server/go/internal/handler/skill.go:2526.

- [ ] `DELETE /api/skills/{id}/files/{fileId}` → `h.DeleteSkillFile`; evidence: server/go/cmd/server/router.go:2526, server/go/internal/handler/skill.go:2621.

- [ ] `GET /api/skills/{id}/versions` → `h.ListSkillVersions`; evidence: server/go/cmd/server/router.go:2527, server/go/internal/handler/skill_version.go:204.

- [ ] `GET /api/skills/{id}/versions/{version}` → `h.GetSkillVersion`; evidence: server/go/cmd/server/router.go:2528, server/go/internal/handler/skill_version.go:248.

- [ ] `POST /api/skills/{id}/versions/{version}/restore` → `h.RestoreSkillVersion`; evidence: server/go/cmd/server/router.go:2529, server/go/internal/handler/skill_version.go:272.

## slack

Destination: `server/src/workpal_backend/slack/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_slack_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/slack/binding/redeem` → `h.RedeemSlackBindingToken`; evidence: server/go/cmd/server/router.go:2042, server/go/internal/handler/slack.go:240.

## squads

Destination: `server/src/workpal_backend/squads/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_squads_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/squads` → `h.ListSquads`; evidence: server/go/cmd/server/router.go:2354, server/go/internal/handler/squad.go:191.

- [ ] `POST /api/squads` → `h.CreateSquad`; evidence: server/go/cmd/server/router.go:2355, server/go/internal/handler/squad.go:254.

- [ ] `GET /api/squads/involved` → `h.ListInvolvedSquadIDs`; evidence: server/go/cmd/server/router.go:2358, server/go/internal/handler/squad.go:230.

- [ ] `GET /api/squads/{id}` → `h.GetSquad`; evidence: server/go/cmd/server/router.go:2360, server/go/internal/handler/squad.go:353.

- [ ] `PUT /api/squads/{id}` → `h.UpdateSquad`; evidence: server/go/cmd/server/router.go:2361, server/go/internal/handler/squad.go:366.

- [ ] `DELETE /api/squads/{id}` → `h.DeleteSquad`; evidence: server/go/cmd/server/router.go:2362, server/go/internal/handler/squad.go:510.

- [ ] `GET /api/squads/{id}/members` → `h.ListSquadMembers`; evidence: server/go/cmd/server/router.go:2363, server/go/internal/handler/squad.go:572.

- [ ] `GET /api/squads/{id}/members/status` → `h.ListSquadMemberStatus`; evidence: server/go/cmd/server/router.go:2364, server/go/internal/handler/squad.go:681.

- [ ] `POST /api/squads/{id}/members` → `h.AddSquadMember`; evidence: server/go/cmd/server/router.go:2365, server/go/internal/handler/squad.go:812.

- [ ] `DELETE /api/squads/{id}/members` → `h.RemoveSquadMember`; evidence: server/go/cmd/server/router.go:2366, server/go/internal/handler/squad.go:901.

- [ ] `PATCH /api/squads/{id}/members/role` → `h.UpdateSquadMemberRole`; evidence: server/go/cmd/server/router.go:2367, server/go/internal/handler/squad.go:957.

## system-wakeups

Destination: `server/src/workpal_backend/system_wakeups/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_system_wakeups_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/system-wakeups` → `h.ListWorkspaceSystemWakeups`; evidence: server/go/cmd/server/router.go:2610, server/go/internal/handler/issue_system_wakeup.go:276.

- [ ] `PUT /api/system-wakeups/{rule}` → `h.UpdateWorkspaceSystemWakeup`; evidence: server/go/cmd/server/router.go:2611, server/go/internal/handler/issue_system_wakeup.go:291.

## tasks

Destination: `server/src/workpal_backend/tasks/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_tasks_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/tasks/{taskId}/messages` → `h.ListTaskMessagesByUser`; evidence: server/go/cmd/server/router.go:2254, server/go/internal/handler/daemon.go:6779.

- [ ] `GET /api/tasks/{taskId}/context-receipt` → `h.GetTaskContextReceipt`; evidence: server/go/cmd/server/router.go:2255, server/go/internal/handler/task_context_receipt.go:133.

- [ ] `POST /api/tasks/{taskId}/retry-source-context` → `h.RetrySourceContextQuickCreate`; evidence: server/go/cmd/server/router.go:2256, server/go/internal/handler/task_lifecycle.go:277, server/go/internal/service/task.go:1790.

- [ ] `POST /api/tasks/{taskId}/cancel` → `h.CancelTaskByUser`; evidence: server/go/cmd/server/router.go:2601, server/go/internal/handler/chat.go:1878, server/go/internal/service/task.go:3008.

- [ ] `POST /api/tasks/{taskId}/rerun` → `h.RerunTaskByUser`; evidence: server/go/cmd/server/router.go:2602, server/go/internal/handler/task_lifecycle.go:187.

## telegram

Destination: `server/src/workpal_backend/telegram/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_telegram_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/telegram/binding/redeem` → `h.RedeemTelegramBindingToken`; evidence: server/go/cmd/server/router.go:2053, server/go/internal/handler/telegram.go:224.

## theme-store

Destination: `server/src/workpal_backend/theme_store/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_theme_store_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/theme-store/themes` → `h.ListStoreThemes`; evidence: server/go/cmd/server/router.go:1779, server/go/internal/handler/theme_store.go:55.

- [ ] `GET /api/theme-store/themes/{themeId}/package` → `h.GetStoreThemePackage`; evidence: server/go/cmd/server/router.go:1780, server/go/internal/handler/theme_store.go:97.

- [ ] `GET /api/theme-store/themes/{themeId}/screenshots/{mode}` → `h.GetStoreThemeScreenshot`; evidence: server/go/cmd/server/router.go:1781, server/go/internal/handler/theme_store.go:142.

## tokens

Destination: `server/src/workpal_backend/tokens/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_tokens_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/tokens` → `h.ListPersonalAccessTokens`; evidence: server/go/cmd/server/router.go:2080, server/go/internal/handler/personal_access_token.go:121.

- [ ] `POST /api/tokens` → `h.CreatePersonalAccessToken`; evidence: server/go/cmd/server/router.go:2081, server/go/internal/handler/personal_access_token.go:64.

- [ ] `POST /api/tokens/current/renew` → `h.RenewCurrentPersonalAccessToken`; evidence: server/go/cmd/server/router.go:2082, server/go/internal/handler/personal_access_token.go:167.

- [ ] `DELETE /api/tokens/{id}` → `h.RevokePersonalAccessToken`; evidence: server/go/cmd/server/router.go:2083, server/go/internal/handler/personal_access_token.go:263.

## upload-file

Destination: `server/src/workpal_backend/upload_file/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_upload_file_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/upload-file` → `h.UploadFile`; evidence: server/go/cmd/server/router.go:1799, server/go/internal/handler/file.go:388, server/go/internal/cli/client.go:494, server/go/internal/integrations/lark/outbound_media_test.go:51, server/go/internal/integrations/lark/http_client_media.go:203.

## webhooks

Destination: `server/src/workpal_backend/webhooks/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_webhooks_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/webhooks/autopilots/{token}` → `h.HandleAutopilotWebhook`; evidence: server/go/cmd/server/router.go:1640, server/go/internal/handler/autopilot_webhook.go:348.

- [ ] `POST /api/webhooks/github` → `h.HandleGitHubWebhook`; evidence: server/go/cmd/server/router.go:1643, server/go/internal/handler/github.go:1293.

- [ ] `POST /api/webhooks/vcs/{connectionId}` → `h.HandleVCSWebhook`; evidence: server/go/cmd/server/router.go:1653, server/go/internal/handler/vcs_webhook.go:94.

- [ ] `POST /api/webhooks/stripe` → `h.HandleCloudBillingStripeWebhook`; evidence: server/go/cmd/server/router.go:1658, server/go/internal/handler/cloud_billing.go:520.

## wecom

Destination: `server/src/workpal_backend/wecom/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_wecom_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `POST /api/wecom/binding/redeem` → `h.RedeemWecomBindingToken`; evidence: server/go/cmd/server/router.go:2049, server/go/internal/handler/wecom_web.go:366.

## working-agents

Destination: `server/src/workpal_backend/working_agents/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_working_agents_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/working-agents` → `h.ListWorkspaceWorkingAgents`; evidence: server/go/cmd/server/router.go:2615, server/go/internal/handler/agent.go:3139.

## workspaces

Destination: `server/src/workpal_backend/workspaces/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_workspaces_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /api/workspaces` → `h.ListWorkspaces`; evidence: server/go/cmd/server/router.go:1828, server/go/internal/handler/workspace.go:161, server/go/internal/daemon/client.go:959.

- [ ] `POST /api/workspaces` → `h.CreateWorkspace`; evidence: server/go/cmd/server/router.go:1829, server/go/internal/handler/workspace.go:249.

- [ ] `GET /api/workspaces/{id}` → `h.GetWorkspace`; evidence: server/go/cmd/server/router.go:1834, server/go/internal/handler/workspace.go:226, server/go/internal/integrations/lark/reference_links_test.go:27, server/go/internal/integrations/lark/outbound_test.go:103, server/go/internal/integrations/wecom/outbound_test.go:296, server/go/internal/integrations/channel/engine/router_test.go:465.

- [ ] `PUT /api/workspaces/{id}/pin` → `h.SetWorkspacePinned`; evidence: server/go/cmd/server/router.go:1835, server/go/internal/handler/workspace.go:191.

- [ ] `GET /api/workspaces/{id}/members` → `h.ListMembersWithUser`; evidence: server/go/cmd/server/router.go:1836, server/go/internal/handler/workspace.go:579.

- [ ] `POST /api/workspaces/{id}/leave` → `h.LeaveWorkspace`; evidence: server/go/cmd/server/router.go:1837, server/go/internal/handler/workspace.go:783.

- [ ] `GET /api/workspaces/{id}/invitations` → `h.ListWorkspaceInvitations`; evidence: server/go/cmd/server/router.go:1838, server/go/internal/handler/invitation.go:252.

- [ ] `GET /api/workspaces/{id}/github/installations` → `h.ListGitHubInstallations`; evidence: server/go/cmd/server/router.go:1843, server/go/internal/handler/github.go:733.

- [ ] `GET /api/workspaces/{id}/vcs/connections` → `h.ListVCSConnections`; evidence: server/go/cmd/server/router.go:1847, server/go/internal/handler/vcs.go:110.

- [ ] `GET /api/workspaces/{id}/qoder` → `h.GetQoderConnection`; evidence: server/go/cmd/server/router.go:1848, server/go/internal/handler/qoder_connection.go:87.

- [ ] `GET /api/workspaces/{id}/qoder/agents` → `h.ListQoderAgents`; evidence: server/go/cmd/server/router.go:1849, server/go/internal/handler/qoder_catalog.go:110.

- [ ] `GET /api/workspaces/{id}/runtime-profiles` → `h.ListRuntimeProfiles`; evidence: server/go/cmd/server/router.go:1853, server/go/internal/handler/runtime_profile.go:256.

- [ ] `GET /api/workspaces/{id}/runtime-profiles/{profileId}` → `h.GetRuntimeProfile`; evidence: server/go/cmd/server/router.go:1854, server/go/internal/handler/runtime_profile.go:279.

- [ ] `GET /api/workspaces/{id}/mcp-servers` → `h.ListWorkspaceMcpServers`; evidence: server/go/cmd/server/router.go:1859, server/go/internal/handler/workspace_mcp_api.go:90.

- [ ] `GET /api/workspaces/{id}/plugins` → `h.ListPlugins`; evidence: server/go/cmd/server/router.go:1863, server/go/internal/handler/plugin.go:181.

- [ ] `GET /api/workspaces/{id}/plugins/{installationId}/surfaces/{surfaceKey}/launch` → `h.GetPluginSurfaceLaunch`; evidence: server/go/cmd/server/router.go:1867, server/go/internal/handler/plugin_surface.go:152.

- [ ] `PUT /api/workspaces/{id}` → `h.UpdateWorkspace`; evidence: server/go/cmd/server/router.go:1872, server/go/internal/handler/workspace.go:442.

- [ ] `PATCH /api/workspaces/{id}` → `h.UpdateWorkspace`; evidence: server/go/cmd/server/router.go:1873, server/go/internal/handler/workspace.go:442.

- [ ] `POST /api/workspaces/{id}/members` → `h.CreateInvitation`; evidence: server/go/cmd/server/router.go:1874, server/go/internal/handler/invitation.go:59.

- [ ] `PATCH /api/workspaces/{id}/members/{memberId}` → `h.UpdateMember`; evidence: server/go/cmd/server/router.go:1876, server/go/internal/handler/workspace.go:645.

- [ ] `DELETE /api/workspaces/{id}/members/{memberId}` → `h.DeleteMember`; evidence: server/go/cmd/server/router.go:1877, server/go/internal/handler/workspace.go:721.

- [ ] `DELETE /api/workspaces/{id}/invitations/{invitationId}` → `h.RevokeInvitation`; evidence: server/go/cmd/server/router.go:1879, server/go/internal/handler/invitation.go:289.

- [ ] `POST /api/workspaces/{id}/mcp-servers` → `h.CreateWorkspaceMcpServer`; evidence: server/go/cmd/server/router.go:1883, server/go/internal/handler/workspace_mcp_api.go:153.

- [ ] `PUT /api/workspaces/{id}/mcp-servers/{serverId}` → `h.UpdateWorkspaceMcpServer`; evidence: server/go/cmd/server/router.go:1884, server/go/internal/handler/workspace_mcp_api.go:222.

- [ ] `DELETE /api/workspaces/{id}/mcp-servers/{serverId}` → `h.DeleteWorkspaceMcpServer`; evidence: server/go/cmd/server/router.go:1885, server/go/internal/handler/workspace_mcp_api.go:274.

- [ ] `POST /api/workspaces/{id}/share-links` → `h.CreateShareLink`; evidence: server/go/cmd/server/router.go:1886, server/go/internal/handler/share_link.go:68.

- [ ] `DELETE /api/workspaces/{id}/share-links/{linkId}` → `h.RevokeShareLink`; evidence: server/go/cmd/server/router.go:1887, server/go/internal/handler/share_link.go:200.

- [ ] `GET /api/workspaces/{id}/share-links` → `h.ListShareLinks`; evidence: server/go/cmd/server/router.go:1888, server/go/internal/handler/share_link.go:174.

- [ ] `POST /api/workspaces/{id}/runtime-profiles` → `h.CreateRuntimeProfile`; evidence: server/go/cmd/server/router.go:1890, server/go/internal/handler/runtime_profile.go:134.

- [ ] `PATCH /api/workspaces/{id}/runtime-profiles/{profileId}` → `h.UpdateRuntimeProfile`; evidence: server/go/cmd/server/router.go:1891, server/go/internal/handler/runtime_profile.go:318.

- [ ] `PUT /api/workspaces/{id}/runtime-profiles/{profileId}` → `h.UpdateRuntimeProfile`; evidence: server/go/cmd/server/router.go:1892, server/go/internal/handler/runtime_profile.go:318.

- [ ] `DELETE /api/workspaces/{id}/runtime-profiles/{profileId}` → `h.DeleteRuntimeProfile`; evidence: server/go/cmd/server/router.go:1893, server/go/internal/handler/runtime_profile.go:542.

- [ ] `GET /api/workspaces/{id}/plugins/packages` → `h.ListPluginPackages`; evidence: server/go/cmd/server/router.go:1897, server/go/internal/handler/plugin_package.go:21.

- [ ] `POST /api/workspaces/{id}/plugins/packages` → `h.PublishPluginPackage`; evidence: server/go/cmd/server/router.go:1900, server/go/internal/handler/plugin_package.go:42.

- [ ] `POST /api/workspaces/{id}/plugins/packages/local` → `h.PublishLocalPluginPackage`; evidence: server/go/cmd/server/router.go:1901, server/go/internal/handler/plugin_package.go:115.

- [ ] `DELETE /api/workspaces/{id}/plugins/packages/{packageId}` → `h.DeletePluginPackage`; evidence: server/go/cmd/server/router.go:1902, server/go/internal/handler/plugin_package.go:146.

- [ ] `POST /api/workspaces/{id}/plugins/preview` → `h.PreviewPlugin`; evidence: server/go/cmd/server/router.go:1910, server/go/internal/handler/plugin.go:214, server/go/internal/service/plugin.go:263.

- [ ] `POST /api/workspaces/{id}/plugins` → `h.InstallPlugin`; evidence: server/go/cmd/server/router.go:1911, server/go/internal/handler/plugin.go:241, server/go/internal/service/plugin.go:340.

- [ ] `GET /api/workspaces/{id}/plugins/{installationId}/invocations` → `h.ListPluginInvocations`; evidence: server/go/cmd/server/router.go:1912, server/go/internal/handler/plugin_hook.go:125.

- [ ] `POST /api/workspaces/{id}/plugins/{installationId}/token` → `h.RotatePluginToken`; evidence: server/go/cmd/server/router.go:1913, server/go/internal/handler/plugin_hook.go:181.

- [ ] `DELETE /api/workspaces/{id}/plugins/{installationId}/token` → `h.RevokePluginToken`; evidence: server/go/cmd/server/router.go:1914, server/go/internal/handler/plugin_hook.go:199.

- [ ] `GET /api/workspaces/{id}/plugins/{installationId}/mcp/{hookKey}/tools` → `h.ListPluginMCPTools`; evidence: server/go/cmd/server/router.go:1917, server/go/internal/handler/plugin_mcp.go:32.

- [ ] `PUT /api/workspaces/{id}/plugins/{installationId}/mcp/{hookKey}/tools` → `h.ApprovePluginMCPTools`; evidence: server/go/cmd/server/router.go:1918, server/go/internal/handler/plugin_mcp.go:68.

- [ ] `PUT /api/workspaces/{id}/plugins/{installationId}/config` → `h.ConfigurePlugin`; evidence: server/go/cmd/server/router.go:1919, server/go/internal/handler/plugin.go:281.

- [ ] `POST /api/workspaces/{id}/plugins/{installationId}/enable` → `h.EnablePlugin`; evidence: server/go/cmd/server/router.go:1920, server/go/internal/handler/plugin.go:305.

- [ ] `POST /api/workspaces/{id}/plugins/{installationId}/disable` → `h.DisablePlugin`; evidence: server/go/cmd/server/router.go:1921, server/go/internal/handler/plugin.go:310.

- [ ] `DELETE /api/workspaces/{id}/plugins/{installationId}` → `h.UninstallPlugin`; evidence: server/go/cmd/server/router.go:1922, server/go/internal/handler/plugin.go:333.

- [ ] `DELETE /api/workspaces/{id}` → `h.DeleteWorkspace`; evidence: server/go/cmd/server/router.go:1925, server/go/internal/handler/workspace.go:1141.

- [ ] `GET /api/workspaces/{id}/github/connect` → `h.GitHubConnect`; evidence: server/go/cmd/server/router.go:1932, server/go/internal/handler/github.go:460.

- [ ] `GET /api/workspaces/{id}/github/installations/{installationId}/repositories` → `h.ListGitHubInstallationRepositories`; evidence: server/go/cmd/server/router.go:1933, server/go/internal/handler/github.go:769.

- [ ] `DELETE /api/workspaces/{id}/github/installations/{installationId}` → `h.DeleteGitHubInstallation`; evidence: server/go/cmd/server/router.go:1934, server/go/internal/handler/github.go:1099.

- [ ] `POST /api/workspaces/{id}/vcs/connections` → `h.ConnectVCS`; evidence: server/go/cmd/server/router.go:1936, server/go/internal/handler/vcs.go:160.

- [ ] `PUT /api/workspaces/{id}/qoder` → `h.SaveQoderConnection`; evidence: server/go/cmd/server/router.go:1937, server/go/internal/handler/qoder_connection.go:257.

- [ ] `POST /api/workspaces/{id}/qoder/check` → `h.CheckQoderConnection`; evidence: server/go/cmd/server/router.go:1938, server/go/internal/handler/qoder_connection.go:215.

- [ ] `POST /api/workspaces/{id}/qoder/environments` → `h.ListQoderEnvironments`; evidence: server/go/cmd/server/router.go:1939, server/go/internal/handler/qoder_catalog.go:143.

- [ ] `POST /api/workspaces/{id}/qoder/stop` → `h.StopQoderConnection`; evidence: server/go/cmd/server/router.go:1940, server/go/internal/handler/qoder_connection.go:537.

- [ ] `POST /api/workspaces/{id}/qoder/resume` → `h.ResumeQoderConnection`; evidence: server/go/cmd/server/router.go:1941, server/go/internal/handler/qoder_connection.go:261.

- [ ] `DELETE /api/workspaces/{id}/qoder` → `h.DisconnectQoderConnection`; evidence: server/go/cmd/server/router.go:1942, server/go/internal/handler/qoder_disconnect.go:34.

- [ ] `POST /api/workspaces/{id}/vcs/connections/{connectionId}/rotate-webhook` → `h.RotateVCSConnectionWebhook`; evidence: server/go/cmd/server/router.go:1943, server/go/internal/handler/vcs.go:304.

- [ ] `DELETE /api/workspaces/{id}/vcs/connections/{connectionId}` → `h.DeleteVCSConnection`; evidence: server/go/cmd/server/router.go:1944, server/go/internal/handler/vcs.go:278.

- [ ] `GET /api/workspaces/{id}/lark/installations` → `h.ListLarkInstallations`; evidence: server/go/cmd/server/router.go:1964, server/go/internal/handler/lark.go:82.

- [ ] `DELETE /api/workspaces/{id}/lark/installations/{installationId}` → `h.RevokeLarkInstallation`; evidence: server/go/cmd/server/router.go:1965, server/go/internal/handler/lark.go:125.

- [ ] `POST /api/workspaces/{id}/lark/install/begin` → `h.BeginLarkInstall`; evidence: server/go/cmd/server/router.go:1971, server/go/internal/handler/lark.go:280.

- [ ] `GET /api/workspaces/{id}/lark/install/{sessionId}/status` → `h.GetLarkInstallStatus`; evidence: server/go/cmd/server/router.go:1972, server/go/internal/handler/lark.go:388.

- [ ] `GET /api/workspaces/{id}/slack/installations` → `h.ListSlackInstallations`; evidence: server/go/cmd/server/router.go:1982, server/go/internal/handler/slack.go:56.

- [ ] `GET /api/workspaces/{id}/wecom/installations` → `h.ListWecomInstallations`; evidence: server/go/cmd/server/router.go:1983, server/go/internal/handler/wecom_web.go:76.

- [ ] `DELETE /api/workspaces/{id}/slack/installations/{installationId}` → `h.RevokeSlackInstallation`; evidence: server/go/cmd/server/router.go:1987, server/go/internal/handler/slack.go:182.

- [ ] `POST /api/workspaces/{id}/slack/install/byo` → `h.RegisterSlackBYO`; evidence: server/go/cmd/server/router.go:1988, server/go/internal/handler/slack.go:98.

- [ ] `DELETE /api/workspaces/{id}/wecom/installations/{installationId}` → `h.RevokeWecomInstallation`; evidence: server/go/cmd/server/router.go:1989, server/go/internal/handler/wecom_web.go:272.

- [ ] `POST /api/workspaces/{id}/wecom/install/byo` → `h.RegisterWecomBYO`; evidence: server/go/cmd/server/router.go:1990, server/go/internal/handler/wecom_web.go:134.

- [ ] `POST /api/workspaces/{id}/wecom/install/begin` → `h.BeginWecomInstall`; evidence: server/go/cmd/server/router.go:1994, server/go/internal/handler/wecom_install_web.go:52.

- [ ] `GET /api/workspaces/{id}/wecom/install/{sessionId}` → `h.GetWecomInstallStatus`; evidence: server/go/cmd/server/router.go:1995, server/go/internal/handler/wecom_install_web.go:141.

- [ ] `GET /api/workspaces/{id}/dingtalk/installations` → `h.ListDingTalkInstallations`; evidence: server/go/cmd/server/router.go:2000, server/go/internal/handler/dingtalk.go:133.

- [ ] `GET /api/workspaces/{id}/dingtalk/groups` → `h.ListDingTalkGroups`; evidence: server/go/cmd/server/router.go:2001, server/go/internal/handler/dingtalk.go:213.

- [ ] `DELETE /api/workspaces/{id}/dingtalk/installations/{installationId}/groups/{conversationId}` → `h.ForgetDingTalkGroup`; evidence: server/go/cmd/server/router.go:2002, server/go/internal/handler/dingtalk.go:521.

- [ ] `DELETE /api/workspaces/{id}/dingtalk/installations/{installationId}` → `h.RevokeDingTalkInstallation`; evidence: server/go/cmd/server/router.go:2003, server/go/internal/handler/dingtalk.go:666.

- [ ] `POST /api/workspaces/{id}/dingtalk/install/byo` → `h.RegisterDingTalkBYO`; evidence: server/go/cmd/server/router.go:2004, server/go/internal/handler/dingtalk.go:571.

- [ ] `GET /api/workspaces/{id}/weixin/installations` → `h.ListWeixinInstallations`; evidence: server/go/cmd/server/router.go:2009, server/go/internal/handler/weixin.go:34.

- [ ] `POST /api/workspaces/{id}/weixin/logins` → `h.BeginWeixinLogin`; evidence: server/go/cmd/server/router.go:2010, server/go/internal/handler/weixin.go:53.

- [ ] `POST /api/workspaces/{id}/weixin/logins/{loginId}/poll` → `h.PollWeixinLogin`; evidence: server/go/cmd/server/router.go:2011, server/go/internal/handler/weixin.go:93.

- [ ] `DELETE /api/workspaces/{id}/weixin/logins/{loginId}` → `h.CancelWeixinLogin`; evidence: server/go/cmd/server/router.go:2012, server/go/internal/handler/weixin.go:133.

- [ ] `DELETE /api/workspaces/{id}/weixin/installations/{installationId}` → `h.RevokeWeixinInstallation`; evidence: server/go/cmd/server/router.go:2013, server/go/internal/handler/weixin.go:161.

- [ ] `GET /api/workspaces/{id}/telegram/installations` → `h.ListTelegramInstallations`; evidence: server/go/cmd/server/router.go:2020, server/go/internal/handler/telegram.go:53.

- [ ] `DELETE /api/workspaces/{id}/telegram/installations/{installationId}` → `h.RevokeTelegramInstallation`; evidence: server/go/cmd/server/router.go:2024, server/go/internal/handler/telegram.go:169.

- [ ] `POST /api/workspaces/{id}/telegram/install` → `h.RegisterTelegramBot`; evidence: server/go/cmd/server/router.go:2025, server/go/internal/handler/telegram.go:91.

## ws

Destination: `server/src/workpal_backend/ws/{routes,schemas,service,repository}.py`. Tests: `server/tests/test_ws_contracts.py`. Run with the foundation-owned Python executable and pytest. Required producer changes belong in the same feature service; append outbox rows inside its transaction, then verify commit, rollback, Redis failure/recovery and duplicate consumption.

- [ ] `GET /ws` → `func(w http.ResponseWriter, r *http.Request) {`; evidence: server/go/cmd/server/router.go:1581.

## Auth/workspace/health reconciliation review (2026-11-21)

Partial review only; checklist boxes remain unchecked. `server/contracts/routes.json` now links existing test functions for health/config/auth/me and workspace list/create/detail. Its success fixtures are Go batch examples, not complete Python parity fixtures. Identity lookup is `GET /api/me`.

Actual implementation: `server/src/workpal_backend/app.py`, `auth/routes.py`, `auth/dependencies.py`, `workspaces/routes.py`, `workspaces/service.py`, `workspaces/repository.py`. Existing tests: `server/tests/test_health.py`, `test_auth_http.py`, `test_workspace_http.py`. Run: `server/.venv/bin/python -m pytest server/tests/test_contract_inventory.py server/tests/test_health.py server/tests/test_auth_http.py server/tests/test_workspace_http.py -q` (19 passed).

Checker review using `check_contracts(..., require_complete=False/True)`: normal 557 → 557; completion 1732 → 1717. Reduction reflects added references only, not route completion. CLI commands: `server/.venv/bin/python server/tools/check_contracts.py` and the same with `--require-complete`.

Remaining: exact request/error fixtures and Python response parity; middleware scope; schema dependencies with supported source references; literal/dynamic frontend mapping; bootstrap retirement decision; Go alias registration audit. Workspace creation specifically requires Task7 daemon refresh outbox and commit/rollback/recovery/duplicate-consumer evidence; do not claim implemented. Frontend exhaustive coverage stays false. Requested `.superpowers/sdd/2026-11-21-python-go-backend/task1-reconciled-auth.md` is absent and outside the three-file write scope; no evidence file was created.

## Task 7 bounded producer backfill: implemented workspace updates

Authorized implementation path: `server/src/workpal_backend/workspaces/service.py` (`update_workspace`); tests: `server/tests/test_workspace_event_producers.py`. Source producer: `server/go/internal/handler/workspace.go:529` (`workspace:updated`). Append inside the existing business transaction; verify commit, rollback, outage and recovery with stable ID. Audit create/pin/read disposition from source, without inventing creation events. No endpoint completion checked here; consumer idempotency and WebSocket delivery remain pending.

## Task 3 bounded invitation persistence continuation

Source batch: `server/contracts/batches/workspace-invitations.{json,md}`. New implementation paths: `server/src/workpal_backend/workspaces/invitations.py`, `server/migrations/versions/0008_workspace_invitations.py`; tests: `server/tests/test_workspace_invitations.py`. This batch covers caller-transaction create/list/revoke persistence, authorization and required invitation events. Acceptance, HTTP wiring, rate admission and email-delivery capability remain separate pending gates. No endpoint is marked complete by this assignment.

## Task 3 bounded invitation HTTP reads and revoke

Paths: `server/src/workpal_backend/workspaces/invitation_routes.py`, `server/src/workpal_backend/app.py` router mounting; tests `server/tests/test_invitation_http.py`. Scope GET workspace invitations, GET personal invitations, GET recipient invitation and DELETE workspace invitation only. Existing invitation service owns revoke/outbox transaction. Create/admission and accept HTTP remain pending separate gates.

## Task 3 invitation inventory reconciliation (six routes; pending)

The six create/list/revoke/personal-list/get/accept entries now reference the existing workspace-invitations source batch, SQLite schema and actual Python tests. `invitation_mutation_routes.py` wires create and accept; `invitation_admission.py` provides Redis admission; `invitations.py` provides transactional persistence and acceptance. Earlier continuation notes describe their assignment-time scope, not current completion. Decline and identity lookup are outside this reconciliation.

Source fixtures are not executed Go differential parity. Middleware/token-kind/task binding, cookie/CSRF parity and explicit email/capacity capability handling remain unresolved. Required invitation/member events append in the business transaction; acceptance tests cover create plus accept Redis outage/recovery with stable IDs. Revoke now has operation-specific outage/reopen FIFO Redis stream recovery evidence (`test_invitation_revoke_recovery.py:14::test_revoke_reopen_outage_fifo`). Accept/decline/member-added projection and actual socket delivery are proven by `test_invitation_conclusion_pipeline.py:24::test_conclusion_pipeline` (four cases), including bound-workspace exclusion and duplicate suppression. Acceptance daemon workspace refresh and exact Go parity remain pending. No route completion checkbox is changed.

## Task 1 invitation decline reconciliation (pending)

`POST /api/invitations/{id}/decline` now references `contracts/batches/invitation-decline.{json,md}` under `server/`, actual `workspaces/invitation_decline.py`, invitation migration/SQL and five real test functions in `server/tests/test_invitation_decline.py`. The earlier focused run predates the corrected race assertions and deterministic committed-order cases; the parent independently reports 249 full-suite passes. Evidence covers recipient rejection and ID/email authorization paths, declined/accepted concluded retries, independent connection decline/accept/revoke races, caller rollback, append failure rollback, database reopen and Redis outage/recovery FIFO publication with stable IDs. This is bounded coverage, not exhaustive errors or Go parity.

Status remains pending. Four conclusion pipeline cases now prove actual socket projection/routing and duplicate suppression for decline and acceptance. Decline recovery is `test_invitation_decline.py:145::test_reopen_outage_fifo`; corrected races are at line 85 and deterministic decline/revoke committed order at line 180. Exact Go parity remains unexecuted, including middleware and capacity handling. Python serializes writers before reads while Go can return 500 on a lost conditional update. Local capacity is disabled.

Checker API validation: normal mode reports 567 global diagnostics and none for decline; require-complete reports 2291 global diagnostics with only `POST /api/invitations/{id}/decline: pending route` for this route. Global incompleteness remains expected; this record has no invalid reference diagnostics. See `.superpowers/sdd/2026-11-21-python-go-backend/task1-decline-reconcile.md` for bounded evidence.

## Task 1 create/revoke realtime reconciliation

Create and revoke remain pending exact Go parity and documented middleware/capability gates. The earlier workspace-only projection statement is superseded for these two routes by the parent correction and test_invitation_realtime_pipeline.py:37: four actual socket modes cover isolated cross-workspace recipient delivery, null recipient suppression, copied-session revocation/member removal and stable-ID duplicates. No email delivery or historical quarantine replay is established. Revoke outage/reopen FIFO stream recovery is now proven separately by `test_invitation_revoke_recovery.py:14`; this and normal socket evidence do not establish a combined restart socket guarantee. Historical quarantine replay remains pending. See `.superpowers/sdd/2026-11-21-python-go-backend/task1-invitation-realtime-reconcile.md`.

### Bounded role and identity reconciliation (2026-11-21)

Only PATCH `/api/workspaces/{id}/members/{memberId}` and GET `/api/me` were reconciled against current source-derived fixtures and Python evidence. Details and actual test names/lines: `.superpowers/sdd/2026-11-21-python-go-backend/task1-role-me-reconcile.md`. Role evidence includes real outer transaction/savepoint rollback on caught lookup/append failures while preserving unrelated caller writes, independent owner serialization, committed reopen/real Redis FIFO recovery and actual socket audience/stable-ID dedup. GET me has source-backed no-business-event classification and persisted default/nondefault read/reopen plus 401 race/500/503 coverage.

Both remain pending for exact Go differential parity and generic global gates. No removal/leave completion is implied; all checklist boxes remain unchanged. Default checker has 555 global diagnostics and none for these exact records; complete mode has 2275 global diagnostics with only `pending route` for each of these two records.
