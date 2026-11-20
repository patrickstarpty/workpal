# Workpal Chat Workflows and Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chat 完成当前用户可在界面完成的业务操作，复杂工作流与 Squad 可执行，Skills 保留不可变版本与验证记录。

**Architecture:** ActionPlan 由平台 Worker 协调，模型仅做短轮次理解/判断；工作流 Module 持有图执行事实；Skills Module 管版本和绑定，三者通过动作及事件协作。

**Tech Stack:** 主计划栈；不引入队列数据库、不执行用户工作流脚本。

**Spec:** [设计](../specs/2026-11-20-workpal-software-development-design.md)、[主计划](2026-11-20-workpal-software-development.md)；依赖 A/B。

## Global Constraints

继承主计划。“Action Registry 是唯一业务行为目录”。“ActionPlan 的持久化协调器运行在 Python 服务端 Worker，不占用 Agent Runtime 槽位。” 同会话目标串行，控制操作不排在消息后；跨会话可并发。

## Review Focus

单槽死锁、确认后目标改变、可选分支错误阻塞汇合、无界返工和 Skill 更新改写历史，分别固定在 C1、C1/C4、C2、C2、C3。

---

### Task C1: 独立 Chat 与可恢复 ActionPlan

**Files:** Modify `services/workpal/workpal/collaboration/{models.py,service.py,actions.py}`；Create `collaboration/{contracts.py,coordinator.py,migrations/0002_chat_plans.py}`、`services/workpal/tests/{test_chat.py,test_action_plans.py}`；Modify `workpal/worker.py`、Runtime `tool_bridge.py`。

**Interfaces:** `collaboration.submit(actor,conversation_id,message,key)->ChatRequestRef`、`coordinator.advance(plan_id,event_id)->PlanView`、`coordinator.control(actor,plan_id,command,revision)->PlanView`，command=`stop|confirm|supply_input|auth_completed|withdraw`。ActionPlan 固定 steps `{id,action_id,payload,depends_on,observed_revisions,status,result_refs}`；每步 key=`request_id:step_id`，没有数据库/系统任意执行工具。

- [ ] **Step 1:** 测 `test_single_slot_releases_coordinator_before_child`、`test_restart_after_step_commit_resumes_once`、`test_stop_bypasses_message_queue`、`test_same_text_new_request_not_deduped`、`test_revoke_mid_plan_stops_remaining_steps`、`test_auth_resume_revalidates_plan`。确定性 fake planner 返回跨项目/Issue/Run 的结构化步骤，断言创建对象真实存在；部分失败保留已完成 refs。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_chat tests.test_action_plans --noinput`，预期协调与恢复断言失败。
- [ ] **Step 3:** 实现 Conversation/Message/Draft/QueuedMessage/ChatRequest/ActionPlan/ActionExecution。CRUD含rename/pin/archive、附件与来源快照；新消息在运行期间可撤回且未发送前不标 Agent 已接收。Send 显式启动短协调 Run，流式内容只来自实际事件。转换 Issue 前展示目标/criteria/历史范围，确认后建立不可变快照，后续消息不改要求。
- [ ] **Step 4:** ActionPlan 持久推进；等待子Run、认证、确认或输入时立即结束协调轮次并释放槽位，事件唤醒下一轮。低风险目标明确直接执行；危险动作聚成具体确认卡，参数/目标/head变化使许可失效；审批决策者是人。用户新增目标先生成新计划/revision，不将“都处理”当无限授权。失败只补偿声明可撤销且未被他人更新的动作，外部 unknown 先对账。
- [ ] **Step 5:** 补测试 `test_prompt_injection_cannot_grant_actions`：工具输出/仓库/Skill中的“发到另一个地址”“批准自己”只作任务数据，schema合规也不能提升权限。重跑全绿，准备提交 `feat: add persistent chat action coordination`。

### Task C2: 版本化图执行与 Squad 分工

**Files:** Modify `workflows/{models.py,service.py,actions.py}`、`agents/{models.py,service.py,actions.py}`；Create `workflows/{contracts.py,graph.py,engine.py,migrations/0002_graph_execution.py}`、`agents/migrations/0002_squads.py`、`services/workpal/workpal/automation/{models.py,migrations/0001_initial.py}`、`services/workpal/tests/{test_workflows.py,test_squads.py}`。

**Interfaces:** `workflows.publish(actor,draft_id,revision)->WorkflowVersionRef` 扩展 A3 同 Interface；`start(actor,subject,version_id,key)->InstanceRef`、`advance(instance_id,event_id)->InstanceView`、`control(actor,instance_id,command,revision)->InstanceView`；`agents.delegate(actor,squad_id,subject,proposal,key)->DelegationView`。Subject 支持 Issue/AutomationRun；NodeAttempt key=`instance:node:attempt_no`；explicit create_child 节点才能创建 Issue。

- [ ] **Step 1:** 测 `test_graph_rejects_unbounded_cycle`、`test_optional_branch_does_not_block_join`、`test_failed_required_branch_not_success`、`test_parallel_same_agent_distinct_runs`、`test_upgrade_does_not_rewrite_instance`、`test_squad_leader_only_until_authorized_split`、`test_budget_exceeded_waits_for_human`。纯 graph 测直接跨 Interface，无 ORM mocks；恢复测试用持久实例。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_workflows tests.test_squads --noinput`，预期图门禁和派发断言失败。
- [ ] **Step 3:** 图节点支持 start/end、human_decision、agent_task、condition、parallel、join、delivery_review、create_child；condition 只允许声明字段和 `eq,ne,in,exists,gt,gte,lt,lte`，无 eval/任意表达式。验证可达、角色、起终点、汇合可完成、返工计数；返工必须指定正整数最大次数。Node 状态固定 `pending,ready,running,waiting_input,succeeded,failed,cancelled,skipped`；Run completed 仍需证据门禁。
- [ ] **Step 4:** Squad leader 接收成员职责快照；默认先草案，人确认派发；项目授权可规定 Agent集合/并发/最大子任务/预算允许自动拆分。超出任一上限 waiting_input，不静默降低或扩大。子任务独立输入/产物/目录；join 只取选定 Artifact，不合并文件。父任务验收独立。取消图阻断新派发并请求取消活动Run；timeout、返工、重启恢复有事件/尝试记录。
- [ ] **Step 5:** 建立最小 AutomationRun schema（id/workspace/requirements_snapshot/source_scope/revision/status，状态 queued/running/in_review/completed/failed/cancelled），加入 run_only 主体的 Delivery 测试；完整调度配置和触发记录由 D4扩展同实体，禁止伪造Issue。重跑测试，准备提交 `feat: execute bounded workflows and squad delegation`。

