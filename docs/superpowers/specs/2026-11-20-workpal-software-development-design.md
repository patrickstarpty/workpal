# Workpal 软件开发协作平台设计

状态：待用户评审。用户已选择统一工作平台与独立执行端方案，尚未批准本设计文档。

本稿以本地 Multica 来源文档为功能基线，定义面向软件开发团队的 Workpal 完整能力和分期边界。后端使用 Python；保留 Workpal 品牌、English UI 与当前 Multica 视觉体系。现有原型仅作为交互参考，不直接修改。本文是待评审设计，不代表功能已经实现。

## 意图与已确认决策

用户希望 Workpal 用于软件开发，同时支持人管理工作与 Agent 真实执行。软件需求、设计、编码、测试、评审和交付形成统一记录；开发者仍可使用外部工具，并将实际产物纳入同一流程。

已确认：功能参考 Multica 来源文档；后端 Python；采用统一工作平台与独立 Runtime；原型以普通文件保存在 assets/archives，不打 ZIP，不直接修改。English UI、Workpal 品牌和现有视觉体系延续项目约束。

成功标准是团队可以从一条有验收标准的需求出发，让人或 Agent 完成仓库修改，提交真实测试证据和 PR，经过评审、返工后形成可追溯的结果；不是页面数量或 Agent 数量。

本文中的首期部署、默认权限、触发政策、数据保留和发布边界是设计者建议，供本次文档评审确认；不将其描述为用户已决定。

## 目标与边界

目标：统一开发协作、真实执行、可靠恢复、证据评审、可复用 Skills。人工执行和 Agent 执行使用相同交付对象，来源身份分别记录。

首个可用版本必须包含真实改代码、执行测试和创建 PR；建设顺序可以先做记录服务，但不能以只有任务管理的版本宣布完成。首期面向一个可信的小型团队、一个 GitHub 仓库、一台团队自有 Runtime 和一种已安装且已授权的 Agent CLI。具体 CLI 留给实施者根据可用环境选择；不得宣称首期已兼容所有提供方。

暂不包含自动生产部署、无人审批合并、公共 Skill 市场、第三方不可信租户托管、原生移动端和多提供方调度优化。Release 保存发布与验证记录，实际部署由团队现有流程执行，后续再接 CI/CD。

失败边界：未执行却报告成功；把运行结束当成交付通过；历史证据随配置改变；同一触发产生重复 PR；取消后在不知情时继续派发；通过导出泄露凭据。界面不能以编造数据掩盖失败或空态。

## 方案选择

方案一为 Python 统一工作平台加独立执行端。服务端管理身份、业务、调度、审计与交付，Runtime 在团队机器上准备仓库并调用 Agent CLI。优点是支持人工与 Agent 并行、靠近已有开发环境；代价是需要执行协议、心跳、租约和断连恢复。用户已明确选择此方案。

方案二为 Python 平台集中管理与执行。所有项目在服务端隔离环境中运行，部署和环境控制更集中，但需要首期建设完整执行基础设施并承担各类项目依赖和凭据运维。因首期成本更高且不如方案一贴合 Multica 的分工，未选。

方案一仍允许未来在云主机部署 Runtime；这不改变服务端不直接执行仓库命令的边界。

## 来源文件

本地 Multica checkout HEAD 为 `428ef30fed49ad3233ef041e74999ecc8fa3168e`。以下链接指向本次阅读的工作区文件；工作区文件可能随后续修改变化，提交号用于定位基线。

