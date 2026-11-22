# Workpal Ticket / Workflow 交接

更新时间：2026-11-22。**当前停止实现，先重新设计工作模型。**

## 用户最新纠正：这是下一步工作的依据

用户明确指出至少有两种情况：

1. 一张 ticket 从头到尾完成计划、设计、开发、测试和部署。
2. 从任意阶段新建 ticket，自由开展设计、开发、测试或部署。

不要把这理解成二选一的产品设置。产品必须同时容纳这些工作方式。不要再直接执行之前提出的“合并成一张 ticket”方案，也不要继续强化“每阶段一张 ticket”的方案。用户要求先停下来思考，再写交接文档；尚未批准新的数据模型或交互方案。

## 应当先分清的概念

- **Ticket：** 有明确目标、范围、责任人和完成条件的一项工作。不能用 ticket 数量表示生命周期完成度。
- **阶段：** 当前工作的活动类型，例如设计、开发、测试、部署。阶段不等于一张 ticket，也不等于 ticket 的状态。
- **状态：** 这项工作是否待处理、进行中、等待复核、完成。设计 ticket 可以在设计被接受后完成，不要求部署；完整交付 ticket 的完成条件由它的交付范围决定。
- **Agent Run：** 某个 agent 的一次执行。同一 ticket、同一阶段可以有多个 agent、多次执行和失败重试。Run 完成不自动意味着阶段获批，更不意味着 ticket 已完成。
- **交付物：** 可被后续工作引用的输入和输出，具有修订版本及来源。输入可以来自同一 ticket 的此前活动、其他 ticket 或用户提供的材料。
- **Ticket 关系：** 按真实工作范围表达父子、阻塞、依赖或关联。只有产生了需要独立跟踪的工作才拆分；进入下一阶段本身不是拆票理由。
- **Activity：** 保存工作发生的顺序、参与者、执行、讨论、决策、产物版本和交接。它应能解释工作如何推进，不能只是罗列状态。

以上是对用户意图的解释及设计约束，不是已经落地的数据库 schema。

## 用场景检验下一版设计

### 同一 ticket 完整交付

“修复上传中断恢复”是一项完整交付工作：计划和设计形成版本化材料，开发产生实现，测试发现问题后回到开发，复核通过再申请部署，部署获准后完成。全程可以留在同一 ticket。不能为了展示六阶段而造六项工作。

### 独立阶段工作

- 用户已有需求，创建“设计恢复上传交互”ticket，只交付可接受的设计。
- 用户提供已确认设计，直接创建开发 ticket；计划和设计历史不是必填前置步骤。
- 用户提供已有版本，创建测试 ticket，输出缺陷和验证报告。测试发现的问题可以留在当前工作中沟通，也可以按实际范围产生关联修复 ticket。
- 用户提供已验收版本，创建部署 ticket，检查发布条件、获得批准、记录发布和回滚材料。

这些例子用于检验自由起步能力，不是预定要创建的四张演示 ticket。

### 过程中拆分、回退与复用

一项工作可以在过程中产生独立设计研究、安全复核或缺陷修复工作。新 ticket 应清楚说明来源、范围及与原 ticket 的关系。后续阶段能引用既有产物，不要求复制历史或把所有活动强制串成唯一顺序。哪些关系、回退和流程配置先做，需要下一版方案明确，不能直接扩成通用工作流引擎。

## 下一步先设计，暂不改数据

1. 明确创建 ticket 时如何表达目标、起始工作阶段、输入材料和完成条件；避免要求用户先理解内部模型。
2. 明确详情页如何同时呈现工作状态、当前活动阶段、负责人、产物和运行记录，而不把阶段强制映射成状态。
3. 用上面的两类路径检查：任意阶段能直接起步；一张 ticket 能跨多个阶段；测试返工不会丢历史；阶段完成不会错误关闭完整交付工作。
4. 明确什么时候在原 ticket 继续、什么时候创建关联 ticket，以及如何携带上下文和产物引用。
5. 再决定演示场景和数据量。数据应服务于这些路径，不再先定“一张”或“六张”。
6. 向用户展示具体方案后再实现和迁移。此前关于固定七张或合并成一张的方案均已被最新纠正取代。

