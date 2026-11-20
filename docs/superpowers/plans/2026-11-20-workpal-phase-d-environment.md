# Workpal Environment Jira and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成真实环境证据 → 原因与方案 → Jira → 修复 PR → 原环境复验，补齐持续自动化、Analytics、Release、备份和单 HTML 离线导出。

**Architecture:** investigation Module 管证据与复验事实；integrations Module 管 Jira 外部状态与对账；修复复用既有 ActionPlan/Run/Delivery。权限沿所有派生对象传播，发布载荷单独审核，恢复状态与代码交付独立。

**Tech Stack:** 主计划 Python/SQLite/Web；文件上传、只读 HTTP 与私网 Runtime 数据采集 Adapter；真实 Jira 类型在接入前确认。

**Spec:** [设计](../specs/2026-11-20-workpal-software-development-design.md)、[主计划](2026-11-20-workpal-software-development.md)；依赖 A/B/C。

## Global Constraints

继承主计划。“默认查询窗口 30 分钟，单次最多 1000 条或 2 MiB、30 秒超时，一次调查默认最多 10 次查询”。“原始日志默认不随单发送”。“仅掩码字符串不自动解除限制”。“没有原故障或仅一个成功请求不能自动证明恢复”。

## Review Focus

用户显式时间被默认覆盖、HTTP 重定向越权、Jira未知结果重复建单、敏感测试数据/commit外发、PR已合并但故障未恢复分别由 D1、D1、D2、D3、D3固定；D4补DST与页面关闭后触发，D5补满盘和删除传播。

---

### Task D1: 环境证据与可追溯结论

**Files:** Create `services/workpal/workpal/investigation/{models.py,contracts.py,service.py,actions.py,evidence.py,findings.py,migrations/0001_initial.py}`、`investigation/sources/{upload.py,http_query.py,runtime_query.py}`、`runtimes/workpal/workpal_runtime/collection.py`、`services/workpal/tests/{test_evidence.py,test_findings.py}`。

**Interfaces:** `investigation.start(actor,project_id,environment_id,service_id,problem,key)->InvestigationRef`；`evidence.collect(actor,investigation_id,QueryRequest)->CollectionResult`；`EvidenceSource.collect(spec:BoundedQuery)->EvidenceBatch`；`findings.record(actor,investigation_id,FindingInput)->FindingRef`。QueryRequest 只含 source_id、capability、service、time_window/timezone、受限 filter、cursor；无任意 URL/SQL/script。CollectionResult 区分 `ok,forbidden,not_connected,no_data,truncated,delayed,timeout,budget_exhausted`。