- [愿景](../../../../multica/VISION.zh.md)：人与 Agent 的共同工作记录、行动协调与人的最终责任。愿景不能当作已实现功能清单。
- [产品与架构概览](../../../../multica/README.zh.md)：任务、Agent、Squad、Skills、运行时、自动化、连接与访问控制。
- [核心概念](../../../../multica/apps/docs/content/docs/concepts.zh.mdx)：Issue、Run、Agent、Runtime 等对象的职责。
- [执行记录](../../../../multica/apps/docs/content/docs/tasks.zh.mdx)：触发、排队、领取、执行、失败、取消与重试。
- [Skills](../../../../multica/apps/docs/content/docs/skills.zh.mdx)：能力包、来源、导入、刷新、绑定与后续运行生效。
- [项目契约](../../../../multica/server/internal/service/builtin_skills/multica-platform/references/projects.md)：持久上下文、仓库和本地目录。
- [Squad 契约](../../../../multica/server/internal/service/builtin_skills/multica-platform/references/squads.md)：leader 路由，不自动向全体成员派发。
- [Autopilot 契约](../../../../multica/server/internal/service/builtin_skills/multica-platform/references/autopilots.md)：schedule、webhook、manual 触发及两种执行模式。
- [Runtime 契约](../../../../multica/server/internal/service/builtin_skills/multica-platform/references/runtimes.md)：服务端与执行端边界、任务身份、工作目录与用量来源。
- [状态生命周期](../../../../multica/docs/issue-status-lifecycle-rollout.md)：状态 key 与生命周期 category 分离，自定义标签不赋予自动化副作用。

以下“沿用”指采纳这些来源中的概念和行为边界；“扩展”指 Workpal 的产品设计，不宣称 Multica 已具备。

## 产品主线

Workpal 管理从意图到交付的协作过程，并把可验证的方法沉淀为团队 Skills。首要用户是项目负责人、执行成员、评审者和工作区管理员；Agent 是被配置、被授权的执行身份。

主线为：收集意图 → 明确范围和验收 → 建立项目上下文 → 分派工作 → 执行并保留证据 → 评审与返工 → 完成和发布反馈 → 沉淀 Skill。

每一步都应回答：当前目标是什么、谁负责、依据是什么、产物在哪里、下一步由谁决定。Chat 可以发起工作，但 Issue 和 Delivery 承担持续记录。

## 功能范围

| 模块 | 沿用 Multica 的基线 | Workpal 设计与交互结果 |
| --- | --- | --- |
| Workspace | 工作区隔离、成员、角色 | 切换工作区后所有对象、搜索和权限按当前范围生效；跨区分享必须显式导入 |
| Inbox | 提及、分配、订阅动态 | 增加待评审、待补充信息、阻塞决策入口；每条通知链接实际对象，已读不等于问题解决 |
| Issues | 描述、负责人、状态、讨论、子任务、历史 | 验收标准、依赖、交付历史和人工完成理由；列表与看板使用相同筛选条件 |
| Projects | 目标与持久资源容器 | 项目概览集中显示目标、上下文、依赖、待决策和交付；仓库绑定与工作区仓库目录分开 |
| Chat | 不依附 Issue 的交流与执行 | 可将对话转为 Backlog Issue，保留来源快照；后续消息不静默重写任务要求 |
| Agents | 指令、提供方、Skills、Access、Runtime | 配置页明确能力、可用状态和权限；修改配置只影响后续运行 |
| Squads | leader、成员、职责与协调指令 | 分派给 Squad 后由 leader 接收；显式拆出子任务才形成成员分工，展示各自产物和阻塞 |
| Runs | 独立运行、事件、取消与重试 | 输入快照、执行事件、产物、用量和失败原因；重试产生新记录并关联前次 |
| Deliveries | 来源强调验收工作本身 | 扩展为版本化产物、逐条验收证据、限制说明、差异比较和明确评审决定 |
| Skill Hub | 创建、导入、来源刷新和绑定 | 扩展版本快照、验证记录、来源交付、适用边界和废弃替代；使用次数不等于有效性 |
| Autopilots | 时间、Webhook、手动触发；创建 Issue 或直接 Run | 展示时区、下次触发、执行模式、最近结果及跳过原因；关闭页面后由未来服务端调度 |
| Connections | 代码托管、消息渠道和 Runtime | 区分配置已保存、待授权、已连接、连接失效；PR 关联不能被当成已合并或已发布 |
| Analytics | 运行、用量、错误和团队视图 | 先做可追溯运行统计，再做交付周期、返工与 Skill 使用分析；无采集数据时显示空态 |
| Settings | 成员、访问、资源和配置 | 权限、事件审计、导出、保留策略；敏感凭据不进入任务提示或离线导出 |

