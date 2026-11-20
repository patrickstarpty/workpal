# Workpal Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从空工作区完成多人协作、人工提交、证据存储与版本化评审，不伪造 Run。

**Architecture:** Django 管身份与持久化，业务动作集中到深 Module Interface；先建立动态数据权限，后续环境调查不需补丁式追踪泄露。

**Tech Stack:** 主计划固定的 Django/Python/SQLite，原生 ES modules。

**Spec:** [设计](../specs/2026-11-20-workpal-software-development-design.md)；[主计划与公共契约](2026-11-20-workpal-software-development.md)。

## Global Constraints

完整继承主计划 Global Constraints。“原型 SQLite 不直接升级为正式产品数据库。” “不把人工评审改成 Agent 自我批准。” 本批只改新产品目录、任务明确的新文档及忽略规则，不接真实外部环境。

## Review Focus

跨工作区猜 ID、同名对象歧义、撤权后派生记录访问、并发审核与缺失证据、恶意文本与本地笔记保留，分别由 A1–A5 测试固定。

## 监工记录：A1 首次交付未通过

2026-11-20：GPT 6.1 Sol 已建立 Django/SQLite 骨架和独立虚拟环境，报告 migrate、Django check、原型 `npm run check` 通过；`test_identity.py`、`test_storage.py` 尚未存在，A1 不验收、不推进 A2。先实现后补测试的事实保留，不能把 import failure 补记为有效行为红灯。

主代理检查现有代码发现：auth login/logout 同时接受 GET；登录限速模型未接入；成员创建仅有内部方法、无 HTTP 管理及撤权路径；请求对象/字段类型、长度、revision 校验不足；部署可能回落到固定开发 SECRET_KEY，测试库目录在导入 settings 时无条件创建且未清理。须补行为测试和必要实现，不能仅修到两个测试文件可导入。

已比对 `/tmp/workpal-supervision-baseline-20261120.json`：受保护文件只有允许追加的 `.gitignore` 与基线不同，现有 `src/`、`backend/`、存档和用户其他追踪改动未改变。下次交付应重复核验并保留本条记录。

第二次交付仅完成 HTTP 方法、JSON 对象及字段校验，新增3个身份测试并通过；尚不验收A1。后续拆为两个文件互不重叠的实施单元：身份管理（identity、urls、身份测试、初始化命令）和存储配置（settings、storage、SQLite连接配置、文件库runner及存储测试）。主代理最后统一运行完整A1验收，不因子单元完成提前推进A2。

身份子单元交付后，主代理补 `tests/test_identity_review.py`：复现无权用户可通过验证顺序探测用户名、成功登录清掉并发失败、GET撤销路由错误开放、只配置ALLOWED_HOSTS却未在读取路径检查Host。已修正并验证身份相关19项测试通过；测试还覆盖admin不能授予/更改owner、最后owner保护（既有测试）、跨区成员ID、撤销一区成员不影响另一区、另一会话Cookie失效和非法输入。并发测试只替换密码检查耗时环节，实际SQLite/事务/线程不替换。受保护基线仍只有`.gitignore`不同。存储子单元及完整A1集成验收尚待完成，所有A1任务框继续保持未勾选。

---

### Task A1: 可登录的空工作区与 SQLite 写入契约

**Files:** Create `services/workpal/{manage.py,pyproject.toml,requirements.in,requirements.lock}`、`services/workpal/config/{settings.py,urls.py,wsgi.py}`、`services/workpal/workpal/{contracts.py,storage.py}`、`services/workpal/workpal/identity/{models.py,service.py,actions.py,migrations/0001_initial.py}`、`services/workpal/tests/{support.py,test_identity.py,test_storage.py}`；Modify `.gitignore`（仅追加 `.venv-workpal/` 和新产品本地数据路径）。各 Python package 加 `__init__.py`。

**Interfaces:** Produces 公共契约；`identity.authenticate(credentials)->Actor`、`identity.require_member(actor,workspace_id)->Membership`；`storage.atomic_write(operation)->result`。`tests.support.WorkpalCase` 用 Django Client 提供 `self.act(actor,action,payload,key=None,revision=None)` 返回 `ActionResult` 或抛 `DomainError`，后续从 Registry 调用；本任务认证测试先用 HTTP Client。fixtures `make_workspace`、`make_member` 创建真实库记录，不绕过授权断言。

- [x] **Step 1:** 建最小可执行 test 配置、依赖清单及锁文件；固定 Django 5.2.19、Gunicorn 27.0.1，锁传递依赖。创建测试 `test_session_workspace_isolation`（其他 workspace GET=404）、`test_csrf_rejects_write`（403）、`test_stale_revision`（409）、`test_busy_timeout`（503/retryable）。两个实际连接竞争同 revision，仅一条写入成功；网络调用不得出现在 `atomic_write` 回调中。
- [x] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_identity tests.test_storage --noinput`，预期因缺少身份/持久化行为失败；不能只凭 import 失败完成红灯步骤。
- [x] **Step 3:** 实现本地账号、管理员创建成员、登录/登出/会话撤销，owner/admin/member 角色、无公共注册。密码使用 Django 哈希；会话 Cookie 为 HttpOnly、SameSite，正式 HTTPS Secure；验证 Host/CSRF。建立实体 workspace 外键、revision 和基础唯一约束，主计划 WAL/IMMEDIATE 设置实测生效，写后才返回成功。`requirements.lock` 安装检查与 migrate 从空文件库通过。
- [x] **Step 4:** 复跑同命令，预期全绿；添加登录失败有界速率限制和用户停用使旧会话失效的断言。失败消息不区分不存在账号与密码错误。
- [x] **Step 5:** 检查 diff 只含本任务路径，记录测试结果；准备提交 `feat: add isolated workspace identity and sqlite transactions`。

A1 统一验收通过（2026-11-20）：默认 `manage.py test --noinput` 真实发现并通过30项测试；空临时库 migrate/check 通过；makemigrations --check 无变化；npm run check 的102项Node测试、2项原型后端测试及单HTML构建通过。主代理另修默认测试从仓库根目录发现0项和迁移失败后数据库NAME未恢复的问题，均有失败→通过回归。部署check只有有意未加入浏览器HSTS预加载列表的W021提示；并未配置或声称完成生产部署。bootstrap参数已核对并写入新服务README。受保护基线除允许的.gitignore追加外一致。未提交Git、未调用真实模型或外部环境。先实现后测试的历史问题仍按上文保留，不追认原始过程符合TDD。通用测试辅助 `tests/support.py` 随真正使用Registry的A2建立，不为A1造空实现。

### Task A2: Action Registry 与可传播权限

进度（2026-11-20）：来源授权子单元经主代理审查通过，`register_object/derive_scope/authorize` 使用真实SQLite记录、递归全部来源和实时grant；已补“删除被引用来源不能变公开”回归。access共12项、全量42项测试通过，迁移与配置检查通过。发布许可、Registry、幂等/确认、审计/outbox及HTTP动作统一仍未完成，A2不整体勾选。前一轮仅import失败不计为行为红灯。

发布许可子单元随后经主代理补测与修复：提供实际SQLite内容snapshot、绑定具体内容/来源/目的地/人/revision/有效期的许可；真实双连接并发审批仅一条成功，审批人撤成员/发布权限和创建人撤读取权限即时阻止外发。补修bool版本号、非法UUID错误及有效期未绑定问题。测试fixture改为无测试方法的mixin，不重复继承计数；当前独立publication测试12项，全量54项通过，迁移检查无变化。尚无外部发送能力，Jira/Repo当前受众验证仍归D/B集成任务；Registry、确认/幂等、审计/outbox及HTTP统一尚待完成。

Registry 核心子单元经主代理补测与修复（2026-11-20）：16项原测试外新增6项行为回归，修复原输入来源在绑定变化后丢失、audit/outbox未保存来源限制、api_key被审计allowlist收录、读取动作误写outbox、非法ActionResult状态未拒绝；输入来源在handler前快照，撤销对象的动作不会因事后重查原对象而失败。幂等结果、审计和outbox持久化scope_refs，重放重新检查历史来源与当前权限；测试结束恢复Registry注册表。全量76项独立测试通过（含真实双连接同key竞争），迁移检查无变化，保护基线仅允许的.gitignore追加有差异。原交付import failure不算有效行为红灯；本轮新增回归有实际失败→通过证据。确认仍仅返回waiting_confirmation，尚无持久确认与HTTP统一入口，A2继续保持未完成。

确认核心子单元验收（2026-11-20）：Confirmation保存参数hash、expected_revision、user/workspace/action/key、来源范围和10分钟有效期；准备不执行handler，消费与本地结果/audit/outbox在同一事务。相同key重试不续期，过期待确认须新key；已完成结果只读重放不重复消费。主代理新增5项测试，覆盖跨用户/工作区/action、真实revision CAS冲突及角色/成员撤销，并修复Agent省略确认ID绕过重放人类限制、普通动作静默忽略其他动作确认ID两处问题。全量89项独立测试通过，包含双连接同token只执行一次；迁移一致性检查通过，保护基线仅.gitignore允许追加不同。尚无统一HTTP动作入口及A1业务资源别名迁移，A2未整体验收。

HTTP传输子单元验收（2026-11-20）：新增通用POST动作和GET catalog，真实会话构造Actor、Host/CSRF、严格有限JSON与重复键检查、1MiB请求上限、脱敏500及事务回滚均经HTTP测试验证。主代理补4项测试，修复超长工作区ID与越界revision被误报500、未配对Unicode代理字符未拒绝；SQLite整数上界为共享存储约束。全量102项独立测试通过，迁移检查无变化，受保护基线仅允许的.gitignore追加不同。生产进程暂未注册业务动作，catalog可为空；A1资源路由尚待迁移，A2仍未整体验收。

业务注册/资源迁移首次委派未交付（2026-11-20）：子代理仅读取资料并复跑102项基线，无红测、无实现改动；不接受为完成。后续拆为“身份业务动作注册”和“资源路由别名迁移”两个独立实施单元，A2保持未验收。

身份动作注册子单元验收（2026-11-20）：启动注册workspace.read/rename及member.list/create/set_role/revoke，成员授权变更要求确认，rename/set_role/revoke要求正整数revision。handler复用已有identity service；Registry仅在非空输出引用时执行事后对象授权，合法自撤可完成，后续新请求和已完成重放仍因失去当前成员身份拒绝。已验证密码不进入Confirmation、IdempotencyResult、audit/outbox或动作输出。全量109项独立测试通过、迁移检查无变化、保护基线仅.gitignore允许差异。旧资源路由仍未迁移，A2未整体验收。

**Files:** Create `services/workpal/workpal/actions/{registry.py,schemas.py,http.py,models.py,migrations/0001_initial.py}`、`services/workpal/workpal/access/{models.py,service.py,contracts.py,migrations/0001_initial.py}`、`services/workpal/workpal/audit/{models.py,service.py,migrations/0001_initial.py}`、`services/workpal/tests/{test_actions.py,test_access.py}`；Modify `config/urls.py`；Create `tests/support.py`。

**Interfaces:** Consumes Actor/ObjectRef/DataScope/ActionRequest。Produces `actions.catalog(actor)->list[ActionSpec]`、`actions.execute(actor,request)->ActionResult`；`access.authorize(actor,action,refs)->None`、`derive_scope(refs)->DataScope`、`prepare_publication(actor,source_refs,destination,content_ref)->PublicationPayload`、`authorize_publication(actor,payload_id,expected_hash)->None`。ActionSpec 含 forms schema、handler、授权/确认策略、补偿标识；外部使用者不能传 Python handler 或 arbitrary action code。

- [x] **Step 1:** 写 `test_action_schema_rejects_extra_fields`、`test_same_key_same_result_different_payload_conflicts`、`test_multi_source_requires_all_grants`、`test_revocation_restricts_descendants`、`test_publication_approval_is_destination_and_hash_bound`。核心断言：`assert derive_scope([a,b]).source_refs == {a,b}`；只获 a 权限的用户不能读派生物，即使是 workspace admin 也需相应数据授权。
- [x] **Step 2:** 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_actions tests.test_access --noinput`，预期拒绝/传播断言失败。
- [x] **Step 3:** 实现 Registry、HTTP 动作映射、当前权限检查、schema 生成与验证；本地副作用、结果、AuditEvent、Outbox 同事务。幂等键作用域 `(workspace,user,action,key)`，请求 hash 不同返回409。Confirmation 保存参数 hash、对象 revision、操作者、有效期（默认10分钟），一次性消费；删除、授权、轮换、合并须确认，普通可恢复创建不强制确认。
- [x] **Step 4:** 实现来源引用与派生引用（通用 ObjectRef 可先代表测试数据源），动态授权只保存关系、不复制宽松角色；脱敏不等于解限。发布内容与目的地要有独立许可。复跑测试并验证直接资源路由与 Chat 风格调用得到相同拒绝和审计，不开 ORM 绕行写入口。
- [x] **Step 5:** 记录 Interface 契约和结果；准备提交 `feat: centralize actions and inherited data access`。

A2 统一验收通过（2026-11-20）：六个身份资源路由均映射Registry，auth/session保持独立传输入口。主代理新增8项真实HTTP集成测试，确认跨入口同key只一份业务效果/审计/outbox、确认双向互通、角色变更/撤销重放、读取仅审计无outbox、输入/Host/CSRF/当前权限一致拒绝、密码不持久化、异常回滚和500脱敏；建立并实际使用WorkpalCase，清除旧认证入口残留的资源分支。全量119项独立服务测试通过，空临时SQLite migrate、makemigrations --check和Django check通过；npm run check的102项Node测试、2项原型后端测试及离线HTML构建通过。保护基线仅.gitignore允许追加不同。未commit/push、未连接真实模型或外部环境。前述先实现后测试/import failure的历史不追认为完整TDD；阶段验收以当前可重复行为证据为准。Publication仍是内部许可核心，实际外发受众验证归B/D集成，不能将本验收当成真实外发或首版交付。

### Task A3: 项目、任务与协作记录

实施拆分：先完成项目记录与授权分页，再接项目资源/不可变工作流、Issue及依赖、协作记录；每个子单元独立验收，不提前勾选A3。A2的Outbox是持久业务事件，不等于执行派发；本任务“没有outbox dispatch”指不得产生Run或执行派发命令，普通业务事件仍随写入同事务保存。B1 Worker只能领取明确的执行命令，不能将任意业务事件当成启动Agent的请求。

项目核心子单元验收（2026-11-20）：Project六动作支持稳定ID、同名明确选择、CAS、归档恢复、当前来源授权和授权后分页。主代理将身份catalog回归改为检查身份动作集合及角色边界，避免与新增合法目录项耦合；新增4项实际失败→通过回归，修复内部service可改变workspace、直接create注册失败残留记录、全空白项目名称和省略description导致上下文误清除。project.update省略description保留原文，显式空字符串清除。全量132项独立测试通过、迁移检查无变化，保护基线仅.gitignore既有允许差异。项目资源、工作流、Issue及协作记录未完成，A3保持未验收。

仓库资源子单元验收（2026-11-20）：ProjectResource六动作保存GitHub/Azure Repos未验证配置；来源继承父项目并只追加，支持授权后分页、CAS、软移除确认和恢复。主代理补6项测试，验证多源撤权分页/历史限制与循环来源导致更新完整回滚，并修复更新Form共享字段导致创建schema必填项丢失、StructuredField未调用声明validators、非法数组边界配置未拒绝、归档项目状态冲突返回码。全量148项独立服务测试通过，迁移检查无变化，保护基线仅.gitignore既有允许差异。仓库未连通或执行；当前资源类型仅repository，local_directory等后续Runtime输入仍未实现；工作流、Issue及协作记录尚待完成。

工作流版本子单元验收（2026-11-20）：草稿与发布版本持久化，定义含状态/转换/评审策略，允许合法返工循环但不执行脚本；发布复制名称/完整定义并保存SHA256，旧版本不从新草稿重建。主代理补8项测试，含真实双连接同revision一胜一冲突、同key只发布一次、完整定义变化后的旧快照、动态撤权/分页/工作区/成员权限与发布后半段失败的完整回滚；修复全空白状态label可通过的问题。全量160项独立服务测试通过，迁移检查无变化，保护基线仅.gitignore允许差异。Project绑定、Issue消费和图执行尚未接入，A3未整体验收。

