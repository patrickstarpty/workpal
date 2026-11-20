# Workpal Runtime Leases Implementation Plan

> **For agentic workers:** 按本计划逐项实施并交父代理评审；用户指定自行完成，不再委派。Task1a已验收，Task1b已由末尾监督记录准入；HTTP仍待核心验收。下方候选审查记录是历史，不覆盖最新准入。

**Goal:** 冻结可独立验收的服务端 fenced lease、HTTP transport 与当前 Agent 初始化准入。

**Architecture:** execution 租约 Module 隐藏当前授权、CAS、秘密轮换和事务事实。HTTP 仅为 Adapter；配置准入与执行授权是两个不同 Seam，不添加 Repository。

**Tech Stack:** 现有 Django、SQLite、Python；无新增依赖。

**Spec:** runtime-protocol.md 最新 Task2/3、phase-b-runtime.md、graph-persistence.md Task2（均同目录）。本候选替代旧 Task2 的冲突签名；须父代理批准才冻结，不修改旧计划。

## Global Constraints

- Task1 配对/绑定57项已验收；保留原B57、Run快照、11态、ACTIVE和one_active_manual_run。
- 不改旧原型、兄弟文件、旧测试、公共schema/config；urls仅Task2父代理分配独占窗口后追加。
- 不安装、不联网、不作Git写操作、不执行真实模型/Runtime/外部服务；不执行skill命令。
- 本次只写本文，不测试；实施专项用.venv-workpal/bin/python，不重复全量或根npm，父代理统一集成。
- 122模块/782不重复测试是父代理既有冻结结果，不作为本计划实测、不累计专项伪造全量。
- 基线85项、既有.gitignore及指定studio.js差异保留，不回退或重建基线。

## Review Focus

1. 身份DTO伪造或验证后撤销：每次事务内由原始凭据重查（Task1）。
2. 撤权取消写后抛错导致回滚：结果返回后才映射HTTP（Task1/2）。
3. 响应丢失与仍存活进程：不重放明文、不重新领取（Task1/2）。
4. SQLite双连接与审计写后失败：CAS、业务和Outbox同事务（Task1）。
5. 无可信Runtime但保存initialized：独立配置准入，无Run副作用（Task3）。

## 已有 Interface 与事实

- 已有 agents.runtime_identity.authenticate_runtime(secret)->RuntimeIdentity(runtime_id,workspace_id)，只识别当前未撤销设备；bind/unbind/revoke已存在。
- 已有 execution.service.start(actor,subject,agent_id,key,trigger='manual') 创建/复用Run；selected/read/control、admission_refs亦已存在。
- Run.created_by 是首次创建者；Intent可由另一当前调用者复用Run，不能把最近Intent.actor冒充created_by。
- selected检查Run来源、当前Issue/Agent读；admission_refs检查当前项目资源但依赖manual key，不能直接当租约授权完整证明。
- access.authorize/derive_scope、identity.require_member、storage.atomic_write、audit.service.record沿用；不改公共Interface。
- 当前control最后read，撤权后不可用。租约停止不调用control，不修改其既有人类权限语义。
- 以下TaskToken、DTO、函数、字段、路由和准入均为新增候选，尚不存在。

## 核心 Interface 与数据合同

新增execution/protocol.py的frozen DTO（时间均aware UTC datetime，HTTP转ISO8601）：
- CapabilityReport(provider_key:str,version:int,installed:bool,authenticated:bool,execution_ready:bool)。封闭字段、version严格int且=1，bool不作int。
- TaskIdentity(runtime_id:int,workspace_id:int,run_id:int,epoch:int,token_id:int)：仅识别，不是许可，不含secret/hash。
- Lease(run_id:int,epoch:int,expires_at:datetime,input_snapshot:dict,allowed_actions:tuple[str,...],task_token:str)。allowed_actions固定空tuple。
- Renewal(run_id:int,epoch:int,expires_at:datetime,task_token:str)：续租永不重传输入。
- Renewed(lease:Renewal)；StopOnly(run_id:int,epoch:int,reason:str)；Denied(code:str,status:int)。判别字段kind分别renewed/stop_only/denied。
- ClaimResult(lease:Lease|None)。不返回cursor、扫描计数、候选ID或页尾标志。

新增execution/leases.py公开Interface：
- claim(runtime_secret:str,capabilities:CapabilityReport)->ClaimResult
- authenticate_task(secret:str)->TaskIdentity：只验类型、hash存在、Runtime未撤销、token未撤销且expires_at>now；不验成员/绑定/lease，不写业务。识别成功不保证renew成功。
- renew(task_secret:str,*,run_id:int,epoch:int)->Renewed|StopOnly|Denied
- claim/renew必须在自己的atomic_write内再次从原始secret识别，禁止接收调用方构造的Identity；authenticate_task不能产生可复用授权票据。
- _clock: Callable[[],datetime] 默认timezone.now；每事务尝试只采样一次aware UTC now。
- 内部可信 Seam：_verify_capabilities(*, runtime_id:int, workspace_id:int, agent_id:int, provider_key:str, now:datetime)->bool，默认False，仅本地测试依赖注入；不接收报告，不根据数据库配置推断installed/authenticated/execution_ready，无生产开关或外部探测。claim与renew每次调用，严格bool返回，异常传播，不能吞成授权拒绝。
- claim CapabilityReport封闭校验只证明客户端声明；三个True也不是信任。先独立验证请求Runtime的copilot_cli能力（agent_id取0表示设备级），False统一409 capability_unavailable且不扫描；候选当前授权成功后再以实际agent_id验证。renew只用已绑定且已授权的当前Agent执行同一可信检查，不构造报告。
- 只有当前及快照provider均copilot_cli可领取；codex_cli/claude_code/gemini_cli/opencode均extension-only，409 capability_unavailable。自报三个True仍不派发。
- Task bearer不接普通Registry HTTP；该入口只认既有session。内部Actor/executor既有语义不改，租约内部以created_by构造Actor仅用于本合同授权和审计。