## 当前真实状态：还没有按新模型改造

- 工作目录：`/Users/patrick/Desktop/Workspace/ai-native/workpal`。
- Web：`http://127.0.0.1:4174`；本地 Python API：4175。
- 默认登录邮箱：`workpal@fwd.com`，本地验证码 `888888`。刷新后重新进入登录流程。
- SQLite：`server/data/python/workpal.sqlite`；workspace slug：`review`。
- 当前仍有 **7 张活动 ticket**：父任务 `lifecycle-delivery` / TAP-283；Plan–Maintain 六张阶段票 `lifecycle-plan` 至 `lifecycle-maintain` / TAP-284–289。
- 前五阶段 done，Maintain in_progress；父任务 in_progress。这是被纠正的旧演示结构，不是新方案。
- 已写入 19 个 Run（包含独立失败和重试）、92 条阶段 Activity 项、169 条 transcript 事件、12 份 Markdown 产物修订。父任务另有总结评论。
- 用户第一次纠正后，只作了口头“合并成一张”的回应，**未执行合并、删除阶段票或重写其关系**；随后用户再次纠正并要求停下。
- 原始本地证据评论已保存在 `archived_evidence_comments`。种子脚本每次写入前备份 SQLite；不要丢弃备份和历史材料。
- 工作树包含多个前序回合的未提交改动。不要整体回退、清理或替换数据库。没有创建 commit 或 PR。

## 已有实现中可复用的部分

- `server/src/workpal_backend/workspace_content/routes.py`：混合评论/事件时间线；issue Run 列表和 subtree 读取；task transcript / context receipt 读取；附件元数据和纯文本预览读取。均以 workspace 授权约束，未实现的执行操作仍明确失败。
- `server/tests/test_workspace_content.py`：补充时间线排序、Run/消息读取、子任务范围、防循环、附件预览和跨 workspace 隔离检查。
- `scripts/seed-lifecycle-story.py`：**固定七张旧结构的种子，暂勿再次运行。** 稳定 ID、备份、内部 `_fixture` 来源字段和版本化材料可复用；票据结构与部分叙事需要重做。
- `apps/web/public/delivery/`：12 份非敏感演示 Markdown。不是实际 agent 输出。
- `apps/web/app/capabilities/overview.tsx`：当前六入口仍指向六张阶段票，需要在新方案确定后处理。
- `scripts/lifecycle-story-qa.mjs`：现有验收写死七票/六页面，也需要随新模型调整，不能作为新需求通过的证据。
- `scripts/register-lifecycle.py`：前序七票注册脚本，同样不能未经审查再执行，否则可能恢复旧结构。
- `docs/lifecycle-demo-route.md`、`docs/superpowers/plans/2026-11-22-lifecycle-activity.md`：均是旧方案，已过时，以本交接和最新用户指令为准。

## 验证记录与未解决项

- 首轮 `npm run check` 完成：1926 个 Python 测试通过、30 subtests，通过 launcher 检查及构建。日志 `/tmp/workpal-story-check.log`。此轮早于最后新增附件预览接口，不能单独证明最终全部代码通过。
- 最新局部 workspace content 测试：25 passed；Overview 测试：5 passed。
- 重复 seed 前后所有 workspace record 的内容摘要相同，已验证幂等性，但仅针对旧七票结构。
- Playwright 已逐页验证六阶段数据、状态/角色关联、附件 URL、Run 和消息，且成功打开 Transcript 并看到工具步骤。
- **附件弹窗的端到端验证尚未通过**：当前 QA 在匹配 `implementation-report.mdv2` 按钮时超时，不能据此声称产品预览坏了，也不能声称已验证成功。附件 API 单测通过，待后续从实际可访问名称和 UI 交互定位。
- 第二轮完整检查已在暂停前启动：日志 `/tmp/workpal-story-final-check.log`，当时仍在执行。后续读取最终退出状态和日志，不要沿用“运行中”当作通过。
- 独立只读审查没有发现新 task/attachment/timeline 路由的具体 workspace 隔离问题；因用户改变要求停止，没有完成种子与完整功能审查。
- 原界面存在本地后端未支持能力的 404/501 请求；不应将“无 pageerror”表述为所有产品功能完整。