项目工作流绑定子单元验收（2026-11-20）：project.set_workflow 以当前revision和人类确认绑定发布版本，0恢复内建默认；历史来源只追加。project.workflow.read返回独立完整快照，内建读取不生成伪发布记录。主代理新增7项测试，验证共同owner也不能跨区绑定、未发布draft ID和非法字段拒绝、确认等待期间撤权/来源变化/CAS冲突、注册后半段失败回滚确认及绑定、内建内容哈希一致。专项12项、全量172项独立服务测试通过，迁移一致性和Django check通过，保护基线仅.gitignore允许差异。Issue、协作及图执行未实现，A3保持未验收。

A3-5实施约定：Issue记录与要求历史。work模块独占Issue及其要求版本的写入；对外小接口为create/read/update/archive/restore/list/read_requirements，Registry只是schema和DTO适配。创建时持久化完整项目工作流快照（包括内建定义），并以定义中首个backlog分类状态为初态；后续项目绑定和默认定义变化不重写已有Issue。要求版本保存title/description/稳定key的criteria及哈希，更新要求只追加版本；负责人/归档变化只递增Issue revision，不伪造要求变更。当前先支持同区有效人类成员负责人，Agent/Squad分配留后续模块接入。Delivery后续引用明确requirements_version_id及revision，不从当前要求重建历史。状态转换、依赖、评论/Inbox分后续单元；普通写入仍只记录业务事件。

Issue记录子单元验收（2026-11-20）：Issue七动作、完整工作流快照、追加式要求版本及人类负责人校验已实现。主代理补10项回归，确认发布版本改绑/reset不改旧Issue、同区且可读的负责人、跨区/停用身份拒绝、归档项目保留既有记录、创建重放不重复业务事件、中文内容哈希、来源追加和授权分页、创建/更新失败的七类表完整回滚。直接service非法Unicode出现真实编码异常红灯，修为DomainError输入拒绝；普通HTTP已有严格JSON校验。专项19项、全量191项独立服务测试通过，迁移一致性及Django check通过，保护基线仅.gitignore允许差异。无Run/状态转换/协作/交付实现，A3继续未整体验收。

A3-6实施约定：Issue状态转换、阻塞和依赖。状态与合法边均读取Issue自己的workflow_snapshot；现有七种状态category另投影为unstarted/started/done/closed生命周期，不改变已发布定义。人工Done要求人类身份、非空理由及快照review_policy的manual策略和reviewer_roles；approved_delivery/approved_head_merged在真实证据门禁接入前拒绝完成，不接收客户端approved标志。Block记录原因和可读的同区责任人，解除保留历史且不启动执行。依赖只允许同区且无环，依赖来源继承只追加；移除关系不解除历史数据限制。完成转换时检查当前依赖是否done，不自动跟随其他Issue改变状态。后续Runtime复用依赖查询接口，任何业务事件都不能直接当作Run派发命令。

状态与依赖子单元验收（2026-11-20）：合法转换、阻塞责任、不可变转换历史、人工完成门禁与依赖记录已实现。主代理补16项回归，覆盖自定义key与旧快照、完整人工完成边界、来源撤销/分页、依赖未完成/取消/归档、关系重加与历史来源保留、反向并发无环和同key并发只一效果、后半段失败九类表回滚。真实红灯后修复：人工Done重放绕过人类/当前评审角色检查；历史列表未逐条授权且审计漏掉历史独有来源；有效多字节文本误按字节数拒绝。专项21项、全量212项独立服务测试通过，迁移一致性和Django check通过，保护基线仅.gitignore允许差异。未启动Runtime、图执行或交付批准，A3整体仍未完成。

A3-7实施约定：评论创建/读取、个人订阅与Inbox。collaboration拥有评论、订阅、通知及已读状态；通过work公开只读接口获得Issue上下文，不跨模块改Issue。评论与通知继承Issue及额外来源，通知只存对象引用与事件标识，列表按当前权限投影标题且授权后分页。评论提及和订阅动态在本地写事务内形成通知；同事件同收件人去重。个人已读只是收件人的元数据，不能改Issue状态、要求或阻塞事实。之后仍需完成评论编辑/移除、分配/阻塞通知接线、子任务关系与Activity等A3剩余行为，再整批验收。

评论与Inbox基础子单元验收（2026-11-20）：8个Registry动作支持评论创建/读取、个人订阅和Inbox/已读。子代理13项测试包含真实同key双连接并发；主代理补6项回归，经真实失败修复归档后已有评论创建结果不能重放、通知hook使用调用者旧ORM对象、非权限故障被静默当成不可见订阅者跳过三处问题。跨区/收件人隔离、实时标题投影、额外来源审计、已读后半段失败回滚已核验。专项19项、全量231项服务测试通过，迁移一致性和Django check通过，保护基线仅.gitignore允许差异。评论编辑/移除、分配/阻塞通知接线、子任务和Activity仍待完成，A3未整体验收。

A3-8实施约定：评论CAS编辑、软移除/恢复与Inbox标未读；作者或当前owner/admin在来源write授权内管理评论，移除须人类确认，重放仍复查当前管理权限。移除不硬删除历史，默认列表隐藏，授权按ID读取仍可恢复。编辑只通知新增提及，旧通知保留且继续继承当前来源限制。work拥有Issue变化，collaboration以小通知接口消费其已持久化ID/revision，分配和进入Blocked同事务落通知；分配给操作者本人默认无自通知，阻塞决策发给明确责任人。标已读/未读和任何通知都不替代Issue状态变更，不派发Run。子任务、Activity和A3集成验收另行完成。

A3-8首次委派未完整交付（2026-11-20）：只实现inbox.mark_unread，不接受为A3-8完成。主代理强化其他收件人的测试，先成功调用真实动作再精确断言not_found，排除unknown_action的404假阳性；另补来源撤销后新请求与已完成重放均403且通知不变的回归。标未读专项3项、全量234项服务测试通过，迁移一致性/Django check通过，保护基线仅.gitignore允许差异。余项拆成A3-8a评论管理、A3-8b分配/阻塞通知接线，继续由GPT 6.1 Sol实施。

A3-8a评论管理验收（2026-11-20）：编辑、软移除/恢复与新增提及通知已实现；权限在handler及幂等重放前均复查，移除需人类确认，来源只追加。子代理18项行为测试通过，主代理补2项：通知后半段503使已写的新通知/正文全部回滚并可重试；直接service错误类型source_refs/非法Unicode来源在真实失败后修为400且不改记录。另用独立临时文件库从含评论/订阅/通知的0001迁移至最新，验证既有正文/mentions/revision/引用保留。专项20项、全量254项服务测试通过，迁移一致性和Django check通过，保护基线仅.gitignore允许差异。A3-8b分配/阻塞通知及后续子任务/Activity尚未实现，A3仍未整体验收。

A3-8b分配/阻塞通知验收（2026-11-20）：Issue创建/变更负责人及进入Blocked已接入collaboration小接口，同事务保存通知；不扩大发送范围、不调用Runtime。主代理补9项回归，无需实现修复：custom blocked key、Agent自分配、通知已读后源动作及hook重放、来源撤销、创建/阻塞阶段503后全表回滚及重试、当前写权限/收件人成员检查、实际双连接分配和阻塞同key各只一通知。专项21项、全量275项服务测试通过，迁移一致性/Django check通过，保护基线仅.gitignore允许差异。A3-8协作管理与通知范围已验收，A3整体仍待子任务、Activity及集成检查。

下一实施单元 A3-9：子任务关系。Issue可有同workspace的一个父Issue，创建时可明确parent_issue_id；跨project关系仍须满足两边当前来源权限。已有关系由独立CAS动作设置/解除，来源只追加，解除/换父不降低历史限制。子任务仍按所选Project在创建时固定自己的工作流和要求，不复制或重写父任务要求；状态、交付和执行保持独立，完成或归档一方不自动改另一方。层级不隐含Run派发或替代父任务评审。拒绝自身/层级环/跨区；新挂接拒绝归档父任务，已有关系保留。子任务列表和parent筛选先授权再分页，不泄露隐藏子项或总数。Activity及A3整体验收留后续单元。

A3-9子任务验收（2026-11-20）：子代理11项基础测试外，主代理新增13项监督回归，均通过，无需实现修复。覆盖换父/解除后的全部历史来源、隐藏子项授权后分页及组合筛选、负责人不可读导致全表回滚、既有评论与Inbox动态继承、跨workspace/跨project及独立工作流与状态、归档父任务的新写入与已完成重放区别、历史来源循环、后半段503完整回滚及同key重试、严格ID类型、普通成员双边write门禁。真实双SQLite连接同key只提交一次，反向挂接只允许一个方向成功。专项24项、全量299项服务测试通过；迁移一致性、Django check通过，保护基线仅.gitignore既有允许差异。本轮新增监督测试起始即绿，不追认为实现前红灯。根npm留A3集成验收；Activity与资源路由别名仍待完成，A3不整体勾选。

下一实施单元 A3-10：Issue Activity。audit深模块拥有历史记录筛选、当前授权、游标和安全投影，work仅注册薄动作；公共接口 `audit.activity.list_issue_activity(actor,issue_id,cursor='',limit=50)->(page,scope_refs)`。依赖为in-process业务读取接口与真实本地SQLite，不增加Repository或泛化事件框架。仅展示真实已完成Issue/Comment业务变更的AuditEvent；明确动作allowlist，排除读取、订阅、个人Inbox及身份事件。不反推不存在的历史before/after、执行身份或测量结果，不输出原始fields、评论正文、来源列表或凭据。Issue事件按其主输出对象关联；评论事件通过已授权的collaboration.read查真实所属Issue，不能把作为来源的其他Issue误认成评论所属任务。每项同时校验当前subject、保存的全部scope_refs和object_refs，再做分页；输出引用保留已展示事件的完整来源限制。游标绑定workspace/Issue，按created_at和UUID稳定排序，默认50/最大200，不输出隐藏总数。Activity读取仍按Registry记录访问审计，但不产生outbox，也不把自己或其他读取事件再次显示。后续另补设计中现已具备能力的两条Issue资源别名及A3整批验收；尚未实现的Run/Delivery等别名随其所属批次接入。

A3-10 Activity验收（2026-11-20）：子代理14项测试覆盖Registry真实unknown_action红灯到实现绿灯。主代理另补6项当前实现即通过的监督测试：依赖/父子主事件归属、评论编辑移除恢复与来源Issue隔离、订阅及Inbox元数据排除、双workspace成员与游标绑定、只读来源可读历史/不可用评论隐藏、签名游标内容结构错误。另将候选查询改为数据库游标过滤、只取必要元数据并分批读取，避免一次加载整个工作区历史和原始请求body；20项专项保持通过。全量319项、迁移一致性及Django check通过；保护基线仅.gitignore允许差异。已更新模块文档，A3仍待资源别名和整批集成检查。

下一实施单元 A3-11：补齐现已实现能力的资源HTTP别名。`POST /api/v1/workspaces/{id}/issues`接收与issue.create相同的普通payload，workspace仅由URL选定；`POST /api/v1/issues/{id}/transitions`的body包含workspace_id、revision和转换字段，issue_id仅由URL选定。两者使用真实session身份、CSRF/Host校验、严格JSON及1MiB限制，Idempotency-Key和可选X-Confirmation-ID来自header；completed返回业务DTO，其他状态保留ActionResult。work/http只做传输映射并调用同一Registry一次，不复制业务策略或绕过当前授权；路径/body冲突或伪造身份字段拒绝。转换body的workspace_id和revision转为Actor工作区选择与expected_revision，其余字段加URL issue_id形成与通用入口相同的payload。遗漏可选字段保留遗漏语义，使两个入口共享同key参数hash、确认、CAS、结果和一次audit/outbox。普通业务操作仍不派发Run。资源Run/Delivery等能力尚未实现，不造空路由。此后父代理完成A3集成与根npm检查；涉及Review的归档保留验证待A4真实Review接入，不伪造事实。

**Files:** Create `services/workpal/workpal/work/{models.py,contracts.py,service.py,actions.py,migrations/0001_initial.py}`、`services/workpal/workpal/collaboration/{models.py,service.py,actions.py,migrations/0001_initial.py}`、`services/workpal/workpal/workflows/{models.py,service.py,actions.py,migrations/0001_initial.py}`、`services/workpal/tests/test_work.py`。

**Interfaces:** Consumes Registry/access；Produces `work.create_issue(actor,command)->IssueView`（title/project/criteria/assignee/source refs）、`work.transition(actor,issue_id,target,revision,reason=None)->IssueView`、`work.list_issues(actor,filter,cursor)->Page`；`collaboration.notify(event)->None`；`workflows.publish(actor,draft_id,revision)->WorkflowVersionRef`。本批 workflow 只实现状态、转换、review policy 不可变快照，图执行归 C2。

- [x] **Step 1:** 在各子单元与 `tests/test_work.py` 覆盖普通编辑不派发、依赖环/跨区、同名明确选ID、归档保留评论、Inbox已读不解决问题；仅产生本地业务outbox。Review尚由A4建立，归档保留真实Review的跨模块回归列入A4 Step 1，不用空表或假Review提前报通过。
- [x] **Step 2:** 各子单元记录实际缺失行为红灯及实现后的绿灯；`.venv-workpal/bin/python services/workpal/manage.py test tests.test_work --noinput` 作为最终双用户HTTP集成回归。监督补测若起始即绿，不追认为实现前红灯。
- [x] **Step 3:** 实现 Workspace/Project/Resource/Issue/Dependency/Comment/Notification 及配置动作，项目仓库引用先保存标识未验证状态；仓库真实性在 B4 确认。默认稳定 key：`backlog,todo,in_progress,in_review,done,blocked,cancelled`，对应 spec 生命周期分类；archive 独立可见性。创建 Backlog 不启动；Block 必有原因/责任人，解除不启动；人工 Done 需人、理由、项目完成策略。分页默认50，最大200；列表/看板同一 filter。
- [x] **Step 4:** 加不可变要求版本、历史事件、Inbox 已读、提及订阅及项目 Context；工作流变更不覆盖旧快照。复跑测试；查询/搜索/通知根据 `authorize` 过滤，不泄露不可见标题、摘要或计数。动作覆盖 CRUD/归档/恢复/评论/依赖/工作区切换/成员管理。
- [x] **Step 5:** 记录结果；保留建议提交说明 `feat: add projects issues and collaboration records`，本轮未执行Git提交或暂存。

A3统一验收（2026-11-20）：A3-11的13项HTTP测试外，父代理补9项专项，覆盖create/transition双向跨入口重放、精确要求/转换历史与audit/outbox/幂等唯一性、两个来源的当前write权限与撤权重放、共享owner跨区拒绝、custom/manual Done及默认完成证据门禁、输入矩阵、Host/CSRF/匿名停用与正向对照、审计后半段故障全表回滚及同key重试。22项专项全绿，无需修改别名实现。另新增2项真实会话双用户HTTP集成：同名项目/上下文和未验证仓库、要求追加、依赖、独立子任务、阻塞/通知/已读、工作流改绑、归档评论与历史、恢复和人工完成；来源撤销同步收窄Issue/Comment/Activity/Inbox及缓存重放。集成测试最初漏传当前project.update契约必填name，修正测试后通过，此失败不计作产品缺陷红灯。全量343项服务测试、迁移一致性、Django check通过；npm run check的102项Node测试、单HTML构建、2项原型后端测试通过，日志在/tmp/workpal-a3-npm-check.log。保护基线仅.gitignore既有允许差异。A3业务记录与协作范围验收完成；真实Review保留回归归A4，连接UI归A5，Runtime/外部系统仍未接入，不宣称首版完成。

### Task A4: 人工交付、证据与并发审核

**Files:** Create `services/workpal/workpal/delivery/{models.py,contracts.py,service.py,actions.py,artifacts.py,migrations/0001_initial.py}`、`services/workpal/tests/{test_delivery.py,test_artifacts.py}`；Modify `work/service.py`、`config/urls.py`。

**Interfaces:** `artifacts.begin(actor,metadata)->UploadRef`、`append(actor,upload_id,offset,chunk)->offset`、`finish(actor,upload_id,sha256)->ArtifactRef`；`delivery.submit(actor,subject,submission)->DeliveryRef`、`delivery.select_current(actor,delivery_id,revision,reason)->DeliveryRef`、`delivery.review(actor,delivery_id,version,revision,decision)->ReviewRef`。Submission 固定 criteria revision、artifacts、逐条证据、limitations、source `human|runtime`、可选 run/head；Decision 为 approve/request_changes+理由，approve 必须明确人决策身份。

