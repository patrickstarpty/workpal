# Workpal Parallel Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按真实依赖并行完成完整首版，子Agent实施，主代理只做任务设计、调度、审查和验收。

**Architecture:** 已验收A1–A4作为共同基线；各条工作线通过小Interface对接，实施文件所有权互斥。新增Django app先用各自测试配置验证，交给指定集成Agent统一加入生产配置，避免并发改settings或既有Registry。独立开发不等于已经集成可用。

**Tech Stack:** 沿用主计划，Python3.11/Django/SQLite、原生ES modules；GPT 6.1 Sol实施。不新增依赖。

**Spec:** [首版设计](../specs/2026-11-20-workpal-software-development-design.md)、[主计划](2026-11-20-workpal-software-development.md)、A/B/C/D四份批次计划。本文件依据用户最新“所有任务能并行就并行，用子agent去做，你只监工”覆盖原A→B→C→D整批串行调度；功能和验收范围不缩减。

## Global Constraints

- “后端 Python，平台数据先统一放 SQLite”。
- “completed 不自动将 Issue 标为 Done。”
- “授权快照用于解释历史，当前授权用于允许下一次副作用。”
- “不把人工评审改成 Agent 自我批准。”
- Copilot CLI默认；Codex CLI、Claude Code、Gemini CLI、OpenCode只留extension-only/not_implemented Interface，不自动回退。
- 当前并发额度含主代理共4个，最多3个实施子Agent同时运行；一个结束即补位。每次新审查使用新Agent，不复用实施者自评作独立审查。
- 共享脏工作区；不commit/push/stash/reset/clean/建worktree，不修改旧原型和保护路径。保留85项原SHA256基线 `/tmp/workpal-supervision-baseline-20261120.json`；精确允许例外见 `2026-11-20-workpal-protection-exceptions.json`（.gitignore既有差异及用户明确确认的studio.js单行改动），其他新差异必须核查，不回退或静默重建基线。
- 不执行真实模型、Runtime、外网业务、Skill安装、npm exec/npx或安装依赖；仅已有Python/Node和隔离临时SQLite/loopback。`python`不可用，使用`.venv-workpal/bin/python`或`python3`。
- 主代理不承担成片功能实施，负责设计、调度、审查和验收；独立审查发现的小型问题按当前编排规则由主代理直接修正，较大实施仍交GPT 6.1 Sol。小型补测须记录真实结果，不伪称测试先行。
- 并行任务只运行本任务专项测试。不要发现半写入兄弟模块后擅自修复，也不要重跑全量把未集成模块的导入失败当基线。统一配置、全量检查、公共README和根npm由后续集成任务独占。

## Review Focus

1. 文件竞争：各任务仅写允许目录、新测试及自己的模块README；不修改config/settings.py、urls.py、根package、公共contracts和旧测试。
2. 依赖假完成：单独配置或纯Interface测试通过只标本模块通过，生产注册、跨模块行为和真实外部验证分别验收。
3. 权限漂移：读取、变更、确认消费和缓存重放均校验当前来源；冻结的快照不授予未来权限。
4. 事实混淆：测试fixture、上传材料、执行结果和部署恢复分开记录；不得以测试数或子Agent报告替代用户路径。
5. 长会话误差：任务有独立计划、文件边界、命令和日志；每波从仓库与工具证据恢复状态，不从旧聊天推定已完成。

## Dependency and ownership map

| 工作线 | 可独立推进 | 必须等待的接线 |
| --- | --- | --- |
| A UI | 既有A1–A4的所有真实页面、状态操作、协作及Delivery/Review | Runtime/Chat等对应后端新增页面 |
| B execution | Agent/Run记录，冻结协议后的Runtime/Provider，代码托管Adapter | 领取/执行/交付端到端、Linux隔离与真实Copilot/PR |
| C collaboration | 图校验、图版本，Skills生命周期，Chat持久记录 | Agent节点与Chat协调依赖B派发；不占Runtime槽位的协调Worker接线 |
| D environment | 环境/调查/上传证据、HTTP采集合同、Jira协议与对账、备份 | 修复依赖B，Chat依赖C；原环境复验和完整首版依赖全链路 |

第一波：B1a、C2a、D1a并行。A5-4c1已验收；A5-4c2状态操作进入就绪队列，在首个空位启动。后续B1b/B2/B3、C2b/C3、D1b/D2、A5其余页面按文件互斥和实际依赖补位，不再等待整批完成。D3/D6整体验收仍等前置事实真实存在。

## Task B1a: Agent configuration and durable Run admission

**Files:** 新增 `services/workpal/workpal/agents/`、`services/workpal/workpal/execution/`（本任务唯一所有者，含正常迁移和各自README）；新增 `services/workpal/tests/settings_execution_lane.py`、`test_execution_admission.py`、`test_agent_configuration.py`。不得改其他文件。

**Interface:** `agents.service.create(actor,name,provider_key='copilot_cli',model='')->AgentView`、`read(actor,agent_id)`、`update(actor,agent_id,revision,**changes)`；`execution.service.start(actor,subject,agent_id,key,trigger='manual')->RunView`、`read(actor,run_id)`、`control(actor,run_id,operation,revision)->RunView`。subject为封闭对象`{type:'issue',id:正整数}`；后续AutomationRun沿同Interface扩展，本任务拒绝尚未支持主体。operation本任务仅cancel；retry/resume明确不可用，不返回虚构Run。

