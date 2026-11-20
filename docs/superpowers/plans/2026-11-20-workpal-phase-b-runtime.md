# Workpal Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 默认 Copilot CLI 完成隔离开发与真实证据提交，支持 GitHub/ADO PR，正确取消、恢复和处理未知外部结果。

**Architecture:** 服务端 execution Module 拥有 Run 状态；Runtime 拥有进程与本地待上传队列；受控 operations 进程独占代码托管写凭据。ProviderAdapter 只处理 CLI 差异，不拥有业务权限。

**Tech Stack:** Python、SQLite、subprocess、Git worktree、Copilot CLI 1.0.112；公共依赖见主计划。

**Spec:** [设计](../specs/2026-11-20-workpal-software-development-design.md)、[主计划](2026-11-20-workpal-software-development.md)；依赖 A1–A5。

## Global Constraints

继承主计划。“服务端超时不意味着远端进程已停止”。“worktree 只提供 Git 工作隔离，不视为安全沙箱。” Copilot 为默认；Codex CLI、Claude Code、Gemini CLI、OpenCode 仅留扩展 Interface，不添加实际 Adapter 或自动回退。

## Review Focus

旧 epoch 继续写入、取消断连后重跑、CLI 假完成、凭据旁路和 PR 超时重建，分别归 B1、B2、B3、B2/B4、B4。

---

### Task B1: 派发、任务租约与事件协议

**Files:** Create `services/workpal/workpal/agents/{models.py,service.py,actions.py,migrations/0001_initial.py}`、`services/workpal/workpal/execution/{models.py,contracts.py,service.py,protocol.py,actions.py,migrations/0001_initial.py}`、`services/workpal/workpal/worker.py`、`services/workpal/workpal/management/commands/runworker.py`、`services/workpal/tests/test_execution.py`；Modify `config/urls.py`。

**Interfaces:** `execution.start(actor,subject,agent_id,key,trigger)->RunRef`；`claim(runtime_identity,capabilities)->Lease|None`；`append_events(task_token,epoch,events)->Ack`；`control(actor,run_id,operation,revision)->RunRef`，operation=`cancel|retry|resume`。Lease 固定 `run_id,epoch,expires_at,input_snapshot,allowed_actions`；Ack 固定连续 cursor 和 missing sequences。协议版本1，默认心跳10s、租约45s、任务令牌60s并随当前租约续发。

- [ ] **Step 1:** 写 `test_two_claimers_one_lease`、`test_old_epoch_rejected`、`test_same_sequence_different_payload_rejected`、`test_manual_start_reuses_but_nodes_do_not`、`test_cancel_disconnected_blocks_replacement`、`test_revoked_actor_cannot_renew`；使用两个真实文件库连接。固定合法 Run 状态为 spec 的11项：`deferred,queued,dispatched,waiting_local_directory,running,cancel_requested,recovery_required,awaiting_input,completed,failed,cancelled`。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_execution --noinput`，预期竞争和 fencing 测试失败。
- [ ] **Step 3:** 实现管理员一次性配对（默认10分钟、单次消费）、可撤销 runtime token、短期任务 token；只有 hash 存库，secret 不进提示。Agent 配置含 provider key、model selection、Skills、Access、Runtime，默认 `copilot_cli`，不可用时 deferred/明确错误。Run 快照固定任务/项目/Agent/Skill/工作流/权限来源。Outbox 领取与写状态同事务，Worker 不在 API 请求内启动 CLI。
- [ ] **Step 4:** 实现11态合法转换：queued 取消立即终止；活动取消先 cancel_requested；租约丢失 recovery_required，未确认停止不派替代。Retry 新 Run；awaiting_input 是结束当前执行的终态，Resume 新尝试关联 checkpoint；基础设施自动重试最多1次，认证/配置/测试失败不自动重试。日志缺口可记录进程终态但 evidence_incomplete。复跑测试全绿。
- [ ] **Step 5:** 准备提交 `feat: add fenced runtime dispatch and event protocol`。

### Task B2: Runtime 进程、仓库隔离与受控操作进程

**Files:** Create `runtimes/workpal/pyproject.toml`、`runtimes/workpal/workpal_runtime/{__main__.py,daemon.py,transport.py,store.py,workspace.py,processes.py,contracts.py}`、`runtimes/workpal/workpal_runtime/operations/{server.py,policy.py,credentials.py}`、`runtimes/workpal/tests/{test_daemon.py,test_operations.py}`、`deploy/workpal/{runtime.service,operations.service,runtime-policy.json}`、`docs/workpal-runtime-operations.md`。

**Interfaces:** `daemon.tick()->TickResult`，依赖 protocol transport 和注入时钟；`workspace.prepare(lease)->WorkspaceRef`；`processes.stop(handle,grace_seconds=10)->StopResult`；`operations.execute(task_identity,OperationRequest)->OperationResult`。OperationRequest 有 operation_id、kind、repo_ref、branch、expected_sha、publication_id；仅 clone/fetch 读取、push_branch、create_pr，以及独立人批准 merge，不提供任意 HTTP/Git 命令转发。

- [ ] **Step 1:** 写 fake transport+真实短命子进程测试：`test_restart_does_not_duplicate_process`、`test_spool_replays_after_ack_loss`、`test_cancel_kills_process_group`、`test_branch_isolation_and_base_sha`、`test_task_cannot_read_host_credentials`。旧 PID 被复用时不得误认/杀错进程，保存启动时间/会话身份进行核验。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python -m unittest discover -s runtimes/workpal/tests -p 'test_*.py'`，预期隔离/恢复行为失败。
- [ ] **Step 3:** Runtime 出站 HTTPS、独立 SQLite spool 保存 run/epoch/process/cwd/cursor/待传事件；先持久化再上传，按 Ack 删除。每次 run 独立 `workpal/<run-id>` 分支、固定 base SHA、worktree，自有 cache 不改用户目录。配置待缺目录时 waiting_local_directory；缺少仓库/权限不自建未知目录。
- [ ] **Step 4:** Linux 为首个真实执行部署：daemon/operations 专用账户；每 Run 独立受限进程/容器，独立文件和 PID 视图、只挂任务目录，禁继承 gh 配置/SSH agent/Git credential helper。operations 独立身份、受限凭据文件、任务侧仅访问受限 socket。网络只允许提供方模型所需端点和受控工具出口；Git 写必须代理，不能用共享 Copilot GitHub 登录的广权限凭据旁路。若认证方式无法满足隔离，连接标 blocked，不能关闭防护宣称成功。CLI 权限 flag 只是附加控制，非 OS 隔离替代。
- [ ] **Step 5:** 重跑测试；Linux OS隔离测试标为单独验收，不得在 macOS 只跑 mock 后报告通过。记录部署限制、spool 备份、取消未确认恢复流程；准备提交 `feat: add isolated runtime and credential broker`。