## 持续有效的用户要求

- 使用英文产品界面、Workpal 视觉系统；不要在界面塞入 prototype/simulation 或“未真实执行”的说明。
- 用户明确授权为原型构造 Agent Run、审批、失败重试和结果。通过内部字段及交付说明如实记录其虚构来源；不要在对外交付时声称真实调用模型、真实测量或生产部署。
- 参考 Multica 官方 Activity、Run transcript、协作评论、交付物版本的体验，而不是堆砌长评论。已查阅官方 issues/tasks/squads 文档及 multica-ai/multica 的 run-lifecycle-demo、squad-demo、deliverables-demo。
- Agent 角色应可理解、有来源，并配置到 workspace；前序已有 15 个角色和 5 个小队来源于公开方法的适配，不应冒称作者本人或官方原样阵容。
- 当前任务不是继续补更多 fixture；应先解决 ticket 与工作流程之间的关系，再做演示数据。

## 2026-11-22 后续落实：新 Workpal 工作空间

本节取代上文“停止实现”的状态。用户在确认 ticket/阶段理解后要求开工，并明确要求新建 Workpal 工作空间承载新票据。

- 新 workspace 显示名 `Workpal`，slug `workpal-team`（`workpal` 为系统保留字），票据前缀 `WP`。
- 新项目 `flexible-workflow`，21 张工作票：Plan/Design/Build 各 4，Test/Deploy/Maintain 各 3；七个内置状态各 3。数量是初始内容要求，无产品上限。
- 每票独立保存 `metadata.workflow_stage`、`metadata.work_scope`、`metadata.completion_criteria`；status 不与 stage 绑定。描述含目标、范围、输入、验收条件，部分票明确关联设计、验证、发布工作；完整交付票可以持续承载工作。
- Overview 读取新工作空间的持久化票据，按当前阶段和状态筛选，也可包含全部阶段。移除固定六张阶段票入口。保留现有阶段发起入口。
- 注册脚本 `scripts/seed-flexible-workflow.py` 只插入缺失记录，不覆盖已有票据，写入前备份。旧 review 的 415 条 workspace_records 经备份逐条比对保持不变；在临时数据库副本验证重复注册保留手工修改。
- 新票据是 authored demonstration 内容，内部 `_fixture` 标记 execution=none；没有创建虚构的执行 Run，没有调用模型或发布生产环境。已有执行和集成功能的限制不因这些内容而解除。
- 此轮没有实现通用工作流引擎、专用阶段编辑器或产物跨票自动传递；现有 ticket 描述和 metadata 表达工作范围，关联采用明确的详情链接。
- 浏览器 QA：`node scripts/flexible-workflow-qa.mjs` 通过分组计数、完整交付票跳转、390px 窄屏布局。组件测试 7 passed。原附件弹窗未验证项仍保留，不能由这轮 QA 推断为通过。
- 浏览器首次检查遇到 API 未启动导致 502；使用现有 `.env` 恢复本地 4175 服务后通过。部分原有搜索/收件箱接口仍返回 501/404，不声称全部集成完整。

### 最终更新

- 用户随后要求将新工作空间改名为 **SMART**；已修改数据库显示名和 Overview 入口。slug 保持 `workpal-team`，21 张票及链接未变；注册脚本首次创建也使用 SMART。
- `npm run check` 已退出 0：1927 Python tests、30 subtests、launcher 检查和 Vite 构建通过。日志 `/tmp/workpal-flexible-check.log`。
- 独立审查发现普通新建票据无 stage metadata 时重跑注册会 KeyError；已用临时数据库复现并修复，缺省归入 unassigned，验证普通用户票据原样保留。
- 改名只涉及显示名和入口文案；另行执行组件测试、浏览器 QA 和构建确认。

### 默认与最近工作空间

