# Workpal Runtime Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 B1b 服务端配对、fenced lease 和可恢复事件协议，不启动真实执行。

**Architecture:** execution 拥有 Run 与协议事实，agents 拥有 Runtime 身份和绑定。一个深 Module 的小 Interface 隐藏事务、当前授权、令牌与顺序处理；不增加通用 Repository 或按动作分支的大 switch。Runtime 仅通过 HTTP 使用协议，不共享 SQLite。

**Tech Stack:** 现有 Django/Python、SQLite、Node 22.22.0；不新增依赖。

**Spec:** [B1](2026-11-20-workpal-phase-b-runtime.md)、[主设计 Runtime 协议与恢复](../specs/2026-11-20-workpal-software-development-design.md)、[已验收 B1a 与 I1](2026-11-20-workpal-parallel-delivery.md)。

## Global Constraints

- 父代理已复核Task1并授权有界实施；Task2/3仍需在前置验收后进一步冻结返回类型/恢复传输合同，不提前实施。不安装、不联网、不调用模型/Runtime、不作Git写操作。
- 保留 B1a Run/Intent 不可变输入、manual key 复用、11态和 one_active_manual_run；awaiting_input 是终态；cancel_requested/recovery_required 占活动唯一性。
- 心跳10s、lease45s、task token60s随lease续发、pairing10min单次消费；全部时间使用服务端 UTC。
- 只存 secret hash；token 不进 audit、IdempotencyResult、Outbox、日志或提示。配对/绑定不证明 Copilot 已安装、已认证或具备执行能力。
- 无 Runtime 或可信能力证明仍 deferred；不自动唤起 CLI/API 进程，不虚构 task 可用。B2 的 daemon/Linux 隔离及 B3 ProviderAdapter 不在本计划。
- 不修改 investigation、其迁移或 D lane 文件；沿现有 ObjectRef/source_refs 授权，不另造环境模型。保护基线 /tmp/workpal-supervision-baseline-20261120.json 的85项与既有 .gitignore 差异。
- 本计划不要求提交。未来修改交互仍须 npm run check；文档交付不重建 dist。

## Review Focus

1. 配对响应丢失：不缓存明文重放，管理员重新签发并撤销旧身份（Task 1）。
2. 当前资源新增或来源撤权：不得只验快照；新领取、续租和任务动作均拒绝（Task 2）。
3. token仍未到期但lease已过期：拒绝业务写入，不推断进程停止（Task 2）。
4. 序列稀疏攻击：有界窗口/批次，不能制造无限 missing 或内存分配（Task 3）。
5. 取消与完成交叉：持久化停止事实优先，不能撤销取消意图或覆盖历史（Task 3）。

---

## 冻结模型与共同 Interface

现有名称：execution.models.Run/Intent；agents.models.Agent；contracts.Actor(user_id,workspace_id,executor_id=None,session_id=None)、DomainError；storage.atomic_write；access.service.authorize/register_object/derive_scope；identity.service.require_member；audit.service.record。没有现成 TaskToken 或 Runtime identity，不得把以下新名字当既有实现。

所有新增 FK 除注明外 on_delete=PROTECT，主键沿现有 BigAutoField；workspace FK identity.Workspace，用户 FK settings.AUTH_USER_MODEL；revision PositiveIntegerField(default=1)，修改用 CAS，溢出拒绝 invalid_input。跨 workspace FK 在写事务中验证；不能靠 FK 自动保证租户一致。

