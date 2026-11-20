# Workpal Query Collection Implementation Plan

**状态：Q1a（来源/政策/确认配置）已验收；Q1b.1纯请求规范化已冻结准入，Q1b.2与Q2/Q3仍为候选，不启动实现。2026-11-20**

> **For agentic workers:** 沿已授权主代理监督并行方式执行；本设计自行完成，不再委派，不重新询问执行方式。每段可独立拒绝验收，无 Git 写操作。

**Goal:** 实现 D1 受限只读查询、持久预算与真实来源证据；真实连接验收仍为首版必做。

**Architecture:** collection 深 Module 通过专用 HTTP 入口编排，网络在 Registry 事务之外。内部 ContextVar 能力沿既有 submit_upload 模式保护短事务 Registry 动作；不改 Registry.execute，不引入公共信任票据或第二套意图。

**Tech Stack:** 现有 Python/Django/SQLite 与标准库，零新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-20-workpal-software-development-design.md` 调查章节；`docs/superpowers/plans/2026-11-20-workpal-phase-d-environment.md` D1/D6；evidence-persistence 计划。

## Global Constraints

仅独立 services/workpal 与 apps/workpal-web 可实施，旧原型不改。默认30分钟、1000记录、2097152字节、30秒、每调查跨所有actor共享10次。旧测试不削弱；真实行为红灯先执行，新补测首次绿如实记录，不删实现制造红灯。无安装/npm exec/npx/根npm/真实模型/Runtime/外网业务。设计修订阶段未运行测试；后续仅按末尾明确准入范围实施和验证。

实读结论：sources.create_upload 只建upload，read_source硬编码upload；evidence.selected/_authorized限定upload；policy配置以 normalize_upload 校验；Registry.execute 所有动作都 atomic_write，cache先resolve_refs再读；confirmations按actor/workspace/action/key、原payload+revision hash、scope、10分钟有效期消费。上传专用入口先处理内存bytes，再以ContextVar能力进入evidence.upload。以下全部新增Interface，不冒充现有连接。

## Review Focus

撤权与缓存泄露归Q1/Q3；默认窗口重试与双连接额度归Q2；DNS/TLS/慢流及崩溃归Q2；本地完成审计失败归Q3；来源与上传key兼容归Q3。每项有下列专项验收。

## 冻结数据合同

QueryRequest封闭字段：source_id、service（严格int，1..MAX_SQLITE_INTEGER，不收bool）、capability（仅search_logs）、time_window（null或封闭start/end ISO字符串各<=64，aware且start<end）、timezone（null或有效IANA <=100）、filters（封闭level、text；均可缺省；level仅debug/info/warn/error，text字符串1..1024）、cursor（null或1..2048字符串）、key（非空白字符串1..200）。规范JSON最大16KiB，禁止额外字段/非有限数/重复键。显式窗口保留；省略/null保留marker，Q1b不固化；Q2首次预留提交才固定UTC now-30min..now及环境timezone，重放不再取now（完整规范见Q1b专段）。

CollectionResult封闭字段：status、code、attempt_id:int|null、evidence_id:int|null、remaining:int|null、replayed:bool。八态为ok/forbidden/not_connected/no_data/truncated/delayed/timeout/budget_exhausted；delayed只表示本地进行中，不相信远端任意状态。400非法输入、409 key或版本冲突、503存储审计故障走DomainError。not_connected在预留前表示未连接且不计费；预留后失败code=transport_failed/invalid_response/outcome_unknown计费，不能宣称无记录。timeout仅deadline确定到期；unknown绝不自动重发。

Config封闭对象（所有字段必填）：version严格int=1；endpoint ASCII https URL <=2048，DNS小写host、端口仅443、路径绝对且不含百分号或dot段，禁userinfo/query/fragment/IP字面值/反斜线；method枚举GET；network_zone枚举public/private；secret_ref不透明字符串1..200（禁空白/control）；capabilities数组恰为[search_logs]；parameter_schema常量search_logs_v1；response_mapping常量jsonl_logs_v1；readonly_proof封闭对象{reference:str 1..1000, sha256:64小写hex, attestation:str 1..2000}。proof只保存管理员审核依据，不能凭GET认定只读；prepare确认展示全文配置与proof hash，未经审核不配置。无任意header/模板/URL拼接/SQL，secret固定由内部Resolver注入Authorization Bearer，绝不回传。请求参数固定service/start/end/timezone/level/text/cursor，逐项URL编码，无法配置键名。仅支持此具体协议；别的源诚实unsupported_protocol。

响应协议jsonl_logs_v1：200、application/x-ndjson、identity编码；每个非空UTF8行一个封闭对象，允许timestamp（aware ISO <=64）、level（上述枚举）、message（字符串）、request_id/trace_id/deployment_id/commit_sha/original_location（字符串<=2048或null），额外字段拒绝，重复键/嵌套/非有限数/坏UTF8拒绝。没有整体JSON路径映射或远端状态。最多保留1000完整行；读取总量含分隔符最多2MiB，多读至多1探测字节仅判断截断且不进入raw hash。第1001条或超字节限停止，舍弃末尾不完整行，truncated=true；自然EOF的坏行invalid_response，不能当截断。恰1000/2MiB需EOF或探测证明是否截断，所有读取受deadline。零完整行但截断仍truncated；仅有效空EOF为no_data。raw_sha256指实际保留的有界响应前缀，raw_bytes同义，另存received_bytes（含探测字节）与discarded_tail_bytes；不声称全源hash。content hash只指脱敏副本。

## Task Q1: query source、政策和真实确认（可独立验收，无网络）

**Files:** 修改 `services/workpal/workpal/investigation/{sources.py,models.py,actions.py}`；新增同目录 `query_contracts.py,query_config.py,query_actions.py,migrations/0004_query_configuration.py`；新增 `services/workpal/tests/test_query_configuration.py`。迁移号实施前核对同线最新叶节点，禁止覆盖兄弟迁移。

**Interfaces:** sources.create_query(actor,environment_id,name,allowed_services)->dict；read_source返回真实adapter_type且只返回现有公开字段。query_config.configure_policy(actor,source_id,policy,expected_revision)->dict；read_policy(actor,source_id)->dict；configure(actor,source_id,config,expected_revision)->dict；read_config(actor,source_id)->dict（只返回revision/hash/configured/connected=false，不公开endpoint、proof、secret_ref）；query_binding.bind(actor,investigation_id,request)->BoundedQuery（完整合同见Q1b专段）。policy必须本段实现并先于configure/bind可用，绝不依赖Q3。

Source新增query_revision=1、nullable current_query_config FK；SourceQueryVersion不可变字段source/revision/config JSON/config_sha256/policy_version FK/creator/created_at，唯一source+revision。新source adapter_type=http_query，upload绝不改类型。政策复用EvidencePolicyVersion及现有严格政策shape与_policy校验纯函数，query独立selected，upload管理入口行为不变。配置要求current_policy存在；policy变更使旧config失配，必须重新确认配置后bind。bind校验当前成员、调查环境、source和service同环境及allowed_services、对象继承read，预留另要求调查环境write；共享secret不产生授权。

Registry公开动作：evidence_source.create_query（owner/admin、write、mutating）；evidence_source.read沿原动作；query_policy.configure与query_config.configure（owner/admin human、publish、mutating、confirmation_required、revision_required）；query_policy.read/query_config.read（owner/admin、publish、read）。创建服务列表校验复用create_upload，不能继承硬编码adapter_type。配置/政策handler不接confirmation参数；仅Registry执行。ActionRequest首次confirmation_id=None产生waiting_confirmation，同key原payload原expected_revision和返回UUID再次execute；Registry.check/consume真实确认，失败回滚，复用已消费token新key拒绝。CAS分别使用policy_revision/query_revision，hash不含secret值；审计只ID/hash/revision，不记config或policy正文。直接Python写函数仅内部管理实现，无公共裸token。

- [ ] 添加权限矩阵、query创建读取/不改upload、严格shape类型和值界限、无政策不能configure/bind、政策变更后重确认、确认过期/复用/改payload、source继承撤权测试。
- [ ] 执行下述Q1专项，记录实际红灯；实现本段后同命令记录绿灯与独立测试数。首绿补测据实标记。
- [ ] 独立拒绝门槛：Q1不能完成以上合同则Q2不开始；Q1通过也只表示配置可用，connected仍false。

## Task Q2: 持久预算与事务外传输（可独立验收，不写Evidence）

**Files:** 修改 investigation/models.py、service.py；新增 `collection.py,query_transport.py,query_http.py,migrations/0005_query_attempt.py`；修改Q1的query_actions.py及 `services/workpal/config/urls.py`；新增 `services/workpal/tests/{test_query_attempts.py,test_query_transport.py,test_query_http.py}`。

**Interface:** collection.collect(actor,investigation_id:int,request:QueryRequest)->CollectionResult；recover(now:datetime)->int只收敛、不联网。query_http.endpoint(request,investigation_id) 对应POST `/api/v1/investigations/<int:investigation_id>/evidence-queries`，session认证/active/host/CSRF沿上传入口，JSON envelope严格{workspace_id,query}、无GET、no-store/nosniff、错误不含源响应。URL注册独占依赖由本段实施，父代理合并协调，不假称不需新路由。不能从通用actions HTTP执行完整query。

单一内部ContextVar _PreparedQuery绑定actor/原请求hash/attempt/phase及有界脱敏完成数据，finally reset，不可序列化或从客户端注入。Registry动作 evidence.query=预留（mutating，capability=read，内部resolver先验证能力再授权）；evidence.query_dispatch=标发送；evidence.query_finish=终结；三者均内部能力必需，catalog虽可显示也不可直接调用。query_actions.register_actions由现有investigation注册入口挂接。Registry.execute保持原样；不添加通用绕过、read编排或第二套ticket。collect先检查connection readiness，再设能力并execute预留，返回后确保connection.in_atomic_block=False才dispatch/网络；若外层事务存在立即503且零发送。dispatch Registry短事务返回后才调用transport。

QueryAttempt：workspace/investigation/actor/key（唯一workspace+actor+investigation+key）、input_hash、bound_hash、hash_version=1、config/policy FK、固定window/timezone、state、code、reserved_at/deadline/completed_at、nullable evidence FK。input_hash为query-v1域分隔+规范用户输入（保留窗口省略标记，排除key）；bound_hash另含固化窗口/config/policy版本。先当前授权后查同key再检查readiness；同input重放永不重算窗口；input不同409。缓存重放还须当前配置/政策版本匹配，否则409且不发送。新key新请求。

IdempotencyResult内部阶段key=attempt ID的固定q1:r/d/f前缀（reserve使用用户key SHA256+调查ID），scope仍现有action/workspace/user；Registry预留payload仅原输入hash、ID等稳定值，不包含now或动态readiness，默认窗口在预留handler首次创建。缓存resolve_refs必须先核能力与当前绑定授权；collect不直接返回Registry预留cache，而读取当前attempt状态。唯一attempt与额度CAS同短事务：Investigation.query_used默认0，条件query_used<10更新加1再插attempt，失败全部回滚；SQLite atomic_write串行竞争，不依赖select_for_update；额度跨actor，锁忙503。首次key固化发生预留提交；未连接不创建attempt、不扣费、不固化时窗，后续已连接可首次预留。

预留前Resolver未接/secret_ref不可解析/私网B Adapter缺失为not_connected且零预留。Resolver是待实现内部依赖 resolve(secret_ref)->SecretHandle；当前默认UnavailableResolver，绝不读取环境变量冒充连接。句柄只留内存；连接故障在预留后全部耗费。reserved→dispatching→succeeded/failed/timeout/unknown；dispatch CAS仅一人可发送，缓存不授予发送权，只有本次CAS新增dispatch结果才发送。reserved/dispatching到期一律unknown；recover无网络。finish本段仅无数据/失败结果；有记录时在Q3启用前not_connected/evidence_sink_unavailable且readiness失败不预留。活动重放delayed/in_progress；终态重放同结果，unknown映射not_connected/outcome_unknown。无HTTP exactly-once，进程崩溃不自动重发。

**生产传输冻结方案:** 标准库socket.getaddrinfo无可靠取消，不能用线程timeout假装覆盖DNS。采用multiprocessing spawn一次性子进程，父进程以monotonic总deadline30s监督并终止/kill并join回收，子进程独立不接Django连接，DNS/TLS/读全部在子进程；IPC有界只传脱敏前受限bytes，不写临时原文。父在截止立即返回timeout，不等待不可控DNS完成，kill回收采用有界清理并报告异常。子进程只解析一次DNS，所有结果必须is_global且拒绝IPv4映射私网、混合地址、metadata；连接固定已校验IP，TLS server_hostname原host、默认CA验证，不再解析，不使用代理。禁所有3xx，非200失败，禁压缩、总header<=32KiB、逐次socket timeout设剩余deadline，限制请求/响应。secret通过私有IPC传句柄实际值且不打日志；不能安全spawn/kill的平台readiness返回not_connected/transport_unavailable。当前未实接Resolver所以生产仍不可用。network_zone=private一律runtime_collection_unavailable，不能客户端allow_private。测试loopback仅测试构造内部Adapter注入，生产工厂无该参数；不把测试Adapter注册为生产选项。

- [ ] Q2专项先跑真实行为红灯：两独立SQLite连接跨actor竞争10/11、同key仅一次CAS发送、相同省略窗口重试不冲突且零重发、新key新窗口、上传key同名不干扰、锁忙503、每个崩溃位置恢复未知。
- [ ] 测试本地HTTP服务重定向/慢流/1000与1001/2MiB±1/坏mapping；内部TLS fixture验证host校验和固定IP；阻塞DNS子进程测试断言父deadline与回收，拒绝地址变体/混合DNS，无真实外网。专用入口CSRF、会话、DTO、公共内部动作拒绝、网络期间无事务。
- [ ] 实现并复跑相同专项；独立可拒绝Q2，即便Q1通过。未实现可靠deadline不可启用transport。

## Task Q3: 规范化来源与原子完成（可独立验收）

**Files:** 修改 investigation/{normalization.py,evidence.py,evidence_actions.py,models.py,query_actions.py,collection.py}；新增 `query_evidence.py,migrations/0006_query_evidence.py`；新增 `services/workpal/tests/{test_query_evidence.py,test_query_actions.py}`。

**Interface:** normalization.normalize_query(content:bytes,*,policy:dict,provenance:dict)->dict；query_evidence.persist(actor,attempt_id:int,batch:EvidenceBatch)->CollectionResult仅供collect内部finish能力使用。从normalize_upload抽纯策略/脱敏逻辑共享，不能调用后篡改origin。query为origin=http_query、coverage=queried_excerpt；上传保持user_upload/uploaded_excerpt。query政策已在Q1就绪。

EvidenceSnapshot新增intent_namespace默认upload；替换旧workspace/actor/key唯一为workspace/actor/intent_namespace/key，上传所有查询显式namespace=upload保持旧hash算法不变，query用namespace=query-v1、key=attempt主键十进制字符串。旧行迁移upload且hash原样不动，QueryAttempt用户key独立，上传任何key不碰撞。新增nullable query_attempt OneToOne、collected_at、query_scope、request_ids、trace_ids、received_bytes、discarded_tail_bytes。DTO/schema/_metadata同段同步，upload新增字段null并保留旧可读合同。

provenance来源仅固定bound request和响应真实字段：scope/window/timezone、collected_at、事件timestamp、request/trace/deployment ID/SHA、位置及保留行号/截断范围；缺值null不补main。多事件保留逐行字段，快照单值只有唯一值时填写，否则null。所有字段与metadata均走policy allow_fields/redact_literals，scope禁止包含原filter text，位置仅保留无query/fragment的https URL（其他null），不保留可带秘密链接。raw bytes只内存，入DB/log/cache/model前脱敏；保留原始prefix hash不保留原文。

完成由evidence.query_finish执行：resolver在cache前再验当前成员/source/env/service及config/policy版本；handler原子创建Evidence、register_object继承限制、更新attempt终态，Registry record/cache在同事务。read/list的_authorized区分upload/http_query但保留同环境/服务/当前授权，upload提交仍仅upload。返回前再授权，撤权拒绝内容；Registry缓存仅状态/ID，不存原文。失败/timeout同样Registry终结审计；record真实写后注入异常，整个完成回滚（含Evidence/cache/attempt终态），独立预留额度不退。collect返回503，另短事务保守标unknown/local_persistence_failed；该事务也失败则recover到期标unknown并写恢复审计，不能返回成功或重新联网。恢复审计失败同事务回滚且报告503，待后续恢复；本地原文丢失不声称可恢复内容。

- [ ] 新专项先验证来源、hash范围、policy脱敏metadata、上传兼容/namespace、11次上传不扣额度、真实撤权、配置变动、record写后回滚与DB持续不可写恢复的行为红灯。
- [ ] 实现后原命令复跑；旧normalization/policy/persistence/http边界断言不删改。Q3可独立拒绝，不以Q2 fakeHTTP通过替代证据验收。

## 专项命令与记录（实施时执行，本修订未执行）

所有命令前缀 `.venv-workpal/bin/python services/workpal/manage.py test`，后缀 `--settings=tests.settings_investigation_lane --noinput`；仅精确模块，不全量发现：

- Q1：`tests.test_query_configuration`
- Q2：`tests.test_query_attempts tests.test_query_transport tests.test_query_http`
- Q3：`tests.test_query_evidence tests.test_query_actions tests.test_evidence_normalization tests.test_evidence_policy tests.test_evidence_persistence tests.test_evidence_http_boundaries`

每次记录命令、退出码、独立测试数、红/绿实际结果、日志路径。不得宣称预期FAIL已经发生。Node若需要只用 `/Users/patrick/.nvm/versions/node/v22.22.0/bin/node`。本计划不授权实网执行。

## 自审及验收残留

六项父代理异议已在正文替换解决：source完整生命周期、政策前置、Registry真实确认、专用入口事务外编排、双hash首次窗口、封闭配置与传输。没有末尾覆盖前文的另一方案。独占接线依赖是Q1 actions注册/模型、Q2 urls与内部动作、Q3 normalization/evidence schema；实施前父代理协调共享文件，不覆盖兄弟工作线。

真实数据源首次查询与可追溯证据仍为首版最终验收必做；secret resolver、私网B获准Adapter及真实来源未接时逐项not_run，fakeHTTP仅证明本地协议。现在不要求用户提供源或密钥，不实现实网。父代理冻结后才进入Q1→Q2→Q3，每段独立验收；本稿只交候选。

## 父代理冻结 Q1a — 2026-11-20

专用HTTP事务外编排方向可行，不能把方向认可当Q2实现准入。Q2仍需冻结dispatch重放不授发送权的具体返回路径、secret Resolver注入、进程清理与deadline、无Evidence sink阶段的测试许可及raw字节定义；Q3亦等前置。本轮只实施可独立验收的Q1a配置闭环，bind/QueryRequest/BoundedQuery归Q1b，不写占位。

Q1a允许正文Q1文件（query_contracts.py仅必要schema/常量，不放未用DTO），read_source从真实行返回adapter_type；既有upload路径/输出字段不变。新create_query同一事务owner/admin管理，当前environment与全部service write，严格同环境服务列表；Direct与Registry一致，Source继承env/service且不新增宽松grant。新query配置/政策管理沿既有upload管理强度：owner/admin且human，目标env write、source read+publish，缓存resolve也复查；源类型不符拒绝。query_policy.read返回与既有policy.read同形；query_config.read固定{source_id,revision,config_sha256,configured,connected}，未配置hash为空、connected始终false，不返回endpoint/secret_ref/proof。configure返回{source_id,revision,config_sha256}，确认及幂等由Registry既有流程实现。query_revision从1开始，每配置CAS+1，版本保存增后的revision，严格expected_revision 1..MAX_SQLITE_INTEGER-1；无current_policy返回policy_required/403。政策变动不覆写旧配置或版本；后续bind必须拒绝失配。

config hash采用规范JSON UTF-8 sort_keys/compact/ensure_ascii=False/allow_nan=False的SHA256；存输入深副本，有限合法Unicode、严格JSON和正文封闭shape。政策使用现有_policy纯校验及同一规范hash，不能把query伪装成upload来源。所有动作audit_fields仅source_id（创建可含environment_id/allowed_services），沿既有安全记录，不新增第二条audit以凑hash/revision；版本表与受限结果保存hash/revision。确认表和IdempotencyResult不得包含config/proof/政策正文。确认消费、记录、来源及cache同事务；当前源授权失败不能用旧缓存绕过。

至少六个独立公开行为验收：真实Registry create→read，query/upload分离；政策→等待确认→消费→配置读取且输入/返回副本隔离；权限及跨区/成员撤销/等待确认撤权与重放；严格config与revision矩阵（拒绝URL端口/私凭据/额外字段/bool等）；真实record写后503全表回滚及同key重试唯一；文件SQLite两连接同revision不同确认竞争仅一版成功、另一409。旧policy专项与query配置专项显式运行，investigation限定迁移check、Django check及85保护核验；无需网络/HTTP/预算。先完成纵向闭环，再补矩阵，不止阅读或红灯即结束。

## Q1a 核心复核及独立审查 — 2026-11-20

来源/政策/确认配置、0004迁移和7项独立测试已落盘，仍未验收。父代理发现并通过公开configure复现：使用assert的输入校验在Python -O下消失；原非法config测试未配置前置政策，policy_required可能掩盖错误。已先配置有效政策，收紧错误码及全表不变断言，-O实际失败后改显式require，回归绿。另用无序allow_fields/redact_literals复现query政策hash与现有规范化合同不符，修为hash(_policy(copied))同时保留原政策深副本。红/绿见/tmp/workpal-query-config-optimization-{red,green}.log和/tmp/workpal-query-config-policy-hash-red.log。新hash审查测试与原配置7+政策6共14项父代理复跑退出0，/tmp/workpal-query-config-parent.log。fixture改为模块引用，避免单模块发现旧TestCase。

Q1a下一独立审查仅扩展tests/test_query_configuration_review.py（保留父代理hash测试），实际缺陷可最小改query_config/query_actions/sources；不改旧14、模型或迁移。两组：①真实确认绑定/过期/篡改/复用、管理员human/跨区和独立来源撤权；②严格类型与配置边界通过Direct/Registry对照，合法已配置政策前置，失败400且全表不变，safe read及审计cache秘密保护。旧回滚/竞争可复跑不重复算新增。Q1b及后续继续等待，connected始终false。

## Q1a 审查检查点与最后三组 — 2026-11-20

独立review新增两项：Direct/Registry非法配置矩阵及确认绑定/过期/重放。父代理发现内容篡改使用非法空对象只能证明输入校验，现改为合法政策/证明文本变更，并精确断言confirmation_conflict/409、全表不变；key和revision也精确断言，action错误schema仅记输入拒绝，不冒称动作绑定已验收。三模块16项独立复跑退出0，/tmp/workpal-query-config-parent16.log。已有-O验证保留。仍不能签署Q1a完成。

最后新增tests/test_query_configuration_permissions.py，保留原16项，三组约6个独立方法：①owner/admin合法、member/executor拒绝、停用或移除成员、跨workspace与他人确认token；后两者先给测试调用者合法目标及权限，避免提前权限拒绝掩盖confirmation绑定。两动作分别用合法payload跨action挪用token也须409。②真实独立上游来源grant逐项撤read/write/publish，等待确认与已完成key重放均复查本动作需要的能力；失败全表不变、未消费token，恢复后原请求正常且精确一次。不要全表撤所有grant代替独立来源证据。③合法长度上界与非法相邻边界对照，以及配置安全投影；独特endpoint/secret_ref/proof/政策正文标记只允许进入受限版本或明确返回政策的read Interface，不能进入config.read、审计、Outbox、Confirmation、IdempotencyResult或异常/捕获日志。connected必须false。任何现有正确行为首次绿如实记录，不追补红灯。实际新缺陷可最小修query_config/query_actions/sources，不改模型/迁移/公共Registry。Q1b及Q2/Q3继续未准入。


## Q1a 功能验收与 Q1b 设计边界 — 2026-11-20

新增5独立方法完成角色/人类与成员生命周期、合法目标上的他人/跨workspace/跨action确认拒绝、独立environment/service/source根grant、长度上下边界、安全投影。父代理读完测试与管理实现，显式四模块21项独立复跑exit0，/tmp/workpal-query-config-parent21.log；-O已有专项保持。Q1a配置管理功能验收通过，connected仍false。验证不含任何网络请求或查询预算。

Q1b暂只准入具体设计，现有bind候选缺QueryRequest/BoundedQuery字段和输入hash、默认时间窗重放语义，不能让实施者猜。下一设计子任务仅更新本文Q1b专段（必要同步冻结数据合同），不改Q1a实现或Q2/Q3候选：明确parse/validate/bind的公开Interface、DTO及只读授权，拆至最多两个可独立实施任务。普通有read授权member可绑定查询，不能直接复用query_config.selected的owner/admin+publish管理门禁；调查/环境/source/service同属关系、allowed_services、input source继承与服务范围须具体裁定。现有Investigation固定service_id，是否允许查询同环境其他service必须按首版调查范围决策，不自行放宽。

设计必须处理：1 请求shape中必填和缺省，以及null/省略规范化；有限JSON/UTF8/16KiB/严格ID/时间与时区过滤。2 纯规范输入hash与key分离，默认窗口不提前固化或因重放重新取now；Q2首次预留才持久化窗口，Q1b不能用只读函数宣称已固定同key。3 当前source配置/政策缺失、版本失配、内容hash损坏的精确错误；不能读取管理Interface后把秘密配置回传普通HTTP。4 BoundedQuery包含哪些内部值、深复制/不可变、范围引用及hash，明确它不是可缓存的许可，Q2同事务重新检查；不会扣费、写行、审计、创建Evidence或宣称connected。5 错误码/权限隐藏、503传播与全表只读/历史上传合同回归测试。

不设计Resolver/DNS/网络/预算账本的新实现；不顺便创建API或生产开关。交可逐条执行的计划及自审异议，父代理冻结后才实施Q1b。无新的用户确认依赖。

## Q1b 完整合同（Q1b.1已冻结准入，Q1b.2仍为候选）

本段细化上文 bind 候选；Q1a 管理合同和 Q2/Q3 实现范围保持冻结。两个小而深的 Module：query_requests 负责纯输入语义，query_binding 负责当前事实与受限配置。仅Q1b.1已由父代理冻结，Q1b.2待独立复核。没有通用授权票据，没有新 HTTP/action，没有连接就绪推断。

### Task Q1b.1：纯请求规范化

**Files:** Create `services/workpal/workpal/investigation/query_requests.py` 与 `services/workpal/tests/test_query_request.py`。现有query_contracts.py导入work.actions并连接ORM；保持CONFIG文件不变，纯请求Module不得导入它。可导入无ORM的workpal.contracts.DomainError，MAX_SQLITE_INTEGER值为2**63-1，不为取常量引入storage/ORM。

**Consumes:** Python 标准库 json/hashlib/datetime/zoneinfo；不依赖 ORM、actor、时钟或 Registry。

**Produces / Interface:**
- `parse_query_request(body: bytes) -> QueryRequest`：仅 query 对象的 UTF-8 JSON bytes，不接受 HTTP envelope；原始 bytes 长度及下述规范 JSON 长度均须 <=16384。拒绝 BOM、非法 UTF-8、重复键（任意层）、非有限数、尾随内容、非对象。
- `normalize_query_request(value: dict) -> QueryRequest`：Direct 调用同一验证逻辑，仅接受精确 dict/list/str/int/bool/None JSON 类型，拒绝 tuple、子类、自定义对象、循环、非字符串键、孤立 surrogate；不通过序列化偷偷转换类型。parse 调用此函数，二者输出相同。
- `QueryRequest` 为 frozen dataclass，全部字段：`source_id:int, service:int, capability:Literal['search_logs'], time_window:QueryWindow|None, timezone:str|None, filters:QueryFilters, cursor:str|None, key:str, input_hash:str`。`QueryWindow` frozen，`start:datetime,end:datetime` 均 UTC aware；`QueryFilters` frozen，`level:str|None,text:str|None`。无 ORM/可变嵌套引用；调用后修改原 dict 不改变结果。构造 DTO 不是信任捷径：bind 重建规范请求并比较 input_hash，拒绝手工伪造 DTO。

封闭字段规则：source_id/service/capability/key 必填且不接受 null；ID 必须 type(x) is int，1..MAX_SQLITE_INTEGER；capability 仅 search_logs。其余均可省略：time_window/timezone/cursor 的省略与 null 归一 None；filters 省略归空 QueryFilters，显式 null 拒绝。filters 只允许 level/text，二者省略归 None、显式 null 拒绝；level 仅 debug/info/warn/error；text 为1..1024字符，cursor 为1..2048字符，二者允许空格组成的非空值，不擅自改变字面搜索及opaque游标。key 为1..200字符非纯空白；全部原样保存，不 trim/大小写折叠。所有字符串拒绝 C0、DEL、surrogate；不做 Unicode NFC。额外字段一律拒绝。

time_window 必须精确 {start,end}，两值字符串长度<=64；接受 RFC3339 `YYYY-MM-DDTHH:MM:SS[.1..6位小数](Z|±HH:MM)`，拒绝 naive、日期单值、闰秒及 -00:00，offset 的HH为00..23、MM为00..59。转 UTC 后必须可表示且 start<end；无相对 now 校验，允许历史和超过30分钟的显式窗口。首版spec第333/401行规定30分钟为缺省，不能用作显式时间上限。timezone 长度1..100，为ZoneInfo可解析的命名时区，包括UTC、GMT、CET及带斜线名称；拒绝绝对路径、空路径段、`.`/`..`路径段及反斜线，不接受数字偏移。它仅为显示/来源上下文，不能给 naive 时间补区或改变已显式 offset 的瞬间。

规范 payload 固定包含 source_id/service/capability、time_window（None 是默认窗口 marker，否则 start/end 为 UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ`）、timezone（None 为环境时区 marker）、filters（只输出实际给定 level/text）、cursor（含 None）；排除 key 与 input_hash。`input_hash=sha256(b'query-v1\0'+canonical_payload_bytes).hexdigest()`；canonical 为 sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False 的 UTF-8 JSON。16KiB 规范大小校验使用上述 payload 加回 key 的对象；hash 大小不计。默认 marker 永不读 now 或环境；key 改变 hash 不变，窗口省略与 null 相同，显式窗口与 marker 不同。