用户进一步明确：首次默认 SMART，之后记住上次使用的工作空间，通过原有工作空间切换器切换。
`PythonSession` 在无明确工作空间的入口中依次选择：当前账号最近使用且仍可访问的工作空间 → SMART (`workpal-team`) → 唯一可访问的工作空间 → 选择页。显式 ticket / workspace 深链接优先，不会被默认项覆盖。最近使用记录按账号 ID 存入本机 localStorage，仅在工作空间上下文准备完成后写入；存储不可用时仍可正常导航。组件测试 35 passed。
浏览器脚本 `scripts/default-workspace-qa.mjs` 已验证首次 SMART → 切换器选择 TAP → 刷新并重新登录、进入仍为 TAP → 切回 SMART。显式 TAP ticket 深链接也已验证不被默认入口重定向。

## SMART Activity 补齐（2026-11-22）

用户指出新票缺失此前明确要求的 Activity；此前“已完成”只覆盖票据列表，遗漏过程体验。

- `scripts/seed-smart-activity.py` 为 21 张 SMART 票补入 173 条协作评论、120 条事件、42 个 Run、210 条 transcript 消息、27 个交付物修订，并在 SMART 注册 15 个来源可追溯的角色。
- Activity 按各票实际 authored 场景区分待优先级、待开始、进行中、待审、完成、阻塞、取消；backlog/todo 无执行 Run。SMART-7 包含失败重试和同票多阶段工作；相关设计/验证/发布票通过明确交接链接关联。
- v2 提供具体回归矩阵、发布/回滚清单、交接责任表、接受的范围、空状态设计和标题行为验收内容。禁止将这些构造内容当作真实执行或测量证据。内部 `_fixture` 标注 synthetic。
- 初次写入前备份 SQLite，437 条既有记录逐条保持不变；重复导入验证内容不变。审查后的补正只修改本轮生成且与预期旧值完全一致的记录，拒绝覆盖并发编辑；去除无变化的状态事件。
- `scripts/smart-activity-qa.mjs` 已逐票打开 Activity，并验证角色、状态顺序、Run 消息、27 个附件内容；真实打开 v2 附件弹窗看到 Regression matrix，并打开 Transcript 看到 Read 步骤。结果：21 tickets / 293 entries / 42 runs / 27 revisions。
- 此轮 `npm run check`：1926 passed、30 subtests passed，1 项 `test_authorized_delivery_and_failed_fanout[context2]` 失败（dispatch 返回 0）。未修改实时消息代码；该文件单独复核 6 passed。不能将整套检查表述为全通过。日志 `/tmp/workpal-smart-activity-check.log` 和 `/tmp/workpal-realtime-recheck.log`。

## 领域头像（2026-11-22）

用户要求所有 agent 增加对应领域的活泼头像。采用现有 Workpal glyph 生成统一彩色徽章（不是另引图标库）：产品靶心、架构模块、工程统筹分支、开发代码、代码审查眼睛、维护扳手、发布火箭、可靠性心跳、安全盾牌、值班铃、研究搜索、重构图层、QA 核验、对抗审查缺陷、科研灯泡。

- `scripts/generate-agent-avatars.mjs` 生成 15 组 SVG 源文件和 256px PNG，存于 `apps/web/public/agent-avatars/`；role catalog 记录 avatarUrl。
- `scripts/register-agent-avatars.py` 备份后为 SMART 15 个、TAP 19 个 agent 更新头像。逐条验证仅 avatar_url 改动，所有其他字段和记录不变。
- Agent Team 的角色图、列表、详情同步使用这些头像；既有 agent UI 和 Activity 通过 avatar_url 自动显示。
- 两个初始注册脚本已使用 catalog 头像，后续新库注册不会丢掉头像。
- 组件测试 11 passed；`scripts/agent-avatars-qa.mjs` 验证 34 agents / 15 distinct avatars，逐个资源 200 image/png，并检查角色图、详情、Activity、agent 列表图片真实加载。

## TAP agent 阵容统一到 SMART（2026-11-22）

用户要求将 SMART agent 放到 TAP，替换 TAP 原有 agent 及票据/Activity 中旧引用。