A4-1实施约定：先实现delivery/artifacts深模块与四个元数据Registry动作，暂不做文件HTTP传输、Delivery/Review或完成状态门禁接线。接口为begin(actor,metadata)、status(actor,upload_id)、append(actor,upload_id,offset,chunk)->当前offset、finish(actor,upload_id,sha256)、read(actor,artifact_id)、read_chunk(actor,artifact_id,offset,length=256KiB)->bytes。metadata封闭为filename、media_type（默认application/octet-stream）、size和source_refs（默认[]）；普通文件单件上限25MiB，块上限256KiB。Upload及Chunk为暂存，只有完整大小与实际SHA256一致才原子产生Artifact；错误哈希/未完成保留暂存且不生成可引用产物。重复原offset同一块内容返回当前offset，内容冲突/跳位拒绝；同upload同hash完成重试返回同一Artifact。完成后清除暂存块，拒绝继续append。

逻辑Artifact与物理ArtifactBlob分离：Blob仅在workspace内按SHA256/size去重，Artifact每次上传独立身份、所有者与来源；相同字节不合并来源、不返回其他人Artifact或暴露复用标记/物理Blob ID。不同workspace不去重。Upload内容和状态仅当前上传者可管理/读取，owner/admin不绕过此所有权及来源权限；Artifact发布后按普通当前成员与全部来源read授权共享。来源注册在begin并由Artifact继承Upload，撤权即时生效。所有本地写与来源更新使用atomic_write；真实双连接验证offset竞争与完成去重。四个动作artifact.upload.begin/read/finish及artifact.read复用Registry，重放前复核上传者/来源，audit不记录文件块；bytes只走后续专用文件传输，不放入JSON ActionResult。

运行总量250MiB与原始日志90天保留在Run/日志接入时落实，A4-1不创建虚假Run或未使用的预算对象；A4后续Delivery引用会阻止证据被清理，清理/导出审计仍按D5完成。A4-2接授权文件HTTP传输与续传，之后才接人工Delivery、Review及A3归档保留回归。以上是实施依赖拆分，不削减首版范围。

A4-1首次交付未完成（2026-11-20）：仅新增test_artifacts.py的一项Registry行为测试，实际unknown_action红灯已记录/tmp/workpal-a4-1-red.log；未建立delivery实现。父代理核对文件及日志，保护基线仅.gitignore既有差异。343项是此前已验收基线，当前新增红测尚未转绿，不能报告当前全量通过。后续实施拆为A4-1a上传暂存/续传/权限与A4-1b哈希发布/产物读取，不改变上面的最终契约。

A4-1a只建立Upload、UploadChunk及begin/status/append深接口，注册artifact.upload.begin/read两动作并让现有红测转绿，补齐真实offset竞争与授权/回滚测试。此阶段Upload均为open，DTO中的artifact_id为0，尚无任何可引用Artifact；不创建空Artifact/Blob模型或假finish实现。A4-1b随后增加Artifact/Blob与Upload完成引用，接finish/read/read_chunk和另两动作，验证哈希、独立来源去重与并发完成。A4-1a不能代替完整A4-1验收。

A4-1a验收（2026-11-20）：子代理交付Upload/Chunk、begin/status/append及两Registry动作，12项独立测试。父代理补8项，实际回归发现直接服务越界upload_id误报404，统一按SQLite整数上界返回400；同时将metadata校验改为显式函数调用，去掉globals查找。补测覆盖封闭metadata、falsey来源值、重复块也需当前write、他人owner/共同跨区成员不能接管、全来源audit/outbox传播、来源/审计/块写入后半段故障全表回滚及同key重试、缓存begin与当前status偏移区别；并加强并发测试确认两条不同SQLite连接及有界barrier。专项20项、全量363项通过，迁移一致性/Django check通过，保护基线仅.gitignore允许差异。新增ID回归日志/tmp/workpal-upload-review-red.log记录真实失败；其他监督测试起始即绿。子代理除原Registry红灯外先实现后补测试的过程偏差保留，不追认完全遵守TDD。仍未发布Artifact、未接文件HTTP，不代表完整A4-1完成。

A4-1b接续边界：在现有Upload上新增可空完成Artifact引用（每次upload唯一），增加Artifact/ArtifactBlob并保留逻辑来源与物理去重分离。finish校验连续块/实际大小/哈希后在一个事务中发布、关联、清理暂存；错误保留原暂存。完成Upload的status返回completed及真实artifact_id，append明确拒绝；同upload同hash完成重试返回同一产物，仍复查当前上传者和来源。Artifact读取按workspace/current read，无owner绕过，metadata查询不加载BLOB，read_chunk仅取有界SQLite片段。artifact.upload.finish和artifact.read为薄Registry适配；finish为幂等写，read不写outbox。跨workspace不复用Blob；同workspace每次独立上传产生独立Artifact，只允许内部复用相同物理字节，不向客户端暴露复用结果或其他Artifact。文件HTTP、Delivery/Review和运行配额仍是后续任务。

A4-1b验收（2026-11-20）：子代理落地Artifact/Blob、完成引用、finish/read/read_chunk和两动作，但仅交付1项Registry红绿测试。父代理补17项回归，实际发现空文件SQLite substr返回None导致TypeError；在已授权及范围校验后明确处理EOF，修复后发布专项18项、含上传核心共38项通过。覆盖多块与二进制范围、空文件、未完/错hash保留暂存、同upload稳定身份、两个所有者及不同来源的内部Blob复用、跨区分离、只读成员与撤权/完成重放、发布后半段登记/审计回滚恢复暂存、已有Blob字节一致性、数据保护及审计不含内容；两实际连接同key仅一次发布，两个上传并发共享Blob仍保留两个Artifact。独立临时SQLite从含旧metadata/来源/偏移/块的0001迁移到最新，继续append并真实finish/read成功；未触碰开发库，此手动迁移检查不计入自动测试数。全量381项、迁移一致性/Django check通过，保护基线仅.gitignore允许差异。整理了动作注册入口和文档，A4-1存储核心验收完成，A4整体未完成。

A4-2文件HTTP传输约定：新增PUT /api/v1/artifact-uploads/{upload_id}/chunks?workspace_id=W&offset=N，接收最多256KiB的application/octet-stream，返回{upload_id,offset}；新增GET /api/v1/artifacts/{artifact_id}/chunks?workspace_id=W&offset=N&length=L，length默认256KiB，返回有界bytes及X-Artifact-Size、X-Artifact-SHA256、X-Next-Offset。两者真实session身份、Host、严格有界整数/无重复或多余query；PUT走CSRF，GET只读。返回no-store/nosniff，块内容始终octet-stream，不把文件名或不可信内容当响应头/HTML执行。metadata begin/read/finish继续经现有Registry；PUT是独立文件流传输，仅复用append的offset/bytes幂等，不增JSON base64动作或块级business outbox。文件生命周期审计由begin/finish保存。GET在同一个本地事务中执行Registry artifact.read及read_chunk，记录有完整来源的读取审计，不记录内容、不写outbox；后半段失败回滚读取审计。客户端按总size组装块并核验整件SHA256，用户下载交互在A5实现；此处不把单块当成完整下载。无HTTP前端、Delivery/Review或Runtime接线，仍需后续实施。

A4-2验收（2026-11-20）：子代理新增16项HTTP测试，父代理补8项监督测试。真实发现CSRF中间件提前拒绝时缺少no-store，最小修复公共csrf_failure后24项专项通过；覆盖多块二进制组装与整件哈希、EOF、严格query/Content-Length、未发布上传不可下载、共享owner跨区隔离、其他成员只读与逐块撤权、审计不包含内容，以及块写入/读取后半段失败的全表回滚和原offset重试。全量405项、迁移一致性、Django check通过；保护基线仅.gitignore既有允许差异。红绿日志/tmp/workpal-a42-review-{red,green}.log，全量/tmp/workpal-a42-reviewed-full.log。根npm留A4集成执行；本单元未接入UI、Delivery/Review或Runtime。

A4后续拆分：A4-3a先落地不可变人工Delivery提交、历史读取和授权分页；A4-3b再加入显式current/candidate选择与CAS；A4-4实现绑定具体提交和要求的Review、差异比较、完成门禁及归档保留回归。各阶段不提前返回尚未存在的审核/运行状态，不缩减最终A4范围。

A4-3a深模块边界：`delivery.service.submit(actor,subject:SubjectRef,submission)->DeliveryDTO`、`read(actor,delivery_id)->DeliveryDTO`、`list_deliveries(actor,subject,cursor=0,limit=50)->Page`。delivery拥有不可变版本、快照、来源继承、附件保留及本地事务；Registry只负责封闭schema与适配。依赖真实SQLite及work.issues/artifacts的in-process公开读取接口，不增加Repository层或网络。Subject沿用公共type/id字符串契约，存储subject_type/subject_id；本单元仅接受真实Issue，不为未来AutomationRun伪造Issue。ID必须规范正整数字符串且在SQLite范围内。

A4-3a提交契约：Registry `delivery.submit`接收`subject:{type:'issue',id:'…'}`、`requirements_revision`、必填非空summary（最多10000字符）、可选limitations（默认空，最多20000字符）、artifact_ids（默认空，最多100个唯一正整数）、evidence（默认空，最多100项封闭`{criterion_key,artifact_ids,note}`；note可省略为空且最多4000字符）、source_refs（默认空，最多50项）。criteria key必须存在于指定要求版本且不重复，每项证据artifact_ids必须是提交附件的唯一子集；允许不完整证据提交，由后续Review门禁阻止无证据批准。本阶段source固定human，仅executor_id为空的人类Actor可提交，不接受伪造source/run/head/测试通过或工具验证字段；文字说明和人工上传保持人工来源。

A4-3a持久化：每次提交一个Delivery，唯一(workspace,subject_type,subject_id,number)，number在IMMEDIATE事务内分配；保存提交人/时间、summary/limitations、指定要求的完整不可变快照（含真实要求id/number/hash）、Issue自身完整workflow_snapshot、附件metadata快照及逐条evidence。另用DeliveryArtifact的真实Artifact外键PROTECT保留证据，不仅保存JSON ID。内容SHA256使用UTF-8、sort_keys、紧凑JSON、禁止NaN，绑定subject、source、summary、limitations和上述四类快照；不含生成的Delivery ID/number/时间。历史read返回这些固定事实；list返回小摘要（id/number/subject/source/submitted_by/created_at/summary/requirements_revision/sha256），省略大快照/附件/evidence，授权后分页默认50最大200且无隐藏总数。此阶段不改变Issue的revision/状态/要求或创建Run/Review，也不输出current/approved等占位状态。

A4-3a授权与事务：Delivery注册为独立派生对象（不自行授予SourceGrant），继承Issue、指定要求版本、所有已发布Artifact及显式来源；提交需当前成员及全部来源write，读取需全部read。不得把消费者Issue权限反向追加到原始独立Artifact；在Issue内产生的上传应在begin时绑定Issue来源。尚未发布的Upload不是Artifact，不能作为证据。归档Issue拒绝新提交，但已完成幂等重放允许且仍复查人类身份和全部当前来源；历史仍可读。Registry `delivery.submit/read/list`使用同一深模块；submit需key，无确认/CAS，结果、来源、关联、audit/outbox同事务；read/list不写outbox。撤权在缓存重放前生效；列表scope必须包含实际展示的Delivery。双连接并发相同key只产生一次提交，两个不同key分配两个不同连续版本。

A4-3a实施与验证：先以真实Registry调用记录unknown_action行为失败（不能用缺失import当红灯），再实现最小提交；在对应修复前补行为测试并真实运行，保留未满足TDD顺序的事实。至少覆盖人工提交无Run/Issue变更、要求更新/项目改绑不修改历史、真实附件/证据关联和无效输入、全来源授权/撤权重放/共同成员跨区、授权分页、归档后的新提交与重放、附件PROTECT及快照副本、登记/审计后半段失败全表回滚与同key重试；两条独立SQLite连接验证相同key及版本分配。正常生成迁移；专项、全量、makemigrations --check --dry-run及Django check必须通过。保护哈希只允许既有.gitignore差异。根npm由父代理在A4集成时执行，当前验收不替代A4-3b或A4-4。

A4-3a首次实施未完成（2026-11-20）：子代理仅阅读，没有代码、测试或日志交付。父代理核对后新增test_delivery.py的一项真实端到端验收测试，使用已存在的项目/Issue/Artifact及Registry，失败于delivery.submit的unknown_action，日志/tmp/workpal-a43a1-red.log。此前405项绿灯仍为旧基线，当前新增红测尚未修复。为缩短单次实施范围，A4-3a1只实现submit/read、不可变存储/附件保留/权限/幂等，并补核心行为回归；A4-3a2接授权分页及完整并发、故障矩阵。两者共同完成才验收A4-3a，不删除前述合同。全量DTO字段固定requirements_snapshot、workflow_snapshot、artifacts_snapshot、evidence；canonical hash对象键固定subject/source/summary/limitations及这四项，不包含生成身份、版本和时间。

A4-3a1验收（2026-11-20）：子代理完成submit/read、Delivery及DeliveryArtifact正常迁移，原端到端unknown_action红测转绿，补4项核心测试起始即绿。父代理另补8项监督测试，真实发现直接Interface的SubjectRef/提交类型及来源长度/Unicode验证不完整，另有返回evidence嵌套列表与调用输入共享引用；修复严格类型/长度和DTO独立副本，并对齐Registry整数上界。其余回归证明归档后的历史读/既成重放与新提交拒绝、DeliveryArtifact自身PROTECT（排除Upload保护遮蔽）、全来源audit/outbox且不反向收窄原Artifact、共同成员跨工作区拒绝、来源注册/附件插入/审计写入后半段503全表回滚与原key重试。专项13项、全量418项通过；迁移一致性、Django check通过，保护基线仅.gitignore既有允许差异。日志/tmp/workpal-a43a1-review-{red,green}.log及/tmp/workpal-a43a1-reviewed-full.log；初次红灯内另有测试断言作用域的次生异常，已修正，不计作产品缺陷。A4-3a1核心验收完成，A4-3a整体仍待后续。

A4-3a2实施单元：增加`service.list_deliveries(actor,subject,cursor=0,limit=50)`及`delivery.list`薄Adapter。subject读权限先检查，再按workspace/subject/id游标取候选；对每个候选当前完整来源read过滤后分页，隐藏行不消耗limit、不暴露总数或标题。默认50最大200，cursor为有界非负整数；仅取摘要列及requirements_snapshot.number，不把附件/evidence/完整workflow等大JSON加载后再丢弃。Page为items和next_cursor，摘要字段已由A4-3a约定固定。Registry输出refs包含主体与实际展示Delivery，访问审计保留这些来源且不写outbox；仅403/404当不可见，503不能伪装空列表。读不要求human executor，submit保持human限制。

A4-3a2验证：新增真实Registry list缺失行为红灯后实现；验证隐藏行前/中/尾的授权分页、空页/末页、只读来源、Issue/Artifact/要求独立来源撤销、跨workspace/subject隔离、严格cursor/limit/subject输入、审计scope和大JSON未选入。另补两条不同SQLite连接同key只生成一次Delivery/附件/audit/outbox/幂等行、不同key生成连续两个number；Barrier必须有超时且确认连接不同、finally关闭连接。补项目工作流改绑不修改Issue/Delivery历史、成员撤销/停用、post-audit幂等保存故障的完整回滚与同key重试，并按既有测试只补真实缺口，不重复已经验证的三处故障。保留父代理现有13项断言，不为绿灯降低权限或快照约束。专项/全量/迁移检查/Django check和保护基线全部通过后交父代理验收；此单元不涉及current/candidate、Review、状态或HTTP别名。