- agents.Runtime：workspace、created_by、name(Char200)、credential_hash(Char64 unique)、revoked_at(nullable datetime)、revision、created_at；注册普通派生ObjectRef('runtime',str(pk))，不设置is_source，不隐式创造权限根或全区授权。管理角色门禁由Module/Registry执行，来源机制沿现有access。
- agents.RuntimePairing：workspace、created_by、name(Char200，签发时冻结)、secret_hash(Char64 unique)、expires_at、consumed_at(nullable)、runtime(nullable OneToOne Runtime)、revision。随机32字节以上secret，SHA256仅对高熵opaque secret；不使用用户密码替代随机凭据。
- agents.RuntimeBinding：workspace、agent(FK Agent)、runtime(FK Runtime)、enabled(bool default true)、revision；unique(workspace,agent)，只选一个目标；解绑仅 disabled，不删除历史。
- execution.Run 新增 lease_owner(nullable FK agents.Runtime)、lease_epoch(PositiveBigInteger default0)、lease_expires_at(nullable datetime)、event_cursor(PositiveBigInteger default0)、evidence_incomplete(bool default false)。Run.revision覆盖状态/租约更新；不改变 input_snapshot/sha256。
- execution.TaskToken：run(FK Run)、runtime(FK Runtime)、epoch(PositiveBigInteger)、secret_hash(Char64 unique)、expires_at、revoked_at(nullable)。旧token续发时撤销；不保存原文。
- execution.RunEvent：run(FK Run)、epoch、sequence(positive integer)、payload(JSON)、sha256(Char64)、created_at；unique(run,epoch,sequence)。hash使用 execution.service.digest 的 canonical JSON；有限JSON、合法Unicode先验证。
- execution.StopFact：run(OneToOne Run)、epoch、runtime(nullable FK Runtime)、confirmed_by(nullable user FK)、kind(Char32: process_exit|admin_verified_stop)、details(JSON)、created_at。details只允许 process_identity、exit_code、reason、evidence_ref；排除任意日志/secret。Runtime声明须通过当前绑定身份并关联已记录进程身份；管理员声明必须具体证据引用与理由，不能只点“超时”。

Task1在agents.runtime_identity内定义frozen RuntimeIdentity(runtime_id:int,workspace_id:int)；Task2的execution.protocol引用该类型，不在Task1依赖尚未存在的execution协议文件。Task2/3再定义TaskIdentity(runtime_id:int,workspace_id:int,run_id:int,epoch:int)、Lease(run_id:int,epoch:int,expires_at:str,input_snapshot:dict,allowed_actions:tuple[str,...],task_token:str)、Ack(cursor:int,missing:tuple[tuple[int,int],...],evidence_incomplete:bool)。所有HTTP输出序列化为JSON，missing是闭区间。任务身份由服务端hash查询生成，拒绝客户端actor/workspace覆盖。TaskIdentity不代替Actor：每次从Run.created_by_id构造当前Actor，再验require_member、Run来源和当前配置。

错误统一 DomainError：invalid_input400、authentication_required401（bearer）、permission_denied403、not_found404（不泄露其他租户）、revision_conflict/idempotency_conflict/lease_conflict/stale_epoch/sequence_conflict/recovery_required/capability_unavailable409、input_too_large413、storage_busy/storage_unavailable503。协议版本只接受1，否则 capability_unavailable。错误无secret、原始payload或凭据hash。

## Task 1: 管理员配对、Runtime身份与Agent绑定

**Files:** Modify `services/workpal/workpal/agents/models.py`, `apps.py`（仅追加注册）；Create `agents/migrations/0002_runtime_identity.py`, `agents/runtime_identity.py`, `agents/runtime_actions.py`, `agents/runtime_http.py`, `agents/RUNTIME.md`（agents根为services/workpal/workpal/agents/）；Modify `services/workpal/config/urls.py`仅追加两路由；Create `services/workpal/tests/test_runtime_identity.py`。不改现有agents service/actions、execution Module、settings、公共README或既有测试。用makemigrations agents --name runtime_identity生成正常迁移。

**Interfaces:** 新建runtime_identity.issue_pairing(actor,name)->dict、read_pairing(actor,pairing_id)->dict、consume_pairing(secret)->dict、authenticate_runtime(secret)->RuntimeIdentity、read_runtime(actor,runtime_id)->dict、bind(actor,agent_id,runtime_id,revision)->dict、unbind(actor,agent_id,revision)->dict、revoke(actor,runtime_id,revision)->dict。

issue仅返回pairing_id/secret/expires_at；consume返回runtime_id/runtime_token，Runtime.name固定为签发的名称，不接收客户端改名。read_pairing返回pairing_id/name/expires_at/consumed(bool)/runtime_id（未消费0），管理员可在消费响应丢失后查到身份并撤销，无须读取旧secret。read_runtime/revoke返回id/workspace_id/name/revision/revoked(bool)，允许管理员读取已撤销的元数据。bind/unbind返回agent_id/runtime_id/revision（更新后的Agent.revision）/binding_revision/enabled。所有DTO无credential_hash/secret_hash。首次绑定Agent.revision CAS+1，新Binding.revision=1；改绑/解绑Agent及Binding各+1，不改旧Run快照或创建Run。解绑须有现有enabled绑定，否则409；已撤销Runtime不得绑定。revoke首次有效CAS+1，之后同key缓存返回原事实；已撤销且以当前revision新key调用返回原元数据，不再改行，旧revision仍409。