- [ ] **Step 1:** 写 `test_sit_uat_prd_custom_environment`、`test_explicit_time_not_replaced_by_default`、`test_1000_records_or_2mib_limit`、`test_11th_query_denied`、`test_cross_environment_shared_connection_denied`、`test_redirect_cannot_escape_endpoint`、`test_uploaded_excerpt_not_full_environment`、`test_confirmation_needs_discriminating_verification`。`test_removed_evidence_does_not_leave_confirmed_answer` 断言当前答案标不可验证且不继续宣称已确认。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_evidence tests.test_findings --noinput`，预期限额、证据与结论门禁失败。
- [ ] **Step 3:** 创建 Environment/Service/DataSource，默认SIT/UAT/PRD，自定义名称不授予权限。upload Adapter 接收真实文本/JSONL错误信息，内容限制先于解析，保留上传人及覆盖范围。HTTP Adapter 管理员配置固定可信endpoint、host/port/method/param schema/response mapping/只读契约，保留配置版本；GET不天然安全、POST不天然可写。网络地址解析、重定向、超时和响应流大小在传输层控制，Agent不可改变端点。私网只由获准Runtime采集，模型进程不可直接接触私网凭据。
- [ ] **Step 4:** 能力按真实 source 注册 `search_logs/query_metrics/get_trace/list_deployments/get_deployed_revision/read_config_diff` 子集。查询前校验用户∩环境∩资源范围，原始输出在持久化、日志与模型上下文前按策略删字段/脱敏；收集 query scope/timezone/events/collected_at/request ID/deploy ID/SHA/截取范围/content hash/来源位置，原始hash与脱敏后hash语义分开，不伪称脱敏副本为原件。无部署SHA不回填main。
- [ ] **Step 5:** Finding 四态 `hypothesis,supported,confirmed,rejected`；confirmed 需可区分替代解释的 VerificationRecord和证据引用，模型重复/时间邻近不够。解释固定 current assessment/impact、observed facts、hypotheses、verification、recommendations；每主要断言引用可访问证据，缺数据显示不足，不捏造概率。临时缓解/长期修复分别给前提风险验证回退，区分建议与已做。复跑全绿，准备提交 `feat: collect bounded environment evidence and verified findings`。

### Task D2: Jira 字段发现、外发和未知结果对账

**Files:** Create `services/workpal/workpal/integrations/jira/{contracts.py,service.py,transport.py,cloud.py,data_center.py}`、`integrations/migrations/0002_jira.py`、`services/workpal/tests/test_jira.py`；Modify `integrations/{models.py,actions.py}`。

**Interfaces:** `JiraAdapter.discover(project_ref,type_ref=None)->CreateMetadata`、`search(query)->DefectPage`、`create(operation)->ExternalIssue`、`observe(issue_ref)->ExternalIssue`、`transitions(issue_ref)->list[Transition]`、`apply_transition(operation)->MutationOutcome`、`reconcile(operation)->MutationOutcome`。`jira.ensure_defect(actor,investigation_id,mapping_id,draft,key)->ExternalIssueLink|ActionResult` 统一门禁、对账和创建链接。

- [ ] **Step 1:** 写 `test_custom_required_fields_prompt_only_missing`、`test_shared_identity_does_not_grant_project_access`、`test_jira_audience_blocks_restricted_draft`、`test_timeout_unknown_never_blind_retry`、`test_external_success_local_failure_recovers_link`、`test_similar_issue_not_auto_merged`、`test_expired_auth_keeps_draft`。真实外部fixture来自提供方协议文档/fakeHTTP，不写死“Bug”或transition ID。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_jira --noinput`，预期未知状态和外发断言失败。
- [ ] **Step 3:** 先实现 JiraConnection/ProjectMapping/ExternalIssueLink/ExternalMutation 与合同 fake。接入前取得目标实例类型/版本、基础地址和测试项目：Cloud 才实现 `cloud.py` REST v3；Data Center 则按其确定版本实现 `data_center.py`。未选/未验证类型的类仅报告 unavailable，不能动态猜测。必须完成所选类型真实建单才能完成本任务联网验收；不能把缺类型作为推迟首版 Jira 能力的理由。[Cloud Issues API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)作为Cloud合同依据。
- [ ] **Step 4:** 读取真实项目、issue type、必填字段/允许值，从映射和证据填写可推导项；用户已说建单且目标确定直接创建。先查相关未解决缺陷，精确 link 可复用，语义相似只供选择。payload 包含症状/环境/影响/时间/复现或未复现/期望实际/部署版本/原因等级/方案/验收；原始日志默认不外发，只用批准摘要和受限链接。校验 Jira受众及当前发起人权限，审计发起人+实际外部身份。
- [ ] **Step 5:** SQLite先记录operation_id/目标/请求hash，再外部调用；只有核验id/key/url才能Created。超时unknown，按关联标记检索核对，无法唯一确认则人工对账；不保证外部恰好一次。成功后本地Issue按external ID幂等；失败默认暂停依赖建单的修复，显式“先本地修复”才绕过。Webhook只刷新，有限轮询兜底，转状态先读取可用transition；外部取消暂停未开始步骤并对活动Run应用取消规则。复跑全绿，准备提交 `feat: add jira defect creation and reconciliation`。

### Task D3: 一句话修复、发布载荷与原环境复验

**Files:** Create `services/workpal/workpal/investigation/{repair.py,verification.py}`、`services/workpal/tests/{test_repair.py,test_environment_disclosure.py}`；Modify `investigation/{models.py,actions.py}`、`integrations/jira/service.py`、`access/service.py`、`operations/policy.py`。

**Interfaces:** `repair.start(actor,investigation_id,defect_ref,repair_request,key)->IssueRef`；`verification.record(actor,investigation_id,VerificationInput)->VerificationRef`；`investigation.resolve(actor,investigation_id,verification_id,revision)->InvestigationView`。VerificationInput 固定目标环境/service/deployed revision/observation window/预先定义criteria/实际结果/evidence refs/负责人；repair_request明确repo/base/target，多个候选返回waiting_input。