## 页面结构

保留当前主导航，减少迁移成本：Work 下放 Inbox、Issues、Projects；Team 下放 Agents、Squads、Skill Hub、Runtimes、Runs、Workflows 和 Analytics；Chat 管理独立对话；Auto 管理 Autopilots；Settings 管理成员和连接。

Delivery 首先是 Issue 的一级标签和 Inbox 的审核入口，不增加顶层导航。项目上下文放在 Project → Context；发布记录先作为 Project → Releases 扩展，不预先建设独立发布平台。

Issue 详情包含 Overview、Discussion、Deliveries、Activity；右侧保留属性和运行记录。Run 详情分为 Input、Timeline、Artifacts、Usage，明确提示实际失败原因与可用操作。Skill 详情包含 Overview、Content、Versions、Validation、Usage；导入预览展示来源、文件和冲突处理选择。

界面继续使用 Inter、中性表面、紧凑行、克制边框和阴影。390px 窄屏下侧栏变为可关闭面板；状态变化不能只靠颜色；表单、菜单、审核操作均可用键盘完成。保留本地 review notes，界面不加入 prototype、research 或 simulation 标签。

## 对象与状态契约

- Issue 是工作承诺；Run 是一次尝试；Delivery 是一次提交；Review 是对特定提交的决定。四者分别存储和转换。
- Issue 使用稳定 status key，另设 unstarted、started、done、closed 生命周期分类。自定义状态仅归类，不隐含派发或完成行为。
- 默认路径为 Backlog → To do → In progress → In review → Done，另有 Blocked 和 Cancelled。归档是可见性属性，不新增状态。
- Run 初期支持 queued、dispatched、running、completed、failed、cancelled；后续执行集成增加 deferred 和 waiting_local_directory。completed 不自动将 Issue 标为 Done。
- 创建 Run 时固定任务要求、项目资源、Agent 配置、Skill 版本、工作流版本和触发者身份。历史展示不得从当前配置反向重建。
- 同一 Issue 可有多个 Run；较晚返回的 Delivery 默认为候选，不自动覆盖当前提交。切换当前提交必须保留操作者和原因。
- Review 必须引用 delivery_id、version 和当时的验收标准。批准需通过产物与证据检查，并在同一事务中确认该提交仍是当前版本。
- Request changes 保留原评审和提交，下次尝试携带返工原因。修改验收标准后，旧批准不覆盖新要求。
- 人工完成必须记录理由与操作者；审核通过、PR 合并、部署和上线验证分别记录，不能互相替代。

## 四个关键使用场景

### 从讨论形成可验收任务

用户在 Chat 中选择项目，补充目标和限制，进入 Create issue 表单确认标题、范围、验收标准和负责人。保存到 Backlog 不触发执行；显式 Start work 才进入派发校验。验收：来源对话可回看、缺少必要参数时保留草稿、重复提交只创建一次。

### Squad 分工与交付评审

负责人将 Issue 交给 Squad；leader 接收成员职责和项目快照，提出或创建明确子任务。各子任务独立运行、提交，主任务汇总产物。评审者逐条核对证据并批准或退回。验收：成员不会因加入 Squad 就同时启动；子任务执行结束不跳过父任务验收。

### 将经验沉淀为 Skill

从已批准 Delivery 发起 Create skill draft，保留来源和作者，整理适用条件、输入、步骤、输出、停止条件及案例。通过验证后发布不可变版本，Agent 绑定确定版本；新版本展示差异后再升级。验收：历史 Run 可定位当时内容；来源刷新形成候选版本，不覆盖已发布内容。这是相对 Multica 原位刷新的明确扩展。

### 计划任务与异常恢复

创建 Autopilot 时明确时区、触发条件、负责人、执行模式和失败处理。每次触发先记录 admission 结果，再派发；重复 Webhook 复用同一记录。验收：暂停后不再接纳新触发；跳过、派发失败和运行失败分别可见；恢复服务时按显式 misfire 策略处理，默认记录错过而不批量补跑。

## Python 后端设计

