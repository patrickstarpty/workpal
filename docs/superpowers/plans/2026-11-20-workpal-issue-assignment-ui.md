# Workpal Issue Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 准确显示当前Issue负责人，允许有权限的成员明确改派或设为Unassigned；现有要求历史和工作流状态保持不变。

**Architecture:** 按codebase-design扩展既有人员目录Module，提供当前工作区单个人员的最小读取Interface；缺失人员返回明确空结果而非伪造名称。改派UI复用Registry的issue.update及已有CAS、通知与幂等语义，后续UI任务在基础读取验收后细化实际共享人员选择Module，不先引入通用表单框架。

**Tech Stack:** Django、SQLite、原生ES modules与现有Playwright；不新增依赖。

**Spec:** [首版设计](../specs/2026-11-20-workpal-software-development-design.md)的Issues负责人及当前授权要求、[主计划](2026-11-20-workpal-software-development.md)、[A5目录验收](2026-11-20-workpal-phase-a-foundation.md)。用户指定GPT 6.1 Sol实施、父代理监督；本文件不扩大执行授权到外部环境。

## Global Constraints

- “工作区身份必须出现在业务查询和写入授权中；客户端提交的 workspace_id 本身不是授权依据。”
- “所有可变主实体带 revision；旧 revision 写入返回冲突，并允许用户比较后重试。”
- “界面继续使用 Inter、中性表面、紧凑行、克制边框和阴影。”
- 目录可见不等于目标人员有Issue/要求读取权限；实际分配继续由work.issues在同事务校验并生成必要通知。
- 保持旧离线原型与review notes；无Git写操作、包安装、npm exec/npx、外网、模型或Runtime调用。使用原Node22.22.0及.venv-workpal/bin/python。

## Review Focus

1. 当前负责人在目录后续页或同名搜索结果之外，读取以稳定user_id精确定位。
2. 人员仅属于其他工作区、已撤成员或停用：不返回用户名，不泄露为什么不存在，不把缺失解释成Unassigned。
3. 请求者在读取前被停用或撤权：即使目标有效仍拒绝请求，Agent身份不绕过当前成员检查。
4. 只读目录不返回密码/email/角色/session，不产生outbox、通知或幂等写入；HTTP继续真实session/CSRF/Host和no-store。
5. 看到某个人员后分配受限Issue仍可失败，失败不改变原负责人、历史或通知；后续UI对确定性400/409保留选择并展示错误；403/404沿用现有client的访问丢失清空流程，禁止保留受限内容。

---

## Task A5-4b5a: Read one current workspace person

这是本轮独立可验收的目录能力；不提前修改UI或Issue业务。

**Files:**
- Modify `services/workpal/workpal/identity/directory.py`：增加`read_person`，与list_people复用同一当前成员过滤规则；不改变list_people合同。
- Modify `services/workpal/workpal/identity/directory_actions.py`：薄Registry Adapter；现有启动注册已调用该文件，不需要修改settings/apps。
- Create `services/workpal/tests/test_person_lookup.py`：独立行为测试，可用无测试方法的fixture，不能继承测试类重复计数。
- Modify `services/workpal/tests/test_identity_actions.py`：仅给现有catalog精确集合增加新动作，不弱化旧断言。
- Modify `services/workpal/README.md`：记录真实Interface及空结果。其他业务/前端/旧测试/计划文件不改。

**Interface:** `read_person(actor, user_id: int) -> dict`。user_id为exact int，范围1..MAX_SQLITE_INTEGER，拒绝bool、None、字符串、浮点、0、负数及越界。当前请求者必须active且属于actor.workspace_id，身份来自Actor；沿用require_member及atomic_write的读取事务方式。仅当目标active且当前Membership属于该工作区时返回`{'person': {'user_id': <id>, 'username': <actual string>}}`；其他所有目标缺失情况统一返回`{}`，不返回用户存在性/其他区信息。不使用空用户名或0伪造人员。SQL只加载User.id、username，过滤可以引用is_active；不加载完整User/email/password。独立直接调用与Registry权限一致。

**Adapter:** 新只读`workspace.people.read`，严格输入`{user_id}`，不可提供workspace/user身份覆盖或额外字段。输出闭合object，唯一可选属性person；person闭合且必须包含正整数user_id和最大150字符username。用现有schema的可选属性（required=[]），不新增oneOf/nullable支持。返回completed、空object_refs；all three roles、capability=read、mutating/confirmation_required/revision_required=False。audit_fields=('user_id',)，仅既有执行审计记录请求目标ID，不放返回用户名或任何认证字段。无outbox/幂等/确认/Notification或业务写入；目录对象不是RegisteredObject，不新建虚构来源对象。