**Behavior:**
- Agent记录workspace、name、provider_key、明确model选择、revision及创建人；owner/admin管理，member读取当前授权记录。提供方值只允许主计划五项；配置保存不证明已安装/认证/可派发。没有真实runtime配对时start创建deferred Run及结构化原因runtime_unavailable；extension-only返回清晰capability_unavailable，不能冒称运行。
- Run快照固定Issue当前不可变要求、项目/资源配置、保存工作流、Agent配置及当前来源引用，均通过所属Module公开读取Interface取得。保留真实FK和内容hash；不跨Module写ORM。返回RunView至少包含id/subject/agent_id/status/revision/input_snapshot/created_at/deferred_reason，枚举沿B1的11态。
- 创建和control使用真实SQLite atomic_write、CAS与来源注册；Run继承Issue、当前要求、项目和Agent的完整限制。普通read/start/cancel都重查成员和当前来源。不能读取的资源不要悄悄从快照删掉。
- `key`是发起人/workspace/动作范围的持久幂等意图；同key不同参数409，合法重放仍复查当前授权。同Issue+Agent人工请求至多一个活动Run；新的manual key复用当前活动Run，不新增派发事实。节点触发需显式非空instance/node/attempt身份，独立作用域；本任务如果未提供完整节点合同则明确拒绝，不用manual key模拟。
- deferred/queued的cancel立即成为cancelled；活动执行状态的cancel语义保留B1原合同，不能在没有执行端确认时宣称进程已停止。cancel只影响Run，不变更Issue状态、要求或人工Delivery/Review。
- 注册薄动作 `agent.create/read/update`、`run.start/read/cancel`（严格schema、revision/key、最小audit字段、来源result_refs）。现有通用HTTP自动复用Registry，无新路由。不要自行实现第二套确认/审计缓存。
- 私有测试settings继承config.settings并只追加本任务两个AppConfig；默认settings仍不接入本模块，交集成Agent后统一注册。迁移正常生成，禁止手抄另一个Module迁移。

- [x] **Step 1:** 通过真实Registry调用agent.create或run.start建立unknown_action行为红灯；不把缺import或迁移失败算红灯。记录 `/tmp/workpal-parallel-b1a-red.log`。
- [x] **Step 2:** 实现上述Interface、模型、动作、来源继承与迁移；先做可操作的配置→deferred Run→读快照→取消闭环，不能仅停在红灯。
- [x] **Step 3:** 独立行为测试覆盖真实持久化/重启读取、创建后改要求/Agent不改旧快照、跨工作区、撤源重放、默认和扩展提供方、无Runtime不伪装可用、同key不同参数、重复人工start、取消CAS及Issue不变；真实双SQLite连接竞争只形成一个活动Run；写后异常完整回滚且同key可重试。
- [x] **Step 4:** `.venv-workpal/bin/python services/workpal/manage.py test tests.test_agent_configuration tests.test_execution_admission --settings=tests.settings_execution_lane --noinput`；以同settings运行makemigrations --check --dry-run与check，均退出0。只报告本任务测试数，保留日志 `/tmp/workpal-parallel-b1a-*.log`。
- [x] **Step 5:** 报告精确Interface、文件、命令、结果和需集成的AppConfig；未实现的配对/claim/lease/event/Worker明确列入B1b，不能宣布Runtime可用。无Git操作。

## Task C2a: Validated workflow graph definitions and safe conditions

**Files:** 新增 `services/workpal/workpal/workflows/graph.py`、`graph_contracts.py`、`GRAPH.md`、`services/workpal/tests/test_graph_definition.py`。不得修改已有workflows contracts/models/service/actions/apps或其测试；本任务为纯计算Module，无新App注册。

**Interface:** `compile_graph(definition)->GraphSnapshot`、`evaluate_condition(condition,values,declared_fields)->bool`。GraphSnapshot为独立JSON对象`{schema_version:1,definition:<规范化图>,sha256:<canonical JSON SHA256>}`；不保留调用者可变对象引用。非法输入抛DomainError invalid_graph/invalid_condition，status400，消息不泄露完整条件值。

**Contract:**
- 图封闭字段`nodes,edges,declared_fields`。nodes为2..200项，每项`id,type,config`；id唯一，1..64 ASCII `[a-z][a-z0-9_]*`。type沿C2：start/end/human_decision/agent_task/condition/parallel/join/delivery_review/create_child。edges最多1000项：`from,to,on,required,max_traversals`；on为always/true/false/approved/rejected，required严格bool，max_traversals严格整数0..100（0普通边，正数表示每实例允许通过的最大次数）。禁止bool冒充整数、重复边、悬空引用及额外字段。
- 恰好一个start、至少一个end；start无入边，end无出边；全部节点从start可达且能到达end。删除所有有正数max_traversals的边后必须无环，确保每个环都有有界返工；禁止以环上任意一个无关计数掩盖其他无界环。本模块只验证边界，不宣称执行端已经消费计数。
- condition节点config为`{condition:<条件>}`，必须分别有true/false两条出边。条件为`{field,op,value}`，exists可省value；declared_fields为唯一字段名列表（最多100），values按完整字符串键读取，不做eval/属性访问/任意路径执行。op只允许eq/ne/in/exists/gt/gte/lt/lte；严格JSON值、不接受NaN/Infinity；数值比较拒绝bool和异类，in右侧必须有界数组。缺字段除exists=false外均返回false，不能凭不存在字段满足ne。
- agent_task config保存agent_id正整数及input_refs字符串列表；这里只验证形状，授权/存在性在后续发布和实例启动核验，不进行数据库读取或派发。human_decision/delivery_review config为reviewer_roles（owner/admin/member非空唯一列表）。parallel config为空；join config为`{mode:'all_required'}`，至少一条required入边；create_child config为非空title与字符串description；start/end config为空。各type的config封闭，错误组合明确拒绝。
- 非condition普通节点仅always出边；human_decision/delivery_review允许approved/rejected，二者必须齐备；一个节点可有多条出边仅parallel或上述决策节点允许。对join可选入边，规范化保留required=false，不能升格成必需。结构校验不把失败节点当成功，不提前创建NodeAttempt或修改Issue状态工作流。

- [x] **Step 1:** 写SimpleTestCase行为测试；模块尚不存在时可建立只含明确NotImplementedError的最小Interface使测试到达行为断言，然后记录缺失行为。不得把ImportError当行为红灯。日志 `/tmp/workpal-parallel-c2a-red.log`。
- [x] **Step 2:** 实现图规范化/验证、稳定hash和封闭条件求值；不接图执行、Run、Registry或旧workflow定义格式。
- [x] **Step 3:** 测合法顺序/并行join/人审分支/有界返工，两个交叠环中的无界路径、悬空/不可达/无法结束、角色/config/值类型/大小边界、全部condition操作与缺字段、输入/输出突变隔离、节点边输入重排后的规范化hash，以及恶意字段值不执行。全部通过公开Interface，不测试私有算法副本。
- [x] **Step 4:** `.venv-workpal/bin/python services/workpal/manage.py test tests.test_graph_definition --noinput`及Django check退出0。保存 `/tmp/workpal-parallel-c2a-*.log`，不受兄弟未集成app影响。
- [x] **Step 5:** GRAPH.md记录schema、返回值和未完成接线。C2b发布/不可变图版本、C2c实例推进/可选汇合/返工计数与B派发仍待后续，不宣称C2完成。无Git操作。