正常迁移execution/0003_runtime_lease.py：
- Run增加lease_owner(nullable FK agents.Runtime PROTECT)、lease_epoch(PositiveBigInteger default0)、lease_expires_at(nullable DateTime)。不改快照/hash/状态/唯一约束。
- RuntimeClaimScan：runtime OneToOne FK PROTECT主键、last_pk PositiveBigInteger default0、revision PositiveBigInteger default0；仅位置，无正文；与下列模型在同一0003迁移创建。
- TaskToken：run/runtime FK PROTECT、epoch PositiveBigInteger、secret_hash Char64 unique、expires_at DateTime、revoked_at nullable DateTime；scope_refs JSONField(default=list)，存排序去重的{kind:str,id:str}限制引用；不存明文/输入。每Run仅一个revoked_at为空的token，条件唯一约束。
- token前缀wp_task_加32随机字节hex；hash SHA256；epoch及scan revision最大2**63-1，Run revision最大2**31-1，溢出400且零写。
- 旧库升级lease_owner/expires为空、epoch0，不回填执行事实；迁移依赖execution0002和实际agents绑定迁移叶节点，生成前确认叶节点，禁止猜造依赖。

## 当前授权、领取与原子性

每次claim/renew由Run.created_by构造Actor(user_id,workspace_id)，executor/session为空；require_member检查用户活跃和当前成员。
在同一事务检查：Run ref及input_snapshot.source_refs全部历史来源write；当前Issue、精确历史requirements、当前Agent、当前Project read并对其refs write；枚举当前全部ProjectResource，逐个read并write，不能只枚举可读资源。
Run注册来源是append-only；同时检查保存的source_refs，历史移除资源不能洗掉授权；新增资源纳入检查但不改输入快照。跨区/缺失/无效来源fail closed。
当前绑定必须enabled、runtime匹配、Runtime未撤销；绑定变更或provider变更均重新检查。无需给created_by虚构runtime对象管理权限。
claim只考虑同workspace绑定的deferred、epoch0、owner为空Run。每Runtime持久扫描按pk严格递增，单事务最多32个候选；从last_pk后取，不足32时本请求不回绕，下次无后继则从0取32个。每个检查过的候选都推进last_pk，无权跳过；成功领取在该位置停止。空集合last_pk归0。位置与scan revision CAS、领取事实同事务提交，冲突重跑整个atomic_write闭包。进程重启读取同一行，客户端不能重置位置；响应丢失仍保留进度。固定有限候选集合且持续调用时，首32条全拒绝仍在后续调用到达第33条；不承诺无限插入下的固定延迟。返回统一lease:null，无私有位置编码（含base64/签名）、数量或原因；不声称消除时间侧信道。
候选当前权限拒绝跳过；候选provider/能力不合格也跳过，不以409暴露该Run。设备级可信能力未验证才统一409。
CAS比较revision/status/epoch/owner及读取的当前绑定revision；事务内重查授权。SQLite写锁或snapshot升级失败由atomic_write重跑整个闭包，不仅重试UPDATE。
成功转dispatched、epoch+1、revision+1、lease=now+45s、token=now+60s，首次Lease才给深复制输入。
审计只含run/runtime/epoch/状态/固定reason；用实际record产生Outbox，与CAS/token同事务，无另起事务。无正文、secret、hash或token响应缓存。
轮换撤销旧token再新建；失败全部回滚。响应丢失旧token立即无效，不能凭原请求重放新token；等租约过期进入恢复，禁止自动重新claim仍可能活着的进程。

### 审计限制引用与撤权后的最小事实

领取及每次成功续租，在有效授权事务中保存token.scope_refs：Run ref、全部本次检查的对象refs、input_snapshot.source_refs及derive_scope(全部refs).source_refs的并集，排序去重；跨workspace拒绝。续租新token保存旧scope_refs与当前有效集合的并集，永不缩小历史限制。字段只接受闭合{kind,id}字符串、合法ObjectRef类型、非空id；不允许客户端写入；迁移无历史token回填。它是审计限制而非授权缓存，当前授权仍完整重查。

停止使用该token已保存集合，另合并服务端从RegisteredObject/SourceLink元数据可遍历得到的当前Run及已保存对象追加根（忽略available标志但不读取正文；循环去重，跨workspace或损坏报503回滚）。这是限制收紧，不用于授予权限，不调用authorize/derive_scope/require_member；来源available=False、成员删除不妨碍写审计。无新根时保留全部历史限制；未来读取audit/outbox仍沿当前动态限制授权，来源不可用默认拒绝，不把引用回传Runtime。

直接调用既有audit.record(actor,spec,result,payload,refs,scope_refs)：actor使用Run.created_by/workspace；spec仅固定action_id/audit_fields/mutating=True，result为ActionResult(state='completed',object_refs=[],data={})；refs仅Run ref的序列化列表，scope_refs为上述序列化限制集合。payload仅run_id/runtime_id/epoch/status/reason，固定reason枚举；无secret/hash/正文。record不重验成员，实际AuditEvent/Outbox和token/CAS同事务，任何写失败全回滚。scope_refs不得空，损坏数据503，无省略审计降级。

## Renew结果、时间与停止合同