- [x] **Step 1:** 先在新测试中通过真实Registry执行`ActionRequest('workspace.people.read', {'user_id': active_member_id}, None, None)`，断言completed且精确person字段；当前实现应失败于unknown_action。先运行并保存`/tmp/workpal-a54b5a-red.log`，不以导入缺失制造红灯。
- [x] **Step 2:** 实现read_person及薄Adapter，正常注册新动作并使原行为测试通过。对不可见目标返回空结果仍是成功读取；仅请求者无权时由现有DomainError返回404。
- [x] **Step 3:** 补Interface/Registry行为测试：owner/admin/member三角色；至少21个成员中按尾部ID读取且只得到该人；同一用户跨区成员、只在他区的用户、不存在、目标停用/撤成员的即时空结果；请求者停用/撤成员即使user_id有效也404；完整类型/范围/额外字段错误400。合法上界MAX_SQLITE_INTEGER但不存在应为空，不误判输入无效。每次只比较精确输出字段。
- [x] **Step 4:** SQL捕获证明User投影仅id/username；直接Interface及Registry前后比较业务表/通知/outbox/cache/confirmation不变，Registry仅准确追加一条read审计，fields只有请求user_id；不存在目标的成功查询不记录用户名。用真实受限Issue/要求和现有issue.update验证“目录可见但目标缺Issue或要求read”时分配失败且原负责人/历史/通知/业务事件不变；无需修改分配实现。
- [x] **Step 5:** 用真实Client(enforce_csrf_checks=True)、session和CSRF，经`POST /api/v1/actions/workspace.people.read`读取有效与空结果，均200且no-store；未登录/缺CSRF/非法Host拒绝，工作区隔离及member.list管理动作仍403。仅扩展catalog精确集合新增read动作。
- [x] **Step 6:** 运行`.venv-workpal/bin/python services/workpal/manage.py test tests.test_person_lookup tests.test_people_directory tests.test_people_directory_review tests.test_identity_actions --noinput`、全量`test --noinput`、`makemigrations --check --dry-run`及`check`，`node --test apps/workpal-web/tests/*.test.mjs`；期望既有604加独立新增测试全部通过，无迁移，Node23。核对85项保护SHA256仅.gitignore既有差异。日志`/tmp/workpal-a54b5a-*.log`，文档交付父代理，不提交。根npm/浏览器由父代理集成。

### A5-4b5a supervision acceptance — 2026-11-20

Sol先通过真实Registry观察unknown_action红灯后实现read_person与只读动作，新增7项独立测试；子代理专项27/全量611通过。父代理审查未发现实现缺陷，新增`tests/test_person_lookup_review.py`3项独立测试：目标始终有效时，撤成员/停用请求者及带executor标识的请求均拒绝，直接Interface与Registry一致；真实会话在两个已授权工作区中看到最新改名、成员撤销及停用结果，空结果仍200且no-store；目录catalog只读标志、遗漏/额外参数400和无审计副作用。此前测试将请求者撤权与已停用目标叠加，补验明确排除该错误成功理由。父代理补测首跑全绿，不追认红灯。

最终专项30项、全量614项（604+7+3）、Node23、创建核心及13条创建审查、迁移/check与根npm run check全通过，日志`/tmp/workpal-a54b5a-supervised-*.log`；85项保护SHA256仅.gitignore既有差异。没有修改生产实现或旧测试、没有Git写操作、安装或外部调用。b5a验收通过，改派UI仍待b5b，A5未完成。

## Task A5-4b5b: Assignment UI and shared people selection

依赖b5a监督验收通过；本轮只实现人员展示、改派与Unassigned，不增加状态转换、Agent/Squad分派或Run。

**Files:**
- Create `apps/workpal-web/src/features/people.js`：目录选择与人员标签Module，创建与改派实际共用。
- Create `apps/workpal-web/src/features/issue-assignee.js`：改派草稿、CAS、意图与dialog生命周期。
- Modify `features/issue-create.js`：仅将人员选择改用共用Module，项目选择及要求表单/保存语义不变。
- Modify `features/issues.js`：真实Assignee标签、Change assignee入口与安全刷新。
- Modify `src/styles.css`仅必要scoped样式，`services/workpal/workpal/web.py`及`tests/test_web.py`仅新资产白名单和断言。
- Create `apps/workpal-web/scripts/qa.issue-assignee.mjs`；修改apps package新增qa:issue-assignee及apps/service README的实际范围。
- 不改client.js、ui.js、requirements-form.js、issue-edit.js、issue-archive.js、任何业务后端、旧QA或计划；公共缺陷以证据交父代理处理。

**People Interfaces:**