- [ ] **Step 1:** 写 `test_diagnosis_only_has_no_mutations`、`test_create_and_fix_one_intent_continues_without_repeated_confirmation`、`test_merged_not_deployed_not_resolved`、`test_failed_reverification_blocks_jira_close`、`test_resolved_can_keep_unknown_root_cause`、`test_recurrence_reopens_preserving_history`。跨链路安全测试：受限PRD日志 → Issue/子任务 → Run/日志 → Delivery/报告 → patch/test/commit/PR，每一项未授权访问或推送均拒绝，撤权即时生效。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_repair tests.test_environment_disclosure --noinput`，预期权限继承/恢复门禁失败。
- [ ] **Step 3:** Registry至少添加 `environment.list,investigation.start,evidence.query,evidence.upload,investigation.explain,jira.search_defects,jira.create_defect,jira.link_existing,repair.start,verification.record,investigation.resolve`。Chat意图仅问原因时只读分析，明确“提缺陷并修复”形成连续ActionPlan，已满足信息/权限的步骤无需重复确认。repo/base从发布映射固定；不能把非代码原因强行变成编码任务。
- [ ] **Step 4:** 修复快照包含环境/部署/证据版本/事实假设/criteria。优先真实重现+失败回归→修复后通过；无法重现如实保留限制。受限材料默认不进入普通开发工作区或外部模型；合成最小重现材料单独prepare_publication，由有环境发布权限的人按具体内容/目的地许可；新patch/test data/commit/PR再次检查，任何改动使原hash失效。生产写库/重启/配置变更/部署不属于 repair.start。
- [ ] **Step 5:** Investigation状态 `investigating,waiting_evidence,recommendation_ready,monitoring,resolved`；取消独立事实。PR merged只影响代码Issue；实际部署版本+足够观察窗口+预定criteria全部满足+指定负责人的确认才resolve，Jira关闭再检查修复/复验门禁。移除证据时当前视图失效标记；原历史decision保留依据不可访问标记。复跑全绿，准备提交 `feat: link repairs to authorized environment verification`。

### Task D4: 关闭浏览器仍运行的自动化

**Files:** Create `services/workpal/workpal/automation/{contracts.py,service.py,schedules.py,actions.py,migrations/0002_triggers.py}`、`services/workpal/tests/test_automation.py`；Modify `automation/models.py`、`worker.py`、`workflows/engine.py`、`delivery/service.py`。扩展C2的AutomationRun同实体，不新建第二套表。

**Interfaces:** `automation.trigger(actor,autopilot_id,TriggerInput)->TriggerDeliveryRef`、`tick(now)->AdmissionResults`；TriggerInput含source/manual|schedule|webhook、scheduled_at/event_id、snapshot，重放增加replay_of。mode=`create_issue|run_only`，后者主体AutomationRun，Delivery/Review共用A4门禁。

- [ ] **Step 1:** 测 `test_trigger_with_browser_closed`、`test_duplicate_event_same_admission`、`test_pause_does_not_cancel_active`、`test_run_only_review_no_issue`、`test_dst_missing_and_repeated_times`、`test_misfire_default_skip`、`test_replay_new_record_keeps_failure`。时钟注入而非真实sleep；另用重启Worker验收持久记录。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_automation --noinput`，预期准入/时区断言失败。
- [ ] **Step 3:** 首版计划类型明确 interval（日历外持续秒数）、daily（本地HH:mm）、weekly（weekday+HH:mm），IANA timezone，下一触发转UTC储存；不宣称任意cron。DST缺失本地时刻记录skipped，重叠默认只执行第一次fold=0；计时键用预期UTC时刻。错过默认记录不补跑；显式bounded catchup需正整数上限。配置包含负责人/模板/输出归属/并发/工作流，重复计划和event ID幂等；达到并发默认skipped，pause拒绝新准入。
- [ ] **Step 4:** Webhook独立secret验证、body上限和重放窗口；只有当前负责人有效权限可派发。run_only完整工作流和人工Review不触发Issue状态转换，Inbox链接AutomationRun。复跑全绿，准备提交 `feat: add persistent scheduled and webhook automation`。

### Task D5: Analytics、Release、保留、导入与离线导出

**Files:** Create `services/workpal/workpal/analytics/{service.py,actions.py}`、`services/workpal/workpal/releases/{models.py,service.py,actions.py,migrations/0001_initial.py}`、`services/workpal/workpal/audit/{exports.py,retention.py,backups.py,imports.py}`、`services/workpal/tests/{test_reporting.py,test_backup_export.py}`、`apps/workpal-web/src/offline/{template.html,render.js,styles.css}`。

**Interfaces:** `analytics.query(actor,filters)->MetricsView`；`releases.record(actor,project_id,release_input)->ReleaseRef`；`audit.export_html(actor,selection)->ArtifactRef`、`backup(destination)->BackupManifest`、`restore(backup,empty_destination)->VerificationReport`、`preview_import(actor,source)->ImportPreview`、`import_confirm(actor,preview_hash,key)->ImportResult`、`retention.apply(policy,now)->CleanupReport`。