- `scripts/sync-smart-agents-to-tap.py` 事务内将 SMART 的 15 个配置复制到 TAP（workspace_id 重绑定）；同 ID 的 15 个旧配置由 SMART 配置替换。
- 旧 Product/Architecture/Engineering/Quality partner 分别映射至 workflow-intent/design-role/implementation/verifier；移除四个旧 agent，TAP 现有 15 个 agent。
- 实际需重写的引用在 3 个 environment session 及 3 个旧 squad 中。现有票据、Activity、Run 已使用保留的 workflow-* 身份，身份不变但解析到新配置；不伪造新历史，不删除票据或 Activity。
- SMART 源工作空间保持不变。旧 runtime 记录、原始导入快照和历史审核材料保留，不重新绑定到新 agent。
- 写入前 SQLite backup `.before-smart-to-tap-*`。临时副本验证替换、源数据不变和重跑幂等。
- 头像 QA 数量调整为两空间各 15，即 30 个 agent。

## 用户纠正头像：必须使用原生 emoji avatar（2026-11-22）

此前自制 Workpal glyph 徽章误解了用户需求，已撤销：删除 30 个自制 PNG/SVG 与生成脚本。使用项目从 Multica 保留的 `emoji:` avatar_url 格式和 `ActorAvatar` 原生组件，按领域分配标准 emoji（例如开发💻、QA🧪、安全🛡️、发布🚀），不再设计一套图片头像。

两工作空间的 30 个 agent、role catalog、Agent Team 页面及注册脚本已同步。数据库写入前备份；现有列表/Activity 自动通过原生组件解析 emoji。旧“领域徽章”段仅为历史记录，不再描述当前实现。

用户问“为何 agent 不能改头像”：实际工作空间 agent 已有编辑能力，入口为详情 Settings → General → Avatar → Change avatar；详情顶部仅展示头像，Agent Team catalog 是静态角色介绍。浏览器实测 TAP Security Engineer 用原生选择器改为 emoji:🦁，PUT /api/agents/workflow-security 返回 200；新浏览器会话重新登录后仍显示🦁，最后已恢复🛡️。无需新增头像保存接口。

## 小队协作与单人指派落实（2026-11-22）

用户确认：项目通常由 Squad 协作推进，也可直接安排单个 agent，不强制一票一人一次运行。

- SMART 注册 5 个现有小队及负责人、成员关系；`register-workflow-team.py --workspace workpal-team` 支持指定工作空间，原有角色配置不覆盖。
- `scripts/assign-smart-work.py` 将既有 21 张票安排为 16 张 Squad 负责、5 张直接 agent 负责，保留 ticket/status/阶段/历史成果；增加当前分工和验收责任说明，重跑不重置人工安排。
- 后端现在按 assignee_type + assignee_id 过滤小队/个人工作列表；支持仅未指派及混合筛选。指派变化在同一事务写入 Activity，重复同值不产生事件；部分字段改派也验证完整身份、拒绝跨工作空间引用。
- 本地配置显式启用 `issue_assignment_without_runtime`，解除指派器的运行环境门槛；权限检查保留，其他后端未声明能力时保留原运行环境要求。只安排工作，不启动模型。
- agent 详情顶部头像已接入原生 AvatarUploadControl，可直接选择 emoji；只对有编辑权限的用户开放。浏览器实测保存、刷新和重进均保留；验证后恢复原头像。
- 验证：62 个前端测试通过；完整 `npm run check` 1936 Python tests、30 subtests、launcher 与构建通过。随后修复审查发现的未指派筛选问题，workspace content 全部 29 tests 通过。
- `scripts/smart-coordination-qa.mjs` 验证 5 squads / 16 squad tickets / 5 agent tickets，全部按类型过滤、Squad → agent → Squad 的实际指派确认和 Activity 记录，以及小队 recent work 排除其他工作。验证最终恢复 SMART-7 为 Engineering delivery。
- 既有交付物覆盖不足仍是独立内容问题；此轮不把分工说明当成代码、评审或测试交付物。并行出现的 evidence.py / delivery-evidence 改动未由本轮接管。