采用模块化单体作为目标架构，API、调度 Worker 和执行 Runtime 分离职责。Python 负责业务服务和未来控制进程；第三方 Agent CLI 作为外部执行器，不要求其实现语言为 Python。具体 Web 框架及依赖版本在实施设计中锁定，本轮不安装依赖。

当前 Python 与 SQLite 服务提供本地记录持久化，业务规则仍主要在前端。它不是完整后端：后续需要将权限、状态转换、派发、评审门禁和幂等性移到服务端。不能只将整份前端 JSON 写入数据库就视作完成。

模块边界：identity 管成员与权限；work 管项目与 Issue；collaboration 管评论、Chat 与 Inbox；agents 管 Agent 与 Squad；execution 管 Run、快照和事件；delivery 管产物与评审；skills 管内容和版本；automation 管触发与调度；integrations 管外部连接；audit 管业务事件和导出。

持久化分为结构化业务记录、追加事件和产物文件。已有原型继续保留 SQLite；新联网产品从首期使用 PostgreSQL，避免同时实现两套并发业务存储。原型 SQLite 不直接升级为生产库。工作区身份必须出现在业务查询和写入授权中；客户端提交的 workspace_id 本身不是授权依据。

核心实体包括 Workspace、Membership、Project、ProjectResource、Issue、IssueDependency、Comment、Conversation、Agent、SquadMember、Runtime、Run、RunInputSnapshot、RunEvent、Delivery、Artifact、CriterionEvidence、Review、Skill、SkillVersion、SkillBinding、Autopilot、TriggerDelivery、Notification、AuditEvent。

所有可变主实体带 revision；旧 revision 写入返回冲突，并允许用户比较后重试。创建 Run、触发自动化和外部事件接收使用明确作用域的 idempotency_key。状态修改和待派发事件在同一数据库事务内写入 outbox，Worker 用租约领取；重试按至少一次投递设计，通过幂等约束防止重复业务结果，不承诺外部工具副作用恰好一次。

Runtime 使用独立任务身份，心跳报告能力和可用性。Worker 不在 API 请求进程内直接启动 CLI。取消先记录请求，收到执行端确认后转为 cancelled；断连期间保留未知或等待确认状态。日志支持单调序号和断点续读；敏感内容在写入日志前脱敏。

服务接口按动作表达业务意图，统一由前端与未来 CLI 调用：

| 接口草案 | 服务端约束 |
| --- | --- |
| POST /api/v1/workspaces/{id}/issues | 成员权限、输入校验、幂等创建 |
| POST /api/v1/issues/{id}/transitions | revision、合法状态转换、显式派发规则 |
| POST /api/v1/issues/{id}/runs | 访问权限、Runtime 就绪、输入快照、重复触发处理 |
| POST /api/v1/runs/{id}/cancel | 操作者授权、取消请求和执行确认分离 |
| GET /api/v1/runs/{id}/events?after= | 有界分页、序号续读、工作区隔离 |
| POST /api/v1/issues/{id}/deliveries | 产物引用、验收证据、版本生成 |
| POST /api/v1/deliveries/{id}/reviews | 当前版本、审核权限、证据门禁、并发冲突 |
| POST /api/v1/skills/{id}/versions | 内容快照、来源、哈希、不可变已发布版本 |
| POST /api/v1/autopilots/{id}/trigger | 权限、触发幂等、准入结果和派发记录 |

事件订阅采用服务端推送接口，读取可以回退到分页轮询；具体传输协议在 Runtime 接入阶段确定。所有错误返回稳定 code、可读 message、request_id 和必要的恢复提示。

## 开发交付的端到端行为

以修复上传重试导致重复文件为验收场景。产品负责人创建 Issue，写清重现步骤、预期行为和验收标准；开发者确认范围和方案，选定仓库与基线提交。Start work 先显示计划使用的 Agent、Runtime、Skills、目标仓库及允许的操作，服务端校验后记录输入快照并入队。

Runtime 为 Run 创建专用分支和工作目录，执行修改与测试。Agent 可以提出需要人决定的问题，此时保存等待原因并通知 Inbox；需要继续时产生带新输入快照的后续 Run，保留父子关联。首期不依赖提供方支持实时插话或进程暂停。