## Task D1a: Environment and investigation records with scoped upload sources

**Files:** 新增 `services/workpal/workpal/investigation/`（含模块README、正常迁移；本任务唯一所有者），新增 `services/workpal/tests/settings_investigation_lane.py`、`test_environments.py`、`test_investigation_records.py`。不得改config、work/access/delivery或旧测试。

**Interface:** `environments.create(actor,project_id,name,timezone,source_refs=())->EnvironmentView`、`read(actor,environment_id)`、`list_environments(actor,project_id,cursor=0,limit=50)`、`grant(actor,environment_id,user_id,read,write,publish,revision)->EnvironmentView`；`sources.create_upload(actor,environment_id,name,allowed_services)->SourceView`、`read_source(actor,source_id)`；`service.start(actor,project_id,environment_id,service_id,problem,key)->InvestigationView`、`read(actor,investigation_id)`、`list_investigations(actor,project_id,environment_id=None,cursor=0,limit=50)`。通过本模块service配置Service记录并提供list/read，签名在模块README完整记录。

**Behavior:**
- Environment真实FK绑定workspace/project，保存name、IANA timezone、revision；SIT/UAT/PRD为默认名称集合，但不在读取时写DB或给所有成员默认权限。提供显式幂等ensure_defaults(actor,project_id,timezone)仅owner/admin配置，重复调用不重建或覆盖已配置记录；自定义名称同权。来源引用只追加。
- 每Environment是独立is_source权限根并继承project和显式sources，创建者需owner/admin且当前project write；事务内仅给创建人初始read/write/publish，其他成员默认无权。grant需owner/admin且当前Environment publish；目标须本workspace有效成员；read/write/publish组合遵守access语义，grant变更CAS与确认动作保护，不绕过上游来源授权。撤权立即影响后续Source/Investigation读取和缓存重放。
- Service属于具体Environment，Source保存明确允许service集合；upload是本任务唯一已支持adapter_type，仅声明上传文本/JSONL能力，不虚构已连接监控源。不接受credential/url/query/script等字段，不建立HTTP或Runtime网络路径。
- Investigation保存problem（1..8000字符）、project/environment/service真实FK、actor、revision、created_at及status=investigating；启动必须同时有目标Environment write和所有来源read，服务必须属于目标环境，指定Source不得跨环境复用扩大权限。默认查询预算10和默认窗口30分钟可保存为明确配置，但本任务不消耗预算、不产生EvidenceSnapshot或任何分析结论。
- Source/Investigation都register_object继承Environment与项目/Service；授权后分页，过滤403时保留503真实故障。读操作不写业务outbox。start通过Registry持久key，直接Interface也应保证同key同请求返回同对象，不同请求409，不出现并发重复调查。
- Registry薄动作至少environment.create/read/list/ensure_defaults/grant，environment_service.create/read/list，evidence_source.create_upload/read，investigation.start/read/list。完整严格schema，当前授权/来源result_refs，最小审计字段；原始problem不放outbox/audit输入摘要。配置保存不等于查询成功，sources只说明真实已实现能力。
- 私有settings继承config.settings，仅追加InvestigationConfig；不改默认settings，不扩展原项目create动作。UI/HTTP上传、实际证据解析脱敏、EvidenceSnapshot/Findings为D1b，未实现不能以占位响应冒充。

- [x] **Step 1:** 在真实Registry建立environment.create unknown_action红灯，保留 `/tmp/workpal-parallel-d1a-red.log`。
- [x] **Step 2:** 实现创建环境→配置Service及upload source→授权成员→启动并读取调查的持久闭环，带正常迁移、薄Registry和模块README。
- [x] **Step 3:** 覆盖默认/自定义环境与时区、授权成员正向对照、同项目不同环境不互通、跨workspace拒绝、source/service错配、撤Environment及上游来源后重放拒绝、过滤后分页、同key不同请求、输入边界和最小审计；真实双连接同key启动只产生一条调查；实际写后失败完整回滚、同key可重试。
- [x] **Step 4:** `.venv-workpal/bin/python services/workpal/manage.py test tests.test_environments tests.test_investigation_records --settings=tests.settings_investigation_lane --noinput`、同settings的迁移检查和check退出0。只跑本任务专项，日志 `/tmp/workpal-parallel-d1a-*.log`。
- [x] **Step 5:** 报告AppConfig、动作和真实支持范围。下一D1b复用A4 Artifact或新的有界上传Interface保存脱敏证据，验证2MiB/1000条/30秒/10次预算；本任务不宣称已经采集环境证据、确认根因或连接Jira。无Git操作。

## Integration and verification queue

### Current follow-up — 2026-11-20

**当前保护确认已关闭：** 用户于2026-11-20明确答复“是，有意修改，保留该改动”。仅接受src/studio.js的SHA256=678532eae3f54f592fc2f0581697b968d60fcf78f7b3a8b965175642cf338e7a（关闭移动菜单后重绘、恢复按钮焦点）这一精确差异，不授权后续原型修改。原85项基线、原脚本/tmp/workpal-studio-protected-20261120.js和精确差异/tmp/workpal-protected-studio-difference.patch全部保留。例外记录于2026-11-20-workpal-protection-exceptions.json；父代理重新核验85项仅两处已接受差异、unexpected=[]，/tmp/workpal-protection-confirmed-20261120.json，exit0。下方历史“全局待确认”记录保留过程事实，以本最新确认覆盖；当前没有需要用户再确认的事项。