所有管理读写均当前owner/admin成员；签发/bind/unbind/revoke额外拒绝非空actor.executor_id，避免执行器取得人类设备管理权限。bind/unbind检查当前Agent与目标/现有Runtime的write；所有读取均检查对象read；Registry resolver在缓存前重复当前角色/来源门禁，不能只在handler检查。Pairing消费前重新检查签发者仍为该workspace有效owner/admin；权限已失效则403且不消费。Runtime凭据成功建立后作为workspace设备身份独立存在，直至显式revoke，不把creator冒充每次请求的运行用户；claim/renew再检查Run.created_by的当前授权。

Registry新增runtime.pairing.read/runtime.read/runtime.bind/runtime.unbind/runtime.revoke，payload分别为pairing_id、runtime_id、agent_id/runtime_id、agent_id、runtime_id。bind/unbind/revoke为mutating、revision_required；读无revision/确认/业务outbox。所有allowed_roles owner/admin；audit_fields仅对象ID。单独runtime_actions注册，不修改既有Agent DTO或能力字段。

秘密签发不用Registry，避免幂等结果缓存：POST `/api/v1/workspaces/<int:workspace_id>/runtime-pairings`，真实session+CSRF，封闭JSON body{name}；POST `/api/runtime/v1/pair`，封闭JSON body{version:1,secret}，仅secret认证、不回退cookie/session，只豁免这一个endpoint的CSRF。均Host校验、POST限定、JSON限16KiB/重复key和额外字段拒绝、no-store/nosniff。管理员签发与consume均调用现有audit.service.record，提供仅含ID的内部spec/payload，置于同一atomic_write；consume审计归签发者并记录pairing_id/runtime_id，绝不把秘密result或原请求送入持久缓存。

Pairing secret与Runtime token各使用独立前缀及至少32随机字节、只保存各自SHA256；类型/长度封闭验证，跨凭据类型拒绝。无效或已撤销Runtime凭据401。未知配对secret401；已知配对过期或已消费409 pairing_unavailable（不回原token）；过期边界expires_at<=clock()。消费双连接CAS consumed_at=None且expires_at>now，同事务创建Runtime、注册runtime ref、审计/Outbox；失败全部回滚，同secret可重试。鉴权无业务写或outbox，不返回hash。丢响应管理员通过read_pairing查询runtime_id后撤销并重签，无后台自动恢复明文。

- [ ] Step1 先写真实session管理员POST签发的HTTP行为测试，当前404为红灯；不能import不存在的模型算红灯。实现上述模型、管理Interface和两HTTP入口，同测转绿。时钟internal seam为runtime_identity._clock默认timezone.now，测试替换为aware UTC callable，不sleep。
- [ ] Step2 `test_pairing_two_connections_consumed_once`：真实两文件库连接同时消费，一Runtime/注册对象/一次消费audit与outbox，失败409；`test_pairing_expiry_response_loss_and_issuer_revocation`：600秒边界拒绝、读配对只能取metadata找回runtime_id、丢响应不返回旧token、issuer降角色/撤成员/停用后不可消费且无副作用。
- [ ] Step3 `test_runtime_secret_never_cached_or_audited`：两个原secret不出现在业务字段（hash列只为digest）、audit/outbox/cache/confirmation/捕获日志与错误；只在签发/消费成功瞬时响应出现。`test_pairing_http_identity_csrf_and_tenant`：真实密码登录/CSRF轮换、成员/匿名/Host/方法/Content-Type/重复JSON/16KiB/跨区对照；pair不以cookie替代secret且错误不回显。
- [ ] Step4 `test_binding_unbinding_and_revoke_current_authority`：Direct及Registry角色/executor/跨workspace/Agent来源撤read或只撤write、Runtime撤权/撤销；当前Agent revision CAS、两连接同revision绑定竞争、同key重放及撤权重放，解绑不删历史，revoke鉴权立即失效，业务/来源/审计都恰当回滚。`test_binding_is_not_provider_capability`：绑定/解绑/撤销都不新建Run或改变旧快照，start仍deferred，四扩展provider仍不可执行。
- [ ] Step5 `test_pairing_audit_outbox_failure_rolls_back`：包装实际record写audit/outbox后503，签发与消费两路径的Runtime/Pairing/访问注册/审计/outbox全表回滚；消费原secret恢复后精确一次。`test_management_reads_and_authentication_are_bounded`：严格ID/revision/token类型边界、管理员读拒绝hash、Registry只读audit无outbox，authenticate无业务写。至少八个独立test方法，保留全部原B24，不继承含test方法的类。
- [ ] Step6 运行`.venv-workpal/bin/python services/workpal/manage.py test tests.test_runtime_identity tests.test_agent_configuration tests.test_execution_admission tests.test_execution_admission_review tests.test_execution_final --noinput`、`makemigrations agents --check --dry-run`、Django check、Node23及85项保护。正常新迁移、临时库，禁止用户DB；不跑全量或兄弟在途迁移检查。日志`/tmp/workpal-b1b1-*.log`，RUNTIME.md写真实范围，完成全部步骤交父代理验收，不派发。

