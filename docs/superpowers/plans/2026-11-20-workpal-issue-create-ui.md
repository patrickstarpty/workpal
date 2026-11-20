# Workpal Issue Creation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在真实工作区创建带项目、要求和可选负责人的 Issue，保存后可读取持久事实，不启动执行。

**Architecture:** 一个创建 Module 持有草稿、项目/人员选择、请求顺序及幂等意图；Issues 页面只负责入口和成功后的读取。现有 client、Registry、Issue 与人员目录 Interface 承担传输及业务权限，表单不复制后端规则。

**Tech Stack:** 原生 JavaScript ES modules、现有 DOM helpers、Django 静态白名单、SQLite、Playwright；不新增依赖。

**Spec:** [首版设计](../specs/2026-11-20-workpal-software-development-design.md)，[主计划](2026-11-20-workpal-software-development.md)，[Phase A / A5-4b1](2026-11-20-workpal-phase-a-foundation.md)。用户已授权 GPT 6.1 Sol 实施、父代理监工；本计划细化既定 A5，不重复请求执行许可。

## Global Constraints

- “界面继续使用 Inter、中性表面、紧凑行、克制边框和阴影。”
- “保留本地 review notes，界面不加入 prototype、research 或 simulation 标签。”
- “授权快照用于解释历史，当前授权用于允许下一次副作用。”
- “completed 不自动将 Issue 标为 Done。” 保存 Issue 不触发 Run；不提供虚假执行控件或测量。
- Workpal 品牌、英文 UI；所有输入按文本渲染，保持390px和键盘操作。不开浏览器持久缓存，不读取或修改旧 notes。
- 只改下列新产品路径，旧 src/backend/离线原型保持不变；不执行 Git 写操作、安装、外网、模型或 Runtime 调用。浏览器验证使用既有隔离临时 SQLite / loopback fixture。

## Review Focus

1. 创建已经提交却丢失响应：原 payload/key 重试，Issue/要求/通知/事件仅一次。
2. 目录和项目可读但不足以写入/分配：以真实保存时授权为准，撤权清除来源内容。
3. 项目/人员分页和迟到搜索：稳定 ID 选择、先授权后分页、旧结果不替换新选择。
4. 创建时项目被归档或候选成员失效：不假成功，明确失败保持可修正草稿；403/404按现有清屏策略处理。
5. 长文本、动态验收条目和关闭对话框：安全文本、窄屏可用、焦点恢复，迟到创建不能强行重新打开旧页面。

## Files and ownership

- Create `apps/workpal-web/src/features/issue-create.js`：唯一创建 Module；私有项目/人员选择逻辑可以共享小函数，不引入通用表单框架。
- Modify `apps/workpal-web/src/features/issues.js`：catalog 控件提示、创建入口、创建成功后刷新并读取。保留全部历史阅读及权限/迟到保护。
- Modify `apps/workpal-web/src/styles.css`：只新增该表单必要的紧凑、换行及窄屏样式。
- Modify `services/workpal/workpal/web.py`、`services/workpal/tests/test_web.py`：仅增加新 JS 的明确静态白名单及资产断言。
- Create `apps/workpal-web/scripts/qa.issue-create.mjs`；Modify apps `package.json`、apps/service README：新增 `qa:issue-create` 和真实范围说明。
- client.js、公共 ui.js、业务后端、既有 QA/测试与所有计划不改；若发现必须修改的共用缺陷，提供真实红灯给监工。

## Interfaces and behavior

**Produces:** `createIssueComposer({client, current, onError, onCreated}) -> {open(returnFocus)}`。每个 Issues 页面上下文创建一个实例；open 打开英文 Create issue 原生 dialog，并返回该 dialog。Module 内部持有草稿、选中对象、两个分页请求序号、创建意图和 dialog 生命周期；caller 不接触 key、游标或表单字段。`onCreated(issue)`仅在当前 dialog/页面仍有效且真实 completed 时调用一次。

**Consumes:** `client.catalog()`、`client.perform(action,payload,{key})`、`ui.el/text/openDialog`。`current()`在导航/选区/登出后为false；新 dialog 实例也需内部序号隔离。403/404交现有 onError/访问丢失路径清屏，context_changed忽略；不得在旧页面显示迟到错误。

**Backend actions:**