### Task B3: Copilot Adapter 与提供方扩展 Interface

**Files:** Create `runtimes/workpal/workpal_runtime/providers/{base.py,catalog.py,copilot_cli.py}`、`runtimes/workpal/workpal_runtime/tool_bridge.py`、`runtimes/workpal/tests/{test_provider_contract.py,test_copilot_cli.py}`、`runtimes/workpal/tests/fixtures/copilot/{success.jsonl,denied.jsonl,partial.jsonl}`；Modify `daemon.py`、`services/workpal/workpal/agents/service.py`。

**Interfaces:** `ProviderAdapter.probe(executable)->ProviderCapabilities`；`run(request:ProviderRequest,emit:Callable[[ProviderEvent],None],control:ControlChannel)->ProviderOutcome`。Capabilities 为 installed/auth_state/version、streaming、structured_output、tool_bridge、session_resume、usage 各自能力，不把未知当 false 或成功。Request 包括固定 provider/version/model、prompt/context refs、workspace、权限配置、可选显式 session id；Outcome 包含 exit_code、session_ref、checkpoint_ref、usage（未上报字段 null）、error。ControlChannel 支持取消；补充输入在当前轮次结束后新 Run 接续，不要求热注入。

- [ ] **Step 1:** fake executable 产生上述 JSONL，测试 `test_default_is_copilot`、`test_unimplemented_providers_reject_dispatch`、`test_truncated_json_and_unknown_event_preserved`、`test_success_exit_does_not_approve_delivery`、`test_auth_failure_no_fallback`、`test_model_not_silently_substituted`、`test_usage_unknown_not_zero`。每 fixture 明确 synthetic，仅测试材料，不进用户工作区。
- [ ] **Step 2:** 同 Runtime unittest 命令，预期事件归一化和禁止回退断言失败。
- [ ] **Step 3:** 实现 Copilot argv：`copilot --no-auto-update -p <prompt> --output-format json --disable-builtin-mcps --no-bash-env --no-custom-instructions`，cwd/权限/工具配置由 Runtime 生成，模型明确配置才传 `--model`。参数兼容性通过 `--help` 和固定版本探测，不靠猜 flag。不使用 `--allow-all/--yolo`，不继承用户插件/MCP/扩展；授予目录和测试命令白名单，敏感提示不放服务日志。运行中收到不兼容协议停止并保存错误。
- [ ] **Step 4:** tool_bridge 提供受限的 Workpal action/control 通道，由 Runtime 注入 task identity，模型不能设置 actor/token。协调轮次可输出受 schema 约束的 ActionPlan，服务端执行后再开下一轮，不从任意 assistant 文本提取并执行命令。代码轮次允许本地编辑/测试与受控代理请求；测试产物由 Runtime 执行命令并捕获退出码/输出/commit，而非相信模型“测试通过”。身份校验、脱敏、环境数据模型外发策略在提示组装前执行。
- [ ] **Step 5:** catalog 注册 `copilot_cli` implemented；`codex_cli,claude_code,gemini_cli,opencode` 为 extension-only/not_implemented，无伪实现。取消走 Runtime 进程组；恢复明确 session id，能力不支持则使用服务器 checkpoint/context 新尝试，禁止 `--continue` 接错会话。复跑全部 Runtime tests；准备提交 `feat: add copilot execution adapter and provider extension seam`。