## Task1 有界实施检查点 — 2026-11-20

第一次B1b1实施代理只阅读、未修改文件或运行验证，不计完成。为让独立交付可验收，将原Task1按Interface分两段；下述Task1a范围优先于原Task1一次完成全部内容的调度，原业务合同保留。

### Task1a：一次性配对与Runtime身份核心

**Files:** 仅允许agents/models.py、新runtime_identity.py、RUNTIME.md、正常生成0002_runtime_identity.py、新tests/test_runtime_pairing.py。路径均沿上文services/workpal；不改apps、urls、旧Agent实现/测试或execution。只创建Runtime、RuntimePairing，不提前创建RuntimeBinding。

**Interfaces:** issue_pairing/read_pairing/consume_pairing/authenticate_runtime/read_runtime/revoke及RuntimeIdentity；参数、返回字段、权限、600秒、凭据hash、对象登记与审计原子性严格沿Task1。revoke Direct与其他变更需人类管理员和CAS；Registry审计由Task1b接入，避免未来重复审计。签发/consume无Registry，仍在本Module同事务record最小ID事实/Outbox。内部时钟seam按上文。不提供HTTP或Registry动作。

- [ ] Step1 新增公开Interface行为测试和最小NotImplementedError占位，观察行为失败后实施；不以缺import替代行为红灯。
- [ ] Step2 实现签发→consume→authenticate→管理员read_pairing定位Runtime→revoke→authenticate拒绝完整核心闭环，秘密仅返回一次。保留固定name及当前issuer角色检查。
- [ ] Step3 至少6个独立测试覆盖：核心秘密与未缓存；600秒边界/响应丢失/issuer降角色；当前人类角色/跨区/输入/token类型/对象授权；真实两连接consume唯一性；实际audit/outbox写后故障的签发和consume全表回滚及重试；revoke CAS/重复与管理读/认证无业务写。使用普通TestCase或TransactionTestCase，不导入TestCase类造成重复发现。
- [ ] Step4 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_runtime_pairing tests.test_agent_configuration tests.test_execution_admission tests.test_execution_admission_review tests.test_execution_final --noinput`全绿，agents迁移dryrun/check和85项hash，日志`/tmp/workpal-b1b1a-*.log`。更新RUNTIME.md的真实未接HTTP/绑定范围，交监督验收。

### Task1b：HTTP、Registry与Agent绑定

依赖Task1a验收后，新增RuntimeBinding及下一迁移，完成原Task1剩余apps/两条URL、runtime_actions/runtime_http、bind/unbind与原Step3/4 HTTP及绑定矩阵。新的test_runtime_identity.py复用Task1a公共Interface，原Task1a测试保持；原Task1只有两段全部验收后才完成。Task2/3依赖完整Task1，不能因核心配对通过就开始派发。

## Task 2: 服务端领取、续租、fencing与当前权限

**Files:** Modify `services/workpal/workpal/execution/models.py`, `service.py`; Create `execution/migrations/0003_runtime_lease.py`, `execution/protocol.py`, `execution/leases.py`, `execution/runtime_http.py`, `services/workpal/tests/test_runtime_leases.py`; Modify `services/workpal/config/urls.py`。依赖Task1身份，独立验收lease，不依赖事件实现。

**Interfaces:** leases.claim(identity:RuntimeIdentity,capabilities:dict)->Lease|None；renew(identity:TaskIdentity)->Lease；authenticate_task(secret)->TaskIdentity。内部 `_clock` callable默认timezone.now。POST /api/runtime/v1/claim，runtime bearer，body{version:1,capabilities}；POST /api/runtime/v1/runs/<int:run_id>/renew，task bearer，body{version:1,epoch}。Bearer端点仅豁免自身CSRF，不接受session回退；URL run必须匹配TaskIdentity。空claim输出{lease:null}。

capabilities封闭对象 provider_key/version/installed/authenticated/execution_ready；provider_key仅copilot_cli，其余字段严格类型；B1b未接B2/B3可信探测时 execution_ready 不能仅凭自报成为生产能力。测试通过注入 leases._verify_capabilities(identity,capabilities)->bool 的内部 seam，默认False；真实实现由B2/B3另验收。Lease.allowed_actions暂为空tuple，token只用于本协议续租/事件，不可调用Registry/merge或任意业务动作。

- [ ] 写 `test_two_claimers_one_lease`：两真实SQLite连接+同步起点，只有一个CAS赢得同Run epoch1，另一个null/503可重试，重试不得多出lease；不以select_for_update冒充SQLite互斥。
- [ ] 写 `test_revoked_actor_source_agent_resource_cannot_claim_or_renew` 参数矩阵：成员删除/用户停用、历史来源撤write、Agent来源撤write、当前项目新增受限资源、Runtime撤销/解绑，全部拒绝且无新token。使用现有 admission_refs/selected及公开资源读取重新验当前配置，不改历史快照。
- [ ] 写 `test_expired_lease_rejects_live_token_and_old_epoch`：推进45秒后，即使token还有15秒亦拒绝；不得新claim；旧epoch写409；续租在有效期内固定续到now+45s/token now+60s并撤销前token。
- [ ] 写 `test_claim_after_actual_audit_outbox_write_rolls_back`：实际record成功后抛错，Run/epoch/token/审计/outbox全回滚；`test_runtime_bearer_http_scope` 断言task不能claim、runtime不能renew、cookie无效、跨run拒绝，secret不回显。
- [ ] 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_runtime_leases --noinput`，仅接受行为失败为红灯。
- [ ] 实现atomic_write内CAS、当前权限、token发放与审计，secret只在响应内。claim直接扫描deferred候选且验证能力后原子转dispatched；不要求修改service.start签名或重做快照。租约过期转recovery_required，不回queued；续租发现撤权转cancel_requested并停止发token，控制响应仅给cancel，不再给输入。身份撤销后的停止报告走Task3恢复路径。
- [ ] 重跑全绿。Worker最小接线暂不需要：claim自身就是事务派发入口，Outbox只是持久通知，不能把每条业务Outbox当派发命令消费。定时过期扫描归Task3，不能在请求中启动进程。