**错误:** 所有 shape/type/编码/大小/时间错误均 `DomainError('invalid_input',固定无输入内容的消息,status=400)`；不回显 key/filter/body。

- [ ] 写行为组 A：parse/Direct 等价、必填与 null 矩阵、未知键/重复键、bool ID、边界 ID、非JSON类型、NaN/UTF8/surrogate、16384/16385 bytes、字符长度邻界。
- [ ] 写行为组 B：aware/offset 等价 hash、30分钟及更长显式窗口均合法、相等/反向/UTC溢出拒绝、IANA单段与多段正例/naive拒绝、filters/cursor/key矩阵、key 排除 hash、默认 marker 与显式窗口隔离、深复制隔离；时间流逝不改变输出，不读取时钟。规范年字符串必须四位，不能依赖平台strftime对小年份的差异。
- [ ] 实施并仅执行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_query_request --settings=tests.settings_investigation_lane --noinput`，记录实际首次结果；新测试首绿不造红灯。

### Task Q1b.2：无副作用的当前授权绑定

**Files:** Create `services/workpal/workpal/investigation/query_binding.py`、`services/workpal/tests/test_query_binding.py`；不修改 Q1a selected、upload、模型/迁移、Registry 或 HTTP。

**Consumes:** Q1b.1 Interface；现有 `service.read(actor,investigation_id)`、`service.read_service(actor,service_id)`、`environments.selected(actor,environment_id,'read')`、`sources.read_source(actor,source_id)`、`access.authorize(actor,'read',refs)` 与只读 ORM。Q1a `query_config.validate(config)`、`normalization._policy(policy)`只用于内容完整性检查；绝不调用管理 selected/read_config/read_policy。

**Produces / Interface:** `bind(actor:Actor, investigation_id:int, request:QueryRequest) -> BoundedQuery`，Actor 使用既有 workpal.contracts.Actor，不另造 actor。`BoundedQuery` frozen dataclass 全字段：`request:QueryRequest, workspace_id:int, actor_id:int, investigation_id:int, project_id:int, environment_id:int, service_id:int, source_id:int, scope_refs:tuple[ObjectRef,...], environment_timezone:str, config_version_id:int, config_revision:int, config_sha256:str, policy_version_id:int, policy_revision:int, policy_sha256:str, config:dict, policy:dict`。config/policy 在每次返回时 deepcopy；frozen 不代表 dict 递归不可变，消费者修改只能影响本次返回值，不能回写 ORM、别次 bind 或其他缓存。不得存模型实例、secret handle、resolved secret、ready/connected、有效期、bound_hash 或已固化默认窗口。repr 隐藏 config/policy/request（含filters/key），错误不回显内容。仅内部 Python 返回，禁止 HTTP/action 序列化、审计、日志或 Registry cache 保存。

顺序固定：验证请求及 investigation_id → 当前 member/read 调查 → read 调查 project/environment/service 与请求 source/service（每个 ObjectRef 当前授权，包括调查已有继承根）→ 检查关系 → 才读取 current config/policy 正文。scope_refs 为 project/environment/investigation/source/environment_service 的去重 tuple，按 (kind,id) 排序；来源继承链由 authorize 现有 derive_scope 校验，不能自行缩减成仅环境 grant。缺失、跨workspace、无权对象统一 `permission_denied/403`，避免透露对象存在；只转换 read 的 not_found/404 或权限403，503保持原样。

关系：调查 project 与 environment.project 一致；service.environment、source.environment 均为调查 environment；请求 service 必须等于 Investigation.service_id 且属于 source.allowed_services。不得查询同环境其他service。source 必须 http_query。已授权对象的用户范围不符为 `query_scope_mismatch/400`，upload 类型为 `query_source_required/400`。损坏数据库关系（调查固定service跨环境、allowed_services含跨环境service、project/workspace不一致）为 `query_reference_invalid/409`；先授权相关引用，不能以损坏错误泄露无权对象。普通 member 仅需当前 read，不要求 owner/admin、human、envwrite 或 sourcepublish；executor 遵从既有当前成员授权，不借配置管理约束新增禁令。

授权成功后完整性检查顺序：current_policy 缺失 `policy_required/403`；current_query_config 缺失 `query_config_required/409`；FK指向不存在/其他source，或 version.revision 与 Source.policy_revision/query_revision 不同为 `query_reference_invalid/409`；config.policy_version_id 不等于 current_policy_id 为 `query_policy_changed/409`；config validate、_policy 校验失败或规范hash不符为 `query_integrity_error/409`。config hash 使用原config规范JSON；policy hash 使用 `_policy(deepcopy(policy))`规范JSON，与Q1a一致。stored digest必须64位小写hex。环境 timezone 损坏也为 query_reference_invalid/409。DB锁忙/不可用遵循现有503转换，不能 catch-all 变400/409或not_connected。

Q2 调用合同（仅约束后续，不建账本）：先 normalize，bind 获取当前read事实，随后查同actor/workspace/investigation/key；已有attempt比较input_hash，相同只使用持久 window/timezone，绝不取 now。配置/政策版本/hash变化拒绝409，不授发送权。新key通过未来readiness后，在预留的同一 atomic_write 内重新 bind，并额外 authorize 调查environment write；再次检查同key竞争，再仅首次创建时取一次 UTC now，None窗口物化[now-30min,now]，None timezone物化本次environment_timezone；显式值原样使用。将这些值和版本/hash在同事务存入attempt并计算bound_hash（Q2定义），提交才称key固化。dispatch/finish/缓存读取也须在各自短事务重新bind并比对持久版本/hash与范围，不能把旧BoundedQuery当授权缓存。默认timezone marker不因环境变化改变input_hash；已有attempt使用持久timezone，新attempt使用当前环境timezone。Q1b只读bind任何次数都不承诺key已预留。

- [ ] 行为组 C：read member成功且无write/publish；owner/admin不是必要条件；独立撤成员、调查继承根、环境/service/source上游read后拒绝，恢复可再次bind；跨workspace/不存在错误相同；已授权同环境其他service也拒绝。
- [ ] 行为组 D：无policy/config、政策换版、revision/FK/hash/JSON损坏、allowed_services/固定service关系损坏精确错误；在无权状态不得先读秘密正文。返回副本篡改不污染下一次bind。
- [ ] 行为组 E：每次成功/失败前后所有业务表完整内容相同（含audit/outbox/cache/Confirmation/connected/预算/Evidence）；注入数据库503保持503。调用现有upload read/提交专项保持原合同。默认resolver或private Adapter未接不能因bind成功宣称ready。
- [ ] 实施后仅执行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_query_binding tests.test_query_request tests.test_evidence_policy tests.test_evidence_persistence --settings=tests.settings_investigation_lane --noinput`，记录命令、exit、实际测试数与日志；不运行全量或浏览器。