本段为此前调度记录；当前调度见文件末尾“层级阅读验收及续租/配置收尾”。此前三项为B取消/改绑与续租竞争、A层级阅读R2、D Q1a配置审查。B领取已完成独立审查，父代理补齐候选verifier异常与正文/秘密检查，改测试fixture引用为模块引用避免单独发现重复；三模块20项退出0，/tmp/workpal-lease-claim-parent-final.log，Task1a功能验收通过。renew核心已实施，父代理24项复跑及强化撤权对照4项均通过（/tmp/workpal-lease-renew-parent-core.log、/tmp/workpal-lease-renew-parent-strengthened.log）；独立竞争/权限/故障矩阵未验收。默认verifier仍False，尚无HTTP或真实执行。D修订已解决Q1接线问题，仅Q1a来源/政策/配置准入，bind/预算/传输/证据完成尚未冻结。A基础阅读core父代理通过，/tmp/workpal-a54d2-reader-parent-core.log；剩余权限/迟到/只读矩阵未验收，改挂与创建子任务后续。B已修复损坏旧scope轮换缺陷，父代理37项通过，/tmp/workpal-lease-renew-parent-review.log，竞争及错误矩阵继续补齐。三路文件互斥。最新父代理专项：B42项exit0（/tmp/workpal-lease-renew-parent-final42.log），A R1三个命名场景PASS（/tmp/workpal-hierarchy-r1-parent.log），D修复优化模式校验和政策hash后14项exit0（/tmp/workpal-query-config-parent.log）；A R1验收，B/D仍待剩余矩阵。父代理本轮npm run check退出0，/tmp/workpal-hierarchy-renew-parent-npm.log；随后的85保护核验仅两个已确认精确例外，unexpected=[]，/tmp/workpal-hierarchy-renew-parent-protection.json。

C2b图存储阶段已完成，父代理原19+竞争/升级3共22项退出0，/tmp/workpal-c2b2-accepted-parent.log；C2c协调/节点Run准入仍后续冻结。D1b2上传持久化及HTTP功能验收通过，父代理B8+D16联合24项退出0，/tmp/workpal-evidence-claim-parent.log；尚无查询账本。最新完整发现仍为下文782，不把专项相加。

B1b Task1配对、身份、HTTP及绑定已功能验收。父代理读取RuntimeBinding/Direct/Registry及10项新测试，独立重跑绑定10+HTTP10+core13+B24共57项退出0，/tmp/workpal-b1b1b-binding-parent.log。绑定不能解除deferred；租约、Worker与真实执行均未实现，Task2/3合同须进一步冻结。

D Task2a/2b功能验收通过。父代理读完真实SourceGrant/审计/授权503/边界与跨调查source补测，补强所有分页只读全表不变量与内部分派Actor权限对照，七模块31项退出0，/tmp/workpal-d1b2b-access-parent.log。HTTP Task3已实施8项专项，父代理日志亦显示8项OK；完整真实撤权/流式边界/副作用矩阵进入独立审查，尚未连接真实查询或Jira。

C Task1图草稿/不可变版本功能验收通过：父代理复核R3真实Registry双连接竞争与历史0001数据库升级后，独立五模块24项退出0，/tmp/workpal-c2b1-accepted-parent.log。B初始化准入已独立复跑6项并验收，/tmp/workpal-agent-initialization-parent.log；Graph计划已冻结initialize作为Registry wrapper，不建第二套Intent。Task2a已实施，父代理原8项复跑退出0，/tmp/workpal-c2b2a-parent.log；独立审查补齐真实provider变更、混合来源和跨区矩阵，后续Task2b列表/并发另验收。shared schema冻结。

B租约候选已解决私有游标、可信能力验证、终态优先级与撤权审计依赖问题；父代理把审计状态改为现有completed，冻结runtime.claim/runtime.renew审计字段及Run/scan溢出界限。仅Task1a准入实施；Task1b/HTTP等前置验收，Task3初始化准入已验收。延期事件/日志默认拒绝不等于删除首版恢复与日志目标。

父代理本批根npm run check退出0，/tmp/workpal-bcd-wave-npm.log；完成后85项保护核验无新增差异，/tmp/workpal-bcd-wave-protection.json。该次studio.js来源当时待确认，现已按本节用户确认及精确hash关闭；不能用npm绿灯替代保护核验。

历史流程偏差保留：B核心原实施后补造的NotImplementedError红灯不追认为测试先行；已有正确行为的新补测首次即绿如实记录，不反向制造红灯。具体合同和证据见[Runtime计划](2026-11-20-workpal-runtime-protocol.md)、[证据计划](2026-11-20-workpal-evidence-persistence.md)、[图计划](2026-11-20-workpal-graph-persistence.md)。

此前A5-4d1依赖界面、D1b2a策略版本、D1b1 normalization13、B1a24、C2a20、D1a19及I1已验收。本批父代理冻结122模块联合运行，782项退出0，94.547秒；测试ID核验782个唯一ID，无重复计数。新全量取代历史I1的680项记录，不把专项相加。模块清单/tmp/workpal-bcd-wave-modules.txt、全量日志/tmp/workpal-bcd-wave-full.log、去重证据/tmp/workpal-bcd-wave-test-ids.json。默认迁移dryrun无变化，Django check无问题；全部检查仍不替代D/C尚缺的合同矩阵，也不消除保护门禁或宣称首版完成。

下方是历史记录；当前状态以本节及专项计划最新验收节为准。

### Accepted Wave 3 and next parallel batch — 2026-11-20

本节保留前一批验收记录；最新调度见上方 Current follow-up。

