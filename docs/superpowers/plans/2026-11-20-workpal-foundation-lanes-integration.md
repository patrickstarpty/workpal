# Workpal Foundation Lanes Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已验收Agent/Run与Environment/Investigation Module加入默认部署，以真实HTTP和联合测试证明接线，不增加执行能力。

**Architecture:** Module的Interface保持不变，只在composition root注册三个AppConfig。旧专项settings继续可用但不重复注册，Registry仍是唯一业务入口；配置接线和真实HTTP测试集中在本任务。

**Tech Stack:** 已安装Python3.11/Django/SQLite、Node22.22.0；无需新依赖。

**Spec:** [设计](../specs/2026-11-20-workpal-software-development-design.md)、[并行计划最新验收](2026-11-20-workpal-parallel-delivery.md)。B1a24、D1a19、C2a20已经父代理复跑通过；默认settings尚未注册B/D。

## Global Constraints

- “后端 Python，平台数据先统一放 SQLite”。“completed 不自动将 Issue 标为 Done。”
- Copilot CLI默认；其他四项含OpenCode只保留扩展Interface，不能自动回退或假装可执行。
- 用户指定GPT 6.1 Sol实施，父代理监工；共享脏工作区，无Git写操作、worktree、安装、npm exec/npx、外网、模型、Runtime或真实凭据。
- 使用`.venv-workpal/bin/python`及现有Node22。85项保护基线`/tmp/workpal-supervision-baseline-20261120.json`仅.gitignore既有差异。
- UI和证据normalization正在并行实施。不得改兄弟文件；本任务不运行浏览器，冻结已验收后端测试清单排除`tests.test_evidence_normalization`。根npm只验证原型，不替代新产品验收。

## Review Focus

1. 私有settings重复app label或重复Registry注册：默认与两个lane配置各自启动成功。
2. 只在测试配置可用：默认settings真实会话HTTP能读写新动作。
3. 迁移升级损坏既有Issue及来源：旧数据库升级和空库迁移均保留真实读取能力。
4. 新catalog意外提升权限：普通member不能管理Agent或创建Environment，无环境grant不能读取其内容。
5. 文档将deferred或上传源配置写成真实运行/采集：所有能力状态和范围与实际返回一致。

## Task I1: Register accepted apps and validate composition

**Files:**
- Modify `services/workpal/config/settings.py`：只追加AgentsConfig、ExecutionConfig、InvestigationConfig。
- Modify `services/workpal/tests/settings_execution_lane.py`、`settings_investigation_lane.py`：兼容默认注册，保留导入路径，确保仅当不存在才追加。
- Create `services/workpal/tests/test_parallel_integration.py`：默认配置的公开HTTP/迁移测试。
- Modify `services/workpal/README.md`：默认可用动作和真实未实现范围。
- 仅若精确catalog断言确实因新增合法动作变化，可对相应旧测试更新新增集合项，保留角色/权限断言；先报告实际文件和失败。不改任何生产Module、urls/web、apps UI、根package、计划或旧原型。

**Interface:** 使用现有`agent.create/read/update`、`run.start/read/cancel`、`environment.create/read/list/grant`、`environment_service.create/read/list`、`evidence_source.create_upload/read`和`investigation.start/read/list`。输入/结果合同沿已验收实现。所有HTTP调用`/api/v1/actions/{action_id}`，session和CSRF取真实登录流程，Actor不来自body。

- [x] **Step 1:** 先用默认配置写`test_default_http_agent_run_and_environment_records`，通过已存在通用HTTP调用agent.create断言completed；实施前实际unknown_action为红灯，缺app ORM导入不算。fixture在调用动作前只使用既有identity/work公开Interface，避免提前导入新模型失败。
- [x] **Step 2:** 仅接三个AppConfig及幂等lane配置，使上述HTTP闭环转绿：owner真实密码登录→create Agent→为真实Issue start deferred Run→read/cancel→create Environment/Service/upload-source/Investigation→read/list。检查deferred原因runtime_unavailable、取消不改Issue，upload-source只是配置，无Evidence或网络调用。
- [x] **Step 3:** 新增`test_default_http_authorization_and_registration`：默认catalog动作无重复；member读Agent但管理拒绝，未授环境权限读Environment/Investigation拒绝；owner合法正向对照。真实Host/缺CSRF/匿名拒绝至少覆盖一条新写动作。不得用通配集合删除权限断言。
- [x] **Step 4:** 新增`test_existing_database_upgrade_preserves_issue`：隔离临时SQLite，使用MigrationExecutor在三个新增app未应用的状态创建既有workspace/project/Issue/requirements（通过可用公开Interface或历史模型）；迁移到完整leaf后用当前Interface读回ID、要求hash与来源不变，旧Issue可以启动新的deferred Run。测试恢复完整schema并清理仅本测试文件；不能使用用户数据库。空库migrate亦在独立临时路径验证，不能动仓库data/workpal.sqlite3。
- [x] **Step 5:** 实施前冻结`services/workpal/tests/test_*.py`模块清单，明确仅排除在途`test_evidence_normalization.py`，加入本任务新模块。以默认settings一次跑全部已验收模块；记录实际数量及完整清单，不把预期数当实测。然后两个lane settings各跑原B24/D19，迁移dryrun/check默认及两lane均退出0。若兄弟短暂编辑造成问题，记录准确失败，不擅自改其文件。
- [x] **Step 6:** 运行`node --test apps/workpal-web/tests/*.test.mjs`及根`npm run check`，保护SHA256核对；保存`/tmp/workpal-integration-i1-{red,http,upgrade,full,execution,investigation,migrations,check,node,npm,hashes}.log`，没有执行的日志不要声称存在。README说明默认配置已接线及仍无Runtime/采集/Jira。报告所有文件、实际命令、去重测试数和退出码，交父代理验收。

完成只证明已验收Module在默认配置可用。B1/C2/D1/A5的剩余功能不在本次完成范围，兄弟新UI和normalization另行验收。

## Supervision acceptance — 2026-11-20

I1限定集成验收通过。新增默认配置真实HTTP unknown_action红灯后接线；默认配置的AppConfig不重复、三个集成测试覆盖真实session/CSRF/Host、角色及环境隔离、原Issue/要求/来源在隔离旧库升级中保持及空库迁移。父代理读取实现、迁移测试和配置，并实际运行三项集成加十三项normalization，16项退出0，`/tmp/workpal-integration-i1-parent.log`。没有使用用户数据库。

Sol冻结103个已验收模块，联合680项退出0；B24、D19、集成3及升级专项1均已包含在680中，不能再累加。清单、实际命令和完整日志为`/tmp/workpal-integration-i1-{modules.txt,commands.log,full.log}`。当时在途normalization不在冻结清单；其13项在后续单独验收，不声称本轮已跑693项全量。三种settings迁移dryrun/check、apps Node23、根npm及85项保护都通过。

父代理同时清理服务README中“Agent/Run/Delivery仍待实施”和“状态只读”的过时段落，未改变生产逻辑。默认可用的是配置/记录、deferred准入与取消；仍无配对、租约、Worker、真实Runtime、证据HTTP上传、外部查询或Jira写入。后续D1b2a可修改本Module模型/新增迁移，B1b/C2b详化计划可并行准备。