心跳建议10s；now==expires_at即过期。每次有效续租从now起45s/60s，不累计；revision与epoch/token CAS失败409 lease_conflict，重新请求仍须当前有效token。
冻结处理顺序：身份→URL/epoch→终态→既有cancel/recovery→租约到期→当前权限/绑定/能力→正常轮换。
- 身份类型错、未知、Runtime撤销、token撤销或now>=token.expires_at：401 authentication_required，零写；故已撤销token重复stop请求为401，不是再次StopOnly。
- URL错404 not_found；epoch与token/Run不符409 stale_epoch，零写。先身份再检查URL，不能探测任意Run。
- completed/failed/cancelled/awaiting_input：409 lease_conflict，零写；即使lease已过期也绝不改为recovery_required。
- 已cancel_requested/recovery_required：仅在仍有效token首次观察时撤销所有有效token，Run revision+1（CAS），记录一次固定reason stop_observed审计；返回原状态对应StopOnly。撤销后重复凭据401，无revision/audit增长。不得轮换或延长。
- lease到期（now==expires_at亦到期）：CAS为recovery_required、revision+1、撤销token并审计，StopOnly lease_expired；不得重新claim。token先到期则身份401，由后续恢复扫描负责到期事实。
- 当前授权/成员/来源/绑定或可信能力失效：CAS cancel_requested、revision+1、撤销token及审计，StopOnly authorization_revoked。仅捕获本步骤预期DomainError的permission_denied/403、not_found/404、authentication_required/401及已明确定义的成员拒绝；不得按所有DomainError或所有异常处理，503和未知错误传播并回滚。能力False视同失格，不暴露引用或正文。
- dispatched/waiting_local_directory/running正常轮换：revision+1，新token及期限；其他状态409零写。CAS比较Run revision/status/epoch/owner、token有效行及binding revision；绑定并发或SQLite升级冲突重跑闭包，不能只重试UPDATE。
- 所有停止返回结果离开atomic_write后才映射HTTP；禁止调用control/read/selected回读已失权内容。取消与续租按CAS线性化，取消先提交则不能续租。
- HTTP StopOnly为200固定{kind,run_id,epoch,reason}，无需任何人类read回读；Renewed为200，Denied按status；已提交停止后transport失败不回滚。
- Runtime撤销或失联时服务器不能保证立即通知；10s只是建议，服务器只能记录声明，不能证明远端OS已停止。

## Task3事件/恢复最小接缝（本轮不实现）

不新增任何events/logs/stop路由；未实现入口404，不能接受session或Runtime bearer绕过task token。测试固定这些入口不能走通。
首版既定恢复与日志目标保留为后续必做；本阶段只延期接线。“过期token直接补传日志”不能直接实现：过期/撤销token只能401，不作为恢复凭据。StopOnly仅对当次仍可识别凭据有效，不承诺长期stop通道。
未来恢复须独立管理员授权、run/epoch/设备绑定的短时恢复许可；合同另审前默认拒绝，不能复用authenticate_task放宽expiry。管理员核实停止沿既定证据要求另验收。
未来日志默认丢弃自由文本正文；仅允许固定枚举event kind、整数exit_code/sequence、服务端ID及长度有界reason_code，额外字段拒绝，落库前白名单投影，禁止原文/hash/异常回显落审计。需要自由文本须另审脱敏合同后才能开放。
恢复声明不得改写为OS停止证明；超时只保留ACTIVE中的recovery_required，阻止替换Run。

## Task 1a：claim与凭据（独立验收）

**允许文件:** services/workpal/workpal/execution/models.py；新同目录protocol.py、leases.py、migrations/0003_runtime_lease.py；新services/workpal/tests/test_runtime_lease_claim.py。不改公共schema/settings/旧测试。
**Interface:** claim(runtime_secret:str,capabilities:CapabilityReport)->ClaimResult；authenticate_task(secret:str)->TaskIdentity；DTO、模型和审计合同见上。renew留Task1b，不创建伪实现。
- [ ] 增加公开Interface验收；缺模块import失败只记接口缺失，正确新补测首次绿如实记录，不修改已验收代码制造红灯。
- [ ] 实施claim/凭据/持久扫描/限制引用正常迁移；保留B57、快照与ACTIVE唯一性。
- [ ] 六组验收：①默认拒绝、报告严格类型与四extension；②前32拒绝后第33可领取、响应无位置、重启续扫；③成员/历史及新增来源/绑定拒绝不泄露候选；④双连接扫描与领取CAS及一个有效token；⑤实际audit/outbox后失败全行回滚；⑥秘密不落日志/cache、旧库迁移与快照不变。
- [ ] 实施时仅专项`.venv-workpal/bin/python services/workpal/manage.py test tests.test_runtime_lease_claim --noinput`，迁移检查由父代理安排；本轮未运行。

## Task 1b：renew与stop（依赖1a独立验收）

**允许文件:** services/workpal/workpal/execution/leases.py；新services/workpal/tests/test_runtime_lease_renew.py。不改1a模型或公共Interface，合同变更退回设计审查。
**Interface:** renew(task_secret:str,*,run_id:int,epoch:int)->Renewed|StopOnly|Denied；复用1a模型/身份/审计Seam。
- [ ] 写公开Interface测试并如实记首次结果，再实现固定优先级、轮换与提交停止结果。
- [ ] 六组验收：①终态+过期零写与全部优先级；②首次stop一次revision/audit、重复401；③来源available=False/成员删除仍提交取消且限制不缩小；④45/60秒等号、响应丢失、旧epoch/URL及溢出零写；⑤双连接cancel/renew及绑定竞争；⑥可信verifier独立无伪报告、预期拒绝与503区分、实际audit后失败回滚。
- [ ] 实施时仅专项`.venv-workpal/bin/python services/workpal/manage.py test tests.test_runtime_lease_renew --noinput`；不运行全量。