`createPersonLabel({client,userId,current,onError}) -> HTMLElement`。0立即显示Unassigned且不查询；正整数用workspace.people.read精确读取，加载时显示Loading person…，有person显示实际`username (#user_id)`，空结果显示`Unavailable person (#userId)`；空结果不是Unassigned，不能取当前登录用户或目录第一页替代。网络失败在该标签局部显示错误及Retry，Issue内容仍可读；403/404调用现有访问丢失路径。每次请求检查current及本标签请求序号，不能在新对象下显示旧人员。不使用跨工作区缓存或浏览器存储。

`createPersonPicker({client,value,current,onChange,onError}) -> HTMLElement`。value是初始user_id（0代表Unassigned）；onChange(user_id)只在用户明确选择时触发。Module独立管理Search people（maxlength150）、20项授权分页、Load more people、加载/空/Retry与真实已选名称。顶部Assignee标题，Unassigned按钮；候选按钮保留`username (#id)`可访问名称和issue-picker-option行class。请求workspace.people.list({query,cursor,limit:20})，搜索改变归零清页，当前选择即使不在搜索页仍通过精确读取显示。列表/已选读取各自防迟到；旧名称查询不可覆盖用户刚选的新ID。可复用上面的只读标签，fieldsets由调用者控制disabled。列表错误重试成功后清自身旧错误；未知保存锁定fieldset但不改变选择。

该Seam只覆盖实际共用的人员查询与选择，项目选择保持既有实现。创建dialog每次open以保留的draft.assignee_user_id创建picker，onChange更新draft；关闭重开重新读取当前人员名称，无需暴露内部DOM或游标给调用者。原创建Interface/可访问名称、13条审查及稳定criterion键不变。

**Assignee Interface:** `createIssueAssigneeEditor({client,issue,current,onError,onChanged}) -> {open(returnFocus)}`。issue是真实issue.read；复制初始revision和assignee_user_id，draft目标在同一详情的关闭重开之间保留。current绑定页面及detailSequence，busy属于每次dialog；每个await/catch/finally都检查current、dialog.open和generation。英文dialog标题Change assignee，显示只读Current assignee（当前baseline人员）及一个picker，按钮Save assignee、Cancel。普通member也可以在catalog含issue.update时进入；后端仍判断实际对象权限。

点击Save且目标与baseline相同，只显示No changes to save，不发请求或生成key。否则固定`{payload:{issue_id,assignee_user_id},revision,key}`，仅调用issue.update，不夹带title/description/criteria/source_refs。只有completed确认本次写入；未知结果/503/非completed保留原意图，fieldset锁定并显示Retry original request，同详情关闭重开仍可点原请求重试。禁止读取当前结果后随意换新key。400确定失败清意图、保留目标可修改；403/404按既有client清空页面，不绕过或悄悄继续。

409保留目标，清确定失败意图、禁用保存，显示Reload current。回读真实issue.read后更新baseline revision及当前负责人，保留本地目标供比较；显示当前真实Issue标题与Current assignee标签，不自动提交。若新baseline已等于本地目标，提示No changes to save并提供Refresh issue调用onChanged，不额外POST；否则用户点击Save才以新revision、新key提交。回读未知失败保留冲突；回读期间关闭后旧响应不得替换新dialog baseline或锁住它。

**Page integration:** 详情常驻`Assignee: <person label>`，人员标签网络失败不影响Issue/要求历史读取。Change assignee只由catalog能力提示，进入时不写。成功或显式Refresh issue触发真实列表与同ID详情回读；保留搜索和Include archived，按现有list/detail序号防止重新打开用户已离开的Issue。不得直接把幂等缓存的旧DTO当当前负责人。相邻编辑/归档/历史行为全部保留，390px与Escape焦点可用。

