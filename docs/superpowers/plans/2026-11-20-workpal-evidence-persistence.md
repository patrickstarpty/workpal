# Workpal Evidence Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将真实文本/JSONL上传保存为当前授权可读的不可变 SQLite EvidenceSnapshot，原文仅在有界进程内存在。

**Architecture:** 一个 evidence 深 Module 封装策略、规范化、幂等与存储；薄 Registry Adapter 只处理授权声明和元数据结果。专用二进制 HTTP 入口先授权、内存规范化，再以进程内能力调用 Registry；通用 JSON 无法提交服务端证据。

**Tech Stack:** 已有 Django、SQLite、Python；无新增依赖。

**Spec:** [设计真实环境/权限/SQLite章节](../specs/2026-11-20-workpal-software-development-design.md)、[D1](2026-11-20-workpal-phase-d-environment.md)、[Current follow-up](2026-11-20-workpal-parallel-delivery.md)、[normalization计划](2026-11-20-workpal-evidence-normalization.md)、`services/workpal/workpal/investigation/NORMALIZATION.md`及`normalization.py`。

## Global Constraints

- 本计划已由父代理复核，按下文有界任务逐段实施；不进行Git写操作/worktree/安装/npm exec/npx/外网/模型/Runtime。首版与Sol实施已经授权，无需再次请求通用交接许可。
- 保护 `/tmp/workpal-supervision-baseline-20261120.json` 的85项，仅`.gitignore`既有差异；I1已验收默认注册，不改settings、公共服务README或既有集成测试。
- “默认查询窗口 30 分钟，单次最多 1000 条或 2 MiB、30 秒超时，一次调查默认最多 10 次查询”。人工上传不是query，不消费或创建空预算账本。
- “仅掩码字符串不自动解除限制”。原字节不得进入Artifact、日志、audit、Confirmation、幂等result或模型；规范化副本也不进入audit/cache。
- 保持English UI、Workpal、现有视觉系统、离线HTML与本地notes合同；本计划无UI改动。既有13项normalization验收不重命名、不削弱。

## Review Focus

1. 策略字面量包含秘密：普通read/audit/cache不能输出策略正文（Task1测试）。
2. 策略切换与丢响应重试：旧key保留首次版本，新key使用当前版本（Task2测试）。
3. 撤权后缓存重放：当前source/service/environment权限优先于缓存（Task3测试）。
4. 真正2MiB正文：专用流读取不触发1MiB JSON限制，超限不落盘（Task3测试）。
5. 时间未知或显式区间：不补造30分钟覆盖；保留显式偏移及IANA时区（Task2测试）。

---

## 已核对的现有合同与入口选择

实际类名为`Environment/Service/Source/Investigation`；来源ref为`evidence_source`，服务ref为`environment_service`。沿用`environments.selected`、`sources.read_source`、`service.read_service`与`service.read`，不把设计中的EnvironmentDataSource当作已存在类。现有动作`evidence_source.create_upload/read`与`investigation.start/read/list`保留。

Registry.execute先clean/resolve/authorize，再hash原request.payload与expected_revision，缓存命中仍检查input与saved.scope_refs/result refs；handler、record、IdempotencyResult在同一atomic_write。record只按audit_fields取值，mutating自动Outbox；read只有audit。新写动作返回元数据不返回content；否则缓存成为受限内容副本。现有publication.store_content上限1MiB且用于精确外发，不承担证据存储或扩大可见性。

选择 `POST /api/v1/investigations/<int:investigation_id>/evidence-uploads` 二进制正文，`Content-Type: application/octet-stream`，query仅`workspace_id,source_id,format,timezone,range_start,range_end`（后三个可省，重复/额外参数400），`Idempotency-Key`必填。禁止文件名、URL、部署SHA、policy或normalized结果输入。range为成对带偏移ISO8601，start<end，timezone缺省使用当前environment.timezone；未知range存null。读取`GET /api/v1/evidence/<int:evidence_id>?workspace_id=N`；列表`GET /api/v1/investigations/<int:investigation_id>/evidence?workspace_id=N&cursor=0&limit=50`。所有响应no-store/nosniff。