- **B1a限定Module验收通过**：原18+6=24项独立测试。父代理读取五项新增测试，确认双用户双连接准入、来源权限矩阵、取消CAS竞争、实际audit/outbox写后回滚和跨区只读行为，实际重跑24项退出0，`/tmp/workpal-b1a-accepted-parent.log`。没有继承测试重复计数；旧快照保持不可变。尚未默认注册，B1b配对/租约/事件/Worker及真实执行未实现。
- **C2a纯计算Module验收通过**：原17+3=20项，父代理读取1000/1001边、交叠环及九类config变异测试并实际重跑，`/tmp/workpal-c2a-accepted-parent.log`退出0。仅图编译与安全条件求值，不含发布/实例/返工消费/派发。
- **D1a限定Module已验收**：父代理19项退出0记录沿用`/tmp/workpal-d1a-accepted-parent.log`，尚未默认注册；没有上传证据或环境查询能力。
- **A5-4c2功能验收通过**：core、six review及三个独立权限场景已实测；父代理重跑权限3组与apps Node23退出0，见`/tmp/workpal-a54c2-accepted-{permissions,node}.log`。子代理旧人员/创建回归、web2、根npm及85项保护通过；父代理目视390截图，Blocked owner无重复Assignee标题。首次登录Username超时原因未明，已保留失败诊断，不能记成修复。独立要求仅撤write仍允许转换是既有read权限合同的正向对照；Issue write及要求read仍须当前授权。

下一三个任务按文件互斥并行，均由新GPT 6.1 Sol实施，父代理只审查、运行现有验证和维护计划：

1. [默认配置集成](2026-11-20-workpal-foundation-lanes-integration.md)：独占settings、私有lane兼容配置、公共服务README及新集成测试，接入已验收B/D，冻结已验收测试清单跑联合回归。不改UI或在途normalization。
2. [Issue依赖界面](2026-11-20-workpal-issue-dependencies-ui.md)：独占新UI、Issues薄接线、web静态白名单、apps文档/脚本。复用已验收后端，无新业务规则。
3. [上传内容解析与脱敏](2026-11-20-workpal-evidence-normalization.md)：纯计算Module和独立SimpleTestCase，无ORM/app/Registry修改。此任务不包含持久Evidence、上传HTTP、预算账本或结论生成。

集成回归明确排除同时开发的`tests.test_evidence_normalization`；不能把它的中途红灯当已验收模块回归，也不能因此宣布仓库所有当前文件都已集成通过。UI完成后再跑该UI的真实浏览器路径。下一就绪队列仍有B1b、C2b、D1b2及A5协作/交付UI，不因本批验收把一级B1/C2/D1/A5标完成。

### Current gate after Wave 3 — 2026-11-20

D1a模块验收通过（私有配置范围，尚未默认注册）。新6项确实通过真实密码登录/CSRF的HTTP、来源权限撤销、确认自撤、过滤分页/503、实际audit写后全表回滚、双连接grant竞争。父代理读完实现和测试并实际重跑19项退出0，`/tmp/workpal-d1a-accepted-parent.log`；子代理迁移/check/保护证据为`/tmp/workpal-parallel-d1a-final-*.log`。默认settings注册和联合回归交独占集成任务，D1b证据与D1整体尚未完成。

B1a Direct准入新资源缺口已有真实红绿修复；上一报告21项包含继承AdmissionReview重复运行的2项。父代理已作最小测试fixture修正，保留原新资源断言但不再继承含test方法的类。正确基线为原18+新增1，剩余五项由新的验证任务完成，不算B1a已验收。

A5-4c2六项core review已有子代理实测绿灯。父代理复跑在首个登录前置步骤等待Username超时（`/tmp/workpal-a54c2-parent-six.log`），没有到业务断言；目前原因未确认，不当作已证明功能失败，也不能直接忽略。需要新子Agent保留诊断并复验。目视截图另发现Blocked owner下面显示复用picker的Assignee标题；父代理仅作最小展示修正：people picker新增可选heading（默认Assignee），状态表单已有legend时省略内部heading，避免误认实际assignee被改变。此变更须随人员相关QA一起回归。

下一三个并行任务：B仅剩五个验证，C仅剩三个边界回归，A登录前置诊断与三个权限场景。B/C/A通过后再由独占集成Agent注册已验收App、跑全量和所有新UI回归；不在多个子Agent修改期间同时改公共settings。

**B remaining-five:** 只扩展tests/test_execution_final.py加入Wave3第1/2/4/5/6项，现有第3项保持；不继承含test方法的类，保留全部旧18项。若发现真实实现缺陷，在agents/execution内部最小修复并记录；全部五项首次即绿也正常完成，不要求制造红灯。以明确独立测试清单和正确去重计数交付。

**C final-three:** 新增tests/test_graph_definition_final.py，包含①合法1000边图与1001边拒绝（都≤200节点且不存在悬空/重复/不可达等其他拒绝原因）；②两个共享节点的环，只有一个环受max_traversals约束时拒绝，两个环都受约束时通过，0/100/101规则正确；③所有node type config的缺字段/额外字段/错误类型、角色/agent bool/condition错误，使用合法图正向对照后单独变异，通过公开compile_graph断言DomainError400。可用subTest表达矩阵，不以子case数量充当独立测试数。保留17项；只允许graph内部必要修复/GRAPH.md，不改旧测试/ORM。专项20项预期（若确有额外独立case如实报告）、check/hash，日志/tmp/workpal-parallel-c2a-final-*.log。

**A permission-final:** 新增qa.issue-transition.permissions.mjs，允许该文件及issue-transition.js必要修复；browser-fixture.mjs仅允许失败诊断增强（保留原错误、输出本fixture的server末尾日志及失败页面状态，不增加自动重试、不隐藏error、不放宽权限/SQL断言）。先诊断首个loadSession/Username失败：捕获实际页面文本、console/pageerror及失败HTTP状态，必要时复现；不得凭一次重跑绿断言找到原因。三个权限场景：①Issue来源与独立要求来源在dialog打开后撤read/只撤write，实际拒绝且无业务变更，403清空dialog/旧详情；②候选Blocked owner选中后被移除membership/停用/撤掉其Issue或要求read，失败无transition/notification/outbox且无假成功；③write已成功但响应丢失后撤发起人来源权限，再用原key重试被拒绝、旧受限结果不重现，已完成的业务事实仍恰好一次。各有正向授权对照，真实服务及SQL，不合成success。完成后重跑core+six review+新3、create/assignee各core+review（共享picker heading轻微改动）、Node、web、根npm及hash，重新截图并目视；日志/tmp/workpal-a54c2-permissions-*.log。不要把“未找到启动偶发原因”伪称已修复，可报告仍未复现及实际检查证据。