等待人决策时，当前进程先停止，保存工作目录检查点，Run 进入终态 awaiting_input；它不占活动运行槽位，也不代表执行成功。检查点包括 base SHA、已有本地提交、tracked diff 与允许保留的未跟踪文件清单及哈希，排除凭据、构建缓存和忽略文件；无法完整保存时显示 checkpoint_incomplete 并禁止自动 Resume。Resume 将人的回答、授权决定和检查点引用写入新快照，在新隔离目录恢复后继续。旧检查点不修改，也不需要先生成 Delivery。原进程尚未确认停止时仍属活动运行，不能 Resume。

开发者或 Agent 提交 Delivery，包含变更摘要、提交 SHA、PR、测试命令、退出码、原始输出引用、验收证据和已知限制。仅有“测试通过”的文本不算测试证据。未经采集的人工报告必须标明由人提交，不能转换成工具执行事件。

评审者在同一页查看要求、diff 引用、证据与限制。退回后再次运行并形成新 Delivery；批准只作用于所审提交。代码类 Issue 的默认完成策略为当前 Delivery 已批准且对应 PR 的已批准 head 已合并；文档等非代码任务可在批准后完成。合并由人通过 Git 服务执行，平台首期只创建 PR、读取检查状态和确认合并事实。

PR 增加新提交时，原 Review 保留历史但不再覆盖新 head。Webhook 更新与主动对账均检查仓库、PR、head SHA 及事件身份；延迟事件不得将旧提交批准附着到新提交。Git 服务暂时不可用时显示状态未确认，不推断完成。

项目 Release 关联具体已完成 Issue 和提交，记录目标环境、发布人、部署引用、验证与回退说明。它不自动调用生产部署。

## 派发与工作流规则

首期采用显式派发，避免编辑负责人意外消耗执行资源：保存 Issue、变更状态、绑定 Agent 和添加评论本身不启动 Run。Start work、Retry、Resume、确认的 Chat Send、Autopilot 触发才进入统一派发入口。提及默认通知；用户选择 Run agent 后才派发。这是对 Multica 部分自动触发行为的有意调整。

工作流配置定义状态、允许的转换、责任角色、交付门禁和返工目的地；首期不实现任意脚本工作流。新配置只作用于后续 Run，正在审核的 Delivery 继续使用快照规则。Block 记录问题和责任人；解除阻塞不自动执行。

子任务依赖必须在同一工作区，拒绝依赖环。父任务可在依赖完成后进入待决策队列，不因子任务 Run 完成就自动 Done。Squad leader 可以创建分工草案；首期由人确认后派发子任务。后续在明确授权与预算内开放 leader 自动派发。

## Runtime 协议与恢复

Runtime 是独立 Python 守护进程，运行在团队控制的机器，首期使用出站 HTTPS 领取任务与上报事件，不要求客户端接受公网入站连接。界面实时更新可采用 SSE；轮询和事件读取具有相同授权边界。协议带版本号，能力不兼容时拒绝派发并给出原因。

注册由管理员签发一次性配对凭据，绑定 workspace 与 Runtime 身份。后续使用可撤销的 Runtime 凭据，Run 领取后只获得短期任务令牌，限定对象、动作和有效期。令牌内容不进入模型提示。凭据保存于受限文件或系统凭据设施，具体设施由实施者选择。

Run 具有 lease_owner、lease_epoch、lease_expires_at。领取和续约在事务中校验；只有当前 epoch 可接受状态更新。Runtime 持久化 run_id、进程标识、工作目录、事件游标与待上报事件，重启后先核对实际进程和服务器状态，再决定恢复或报告中断。

服务端超时不意味着远端进程已停止：租约丢失后进入 recovery_required，不立即在第二个 Runtime 重跑。旧执行端必须停止任务；无法确认时由管理员核验并记录处置。受限外部凭据与运行隔离用于降低旧进程继续产生副作用的风险，租约本身不构成操作系统隔离。

事件以 run_id、epoch、sequence 去重；相同键不同内容拒绝并审计。进程结束与事件上传分别确认：日志有缺口时可以记录执行终态，但交付须显示 evidence_incomplete，不能声称完整验证。