## Task 2：HTTP Adapter（核心验收后）

**允许文件:** 新execution/runtime_http.py、新tests/test_runtime_lease_http.py；config/urls.py仅父代理独占窗口追加。没有窗口则不碰urls，等待父代理分配。
**公开Interface:** POST /api/runtime/v1/claim body{version:1,capabilities}，runtime bearer；POST /api/runtime/v1/runs/<int:run_id>/renew body{version:1,epoch}，task bearer。严格封闭JSON、16KiB、重复key拒绝、Host校验、POST限定、no-store/nosniff，仅这两入口豁免CSRF。
- [ ] 写真实HTTP请求测试，当前路由404如实作为缺入口；实现Adapter调用核心原始bearer Interface，不接受cookie/session替代。
- [ ] 六组场景：①真实pair获得bearer后claim/renew；②task不能claim/runtime不能renew/session不能替代；③跨run/epoch/撤销/过期及提交后StopOnly200；④JSON/方法/Host/大小/重复key；⑤丢响应不重放及响应无秘密错误回显；⑥事件/日志/stop未实现路由不可走通，Registry不接受task bearer。
- [ ] 仅运行`.venv-workpal/bin/python services/workpal/manage.py test tests.test_runtime_lease_http --noinput`；父代理整合原B57，不在本专项重复全量。

### Task1/2严格输入补充

核心与HTTP均严格type(x) is int（拒bool），run_id/epoch在1..2**63-1；revision持久增量上限2**31-1，scan revision上限2**63-1，任何溢出400且事务零写。secret严格str及既有wp_runtime_/wp_task_格式与长度，不strip/强转；错误不回显。CapabilityReport必须精确DTO类型且每字段严格校验，provider_key为已知五值，未知400。所有now必须aware UTC；时钟非法或加45/60秒溢出返回400零写。HTTP version严格int=1，epoch同核心；不接收客户端scope/时间/身份/游标/额外字段。

## Task 3：后续有界的当前Agent初始化准入（独立验收）

**允许文件:** 新execution/admission.py、新tests/test_agent_initialization_admission.py；不改Graph、agents或service.start。
**公开Interface:** admit_initialization(actor:Actor,agent_id:int)->AgentInitializationAdmission(agent:dict,source_refs:tuple[ObjectRef,...],purpose='initialized',execution_authorized=False)。DTO定义在本文件，不改公共contracts。
调用方同一事务中调用；当前require_member、Agent read、来源read、provider配置严格合法且仅copilot_cli允许；返回公开Agent深复制及derive_scope来源。无Runtime仍允许保存initialized；不检查安装/认证，不授予派发资格。
拒绝：成员缺失404、来源权限403、跨区/不存在404、ID非法400、其他provider409 capability_unavailable；存储错误503。DTO仅当前事务事实，禁止缓存当未来授权。
Graph另负责主体write、精确要求/图版本及所有输入read；本函数不能替代这些检查。未来claim仍重新执行可信能力与全部write门禁。
- [ ] 写公开Interface六组场景：①无Runtime可准入且execution_authorized=False；②四扩展provider拒绝；③独立Agent来源撤权/成员停用/跨区；④严格ID/配置及返回快照不被修改；⑤调用前后Run/Intent/Issue/Agent/审计/Outbox零变化；⑥同事务授权后回滚与重复调用无写。
- [ ] 实施后仅运行`.venv-workpal/bin/python services/workpal/manage.py test tests.test_agent_initialization_admission --noinput`，首次绿不造红。
- [ ] 父代理验收此Interface后再分配Graph Task2接线；本文不宣称已可接GraphInstance。

## 自审与交接

| 审查冲突 | 修订合同与验收归属 |
|---|---|
| 1 私有pk泄露/饥饿 | 无客户端cursor；RuntimeClaimScan持久位置、32条推进及重启，1a第2/4组 |
| 2 伪能力报告 | verifier独立精确签名、默认False；双provider检查，1a第1组/1b第6组 |
| 3 renew顺序与提交 | 终态先于到期；首次stop撤token增revision、重复401；503传播；1b第1/2/6组 |
| 4 撤权审计失败 | token.scope_refs完整字段及只增限制；最小record不重授权，1b第3/6组 |
| 5 身份/输入/延期目标 | 原始secret事务重查、HTTP session规则不改内部Actor、严格输入/CAS；恢复日志后续必做且当前默认拒绝 |

剩余准入：父代理须审核本候选（含仅限制收紧的元数据遍历）、确认实际迁移叶节点并分配urls窗口；不得据此直接编码。Task3与下方冻结准入逐字保留。默认verifier=False，无真实执行。本轮仅文档修订，未运行测试或迁移，不记录未运行通过；122/782仅既有冻结事实。

## 父代理审查与分段准入 — 2026-11-20

核心Task1/HTTP Task2尚未冻结，不按候选直接实施。需要设计续作解决：①next_cursor为未授权候选Run的pk会泄露对象存在，和“无权候选不泄露ID”冲突；采用不向客户端暴露私有位置的有界轮转合同并给出持久/重启语义。②renew不得从当前Agent自行构造installed/authenticated/execution_ready报告作为验证输入，可信verifier需独立于客户端与伪造报告。③终态必须先于lease过期处理，避免把已完成Run改回recovery_required；现有cancel_requested/recovery_required幂等处理与token过期分支需明确优先级。④来源被停用/撤成员后取消审计仍须成功，不能依赖再次授权读取或对已不可用来源derive_scope而回滚；冻结可安全保存的限制引用及审计范围。⑤本阶段未实现事件/日志入口可默认拒绝，但不能删除首版既定日志与恢复能力；旧Task3目标保留，具体恢复许可/文本脱敏另审。通用HTTP Registry不接受task bearer，内部Actor的既有executor语义不改。