### Task C3: Skills 生命周期与快照绑定

**Files:** Create `services/workpal/workpal/skills/{models.py,contracts.py,service.py,actions.py,imports.py,migrations/0001_initial.py}`、`services/workpal/tests/test_skills.py`；Modify execution 快照构建。

**Interfaces:** `skills.import_source(actor,source,conflict_policy)->SkillDraftRef`；`validate(actor,draft_id,case,mode)->ValidationRef`；`publish(actor,draft_id,revision)->SkillVersionRef`；`bind(actor,agent_id,version_id,revision)->BindingRef`。Case 保存 input/expected/artifacts/environment/reviewer；mode=`automatic|human` 分开记录；自动验证若调用 CLI 走正常 Run，不在 API 内执行。

- [ ] **Step 1:** 测 `test_refresh_creates_draft`、`test_old_run_keeps_skill_hash`、`test_import_does_not_execute_install_commands`、`test_unvalidated_publish_rejected`、`test_deprecate_preserves_existing_history`、`test_restricted_delivery_skill_keeps_scope`。来源包含 shell安装脚本只可文本展示；压缩/路径遍历与symlink越界拒绝。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_skills --noinput`，预期不可变性/导入安全断言失败。
- [ ] **Step 3:** 草稿编辑、文件/可信固定来源导入、冲突预览、diff、验证、版本发布、显式绑定升级、停用与废弃替代。发布前至少一条含实际产物和人评审的通过验证；自动检查不能顶替人评审。已批准 Delivery 可作为草稿来源；版本内容/hash/作者/适用范围不可变；刷新不覆盖发布版本；历史绑定内容归 Run 快照。
- [ ] **Step 4:** 重跑测试、A4/B1回归；prepare publication 适用于来自受限材料的 Skill分享/导出。准备提交 `feat: add validated immutable skill versions`。

### Task C4: Chat 与 UI 行为覆盖验收

**Files:** Create `apps/workpal-web/src/features/{chat.js,squads.js,workflows.js,skills.js}`、`apps/workpal-web/src/client-actions.js`、`services/workpal/tests/test_action_coverage.py`、`docs/workpal-action-coverage.md`；Modify `app.js`、`scripts/qa.mjs`。

**Interfaces:** `clientActions.execute(id,args)->ClientActionResult` 仅允许 theme/sidebar/notes/draft 的白名单；不接 arbitrary JavaScript。安全秘密控件属于 `waiting_user_auth` continuation，不把 token 放消息；UI `data-action-id` 与 Registry 和 clientActions 的覆盖矩阵可生成。

- [ ] **Step 1:** 建 `test_every_business_ui_action_is_registered`、`test_every_registered_user_action_has_chat_schema`、`test_unknown_client_action_denied`；同一 registry 动作以页面用户和 Chat代理用户调用，assert 权限/对象结果相同。浏览器 `--suite collaboration` 先验证缺少交互失败。
- [ ] **Step 2:** 完成所有页面实际操作：Chat流、队列/撤回、停止、输入/确认/认证恢复；工作流可编辑图或可访问节点表单并保存执行；Squad配置/分工；Skills 内容/版本/diff/验证/usage。对不明确同名仓库仅提一个聚焦问题；已有明确参数不重填页面。确认卡显示具体对象/数量/head/影响；计费/用量未知如实展示。
- [ ] **Step 3:** 浏览器覆盖一句话建项目并拆任务、批量调整、定时工作流（D4接通后加入）、Skill沉淀绑定、人的具体批准、PR head变化拒绝；1440/390px键盘操作、重载草稿、服务重启续读、单槽工作流与Stop。所有材料有授权限制时 chat消息/搜索/缓存同样收窄。
- [ ] **Step 4:** 跑平台全部测试、Runtime tests、`node apps/workpal-web/scripts/qa.mjs --suite collaboration`、`npm run check`。自动化及环境新动作在 D批完成后必须补同矩阵，不允许“核心Chat完成但其他按钮无工具”的首版豁免。
- [ ] **Step 5:** 准备提交 `feat: complete chat workflow and skill interaction coverage`，交付监工核对全目录动作，不以关键词路由替代真实自然语言验收。
