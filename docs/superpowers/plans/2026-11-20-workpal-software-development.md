# Workpal Software Development Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在独立目录实现完整联网首版，贯通需求、真实开发、审核，以及环境证据调查 → Jira 缺陷 → 修复 PR → 原环境复验。

**Architecture:** Python 模块化单体持有业务事实，独立 Worker 协调持久任务，独立 Runtime 调用默认 Copilot CLI。前端和 Chat 共用 Action Registry；授权、证据继承、幂等、审核门禁各集中在具有小 Interface 的深 Module 内。SQLite 是平台唯一业务存储，Runtime 自有 SQLite 只保存执行恢复信息。

**Tech Stack:** Python 3.11+、Django 5.2.19（ORM、迁移、会话、密码哈希）、SQLite、Gunicorn 27.0.1；原生 JavaScript ES modules、CSS、HTML；Django/unittest、Node test runner、Playwright；Copilot CLI。

**Spec:** [首版设计](../specs/2026-11-20-workpal-software-development-design.md)。执行者须同时读设计、本文和当前批次文件。

## Global Constraints

以下引文逐字沿用设计；各批任务隐式包含这些约束。

- “后端 Python，平台数据先统一放 SQLite”。
- “不引入 PostgreSQL、Redis 或对象存储，也不预设迁移时间。”
- “原型 SQLite 不直接升级为正式产品数据库。”
- “首版包含的页面必须可实际读写并调用对应业务服务，不用占位页、仅静态示例或“后续开放”替代。”
- “界面继续使用 Inter、中性表面、紧凑行、克制边框和阴影。”
- “保留本地 review notes，界面不加入 prototype、research 或 simulation 标签。”
- “completed 不自动将 Issue 标为 Done。”
- “授权快照用于解释历史，当前授权用于允许下一次副作用。”
- “不把人工评审改成 Agent 自我批准。”
- “只导入和审阅文件，不执行来源页面的安装命令。”
- “PR 合并可完成代码 Issue，但调查仍需记录目标环境实际部署版本和复验结果，必要时由有环境权限的人确认恢复。”
- 不修改 `src/`、`backend/`、`index.html`、`review-v1.html`、`assets/archives/` 的既有产品逻辑和存档。原型仍无依赖并可导出单 HTML；新产品单独运行，离线导出无网络执行能力。
- 所有用户文本按文本渲染；390px、键盘操作、本地 review notes 是验收条件。测试默认不调用真实模型、不访问真实环境、不执行 Skill 安装命令。

## Review Focus

1. 受限 PRD 证据派生的任务、日志、报告与 PR 泄露：A2 建继承模型，D1/D3 测撤权和受限发布载荷。
2. 外部已经成功但本地超时/崩溃：B4 和 D2 测对账恢复，禁止盲目重建 PR/Jira。
3. 单槽 Runtime 下 Chat 等子任务导致死锁：C1 测协调轮次结束释放槽位，停止走控制通道。
4. PR head、验收标准或权限在确认后改变：A4/B4 测旧批准失效、并发只接受一个有效 revision。
5. 非标准输入与故障：D1 测时区、截断和恶意日志；D4 测 DST；D5 测磁盘满、备份和删除后的派生内容不可访问。

## 本轮决定、授权与现状

- 用户已要求写计划并随后安排 **GPT 6.1 Sol 实施，主代理监工**。这是本次执行授权；设计文件仍保留此前“待评审”的历史措辞，不据此重复索要已给出的执行许可。
- 最新 Runtime 范围：**Copilot CLI 为默认且首版唯一必须真实接入的执行器**。Codex CLI、Claude Code、Gemini CLI、**OpenCode** 只保留扩展 Interface 与显式 `not_implemented` 能力声明；不安装、不伪装可用、不自动回退。
- 本机只读探测：Copilot CLI `1.0.112`、Codex CLI `0.166.0`、Claude Code `2.1.309`；Gemini CLI 未在 PATH 中发现。未检查账号授权，未调用模型。Copilot 首版兼容基线固定 `1.0.112`，部署前探测能力并记录确切版本，升级需要协议回归。
- 现有 `backend/server.py` 是 loopback 的 `records(key,value,revision)` 持久化；`src/backend-storage.js` 用同步 XHR 保留 localStorage 契约；`src/model.js`/`studio.js` 持有业务行为。不可包装为正式后端继续堆功能。
- `src/environment-chat.js` 只有 DEV/UAT/PRD 样例与本地队列；正式产品从空工作区起步，默认环境 SIT/UAT/PRD，可自定义。不得把样例回复、用量、Run 导入真实事实。
- 工作区存在大量用户未提交改动。实施只暂存自己新增/修改的文件；禁止 `git add .`、重置、清理或覆盖既有改动。计划先写文件，不自动提交用户改动。