Task3初始化准入不依赖租约，可以先独立实施，仅允许execution/admission.py与tests/test_agent_initialization_admission.py。冻结admit_initialization返回本文件内frozen AgentInitializationAdmission；agent为公开agents.read DTO的深复制，source_refs是derive_scope得到的根引用排序tuple，不额外混入Agent ref（Graph调用方另保存精确Agent ref）。purpose固定initialized、execution_authorized固定False。严格正整数ID；当前成员与Agent read；仅copilot_cli，name非空白str且<=200、model为str且<=200（空合法）、provider严格已知，错误沿Task3约定。对配置的检查不宣称安装/认证/运行许可。调用方应在保存初始事实的同一事务使用；没有写入/audit/outbox/Run/Intent副作用，也不接入Graph或start。该小任务经监督验收后才解除Graph的B接口门禁，Graph自己的key/Registry接线仍须冻结。

## Task1a 监督复核与实施准入 — 2026-11-20

上述五项设计冲突已通过本次修订解决；Task1a claim/凭据现在冻结并授权实施，不再等待用户确认。父代理对照实际audit.service.record纠正了不存在的outcome `ok` 为 `completed`，并区分Run和scan revision上限。Task3初始化准入已实作并经父代理6项独立复跑验收；不得在租约任务重做或改写它。

审计精确合同：claim的action_id固定runtime.claim；将来的renew和停止观察均用runtime.renew。audit_fields固定(run_id,runtime_id,epoch,status,reason)，mutating=True；可用Module内部仅含这些字段的frozen审计spec，不注册普通session业务动作。refs=[asdict(Run ObjectRef)]，scope_refs为排序去重后同形的dict列表。claim reason固定claimed，正常续租renewed，停止reason只用上文stop_observed/lease_expired/authorization_revoked；未领取的扫描及身份识别不记业务Outbox。

候选provider拒绝的统一解释：请求报告为四扩展provider时设备级409；一个候选Run的当前/快照provider不合格只跳过该候选，不暴露其ID或原因。默认可信verifier返回False不扫描、不写游标、不派发。仅本地测试注入可信验证，不能把测试许可包装成生产执行能力。

已核实磁盘迁移叶节点为execution/0002_remove_run_one_active_manual_run_and_more.py、agents/0003_runtime_binding.py；新正常迁移0003_runtime_lease依赖这两个实际节点。Task1a只拥有其列明的六类文件，其他工作线分别审查investigation HTTP与workflows实例；不得改urls/settings/schema、旧测试、admission或兄弟模块。除新专项外，可运行execution限定迁移dry-run及check；全量和根npm由父代理批次统一。Task1b与Task2仍等Task1a功能验收，事件/恢复/Worker/真实Copilot执行仍未实现。本文修订是静态合同复核，未声称租约测试已运行。

## Task1a 有界实施拆分 — 2026-11-20

首轮Task1a代理读取后提前结束，临时未完成文件由其删除；父代理复核磁盘尚无protocol/leases/0003或新增测试，现有Run/Intent定义保持。没有确认的外部阻塞，不能记录为已实施。为取得可验收增量，拆为以下连续小段，原Task1a六组整体验收要求保留。

**Task1a1：数据模型、DTO与只读任务身份。** 允许execution/models.py、新protocol.py、新leases.py、新正常0003_runtime_lease.py、新tests/test_runtime_task_identity.py。模型/DTO字段严格沿上文；leases只实施authenticate_task(secret)->TaskIdentity和所需内部验证，不先写claim/renew占位或公开凭据铸造入口。秘密只接受wp_task_加64位小写hex；用hash定位当前未撤token、未撤Runtime、expires_at严格大于本次采样aware UTC now。返回runtime/workspace/run/epoch/token标识，无secret/hash/正文。此函数仅识别，不查询成员/绑定/来源或改变Run状态；后续claim/renew仍在各自事务重验。

本段测试可用真实配对Interface取得Runtime、start Interface取得deferred Run，再仅在fixture向新TaskToken表放入已知秘密hash，明确不是生产签发能力或claim验证。至少四个独立方法：合法身份与frozen DTO/无秘密；非法类型/格式/Runtime或pairing凭据/未知hash统一401；精确过期等号、撤token及撤设备401，非法clock400；全部成功及拒绝读取无表行变化，成员或绑定/lease状态变化本身不替代token身份校验。另核验新Run默认epoch0/owner与期限空、一Run仅一个有效token/撤销后可新建。正常生成迁移后运行test_runtime_task_identity及已有test_execution_admission，不跑全量。migration dry-run/check和85保护照旧。迁移历史升级完整矩阵仍归Task1a2整体验收，本段不冒称完成它。

**Task1a2：领取、持久扫描与原六组完整验收。** 依赖1a1验收，复用这些模型/DTO/身份Interface实施claim；新增test_runtime_lease_claim.py，保留1a1测试。授权、可信能力、CAS、审计、真实两连接、历史升级及秘密保护合同完全不减；此段另行调度，之前Task1a整体保持未完成。

### Task1a1 监督验收与领取实施边界

模型、frozen DTO、只读authenticate_task和正常execution0003迁移已实施。Sol新5项+既有admission13项共18项通过；父代理读全部实现、迁移及测试后，在B身份5+C实例12+D HTTP13共30项联合专项中独立复跑通过，/tmp/workpal-bcd-small-parent.log，exit0。Task1a1功能验收通过；凭据来自明确的测试fixture，不能据此声称生产签发/claim已可用。85保护仍为既知两项差异。