Cancel 对尚未领取的任务立即生效；活动任务进入 cancel_requested，执行端终止进程组并确认。断连期间保持取消待确认，阻止替代执行。Retry 始终创建新 Run；基础设施恢复重试有上限，默认最多一次，鉴权、配置或测试失败不自动重试。

同一 Issue 与 Agent 首期仅允许一个活动 Run，重复 Start 返回已有运行。跨 Issue 并发受 Runtime 槽位和仓库工作目录隔离控制。并行候选 Delivery 的数据模型预留，首期不默认开启同一任务的竞赛执行。

## 仓库与执行边界

首期使用 Runtime 自有仓库缓存与每次运行独立 worktree，固定输入 base SHA，创建 workpal 命名空间的唯一分支。不能修改原型工作目录、用户当前分支或共享缓存中的工作树。后续返工从选定 Delivery 的提交开始，所有基线均可追溯。

在开始执行时明确允许读取、修改、测试、推送任务分支和创建 PR；合并、修改保护规则与部署不在 Agent 默认权限内。需要额外操作时记录 approval_required，由有权限的人作出决定。Skill 中的指令不能提升授权。

初期只接受团队可信仓库和可信提供方，Runtime 运行于专用系统用户或专用容器，限制可访问目录与凭据。worktree 只提供 Git 工作隔离，不视为安全沙箱。不将公共不可信仓库执行作为首期能力。

PR 创建使用 run 与仓库的持久 operation key；外部调用超时后先按分支和仓库对账，不盲目重建。推送使用预期分支状态检查，禁止强推他人分支。测试结果记录命令、工作目录、提交、退出码与时间，禁止将旧提交测试用于新提交的批准。

GitHub 写操作通过 Runtime 的受控操作代理完成，Agent CLI 不持有 GitHub 仓库写凭据。CLI 可在隔离目录本地编辑和提交，再请求 push_branch 或 create_pr；代理核验当前任务授权、仓库、允许分支、预期提交与操作键后执行。代理以独立系统身份保存凭据，任务进程不能读其文件、环境或进程接口。任务侧禁止继承用户 gh 配置、SSH agent 和通用 Git 凭据。只允许上述动作，不提供任意 GitHub API 转发，因此不暴露合并、保护规则修改和部署操作。提供方自身的模型认证单独配置，不共享 GitHub 写权限。此代理属于 M1 的必要执行边界。

## 权限与数据管理

首期提供管理员创建的本地团队账号、服务端会话和 owner、admin、member 三种角色，不开放公共注册。密码使用成熟哈希库，框架和认证依赖由实施者在计划阶段核验选择，禁止自制密码学。

工作区成员默认可读业务记录；member 可创建和编辑任务，只有获准使用 Agent 与 Runtime 的成员可执行；项目 reviewer 可批准或退回，Agent 不能批准自己的产物。owner 和 admin 管成员、连接、Runtime 和配额。批准和执行时均实时检查权限，不能只信任创建时的权限快照。

授权快照用于解释历史，当前授权用于允许下一次副作用。撤销成员或 Runtime 凭据后停止新任务和新令牌签发，活动执行进入取消流程。执行中无法立即收回已经发给外部 CLI 的权限时，界面保留这一未确认状态。

产物首期存在服务器管理目录，用数据库记录 workspace、哈希、大小与所有者，通过授权下载接口访问，禁止直接拼接用户路径。建议默认单产物 25 MiB、单次运行产物总计 250 MiB，超限记录明确错误。原始执行日志保留 90 天；被 Delivery 引用的证据随 Delivery 保留，不能被日志清理破坏。清理和导出均有审计记录。

备份须包含数据库和产物清单，并校验哈希及恢复后的引用。离线 HTML 导出只包含用户有权导出的选定记录，默认排除执行原始日志和全部凭据；用户文本转义。离线文件不能实施服务器权限，也不支持自动回写合并。

## 原型与新产品的关系

原型存档位于 assets/archives/workpal-baseline-20261120-001724，保留现有静态源码、构建产物与校验清单。已存档的说明反映当时状态，不跟随新设计修改。