## Task 3: 有界事件、取消确认与恢复

**Files:** Modify `execution/models.py`, `protocol.py`, `runtime_http.py`, `service.py`（同前缀）；Create `execution/migrations/0004_runtime_events.py`, `execution/events.py`, `execution/recovery.py`, `services/workpal/tests/test_runtime_events.py`, `services/workpal/tests/test_runtime_recovery.py`; Modify `execution/actions.py`, `services/workpal/config/urls.py`; Create `services/workpal/workpal/worker.py`, `services/workpal/workpal/management/commands/runworker.py`。依赖Task2 lease；Worker包含在本任务独立验收，不再拆第四任务。

**Interfaces:** events.append_events(identity:TaskIdentity,epoch:int,events:list[dict])->Ack；recovery.confirm_stop(identity:RuntimeIdentity,run_id:int,epoch:int,fact:dict)->dict；recovery.verify_stop(actor,run_id,epoch,revision,evidence_ref,reason)->dict；recovery.expire_leases()->int。POST /api/runtime/v1/runs/<int:run_id>/events 使用task bearer，body{version,epoch,events}；POST同前缀 /stop 使用runtime bearer，body{version,epoch,fact}；已过期task不承担恢复认证。Registry runtime.verify_stop使用owner/admin、当前Run写授权、revision_required，审计证据引用；不能借恢复读取输入。Runtime已撤销则只准管理员核验，不能恢复其通用凭据。