- [ ] **Step 1:** 测 `test_unknown_usage_not_zero_cost`、`test_release_record_does_not_deploy`、`test_backup_wal_concurrent_writes_restores_hashes`、`test_disk_full_never_reports_saved`、`test_export_no_credentials_or_raw_logs`、`test_deleted_evidence_no_search_summary_copy`、`test_import_preserves_notes_excludes_fixture_execution`。导出脚本/HTML注入文本只展示文字，无请求/执行副作用。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_reporting tests.test_backup_export --noinput`，预期真实性/恢复/删除断言失败。
- [ ] **Step 3:** Metrics只聚合真实Run次数/失败取消/审核周期/返工/Skill使用；按workspace/project/时间过滤，能下钻来源；未知用量=null且不参与零成本推断，无记录为空态。Release固定已合并提交/Issue、目标环境、人工发布人/部署引用/验证回退，绝不调用部署。
- [ ] **Step 4:** 在线backup API取得一致snapshot并核验BLOB/hash/ref；Runtime spool独立备份说明。上传/日志清理有界批次；证据引用默认保留，环境强制删除时级联删除派生摘要/索引/缓存并保留无内容tombstone，不能留下绕过删除的副本。数据导出与backup权限分开；backup是管理员受限完整副本，export按用户当前对象权限过滤。
- [ ] **Step 5:** 导出单HTML内嵌CSS/字体/脚本，默认无原始日志/凭据/可联网敏感链接内容，无网络依赖、无自动回写；本地notes可编辑保存。正式数据导入显式预览ID映射/来源/时间/notes；样例Run/虚构对话/fixture用量不能成为真实事件。复跑全绿，准备提交 `feat: add truthful reporting backup and offline review`。

### Task D6: 页面、动作覆盖与完整首版验收

**Files:** Create `apps/workpal-web/src/features/{environments.js,investigations.js,autopilots.js,analytics.js,releases.js}`、`services/workpal/workpal/management/commands/acceptance.py`、`services/workpal/tests/test_incident_end_to_end.py`、`docs/workpal-v1-acceptance.md`；Modify `features/{chat.js,connections.js,settings.js}`、`app.js`、`scripts/qa.mjs`、`tests/test_action_coverage.py`、`docs/workpal-action-coverage.md`。

**Interfaces:** 沿既有Registry。`acceptance --config <nonsecret-file> --case <name> --output <path>`，凭据使用secret refs，配置限定测试项目/环境/仓库；报告包含每项 `passed|failed|not_run`、原始证据引用、版本、真实对象链接，不能用缺配置skip包装总通过。

- [ ] **Step 1:** deterministic端到端测试建立临时HTTP证据源/Jira/GitHub/ADO/fakeCLI：提供UAT重复上传证据→结论带引用→创建Jira→实际修改测试仓库→测试/PR→合并未部署仍monitoring→部署与复验通过后resolve。分别注入缺关键证据、超时已建单、撤权、无效发布载荷、服务重启、复验失败和重开。
- [ ] **Step 2:** 先跑 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_incident_end_to_end tests.test_action_coverage --noinput` 及浏览器 `--suite environment` 见行为红灯，再实现D批所有页面/动作：项目Environment/Investigations/Releases、Chat调查入口、连接字段发现、预算/证据/假设、建单各步状态、复验表单、自动化/分析/备份导出。四种环境、窄屏键盘、notes、未知/失败/空态有完整用户路径。
- [ ] **Step 3:** 完整平台与Runtime测试、所有Web suites、`npm run check` 全通过；Django `check --deploy` 在部署配置检查；文件DB测试覆盖并发领取/审核、锁忙、磁盘满、进程中断、备份恢复。审计补齐UI与Chat全动作映射。无模型调用的结果明确为local/protocol verification。
- [ ] **Step 4:** 在获准测试配置上执行真实验收：Copilot登录可用、Linux隔离验证、GitHub与ADO各一条实际改动/测试/PR/新head批准失效/合并事实/断连对账；SIT/UAT/PRD及自定义环境路由、至少一项真实查询源和真实上传、选定Jira实例的必填字段/创建权限/对账/修复关联、原环境部署版本与复验。只向指定测试项目写入；需人批准的真实合并保持确定head确认。
- [ ] **Step 5:** 一槽Chat跨模块自然语言链路、人工审核、Skills发布升级、复杂并行返工、关闭浏览器调度、撤权、限制传播/敏感PR阻断、恢复后导出打开均记录证据。真实条件缺失只列not_run；四批实现完成和完整首版已验收分别报告。准备提交 `feat: complete incident workflow and v1 acceptance`，主代理审阅最后交付与外部验收缺口。
