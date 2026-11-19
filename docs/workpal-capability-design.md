# Workpal 功能与 Python 后端设计

本稿是早期能力梳理，已被[正式设计](superpowers/specs/2026-11-20-workpal-software-development-design.md)取代。最新用户要求为 SQLite 统一持久化、GitHub 与 Azure Repos Git、首版包含独立 Chat、复杂工作流、自动化、真实环境故障调查、Jira 建单与修复及完整核心能力；下文旧分期不再作为实施依据。

本稿以本地 Multica 来源文档为功能基线，定义 Workpal 的完整能力和分期边界。后端使用 Python；保留 Workpal 品牌、English UI 与当前 Multica 视觉体系。现有原型仅作为交互参考，不直接修改。本文是待评审设计，不代表功能已经实现。

## 来源基线

本地 Multica checkout HEAD 为 `428ef30fed49ad3233ef041e74999ecc8fa3168e`。以下链接指向本次阅读的工作区文件；工作区文件可能随后续修改变化，提交号用于定位基线。

- [愿景](../../multica/VISION.zh.md)：人与 Agent 的共同工作记录、行动协调与人的最终责任。愿景不能当作已实现功能清单。
- [产品与架构概览](../../multica/README.zh.md)：任务、Agent、Squad、Skills、运行时、自动化、连接与访问控制。
- [核心概念](../../multica/apps/docs/content/docs/concepts.zh.mdx)：Issue、Run、Agent、Runtime 等对象的职责。
- [执行记录](../../multica/apps/docs/content/docs/tasks.zh.mdx)：触发、排队、领取、执行、失败、取消与重试。
- [Skills](../../multica/apps/docs/content/docs/skills.zh.mdx)：能力包、来源、导入、刷新、绑定与后续运行生效。
- [项目契约](../../multica/server/internal/service/builtin_skills/multica-platform/references/projects.md)：持久上下文、仓库和本地目录。
- [Squad 契约](../../multica/server/internal/service/builtin_skills/multica-platform/references/squads.md)：leader 路由，不自动向全体成员派发。
- [Autopilot 契约](../../multica/server/internal/service/builtin_skills/multica-platform/references/autopilots.md)：schedule、webhook、manual 触发及两种执行模式。
- [Runtime 契约](../../multica/server/internal/service/builtin_skills/multica-platform/references/runtimes.md)：服务端与执行端边界、任务身份、工作目录与用量来源。
- [状态生命周期](../../multica/docs/issue-status-lifecycle-rollout.md)：状态 key 与生命周期 category 分离，自定义标签不赋予自动化副作用。

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

持久化分为结构化业务记录、追加事件和产物文件。平台数据先统一使用 SQLite，包含业务记录、事件与附件内容；首期同时支持 GitHub 与 Azure Repos Git。正式设计以 [软件开发协作平台设计](superpowers/specs/2026-11-20-workpal-software-development-design.md) 为准。工作区身份必须出现在业务查询和写入授权中；客户端提交的 workspace_id 本身不是授权依据。

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

## 分期交付与验收

1. 设计冻结：确认来源映射、对象、状态、页面和接口；保存原型基线，保留未决设计，不修改交互。
2. 本地业务后端：Python 承接 Issue、项目、评论、Delivery、Review、Skill 版本和历史快照。验收服务重启恢复、版本冲突、评审门禁与数据导出。此阶段无真实 Agent 执行。
3. 协作基础：身份与权限、Inbox、审计、共享数据、连接状态。验收跨工作区隔离、权限撤销和通知去重。
4. 执行集成：单一 Runtime 和单一提供方先跑通领取、事件、交付、取消、重试，再增加 Squad 分工。真实模型调用作为独立后续实施范围。
5. 自动化与沉淀：后台调度、Webhook、Skill 验证与发布、发布反馈。验收重复投递、服务中断恢复、Skill 版本追溯。

当前原型仍须保持无依赖、可导出单个离线 HTML；未来联网产品可以依赖 Python 服务。离线导出仅携带允许导出的快照，不承诺同步、后台执行或多用户权限。来源演示数据和真实事件分开存储，用量与效果统计只读取真实事件。

## 评审重点

先评审 Issue → Run → Delivery → Review 的闭环和 Skill 版本策略，再确定真实运行时接入范围。发布自动执行、多渠道接入和复杂权限细分放到后续，不作为首个可用版本的必要条件。

实现阶段需运行 npm run check，并为 Python 的授权、状态转换、幂等、并发评审及恢复路径增加有意义的测试。此次仅添加设计文档和移动既有存档，不运行会重建 dist 的检查，以保留原型基线。