A4-3a2验收（2026-11-20）：子代理仅新增list实现和1项Registry红绿测试，未完成整单元。父代理补11项分页/授权/集成回归及2项真实双连接测试；发现resolver和handler重复扫描候选历史，改为共享严格subject解析和独立subject_refs授权解析，候选查询只执行一次且不加载大快照。其余监督测试起始即绿：隐藏前/中/尾、只读executor、要求/产物来源独立撤销、主体与workspace隔离、严格输入、完整读取审计、503不伪装空页、撤成员/停用账户、项目改绑保留历史、幂等保存真实插入后失败全表回滚；两个不同连接同key仅一份Delivery/附件/audit/outbox/幂等行，不同key产生连续两版本且Issue/要求不变。Delivery专项27项、全量432项、迁移一致性及Django check通过；保护基线仅.gitignore允许差异。日志/tmp/workpal-a43a2-review-{red,green}.log及/tmp/workpal-a43a2-reviewed-full.log。A4-3a不可变人工提交与读取范围验收完成，A4仍待当前选择、Review和集成；根npm留A4整批验收。

A4-3b实施设计：保持Delivery不可变，另设每subject一条可变DeliveryCurrent及不可变DeliverySelection历史。所有新增提交先是候选；只有明确的人类选择才改变current，后来的提交不覆盖。既有数据不回填虚构选择。无选择时current.read返回真实空状态`{subject,revision:1,current_delivery_id:0,current_delivery_number:0}`且不写状态表；1是已定义的初始CAS版本，首次选择成功创建revision=2的状态。后续每次选择CAS递增；不同key对同一revision只能一次成功，同key重放仍返回原动作快照，不回拨当前指针，当前情况另用current.read获取。候选是与当前ID比较得出的角色，不在Delivery中添加可变flag，也不改变现有list/read的不可变DTO。

A4-3b1深Interface：`selection.current(actor,subject:SubjectRef)->CurrentDTO`及`selection.select_current(actor,delivery_id,revision,reason)->CurrentDTO`，薄Registry动作`delivery.current.read`（subject）与`delivery.select_current`（delivery_id、必填非空reason最多4000字符，expected_revision必填正整数）。选择无额外确认token，明确人类Actor及具体目标/reason/CAS构成操作；executor_id非None拒绝包括重放。当前读取允许有权限的executor。选择需当前subject、目标Delivery及已有current Delivery全部write；读取需subject和实际current Delivery全部read。归档Issue只禁止新选择，历史读与已完成重放仍复查当前权限后允许。旧要求的Delivery可以选为current，但不能绕过后续Review对当前要求的门禁。本单元不自动转换Issue状态或修改Issue revision，不制造Review/Run。

A4-3b1存储与来源：DeliveryCurrent以(workspace,subject_type,subject_id)唯一，保存current_delivery的PROTECT外键和revision；DeliverySelection追加保存current行引用、before_delivery可空和after_delivery的PROTECT外键、该次结果revision、操作者、reason、时间，唯一(current,revision)。选择必须在同一atomic_write中完成CAS、历史、来源、Registry result/audit/outbox，任何后半段失败全部回滚。可变指针仅是内部并发状态，不注册为可被正文继承的来源对象；避免返工的Review/新Delivery再选为current时产生来源循环。每条不可变Selection注册为派生对象，继承subject及真实before/after Delivery，保留切换理由的完整权限。current.read仅返回当前ID/number/subject/revision，输出refs为subject及当前Delivery；它不披露旧目标或reason。选择结果refs还包含本次Selection，审计和缓存保留before/after及所有来源；历史列表后续按每条Selection权限过滤，不能通过指针改向放宽旧事件/缓存权限。

A4-3b分工：先由GPT 6.1 Sol完成b1两Interface、状态/历史模型、正常迁移及核心测试（空状态无写入、明确选择、后到候选、CAS、重放、人类及来源限制）。b2补选择历史读取和完整并发/故障矩阵，随后进入A4-4。父代理保留独立验收；本阶段所有已有Delivery测试必须继续通过，不能为新增状态字段修改其固定DTO或放松来源权限。

A4-3b1验收（2026-11-20）：子代理交付两Interface、Current/Selection模型和正常迁移，4项核心测试；真实红灯仅覆盖current.read，未声称select_current单独先红。父代理补9项监督回归和3项真实双SQLite连接测试，发现current元数据读取懒加载整个Delivery快照，改为仅选择身份/版本列后转绿。其余起始即绿：目标及原current双方write、改向公开不泄露旧私有理由/缓存、返工继承不可变Selection无来源环、归档新选择拒绝与历史重放、共同成员跨区、严格输入/冲突、首次来源登记及后续历史/审计/幂等保存后半段失败全表回滚、历史FK保护旧Delivery。两条不同连接同key只一次，两个首次或后续不同key竞争同revision均一成功一409，精确audit/outbox/幂等行只有一次。选择专项16项、全量448项、迁移一致性/Django check通过；保护基线仅.gitignore既有差异。日志/tmp/workpal-a43b1-review-{red,green}.log及/tmp/workpal-a43b1-reviewed-full.log。核心与竞争/写失败范围验收完成，b2尚需选择历史读取；A4整体及Review仍未完成。

A4-3b2实施约定：只增加`selection.list_history(actor,subject,cursor=0,limit=50)->Page`及薄动作`delivery.selections.list`，输入subject/cursor/limit与Delivery列表同一严格范围。先检查subject当前read，不要求当前指向Delivery可读；随后按workspace/subject与id游标筛选不可变Selection，逐条完整来源read授权后分页。当前目标变为私有时，仍可以看到自己有权读的早期公开历史；不能因为能读当前公开目标就读取旧私有reason。403/404隐藏，503传播。返回items/next_cursor，无隐藏总数；每项固定id、subject、revision、before_delivery_id（首次0）、before_delivery_number（首次0）、after_delivery_id、after_delivery_number、actor_user_id、reason、created_at。版本号来自各事件自己的before/after不可变Delivery，不通过当前指针重建。仅取事件元数据/reason与两个Delivery number，不加载完整交付快照。Registry resolver仅授权subject，不重复扫描；结果refs为subject和实际展示的Selection，审计保留所有展示来源且无outbox。无选择时空页，不创建指针或历史。

A4-3b2测试先记录真实Registry unknown_action红灯，随后覆盖不可变前后版本与理由、公开/私有事件混排分页、当前目标私有仍可读旧公开历史、改向公开也不放宽旧私有事件、read-only/executor、撤源、归档、跨subject/workspace、严格输入、503完整访问审计回滚和元数据查询。父代理已在b1监督阶段补齐选择竞争与写失败矩阵，本单元无需重复或改写这些测试。完成专项/全量/迁移一致性/check和保护基线后交监督验收；不提前接Review或Issue完成。

A4-3b2验收（2026-11-20）：子代理完成历史Interface/薄Registry与7项测试，记录真实unknown_action红灯。父代理另补5项均起始通过，无需实现修复：私有事件前中尾混排、当前私有仍可见旧公开历史、改向公开不放宽旧理由、精确输出refs/审计scope、真正只读executor及归档后撤源、同用户多workspace/多subject隔离、实际访问审计写入后503全表回滚、subject非法输入及空态不建指针。历史专项12项、全量460项、迁移一致性/Django check通过；保护基线仅.gitignore既有允许差异。日志/tmp/workpal-a43b2-review.log及/tmp/workpal-a43b2-reviewed-full.log。A4-3b当前选择与历史范围验收完成；Review及A4集成仍未完成，根npm留整批执行。

A4-4实施拆分：a先实现真实不可变Review的决定与单条读取，b接授权历史/差异数据和完整并发故障验证，c将approved_delivery完成门禁接入Issue并补归档保留Review集成，d补Delivery/Review资源HTTP别名与A4整批验收。approved_head_merged在没有B4已验证head/合并事实时继续拒绝完成；本阶段不虚构工具执行或提供方事实。

A4-4a深Interface：`review.review(actor,delivery_id,version,revision,decision)->ReviewDTO`、`review.read(actor,review_id)->ReviewDTO`，Registry为`delivery.review`（delivery_id、version、decision；expected_revision来自当前DeliveryCurrent）与`review.read`（review_id）。decision封闭为outcome（approve/request_changes）、必填非空reason最多4000字符、可选source_refs默认[]最多50项；来源kind/id和UTF8边界沿用现有约定。只有executor_id为空且当前Membership.role属于该Delivery已保存workflow_snapshot.review_policy.reviewer_roles的用户能作出任一决定，重放前也检查。读取只需当前成员和全部来源read，不要求reviewer角色或human。动作需key及正整数revision，无另一个确认token。

A4-4a决定门禁：version必须精确匹配Delivery.number；新决定必须针对实际current Delivery并匹配当前revision，归档Issue拒绝新决定。approve还要求Delivery固定要求的id/number/hash与Issue当前要求一致，有至少一条验收criteria，每个criterion均有至少一个已发布Artifact作为证据，不能用空artifact_ids的文字note代替。重新读取提交附件metadata核对id/size/sha256及证据引用属于manifest，复用已经完成实际哈希发布的Artifact，不在写事务中重复扫描所有BLOB。request_changes允许证据不全或要求已更新的当前提交，以保存真实返工理由。两种决定都需要subject、Delivery、被评审要求和显式来源的全部当前write；批准不转换人工来源为工具证据，也不声称测试命令执行/PR已合并。代码完成仍需未来独立门禁。

A4-4a持久事实：新增Review模型，保存workspace、Delivery及DeliveryCurrent的PROTECT引用、version、该次结果revision、delivery_sha256、requirements_snapshot、workflow_snapshot、outcome/reason、actor、created_at；唯一(current,revision)。ReviewDTO固定id、subject、delivery_id、version、revision、delivery_sha256、requirements_snapshot、workflow_snapshot、decision:{outcome,reason}、actor_user_id、created_at，全部为独立不可变快照。subject取关联Delivery的固定type/id，不从current目标重建。只推进DeliveryCurrent.revision（保持目标ID），然后追加Review并注册派生ObjectRef('review',id)，来源为subject、该Delivery、被评审要求与显式来源；不继承可变指针，也不额外写Selection事件。CAS、Review/来源、Registry result/audit/outbox同事务，任何失败全回滚。审计仅安全delivery_id/version等字段，不记录reason或证据原文。

A4-4a重放与后续有效性：resolver只做当前身份/角色/来源和固定输入校验；current是否仍指向目标、CAS、归档、要求/证据等新执行门禁放handler，避免把历史幂等结果当成新决定。相同key返回原Review，不再次推进revision；当前情况另用current.read。后续有效批准必须匹配当前Delivery及其hash、当前要求和当前状态revision；新选择、新决定或要求修改均不能沿用旧批准。旧Review继续保留并按当前来源授权读取，列表不能退回使用较早可见approve冒充最新有效决定。完成门禁与授权历史在后续单元实现，不在a阶段返回虚构的有效批准/Done状态。

A4-4a最小验证：先真实Registry缺失行为红灯再实施；覆盖真实产物+逐条证据的人工approve、note-only/缺criteria阻止approve、request_changes保留不完整提交理由、version/current/revision/新要求冲突、人类及快照reviewer角色、幂等后原Review不变、只推进Current revision且Issue/Delivery/Selection不变。使用真实SQLite和现有无测试Fixture；正常生成迁移，专项/全量/迁移漂移/check和保护基线通过再交监工。完整两人竞争、后半段失败、来源与自定义策略矩阵及历史分页由b及父代理补足；不得将人工评审记录当作执行测量。

A4-4a验收（2026-11-20）：子代理落地Review模型、决定/read和正常迁移，6项独立测试；首条真实unknown_action红灯，其余实现后补测未追认TDD。父代理另补12项校验/集成和3项真实双连接测试，发现catalog未声明ID上下界及Review读取重复加载Delivery大快照，修正后通过。其余起始即绿，验证逐条证据与真实空criteria、附件metadata不匹配、要求更新后拒绝新批准而保留旧记录、自定义member reviewer无owner绕过且不受项目改绑重写、私有Review来源/缓存隔离、跨workspace/撤成员/停用、严格输入、Review/来源/审计/幂等四阶段真实写入后失败全表回滚、返工继承Review无环及归档保留真实Review。两个独立连接同key只一次、两名人类竞争只接受一决定、Review与选择共用revision只一方成功；精确audit/outbox/幂等行及Issue不变均通过。Review专项21项、全量481项、迁移一致性/Django check通过；保护基线仅.gitignore既有差异。日志/tmp/workpal-a44a-review-{red,green}.log及/tmp/workpal-a44a-reviewed-full.log。决定核心验收完成，不代表批准有效性、完成门禁或A4整体完成。

A4-4b进一步拆为b1审核历史、b2提交差异数据；核心并发/故障矩阵已由父代理在a验收补足，不重复扩张。b1新增`review.list_reviews(actor,subject,cursor=0,limit=50)->Page`与`review.list`薄Registry动作，subject/cursor/limit复用严格范围（默认0/50、最大200）。先subject read，再按workspace及Review关联Delivery的固定subject筛选历史、id游标排序，逐条Review完整来源read过滤后分页；不能要求当前Delivery或最新Review可读，不能借公开current放宽旧私有reason。403/404隐藏，503传播，无隐藏总数；空页不建业务记录。

A4-4b1摘要固定id、subject、delivery_id、version、revision、delivery_sha256、requirements_revision、decision:{outcome,reason}、actor_user_id、created_at。所有值来自Review保存的事实及其不可变Delivery身份；requirements_revision仅取Review.requirements_snapshot.number的JSON投影，不加载大快照后丢弃，不通过Current或Issue当前要求重建。resolver只subject授权、不扫描候选；输出refs包含subject及展示Review，访问审计保留这些来源且无outbox。读取允许只读成员和executor，不套用写决定的reviewer_roles。结果不包含is_current/effective/approved等动态结论；历史中可见的较早approve不能代替被隐藏的更新决定，完成门禁仍须走后续独立接口。

A4-4b1验证：先Registry缺失行为红灯，覆盖跨提交的不可变历史、旧/新要求revision、私有事件前中尾分页、最新Review或current私有仍可读旧公开历史、改向公开不放宽旧私有理由、只读executor与归档/撤权、workspace和subject隔离、严格输入、来源/审计scope无outbox、503及实际读取审计写入后的完整回滚、一次摘要查询不加载快照。保留现有全部测试；正常专项/全量/迁移一致性/check/保护基线后交父代理，暂不加入差异算法或Issue完成。

A4-4b1验收（2026-11-20）：子代理交付review.list_reviews/薄Registry及5项测试，真实unknown_action红灯已转绿。父代理补6项均起始通过，无需实现修复：跨Delivery与要求版本的固定历史、私有current/最新决定与旧公开历史隔离、精确refs/审计scope及改向公开不泄露旧理由、归档只读executor后按Artifact和subject分别撤权、共同成员跨workspace/subject、lookahead授权503不返回部分页且全表无写入、严格subject输入与空页不建业务记录。历史专项11项、全量492项、迁移一致性/Django check通过；保护基线仅.gitignore既有允许差异。日志/tmp/workpal-a44b1-review.log及/tmp/workpal-a44b1-reviewed-full.log。审核历史范围验收完成，不代表有效批准或Issue完成门禁已经接通。

A4-4b2深Interface：`comparison.compare(actor,before_delivery_id,after_delivery_id)->ComparisonDTO`，只读Registry `delivery.compare`接两个有界正整数ID。两份Delivery必须属于actor当前workspace及同一subject，先对两边完整当前来源read授权后才返回任何比较数据；不同subject拒绝409，缺失/跨区沿用404，不允许部分披露。允许同ID及反向比较，只读成员/executor也可使用。读取双方已经保存的不可变快照，不从Issue/Project/Artifact当前配置反推历史，不读BLOB、不请求模型/Git/网络，也不生成执行、合并或审批有效性的结论。

A4-4b2输出固定subject、before、after、text_changes、criteria、artifacts、evidence、workflow_changed。before/after各为id、number、sha256、requirements_revision、requirements_sha256、workflow_sha256。text_changes仅列真实变化，按summary、limitations、requirements.title、requirements.description固定顺序，每项{field,before,after}保留原文本。criteria按key、artifacts按逻辑id、evidence按criterion_key匹配；每组返回added、removed、changed、before_order、after_order，added按after顺序、removed按before顺序、changed按after顺序；changed项为{key或id或criterion_key,before:完整原项,after:完整新项}。原项分别为已保存的criterion {key,text}、Artifact metadata DTO、evidence {criterion_key,artifact_ids,note}。同名或同hash的不同逻辑Artifact仍为不同引用，不合并来源；同key内容不同才列changed，纯重排只体现在两个order数组。workflow_changed为完整已保存workflow_snapshot是否不同；其具体内容仍从Delivery.read查看。返回独立副本，不把文字“测试通过”的变化升级为工具事实。