为保持后续任务有界，Task1a2分为领取实施与独立验收两轮：**1a2a**只修改execution/leases.py，新增tests/test_runtime_lease_claim.py，按上文完整授权、可信验证、扫描、CAS与审计合同实现claim，不改已验收模型/DTO/身份公开语义。至少三个核心测试：默认能力拒绝且无扫描写入、真实配对/绑定/deferred Run在本地可信seam下领取并authenticate成功（精确状态/epoch/期限/快照与审计）、前32受限候选后第33可领取及重连续扫。严格report非法矩阵可并入第一组；不开放生产测试开关。**1a2b**随后独立补齐当前/历史/新增资源授权、真实两连接竞争、实际record后回滚、旧库升级与完整秘密保护，不修改或削弱上述核心测试。只有两轮均通过才完成原Task1a六组要求。renew/HTTP继续等待。

Task1a2a实施检查点：claim核心与三个TransactionTestCase已落盘，默认可信verifier=False。父代理读完整领取实现和3项测试后，在B8+D16联合24项中独立复跑退出0，/tmp/workpal-evidence-claim-parent.log。已证明本地可信seam下基本领取/识别、默认拒绝、32+1重连扫描；不替代当前授权竞争及故障验证。未发现已确认需立即修改的产品缺陷。

Task1a2b独立审查仅新增tests/test_runtime_lease_claim_review.py，可对发现的实际缺陷最小修execution/leases.py，不能改原8项/模型/迁移/公共接口。四组交付：①Run.created_by与Runtime配对管理员不同，当前成员/独立Agent及精确历史要求/历史与新增资源write拒绝、不变原快照，设备撤销/改绑与provider失格，普通无权扫描只变scan不产生token/业务审计；②文件SQLite双连接同时claim、一次lease/token/audit/outbox与scan CAS，无双派发；③真实audit.record写后503全表回滚/重试，可信检查503或非法类型不吞、溢出零写、secret/hash/正文不进audit/cache；④隔离execution0002历史schema创建既有Run/Intent并升级0003，旧快照/行保留、新lease默认空/0，重复迁移不改数据。只跑新模块+原8、限定迁移/check/85hash，日志/tmp/workpal-lease-claim-review-*.log。全部四组才判Task1a整体；renew未实现。

保护更新：用户已确认studio.js精确差异；沿parallel-delivery最新确认及protection-exceptions.json核对85项，不再因历史“待确认”措辞阻塞后端。原基线不改。

## Task1a 功能验收与 Task1b 实施准入 — 2026-11-20

Sol独立审查新增10项；父代理读完整实现与测试后补齐候选级verifier的503/非法返回回滚、合法False隐藏候选及后续可领取，另检查真实输入正文/Runtime与Task凭据/hash不进入领取审计/Outbox/缓存/错误和日志。新模块采用模块fixture引用，避免单模块发现重复计数。三模块20项独立复跑通过（12审查+3领取+5身份），/tmp/workpal-lease-claim-parent-final.log，exit0。补测首次绿如实记录，未改生产实现。Task1a功能验收通过；默认可信能力仍False，不能据此宣称真实派发。

Task1b现准入实施，仅leases.py与新test_runtime_lease_renew.py。按上文固定优先级和六组行为实施，原20项保留；不要留下renew占位后停止。允许内部拆出共用now身份解析，public authenticate_task仍只读原合同，每次renew事务尝试只取一个now。

返回/错误精确化：已定义身份401、对象404、stale_epoch/lease_conflict409为Denied(code,status)，从事务正常返回且零写；调用方类型/严格整数/clock/overflow和非法verifier返回沿DomainError400，存储及审计503和非预期异常传播并回滚。先识别secret，再严格检查run_id/epoch类型和范围，然后查身份对应Run及URL/epoch；无效凭据不提供目标信息。所有Run状态以当前表值判断，不能依赖传入DTO。终态优先于到期，停止结果提交后才返回，不能用已撤权的人类read生成响应。

本轮至少四个独立核心方法涵盖：正常轮换与旧token失效/唯一有效凭据/45与60秒；身份/URL/epoch/终态优先级零写；已有cancel/recovery和lease到期一次停止，旧token后续401；成员/来源/绑定/能力撤销后的停止审计保持全部历史及新增限制，真实record后503回滚。六组完整并发矩阵保留后续独立审查，不以核心绿灯冒称Task1b完成。HTTP、事件、Worker及真实Runtime均不在本轮。

## Task1b 核心复核与独立审查 — 2026-11-20

renew已落盘，含当前身份和状态优先级、一次性轮换、停止提交及元数据来源遍历。父代理阅读全部实现和4核心测试，独立四模块24项退出0，/tmp/workpal-lease-renew-parent-core.log。发现原撤权测试对所有模式都使用verifier=False，可能掩盖权限检查缺失；父代理仅将非capability模式改为True，强化后核心4项复跑退出0，/tmp/workpal-lease-renew-parent-strengthened.log。未改变产品实现。

Task1b仍未完整验收。独立审查新增tests/test_runtime_lease_renew_review.py，保留旧24项；实际产品缺陷先用公开renew复现，最小修leases.py。重点：停止与正常轮换精确audit/scope/token/状态；45/60等号和所有身份/epoch/终态优先级；来源/成员/新资源/绑定/provider各独立撤销（其余权限和verifier保持合法）；真实SQLite两连接renew/renew、cancel/renew、unbind/renew线性化及重试；当前授权或verifier503/非法结果与损坏scope全表回滚，成功及停止实际audit写后失败；输入正文/秘密不进审计缓存、旧token响应丢失不能重发。不得以几项包含多个弱分支的绿灯替代明确合同，也不得为旧正确行为补造红灯。仅显式五模块专项、execution迁移check、system check和85精确例外核验。HTTP、事件和真实执行继续等待。