事件为封闭{sequence,type,payload}，type=started|log|process_exit|awaiting_input；started携带process_identity字符串<=200；log携带text<=8192；process_exit携带process_identity/exit_code；awaiting_input携带process_identity/checkpoint_ref/checkpoint_complete。批次<=100、请求<=256KiB、sequence<=cursor+1000且<=2**63-1，非法全批回滚；Ack最多100个missing闭区间，窗口内缺口超过此数则以400拒绝该批，不能截断假装完整。相同sequence同canonical payload含type幂等；不同payload409并记录不含payload的冲突审计（独立拒绝事务，不保留该批业务写）。按run/epoch计算cursor，补齐后推进，missing至本epoch已接收最大序号。

- [ ] 写 `test_same_sequence_same_payload_idempotent` / `test_same_sequence_different_payload_rejected` / `test_ack_contiguous_cursor_bounded_missing`：先1,3=>cursor1/missing[[2,2]]，再2=>cursor3；重复不重复状态或审计成功事件；1001窗口/101条/大包拒绝。
- [ ] 写 `test_old_epoch_events_rejected`、`test_terminal_with_log_gap_is_evidence_incomplete`：进程退出可结束但cursor不越缺口，evidence_incomplete=True，后续补传同epoch日志可补齐但不改历史退出事实。终态只允许日志补传，不接受第二种终态覆盖。
- [ ] 写 `test_cancel_disconnected_blocks_replacement` / `test_cancel_completion_race_preserves_stop_fact`：现service.control(actor,run_id,'cancel',revision)保留签名；deferred/queued立即cancelled，dispatched等先cancel_requested；断连过期recovery_required仍阻止替代。只有同run/epoch/process_identity可信退出或管理员核验StopFact后cancelled；退出前不释放。awaiting_input必须先StopFact且checkpoint完整才能成为该终态，否则保留恢复状态并记录checkpoint_incomplete。
- [ ] 写 `test_recovery_after_permission_revocation_is_stop_only`：Runtime身份仍有效时允许最小stop事实、不返回上下文、不发token；旧epoch拒绝；无进程标识不得确认。过期后原epoch恢复报告只允许stop和有界日志，不允许状态running/续租/动作；恢复不增加epoch复活执行。
- [ ] 写 `test_events_actual_audit_outbox_failure_rolls_back`：真实SQLite双连接对同sequence并发一份事实；实际record后抛异常，Run状态/cursor/RunEvent/StopFact/AuditEvent/Outbox一起回滚；重试精确一次。`test_events_http_task_identity_csrf_scope`：session带CSRF也不能替代bearer，错run/epoch拒绝，普通Registry不能注入executor_id。
- [ ] 运行 `.venv-workpal/bin/python services/workpal/manage.py test tests.test_runtime_events tests.test_runtime_recovery --noinput`；实现事件事务和恢复Interface，内部events._clock/recovery._clock默认timezone.now；时间推进测试通过实际lease到期路径而非直接改状态。
- [ ] 实现 worker.tick()->int 仅调用expire_leases；runworker支持 --once，有界每批100行CAS，重复tick无额外事实。`test_worker_restart_expiry_is_idempotent` 在文件库重新建连接后再次tick，不重复终止或启动任务。恢复处理与审计同事务；没有网络/子进程/模型。
- [ ] 重跑本任务及B24：`.venv-workpal/bin/python services/workpal/manage.py test tests.test_agent_configuration tests.test_execution_admission tests.test_execution_admission_review tests.test_execution_final tests.test_runtime_identity tests.test_runtime_leases tests.test_runtime_events tests.test_runtime_recovery --noinput`；再运行 `.venv-workpal/bin/python services/workpal/manage.py check` 和 `makemigrations --check --dry-run`。不把继承重复计数当新增验收；保存失败与通过证据。

## 明确保留的后续工作与接线风险