### Wave 3 — finish observable acceptance paths

Wave 2真实结果：B修复awaiting_input活动集合和Registry资源write重放，18项通过；D补权限解析/输入等但只有13项通过，所谓HTTP文件尚无HTTP请求；A状态编辑仅普通todo→in_progress→in_review路径通过。以上不得标为完整验收。本波不新增业务范围，以每路六个可观察场景完成遗留；首次即绿的补测如实记绿，不为满足TDD回退代码或造红灯。

**B1a-final（六个独立行为测试）**：新增tests/test_execution_final.py，沿用execution_lane，允许仅agents/execution内部必要修复及模块README，不改已有18项或其他模块。
1. 两个不同有效成员各自通过Registry同时start同Issue+Agent，真实两SQLite连接；只一Run、每人一Intent与一个成功业务audit/outbox/cache；各自重放计数不增加。
2. Agent来源和独立当前要求来源分别撤read、或只撤write保留read；Direct Interface与Registry的旧key/新keystart、read、cancel符合能力。先建立完整正向对照，再撤权；仅撤write时read仍应可用。
3. 首Run后新增/限制ProjectResource，Direct start与Registry在同一准入合同上不能分歧，不静默省略当前不可见/不可写资源；旧Run快照不变。注意现admission_refs只由Registry resolver调用，需用公开行为确认Direct重放/复用路径是否一致。
4. 两连接同revision不同key取消，一成功一revision_conflict，无重复cancel业务事件；cancel_requested/recovery_required不可生成替代Run，awaiting_input等终态不占活动唯一性。
5. 在真实Registry.record已经调用原函数写AuditEvent/Outbox之后抛DomainError503；Run/Intent/RegisteredObject/SourceLink/IdempotencyResult/AuditEvent/Outbox全表快照回滚，原key重试成功且精确一次。
6. 用同一用户在两个workspace的有效成员身份，跨区Run/Agent/Issue拒绝且不产生事实；读取只增加正确read audit、无outbox，不更改业务行。
运行原18+上述新测试、正常迁移dryrun/check、85项保护核对，日志/tmp/workpal-parallel-b1a-final-*.log。通过后交父代理验收，可进入B1b计划，不在本任务写lease/Worker。

**D1a-final（六个独立行为测试）**：新增tests/test_investigation_final.py，沿用investigation_lane，允许investigation内部必要修复/README；保留原13项（包括仅检查contract的旧HTTP命名测试，不把它计为HTTP证据）。
1. Client(enforce_csrf_checks=True)真实用户名密码登录，轮换CSRF，通过通用动作HTTP建立带非空source_refs的Environment/Service/upload source/Investigation，读取和environment_id过滤正确；含Host/CSRF/匿名拒绝的正反对照。父代理静态检查发现actions.handler在source_refs转换后又局部import ObjectRef，非空source_refs可能触发未绑定局部变量，必须通过真实HTTP证明后修复。
2. 对Environment及上游来源分别只撤write/publish保留read：旧key缓存和新key写入拒绝，read仍允许；grant waiting_confirmation后撤publish，消费拒绝且token未消费，无授权副作用。审计/confirmation绑定真实完整输入来源。
3. 自撤授权确认后成功空结果，真实grant/revision变化，后续读取和旧key重放拒绝；停用目标成员不能授权。另一人已授权环境保持可用，不扩大成全工作区撤权。
4. 同项目两环境/两workspace和source-service错配拒绝，授权后分页无私有行且503不能吞成空页；读无业务outbox、problem不出现在audit/outbox。Start只要求上传source read、目标环境write；不要把所有refs统一write导致独立只读证据源也无法启动调查，Direct与Registry保持同一合同。
5. 真实Registry.record调用原函数写audit/outbox后503：分别覆盖create与grant/调查之一，业务/访问关系/confirmation消费/cache/audit/outbox完整回滚，同key恢复后精确一次。
6. 真实两连接同环境revision竞争grant（各有单独已准备确认），一成功一409；另一用户不被错误授权，审计/outbox只一次。复用既有调查同key竞争测试作为另一并发证据。
运行原13+新6、迁移/check和85项保护核对；日志/tmp/workpal-parallel-d1a-final-*.log。缺HTTP或回滚任何一项不能报本轮完成；不新增Evidence/联网能力。

**A5-4c2-core-review（六个真实浏览器场景）**：新增apps/workpal-web/scripts/qa.issue-transition.review.mjs；允许issue-transition.js、Issues薄接线、必要CSS、apps README/package修复；保留原core和旧QA，不改业务后端。按状态操作专项计划完成：①member Blocked→Todo闭环及owner/assignee区分、无效输入无POST、通知/历史和独立context持久化；②正常发布custom key/label+manual策略的人类Done与角色拒绝；③默认代码Done真实completion_not_ready及未完成依赖拒绝；④两种409（目标失效、目标已达到）回读不自动写；⑤真实写后丢响应→原payload/key/revision重试→实际最新状态回读，精确SQL历史/audit/outbox/cache唯一性；⑥在途关闭重开、旧回读及切Issue/工作区响应隔离。每场景通过真实withBrowser库与HTTP，不合成成功响应；可复用已有QA helpers，不继承/复制旧断言削弱证据。
运行新六场景、原core、status-history/Issues/Assignee各core+review、Node、web2、迁移/check及保护核对，日志/tmp/workpal-a54c2-review-*.log。重拍1440/390有意义的Blocked或Done表单截图并目视检查。完成后还需父代理复核，不宣称A5整体完成。

### Wave 2 — B1a review, D1a completion, A5-4c2 UI

B1a首交16项专项、D1a首交9项专项通过但未集成；C2a独立审查后17项通过，已修复递归比较/Unicode/重复决策分支，尚欠边数1000/1001、两个交叠环和非法config边界的完整持久回归，C2a保留待验收，C2b不启动。下一波用3个空位并行做下述B/D独立审查及[A5状态操作界面](2026-11-20-workpal-issue-transition-ui.md)，避免A界面长期等待。新全量基线不能仍写成614+简单相加，待统一配置后实际执行。