### 独立自审异议表

| 异议 | 推荐裁定与理由 | 验收归属 |
|---|---|---|
| DTO冻结却藏可变秘密？ | 明示dict深复制而非假称递归不可变；仅内部使用并隐藏repr，保持seam小 | D/E |
| 只读bind能否固定key/默认窗口？ | 不能；只产marker，Q2同事务首次创建物化，避免重放漂移 | B及Q2后续 |
| 普通查询沿管理门禁？ | 独立read绑定，保留Q1a管理强度；预留write另属Q2 | C |
| 同环境多个服务是否允许？ | 仅调查固定service，符合现有调查事实，避免扩大数据范围 | C/D |
| hash可信是否等于授权？ | 每次重读关系、授权及内容完整性，旧DTO无持久许可 | C/D |
| 全表只读或503是否能靠语法证明？ | 必须后续行为快照与故障注入；本次未运行任何测试 | E |

本次只有设计修订，以上均为未来验收要求，不是实测结果；Q1a父代理21项既有结果不计作Q1b通过。两任务交父代理冻结，无新增用户确认依赖；Q2/Q3、真实连接与secret resolver仍未实现/未验证。

### Q1b.1 父代理冻结与实施准入 — 2026-11-20

父代理对照首版spec及现有导入关系作三项修正：30分钟仅默认窗口，显式较长窗口保留；命名时区允许GMT/CET等合法单段名称；纯解析放入新query_requests.py，避免旧query_contracts导入work.actions/ORM。同时保留既有text/cursor非空字面值合同，不新增纯空白禁令。上文Q1b.1已同步更新，可直接实施；Q1b.2授权/关系/完整scope与错误隐藏合同仍候选，未准入，不按冻结一项推断全部获准。

本轮只允许新query_requests.py和test_query_request.py。先以实际公开Interface行为建立失败，再完成两Interface及frozen DTO；仅缺import不能冒称有效行为红灯。测试包括独立进程未配置Django时可导入/调用，确保纯Module；封闭字段与所有边界、hash明确期望、deepcopy/frozen、默认窗口不读now、固定错误无内容，至少6项独立方法，现有正确行为补测首绿如实记录。新专项与Q1a四模块21项显式回归、system check、85精确保护；无模型变动无需新迁移，不运行根npm/全量。日志/tmp/workpal-query-request-*.log。实现后交监督，不连接HTTP/预算/网络/Resolver，不改Q1a文件或其他计划。

设计保护核验：使用指定 .venv-workpal/bin/python 对原85项逐文件SHA256比对，仅应用已批准两项精确例外，exit 0，mismatches=[]；日志 `/tmp/workpal-q1b-design-protection.log`。未改写基线。文档写入命令exit 0；未执行代码/测试/浏览器/npm/Git写操作。