### Task B4: GitHub 与 Azure Repos 的 PR 交付

**Files:** Create `services/workpal/workpal/integrations/{models.py,contracts.py,service.py,actions.py,github.py,azure_repos.py,migrations/0001_initial.py}`、`runtimes/workpal/workpal_runtime/operations/{github.py,azure_repos.py}`、`services/workpal/tests/{test_code_hosts.py,test_merge.py}`；Modify `delivery/service.py`、`operations/policy.py`。

**Interfaces:** `CodeHost.observe(repo_ref,pr_id)->PullRequestFacts`、`mutate(operation)->MutationOutcome`、`reconcile(operation_id)->MutationOutcome`；MutationOutcome=`confirmed|failed|unknown`+external refs。Facts 含稳定 repo identity、PR id、head SHA、merge SHA、state、checks（pass/fail/unknown）、原始提供方状态；统一主键 `(connection,repo identity,provider PR id)`。

- [ ] **Step 1:** 用两类独立 HTTP fake 测 `test_create_timeout_reconciles_branch`、`test_same_pr_number_different_repo`、`test_new_head_invalidates_review`、`test_ado_abandoned_not_merged`、`test_unknown_checks_block_merge`、`test_delayed_webhook_does_not_approve_new_head`、`test_merge_confirmation_bound_to_head`；重复请求只复用 operation，不盲发第二次外部 create。
- [ ] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_code_hosts tests.test_merge --noinput`，预期对账和审核断言失败。
- [ ] **Step 3:** 实现 connections/repo catalog/project binding/PR 读写与轮询：GitHub 初期凭据采用限定测试仓库的 fine-grained token，通过安全控件进入 broker；ADO 首期 Services + 组织允许的短期 PAT，Server/TFVC 不宣称支持。配置保存不等于 connected；验证真实访问、凭据轮换不改历史。HTTP timeout30s、最多有界分页；Webhook 按提供方验证，事件仅刷新信号。主动对账默认60s、失效退避最高15min。
- [ ] **Step 4:** create PR 之前持久 operation key；推送限定分支与预期 remote head，禁 force push。所有要外发的 patch/test data/commit message/PR body 包含在已批准 PublicationPayload，publication hash 必须对应确切 Git tree/commit 及目的地；修改后重新门禁。人在页面或 Chat 对具体 head 确认合并后才发一次性 merge 许可，编码任务 token 不可调用。检查平台 Review、provider checks/branch policy、当前授权；已批准 head 的 merge fact 才完成代码 Issue。
- [ ] **Step 5:** 重跑相关测试和 A4 回归；准备提交 `feat: reconcile github and azure repos deliveries`。真实账号/测试仓库未配置时联网验收保留 not_run。

### Task B5: Runtime、Agent、Run 与代码连接界面

**Files:** Create `apps/workpal-web/src/features/{agents.js,runtimes.js,runs.js,connections.js}`、`apps/workpal-web/tests/runtime.test.mjs`；Modify `app.js`、`features/delivery.js`、`scripts/qa.mjs`；Create `services/workpal/tests/test_development_flow.py`。

**Interfaces:** 使用 Registry 的 `agent.*`、`runtime.*`、`run.start/cancel/retry/resume`、`connection.*`、`repository.*`、`pull_request.*`；Runtime 协议端点不向普通用户暴露任务令牌。

- [ ] **Step 1:** 建 `test_development_flow`，fake CLI 在临时 Git 仓库实际修改文件、执行真正失败/通过测试、生成 commit，fake host 接收 PR；断言 run.completed 时 issue 仍未 Done，拒绝旧 commit 测试证据。浏览器 `--suite runtime` 覆盖 Start、log续读、断连取消、Retry、current/candidate、PR新head。
- [ ] **Step 2:** 先运行平台测试与该浏览器 suite 确认缺少行为，再实现页面 Input/Timeline/Artifacts/Usage、受限凭据安全表单、Copilot默认选择及扩展 provider 不可用状态。缺日志、未知用量、取消待确认真实展示，不能用绿色成功掩盖。
- [ ] **Step 3:** 跑平台全部测试、Runtime全部测试、`node apps/workpal-web/scripts/qa.mjs --suite runtime`、`npm run check`。真实模型测试只在 D6 专门授权链路运行；本批 local fake 结果标为合同测试。
- [ ] **Step 4:** 准备提交 `feat: expose runtime and code delivery lifecycle`，提交本批验收给监工；B2 Linux 隔离和真实 provider 未通过不能勾选“真实交付已验收”。