新联网产品后续在独立目录实现，建议 apps/workpal-web 与 services/workpal，Runtime 在 runtimes/workpal；此次不创建这些目录或脚手架。原型的无依赖单 HTML 约束继续适用于存档和离线交付，Python 联网系统承担真实协作与执行，不能声称同一个离线文件能完成这些网络能力。

不直接复制原型的整份记录库成为正式数据。新产品从空工作区开始；需要迁移时提供显式预览和导入，把原记录 ID 映射到新 ID，保留 review notes、来源和时间。样例运行、虚构对话及用量不得导入为真实执行或统计证据。

## 分期与验收

M1 是首个可用版本，包含共享任务记录、Python 业务服务、账号权限、一个 Runtime 和提供方、GitHub PR、人工评审、取消恢复及基础 Skill 固定版本绑定。可以分成记录服务、执行协议、真实交付三个内部里程碑，但全部完成后才视为 M1。

M2 扩展 Squad 分工、依赖调度、完整 Skill 创建验证发布、计划与 Webhook 自动化。M3 扩展多 Runtime、多提供方、更多代码托管和消息渠道、Release 集成与效果分析。首期不以完整复制 Multica 全部集成为目标。

M1 页面范围明确为 Workspace 与账号、Project 与仓库上下文、Issues 列表与详情、基础 Inbox、Agent 与 Runtime 配置、Run 记录、Delivery 与 Review、Skill 固定版本管理和必要连接设置。Inbox 首期只覆盖分配、待输入、待评审和失败通知；工作流采用固定默认流程，不提供自定义工作流编辑器。M1 提供只读离线 HTML 的选定 Issue 与交付导出，以及备份恢复。独立 Chat、自定义 Workflows 和基础运行 Analytics 放入 M2；完整团队效果分析放入 M3。Issue 内的评论、补充输入和 Resume 已能支撑 M1 的交互闭环。

验收表中人工开发、Agent 开发、返工评审、重复派发、恢复取消、权限隔离、固定 Skill 快照以及备份导出均属于 M1；Webhook 重复处理和完整 Skill 发布升级属于 M2。M1 的 GitHub PR 状态 Webhook 属于连接必要能力，与 M2 的通用自动化 Webhook 分开。

| 验收场景 | 可观察结果 |
| --- | --- |
| 人工完成开发 | 可提交真实 PR 和证据并进入同一评审流程，无需伪造 Run |
| Agent 端到端开发 | 独立分支实际发生改动，测试可追溯到提交，PR 可核验，Run 完成不越过审核 |
| 返工与并发评审 | 新版本保留旧记录；两次并发审核仅接受符合当前 revision 的决定 |
| 重复派发和重复 Webhook | 一次业务动作仅对应一个有效 Run 或 PR，重复请求返回已有结果 |
| 断连、重启与取消 | 任务不被不明状态自动替跑，恢复后日志续传，取消确认可追溯 |
| 权限和隔离 | 跨区 ID 访问被拒绝，Agent 不可批准交付，任务进程不能访问其他项目凭据 |
| Skill 更新 | 历史 Run 使用旧快照；新版本验证和升级不会改写历史 |
| 备份与离线导出 | 恢复后证据引用有效，导出无凭据，离线审阅可打开 |

验证分为领域测试、真实数据库并发测试、假 Runtime 的协议故障测试和浏览器交互测试。真实模型调用只在后续实施且配置授权后进行验收，本次设计不运行模型。未来修改原型交互必须运行 npm run check；本次文档改动只检查引用、内容和 Git 差异，避免重建存档对应的 dist。

## 留给实施者的决定

Python Web 框架、ORM、迁移工具、前端框架、具体提供方及其适配器参数、部署打包方式和索引细节，由实施者在不改变本稿行为契约的前提下确定，并在实施计划中记录依据。Python 模块化单体、PostgreSQL、独立 Runtime、不可变历史、服务端授权、显式派发和人的最终评审不由实现细节改变。

本设计批准后再编写实施计划，不在此次开始产品代码、依赖安装或真实执行。