独立review新增13项，真实复现正常轮换未验证旧scope引用；最小修复复用元数据校验后，父代理五模块37项独立复跑exit0，/tmp/workpal-lease-renew-parent-review.log。Task1b仍待剩余实际cancel/renew和改绑/renew双连接竞争、新资源与跨区scope、授权错误过滤及完整秘密输出矩阵。新增test_runtime_lease_renew_final.py只做这些残留，不重复37项当新增证据；实际缺陷可最小修leases.py，旧测试保留。

续租final追加5项精确授权错误码过滤检查，父代理读代码并六模块42项复跑退出0，/tmp/workpal-lease-renew-parent-final42.log。只增加错误过滤证据，未增加真实取消/改绑竞争；Task1b未验收。下一新test_runtime_lease_renew_races.py仅负责cancel/renew及bind/renew真实两连接两种提交顺序与竞争；scope新资源/跨区/容器及完整输出检查另一个有界后续，不把42绿灯替代。

## Task1b 竞争监督验收及最后两组 — 2026-11-20

独立races新增6项，两种改变各有实际双连接竞争与两种提交顺序。父代理在任何显式重试前补充首次两请求的完整表快照检查：非允许表不变；Run状态/revision/快照、token数量和撤销、Agent/Binding revision与目标、audit/outbox增量必须精确对应实际成功请求。原有失败409单独重试零写及最终原凭据401零写保留。强化后七模块48项独立通过，/tmp/workpal-lease-renew-parent48.log。并发环境不能将其他成功事务的写入误算为失败事务部分写，本轮用完整合法提交集合与串行失败重放共同验证。

父代理另通过公开renew复现损坏scope容器问题：JSON null抛TypeError、空对象可被当成空列表并提交。新增test_runtime_lease_renew_final中的一项独立方法覆盖null/对象/空数组/字符串/数字/布尔与正常、停止两路径；最小修为scope_refs必须非空list，不改变合法scope。真实红灯/tmp/workpal-lease-scope-container-red.log；修复后七模块49项通过，/tmp/workpal-lease-renew-parent49.log。迁移/check及85保护零意外差异，见/tmp/workpal-supervision-renew-query-*.log与protection.json。

Task1b只剩两组独立验收，新增tests/test_runtime_lease_renew_scope_output.py，不重复改原49项：①领取后新增资源权限正反对照、成功轮换scope包含新增资源及旧历史根、已保存对象追加根后撤权停止仍保留完整限制；损坏跨workspace引用在正常/停止路径503全表回滚，修复后原token仍可用。停止scope沿上文精确元数据合同，不凭空读取未曾保存的新资源正文。②成功/停止/Denied/400/503的响应、审计、Outbox、幂等/进程缓存及捕获日志秘密矩阵，输入正文、旧/新Task secret及hash、Runtime凭据均不得意外保存或返回；正常Renewed的唯一新task_token字段是授权返回，不把这项合法返回算泄漏。记录实际audit失败回滚与原token重试证据可复用旧测试，不能以mock授权替代真实scope行为。实际缺陷先公开复现再最小修leases.py。此两组通过并由父代理复核后才验收Task1b，HTTP/事件/Worker/真实Runtime尚未实施。


## Task1b 功能验收与 HTTP Task2 实施准入 — 2026-11-20

最后scope/output新增4项，父代理读完全部测试，补充成功轮换必须包含新增Resource对象引用（不只其来源根）的断言；八模块53项独立通过，/tmp/workpal-lease-renew-parent53.log。覆盖新增资源准入正反例、保存对象追加根后的停止限制、跨区损坏回滚及原token重试、输出/日志/缓存秘密矩阵。Task1b功能验收通过；Task1a与初始化准入此前已验收。默认可信verifier=False保持，无真实执行。迁移/check见/tmp/workpal-bd-accepted-{migrations,check}.log。

HTTP Task2现在准入，urls独占窗口分配给本任务，A只动web资产，D只设计。只新增execution/runtime_http.py、tests/test_runtime_lease_http.py，config/urls.py追加两条明确路由，execution/README.md追加真实范围。不改leases/protocol/agents/session/Registry/共享schema。Interface路径、DTO和POST合同按前文；没有事件/日志/stop路由。

补充冻结传输细节：
- Host校验、POST检查先执行；然后只从Authorization读取单一 `Bearer <secret>`，scheme固定Bearer，秘密严格wp_runtime_或wp_task_及64位小写hex。缺失、多值/逗号/额外空白、错误凭据种类401；cookie/session不能替代。完整当前身份始终交核心从原始secret重验，不预造Identity。
- JSON body只接受封闭字段，Content-Type application/json、无query。claim外层{version,capabilities}，capabilities精确5字段与CapabilityReport同形；renew外层{version,epoch}。外层及内层version严格int=1，外层已知不支持整数版本409 capability_unavailable，bool/其他类型400；provider和其他报告类型由核心同合同验证。不能接受workspace/actor/scope/clock/cursor。
- Content-Length若存在必须非负十进制，超过16384直接413；实际读取最多16385探测字节，超额413，不先无界request.body。UTF8/重复key/非有限JSON/非对象/非法Unicode及多余字段400。真实大小等号与+1对照，不能只测错误Content-Length。
- 成功claim 200直接ClaimResult序列化；Renewed和StopOnly 200直接对应DTO，aware UTC时间ISO字符串。Denied按自身status返回该DTO，绝不重查已经撤权的用户内容。DomainError只映射固定已知code/status及常量message，不回显任意exception消息/属性；未知异常500 internal_error常量。若核心意外给出未定义错误码，不把它当权限失效或反射到HTTP正文。
- 两端点所有自己的成功及错误响应no-store/nosniff。仅这两bearer入口CSRF豁免，既有session管理入口和通用Registry仍保持真实CSRF要求。无CORS放宽，无运行Provider开关。调用核心完成提交后再序列化响应，丢响应不能恢复旧凭据或重新派发。