A4-4b2内部实现只需一条读取Interface和私有的按key比较函数，不引入通用JSON diff框架或Repository。Registry resolver用轻量身份/subject查询与来源授权，不先读取两份完整快照再让handler重复加载；结果refs包括subject与双方Delivery（去重），访问审计保留来源并只写两个ID，无outbox/业务写/新Comparison模型。严格封闭输入/输出schema，现有100项集合边界继续生效。

A4-4b2验证先以真实Registry缺失红灯开始，覆盖文本/criteria/附件/evidence增删改与顺序、同ID零差异和反向比较、同字节不同Artifact身份、要求继续更新/项目改绑不改变历史比较、双边来源撤权与只读executor、同用户跨workspace及跨subject拒绝、严格ID/额外字段、快照副本、完整审计scope无原文、后半段读取审计失败回滚和查询不读BLOB/不重复快照。专项/全量/迁移一致性/check/保护基线通过后交监工；批准有效性与Issue完成仍归A4-4c。

A4-4b2验收（2026-11-20）：子代理交付比较Interface、薄Registry和11项测试，真实unknown_action红灯后转绿。父代理将原私有函数重排测试替换为真实提交及Registry比较，将直接改Issue项目外键的测试替换为真实工作流发布/项目绑定；另补3项监督测试。14项专项通过，覆盖要求/文本/证据增删改和顺序、相同字节的不同Artifact身份、反向/同ID比较、返回值嵌套副本、两侧独立来源及只读executor、跨工作区混合请求不返回部分数据、精确审计来源且无outbox。附件metadata按已发布逻辑Artifact保持不可变，公开上传产生新身份，测试不伪造同ID可编辑附件。全量506项、迁移一致性/Django check通过；保护基线仅.gitignore既有允许差异。日志/tmp/workpal-a44b2-review.log及/tmp/workpal-a44b2-reviewed-full.log。监督补测起始即绿，不追认为实现前红灯。差异数据范围验收完成，A4整体尚未完成。

A4-4c拆为c1当前批准有效性读取、c2接入Issue完成门禁，随后补Delivery/Review资源HTTP别名和A4集成验收。先实现c1，保持状态转换的现有行为。深Interface为`approval.inspect(actor,subject)->(ApprovalDTO,scope_refs)`，把当前指针、精确Review、要求身份与来源校验藏在delivery模块内；Registry只注册只读`delivery.approval.read`，输入为subject。使用真实本地SQLite和已有事务机制保证一次检查内读取一致，直接Interface调用也具备这个边界；不新增模型、迁移、缓存批准标记、Repository或通用策略框架。

A4-4c1输出固定subject、status（approved|not_approved）、reason（approved|no_current_delivery|review_required|changes_requested|requirements_changed|submission_changed）、current_revision、current_delivery_id、current_delivery_number、review_id、review_revision、requirements_revision、completion_policy。无current时revision=1，目标及Review的ID/number/revision为0；有current但该revision没有Review时Review两字段为0。requirements_revision取Issue当前真实要求number；completion_policy取Issue自己保存的工作流策略，不读取Project最新绑定。此输出只判断人工批准有效性，不输出can_complete、merged或tests_passed；即使approved且策略为approved_head_merged，也不代表代码已完成。

A4-4c1判断顺序：先当前成员及subject read，再明确授权当前要求ObjectRef，才可披露要求revision。无current返回no_current_delivery，不扫描候选提交或审核历史。有current必须授权实际目标Delivery全部read来源，只取必要身份、hash及JSON路径元数据。只查询该Current且`Review.revision == Current.revision`的精确决定；不存在返回review_required，不能退回较早可见approve。存在则先授权该Review，隐藏的最新决定直接拒绝，不返回部分DTO或把它伪装为未审核。核对Review与current Delivery的id/version/sha256/工作流hash，错配返回submission_changed；request_changes返回changes_requested。approve还须Delivery和Review的要求id/number/sha256均匹配Issue当前要求；不匹配返回requirements_changed，即使文字改回原样也不能复用旧要求身份。全部吻合才approved，未知决定或不一致事实保持不批准。

A4-4c1权限及来源：允许当前只读成员和executor读取，不将写Review的human/reviewer角色门禁套用于读取。历史决策保留作出时的真实身份，不因读取者不是reviewer而隐藏其已获准材料；每次读取仍检查当前成员及每一来源。scope_refs返回subject、当前要求、实际current Delivery及命中的精确Review（按存在去重）；Registry输出和访问审计保留这些来源，审计字段仅subject，无outbox/幂等结果/业务状态写入。resolver只做subject授权，复杂读取集中在Interface；不加载Delivery/Review的大快照、附件或BLOB，不重复做产物哈希扫描，不调用模型/网络。

A4-4c1验证：先真实Registry unknown_action行为红灯，至少覆盖无current→已选未审核→退回→批准的真实路径、同目标重选和新决定令旧批准失效、要求更新及改回仍失效、项目工作流改绑不重写策略；最新私有Review拒绝且不回退旧公开批准、独立当前要求来源、只读executor/撤权/工作区隔离、严格subject和闭合输出、完整审计scope及无业务写入、读取授权503和审计后半段失败全表回滚、metadata查询不加载大快照。通过公开Interface/Registry构造事实，复用无test方法的Fixture，不继承测试类造成重复计数。运行专项/全量/迁移一致性/check和保护基线后交监工；不提前修改Issue转换、资源HTTP、Runtime或外部系统。

A4-4c2后续接线约束：manual保留人类/理由/快照角色/依赖门禁；approved_delivery使用c1结果并在同事务复查当前write及完成条件；approved_head_merged在B4取得真实已批准head合并事实前继续拒绝Done。Review不会自动转换Issue。新转换要保存真实审批依据并继承来源，不能直接将Review作为Issue来源而形成Review→Delivery→Issue环；沿用来源根集合和独立转换历史保存依据的具体接口，在c1验收后细化。幂等历史成功结果保持历史快照，新的当前完成判断仅在新执行时发生，不以旧结果冒充当前批准。

A4-4c1验收（2026-11-20）：子代理交付approval.inspect、薄Registry及10项独立测试，首条真实unknown_action红灯，其余实现后补测。父代理补10项监督测试，真实发现公开输出schema缺少completion_policy枚举和整数边界，复用workflow策略schema并补足边界后20项专项通过。其余覆盖最新私有Review拒绝且不回退旧批准、独立当前要求来源、要求改回相同hash仍因新身份失效、项目重绑保留Issue策略、私有未选候选不干扰批准、只读executor/跨区/撤源/撤成员/停用、准确输出及审计来源、直接读取无业务写入、授权503及真实审计写入后失败全表回滚、SQL只读Delivery/Review必要JSON路径、不一致持久决定不批准。全量526项、迁移一致性/Django check通过；保护基线仅.gitignore既有差异。日志/tmp/workpal-a44c1-review-{red,green}.log及/tmp/workpal-a44c1-reviewed-full.log。c1验收完成，尚未接通Issue完成，A4不整体勾选。

A4-4c2实施Interface仍为`transitions.transition(actor,issue_id,target,revision,reason='',blocked_owner_user_id=0)->IssueDTO`，Registry输入及IssueDTO保持不变。完成判定集中在work/transitions调用delivery/approval.inspect，不能由HTTP或调用方传入approved/Review ID来绕过。新执行必须先满足真实Issue CAS、自己的工作流允许边及Done category的人类/快照reviewer角色/非空理由；manual沿用原有行为，approved_delivery要求inspect.status为approved并对返回全部scope_refs授权write，approved_head_merged仍返回completion_not_ready 409。所有Done还须无未完成依赖；inspect的403/404/503原样传播，未获有效批准为completion_not_ready 409。保留自定义状态key，不能写死target=='done'。不因批准自动转状态，不增加Run或外部调用。

A4-4c2持久依据：IssueTransition新增可空`completion_review` FK到delivery.Review（PROTECT）与`completion_snapshot` JSON（default=dict），正常生成work迁移并依赖现有delivery Review迁移；旧历史和manual/非Done记录保持null/{}。approved_delivery完成时，在同事务保存真实Review FK及inspect返回的小DTO独立副本；已有requirements_version和workflow_sha256继续固定本次Issue要求/工作流。历史读取仅对有依据的项追加可选`approval`字段，值为保存的小DTO；其他历史不添加该字段，closed schema的该属性可选但若存在必须完整符合批准读取DTO。后续current选择/决定/要求改变不重建或改写历史批准依据，当前有效性仍单独用c1读取。Review和其Delivery不能因删除而留下悬空完成依据。

A4-4c2来源：完成前从inspect返回refs通过derive_scope取实际根来源，先当前write授权，再追加到Issue注册对象并复查已有assignee仍可read。来源只追加；不能将依赖Issue的Review/Delivery/requirements对象直接追加给Issue而造环。不可变Transition本身继承Issue和此次inspect的完整refs，以保留真实决定/产物的动态授权及根来源。任何来源环、授权/负责人检查失败均回滚全部变化。历史来源图未使用可变Current指针。只需现有access Interface，不增权限框架。新完成Registry结果仍返回IssueDTO，但object_refs按Issue在前加上本次不可变Transition，供幂等结果、访问审计和业务outbox固定批准依据；可以复用已有selection Adapter按subject/revision定位刚保存历史的模式。manual及普通转换保持现有结果refs。

A4-4c2重放与事务：resolver保留当前human/reviewer角色及Issue当前write检查，不在resolver执行新的批准/状态/CAS判断；这些新执行门禁在handler事务内。合法旧key重放返回原IssueDTO及原Transition引用，不重复写历史、不把旧Review应用到新要求；缓存仍复查当前Issue与保存的完整来源。来源追加、Issue CAS、Transition/FK/快照、Registry结果、审计和outbox在同一个atomic_write事务，任一步失败全部回滚。父代理将补真实并发：同Issue revision只能一次转换；与新要求竞争符合Issue CAS；与新Review/选择竞争按数据库提交顺序判断，不伪造跨两个不同revision的“一定只有一个成功”规则，已提交的历史转换不会因后来的决定被追溯改写。

A4-4c2文件范围：修改`work/models.py`、`work/transitions.py`、`work/issue_actions.py`、work与服务README；新增正常work migration及`tests/test_completion.py`（需要可加独立并发测试文件）。不修改approval/Review/Artifact行为、Registry核心、HTTP、旧原型或其他计划。旧测试除确因新授权能力需要调整的精确断言外不得弱化；先向监工报告该断言。

- [x] A4-4c2先写真实人工批准的approved_delivery自定义Issue经Registry完成测试，观察当前completion_not_ready红灯；不要以缺失model/import代替行为失败。
- [x] 实现最小完成门禁、来源传播、真实FK/不可变依据和薄Adapter；正常生成迁移。
- [x] 验证新批准可完成、无批准/退回/换目标/新要求拒绝、默认代码策略仍拒绝、manual保留、human/快照角色/理由/依赖和当前write门禁；验证完成来源无环、负责人隔离、历史依据及幂等唯一性、后半段失败回滚。不要伪造执行或合并事实。
- [x] 运行专项、全量、迁移漂移、Django check和保护基线核对，记录真实红绿；完成专项竞争由父代理补验，根npm与A4集成仍留整体批次。禁止自动Git提交。

A4-4c2验收（2026-11-20）：子代理交付完成门禁、真实Review FK、保存的批准小快照及正常迁移，9项独立测试。首个fixture漏掉绑定确认曾误入invalid_transition，修正fixture后才观察真实completion_not_ready红灯并实现，未将fixture错误计作产品红灯。父代理新增7项校验与5项真实双SQLite连接测试，均起始即绿，无实现修复：manual和默认代码策略、人类/快照角色/理由/依赖及伪造参数拒绝、私有Review写权限、Issue/既有Comment/Transition动态根来源且无环、准确audit/outbox/cache范围、真实FK删除保护、要求/决定变更后的历史快照和重放、来源/历史/cache实际写后故障全表回滚、来源环与共享成员跨区。两个连接同key仅一次，两个用户同Issue revision仅一次，新要求与完成遵守CAS，新审核/新选择与完成遵守事务提交顺序，完成依据始终是执行当时真实Review。专项21项、全量547项、迁移一致性/Django check通过；保护基线仅.gitignore既有差异。日志/tmp/workpal-a44c2-review-final.log及/tmp/workpal-a44c2-reviewed-full.log。完成核心验收通过，A4仍需资源别名与整体HTTP/npm验收。

A4-5资源HTTP别名实施约定：新增`POST /api/v1/issues/{issue_id}/deliveries`和`POST /api/v1/deliveries/{delivery_id}/reviews`，分别只做`delivery.submit`和`delivery.review`的传输映射。新增`delivery/resource_http.py`，既有`delivery/http.py`继续专管文件块。使用真实session Actor、Host、CSRF、现有严格JSON/1MiB上限；拒绝额外query、非JSON、重复JSON key、非有限数及非法Unicode。只调用一次Registry，不复制授权、证据、CAS或事务业务规则，不直接调用submit/review服务写入。

A4-5创建body包含workspace_id以及delivery.submit除subject以外的字段（requirements_revision、summary及可选limitations/artifact_ids/evidence/source_refs）；subject只由URL构造为issue及规范十进制ID，body带subject或issue_id一律拒绝。workspace_id只选择真实会话用户所在工作区，不能替代成员或来源授权；submit不接revision。Review body包含workspace_id、revision、version、decision；delivery_id只由URL提供，body同名字段拒绝。revision映射expected_revision；version仍表示固定Delivery.number，不能混同Current revision。路径对象ID、workspace_id与revision均须exact int、拒绝bool、正数并受SQLite边界约束；对象ID使用1..MAX-1，transport workspace/revision沿用现有通用入口1..MAX，业务Interface可继续收窄。未知字段（含user_id/executor_id/approved等）由封闭schema拒绝，不能丢弃。

A4-5两路由都要求Idempotency-Key header；可选X-Confirmation-ID只原样映射确认字段，不伪造确认或改动现有动作确认策略。保留可选字段的原始遗漏语义，使普通入口与别名双向重放使用完全相同payload hash、key和revision，只产生一次业务事实/audit/outbox/幂等行。completed返回业务DTO；其他状态保留ActionResult。复用现有DomainError序列化及脱敏500，响应加no-store，CSRF中间件拒绝沿用现有全局no-store。无登录/会话机制重写，无自动选择、批准或完成；AutomationRun尚未实现，不加空别名。

A4-5文件范围：新增`services/workpal/workpal/delivery/resource_http.py`、`services/workpal/tests/test_delivery_aliases.py`；修改`config/urls.py`仅追加两路由，以及delivery/服务README。先真实HTTP 404红灯，再实现；使用Django Client(enforce_csrf_checks=True)、真实会话和SQLite业务，复用无test方法Fixture。测试至少包括两路由成功、generic→alias及alias→generic重放/精确唯一性、changed payload和stale revision 409、权限和撤源重放拒绝、共享成员跨workspace、body/path冲突和整数/字段矩阵、Host/CSRF/匿名/停用正反对照、坏JSON/过大body/query/method、实际审计后失败全表回滚和同key重试。专项/全量/迁移/check/保护基线通过后父代理再进行A4多用户HTTP闭环及根npm验收。

- [x] **Step 1:** 各子单元测试覆盖人工提交、缺证据拒绝批准、两人同revision竞争、新要求使旧批准失效、晚到提交仅候选、未完成上传不能作为证据，并完成真实Review归档保留回归。Agent批准403；人工HTTP闭环的outbox无Run/Runtime派发命令，不用尚不存在的Run表伪造计数证明。
- [x] **Step 2:** 各子单元记录真实Registry/HTTP行为红灯及后续绿灯，监督补测起始即绿如实记录；最终通过全部服务测试及多用户HTTP闭环。
- [x] **Step 3:** 已实现SQLite BLOB分块、25 MiB/件、256 KiB/块、续传、实际哈希核验与原子发布、当前授权下载及workspace内物理去重。失败保留暂存，不发布Artifact。按前述A4-1依赖拆分，250 MiB/Run和90天原始日志保留随真实Run/日志接入及D5清理落实，不将其标为当前已有能力；真实Delivery FK保护引用产物。
- [x] **Step 4:** 已实现人工版本化Delivery/Review、返工理由、显式current/candidate、差异、批准有效性和非代码完成门禁。人工报告保持human；默认代码策略没有B4真实head合并事实时保持In review，不生成工具执行结论。HTTP及公开Interface验证通过。
- [x] **Step 5:** 已记录验收；保留建议提交说明 `feat: add versioned deliveries and evidence review gates`，未执行Git提交/暂存。