Retry/Resume仍由现service.control返回capability_unavailable，不在B1b伪造实现。后续必须新Run身份、parent_run FK、自有新Intent、完整新快照和checkpoint引用；旧Run/事件/StopFact不改写；取消未确认和recovery_required不得绕过活动唯一性，awaiting_input已停止才能Resume。基础设施自动重试最多一次、认证/配置/测试失败不自动重试，连同checkpoint内容哈希验证由B2/B3及后续控制任务验收。

服务端可信停止只能依赖已认证Runtime对已登记进程身份的具体声明或管理员实际核验证据；服务端本身不能证明远端OS已停止。B2必须补进程组/启动时间/PID复用、受限凭据、spool与停止报告真实性，B3必须替换默认拒绝的能力验证seam。仅配对不能解除deferred。I1已默认注册既有agent/run动作，不重复创建注册入口；新runtime动作沿agents.apps既有ready注册路径增加，HTTP URL接线需父代理调度公共文件独占窗口，三任务不能同时编辑这些文件。

自审：上述旧函数名与当前源码一致；所有新增身份/token/lease/事件/Worker名称已显式标新。迁移编号基于当前agents0001/execution0002，实施开始若兄弟任务新增迁移须由父代理重排，不修改D模型消解冲突。本次未执行生产代码、HTTP或SQLite验收；列出的测试是实施交付条件，不是已通过结果。

父代理Task1复核：补齐原计划缺失的RuntimeIdentity定义时机、read_runtime/read_pairing/解绑Interface及返回schema，冻结配对名和响应丢失后的管理员定位路径，明确当前角色/来源/issuer撤权与审计原子性。Runtime不是新数据源权限根，签发/绑定不授予执行器人类管理身份。Task1可独立实施。

Task2/3保留下一阶段复核项：renew撤权时须提交cancel_requested但不能在同一事务内抛异常反向回滚，需用明确的Lease或stop-only响应类型；过期任务补传日志的传输入口和认证必须与stop路径区分；日志在落库前的脱敏政策及可证明的停止事实需完整合同，不能直接沿当前草案假定已解决。Retry/Resume和真实可信capability仍未实施。

## Task1a 监督验收与下一阶段 — 2026-11-20

Task1a核心验收通过：原7+监督新增6+既有B24共37项退出0，见/tmp/workpal-b1b1a-review-green.log。监督红测复现空executor绕过、503被误作403、审计状态/对象与scope遗漏；最小修复后通过。新增补测覆盖真实全行回滚、停用/移除issuer、read/write分离。原代理实现先于测试，后来进程内替换为NotImplementedError的失败不追认为先红证据；流程偏差保留。无HTTP、Registry、绑定或执行。

Task1b进一步分两个可独立验收的接线：

**Task1b1（现在实施）：HTTP与管理Registry。** 只新增agents/runtime_http.py、runtime_actions.py、tests/test_runtime_http.py，apps.py仅注册，config/urls.py只加原合同两路由，更新RUNTIME.md。不新增模型/迁移，不实现bind/unbind。注册runtime.pairing.read/runtime.read/runtime.revoke；读的角色owner/admin、capability read、无key/confirmation；revoke当前人类owner/admin和runtime write在缓存前重查，revision_required、key必填、不另加确认。结果schema与Task1 DTO一致，审计仅ID。签发/consume的原审计已由核心负责，HTTP不得重复record。

先真实POST签发404红灯，然后实现POST /api/v1/workspaces/<id>/runtime-pairings与POST /api/runtime/v1/pair。按原合同session/CSRF与仅secret配对分开，均Host、严格JSON、16KiB、重复字段拒绝、no-store/nosniff。禁止返回或缓存hash/原始请求；无cookie替代secret。至少6个独立测试覆盖：真实登录及完整配对/读取/撤销/鉴权闭环；方法/Content-Type/重复字段/超限/版本/错误无秘密；Host/匿名/CSRF轮换和缺失/成员/跨区；issuer撤权和响应丢失后的metadata定位；Registry同key重放、CAS和当前角色/executor/source撤权；HTTP实际audit写后故障全行回滚及重试。保留原13个core测试与B24。运行新专项+两core模块+B24、check/agents迁移dryrun/hash，日志/tmp/workpal-b1b1b-http-*.log。