| Action | Payload / result |
| --- | --- |
| `project.list` | `{query,include_archived:false,cursor,limit:20}` → items/next_cursor，显示真实 name、description、ID 区分同名项目 |
| `workspace.people.list` | `{query,cursor,limit:20}` → items的user_id/username及next_cursor，只代表当前工作区人员 |
| `issue.create` | `{project_id,title,description,criteria,assignee_user_id}`；不传revision；稳定key；completed返回实际Issue DTO |

Issues 入口先清旧页，等待 catalog 时不能留下旧控件；只在 catalog 含 issue.create 时显示 Create issue。member 也可创建，不能沿用 Projects 管理角色限制。catalog 只是控件提示，每次真实动作仍实时授权。

表单包含：必选 Project、Title（required、300）、Description（20000）、Acceptance criteria（0..100条，文本required且每条2000）、可选 Assignee（默认 Unassigned=0）。条目用 Add criterion/Remove criterion 控件增删；创建 Module 自动生成稳定且互异的合法 key（criterion_1起，递增且不复用已删除编号），不让用户填写内部 key。label为Acceptance criterion N，移除控件为Remove criterion N；删除或编辑条目不串文本，剩余条目编号保持稳定。项目选择按钮为name (#id)，人员选择按钮为username (#user_id)，保存按钮为Create issue；表单可通过这些可访问名称验证。标题/标准纯空白不给出成功；实际服务器错误仍显示。

项目与人员均用真实搜索及 Load more，不下载无限目录、不要求输入对象ID、不用本地筛选冒充服务端搜索。各自最多每页20，query上限分别200/150；新搜索cursor归0并清旧结果；next_cursor=0不显示更多。选择后显示明确名称/用户名与实际编号，并保留选中值；后续搜索不把另一个同名项自动选中。Assignee可显式回到Unassigned，不能把用户名当user_id；不宣称目录用户已获Issue权限。项目为空时显示可理解的空状态且禁止保存，读失败提供 Retry，不假装空目录。

保存时固定 payload 和 `crypto.randomUUID()` key，双击只发送一次；正在保存或未知结果时锁定编辑。仅 completed 当作成功；其他动作状态/网络丢失/损坏响应保留原意图，提供 Retry original request，不能先清 key 再创建。已知400/409失败保留草稿并允许修正后作为新意图提交；项目归档409不得显示保存成功。403/404清除受限内容，不能保留旧私有搜索结果。

Cancel/Escape始终可关闭并返回焦点；在同一 Issues 上下文内重新打开时保留未完成草稿及未知创建原意图。若关闭时仍有请求，把它视为待核实，忽略已关闭 dialog 的迟到响应，重新打开可用相同key确认结果，不能悄悄生成第二份。导航/切区后不把旧草稿或迟到响应带到新上下文，不写localStorage/sessionStorage；不声称跨浏览器重启可恢复未确认意图。

真实成功关闭dialog，父页面清搜索、刷新列表并读取该Issue；刷新期间用户又选了其他Issue或切页时，旧刷新不能重新打开刚创建的Issue。复用已有列表/详情序号，保持独立要求历史可读。显示实际保存的状态label和要求版本，不自行指定Done、派发或人工批准。

## Task A5-4b2: Connected Issue creation

- [x] **Step 1 — Record a behavior red:** 在qa.issue-create中用既有withBrowser种真实Project和有效成员（不预建目标Issue），登录选区进入Issues，再点击Create issue并断言dialog可用。实施前运行`node apps/workpal-web/scripts/qa.issue-create.mjs`，应因缺创建入口失败；不以import失败或服务没启动作为产品红灯。
- [x] **Step 2 — Implement the Interface:** 按上述文件与合同实现composer、两个真实选择器、要求编辑和稳定创建意图；接入Issues入口及安全成功回读，新增静态白名单/资产断言。正常换行和命名，避免压缩成超长代码行；不复制项目编辑器历史缺陷。
- [x] **Step 3 — Prove the normal journey:** 同一脚本经真实UI以member选择项目/人员，填写标题/说明/两条标准并创建；新context重新登录后读取同一Issue及要求v1，数据库确认project、assignee、原文字段、稳定合法标准key。再测Unassigned和无标准合法，Add/Remove保持文本对应，空项目禁止保存。核对只创建Issue/要求/应有通知，未开始执行。
- [x] **Step 4 — Exercise each review focus:** 至少21个可见项目+私有/归档项目、21个有效人员+inactive/其他区账号，验证两种选择器授权后分页/同名ID/搜索与迟到响应；真实commit后abort响应，原key重试（含Escape后重开），Issue/要求/业务audit/outbox/cache/分配通知无重复；真实归档项目409保留草稿并可改选；候选人撤成员及项目撤源后不产生Issue、清受限内容；受限项目的目录可见候选人没有来源权限时分配被拒绝；正在请求时关闭/切区及成功后刷新期间新选择不被迟到结果覆盖。只延迟/丢弃真实route.fetch结果，不能mock成功。
- [x] **Step 5 — Check interaction and integrate:** 1440/390检查长标题/说明/用户名和恶意文本不执行、不横向溢出，Tab/Enter/Escape与焦点返回有效，动态条目label/错误alert/加载status可用，零pageerror/外网请求。截图`outputs/workpal-web/a54b2-create-{desktop,mobile}.png`。运行全部Node21、qa:shell、qa:review、qa:projects、qa:projects-review、qa:issues、qa:issues-review、新qa:issue-create、Django test tests.test_web、makemigrations --check --dry-run及check、保护SHA256。后端业务未改无需子代理重跑全量604项；根npm由父代理集成批次执行。记录实际日志和缺口，不提交Git。

**Acceptance scope:** 仅接通创建和创建后的真实阅读；编辑/重新分配、归档恢复、状态/依赖/层级/协作仍由后续A5计划承担。基础目录和HTTP缓存限制已验收，未经新证据不要重写。本任务完成不代表A5或首版完成。

## 监督拆分记录

2026-11-20：首次子代理仅新增真实浏览器缺入口红测，未实现composer；日志/tmp/workpal-a54b2-red.log。父代理核对后保留有效Step 1，将其余工作拆为两次可审查交付，整体合同和Step 4/5不删除、不提前勾选。

- **A5-4b2a 实施创建闭环：** 实现完整composer行为合同和薄页面接线，以既有qa.issue-create验证普通成员选择项目/负责人、两条要求（新增三条删除中间条）、Escape保留草稿、真实保存、新context持久化、Unassigned及1440/390。父代理已扩展该脚本并固定可访问名称；不削弱测试来适配实现。该轮只需新脚本、旧qa.issues、Node21、web专项、迁移/check、保护hash及文档通过；其他浏览器矩阵由b2b完成。
- **A5-4b2b 监督验收：** 父代理独立审查并补Step 4故障/权限/分页/迟到矩阵，以及Step 5全套回归和根npm。b2a绿灯只说明基础创建可用，不等于A5-4b2完整验收。新增实际缺陷优先最小修复，不因功能数量多而跳过验证。


## A5-4b2 监督验收（2026-11-20）

Sol完成b2a创建Module及闭环，原红灯转绿，父代理既有创建断言保持不变。父代理新增qa.issue-create.review十三条真实浏览器场景，实际发现并修复五项产品缺陷：表单宽于dialog造成内部横向裁切；重开草稿丢失已选名称；目录重试成功后旧错误不清；100条标准时Add按钮仍可点击；跨工作区丢弃迟到响应却不释放未读取body，导致连接继续接收。前四项在composer及scoped CSS最小修复，最后一项在client.request丢弃旧响应时best-effort cancel，并新增2条真实ReadableStream测试固定取消、取消失败/未决不阻塞新上下文及不解析旧403。Node由21增至23项，全绿。

十三条浏览器检查全绿：两种目录授权后25项分页/字面搜索、同名ID与名称、真实commit后丢响应与Escape重开原payload/key重试、在途关闭重开一次创建、项目归档409、目录可见但来源不允许分配、候选人撤成员及项目撤源、搜索/保存后刷新/跨区迟到、空项目与读失败重试、100项上限及恶意长文本。数据库核对每次成功意图的Issue/要求/audit/outbox/cache及分配通知均唯一；被拒绝的请求不建记录。两项最初的QA定位问题（has locator应相对section、清空后隐藏alert应按DOM读取）已修正，不算产品缺陷。跨区networkidle超时经真实复现及取消body修复后通过，没有删除该等待来掩盖问题。

实际验证：创建闭环、13条创建审查、旧shell、旧review9、projects、projects.review9、issues、issues.review8，Node23，Django web2、迁移/check、根npm全部通过；重新目视1440/390截图，dialog自身无横向溢出。新日志/tmp/workpal-a54b2-{review-red,review-accepted,core-accepted,stale-body-red,stale-body-green,npm-accepted}.log。业务后端未改，全量604沿用A5-4b1实际验收，不伪称本轮复跑。保护SHA256仅.gitignore既有差异；无Git写操作或真实外部调用。A5-4b2验收完成，编辑/重分配等后续工作及A5整体仍未完成。