上传不访问request.body/request.POST/request.FILES；认证、Host、CSRF、成员及目标授权先于request.read，检查Content-Length且用read(65536)累积至2097153即413；无临时文件、请求内容日志或异常原文。最大原文/副本均2097152字节，最多1000非空记录，复用normalize_upload原合同。默认通用JSON parse_json的1MiB及settings完全不变。舍弃Artifact分块（原文先持久化）；舍弃base64 JSON（膨胀且1MiB）；舍弃仅绕过JSON限制却调用request.body（仍受Django全局限制）；舍弃客户端normalized dict（可伪造hash/脱敏）。

## 冻结的Interface与数据合同

新`evidence.py`为唯一深Module，不建通用Repository。公开：
- `configure_policy(actor, source_id:int, policy:dict, expected_revision:int)->dict`：人类owner/admin（actor.executor_id必须为None）、当前source read/publish且environment write；policy严格复用normalizer封闭schema。Source初始policy_revision=1、current_policy=None，明确未配置；首次配置expected_revision=1后创建revision=2的版本并将指针/revision原子更新到2。之后同样CAS递增。返回source_id/revision/policy_sha256，不回正文。未配置时上传403 policy_required，不能把allow_fields=[]误当拒绝JSONL的策略。
- `read_policy(actor, source_id:int)->dict`：同样人类owner/admin及source read/publish、environment write，仅用于管理；返回source_id/revision/configured/policy_sha256，已配置时另带policy（未配置省略policy，hash为空串）。策略字面量可能含秘密，执行器身份即使代表管理员也拒绝；上传执行仅在Module内部使用策略，不复用此管理读取或向执行器返回正文。普通source.read保持原DTO，不暴露policy正文或新增敏感字段。此Interface不得产生业务写/outbox。
- `submit_upload(actor, investigation_id:int, source_id:int, content:bytes, *, format:str, timezone:str|None=None, range_start:str|None=None, range_end:str|None=None, key:str)->dict`：先当前授权再哈希/规范化，最后内部调用Registry `evidence.upload`，返回metadata。
- `read_evidence(actor,evidence_id:int)->dict`：返回metadata+content；`list_evidence(actor,investigation_id:int,cursor:int=0,limit:int=50)->dict`：仅metadata及next_cursor，授权过滤后分页，503不吞。

metadata固定id/investigation_id/environment_id/service_id/source_id/actor_id/created_at、policy_revision、normalizer所有输出字段（除content）、timezone/range_start/range_end、event_time=null、deployment_id=null、commit_sha=null、original_location=null。origin=user_upload、coverage=uploaded_excerpt，不把采集时间当事件时间；created_at为服务端UTC。range是用户声明的片段区间，不是验证过的覆盖率；included_line_numbers保留原行号。显式时间不被30分钟默认覆盖；未知部署SHA绝不填当前main。无模型消费或发布许可。

所有ID/cursor/limit严格拒bool及越界，沿用MAX_SQLITE_INTEGER与limit1..200。source必须adapter_type=upload、同environment且allowed_services含调查service；当前membership、调查read、environment write、source与service read均必需。读每次重新检查调查/environment/source/service与evidence ref；登记evidence ref继承四者及其上游，不能因redaction解除来源。source动态允许关系改变亦重新校验，历史refs不删除。

内部`_PreparedUpload`冻结对象仅存在ContextVar作用域，由submit_upload创建并finally reset；保存可信normalized结果、actor/workspace/key和规范描述。Registry payload只有investigation_id/source_id/format/timezone/range_start/range_end/raw_sha256/raw_bytes；不含content或policy。`evidence.upload` resolver在缓存查询前要求当前ContextVar能力且逐字段/actor/key匹配，generic HTTP即使猜中hash也403。能力不是客户端token或数据库行。策略版本不进request hash；省略timezone须在描述中保留null，不能因环境默认时区后来变化导致同一请求意图被重新解释。旧key在当前授权后查既有snapshot并比较相同描述，匹配则复用首次策略及实际时区；不同内容/format/显式范围409。新key选当前策略；规范化完成到事务落库间当前策略变动返回409 policy_changed，不缓存，原key重新准备可成功。成功旧key重试返回旧版本；后续保留/删除策略可另行使内容不可访问。