A4-5及A4统一验收（2026-11-20）：子代理交付两条Delivery/Review资源别名及14项测试，真实HTTP404红灯后转绿；补测中的fixture key冲突已修正，不计作产品失败。父代理新增4项HTTP监督回归，18项专项全绿：Review严格输入/正整数/路径字段、真实Host/CSRF与正向对照、no-store、实际审核及审计写后503完整回滚/同key重试/精确唯一性、可选字段遗漏与显式默认值不能误用同key。未发现需要修改的别名实现。

另新增2项多用户HTTP集成，真实密码登录及CSRF轮换、工作流发布/确认绑定、成员创建Issue、文件分块/续传/未完成finish拒绝/整件下载哈希、note-only批准拒绝、退回/修订/显式选择/人工批准/差异与历史、非代码完成/真实Review FK、归档保留Review、撤销证据权限后Issue/Delivery/Review/Activity/Inbox/下载及缓存重放一起收窄均通过。独立默认代码路径在真实人工批准后仍留In review，缺provider合并事实不能Done。全量567项服务测试、迁移一致性和Django check通过；npm run check的102项Node测试、单HTML构建、2项原型后端测试通过。日志/tmp/workpal-a45-review.log、/tmp/workpal-a4-journey.log、/tmp/workpal-a4-final-service.log、/tmp/workpal-a4-npm-check.log。保护基线仅.gitignore既有允许差异，未提交Git。A4人工交付/审核范围已验收；A5界面、真实Runtime/外部系统、Run配额/日志保留仍未交付，不宣称首版完成。

### Task A5: 可实际操作的英文界面

**Files:** Create `apps/workpal-web/{index.html,package.json}`、`apps/workpal-web/src/{app.js,client.js,ui.js,styles.css}`、`apps/workpal-web/src/features/{workspace.js,projects.js,issues.js,inbox.js,delivery.js,settings.js}`、`apps/workpal-web/tests/client.test.mjs`、`apps/workpal-web/scripts/qa.mjs`；Create `services/workpal/workpal/web.py`；Modify `config/urls.py`。

**Interfaces:** `client.perform(actionId,payload,{revision,key,confirmationId})->Promise<ActionResult>`；`ui.text(value)->Text`、`ui.openDialog(content,{returnFocus})`；`features.mount(root,{client,actor})`。所有业务按钮声明 `data-action-id`，UI 功能映射至 Registry；本地 notes 的读写以受限客户端动作声明，仅可修改 Workpal 自己的 notes key。

A5按可独立验收的调用链实施：A5-1会话上下文与客户端传输；A5-2同源页面托管、登录/工作区选择与可访问的基础布局；之后接Project/Issue协作、上传/Delivery/Review和设置/工作流等实际页面，最后执行1440px/390px、多用户、键盘与notes闭环。阶段中的未实现能力不作为已交付页面；A5所有页面与验收未齐前不宣称已完成英文界面。沿用已有品牌/Inter/中性紧凑视觉，不搬原型状态，不影响原型单HTML导出。

A5-1先补实际启动所需的身份上下文：`identity.service.session_context(user_id)->SessionDTO`以及`GET /api/v1/auth/session`。SessionDTO固定`user:{id,username}`、`workspaces:[{id,name,revision,role}]`，列表按workspace id稳定排序，仅当前用户实际Membership；停用/匿名拒绝403，无工作区的已登录用户得到真实空列表。返回当前数据库事实，成员撤销或角色修改下次读取立即反映，不依赖登录时快照；不返回其他用户、凭据、session key或source grants。HTTP从session取user_id，拒绝query身份选择/额外query，Host及方法限制真实生效，响应no-store；此读取属于身份握手，无工作区业务outbox。保持现有login/logout/CSRF契约，CSRF仍在登录后轮换。

A5-1客户端深Interface位于`apps/workpal-web/src/client.js`：导出`createClient({fetchImpl=globalThis.fetch,onAccessLost=()=>{}}={})`与结构化ClientError；实例仅暴露`loadSession()`、`login(username,password)`、`logout()`、`selectWorkspace(id)`、`catalog()`、`perform(actionId,payload,{revision,key,confirmationId}={})`。session方法返回SessionDTO，selectWorkspace同步选择刚读取上下文中实际存在的ID并返回workspace DTO；不自动选陌生ID或凭猜测创建上下文。catalog使用选定workspace GET现有动作目录；perform向通用动作入口发送workspace_id/payload与调用方提供的revision/key/confirmation，返回完整ActionResult，waiting_confirmation等不是完成，不自动批准。调用者按一次用户意图生成并保存key，显式重试沿用同key/payload/revision，客户端不自动生成新key重试。

A5-1传输Implementation只允许固定同源相对`/api/v1/`路径，actionId编码为路径段，fetch使用credentials:'same-origin'、mode:'same-origin'、cache:'no-store'、redirect:'error'。POST从真实csrf接口取得token，login成功后再次取token并读取session；logout无论网络结果均清掉本地上下文，但网络失败仍抛未知结果错误，不冒充服务端登出成功。password仅用于本次请求，不保存到localStorage/sessionStorage或日志；业务数据不持久缓存、不写旧原型notes。输入请求先取独立JSON快照，异步等待时调用方修改表单不能改变已发请求；拒绝不能安全传输的非有限数、循环/非JSON值和不安全整数，保留真正遗漏的可选字段。

A5-1错误与迟到响应：ClientError包含status/code/message/requestId/retryable及outcome（failed|unknown）；保留服务端有界错误语义，409不改动调用方输入或自动重发。网络中断、异常协议响应或已发送请求的迟到结果不能当作完成，写请求结果可能未知，必须由调用方使用原key核对/显式重试。403/404触发onAccessLost({workspaceId,code})供页面清除当前来源数据，认证失效另清会话/工作区；不把普通权限不足当成成功空结果。切换工作区、重新登录、登出或刷新上下文的成员变化推进本地generation；发出前后检查捕获generation，旧工作区/旧登录请求不得把结果或错误应用到新上下文，不自动重放旧操作。返回session/workspace为独立副本，不暴露可变内部状态。该客户端只拥有握手、选择和请求一致性，不复制服务端角色、来源或完成策略。

A5-1文件范围：新增`apps/workpal-web/package.json`（private/type module/无运行依赖）、`src/client.js`、`tests/client.test.mjs`及README；修改identity/service.py、identity/actions.py和config/urls.py仅增加session上下文；新增`services/workpal/tests/test_session_context.py`，更新服务README。不先建UI占位页、模型或通用状态框架，不改根package/src/backend。先真实HTTP404红灯及客户端公开Interface的行为断言再实施；如果客户端尚无模块，可先提供最小明确未实现的导出，使失败来自行为而不是import。Django测多工作区、匿名/停用、当前撤成员/角色、严格方法/Host/query、不泄露秘密及无业务写；Node测真实请求映射、CSRF轮换、key/确认保留、409保留输入、403清除通知、网络未知不自动重试、workspace/logout迟到响应隔离及快照副本。运行专项Node、专项Django、全量服务、迁移漂移/check和保护哈希；真实浏览器跨层验收随A5-2起接入，不将传输测试冒充已完成界面。

A5-1首次监督评审（2026-11-20）：子代理仅交付1项session测试及1项客户端测试，虽服务全量568项通过，不能据此验收。父代理新增5项session监督测试，实际发现service将bool/string ID当数据库ID，以及未知异常走Django默认500而缺no-store/统一错误；已补exact int界限和脱敏JSON异常响应，6项session测试通过，迁移/check通过。新增16项公开客户端合同测试后，Node合计17项中12通过、5失败：坏session/ActionResult/catalog等响应未经结构校验即可返回；无效403 body不触发来源数据清除；login与logout同时修改会话cookie。红灯日志/tmp/workpal-a51-review-node-red.log。其余正向映射、CSRF轮换、确认不自动消费、409保留表单、网络未知不自动重试、工作区迟到响应、JSON输入快照和当前成员刷新等测试起始通过。A5-1保持未验收，不进入页面开发。

A5-1补齐契约：响应必须按对应Interface校验。Session的user/workspace字段、正安全整数、role枚举、唯一workspace ID及封闭字段不接受伪造/额外secret；ActionResult完整保留已知state、object_refs字符串kind/id、对象data和JSON error，不能把空对象/数组/未知状态/不安全数字当成功。catalog必须有合法actions列表及实际可消费的目录元数据，不复制服务端业务schema执行逻辑；login/logout/CSRF也须校验各自响应。响应校验失败统一ClientError invalid_response，outcome unknown，不能暴露原始坏响应。HTTP403/404的当前上下文即使body损坏仍发送onAccessLost通知（code为invalid_response），旧generation的响应仍不能清除新上下文。

A5-1认证竞争修复：generation只能隔离JavaScript结果，不能阻止浏览器已经接收的旧Set-Cookie覆盖新session。login/logout的cookie变更请求必须在客户端串行执行，最新用户意图立即使旧上下文失效；已发送的旧请求允许结算但结果不能应用，排队中被更新意图替代的操作不再发送。下一项认证操作在上一项结算后重新读取CSRF，避免使用登录前token。不得靠延时或重试认证POST解决，也不能以排队死锁阻止login内部加载session；普通session刷新与认证队列要保持同一身份顺序。公开Interface不增加全局状态框架。下一Sol修复只限client.js及该Module说明/新增行为测试，保留父代理红测的断言；后端小问题已由父代理修复。

A5-1后端补验：上述6项session专项及全量573项服务测试通过，迁移/check通过，保护基线仅.gitignore既有差异。日志/tmp/workpal-a51-review-session-{red,green}.log与/tmp/workpal-a51-reviewed-service.log。客户端17项中的5项红测仍未修复；不将后端绿灯当作A5-1整体通过。

A5-1客户端首次补齐未执行（2026-11-20）：子代理重跑17项得到12通过/5失败后，因调用不存在的`python`命令停止，未写入修复。父代理已实际确认`/usr/local/bin/python3`与`.venv-workpal/bin/python`（3.11.3）、Node v22.22.0可用，客户端文件可正常读取；这不是外部阻塞，不需用户处理。重新委派时直接使用可用编辑工具或python3，保留现有红测和既定Interface，不重复已完成的后端实施。

A5-1监督验收通过（2026-11-20）：Sol完成响应校验与认证队列后，父代理实际复跑19项Node测试通过，再新增2项兼容/交叠测试并观察到真实失败：真实目录schema中的SQLite 64位上限被当作业务整数拒绝，以及loadSession只等待旧认证队列、可能取消后来登录意图。父代理最小修复仅对catalog描述性schema数字允许有限非安全整数（业务输入、响应ID仍严格），session刷新循环等待最新认证屏障。21项Node全部通过，日志/tmp/workpal-a51-compatibility-{red,green}.log与/tmp/workpal-a51-final-node.log。另在独立临时SQLite正常迁移并使用真实Django HTTP/CSRF响应，把实际session、全部68项catalog和workspace.read交给客户端Interface验证通过；不是mock成功或额外测试计数。最终服务全量573项通过（/tmp/workpal-a51-final-service.log），Node语法、迁移漂移、Django check通过，保护SHA256仅.gitignore既有允许差异。README已反映真实范围；会话与客户端单元可进入A5-2，A5英文页面及完整闭环尚未完成。

A5-2实施范围：同源页面托管、真实登录/登出、工作区选择/读取/改名，以及可访问的英文基础布局。以一次可操作的workspace流程为验收对象，不先造Projects/Issues等空菜单或虚构内容；这些页面在后续单元接通时再加入导航。本单元完成不等于A5整体完成。

A5-2文件：新增`apps/workpal-web/index.html`、`src/app.js`、`src/ui.js`、`src/styles.css`、`src/features/workspace.js`、`scripts/qa.mjs`；新增`services/workpal/workpal/web.py`、`services/workpal/tests/test_web.py`；config/urls.py只追加产品页面/静态白名单路由；更新apps package脚本及两处README。复用现有只读`assets/fonts/inter-latin.woff2`与Workpal品牌mark，不改原型src、根package、backend、旧导出或存档。已探测安装可用的Playwright模块：`/Users/patrick/.codex/worktrees/tapper-agent-workflows/tap/deploy/browser/node_modules/@playwright/test/index.js`，Chromium已存在，不安装依赖。

A5-2托管Interface：Django `/`提供产品index，`/app-assets/{asset}`只接受显式资源映射（当前app/client/ui/workspace脚本、CSS、Inter及brand mark）。按文件类型返回正确Content-Type与nosniff，不提供目录浏览、任意仓库路径或Python源码；路径/编码遍历、未知文件404。GET/HEAD，其他405，Host必须校验。index及当前资源no-store；CSP限制脚本/样式/连接/表单至self、无inline脚本、base-uri/object-src/frame-ancestors受限。API和session路由不改变；页面本身不嵌入用户/业务数据，由client加载真实事实。

A5-2界面：`lang=en`、viewport、Inter、中性表面、紧凑间距与克制边框/阴影，Workpal标题及已有mark。启动先显示读取状态，真实authentication_required才显示Username/Password登录表单；表单method=POST，绝不把密码放URL。登录后显示当前用户和实际workspace选择，重复名字用ID辅助区分；没有成员关系显示真实空状态和登出，不伪造创建按钮。选区后通过client.catalog及workspace.read加载真实名称/角色；仅目录允许workspace.rename时显示Edit workspace。界面只展示当前已接通的workspace功能，不暴露action schema、provider配置、CAS/key等实现细节，不加入prototype/research/simulation标签。

A5-2用户交互：workspace改名使用真实Registry动作与当前revision及一个用户意图的稳定key，等待时禁重复提交。只有completed才更新显示；409保留输入并提供重新读取当前workspace的操作，不偷偷覆盖用户草稿；网络未知保留原意图/key，明确显示尚未确认，可显式重试原保存或重新读取，不能显示成功。未预期waiting/unknown状态不能伪装保存完成。onAccessLost立即清除来源数据/关闭旧对话框，提供重新读取账户；context_changed的旧响应不覆盖新界面。登出立即清除旧工作区显示，若服务端状态未知仍如实提示。所有用户名/工作区名/错误只用textContent或文本节点，不innerHTML、不执行输入。

A5-2 UI Interface保持小：`ui.text(value)`返回文本节点；确有编辑对话框时`ui.openDialog(content,{returnFocus})`负责原生dialog关闭、Escape和焦点返回，不能让每个feature自做一套。布局1440px和390px均无横向溢出，表单有label、错误role=alert、加载role=status、键盘Tab/Enter/Escape可用。当前只有workspace页，可使用紧凑顶部选择和内容区，完整侧栏在后续实际导航接入时加入，不造空抽屉。此阶段不写任何localStorage/sessionStorage，也不触碰旧review notes；notes独立接入时再有明确新命名空间和导入预览。

A5-2验证：先Django真实GET `/`404和Playwright真实页面缺失行为红灯，再实现。`qa.mjs --suite shell`在自己创建的临时目录内建立独立SQLite，显式WORKPAL_DB_PATH，正常migrate并仅在该库种测试用户/两个workspace；启动自己的loopback Django进程。使用实际Playwright浏览器UI登录、选择工作区、编辑并确认持久化、成员只读、换区、登出/重新登录；按1440px/390px检查长/恶意文本仅显示为字、键盘与dialog焦点、无pageerror/外部请求。不得用page.evaluate调用内部业务方法替代用户操作，不mock fetch成功。另用真实HTTP测试静态白名单/遍历、Host/method、Content-Type/CSP/no-store。qa finally关闭自有浏览器/服务并删除自己临时目录，绝不触碰开发数据库；截图保存outputs/workpal-web/a52-shell-{desktop,mobile}.png供父代理视觉验收。未实现suite明确拒绝，不能把shell当完整foundation闭环通过。

A5-2验收命令：全部apps Node测试、`node apps/workpal-web/scripts/qa.mjs --suite shell`、新web测试、全量服务、迁移漂移/check、保护哈希；根npm由父代理在该UI批次统一复核。临时服务器仅用于自动化验证，交付文档说明启动方式和真实范围；不声称Project/Issue/Delivery页面、Runtime或首版已经完成。