**B1a-review**：允许agents/、execution/内部最小修复与正常新迁移、新增tests/test_execution_admission_review.py；不改原16项、公共设置或其他Module。父代理发现ACTIVE=STATES[:8]将awaiting_input包含在活动集合，违反其“结束本次执行、Resume新尝试”合同；新增真实行为红灯后修正状态集合及唯一约束迁移。独立审查必须验证：cancel_requested/recovery_required仍阻止重复派发，awaiting_input/completed/failed/cancelled不占活动唯一性；两个用户同时manual start只产生一个Run、两个用户各自intent；真实Registry的同key和新key在资源来源只撤write保留read、Agent来源撤权、独立要求撤权后均符合当前准入能力。已有resolve_refs在Registry缓存返回前只解析Issue/要求/Agent，需验证原Run完整来源write不能在重放时绕过；如缺失，在execution所属Interface中收敛，勿改公共Registry。测试跨workspace、输入边界、CAS取消竞争、所有副作用回滚（含实际audit/outbox写后故障）、read无业务事件。资源ID只读ORM枚举暂保留明确记录，不另建全局查询层或静默忽略不可见资源。迁移/check及原16+新增专项都用tests.settings_execution_lane，日志/tmp/workpal-parallel-b1a-review-*.log；提交实测结果后父代理验收，仍不接claim/lease/Worker。

**D1a-review**：允许investigation/内部修复及正常迁移、新增tests/test_environment_access_review.py、test_investigation_http_review.py，不改旧9项/公共Registry/配置或兄弟代码。补齐environment.create的source_refs严格StructuredField（复用现有ObjectRef JSON格式并转换），以及investigation.list可选environment_id。所有Direct Interface ID/revision/cursor做严格整数与SQLite范围检查，拒绝bool/string/0/负数/溢出；grant目标须本workspace有效且user.is_active成员；ensure_defaults即使记录已存在也验证timezone。

D的resolve_refs当前全部空且capability默认read，必须按动作解析真实输入对象、创建上游对象和来源；grant用publish，其余写用write，read用read，在确认准备/消费和缓存重放之前校验当前权限，并保留输入scope供审计/确认绑定。缓存读取不代替当前write/publish权限。对environment.grant自撤，允许合法自撤read/write/publish在事务中生效，不能被post-action读检查反向回滚；此动作可以返回空对象并无输出refs，其schema应明确支持该情况。输入scope仍入审计，后续重放因当前权限消失被拒绝，不泄露历史受限内容。

D测试矩阵必须跨真实Registry及会话HTTP（私有settings已有通用路由）：读写正向对照、跨workspace、同项目两环境、来源追加继承、上游/环境撤read与只撤write/publish的重放/确认拒绝、被停用目标、严格输入、授权过滤后分页和503传递、source/service错配、秘密problem不进audit/outbox。确认scope核对完整来源；读事件有正确scope且无业务outbox；创建/授权/调查在实际audit写后失败全表回滚、同key重试精确一次；同key和grant同revision真实两连接竞争。父代理所述均需先复现，不将未经测试的推断写成已证实。命令用tests.settings_investigation_lane运行旧9+两个新测试、迁移/check，日志/tmp/workpal-parallel-d1a-review-*.log；保持未采集证据/未联网/未注册默认settings的真实范围。

### C2a supervision and C2a-review contract — 2026-11-20

首个实施已交付graph.py/graph_contracts.py/GRAPH.md及9项专项。父代理重跑9项通过，但公开Interface探测确认两处缺陷：eq({flag:true},{flag:1})和eq([false],[0])错误为true；declared_fields包含孤立Unicode surrogate时compile_graph抛UnicodeEncodeError，未按合同返回DomainError。C2a保持待验收，不能进入版本持久化兼容承诺。

明确尚未发布的v1条件合同：eq/ne/in采用递归JSON类型比较；boolean与number永不相等，JSON number的int/float表示按数值比较（1与1.0相等），数组保持顺序，对象不依赖键顺序，null与缺字段不同。缺字段规则仍是除exists=false外一律false。规范化hash保持规定的canonical JSON表示，不承诺不同数值文本表示具有相同hash。条件分支节点明确包括condition；human_decision/delivery_review和condition均恰好两条出边、各标签一次；需要扇出用parallel。in上限固定100，当前既有实现的深度上限32予以保留。

非法Unicode（键或值）、非JSON容器、递归容器、过深/非有限值及编码/序列化失败均返回脱敏DomainError，不能泄露原输入或抛未处理500。不为修补引入eval、任意对象比较hook或新增依赖。