- [x] **Step 1:** 新qa.issue-assignee使用withBrowser种真实Project/Issue、至少22名工作区人员，Issue初始指向目录后页人员；member登录读取真实详情。实施前用正常UI点击Change assignee保存缺入口红灯`/tmp/workpal-a54b5b-red.log`。fixture/import失败或实现后临时隐藏入口不算红灯。
- [x] **Step 2:** 实现两个文件的上述Interface及创建共用、详情入口、资产和文档，使同一测试通过；代码不加入业务权限判断或本地通知模拟。
- [x] **Step 3:** 核心闭环：详情精确显示后页当前负责人；打开不变保存无POST；搜索/翻页选真实owner并Save→列表/详情实际回读→独立context仍显示owner→改为Unassigned。断言两次实际写入revision各+1，所有要求历史/current要求ID/工作流/状态/项目/父子关系不变，通知仅实际新分配给owner时一条，Unassigned不新增；每次update的audit/outbox/cache各一次。确认payload仅issue_id、assignee_user_id。Cancel/Escape无写入、焦点返回、同详情草稿目标恢复；已有负责人撤成员后显示Unavailable person而不是Unassigned。1440/390及用户名中的恶意文本不执行，截图outputs/workpal-web/a54b5-assignee-{desktop,mobile}.png。
- [x] **Step 4:** 两个真实context同revision，A分给owner、B已选另一person；B保存409保留所选目标，Reload显示owner并保留B选择，B显式再Save，新revision/key成功。SQL断言最终负责人、两次通知及历史不变，不直接改DB模拟成功。另测服务端真实commit后丢响应，关闭重开后原action/payload/revision/key重试，只一次分配/通知/事件。
- [x] **Step 5:** 运行新qa.issue-assignee、qa.issue-create及qa.issue-create.review（13项）、qa.issues、qa.issue-edit及qa.issue-archive核心、Node23、Django test_web2、迁移/check；85项保护SHA256仅.gitignore既有差异。日志/tmp/workpal-a54b5b-*.log。业务后端未变无需重复全量614；其余浏览器及根npm由父代理批次。不得修改旧QA以迁就实现，也不只建立红灯就停止。

### Implementation handoff after the first attempt

2026-11-20：首轮b5b只建立真实member缺Change assignee入口红灯，代码与绿灯尚未实施，不能验收。保留`qa.issue-assignee.mjs`及`/tmp/workpal-a54b5b-red.log`，不重新制造或弱化红灯。

下一轮b5b1集中完成Step 2的全部Interface与Step 3可操作闭环、Step 5限定回归；409/未知结果的实现合同仍完整保留。Step 4双人冲突与真实丢响应专项由父代理在b5c一起补验，不据此删减整体要求。只有本轮实现及父代理验收全部通过才完成b5b/b5；后端614基线保持。

## Task A5-4b5c: Independent assignment supervision

父代理补验目录查询迟到、当前人员标签网络恢复、只读要求仍允许改派、候选撤成员/停用/撤来源、当前请求者撤权、同目标409不重复写、原意图重放期间另一人再次改派、在途保存/Reload关闭重开、跨Issue/工作区及回读竞争，精确通知和全表回滚；重跑全部旧界面、根npm/保护基线并目视截图后才验收b5整体。A5仍包含状态协作、讨论与Delivery/Review等后续界面。


## A5-4b5b / b5c supervision acceptance — 2026-11-20

改派UI监督验收通过。首轮只建立缺入口红灯，后续Sol实现people标签/共用picker、Change assignee→owner→Unassigned以及409/原意图逻辑；子代理核心QA尚未提供SQL、跨context和截图证据，父代理补齐后才验收。

父代理新增`qa.issue-assignee.review.mjs`16条独立场景。真实验证member对目录后页当前人员的读取、无变化不POST、Escape草稿恢复、owner改派及新context持久化、明确Unassigned、缺失账号与Unassigned区分。SQL逐字段对比：仅assignee/revision/updated_at变化，旧要求版本及current要求/项目/工作流/状态不变，实际分配通知recipient/event_key正确、Unassigned无新通知，audit/outbox/cache随真实写入精确一次。

双context同时改派分别覆盖目标尚未达到与已达到两种409；回读保留本地目标、明确新revision/key或仅Refresh。真实commit后丢响应再被他人改派，原请求重放只追加原有一次，界面回读最新负责人。在途保存/Reload关闭重开、跨Issue/工作区/列表回读、候选成员/活动/Issue与要求来源权限、当前请求者撤权及缓存重放撤权、只读要求可改派、名称读取网络恢复、目录及所选人员迟到隔离均通过。

新增补验最初有3条错误的相对定位器，已改为按Current assignee内容选择真实容器，这些失败不算产品缺陷。修正测试后16条中仅长用户名dialog横向溢出失败（`/tmp/workpal-a54b5c-review-second.log`）；父代理为所有person-label加overflow-wrap:anywhere，使16条全部通过（`/tmp/workpal-a54b5c-review-green.log`）。没有为原实现补测首跑绿的场景追认TDD。

最终全部13个既有浏览器脚本（含改派核心、创建/编辑/归档/Issue阅读/项目/shell及各自审查）通过，另有16项新改派审查全绿；Node23、Django test_web2、迁移/check、根npm run check退出0。日志`/tmp/workpal-a54b5c-accepted-*.log`。已目视1440/390截图`outputs/workpal-web/a54b5-assignee-{desktop,mobile}.png`，长名称正常换行，列表可纵向滚动；85项保护SHA256仅.gitignore既有差异。业务后端未改，614全量沿用b5a验收记录，未声称本轮重跑。无Git写操作、安装、外网或模型/Runtime调用。A5仍未完成。