**Task1b2（b1后）：Agent绑定。** 按原Task1 bind/unbind合同新增RuntimeBinding与下一迁移、两Registry动作、绑定并发与旧Run保持deferred验证；另给有界实施交接。完整Task1只有b1/b2均验收后才完成，租约仍不启动。

## Task1b1 功能审查与Task1b2冻结 — 2026-11-20

HTTP/Registry功能验收通过：Sol新7+core13+B24=44项通过；父代理新增3项真实严格CSRF登录→匿名pair→通用动作读取/撤销、16KiB恰好/多1字节、Registry revoke实际audit写后全行回滚及同key一次，独立运行HTTP10+core13=23项退出0，/tmp/workpal-b1b1b-parent.log。本轮未发现需修改HTTP实现的问题。当前保护文件src/studio.js另有单行菜单焦点变化，来源待确认，不属于本模块已验证实现，整体保护门禁仍未通过。

**Task1b2现可实施：** 允许agents/models.py、runtime_identity.py、runtime_actions.py、RUNTIME.md，正常新增0003_runtime_binding迁移、新tests/test_runtime_binding.py。不改HTTP/urls/settings/execution/旧测试。完整公开签名bind/unbind保持原Task1，模型RuntimeBinding字段沿共同合同。所有Direct写和Registry resolver当前人类owner/admin（executor_id非None皆拒）；Agent、目标Runtime和已有Binding指向的Runtime均当前write授权，同workspace，绑定目标已撤销返回capability_unavailable409。解绑可清理已撤销但仍可授权读取的Runtime，不冒充停止远端进程。

成功的新bind总使Agent.revision CAS+1，新Binding.revision=1，既有Binding则+1并enabled=True；同目标的新key也依同一更新规则。unbind CAS同样使两revision+1、enabled=False，不删除行；无启用绑定的新执行409。resolver可读取disabled记录核验权限，不能在缓存查询前因disabled否决已经成功的unbind重放；真正handler才检查当前enabled。所有同key返回原事实且不增revision/audit/outbox。

Registry runtime.bind payload{agent_id,runtime_id}，runtime.unbind payload{agent_id}，expected_revision对应Agent.revision；mutating/revision_required、无额外confirmation。capability write，输入refs包含Agent、目标与已有Runtime；result_refs对保存结果中的Agent/Runtime也复查当前write，保证改绑后旧key仍不能绕过原目标来源撤权。结果只含agent_id/runtime_id/revision/binding_revision/enabled，不含凭据。来源/角色/成员变化在缓存前生效；旧结果revision是历史事实，不用当前行覆盖。Direct不重复Registry审计，Registry字段仅ID。

至少6个独立测试：真实bind→重绑→unbind及同key一次；member/executor/跨区/ID/闭合字段/revision及撤销目标拒绝；Agent/目标/既有Runtime当前来源撤read与只撤write、旧key撤权重放；真实两连接同Agent revision一成功一409、同key仅一次；实际record写audit/outbox后503，Agent/Binding/来源/cache/审计全行回滚及原key重试；旧Run输入/hash/状态不改，新Start仍deferred，四extension provider仍不可执行。指定new专项+HTTP10+core13+B24（原47项）及agents迁移dryrun/check/hash，日志/tmp/workpal-b1b1b-binding-*.log。无租约/Worker/进程或模型。

## Task1b2 功能验收 — 2026-11-20

RuntimeBinding及正常0003迁移、bind/unbind Direct与Registry已实施。父代理读取实现与10个独立测试后重跑绑定10+HTTP10+core13+B24共57项，退出0，/tmp/workpal-b1b1b-binding-parent.log；覆盖双连接CAS/同key、当前与旧目标来源权限、实际审计写后全行回滚、Run快照保持及四扩展provider拒绝执行。Sol记录真实unknown_action红灯，补测首次即绿未追认测试先行。agents迁移dryrun/check通过；父代理本批根npm run check退出0，/tmp/workpal-bcd-wave-npm.log。

Task1配对、身份、HTTP与绑定功能验收通过。85项保护仍仅.gitignore既有差异与指定src/studio.js待确认改动，整体保护门禁未通过。绑定不代表可信能力，所有新Start仍deferred。Task2/3仍保留原冻结门禁；下一步单独设计租约领取/续租及撤权stop-only返回合同，先解决提交取消后抛异常回滚等矛盾，未经复核不实施租约。
