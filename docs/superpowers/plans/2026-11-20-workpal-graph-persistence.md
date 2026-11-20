# Workpal Graph Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 持久化可授权的不可变图版本，并独立保存 Issue 图实例的初始事实快照，不启动执行。

**Architecture:** 新建 GraphDraft / GraphVersion / GraphInstance，继续放在 workflows Module；现有 WorkflowDraft / WorkflowVersion 专用于 Issue 状态及完成策略，所有旧 Interface 保持原义。把规范化、授权、来源继承、CAS 和幂等收敛到图持久化 Interface，Registry 只是 adapter。两个任务分别验收，Task 2 依赖 Task 1 和下述 Agent 交接门禁。

**Tech Stack:** Python / Django / SQLite / 标准库 SHA256；无新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-20-workpal-software-development-design.md`（303–311 图工作流）；`docs/superpowers/plans/2026-11-20-workpal-phase-c-collaboration.md` Task C2；`docs/superpowers/plans/2026-11-20-workpal-parallel-delivery.md` C2a；`services/workpal/workpal/workflows/GRAPH.md`。

## Global Constraints

- 父代理已复核并授权Task1独立实施；Task2保留B准入及下述精确接线复核门禁。不得Git写操作、worktree、安装、npm exec/npx、外网、真实模型或Runtime。
- 不再次委派；header 的技能执行建议不覆盖用户限定的 GPT 6.1 Sol 自行实施、父代理监工方式。
- 保留旧原型、旧测试、旧计划、公共 README 和 agents 目录；保护 `/tmp/workpal-supervision-baseline-20261120.json` 的85项，仅允许既有 .gitignore 差异。
- Python 固定 `.venv-workpal/bin/python`；Node 固定 `/Users/patrick/.nvm/versions/node/v22.22.0/bin/node`。专项测试不做全量发现，不调用 npm 检查旧原型。
- C2a 已验收20项；其纯计算 Interface 不改。图结构通过不等于授权通过或可执行。默认settings已注册workflows/agents，不再建立lane settings。

## Review Focus

1. 来源撤权后旧 key、读缓存和历史快照均不能泄漏正文：两任务各测真实 Registry 重放。
2. input_refs 字符串歧义、未知对象和跨 workspace：Task 1 固定解析及拒绝矩阵。
3. SQLite 双连接同版本发布和同 key 创建：两任务验证唯一事实及可重试忙错误。
4. audit/outbox 实际写入后异常：两任务验证业务、来源、幂等、审计全部回滚。
5. 要求/Agent/项目绑定升级后旧实例不变：Task 2 断言完整历史 JSON/hash，且 Issue 状态历史不变。

---

## 决策与兼容

选择独立图模型而非扩展旧 version.definition：旧 definition 的 states/transitions/review_policy 被 project.snapshot_workflow、Issue 创建、transitions 直接读取；替换为 nodes/edges 会破坏 A3。代价是独立动作命名与显式图版本选择，收益是不做有歧义的类型判别或数据转换。正常增量迁移只建新表，旧数据零回填，旧项目 workflow_version_id、Issue.workflow_snapshot 和要求历史逐字保留。无图配置默认是“没有图实例”，不能偷偷生成图或改变旧默认流程。

名称 GraphVersion 是物理隔离选择，承载设计文档所称不可变执行图；不重命名旧 WorkflowVersion。此批不接项目图绑定、AutomationRun、NodeAttempt、advance/control、Run、派发、租约或 Worker。AutomationRun 在此无可消费的已验收主体 Interface，subject 非 issue 返回 unsupported_subject/400，不能虚构主体。

## 公共 DTO 与授权合同

以下均为本计划新增 Interface，不冒充现有函数。新 `persistence_contracts.py` 定义 TypedDict：GraphDraftSummary `{id,name,revision,current_version_id}`；GraphDraftView 在Summary之上增加definition；current_version_id未发布为0。GraphVersionView `{id,draft_id,number,name,graph:GraphSnapshot,published_by,published_at,resolved_inputs:list[NodeInputs]}`；NodeInputs `{node_id,agent_id,input_refs:list[{kind,id}]}`。GraphInstanceView `{id,version_id,subject:{type,id},state:'initialized',snapshot:InstanceSnapshot,sha256,created_at}`；InstanceSnapshot `{schema_version:1,graph_version:GraphVersionView,issue:dict,requirements:dict,agents:list[dict],source_refs:list[{kind,id}],created_by:int}`。Issue/requirements/Agent dict 是现有公开 read 返回值的深复制，不新增猜测字段。时间只存创建事实；无运行时间、输出、节点成功或 ready 标记。

`input_refs` 冻结为 `kind:id`，只在首个冒号切分；kind 匹配 `[a-z][a-z0-9_]{0,63}`，id 为非空 UTF-8 字符串、禁止冒号，总长最多256；每节点最多50项且无重复。不把字符串当路径、URL、命令或动态变量。只允许已存在 available 的 RegisteredObject，经 access.resolve、derive_scope、authorize 验证同 workspace；不引入猜测的全局业务对象读取函数。语法不合法 invalid_input/400；未知、不可用、跨区或撤权统一 permission_denied/403。图 compiler 接受的宽字符串形状不变，发布持久化层加严。保留字符串顺序，resolved_inputs 为额外不可变解析快照，不能改写 C2a graph sha256。

写入均要求当前owner/admin，普通成员可读当前授权内容。创建先compile_graph，再通过agents.service.read及access授权核对所有Agent/input为当前read可用，登记草稿继承它们。更新在事务内检查当前草稿write与新Agent/input write，保留旧来源并追加新来源；发布检查草稿及定义中Agent/input的publish。对象的能力包含其全部上游根，不能一边继承输入来源、一边承诺发布只需输入read。只拥有read的输入可用于草稿创建和历史读取，但不能据此批准发布；测试须明确read允许而publish拒绝的对照。发布是内部不可变配置记录，不替代外发Publication许可，也不授予Agent执行权。Agent对象存在性/DTO经agents.service.read，所需额外能力经access.authorize核验，不读取agents ORM。版本继承草稿、全部Agent/input；更新来源只追加，旧版本访问可随上游收窄。任何来源环（包括引用自身或已有下游）拒绝并完整回滚，不删除历史来源来消环。

实例新建要求当前主体 write、精确当前要求 read、图版本 read、所有 Agent 与输入 read；Agent 可执行资格不能由 read 推断。交接 B：需要一个无执行副作用、可在同一事务调用的当前 Agent 准入 Interface，返回明确可用于图任务的授权/配置快照或拒绝；现有 agents.service.read 仅配置读取，execution.start 会建 Run，二者均不能充当该准入证明。Task 2 在 B 冻结具体函数/DTO/失败码并验收前不得接通创建动作；不得编辑 agents 或调用 start 绕过。无 Runtime 不阻止保存已获准的初始事实，但只能 state=initialized，不声称 queued/running。每次未来真正派发必须重新授权，不沿用旧快照当许可证。

## Task 1: 独立图草稿与不可变发布

**Files:** Create `services/workpal/workpal/workflows/persistence_contracts.py`, `graph_models.py`, `persistence.py`, `graph_actions.py`, `migrations/0002_graph_persistence.py`, `services/workpal/tests/test_graph_persistence.py`；Modify `workflows/models.py`（仅导入新模型）、`workflows/apps.py`（追加 graph_actions.register_actions）。迁移如被占号须先协调，不覆盖。

**Interfaces:** `persistence.create(actor,name,definition)->GraphDraftView`; `update(actor,draft_id,revision,name,definition)->GraphDraftView`; `publish(actor,draft_id,revision)->GraphVersionView`; `read(actor,draft_id)->GraphDraftView`; `read_version(actor,version_id)->GraphVersionView`; `list_drafts(actor,cursor=0,limit=50)->{items:list[GraphDraftSummary],next_cursor:int}`。Actor/ObjectRef/GraphSnapshot复用现有类型。仅Registry写入口要求并持久化key，使用已有IdempotencyResult；Direct是同事务业务Interface，不另建GraphIntent，也不伪称Direct具备key重放。当前handler仅收到actor/payload/revision，不能取得外层key；本任务不改Registry或增加隐式上下文传key。所有同key测试经真实execute；Direct测试覆盖CAS/授权/事务。

- [ ] 写新增失败测试：`test_legacy_workflow_unchanged`, `test_reference_resolution_matrix`, `test_publish_current_agent_and_input_access`, `test_draft_sources_accumulate`, `test_hash_and_detached_views`, `test_cas_and_key_conflict`, `test_authorized_pagination`, `test_publish_replay_revocation`, `test_two_connection_publish`, `test_audit_write_failure_rollback`。分别断言旧快照原样、上述语法矩阵、真实来源 grant 拒绝、删除引用不去来源、重排 graph hash 相等且 name 不影响 graph hash、stale revision 409、同 key 异请求409、分页过滤403而503不吞、撤 publish 拒绝旧发布 key、同 revision 两连接只一版本、失败后所有行数回到基线且同 key 可重试。
- [ ] 运行下述专项命令，记录真正产品断言红灯，不把导入失败算红灯。
- [ ] 实现上述 Interface。GraphDraft存workspace FK、name Char200、definition JSON、revision PositiveBigInteger(default1)、current_version nullable FK GraphVersion(PROTECT)。GraphVersion存workspace FK、draft FK(PROTECT)、number PositiveBigInteger、name Char200、graph JSON（完整GraphSnapshot）、resolved_inputs JSON、published_by用户FK(PROTECT)、published_at DateTime，唯一draft+number。正常BigAutoField；workspace/user FK均PROTECT。name非空白合法Unicode，最多200字符；所有input_refs先按上述语法和上限核验。普通派生引用kind固定workflow_graph和workflow_graph_version，均不设is_source。CAS 严格正 int 且小于 MAX_SQLITE_INTEGER；失败 revision_conflict/409，所有 ID 拒绝 bool/string/溢出。创建/更新均编译并保存规范化definition，当前授权、CAS、来源更新在同一atomic_write内；publish在该事务中重新校验当前定义、CAS revision+1、插入版本并更新current_version指针，number为同draft当前max+1。版本名称和graph不随后续draft更新；Direct不额外record，Registry负责一次audit/outbox/cache。内容 hash 使用 C2a compile_graph 返回值，name 与授权快照不混入它。返回值深复制。
- [ ] 注册 `workflow_graph.create/read/list/update/publish/version.read`，闭合 forms/schema；publish/update revision_required，所有写 key 必填，角色与 Direct 一致。list cursor=0、limit=50，最大200，严格整数，授权后按 pk 分页、末页0，无 total。result_refs 从保存版本解析不可变引用并验证 workspace/归属；resolve_refs在缓存前核验当前角色、草稿及相关Agent/input所需能力（create/read/list为read，update为write，publish为publish；version.read为read）。update检查payload新定义和当前草稿的累积来源；publish解析当前草稿，并由result_refs另外核验保存结果的精确版本/归属。旧key不做CAS、不再发布，但必须当前授权，保存scope及结果仍复查read；撤publish而保留read后历史读取允许、publish重放拒绝。不得只在handler做角色/来源门禁。audit_fields仅draft_id/version_id及分页，create为空；不得把name、definition、条件值或input正文写入审计。所有读mutating=False；update/publish不增加额外confirmation_required。
- [ ] 绿灯验收：`.venv-workpal/bin/python services/workpal/manage.py test tests.test_graph_persistence --noinput`；预期全部通过，报告实际数量。SQLite TransactionTestCase 使用文件库两独立连接和 barrier，无 sleeps 伪造竞争；一方可返回 storage_busy/503，重试后唯一版本。真实 Registry audit.record 包装原函数写入后抛错，断言版本、CAS、来源、audit/outbox及Registry key均回滚；Direct不伪称有Registry审计。

## Task 2: 独立实例初始快照（有 B 交接门禁）

**Files:** Modify Task 1 的 graph_models.py/persistence_contracts.py/graph_actions.py；Create `workflows/instances.py`, `workflows/migrations/0003_graph_instance.py`, `services/workpal/tests/test_graph_instances.py`。不修改 work/execution/agents、公共配置或旧测试。

**Interfaces:** `instances.initialize(actor,subject:SubjectRef,version_id:int,key:str)->GraphInstanceView`; `read(actor,instance_id:int)->GraphInstanceView`; `list_instances(actor,cursor=0,limit=50)->{items,next_cursor}`。使用 Task 1 read_version；使用已有 work.issues.read/read_requirements 获取精确要求及项目身份，保留受保护 Issue/requirements/version FK，Agent 快照使用冻结后的 B Interface。SubjectRef.id为规范正整数字符串，拒绝其他格式；不接受调用者提交的要求/授权快照。Task2暂未授权实施：其中initialize key如何经Registry接入须在B合同冻结时一并复核，不可照原草案增加第二层Intent却取不到外层key。

- [ ] B 交接验收后才写测试：`test_initialization_is_not_execution`, `test_upgrade_preserves_history`, `test_initialize_rechecks_agent_and_requirements`, `test_instance_replay_revocation`, `test_instance_pagination`, `test_two_connection_same_key`, `test_instance_audit_failure_rollback`。断言 state 唯一 initialized，Run/NodeAttempt/Issue 状态及项目/Issue 历史零变化；升级 Agent/要求/图后旧 JSON/hash 不变；撤 Agent/独立要求来源新旧 key 均拒绝；仅撤主体 write 时 read 可用但 initialize 重放拒绝；分页语义同 Task 1；双连接仅一实例；实际 audit/outbox 写后故障全部回滚再重试成功。
- [ ] 运行专项记录产品红灯，然后实现 initialize/read/list。GraphInstance append-only，无 update/delete 动作；不同 key 可保存不同初始实例，不套用手工 Start 活动 Run 唯一性。key 相同同请求回同实例但重查当前主体 write 和保存要求/Agent/input 的当前 read，不改用今天的要求替代旧版本。key 请求 hash 只绑定 subject/version，快照 hash 对完整保存 JSON canonical UTF-8 SHA256；不含自身 sha256，保存的发布时间可含，创建时间在外层。
- [ ] 在 atomic_write 内取得当前主体/要求/B授权，深复制 DTO、保存精确 FK 和来源（主体、精确要求、版本、所有 Agent/input、源根），再保存 intent。B 资格失效返回 B 冻结错误；不落半条实例。read 仅 read 当前全部保存来源，不要求主体 write。注册 `workflow_graph.instance.initialize/read/list`；result_refs 重新验证保存实例身份和精确历史要求，resolve_refs 对 initialize 在缓存前实施混合能力，禁止用 Registry 全部 write 替代它。审计只含对象身份，不记录要求正文/条件值/输入正文。
- [ ] 绿灯验收：`.venv-workpal/bin/python services/workpal/manage.py test tests.test_graph_instances --noinput`。双连接/故障注入方式同 Task 1；幂等、来源、审计与业务在同一事务提交。无匹配 B Interface 时报告 Task 2 未实施，不用 fixture 声称完成接线。

## 最终专项交接与自审

后续实现验收命令（本轮未执行）：`.venv-workpal/bin/python services/workpal/manage.py test tests.test_graph_persistence tests.test_graph_instances --noinput`；`.venv-workpal/bin/python services/workpal/manage.py makemigrations --check --dry-run`；`.venv-workpal/bin/python services/workpal/manage.py check`。迁移升级用已有旧 Workflow/Project/Issue 数据库副本执行 migrate 后逐字比较旧 definition/sha256/workflow_snapshot/要求历史，不修改旧测试。Task1只运行test_graph_persistence和已验收C2a20项、旧workflow/项目绑定专项、makemigrations workflows --check --dry-run、check及85hash；不得运行兄弟在途模块的全量发现。默认配置已经可用，无需新增lane设置或询问配置许可。日志/tmp/workpal-c2b1-*.log。

自审完成：独立模型避免两种 definition 混用；Task 1 可独立验收，Task 2 唯一外部缺口是 B 当前准入合同，已设禁止接通门禁；所有跨任务 DTO 由 persistence_contracts 唯一定义。五项 Review Focus 均有归属测试。当前承诺只覆盖版本存储与初始事实，不覆盖 C2 执行、AutomationRun 或 Runtime。待冻结事项只有 B Interface 的具体名称/DTO/错误码及集成 lane 文件；input_refs 编码、hash 分层、兼容默认和重放能力已在本计划冻结。未运行代码或测试，不能将上述预期当实测。

## 父代理合同复核 — 2026-11-20

保留独立图模型，Task1可实施。纠正两处原方案矛盾：Registry handler不接收key，移除Task1 GraphIntent及Direct key参数，幂等只用现有Registry；派生草稿继承输入限制，publish能力必然作用于这些来源，现明确发布当前publish、更新当前write、读取read，不再承诺输入只需read即可发布。补齐普通ObjectRef名、模型字段/指针CAS、元数据分页、审计无正文和来源循环回滚。Task2的B接口及initialize与Registry幂等衔接仍须后续冻结，不宣称该阶段已具备实施条件。本轮为静态审查，未运行代码测试。

## Task1 实施续作与schema接线 — 2026-11-20

首轮实施代理只阅读，零代码/测试。监督新增tests/test_graph_persistence.py的真实Registry create→read验收样例，先调用workflow_graph.create失败于unknown_action，/tmp/workpal-c2b1-parent-red.log退出1；不是导入失败。续作须保留该断言，实现至绿并补其余完整Task1矩阵。

补冻结条件literal的schema接线：condition.value合法值是任意有限JSON（C2a含递归对象/数组比较），不能强制string。允许本Task1最小扩展actions/schemas.py支持标准JSON Schema空schema {} 作为任意有限JSON literal，check_schema({})可接受、validate仍先执行finite_json；其他非空schema保持既有封闭object规则，additionalProperties=True仍拒绝。新增tests/test_graph_schema.py验证各literal类型、嵌套值、NaN/Infinity/非法Unicode/非JSON类型拒绝，以及旧封闭object未放宽。此通用表达只用于图condition.value叶子；图外层、nodes/edges/config等字段仍完整闭合，语义组合和深度由compile_graph再次验证。输出GraphSnapshot使用同一图schema；不得把整个graph/schema改为{}逃过字段约束。已验收nullable标量联合保持不变。

actions/schemas.py本波仅C实施者可修改，需随test_structured_fields、test_action_http和test_evidence_persistence_review回归；B/D任务不改此文件。默认apps注册最后接入，避免半成品import干扰并行测试。Task2仍等待B合同和幂等接线复核。

Schema子项已监督验收（2026-11-20）：actions/schemas.py仅对精确空dict schema增加有限JSON literal支持，validate先执行finite_json，封闭object和nullable规则保留。新增4项测试，父代理独立运行graph_schema/structured_fields/action_http/evidence_persistence_review共22项退出0，/tmp/workpal-c2b1-schema-parent.log。持久化模型、迁移及Registry仍未实施；原create→read红测仍未修复。下一代理只实施Task1持久化主线，不再修改schema或重复把schema子项算作Task1完成。

Task1主线已实施检查点：GraphDraft/GraphVersion、0002迁移、六Direct与六Registry动作落盘，原create→read红测转绿；Sol专项55项含11个持久化测试通过。当前仅初步功能证据，尚缺真实授权分页、完整拒绝/来源环/缓存与升级验证矩阵。父代理已读取实现和测试，未发现须立即修改的实现缺陷；安排独立有界验收补齐，Task2仍未接。保护检查新增src/studio.js差异，不能据此判整体验收通过，也不得修改该文件消差异。

Task1独立审查第一批：新增test_graph_persistence_review.py的3项首次即绿测试，覆盖create/update/publish实际record后503全行回滚及原key重试、Direct严格ID/revision、分页503传播。Sol冻结专项62项通过；父代理独立复跑原11+新3共14项通过，/tmp/workpal-c2b1-review-parent.log。尚不构成Task1整体验收。余项拆为三个有界批次：R1当前角色/Agent与输入权限、缓存撤权及来源循环；R2输入引用/JSON literal矩阵与真实授权分页审计；R3文件SQLite的Registry竞争及历史库迁移升级。当前仅R1委派实施，R2/R3保持待办，Task2仍有原门禁。85项保护差异仍为.gitignore与指定src/studio.js，全局门禁未通过。

R1功能验收通过：test_graph_permissions.py新增4项覆盖独立Agent/input来源、角色与成员撤权缓存重放、历史来源累积、自身/下游循环的完整回滚及重试。父代理已审阅并在图18+D新8共26项中独立复跑通过，/tmp/workpal-dc-review-parent.log。首次两处失败为测试错误预期非成员403，按现有404隐藏合同纠正；未发现产品缺陷，未修改实现。当前进入R2输入/literal/授权分页，R3并发/旧库升级仍待办；Task2仍不得开始。父代理根npm通过，全局保护门禁仍待确认。

R2功能验收通过：test_graph_inputs_listing.py新增3项公开引用边界/租户隔离、JSON literal往返/封闭字段、真实SourceGrant分页与审计。父代理审阅时补强逐页精确object_refs断言，防止只检查属于全体可见对象却漏记或多记当前页；独立运行图四模块21项退出0，/tmp/workpal-c2b1-r2-parent.log。未修改产品实现。R3作为最后有界批次完成Registry真实双连接同key/独立key发布及隔离历史数据库升级，Task1仍未整体验收；Task2保持原门禁。

## Task1 监督功能验收 — 2026-11-20

R3新增三个独立测试：真实Registry双连接同key/独立key发布、失败key以新revision重试与胜方历史重放；隔离子进程中workflows0001历史schema创建旧Workflow/Project/Issue及两版要求，升级后原始SQL行与关联逐字保持，新Graph表为空、重复迁移无变化。父代理已读测试并独立运行五模块24项全部通过，/tmp/workpal-c2b1-accepted-parent.log。Task1图草稿与不可变版本功能验收通过，未运行图或创建实例。原85项保护门禁仍待src/studio.js来源确认。

Task2继续等待B的admit_initialization实作验收及initialize与Registry key接线冻结；下一并行小任务在execution/admission.py实现该无副作用准入，不提前建立GraphInstance或派发Run。

## Task2 前置验收与幂等接线冻结 — 2026-11-20

B接口已验收：execution.admission.admit_initialization(actor,agent_id)返回frozen AgentInitializationAdmission，agent独立DTO、排序根来源tuple、purpose=initialized、execution_authorized=False；Copilot配置可在无Runtime时准入，四扩展provider拒绝。Sol新6+B24共30项通过；父代理读实现与测试后独立6项退出0，/tmp/workpal-agent-initialization-parent.log。该接口没有Run/Intent/审计/Outbox写入；Graph本身仍负责主体、要求、版本和输入授权。

Task2原initialize签名保留，但幂等改为唯一Registry所有：公开initialize(actor,subject:SubjectRef,version_id:int,key:str)校验SubjectRef后调用execute(ActionRequest('workflow_graph.instance.initialize',{'subject':asdict(subject),'version_id':version_id},None,key))并返回data。Adapter handler只调用同Module内部的创建逻辑，不递归调用initialize；不新增GraphIntent/InstanceIntent，不读写Registry私有_specs/缓存表，不用ContextVar偷传key。普通通用HTTP动作也经同一Registry执行。幂等哈希沿既有payload+expected_revision，公开wrapper固定None；不同key允许新事实，同key不重新快照。

SubjectRef只接受type='issue'、id为规范正整数字符串（无符号/空白/前导零，<=MAX_SQLITE_INTEGER-1）；Direct拒绝任意dict替代SubjectRef，Registry subject为封闭{type,id}对象。version/instance ID及分页用严格整数。新对象kind=workflow_graph_instance，普通派生对象，不是来源根。

GraphInstance新增workspace、version(GraphVersion)、issue(work.Issue)、requirements(work.IssueRequirements)、created_by用户FK（全PROTECT）、state Char16 default initialized、snapshot JSON、sha256 Char64、created_at auto_now_add；无revision、无修改/删除接口。主键BigAutoField；正常workflows0003_graph_instance迁移。所有FK同区及requirements属于issue在业务事务验证。snapshot结构沿InstanceSnapshot：schema_version=1、graph_version完整GraphVersionView、issue完整当前IssueView、requirements精确History、agents按id排序去重的当前Agent DTO、source_refs为主体/项目/精确要求/图版本/Agent/input直接引用及全部根的排序并集、created_by。created_at只在外层；sha256对完整snapshot canonical UTF-8有限JSON计算，不包含自身hash。所有返回深复制，state只能initialized。

initialize resolver在缓存前用既有issues.selected(actor,id,'write')核验当前主体，但不调用issues.read去提前取今日要求正文；用persistence.read_version核验精确版本、从其不可变resolved_inputs核对Agent/input，并对每个Agent调用admit_initialization。对主体显式write，其余read，ActionSpec.capability='read'，不要用全局write误拒只读输入。resolver返回主体/项目/版本/Agent/input引用，确保当前授权与历史scope保留。创建handler才在同一事务调用issues.read和read_requirements获取当前精确要求，保存其FK/快照；全部对象当前read再次成立后登记instance来源。任意失败全事务回滚，无Run/Issue/Agent改动。

初始化result_refs复查保存结果对应真实GraphInstance、workspace/subject/version/requirements FK与快照身份，读取精确保存要求的read权限、当前主体write及保存实例全部来源read；不能把今天新要求替换旧版本。同key重放只依赖原保存要求的read（当前Issue ref仍须write），今日独立要求来源收窄不应无故取今日正文导致旧快照无法重放。若原要求或Agent/input撤权，旧key拒绝。B资格当前失效同样拒绝初始化旧key；普通read只核验保存内容read，不因provider后改而失去历史读取。read/list不要求主体write，读无业务Outbox/cache。

Registry新动作initialize/read（后续list），allowed_roles owner/admin/member，无额外人类确认/revision；initialize key必填。审计仅subject/version_id/instance_id/分页等身份，不含snapshot/正文。输出外层和snapshot封闭schema；Adapter层可复用work.issue_actions.VIEW/HISTORY、agents.actions.VIEW、graph_actions.VERSION等现有静态schema，业务instances.py只调用公共业务Interface，不能使用{}放开整个快照。图condition.value仍沿已验收有限JSON literal schema。

### Task2a：初始快照创建与精确历史读取

允许修改workflows/graph_models.py、persistence_contracts.py、apps.py（仅注册）；新增instances.py、instance_actions.py、0003_graph_instance正常迁移、tests/test_graph_instances.py，更新GRAPH.md；不改agents/execution/公共schema/配置/旧测试。实现initialize/read及其两个Registry动作，不提前做list。

- [ ] 真实Registry initialize先unknown_action红灯，再实现同测转绿；主体/版本/Agent均通过真实Interface建立。
- [ ] 至少五项独立测试：创建→read哈希/深复制/精确FK与无执行副作用；同key不变与异请求409；Agent/要求/图更新后旧快照不变、新key新当前事实；当前主体write与独立要求/Agent/input read的混合授权，含只撤write保留read和四扩展provider；真实record写后503完整行回滚及原key重试。旧key与今日独立要求授权的特殊对照必须覆盖。
- [ ] 新专项+Graph持久化五模块24项+初始化准入6项、workflows迁移dryrun/check/85hash；日志/tmp/workpal-c2b2a-*.log。完成后交父代理，不声称图执行。

### Task2b：授权列表与实例竞争验收

Task2a验收后补list_instances/Registry instance.list、授权后分页、真实双连接同key实例唯一、完整缓存撤权/跨区与实际审计后失败矩阵、旧库升级保持全部既有图/Issue历史。此段另派有界任务；Task2整体仅两段均验收后完成，仍不含节点推进或派发。

## Task2a 实施检查点 — 2026-11-20

GraphInstance/正常0003迁移、initialize/read及两个Registry动作已落盘。父代理已阅读模型、迁移、instances与Adapter及8项测试，并独立复跑8项退出0，/tmp/workpal-c2b2a-parent.log。现有证据覆盖initialized无Run、哈希与返回深复制、同key历史快照、今日独立要求撤权不影响旧key、主体write撤销、审计后回滚；尚不能代替完整混合权限及provider矩阵。

下一独立审查仅新增test_graph_instances_review.py：用真实当前Agent修改四扩展provider；分别撤Agent/input/保存要求read或仅write；不同Agent与重复节点去重、跨workspace/主体/version组合；核对历史内容/hash与缓存重放，全表回滚及副作用。保留原8项；正确行为首次绿如实记录，发现实现缺陷先复现再最小修复instances/instance_actions。Task2a仍待该审查，Task2b尚未开始。保护差异仍为既知两项，不静默放行全局门禁。

Task2a独立审查第一批新增4项，真实四provider变更、保存要求read撤权、Direct/Registry共享key、SQL全表回滚与hash均通过；父代理将fixture改成模块导入，避免单独发现该文件时混入原测试类，未改变行为断言。父代理原8+新4纳入联合30项退出0，/tmp/workpal-bcd-small-parent.log。该批不替代尚缺矩阵。

剩余审查只新增test_graph_instances_permissions.py的两个有界场景：①真实member、两个Agent及重复节点、独立Agent/input来源分别只撤write或撤read、新旧key/read与来源完整去重；②actor同时是两区成员的主体/version/Agent/input跨区拒绝，合法另一主体/版本同key冲突及严格ID/SubjectRef边界。所有拒绝完整行不变；不重做已验收provider/回滚矩阵，不提前实施list。两场景完成后交Task2a整体验收。

## Task2a 监督功能验收 — 2026-11-20

剩余两项真实member/多Agent重复节点/独立来源混合能力及双workspace归属、严格ID矩阵已完成，未修改实现。父代理读逐项断言后独立复跑原8+review4+permissions2共14项退出0，/tmp/workpal-c2b2a-accepted-parent.log。结合此前的完整SQL回滚、历史key/当前配置与保存要求复核，Task2a初始快照和历史read功能验收通过；不存在Run创建或节点推进。两项首轮失败为fixture/helper及错误预期修正，不记产品红灯。原85项保护门禁仍待确认，Task2整体尚缺下述两段。

### Task2b1：当前授权后的实例摘要列表

允许修改workflows/instances.py、instance_actions.py、persistence_contracts.py、GRAPH.md；新增tests/test_graph_instance_listing.py。无模型/迁移/配置变更，不改旧14项。

公开list_instances(actor,cursor=0,limit=50)->{items:list[GraphInstanceSummary],next_cursor:int}。Summary固定{id,version_id,subject:{type,id},state,sha256,created_at}，无snapshot/正文；完整内容仍用read。cursor严格int、0..MAX_SQLITE_INTEGER-1，limit严格int且1..200；任何额外字段由Registry封闭schema拒绝。当前require_member及workspace过滤，按pk递增；逐候选复用本Module现有selected的保存身份/FK与完整来源read验证，仅403无权跳过，其他错误尤其503传播。授权后再计数分页，多看一条可见项，next_cursor为最后返回可见项id，有且只有后续可见项时非0。全私有/末页返回0，无total或私有编号/数量。历史读取不调用admit_initialization、不要求主体write，当前provider改变不影响合法历史摘要。可复用selected读取保存快照完成验证，本轮不承诺完全避免snapshot数据库列读取；输出仍严格仅摘要。

注册workflow_graph.instance.list，只读、allowed_roles同read、capability=read、无key/确认/revision要求。可选forms必须把未提供cursor/limit实际归一为0/50，避免已有Evidence的默认值遗漏问题。resolve_refs不把未返回候选纳入scope；result_refs仅逐个验证返回摘要与对应真实实例、当前saved来源，再返回本页实例refs。Registry访问审计object_refs仅本页，scope继承本页完整限制，不记录私有候选或额外peek项；无Outbox/cache/业务写。Direct无审计。返回数据不可变更保存事实。

四项有界验收：①真实Registry缺list动作红灯后变绿，默认参数、严格边界/封闭字段及合法空页；②真实SourceGrant私有前/中/尾混排，分页无重复/漏项，逐页精确object_refs及scope；③仅撤主体write或改provider仍可列历史，撤read即时过滤，跨区成员与停用成员当前检查；④真实授权503及实际read audit后503传播，SQL全表回滚；每次成功Direct/Registry分页仅预期访问审计、无业务变化，返回无snapshot。新模块加原14项、限定workflows迁移dry-run/check/85hash；不跑全量或根npm。日志/tmp/workpal-graph-instance-listing-*.log。

### Task2b2：实例竞争与历史升级（b1后独立验收）

保留b1实现和测试，只补文件SQLite两独立连接的同key一次实例/audit/outbox/cache、不同key合法两个初始事实，以及隔离workflows0002历史schema到0003升级保持旧图/Issue/要求行和hash、新GraphInstance表为空、重复迁移不改变数据。实际record故障完整回滚已由Task2a覆盖，仅对并发产生的新关注补验，不反复扩张旧矩阵。完成后Task2才整体功能验收；节点推进、Run派发仍属后续C2。

Task2b1监督功能验收通过：摘要list及只读Registry动作已实施。父代理读实现及5项测试，并补强原AuditEvent行不变和真实主体write撤销对照；独立新5+原14共19项退出0，/tmp/workpal-c2b2b1-parent.log。默认分页、严格摘要、当前授权后分页及精确本页审计、503回滚均有证据。Task2b2现可只新增tests/test_graph_instance_concurrency.py完成上述三项（同key、不同key、真实历史升级），不改模型/迁移或旧测试。

保护确认已关闭：用户明确确认保留studio.js单行改动，精确允许hash见protection-exceptions.json。85项原基线仍保留，当前核验仅两处已接受差异；本文件早先“待确认”是历史记录，不再作为当前门禁。

## Task2 与图持久化监督功能验收 — 2026-11-20

Task2b2三项独立测试完成。父代理读真实文件SQLite双连接/barrier、同key一次事实/不同key两个事实及独立子进程MigrationExecutor历史0002升级代码，复跑原19+新3共22项退出0，/tmp/workpal-c2b2-accepted-parent.log。验证包含业务/来源/audit/outbox/cache精确计数、原Issue/要求/执行记录不变、完整snapshot/hash和深复制、旧图/Workflow/Project/Issue/两版要求SQL行保持以及重复迁移稳定。

Task1图草稿/不可变版本、Task2初始实例/历史读取/授权摘要列表及持久并发、迁移范围功能验收通过，即C2b存储阶段完成。此结论不包括C2c节点推进、人工节点处理、Squad分工或Run派发；这些仍须后续冻结协调与B节点准入合同，不把initialized解释为running。保护核验使用原85项基线加两项已确认精确例外。