### Task 1: 受限策略版本

**Files:** Modify `services/workpal/workpal/investigation/models.py`, `apps.py`（只注册新增动作）；Create `investigation/evidence.py`, `investigation/evidence_actions.py`, `investigation/EVIDENCE.md`, `investigation/migrations/0002_evidence_policy.py`, `services/workpal/tests/test_evidence_policy.py`，上述investigation根均为`services/workpal/workpal/investigation/`。使用makemigrations investigation --name evidence_policy正常生成；Task2始终新增下一迁移，不改已验收迁移。原actions.py和sources.py合同保持。

**Interfaces:** 产生上述configure_policy/read_policy；新增`evidence_policy.configure/read`。configure的payload为source_id/policy，expected_revision沿ActionRequest传入，confirmation_required=True、revision_required=True，handler映射为expected_revision；read仅source_id、mutating=False、无confirmation/revision。均allowed_roles owner/admin，resolve先明确校验environment write，输入refs返回source、capability=publish，Module自身也做同一当前权限校验。audit_fields仅source_id，Confirmation只保存既有digest/scope；配置结果/幂等cache只有metadata。read的policy正文只在授权管理结果中，读动作不缓存。通过公开normalize_upload(b'',format='jsonl',policy=policy)验证并取得policy_sha256，不导入normalizer私有validator。

- [ ] Step1 写`test_policy_registered_configuration_and_secrecy`，通过真实Registry configure取得waiting_confirmation，再用真实人类confirmation提交；先记录unknown_action红灯，不能提前import缺模型制造红灯。断言首次revision2、只新增一个版本、Source指针正确，原source.read DTO不变且不泄露literal。
- [ ] Step2 运行`.venv-workpal/bin/python services/workpal/manage.py test tests.test_evidence_policy --noinput`记录红灯；实现模型和薄Adapter使同测转绿。
- [ ] Step3 EvidencePolicyVersion保存source FK PROTECT、revision正整数、policy JSON、policy_sha256 char64、creator FK PROTECT、created_at，unique(source,revision)。Source新增current_policy FK PROTECT nullable（合法未配置状态）、policy_revision正整数默认1；新旧Source均保持未配置，迁移不制造批准过的策略。configure在atomic_write内创建完整新版本并CAS更新两个Source字段，版本通过Interface只插入不覆盖。校验source属于actor workspace、adapter_type=upload；旧版本及输入字典不可被后续配置修改。
- [ ] Step4 至少六个独立测试方法覆盖：①上述确认配置/秘密不进普通source.read、audit/outbox/cache/Confirmation；②未配置读状态、非法policy/ID/revision完整矩阵零写、更新保留旧版/输入隔离；③Direct/Registry的owner/admin/member、跨区、撤source publish与environment write、等待确认和缓存重放时撤权均拒绝；④两真实SQLite连接、各自独立confirmation、同revision竞争一成功一409，仅一版本/指针变更/audit/outbox/cache/确认消费；⑤包装原registry.record实际写audit/outbox后抛503，Source/PolicyVersion/访问关系/缓存/确认/审计全表回滚，原key恢复后成功一次；⑥授权管理read返回正文、普通角色/撤权限拒绝，读仅access audit、无业务副作用。正确既有行为补测首跑绿如实记录。
- [ ] Step5 重跑专项及既有D19/normalization13、迁移dryrun、check和85项保护；另用隔离SQLite迁移旧0001并以历史模型创建Source后升级，验证旧Source关联/数据不变且current_policy=None、policy_revision=1。日志`/tmp/workpal-d1b2a-*.log`。文档说明仅策略配置，无Evidence/HTTP上传，交父代理验收。

### Task 2: 不可变证据与事务合同

**Files:** Modify `investigation/models.py`, `evidence.py`, `evidence_actions.py`, `EVIDENCE.md`（均位于`services/workpal/workpal/`）；新建下一正常迁移0003_evidence_snapshot.py；Create `services/workpal/tests/test_evidence_persistence.py`。依赖Task1验收，不改旧sources/actions或公共Registry。