A5-2监督验收通过（2026-11-20）：子代理已实现真实托管和workspace界面，但父代理新增浏览器行为检查发现三项真实失败：invalid_credentials的403将登录表单清掉、改名后选择器仍显示旧名称、明确400输入失败被误报未知结果并禁用输入。最小修复后6条监督场景全绿；再补迟到读取、登出响应丢失及150字符用户名，实际复现390px横向溢出并加文本换行。最终9条监督场景全绿，包括两个真实用户409、commit后丢弃响应并原key重试且audit/outbox/幂等各一次、真实成员撤销清屏和空成员列表。日志/tmp/workpal-a52-review-{red,green}.log、/tmp/workpal-a52-long-name-red.log、/tmp/workpal-a52-review-accepted.log。父代理把固定18762端口改为browser-fixture深Module：自己服务进程绑定port 0并报告已绑定端口，显式development/临时DB，所有context禁外部请求，finally清理自有资源，支持npm --prefix路径。`qa.mjs --suite shell`和npm --prefix实际通过，包含Tab/Enter/Escape、焦点、1440/390及恶意文本，截图已目视检查。全量服务575、Node21、迁移/check及根npm（102 Node、构建、2原型后端）通过；保护SHA256仅.gitignore既有允许差异。日志/tmp/workpal-a52-{shell-parent,service-parent,node-parent,parent-npm}.log。实施前浏览器缺页红灯未执行的过程偏差保留，不追认。A5-2通过，A5整体仍未完成。

#### A5-3：项目列表、详情与管理界面

**Files:** Create `apps/workpal-web/src/features/projects.js`、`apps/workpal-web/scripts/qa.projects.mjs`；Modify `src/app.js`（实际Workspace/Projects导航及上下文生命周期）、`src/styles.css`（紧凑项目行/表单）、`services/workpal/workpal/web.py`（仅静态白名单）、`services/workpal/tests/test_web.py`（仅新资源断言）、apps package脚本及apps/service README。可按真实职责新增小的UI辅助文件及专门测试，但必须列明；client、backend业务、旧原型和已有行为断言保持不变。

**Interfaces:** Consumes A5-1 client、`ui.el/text/openDialog(content,{returnFocus,label})`及 `browser-fixture.withBrowser(run)`/`signIn`。Produces `showProjects({client,content,current,onError})->Promise<void>`：单个Module内部拥有列表、筛选、详情和编辑状态；caller只提供当前工作区的client和上下文存活判断，不感知游标、请求序号或幂等细节。内部请求序号隔离搜索/详情迟到结果，父级current隔离导航/工作区切换；切换任何页面关闭旧dialog。只渲染实际可用Workspace/Projects导航，保留选区后默认Workspace以兼容已有操作；不创建未实施页面入口。

**Backend contract:** 六个现有Registry动作`project.create/read/list/update/archive/restore`，VIEW为id/name/description/archived/revision/created_at/updated_at/workflow_version_id。create传name及description；read传project_id；list传query/include_archived/cursor/limit，返回items/next_cursor（0表示无更多）；update传project_id/name/description及expected_revision；archive/restore传project_id及expected_revision。所有写动作需要稳定key；当前六动作都不要求服务端确认，不额外制造批准流程，意外non-completed仍不得显示成功。owner/admin可写，member只读，目录只作可用控件提示，真正权限始终由动作执行时检查。项目来源继承可能使owner也看不到指定项目。

- [x] **A5-3 Step 1:** 新建真实浏览器测试，登录选区后查找Projects并打开列表，应因缺失入口/列表行为失败，记录日志；不得用import失败或mock成功响应当证据。复用已验收临时数据库/动态端口fixture，不另造固定端口服务器。
- [x] **A5-3 Step 2:** 实现项目列表、名称搜索、Include archived筛选、Load more（每页20），过滤条件改变从cursor 0重新读并清旧页。只显示服务端授权后的items，不猜隐藏记录数量、不用浏览器已加载数据代替真实搜索；真实空/加载/错误状态可操作。项目行由键盘可操作控件打开详情，展示name/description/归档状态；同名项目用实际description或可读编号明确区分，不按name猜对象。不展示无实际事实的仓库、Issue数或执行状态，不要求用户输入project ID。保持英文品牌/Inter/中性紧凑行，无不必要装饰。
- [x] **A5-3 Step 3:** 接通Create project、Edit project（name上限200、description上限10000）、Archive project和Restore project。每次用户意图在发送前固定payload/revision/key，重复点击禁用；未知结果只提供原意图重试或真实刷新，不能生成新key造成重复创建；明确输入错误可编辑。409保留draft并reload当前事实，不悄悄替换草稿。只有completed更新事实，归档默认从活动列表移除、Include archived可见并可restore。更换页面/工作区和403/404立即清旧内容、关dialog；不能泄露迟到错误或结果。所有输入和来源只用textContent/text节点。不得修改项目后端或把列表结果当授权凭证。
- [x] **A5-3 Step 4:** `node apps/workpal-web/scripts/qa.projects.mjs`以真实UI验证创建→重载/独立context持久化→编辑→归档筛选→恢复、member无写控件、跨workspace隔离、受限项目不显示及真实来源撤权。分页种至少21条可见记录和私有记录，检查授权后翻页/搜索重置无重复；创建响应在真实commit后丢弃，再原key重试，数据库Project/audit/outbox/幂等均只一次；两context编辑冲突保留draft；快速筛选/详情/工作区切换迟到结果不覆盖；恶意文本、长name/description、1440/390、Tab/Enter/Escape/dialog焦点，无浏览器错误/外部请求。禁止绕过UI调用内部业务方法或mock成功。截图outputs/workpal-web/a53-projects-{desktop,mobile}.png供父代理检查。
- [x] **A5-3 Step 5:** 运行Node21及新增合同测试、shell、qa.review、qa.projects、Django web专项、迁移/check和保护SHA256；静态映射之外不改后端业务时不要求子代理重复全量服务，父代理按集成变更决定。记录真实测试数/日志及缺口；根npm留父代理批次。完成本单元不等于完整Project Context/工作流绑定页面、Issue页面或A5完成，不提交Git。

A5-3监督验收通过（2026-11-20）：Sol实现六个项目动作界面和基础浏览器路径，专项矩阵及文档未齐，首次交付不验收。父代理新增qa.projects.review九条真实浏览器路径，其中四条实际失败：创建响应丢失后Reload清空key导致2个Project/audit/outbox/幂等结果；Projects等待catalog时旧workspace编辑控件仍可操作；保存后的迟到列表刷新打开旧项目、覆盖新选择；200字符无空格标题造成390px溢出。最小修复保留未知创建原意图/key、入口先清屏、列表刷新返回仍有效的选择状态、长标题换行。九条全绿，包含授权后25条分页/隐藏来源/同名对象、member只读、跨区、真实来源撤权、两context冲突、三类迟到响应及恶意长文本；日志/tmp/workpal-a53-review-{red,green}.log。父代理修正原QA在restore未结算时就截图的验证漏洞，补独立context持久化、真实恢复后Active、键盘及尺寸断言；重新目视1440/390截图通过。Node21、旧shell、旧review9、新projects完整路径、web2、迁移/check及根npm通过，日志/tmp/workpal-a53-parent-*.log。后端业务未改变，服务全量575沿用A5-2实际验收，不伪称本次复跑。README/package补齐，保护SHA256仅.gitignore既有差异，无Git写操作。Project资源/工作流界面仍待后续，A5未完成。

#### A5-4a：Issue 阅读与不可变要求历史

本单元把已保存Issue及要求历史接入真实UI。后续A5-4b接创建/编辑/归档与人员选择，A5-4c接状态、依赖、层级及协作；不把本单元当完整Issue页面。人员选择需要面向普通成员的最小目录Interface，不能借用管理员member.list或要求输入用户ID；该接口在A5-4b前单独设计，当前不造负责人姓名或写控件。

**Files:** Create `apps/workpal-web/src/features/issues.js`、`apps/workpal-web/scripts/qa.issues.mjs`；Modify app.js（新增真实Issues导航）、styles.css（阅读列表/版本区域）、web.py（只静态白名单）、test_web.py（新资产）、apps package scripts及两处README。复用client/ui/browser-fixture，保持现有QA和backend业务不变。新代码正常换行/缩进，避免把Module压成少量超长行。

**Interface:** `showIssues({client,content,current,onError})->Promise<void>`隐藏列表、筛选、选中Issue、要求版本及请求序号。父级current保护工作区/导航；内部序号分别保护列表、详情和历史选择。进入即清旧页面，任何非completed不当事实，403/404清来源内容且不退回旧可见版本；普通失败提供显式重试。所有显示文本使用ui.text/el，不持久化浏览器状态。

**Consumes:** `issue.list({query,include_archived,cursor,limit})`（limit20、next_cursor0结束，items无workflow_snapshot）；`issue.read({issue_id})`返回当前VIEW和保存的workflow_snapshot；`issue.requirements.read({issue_id,number})`返回不可变{id,issue_id,number,title,description,criteria,sha256,created_by,created_at}。项目名称需真实`project.read({project_id})`，不要按ID猜；读取Project也接受当前权限错误。列表只用服务端返回status_category显示标准状态组，详情用保存snapshot.definition.states中匹配status_key的label。要求版本号取requirements_revision，不把Issue revision或requirements_version_id当版本号。

- [ ] **A5-4a Step 1:** 在真实临时库创建有两版要求的Issue，浏览器登录/选区查找Issues入口并打开，先观察实际缺页行为红灯；复用withBrowser，不使用假响应/import失败。
- [x] **A5-4a Step 2:** 接入英文Issues列表、标题搜索、Include archived、Refresh和Load more。授权后分页并显示真实空状态；过滤变化重置cursor/旧内容，列表项用标题和Issue编号明确选择，同名标题不能串记录。列表显示标准状态组及要求版本，详情显示真实title/description/criteria（key和text）、项目名称、归档状态、当前工作流状态label和要求版本；不显示不存在的执行结果/进度/Review结论，不渲染未接通的创建/状态按钮。
- [x] **A5-4a Step 3:** 详情提供要求版本阅读，初始当前版本，Previous version/Next version在1..requirements_revision范围内移动，每次请求实际历史。历史标题/描述/criteria与版本标签来自同一响应，与当前Issue信息视觉区分；不把历史内容写回当前记录。切换Issue、工作区、导航或刷新时取消旧版本呈现，迟到结果不能覆盖新选择。按需请求版本，不能一次为任意大版本号生成海量option或请求所有版本。
- [x] **A5-4a Step 4:** qa.issues.mjs验证当前/旧版本差异和只读无业务outbox/实体修改；member可读有权记录、跨区/私有来源隐藏、当前或历史单独撤权后清屏无旧版本回退；至少21条可见+私有数据验证授权后分页、搜索重置和同名ID选择；旧Issue仍按保存工作流snapshot显示custom label而非当前项目新绑定；列表/详情/版本迟到响应与换区隔离；浏览器断网后读取失败不伪装空列表、恢复联网可显式重试；恶意/长文本、1440/390、键盘选择和无pageerror/外网。检查历史请求没有mutating动作，read审计允许、outbox不得新增。截图outputs/workpal-web/a54a-issues-{desktop,mobile}.png。
- [x] **A5-4a Step 5:** 全部Node、shell、qa.review、qa.projects、qa.projects.review、qa.issues、web专项、迁移/check和保护SHA256通过；README明确阅读范围及后续写入口。backend业务不变时全量服务/根npm由父代理集成批次决定；不得提交或宣称A5完整。把实际缺口列清，不拿已有绿灯计作新测试。

A5-4a首次监督评审（2026-11-20）：子代理交付阅读UI与部分浏览器路径，权限/迟到/custom workflow/outbox矩阵未齐，保持未验收。父代理审查独立要求来源时发现既有业务缺口：IssueDTO直接复制当前要求的title/description/criteria，却只授权Issue；list及缓存create同样缺少要求版本引用。新增tests/test_issue_requirements_access.py四条真实ORM/Registry测试全部失败：直接read未拒绝、授权前分页仍返回私有要求Issue、cached create返回私有要求正文、历史结果/审计无具体要求引用。红灯/tmp/workpal-a54a-requirements-access-red.log。不得仅在UI隐藏这些数据，也不得用前一次575项绿灯覆盖新红灯。先完成下列安全修复再验收UI；原始入口红灯未先种两版Issue的过程缺口保留。

#### A5-4a 修复：要求内容的授权与结果来源

**Files:** Modify work/issues.py、issue_actions.py，以及返回IssueDTO的transitions/dependencies/hierarchy内部调用；actions/contracts.py和registry.py仅加入下述结果引用seam；必要的模块README；Create额外focused测试。保留父代理四条红测，旧测试不得削弱以迎合变更。DTO schema及公开service参数保持兼容，Issue仍为object_refs首项，原transition证据引用顺序保留。不改UI/客户端、无外部操作。

**Interface / ownership:** Issue Module集中持有“这份DTO代表哪个要求版本”的规则，不能让各HTTP/页面推断。内部提供current-content授权和DTO→精确对象引用的辅助Interface；读取当前Issue正文必须授权Issue及其current_requirements，列表在该授权后分页，children列表复用同一规则。历史读取只授权Issue及请求的历史版本，不以当前版本替换历史引用；独立旧版本的权限变化不能被错误当作新版本引用。直接service和Registry路径均执行相同授权。普通关系/状态动作若返回Issue正文也必须授权该版本，失败回滚本事务；不为仅返回ID/状态元数据的操作无差别附加全文权限。

**Registry seam:** ActionSpec末尾可选`result_refs`（默认None），签名`result_refs(actor, result: ActionResult)->Iterable[ObjectRef]`，由具体Module根据实际结果data提供来源，Registry不认识Issue字段。统一追加/稳定去重handler或缓存原有refs，既用于新结果的授权/审计/outbox/幂等，也用于重放时的实时授权；保持已有refs顺序。重放也调用该resolver，用保存DTO中的精确requirements_version_id，不能使用当前Issue的版本。这样修复既有SQLite幂等行缺少要求refs的情况，无需重跑业务handler、重写历史结果正文或增加副作用。resolver缺少/不匹配/已删除的要求版本必须拒绝，不能猜最新或静默跳过。默认None的其他action行为不变。

**Issue actions:** create/read/update/archive/restore/transition/dependency.add/remove/set_parent等实际返回IssueDTO的动作，提供Issue+该DTO的要求引用；list/children对所有实际返回items逐项提供相同refs；requirements.read提供Issue+data.id所指的精确历史要求。包含正文的已缓存旧结果也在resolver复查归属/workspace和当前read权限。read审计记录要求及完整根来源，无业务outbox；新写事件/幂等保留输入与实际输出的完整来源。

**Update provenance:** 编辑要求时，在读取/沿用旧title/description/criteria前检查旧要求的当前read/write权限；独立service调用不能绕过。将所沿用要求的实际来源根限制追加到Issue/新要求继承链，沿用现有只追加来源规则，禁止建立Issue→其requirements→Issue循环。同事务重新检查现有/新assignee可读，失败需还原Issue、要求历史、来源、通知、audit/outbox/cache。归档/状态等不改要求正文的动作只因输出正文检查read，不新增不必要的要求write门禁。

- [x] **Fix Step 1:** 复跑tests.test_issue_requirements_access，确认4项真实失败，并为resolver的旧缓存、错误归属、历史版本与当前版本不同及写事务回滚补行为断言。
- [x] **Fix Step 2:** 实现集中内容授权、授权后分页、精确结果来源resolver及读取/更新传播；不通过收紧所有历史读取到当前要求、清空缓存、给owner绕过或绕开Registry修复。
- [x] **Fix Step 3:** 验证新旧缓存重放都拒绝撤源后的历史正文、当前版本更换后仍按缓存旧版本检查；独立旧历史限制不使另一新公开版本被错误标记；list/children过滤后分页；关系/状态/归档输出拒绝后全事务回滚；部分内容编辑不能把私有要求复制成公开新版本；合法read无业务写入且审计scope完整；默认resolver缺省动作不变。
- [x] **Fix Step 4:** 专项、全量服务、迁移/check及保护SHA256通过，文档说明新的Interface和兼容重放行为。实际新测试首跑绿可如实报告，不追认TDD。UI矩阵仍待父代理后续补验，本修复不代表A5-4a或A5完成。