按前文六组完成独立真实HTTP验证（建议6~8方法，不能只测view内部）：密码登录/CSRF真实配对取得Runtime bearer，Registry绑定和start真实创建Run，在本地可信seam下claim→renew→停止及状态/audit/outbox/token；默认可信False真实拒绝；凭据种类/过期/撤销/跨Run/epoch与session对照；严格body/Host/method/bounds；响应被丢弃后的原凭据重试无重放、固定错误秘密检查；真实record写后503回滚与原凭据重试。后续事件/日志/stop404且generic Registry拒task bearer作为对照。禁止用fake核心成功DTO代替主闭环；fixture可调用公开Direct建业务，但配对和核心端点必须真实HTTP。

先运行真实claim路由404红灯，再实施并原测试绿。回归显式新模块+原八个lease模块53及tests.test_runtime_http7，不扩全量或根npm。execution迁移dry-run、system check及85精确保护。日志/tmp/workpal-lease-http-*.log。Task2独立验收后才推进事件/恢复，真实Runtime仍未实现。


### HTTP Task2 草稿复核与真实闭环分段 — 2026-11-20

首轮新runtime_http、两路由和README已落盘，仅新增路由测试1项；其61项回归为旧60+新1，不是六组HTTP行为验收。父代理读实现后通过真实HTTP调用/仅注入核心异常的映射测试复现storage_busy被映射500（合同要求503），/tmp/workpal-lease-http-parent-busy-red.log退出1；最小追加固定storage_busy消息/503映射。此测试只证明HTTP错误投影，不冒称真实数据库竞争或配对闭环。修后与旧Runtime HTTP基础专项日志/tmp/workpal-lease-http-parent-basic.log，85精确保护/tmp/workpal-lease-http-parent-protection.json无意外差异。Task2仍未验收。

下一Task2a仅新增tests/test_runtime_lease_http_flow.py，三个真实闭环组：①密码登录/CSRF配对取得bearer、Registry绑定与start，默认verifier=False拒绝无派发，在本地可信seam下HTTP claim→renew→当前成员撤销后StopOnly，严格SQL Run/epoch/revision/token/audit/outbox与旧token重复401；②合法独立fixture上Runtime/Task凭据错入口及cookie/session不能替代，真实session配对管理缺CSRF拒绝、通用Registry不认Task bearer，正确配对/接口作为正向对照；③实际audit.record写后503分别覆盖claim/renew全表回滚、原凭据重试唯一，并丢弃真实响应验证旧轮换凭据不能取得新token。允许实际产品红灯最小修runtime_http.py，不改租约核心或其他模块。原父代理两个测试与旧60保持。先完三组，不再在路由层停止；原六组其余严格传输/完整时间错误/秘密矩阵单独Task2b后续，不删除验收要求。事件/恢复/真实Runtime未做。

### HTTP Task2a 监督检查与 Task2b 准入 — 2026-11-20

父代理已读新3方法与完整HTTP适配器，独立重跑新flow+lease_http+runtime_http共12项，/tmp/workpal-lease-http-parent-flow.log exit0。真实配对、领取/轮换/撤权停止、凭据与session分离、实际record写后503回滚及旧token拒绝成立。现有response loss方法在读取响应内容后删除变量，只能说明旧token不能重用，不能替代“客户端未接收新token”的边界证据；保留旧测试，下一段强化而不改名冒称完成。Task2整体未验收。

Task2b现在准入，仅新增tests/test_runtime_lease_http_boundaries.py；实际公开HTTP红灯允许最小修execution/runtime_http.py，不改核心leases/protocol、旧测试、models/迁移、urls、Registry或身份模块。保留默认verifier=False，正向领取只在测试本地可信seam下。三组有界验收（建议6至9个独立方法，禁止继承旧TestCase重复计数）：

1. 严格传输：两个真实Client端点的Host/method/query/content-type、封闭shape/type/重复JSON键/UTF8/surrogate/非有限值、未知version、严格Bearer和凭据种类；合法请求作正向对照。真实raw body 16384/16385字节对照；Content-Length缺省、非法和超长数字（含大量前导零）不抛未脱敏500。使用受控stream直接view补证最多读取16385探测字节，明确不是HTTP集成替代。拒绝前后业务全表不变；不允许靠mock核心成功覆盖全部请求解析。
2. 当前凭据与时间：真实claim所得token覆盖错误Run、严格epoch及stale_epoch、Runtime/Task撤销、lease45秒与token60秒精确边界、终态优先级，HTTP状态/DTO/UTC期限同核心。只有_stop_only改变状态且精确一次，401/404/409拒绝全表不变；不声称OS停止。另发一次真实renew并完全不消费其新token响应，再用客户端唯一旧token重试，401且不重发新token，DB轮换恰一次。
3. 安全输出：Claimed/Renewed/StopOnly/Denied/400/401/403或404/409/413/503/500均no-store/nosniff；固定DomainError码/status映射及未知异常脱敏可仅注入错误seam，但与真实闭环结果区分。输入正文、旧/新secret/hash、Runtime凭据不进错误、audit/outbox/cache或捕获日志。成功唯一新task_token字段允许返回，不能把授权返回误算泄漏。错误内容绝不回显异常属性。运行新模块+既有HTTP12和八个lease模块53、execution迁移dry-run/check、system check、85精确保护；日志/tmp/workpal-lease-http-boundaries-*.log。根npm由监督批次运行。