**Interfaces:** 实现submit_upload/read_evidence/list_evidence及私有prepared能力；新增`evidence.upload/read/list`。upload的Registry resolver对环境write单独authorize，返回调查/source/service供read授权，spec capability=read、mutating=True、confirmation_required=False、audit_fields仅investigation_id/source_id/format。read/list mutating=False、audit_fields仅ID与分页；read ActionResult可以返回content但不产生IdempotencyResult。upload结果与缓存只含metadata。

- [ ] Step1 写`test_snapshot_hashes_time_and_policy_retry`：raw/content/policy三hash真实，1001行保留1000行及truncated，null时间/部署不虚构，显式区间保留；换策略后旧key返回同snapshot，新key新版本；不同正文同key409；人工上传11次不受query_budget=10影响。
- [ ] Step2 写`test_snapshot_two_connection_uniqueness`及`test_snapshot_audit_failure_rolls_back_all_tables`：文件SQLite双连接同actor/key同内容一snapshot、一cache、一写audit/outbox；不同内容同key一成功一409；patch registry.record先调用原函数实际写audit/outbox再抛503，所有业务/访问/缓存/审计表全表快照一致，恢复后原key成功一次。另测策略切换准备后提交409无残留。
- [ ] Step3 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_evidence_persistence --noinput`确认红灯。
- [ ] Step4 EvidenceSnapshot字段：workspace/project/environment/service/source/investigation/actor/policy_version均PROTECT FK，key char200、request_hash char64、created_at；normalizer的content TextField及所有hash/count/status/format/origin/coverage/line numbers字段逐名保存；timezone char100、range_start/end nullable CharField(max_length=64)保留已经验证的原始显式偏移字符串，比较时解析为aware datetime，event_time nullable DateTime、deployment_id/commit_sha/original_location nullable Text。unique(workspace,actor,key)；非负计数及included<=total、字节<=2097152 check。不提供update/delete Interface，内容及metadata只插入；不引入永久拒绝删除的SQL触发器阻塞后续保留清理，D5须经独立有权限的tombstone/清理Interface实现。跨FK workspace/environment一致性在同事务校验；数据库FK/unique启用。hash与读取大正文在事务外，事务内复核权限、策略CAS与prepared内容，再插入/注册ref；Registry包住audit/cache原子写，禁止提前commit。沿用atomic_write有界busy重试，不依赖select_for_update。
- [ ] Step5 重跑Step3应PASS。read/list只读业务表，Registry读audit增长、Outbox不变；增加`test_evidence_read_list_current_scope_no_outbox`覆盖授权过滤与503传播。

### Task2 有界实施检查点 — 2026-11-20

首次Task2子代理仅阅读后结束，无代码、迁移或测试。工具记录没有权限拦截或命令失败，提前结束原因未确认；不能标记实施完成。原Task2合同不减，按两个可独立审查的交付继续：

**Task2a：上传落库与授权读回。** 允许原Task2的models/evidence/evidence_actions/EVIDENCE.md、正常0003迁移，以及新tests/test_evidence_persistence.py。只实现submit_upload、read_evidence、evidence.upload/read及内部PreparedUpload能力。完整数据字段、当前授权、哈希/策略/时区重放、事务与scope合同保持；暂不声明list_evidence/evidence.list可用。

- [ ] Step1 先建一个真实上传→授权read的公开Interface测试；缺Interface可最小NotImplementedError占位，实际行为红灯后实现，不以import失败计红灯。
- [ ] Step2 实现同actor/key唯一落库、原文只在进程中、metadata只含规定字段、同事务登记来源/audit/outbox/cache。保留空事件/部署事实，不把上传解释为查询；全部显式区间和默认时区意图按原合同。
- [ ] Step3 至少四个独立测试：①真实三hash/脱敏内容/immutable字段/metadata缓存无正文，用户显式时间与unknown事实；②同key政策和默认时区变化后仍返回首次事实、不同正文冲突、新key新策略、11次上传不消费查询预算；③普通成员正向上传读回、跨区/当前撤权拒绝、通用Registry无能力不能伪造或取缓存、ContextVar异常后清理；④真实registry.record写后503引发所有业务/来源/审计/cache回滚，原key恢复重试恰好一次。
- [ ] Step4 运行新专项+策略8+normalizer13、investigation迁移dryrun、check及85项hash，日志`/tmp/workpal-d1b2b1-*.log`。更新Module文档，明确本段没有列表/HTTP，交父代理审查；不能因此标Task2整体完成。

**Task2b：授权列表与完整并发验收。** 依赖2a。补list_evidence/evidence.list和原Task2的两连接同/异内容同key、准备后策略竞争、读分页撤权/503完整矩阵。保留2a测试，不通过修改它们降低断言。两段均验收后才进入Task3。

### Task 3: 真实HTTP完整闭环

**Files:** Create `services/workpal/workpal/investigation/evidence_http.py`, `services/workpal/tests/test_evidence_http.py`; Modify `services/workpal/config/urls.py`, `services/workpal/workpal/investigation/NORMALIZATION.md`。依赖Task1/2和I1配置交接；不改settings/公共README/集成测试。

**Interfaces:** 实现上文三个真实路径；GET通过registry.execute对应evidence.read/list，POST调用submit_upload。沿用Actor(user.pk,workspace,executor_id=None,session_id=session_key)、现有CSRF middleware与DomainError JSON。200成功、400格式/未知参数、403权限或伪造能力、404跨workspace不可见、409key/policy冲突、413超限、503busy/audit故障。不得将错误原文插入响应。

- [ ] Step1 写`test_binary_two_mib_session_csrf_roundtrip`：Client(enforce_csrf_checks=True)真实密码登录与轮换CSRF，恰好2097152字节text成功并读回hash，2097153拒绝且全表不变；默认generic JSON超过1MiB仍413。检测无Artifact/ArtifactBlob/Upload新增及无临时上传文件；200不等于完整环境覆盖。
- [ ] Step2 写`test_generic_forgery_revocation_and_cache_secrecy`：直接POST /api/v1/actions/evidence.upload伪造hash/规范化字段403或schema400，无业务行；真实上传成功丢响应后撤environment/source上游read与仅撤environment write分别重试原key403，不回缓存；read-only在仅撤write时仍成功。源service错配/跨workspace/停用身份、非法Host/匿名/缺CSRF各有正向对照；秘密不见于audit/Confirmation/cache/异常日志。
- [ ] Step3 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_evidence_http --noinput`确认红灯。
- [ ] Step4 实现流式HTTP与路由，复用现有error包装，错误日志禁止request body与prepared repr；完成文档标明上传材料来源、截断/未知时间/未知部署与无实时查询事实。再运行Step3应PASS。
- [ ] Step5 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_evidence_policy tests.test_evidence_persistence tests.test_evidence_http --noinput`、`.venv-workpal/bin/python services/workpal/manage.py makemigrations --check --dry-run`、`.venv-workpal/bin/python services/workpal/manage.py check`、`npm run check`，预期全部退出0；核对85项保护hash，不跑兄弟在途测试。报告独立测试数量，不把subTest计多项。

## 自审与衔接

初始Source配置revision=1表示未配置，第一次成功配置产生revision2，与Registry positive revision/CAS一致。策略JSON的version=1是normalizer格式版本，policy_revision是管理员配置修订，二者不混用。父代理纠正了空allow_fields仍能产生JSONL空对象的原默认策略矛盾，以及缺少管理read Interface、同迁移并发编辑、时间偏移丢失和默认时区变化破坏重放等问题。I1已通过默认接线验收；本计划Task1可开始，Task2/3仍等待前置验收。Task2缓存绑定描述由服务端构造，scope保留原来源；当前授权与当前允许服务仍每次检查。

后续范围：真实HTTP查询Adapter的固定端点/重定向/超时及10次query预算账本（实际发起query时原子预留，失败/超时亦记录，不把本轮上传计入）；Findings与引用、外发精确载荷审批、Jira、原环境部署与复验、保留删除/tombstone及缓存清理均另行实施。本计划不声称这些能力、实时采集或上传功能已完成。literal脱敏不等于模型发送许可。本轮仅计划自审，不运行实施验证，不建Git提交。

## Task1 监督验收 — 2026-11-20

Task1已验收。Sol原6项独立测试、历史0001升级、D19/normalization13及迁移/check/npm/hash通过；父代理读实现与测试并复跑原6项。审查进一步明确人类管理合同，新增2项测试实际复现管理员派生executor可读取策略正文、Direct配置可绕过该限制，最小统一selected门禁后转绿。首次审查命令因导入旧TestCase被发现重复运行5项；已改为模块导入，最终原6+新2+normalization13=21项独立测试退出0，未把重复发现或subTest累加。证据为`/tmp/workpal-d1b2a-review-{red,green,migrations,check}.log`；原始红灯仍保留。此限制为本轮明确的管理Interface合同，原初计划未明言executor规则，不追认为原设计原文。

Task2可启动，仅新增Evidence持久化/读取/Registry内部能力；Task3 HTTP继续等待，尚无可用上传入口。

Task2a续作检查点：已有tests/test_evidence_persistence.py的上传→read一项真实红测，以及evidence.py两个NotImplementedError占位；日志/tmp/workpal-d1b2b1-red.log退出1。没有实现/迁移，也无工具阻塞。后续必须保留原红测推进至绿灯及剩余3项，不能将占位或再次复现同一红灯视为完成。

## Task2a 监督验收 — 2026-11-20

Task2a上传落库/授权读回核心验收通过。原4项上传测试保持；监督新增7项（5项实际Evidence行为与2项nullable schema验证），补齐显式偏移时间、member/read-write撤权、跨区、三hash/1000行截断/审计scope及实际record写后全表行内容回滚。真实红测确认nullable字段只声明null导致显式字符串500；共享schema仅新增标量+null的两种类型联合，保留闭合对象/有限JSON/原类型边界，元数据range改为string|null。最终上传/策略/解析及actions/confirmations共56项退出0，另StructuredField/HTTP/identity actions18项退出0，均为专项而非新全量数。日志/tmp/workpal-d1b2b1-{review-red,reviewed}.log、/tmp/workpal-schema-nullable-regression.log。

默认省略值的持久描述仍为null，私有Registry表单wire映射为空字符串；旧key在公开submit_upload内构造请求时使用同一prepared.key，进程内能力不对外提供。原先计划的单类型schema限制现已消除。Task2b继续列表与真实并发/策略竞争，Task3 HTTP尚不可用；此验收不等于Task2整体完成。

Task2b检查点：列表实现已落盘，Sol新增6项但未做真实两连接或完整当前授权/审计矩阵，不计Task2b完成。父代理复现通用Registry只给investigation_id时未应用默认分页的400，新增test_evidence_listing_review.py并修正EvidenceListForm可选cursor/limit规范化为0/50；原严格边界仍保持。新旧listing/concurrency/persistence/review专项共18项通过，/tmp/workpal-d1b2b2-parent-{red,green}.log。下一有界任务只补真实两连接、真实来源授权分页及scope/副作用矩阵，HTTP仍未接线。

Task2b第二批：test_evidence_final.py新增8项，包含文件SQLite双独立连接同/异内容同key竞争、当前可用性过滤、环境仅撤write、allowed_services收窄、实际审计后503全行回滚。Sol联合47项通过；父代理复跑D新8+C图18共26项退出0，/tmp/workpal-dc-review-parent.log。分页私有项当前通过available=False模拟，尚需真实SourceGrant逐项差异及精确audit scope、授权过程503、Direct/Registry严格边界和跨调查/source对照；Task2b未验收。下一有界批次仅补上述四组，不重做并发；Task3 HTTP继续等待。根npm已父代理统一通过，保护差异未增加但全局仍待确认。

## Task2b 监督验收与HTTP接线 — 2026-11-20

test_evidence_access_final.py的四项补测覆盖真实SourceGrant私有分页/精确scope及SQL投影、授权后503、Direct/Registry边界、跨workspace/调查/source与动态撤权。父代理补强所有分页调用的全表只读不变量，并新增owner/member内部分派Actor（含空executor_id）的授权对照：可按原用户授权上传/读取，不能管理策略、伪造prepared能力或绕过撤write；HTTP始终构造executor_id=None。原测试未削弱，最终指定七模块31项退出0，/tmp/workpal-d1b2b-access-parent.log。Task2a/2b功能验收通过；原有保护门禁待确认不变。

Task3现可实施，config/urls.py在本轮仅由证据HTTP任务追加三条既定路由，B不接HTTP。为保证读正文前授权而不跨Module调用私有函数，额外允许evidence.py新增唯一公开authorize_upload(actor,investigation_id,source_id)->None，内部复用_authorized(...,write=True)，无政策正文/业务写/审计；submit_upload仍在读取后完整重新授权。不得借此改旧业务语义或暴露prepared对象。POST返回metadata JSON，GET单条返回metadata+content JSON，GET列表返回items/next_cursor JSON，沿现有资源路由data形状与actions.http.error脱敏错误；不另套ActionResult envelope。认证/Host/严格query与权限先于request.read；只通过64KiB流块读取，最大2MiB，多1字节413，不触发request.body/POST/FILES。通用JSON 1MiB限额与全局settings不改。支持两条GET的只读权限及POST真实session/CSRF，不能新增csrf_exempt。正常和拒绝响应no-store/nosniff。根npm留父代理统一。

## Task3 实施检查点与独立审查 — 2026-11-20

三条HTTP路由、公开authorize_upload和流式Adapter已落盘；Sol新8项及指定回归共48项通过。父代理读实现和8项测试，/tmp/workpal-d1b2-http-parent.log显示8项OK。原始错误消息回显已由实施者改为固定脱敏消息；父代理暂未确认新的实现缺陷。预授权和读取后二次授权当前测试主要依赖mock拒绝，不能替代真实grant在读取期间改变的证据。

下一独立审查只新增test_evidence_http_review.py，按四组闭环补齐：①真实member session、Host/匿名/停用/旧CSRF、环境仅撤write仍可read与source/跨区错配；②受控真实stream及长度边界、读正文前拒绝、读期间真实撤grant后无Evidence落库，分清Django中间件自身行为与本view禁止body/POST/FILES；③JSONL筛选脱敏/1001行截断、时区区间与新旧key策略事实；④实际audit后503全行回滚、原key重试精确一次、逐次GET只读审计、上传不消费查询预算及无Artifact/临时文件副产物。已有8项保留，新测试正确行为首次绿如实记；若发现缺陷仅对evidence_http/公开preflight最小修复，不改公共HTTP、schema或业务持久合同。此审查通过前Task3仍不标完整验收。

Task3独立审查第一批新增5项，真实member/仅撤write、受控stream长度与真实读取期间撤grant、JSONL政策重放、实际record后回滚与GET副作用通过。父代理补强直接view同时禁止body/POST/FILES访问，未修改业务实现；原8+新5纳入联合30项退出0，/tmp/workpal-bcd-small-parent.log。仍有以下限定残留，不把本批绿灯当完整验收。

下一小批仅新增test_evidence_http_boundaries.py，完成两组：①身份/Host/旧CSRF及当前独立来源、service错配、actor两区成员的workspace隔离，均真实HTTP正向对照后拒绝，业务全表不变；②时区/范围非法边界400、11次成功上传不改Investigation行和query_budget=10展示，Artifact/Blob/Upload不增，专用临时目录及上传文件构造路径无原文文件。预算目前只是公开View固定10且尚无查询账本，测试只能证明上传不变更调查记录，不能宣称真实查询扣费账本已存在。保留之前13项，不重复stream与policy矩阵；通过后再判Task3整体验收。

## Task3 监督功能验收 — 2026-11-20

最后3项真实HTTP测试已完成身份/Host/旧CSRF、独立来源与双工作区/服务隔离、时间边界、11次上传及无临时原文/Artifact副产物。父代理读全部断言后，在D16+B8联合24项中复跑退出0，/tmp/workpal-evidence-claim-parent.log。D1b2策略版本、上传落库/读回/列表和三条HTTP入口功能验收通过；仍没有真实查询、查询预算账本、Findings、Jira或环境恢复证明。当前预算10是既有view展示值，不将它描述为已验证的查询计数器。

用户已确认studio.js精确差异，保护例外与85项核验以parallel-delivery最新记录和2026-11-20-workpal-protection-exceptions.json为准；旧待确认措辞仅为历史。本批之后进入独立query-collection实施设计，不修改已验收上传合同或把upload伪装成query。