A5-4a监督验收通过（2026-11-20）：子代理完成要求内容授权和结果引用seam，全量583项通过，但扩展矩阵未齐。父代理新增8项独立后端测试，实际复现旧缓存缺少正文字段可跳过来源校验、缓存版本身份/正文绑定不严及编辑输入的旧要求引用遗漏。最小修复让resolver拒绝不完整或归属、版本号、正文不匹配的缓存；仅返回关系元数据的动作不套用正文resolver；issue.update新执行保留旧要求与实际新要求引用，重放不改用今天的要求。16项要求权限专项和全量591项通过，包括children授权后分页、read-only grant、既有/新assignee撤权及状态/依赖/层级失败全表回滚。日志/tmp/workpal-a54a-access-review-{red,green}.log、/tmp/workpal-a54a-supervised-service.log。

父代理新增qa.issues.review八条真实浏览器检查：授权后分页与同名ID、独立旧要求撤权、Issue来源撤权、保存的custom workflow label、列表/详情/历史/工作区迟到响应、可读状态名称及390px长恶意文本。状态直接显示in_progress的真实红灯经英文标签格式化修复；所有读取路径核对实体、outbox与幂等结果不变，读取审计保留具体要求来源。原qa.issues完整路径、Node21、旧shell、旧review9、projects及projects.review9均通过；迁移/check与根npm（102 Node、离线构建、2原型后端）通过。日志/tmp/workpal-a54a-{status-red,ui-accepted,reading-accepted,node-accepted,shell-accepted,shell-review-accepted,projects-accepted,projects-review-accepted,npm-accepted}.log。1440/390截图已目视检查，保护SHA256仅.gitignore既有允许差异，无Git写操作。原Step 1未先种两版Issue的过程缺口保留为未勾选，不追认TDD；本单元功能验收通过，A5整体仍未完成。

#### A5-4b1：工作区人员目录 Interface

**Goal:** 为后续Issue创建/负责人选择提供真实且最小的工作区人员列表。目录可见不代表该人有权读取某个Issue；实际分配仍由issues Module检查Issue及要求来源，不改变现有授权。

**Architecture:** identity目录Module隐藏当前成员校验、有效账号筛选、搜索和游标分页；Registry Adapter只做封闭schema及结果映射。使用现有User/Membership和SQLite，不引入Repository、模型、迁移、专门HTTP别名或前端控件。

**Files:** Create `services/workpal/workpal/identity/directory.py`、`directory_actions.py`、`services/workpal/tests/test_people_directory.py`；Modify `identity/apps.py`（只注册新动作）、`services/workpal/README.md`（目录契约）。`tests/test_identity_actions.py::test_catalog`两处精确集合只追加workspace.people.list，保持member.list仅owner/admin的断言；其他旧测试及公共Registry、现有identity业务、UI、原型和计划不改。

**Consumes:** `require_member(actor, actor.workspace_id)`、`atomic_write(operation)`、Membership/User、ActionSpec/ActionResult及现有通用HTTP。测试通过公开Interface/Registry/真实session HTTP调用，不继承含test方法的测试类。

**Produces:** `directory.list_people(actor, query='', cursor=0, limit=50) -> {'items': [{'user_id': int, 'username': str}], 'next_cursor': int}`。同一SQLite事务内检查当前有效成员并读取，不缓存账号或成员；owner/admin/member均可读。只返回actor.workspace_id内仍有Membership且User.is_active的账号，按User主键升序；cursor是排他User主键，0为初页或无后续页；先全部过滤再取limit+1判断下一页，不暴露隐藏数量。query默认空串，最大150字符且不strip，使用Django icontains的字面子串语义（ASCII大小写不敏感，非ASCII遵循现有SQLite行为，不额外承诺Unicode折叠）；百分号/下划线不是通配符。直接Interface拒绝非str、NUL/非法Unicode；cursor为exact int的0..MAX_SQLITE_INTEGER，limit为exact int的1..200，拒绝bool、null、浮点和数字字符串。业务字段错误为invalid_input 400，非成员/停用请求者为not_found 404。身份来自Actor，不能传workspace/user覆盖字段。

**Adapter:** 注册只读`workspace.people.list`，输入仅可选query/cursor/limit，遗漏用上述默认值；提供显式null不当遗漏。输出闭合schema：items最多200，user_id为1..MAX_SQLITE_INTEGER，username为string/maxLength150，next_cursor为0..MAX_SQLITE_INTEGER。ActionSpec capability=read、allowed_roles为全部三种角色、mutating/confirmation_required/revision_required=False；无输入/输出业务ObjectRef，不把Membership伪装成RegisteredObject。读审计仅记录cursor/limit及框架身份，禁止将返回用户名、email、密码、role、membership revision、session或其他工作区信息放入结果/审计；无outbox、幂等结果、确认或业务写入。执行身份读取遵循已有Actor当前成员规则，不添加权限绕过。

**Review Focus:** 跨区同一账号及停用/撤成员；分页过滤和字面特殊字符；普通成员不获得管理接口；只读结果不带认证字段；目录可见与Issue分配权限分离。以下测试逐一固定，不扩展为组织通讯录。

- [x] **A5-4b1 Step 1:** 新建`test_registered_member_directory`，真实成员经Registry执行ActionRequest('workspace.people.list', {}, None, None)，断言completed、只含当前工作区的user_id/username和next_cursor。先运行该测试，记录unknown_action行为红灯；不导入尚不存在的directory来制造import失败。
- [x] **A5-4b1 Step 2:** 实现上述一个Interface、薄Adapter及启动注册，使同一测试转绿；正常定义forms/schema默认值，不用`value or default`吞掉非法值。目录SQL只投影目标User的id/username，关联过滤可以引用is_active但不能select密码/email或完整User。service独立调用也具备当前成员与同一读取事务规则。
- [x] **A5-4b1 Step 3:** 补公开Interface/Registry行为测试：三个角色均可读而member.list仍拒绝member；相同用户在两区、其他区独有用户、inactive及撤成员过滤；至少3页有过滤项且无重复/跳项，查询切换重置由传入cursor0生效，%/_按字面匹配及ASCII大小写；已读后目标撤销/停用和请求者撤销/停用即时生效；query长度/类型/Unicode与cursor/limit完整非法矩阵，额外workspace_id/user_id拒绝。用SQL捕获直接Interface证明只投影最小账号字段；对比业务表、outbox/cache/confirmation前后无变化，Registry仅追加准确read审计。用真实受限Issue及已有分配Interface验证看到人不授予其Issue/要求权限，失败保持Issue/通知不变。
- [x] **A5-4b1 Step 4:** 使用Client(enforce_csrf_checks=True)、实际session和CSRF token经通用POST读取目录；验证HTTP与Registry结果一致、未登录/缺CSRF/非法Host拒绝、工作区隔离及成员管理仍403。仅更新现有catalog精确集合的新增动作项，不放宽旧权限断言。
- [x] **A5-4b1 Step 5:** 运行`.venv-workpal/bin/python services/workpal/manage.py test tests.test_people_directory tests.test_identity_actions --noinput`、全量服务、makemigrations --check --dry-run、Django check、`node --test apps/workpal-web/tests/*.test.mjs`及保护SHA256。预期原591项加真实新增独立测试全部通过，迁移无变化，原Node21通过，受保护文件只有.gitignore既有差异；记录实际数量和日志。更新README并交父代理验收；不提交Git、不运行网络/模型/Runtime、不提前修改Issue写界面。根npm/浏览器由父代理按集成批次决定。

A5-4b1监督验收通过（2026-11-20）：Sol交付目录Interface、只读Registry Adapter和5项测试，真实unknown_action红灯后转绿，但HTTP、SQL及权限矩阵未齐。父代理新增8项独立测试，覆盖三页过滤/游标、字面搜索、跨区共享账号与目标/请求者撤权、完整非法输入、SQL不加载密码/email等字段、准确读审计且所有其他表不变、实际登录/session/CSRF/Host、目录可见但Issue或独立要求无权限时分配回滚。补验真实发现通用动作成功响应及CSRF提前拒绝均缺no-store；新增workpal/http.py响应middleware并放在最外层，统一覆盖/api/v1/成功、错误、catalog及资源别名。红灯/tmp/workpal-a54b1-http-cache-red.log；修复后目录/身份/HTTP专项29项全绿，目录独立测试共13项。全量604、Node21、旧Issue浏览器路径、迁移/check及根npm通过，日志/tmp/workpal-a54b1-supervised-{full,node,browser,npm}.log。保护SHA256仅.gitignore既有差异。除缓存header缺口外补测起始即绿，不追认TDD；无Git或外部调用。目录验收完成，A5仍进行中。

#### A5-4b2：Issue 创建界面

已按codebase-design将创建草稿/选择器/幂等意图收敛为单个Module，详细计划见[Issue Creation UI](2026-11-20-workpal-issue-create-ui.md)。GPT 6.1 Sol实施、父代理监督；当前只接创建，后续另做编辑/重分配、归档恢复及状态协作，不借本单元宣布A5完成。

A5-4b2监督验收通过（2026-11-20）：创建闭环及13条独立浏览器场景全绿，父代理修复dialog裁切、草稿选中名称、重试错误清除、100项上限按钮及旧响应body未取消五个缺陷。Node新增2条取消stream回归，现23项；旧全部浏览器、web2、迁移/check、根npm和保护基线通过。完整证据及原始流程偏差见创建专项计划验收节。后端604项沿用A5-4b1，本轮无业务后端改动。A5未完成。

#### A5-4b3：编辑 Issue 要求

详见[Issue Requirements Editing](2026-11-20-workpal-issue-requirements-edit-ui.md)。按codebase-design将创建与编辑实际共用的要求字段/稳定key操作收进单个Module。Sol先实现编辑/409核心闭环，父代理随后补完整未知结果、撤权和竞争矩阵；重新分配与归档另行接入。

A5-4b3监督功能验收通过（2026-11-20）：父代理11条独立浏览器补验复现并修复关闭重开忙碌状态、旧回读隔离及标准key复用三个缺陷。编辑/创建/Issue/项目/shell共10个浏览器脚本、Node23、web2、迁移/check、根npm与85项保护SHA256均通过；后端604沿用既有基线。原实施前红灯缺失不追认；子代理npm exec实际下载Node27alpha的命令偏差已核实并隔离新建目录，最终全部以原Node22.22.0验证，详见专项计划验收节。A5未完成。

#### A5-4b4：Issue 归档与恢复

详见[Issue Archive and Restore](2026-11-20-workpal-issue-archive-ui.md)。只接现有issue.archive/restore和授权回读，归档保持状态与要求历史；Sol实施完整可操作闭环，父代理补验并验收。重新分配及状态协作后续另做。

A5-4b4监督验收通过（2026-11-20）：Sol核心闭环具备真实缺入口红灯；父代理12项独立补验发现并修复冲突回读后关闭重开丢失可见性说明。核心+全部旧浏览器、Node23、web2、迁移/check、根npm与保护SHA256通过，详见专项计划验收节。要求历史/工作流状态不变；原意图重放后回读实际最新状态，未将缓存DTO当当前事实。后端604沿用既有基线。

#### A5-4b5：负责人读取与改派

见[Issue Assignment UI](2026-11-20-workpal-issue-assignment-ui.md)。先补按ID读取当前工作区人员的窄Interface，以便当前负责人不在目录第一页或已离开时准确展示；然后接改派UI及通知/冲突验收。目录读取不构成Issue或要求的授权。

A5-4b5a监督验收通过（2026-11-20）：Sol人员精确读取7项独立测试，父代理补3项请求者有效性、真实会话跨区动态事实及只读合同检查，未发现实现缺陷。专项30、全量614、Node23、创建核心/13补验、迁移/check、根npm及85项保护基线通过；证据见负责人专项计划。改派UI b5b已细化共用人员选择、精确人员标签、CAS/原意图重试和真实通知闭环，继续交Sol实施。

A5-4b5b/b5c监督验收通过（2026-11-20）：Sol实现共享人员选择及改派闭环，父代理新增16条独立UI补验、真实SQL/通知/历史与跨context持久化断言，修复长人员名称撑宽dialog。全部旧浏览器、Node23、web2、迁移/check、根npm和保护SHA256通过，614后端全量沿用b5a。补验中的3条定位器失败与1处真实布局缺陷分别记录于专项计划，不混为产品红灯。A5-4b创建/要求编辑/人员改派/归档界面完成，A5整体未完成。

#### A5-4c1：状态历史与当前阻塞信息

详见[Issue Status History UI](2026-11-20-workpal-issue-status-history-ui.md)。先以只读Module展示真实转换事实、原因及责任人，并复用人员标签；后续c2再接状态转换、阻塞操作和完成门禁。不会从历史最后一条推导当前状态或凭Done声称PR合并/环境恢复。

A5-4c1监督功能验收通过（2026-11-20）：12条独立浏览器补验发现并修复解除阻塞历史缺少Unassigned新值；权限、分页和迟到响应矩阵全绿。相关历史/Issues/Assignee浏览器、Node23、web2、迁移/check、根npm及85项保护核对通过。原实施前红灯缺失和一次登录前置超时如实记录于专项计划，不追认TDD。后端614沿用既有基线。用户随后要求所有可独立任务并行、子Agent实施而父代理只监工，后续调度改按并行计划，A5仍进行中。

#### A5-4c2：状态变更、阻塞与完成门禁

监督功能验收通过（2026-11-20），完整证据见[状态操作专项计划](2026-11-20-workpal-issue-transition-ui.md)末节。普通/自定义状态、人类完成门禁、阻塞责任人与assignee区分、冲突/未知结果/撤权/迟到矩阵已实测。独立要求只撤write保留read是正确的正向对照；真实登录前置超时尚未复现和定位，诊断已保存，不声称修复。A5仍进行中；下一项见[依赖界面计划](2026-11-20-workpal-issue-dependencies-ui.md)。





- [ ] **Step 1:** 为 client 写409保留输入、403清除不可见缓存、服务断线不冒充保存成功的行为测试；在 `qa.mjs --suite foundation` 定义用户路径：登录 → 项目/Issue → 人工提交 → 退回 → v2批准 → notes重载，标题输入 `<img src=x onerror=...>` 仅显示文本。先运行 Node tests 和该浏览器场景，预期功能缺失失败。
- [ ] **Step 2:** 实现导航与 A1–A4 所有实际页面，沿用品牌/Inter/中性紧凑布局；复用只读资产而非拷贝样例状态。开始只有已实现页面，不以占位页冒充首版。表单处理 loading/error/empty/conflict；普通业务写入用 Registry；角色/确认控件提供真实授权结果。
- [ ] **Step 3:** 按1440px及390px做键盘 Tab/Enter/Escape、焦点返回、可关闭侧栏、长文本和表单错误提示；notes 只在新产品命名空间写入，读取旧笔记必须显式导入预览。所有来源文本用 textContent，富文本允许清晰的安全子集，不直接 innerHTML 用户内容。
- [ ] **Step 4:** 运行 `node --test apps/workpal-web/tests/*.test.mjs`、`node apps/workpal-web/scripts/qa.mjs --suite foundation`、全部平台测试及 `npm run check`。预期全绿或明确记录独立既有失败；本批验收必须有真实临时 SQLite 与多用户浏览器操作，不能只测 HTML 字符串。
- [ ] **Step 5:** 准备提交 `feat: add connected workspace and delivery UI`，向监工交付 A1–A5 文件和结果。不得声明 Runtime、真实 PR 或环境调查已经可用。

A5-4d1监督验收通过（2026-11-20）：真实依赖20+2分页、跨项目添加/移除、独立context持久化、两种409、丢响应幂等、来源撤权及导航迟到矩阵通过。父代理core4组和review6组实际退出0；启动诊断完成隔离fixture连接队列修正，不宣称历史唯一根因。完整证据与流程缺口保留在[依赖专项计划](2026-11-20-workpal-issue-dependencies-ui.md)末节。

#### A5-4d2：父任务与子任务界面（实施设计中）

C2b存储阶段验收后释放一个并行位，安排GPT 6.1 Sol依据已有hierarchy/issue Registry及当前Issues UI形成workpal-issue-hierarchy-ui.md专项计划。仅做设计，不修改生产代码；主代理审查后实施。范围为当前父任务和授权子任务阅读、显式设置/解除父任务、复用创建界面创建子任务，状态/要求/工作流/交付继续各自独立，不派发Run。计划须冻结真实Interface、键盘/390布局、CAS/未知结果原意图重试及撤权/迟到验证；不重做依赖模块或新增业务后端语义。
