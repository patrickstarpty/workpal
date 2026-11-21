# ApiClient attachments/chat and adjacent finite wrappers

Static audit; root review pending. Whole_source false. No backend claim.

Exact declaration bodies and request expressions, lines, inventory tuples, actual verbs, proof hashes and source checks are in the companion JSON. All branches, query/body/header construction, parse fallbacks and catches are retained verbatim for review. Shared fetch is used throughout; attachment text/blob use fetchRaw. No direct global fetch occurs in this section.

- listChatSessions: 4101-4112; 1 request(s).
- getChatSession: 4114-4119; 1 request(s).
- createChatSession: 4121-4134; 1 request(s).
- deleteChatSession: 4136-4138; 1 request(s).
- regenerateChatQuickActions: 4150-4158; 1 request(s).
- updateChatSession: 4160-4168; 1 request(s).
- setChatSessionPinned: 4170-4175; 1 request(s).
- setChatSessionArchived: 4177-4182; 1 request(s).
- listChatPinnedAgents: 4185-4187; 1 request(s).
- pinChatAgent: 4189-4194; 1 request(s).
- unpinChatAgent: 4196-4198; 1 request(s).
- listChatMessages: 4200-4205; 1 request(s).
- listChatMessagesPage: 4207-4244; 1 request(s).
- sendChatMessage: 4246-4272; 1 request(s).
- startMikaOnboarding: 4274-4292; 1 request(s).
- getPendingChatTask: 4294-4299; 1 request(s).
- prioritizeQueuedChatTask: 4301-4315; 1 request(s).
- clearQueuedChatTasks: 4317-4321; 1 request(s).
- listChatDraftRestores: 4328-4341; 1 request(s).
- consumeChatDraftRestore: 4344-4348; 1 request(s).
- listChatSessionWakeups: 4351-4362; 1 request(s).
- cancelChatWakeup: 4364-4368; 1 request(s).
- retryChatWakeup: 4370-4374; 1 request(s).
- listMyChatWakeups: 4376-4387; 1 request(s).
- listPendingChatTasks: 4389-4391; 1 request(s).
- hasAnyPendingChatTasks: 4393-4395; 1 request(s).
- markChatSessionRead: 4397-4399; 1 request(s).
- cancelTaskById: 4405-4424; 1 request(s).
- listAttachments: 4426-4431; 1 request(s).
- getAttachment: 4437-4442; 1 request(s).
- getAttachmentForDownload: 4446-4451; 1 request(s).
- deleteAttachment: 4453-4455; 1 request(s).
- getAttachmentTextContent: 4470-4487; 1 request(s).
- getAttachmentBlob: 4507-4510; 1 request(s).
- listProjects: 4513-4521; 1 request(s).
- getProject: 4523-4526; 1 request(s).
- createProject: 4528-4534; 1 request(s).
- updateProject: 4536-4542; 1 request(s).
- deleteProject: 4544-4546; 1 request(s).
- archiveProject: 4548-4553; 1 request(s).
- restoreProject: 4555-4558; 1 request(s).
- getProjectMembers: 4560-4565; 1 request(s).
- getProjectSubscription: 4567-4572; 1 request(s).
- setProjectSubscription: 4574-4580; 1 request(s).
- parseProjectSubscription: 4582-4584; 0 request(s).
- addProjectMembers: 4586-4593; 1 request(s).
- removeProjectMember: 4595-4597; 1 request(s).
- listPrivateProjectsForOwner: 4601-4606; 1 request(s).
- joinPrivateProject: 4608-4611; 1 request(s).
- listProjectResources: 4614-4618; 1 request(s).
- createProjectResource: 4620-4628; 1 request(s).
- updateProjectResource: 4630-4639; 1 request(s).
- deleteProjectResource: 4641-4648; 1 request(s).
- listLabels: 4651-4656; 1 request(s).
- getLabel: 4658-4663; 1 request(s).
- createLabel: 4665-4673; 1 request(s).
- updateLabel: 4675-4683; 1 request(s).
- deleteLabel: 4685-4687; 1 request(s).
- listIssueWorkflows: 4691-4696; 1 request(s).
- createIssueWorkflow: 4698-4706; 1 request(s).
- updateIssueWorkflow: 4714-4722; 1 request(s).
- dryRunIssueWorkflowUpdate: 4724-4732; 1 request(s).
- deleteIssueWorkflow: 4734-4736; 1 request(s).
- previewWorkflowBrief: 4742-4754; 1 request(s).
- setWorkflowHandoff: 4762-4776; 1 request(s).
- previewWorkflowHandoff: 4785-4793; 1 request(s).
- setProjectWorkflow: 4799-4804; 1 request(s).
- dryRunProjectWorkflow: 4806-4815; 1 request(s).
- listIssueStatuses: 4819-4825; 1 request(s).
- createIssueStatus: 4827-4835; 1 request(s).
- updateIssueStatus: 4837-4845; 1 request(s).
- reorderIssueStatuses: 4853-4865; 1 request(s).
- archiveIssueStatus: 4872-4877; 1 request(s).
- listProperties: 4880-4899; 1 request(s).
- listQuickActions: 4913-4927; 1 request(s).
- createQuickAction: 4929-4937; 1 request(s).
- updateQuickAction: 4939-4947; 1 request(s).
- deleteQuickAction: 4949-4951; 1 request(s).
- runQuickAction: 4959-4966; 1 request(s).
- renderQuickAction: 4975-4983; 1 request(s).
- createProperty: 4985-4993; 1 request(s).
- updateProperty: 4995-5003; 1 request(s).
- setIssueProperty: 5005-5013; 1 request(s).
- unsetIssueProperty: 5015-5022; 1 request(s).
- listLabelsForIssue: 5024-5029; 1 request(s).
- attachLabel: 5031-5039; 1 request(s).
- detachLabel: 5041-5048; 1 request(s).
- listLabelsForResource: 5050-5058; 1 request(s).
- attachLabelToResource: 5060-5072; 1 request(s).
- detachLabelFromResource: 5074-5085; 1 request(s).

Boundary: listIssueViews crosses the cutoff and belongs whole to the next section. upload 4058–4098 remains in the shared execution proof. parseProjectSubscription is a named local parsing helper, not an unknown transport gap. No trailing top-level helpers/exports follow the class.

Dynamic method: setProjectSubscription selects PUT when subscribed and DELETE otherwise. Dynamic label resource routes select agents for agent and skills otherwise. Inventory tuples are copied without rewriting. Missing source-line mappings remain explicit per request.

## Root boundary review

Validated every declaration and copied inventory tuple. Both adjacent assignments omitted listIssueViews; root read and recorded its complete body and client:5096 GET mapping. It serializes scope_type and optional truthy scope_id, then parses with an empty-list fallback. Whole-client closure remains pending.