新上下文审查Agent拥有graph.py、graph_contracts.py、GRAPH.md及新增tests/test_graph_definition_review.py；保留原9项，不修改旧断言。先对上述公开Interface行为记录失败，再实施合同修复，并独立补齐原C2a的封闭schema、全部节点config/边分支、边界、断路与交叠环、有界自环、条件类型/缺字段、突变隔离和重排hash矩阵。不能用私有方法测试替代Interface行为，不能把fixture失败算产品红灯。命令为 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_graph_definition tests.test_graph_definition_review --noinput`、Django check，日志 `/tmp/workpal-parallel-c2a-review-*.log`；核验85项保护基线。无需运行兄弟未集成模块全量测试，无AppConfig/公共配置修改、Git写操作或外部调用。专项通过后由主代理复核新差异再决定验收。

主代理逐项读差异、复核子Agent日志并运行其现有检查。需要新增测试或修复时交新子Agent，不由主代理扩写。优先对B当前授权/取消/并发、C有界环与条件、D独立环境授权做新上下文审查。发现合同矛盾先修具体计划/Interface，不同时让两方猜接线。

一个实施槽空出后可安排独占集成Agent：合并已经审查的AppConfig到默认settings，生成联合测试settings用于全部新旧测试，确认迁移互不依赖未验收模块，跑完整服务/Node/根npm并更新公共README。A5下一UI任务也使用空位，拥有UI/静态白名单文件，不与后台模块冲突。迁移/app未集成前不能把默认部署标为已支持该功能。

完成比例仍按首版20个一级任务及其验收记录报告；第一波启动增加“进行中”，不增加“已完成”。真实Copilot、Linux隔离、GitHub/ADO/Jira和SIT/UAT/PRD需后续指定测试环境及安全凭据，未运行项明确not_run。

A层级R2最新：父代理修正迟到测试fixture后复现并修复局部旧403全局清屏，当前回调Interface及测试见hierarchy计划末尾。App Node26与9个review分支通过；尚待filter/分页乱序、键盘导航与完整回归，A Task1未整体验收。B真实竞争与D配置审查仍由各自子Agent执行，未轮询或重复派发。


## 层级阅读验收及续租/配置收尾 — 2026-11-20

A层级Task1已验收：父代理独立复跑原11场景，并追加真实旧导航403清新详情红灯后修复，最终12命名场景全绿；Issues review、Node26通过。代码仅将现有client current回调传入详情issue/project读取，保持当前真实403仍清屏。图片1440/390父代理目视。Task2a改挂/解除现在准入，详见hierarchy计划末尾；创建子任务及完整写权限/乱序矩阵后续。

B续租竞争6项已监督复核并强化首次提交集合断言，48项通过。父代理再复现并修正scope容器损坏被接受，新增一独立方法，49项通过；见/tmp/workpal-lease-renew-parent49.log。Task1b仍待新资源/历史及跨区scope、完整输出秘密两组，不把默认可信验证False说成可真实派发。D配置16项独立复跑通过，内容篡改已改为合法payload验证confirmation绑定；仍缺角色/他人确认与独立上游权限、合法边界和安全投影，Q1a未验收。对应验收计划已冻结，Q1b和查询网络未准入。

本批根npm、迁移漂移/system check已执行；最终命令日志以/tmp/workpal-supervision-final-npm.log、/tmp/workpal-supervision-renew-query-{migrations,check}.log、protection.json为准。85项仅两精确已授权差异，unexpected=[]，不再要求用户确认。完整后端最新联合冻结事实仍是122模块782项，后续专项不相加成全量数字。

下一并行三项：A Task2a父任务编辑核心（apps及仅资产接线）；B续租scope/output独立收尾（execution与新测试）；D Q1a角色、确认和安全投影独立收尾（investigation与新测试）。各自文件互斥，由GPT6.1 Sol执行，父代理复核。尚无Runtime/环境真实查询/Jira集成验收，首版未完成。


A Task2a实施回报未完成：仅Module/入口/资产草稿，无浏览器行为证据。父代理修正两处小型请求/刷新代际接线，App26及web2基础检查通过，未验收写功能。新子任务先完成Task2a1真实改挂/解除持久闭环；其余候选及故障矩阵继续待办，首版及A5未完成。B scope/output、D Q1a权限任务继续运行，不重复派发或轮询。


## 三线新的准入检查点 — 2026-11-20

B Task1b续租核心验收通过，父代理53项独立复跑；Q1a查询来源/政策/确认配置管理验收通过，父代理21项独立复跑。两组只证明本地合同，默认verifier=False、connected=False不变。A Task2a1改挂解除真实双context/SQL闭环经父代理复跑通过，Task2a2候选键盘与Task2a3冲突/丢响应仍待。对应日志/tmp/workpal-lease-renew-parent53.log、/tmp/workpal-query-config-parent21.log、/tmp/workpal-parent-vertical-parent.log，均exit0。

下一并行：B租约HTTP实现（独占config/urls.py仅两路由；不动核心）；D Q1b请求绑定精确设计（仅query-collection计划，不实施网络或预算）；A父任务候选/键盘组（仅UI及新review）。根npm/tmp/workpal-abc-next-parent-npm.log exit0，迁移/check与85精确保护/tmp/workpal-bd-accepted-*通过。首版、B Runtime、D查询与A5整体均未完成，不把专项相加为全量。最新整体后端冻结仍为782独立项。


B HTTP首轮只完成传输草稿与一个路由测试，未验收。父代理实际HTTP红测修复storage_busy错误映射500→503，保留固定脱敏消息。下一新任务只完成真实pair→claim→renew→撤权停止、身份隔离与审计回滚三组闭环，其他六组剩余要求保留；默认可信能力False不变。A候选/键盘和D Q1b设计仍各自进行，不重复派发。

## 候选阅读与租约HTTP闭环复核 — 2026-11-20

A父候选两组QA经父代理代码审查、独立复跑及390截图目视通过，Task2a2功能验收；日志/tmp/workpal-parent-candidates-parent-review.log。子Agent报告的焦点红灯路径不清，不补认准确日志证据。Node26通过，/tmp/workpal-parent-candidates-parent-node.log。改挂/解除纵向core此前通过，完整Task2仍待冲突、未知结果、权限和循环。

B新真实HTTP flow三方法经父代理审查并与旧HTTP9共12项独立复跑通过，/tmp/workpal-lease-http-parent-flow.log。旧53核心仍是此前独立结果，不合并为本次全量。flow证明配对/领取/轮换/撤权停止、session分离、审计写后回滚；其删除已读response变量并非真实未接收新token的证据，下一边界组补齐。HTTP Task2仍未整体验收，默认可信verifier=False保留。

D Q1b计划已复核：纠正默认30分钟被误写为显式上限、允许GMT/CET等命名时区、保持opaque cursor/text字面值。新纯query_requests Module避开旧query_contracts的ORM导入。仅Q1b.1冻结实施，授权绑定Q1b.2继续待审，Q2预算/网络/Q3证据未准入。

下一三个GPT6.1 Sol子任务：A父任务Task2a3两组冲突/丢响应闭环（issue-parent与新recovery QA）；B HTTP Task2b严格传输/时间/秘密（新边界测试、实际缺陷仅runtime_http）；D Q1b.1纯请求解析（两个新文件）。文件互斥，父代理监工及验收，不把未完成回报标完成。根npm本批/tmp/workpal-three-lanes-parent-npm.log exit0；85保护/tmp/workpal-three-lanes-parent-protection.json精确两例外、unexpected=[]。无新用户确认依赖，无真实Runtime或环境连接。后端整体冻结仍122模块782项，不与专项相加。