## 实施选择与依据

选择 Django 而非继续扩写标准库记录服务：身份、会话、密码管理、ORM 和迁移已有成熟实现，业务 Interface 保持框架外观之外。使用框架默认 PBKDF2，不自制认证算法。Django 5.2 为 LTS，本文固定已发布修订版 5.2.19；依据：[发行列表](https://www.djangoproject.com/download/)、[5.2.19](https://docs.djangoproject.com/en/5.2/releases/5.2.19/)、[密码管理](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/)。Gunicorn 固定 [27.0.1](https://pypi.org/project/gunicorn/27.0.1/)，单 API worker，独立一个业务 Worker；正式部署由已有 TLS 反向代理暴露，开发仅 loopback。

前端选原生 ES modules，复用视觉 token、字体和品牌资产，不搬运原型业务状态机；不加 React、通用状态管理或前端业务数据库。HTTP 动作请求与事件轮询先完成；2 秒轮询、每页最多 200 事件、退避上限 30 秒。SSE 是可选优化，不是正确性的前提。

SQLite 设置 WAL、foreign_keys=ON、busy_timeout=5000；写事务采用 IMMEDIATE，条件更新并检查行数；禁止网络 I/O 持锁、禁止依赖 `SELECT FOR UPDATE`。锁忙至多重试 2 次（50/150ms），再返回 `storage_busy`。这是实现默认值，可配置且测试固定。参考 [Django SQLite 事务](https://docs.djangoproject.com/en/5.2/ref/databases/#transactions-behavior)。

执行器以子进程 argv 调用，不拼 shell；Copilot 使用非交互 JSONL，真实模型、工具请求和用量均以提供方实际事件为依据。[官方程序化 Interface](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference)支持 JSONL。当前四个候选扩展各自有不同会话/工具机制，Interface 不假设统一 resume 或用量字段；参考 [Codex](https://learn.chatgpt.com/docs/non-interactive-mode)、[Claude Code](https://code.claude.com/docs/en/headless)、[Gemini CLI](https://geminicli.com/docs/cli/headless/)。OpenCode 先保留 provider key，不在未实接时承诺具体协议。

## Module 与 Seam 设计（codebase-design）

| Module / 文件根 | 小 Interface | 藏在 Implementation 内的复杂性与收益 |
| --- | --- | --- |
| `services/workpal/workpal/access/` | `authorize(actor, action, refs)`、`derive_scope(refs)`、`prepare_publication(...)` | 当前成员权限、来源限制交集、撤权和目的地发布；删除此 Module 会让每个读取、Chat、导出、PR 重复实现策略 |
| `.../actions/` | `catalog(actor)`、`execute(actor, request)` | schema、确认、revision、幂等、审计和业务 handler 路由；不是承载全部业务的巨型 switch |
| `.../work/`、`.../delivery/` | 任务转换、提交、评审 | Issue/Run/Delivery/Review 独立事实与版本门禁，调用者不能自行标 Done |
| `.../execution/` | `start`、`claim`、`append_events`、`control` | 不可变快照、租约、fencing、重试取消恢复、日志完整性 |
| `runtimes/workpal/workpal_runtime/providers/` | `probe()`、`run(request, emit, control)` | Copilot 参数、事件解析与能力差异；真实 Copilot 与 deterministic fake 两个 Adapter 验证 Seam，扩展四项不建空转实现 |
| `.../integrations/` 与 Runtime `operations/` | `observe`、`mutate`、`reconcile` | GitHub/ADO/Jira 差异、外部未知状态、受控凭据与写权限 |
| `.../collaboration/`、`.../workflows/` | `submit`、`advance`、`control` | Chat 持久计划、单槽协调；图条件、并行汇合、返工与决策 |
| `.../investigation/` | `collect`、`record_finding`、`start_repair`、`resolve` | 查询预算、证据来源、根因等级、复验；数据采集 Adapter 分上传、HTTP、私网 Runtime |
| `.../skills/`、`.../automation/`、`.../audit/` | 版本发布、触发准入、授权导出 | 不可变版本、时区幂等调度、保留和审计；不加入泛化仓储基类 |

依赖分类：工作流计算为 in-process，直接测 Interface；SQLite 为 local-substitutable，用真实临时文件库；Runtime 为 remote but owned，用协议 Adapter/fake；GitHub、ADO、Jira、CLI 为 true external，使用各自合同测试。数据库不额外套抽象 Repository，时钟和网络传输在真正变化的 internal seam 注入。tests 不访问私有方法，不用 mock ORM 替代并发验证。

## 共同数据与动作契约

`services/workpal/workpal/contracts.py` 定义以下 dataclass/类型；业务 DTO 归所属 Module 的 `contracts.py`，不得跨 Module 导入 ORM model 来修改状态。

- `Actor(user_id, workspace_id, executor_id=None, session_id=None)`：身份来自认证中间件，body 中的 ID 不能伪造 Actor。
- `ObjectRef(kind, id)`；`SubjectRef(type, id)` 的 type 为 `issue|automation_run|conversation`，Delivery 只允许前两种。
- `ActionRequest(action_id, payload, expected_revision, idempotency_key, confirmation_id=None)`；`ActionResult(state, object_refs, data, error=None)`，state 为 `completed|accepted|waiting_input|waiting_confirmation|waiting_user_auth|failed|unknown`。
- `DomainError(code,message,request_id,retryable,details)`；HTTP 400 schema、403 permission、404 不可见对象、409 revision/confirmation、413 size、503 storage/capability。错误响应、日志不得含 secret 或受限材料。
- `DataScope(workspace_id, source_refs)`：source refs 是动态策略引用集合，不是创建时角色快照；多来源要求全部当前授权，不是挑一个宽松权限。限制沿派生关系传播，索引/Inbox 也只能投影当前可见信息。
- `PublicationPayload(id, source_refs, destination, content_hash, content_ref, revision, status)`：与原始材料分开存。外发时重查具体内容、目的地、当前策略与人的发布许可；批准不降级原对象访问限制。
- `EventEnvelope(id,workspace_id,aggregate_ref,sequence,type,payload,created_at)`；业务 outbox 和状态在同事务写入，消费幂等。CLI 原始事件不直接当业务命令执行。

动作统一经 `/api/v1/actions/{action_id}`。设计中的资源路由作别名映射同一 handler，包括 Issue Run、Cancel、events、Delivery、Review、Skill version、Autopilot trigger、AutomationRun Delivery。鉴权会话、Runtime 协议和文件流传输单独定义传输入口；对象发布/确认仍经过 Registry。Action spec 声明输入输出 JSON schema、授权、读写性质、幂等、确认、补偿和审计；schema 由受支持的 Django Form 字段映射并与服务端校验做往返测试，拒绝额外字段。

## 文件结构与四批计划

每个业务 Module 只有 `models.py`、`contracts.py`、`service.py`、`actions.py` 和必要 `migrations/`，按任务逐步建立，不一次生成全树。测试同 Module 责任放 `services/workpal/tests/`。`apps/workpal-web/src/features/<name>.js` 持有对应视图，通用 `client.js`/`ui.js` 管请求、转义、焦点；不建立另一个前端状态机。

| 批次 | 计划 | 独立可验收结果 |
| --- | --- | --- |
| A | [身份、业务记录与交付](2026-11-20-workpal-phase-a-foundation.md) | 多用户从空工作区到人工真实证据交付与版本化评审 |
| B | [Runtime 与代码交付](2026-11-20-workpal-phase-b-runtime.md) | Copilot 真实修复、两种 Repo、取消恢复、受控发布与 PR 对账 |
| C | [Chat、工作流与 Skills](2026-11-20-workpal-phase-c-collaboration.md) | 自然语言操作全覆盖，单槽不死锁，复杂流程和技能版本可执行 |
| D | [环境调查、Jira 与首版验收](2026-11-20-workpal-phase-d-environment.md) | 真实调查和 Jira 修复复验闭环、持续自动化、备份导出与完整首版 |

原定顺序为 A → B → C → D。用户于2026-11-20明确要求所有可独立任务并行、子Agent实施而主代理只监工，现按[并行交付计划](2026-11-20-workpal-parallel-delivery.md)的实际依赖调度；不再把整批完成设为无关模块开工的前提。四批全部完成且完成真实验收才叫首版完成。每任务只修改拥有文件；不执行Git提交/暂存，监工记录验收。每任务先行为测试失败，再最小实现，再同一测试通过；不为文档、薄转发和可逆样式修改追加镜像测试。

## 测试命令与真实验收入口

实施时 A1 建立 `.venv-workpal/`，锁定全部传递依赖到 `services/workpal/requirements.lock`；不改变原型依赖。下文 `WP_PY=.venv-workpal/bin/python` 仅为命令说明，执行时使用确切路径。

- 平台：`.venv-workpal/bin/python services/workpal/manage.py test tests.<模块名> --noinput`；SQLite 并发用 `TransactionTestCase` 和临时文件库，不能内存共享库或单连接替代。
- Runtime：`.venv-workpal/bin/python -m unittest discover -s runtimes/workpal/tests -p 'test_*.py'`，其 `pyproject.toml` 可编辑安装仅本地代码。
- Web：`node --test apps/workpal-web/tests/*.test.mjs`；`node apps/workpal-web/scripts/qa.mjs --suite <name>`，使用现有 `WORKPAL_PLAYWRIGHT` 约定，测试脚本自行管理临时 DB/loopback 测试服务并清理。
- 原型兼容：实施每批结束运行 `npm run check`，构建的 dist 不提交到存档；先记录既有失败，不能把基线失败静默算成新代码通过。
- 联网验收：D6 的 `acceptance` 命令仅在指定测试项目和授权凭据就绪后运行；单元测试/协议桩通过不等于真实验收通过。缺少配置标 `not_run` 并列出缺项，不伪造数据或降格完成。

## 外部输入与监工交接

可立即实现本地代码及 fake 合同测试；真实数据源、Jira Cloud/Data Center 类型与版本、GitHub/ADO 测试仓库、Runtime 专用 Linux 执行环境、Copilot 授权由实际接入时配置，秘密只走安全凭据控件。Jira 适配合同先建立；接入前确认目标类型，选定类型实现并实测，另一类型显示不可用，不同时假称都支持。

监工逐批查看文件差异、任务测试和错误路径；A2、B2/B4、C1、D1/D3 为重点审核点。GPT 6.1 Sol 不自行扩委派；每批报告修改文件、命令及结果、未验收事项。用户已授权按计划开工，无需再次选择执行方式；真实外部写操作仍限定在后续明确的测试账号、项目和目标内。

## 自查记录

- 设计功能表全部分配：Workspace/Projects/Issues/Inbox/Settings → A；Runs/Runtime/Repo → B；Agents/Squads/Chat/Workflows/Skills → B/C；Environment/Jira/Autopilot/Analytics/Release/Export → D。
- 状态、默认限制、工作流两种主体、外部 unknown、单槽调度、传播权限与 PR 发布载荷均有拥有任务和测试。
- 用户最新要求已覆盖设计旧“一种未指定 CLI”：默认 Copilot CLI；四项扩展仅合同；实施模型为 GPT 6.1 Sol，二者不是同一个概念。
- 本计划写作不运行模型或生产连接，不修改原型。实施启动状态另行记录，不能将下方未勾选任务视为完成。
