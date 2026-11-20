# Workpal Issue Transition UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 成员通过真实界面变更Issue状态、记录阻塞原因与责任人，符合人工完成门禁，能从冲突或未知写结果中恢复。

**Architecture:** 按codebase-design把目标选择、草稿、权限提示、稳定写意图和冲突回读放入一个Module，Issues页只提供入口与成功后的真实回读。复用已验收人员选择和状态历史；业务规则仍由既有issue.transition执行，不建立前端业务状态机。

**Tech Stack:** 现有原生ES modules/DOM/CSS、Django静态白名单、Playwright与隔离SQLite，无新依赖。

**Spec:** [设计](../specs/2026-11-20-workpal-software-development-design.md)、[A5](2026-11-20-workpal-phase-a-foundation.md)、[并行调度](2026-11-20-workpal-parallel-delivery.md)、[历史验收](2026-11-20-workpal-issue-status-history-ui.md)。用户已授权Sol实施、父代理只监工，无需重复确认。

## Global Constraints

- “人工完成必须记录理由与操作者”。“completed 不自动将 Issue 标为 Done。”
- “Block 记录问题和责任人；解除阻塞不自动执行。”
- English UI、Workpal品牌、Inter/中性表面/紧凑布局、390px与键盘可用；文本按textContent处理。
- 不改业务后端、公共client/ui/people、旧原型及旧QA；B/D兄弟只写各自新后台模块，本任务独占下列UI和静态资源文件。无Git写操作、依赖安装、npm exec/npx、外网/模型/Runtime。
- 使用现有Node22.22.0及.venv-workpal/bin/python；浏览器测试仅现有withBrowser隔离loopback环境，不访问用户实际数据。

## Review Focus

1. 保存的workflow key/label/edges与当前项目定义不同：只用该Issue快照，标签重复时附key帮助选择。
2. 已保存却丢响应：保留同payload/revision/key显式重试，不能重复历史/通知或把缓存结果当当前状态。
3. 409期间其他人改变状态/要求：明确回读、重算合法目标、保留草稿，目标已经达到时不再写第二条历史。
4. Blocked owner与assignee不同；候选成员/来源权限在选中后撤销时服务端拒绝，UI不能宣布成功。
5. Done需要当前人类角色、理由及项目证据/依赖门禁；默认代码策略缺真实合并事实时显示拒绝，不能绕过完成。

## Task A5-4c2: Change status, block and explicitly complete

**Files:**
- Create `apps/workpal-web/src/features/issue-transition.js`、`apps/workpal-web/scripts/qa.issue-transition.mjs`。
- Modify `apps/workpal-web/src/features/issues.js`仅薄接线；`styles.css`仅必要新样式；apps package新增qa:issue-transition；apps README记录真实范围。
- Modify `services/workpal/workpal/web.py`及`services/workpal/tests/test_web.py`仅静态资源白名单与资产断言。
- 不改其他文件，尤其不修改业务transitions/Registry、现有编辑/改派/历史Module或旧QA。服务公共README留后续集成任务。

**Interface:** `createIssueTransitionEditor({client,issue,current,onError,onChanged})->{open(returnFocus)}`。issue为真实已读DTO，Module保存独立baseline、target、reason、blockedOwner及未知写intent；每次open有独立busy/generation，关闭不丢草稿和未决intent。成功只调用onChanged触发真实list/detail回读，不渲染旧写响应覆盖更新事实。

**Read and write contracts:**
- Issues仅在catalog包含issue.transition时显示`Change status`。dialog显示当前Status（保存label）及目标select `Target status`，选项只取baseline.workflow_snapshot.definition.transitions中from===baseline.status_key的to。没有出边显示No available transitions；不凭英文label决定类别或生成额外边。初始目标未选择。
- textarea `Reason`最长4000。目标category=blocked或done时要求非空trim文本；其他目标可选reason。Blocked显示`Blocked owner`共享createPersonPicker，必须正整数；payload在非blocked时固定blocked_owner_user_id:0，不能残留草稿owner。current assignee不改变。
- `client.perform('issue.transition',{issue_id,target,reason,blocked_owner_user_id},{revision:baseline.revision,key:crypto.randomUUID()})`。只有显式submit创建冻结intent；输入未完成/目标等于当前时不发POST。按钮`Save status`；unknown时显示`Retry original request`并锁定输入。
- 目标done的角色提示来自真实workspace.read {}的data.role，和快照review_policy.reviewer_roles比较。可在open时读一次；结果迟到有generation守卫。角色未知或不允许时禁用done提交，并显示Checking reviewer permissions / Human reviewer required及局部Retry权限读取，其他合法状态仍可选。该提示不替代服务端当前授权；不得给member自动提升角色，也不假设owner始终在自定义reviewer_roles中。
- Done的证据、依赖与current Review有效性由服务端核验。默认approved_head_merged尚无B4时409 completion_not_ready应完整显示，保留输入和当前状态；manual策略的人类授权和reason成功走真实动作。UI不伪造PR/部署/恢复结论。
- 400明确输入拒绝可清intent并修订；409清intent、保留草稿和服务端原因，展示`Reload current`，禁止盲重发。回读issue.read取得完整新baseline/revision，显示新当前Status与提醒；保留目标若仍合法，失效目标明确显示Unavailable且要求重新选择；若target已为当前状态，仅提供`Refresh issue`，不产生重复转换。回读不自动提交。
- 网络失败/非completed结果保留原intent；再次open仍显示unknown及原请求重试，不能换key或把Refresh当作写结果确认。原重试成功后回读实际当前Issue，即使另一人已转换到更新状态。失败、await及finally均检查dialog/页面/请求generation。
- 当前403/404或会话失效沿现有onError/global onAccessLost清详情及dialog，不能显示旧成功或旧受限草稿。close/Escape返回入口焦点，取消不写业务。

- [x] **Step 1:** 用withBrowser、真实member、真实Project/Issue（已在todo）建立缺`Change status`入口行为红灯；先读取Issue成功再点击，日志 `/tmp/workpal-a54c2-red.log`。不把导入/fixture/启动失败或实施后临时隐藏入口当红灯。
- [x] **Step 2:** 实现一个Module及薄接线/资源配置，使同一真实用户路径可操作。不要仅交红灯或占位按钮。
- [x] **Step 3:** core QA：member todo→blocked（reason+另一个人的blockedOwner）→todo→in_progress→in_review；每次真实回读和独立browser context持久化一致；当前阻塞/历史前后owner正确，assignee、要求历史、workflow快照不变；真实状态事件和通知各一次。没有理由/owner拒绝时无POST，Cancel/Escape保留草稿且无写。
- [x] **Step 4:** 使用正常workflows.create/publish及project.set_workflow建自定义key/label/manual策略；允许的member带理由Done成功，角色不在reviewer_roles时UI禁用并解释。默认代码策略owner尝试Done因真实completion_not_ready被拒绝，不变Issue/history/outbox；未解决依赖真实dependency_blocked。不要篡改成功响应或绕过后端。
- [x] **Step 5:** 至少覆盖409新状态回读与原target失效、另一人已达到目标后的无重复写、真实服务已写后丢响应的原请求重试（原payload/key/revision相同且历史/通知/业务audit/outbox/cache精确唯一）、在途关闭重开不锁死、切Issue/工作区旧结果隔离。HTTP故障注入必须route.fetch真实响应后丢弃，不合成成功。缺口明确交后续独立审查，不以测试数量代替矩阵。
- [x] **Step 6:** 1440/390截图 `outputs/workpal-web/a54c2-transition-{desktop,mobile}.png`，验证Tab/Enter/Escape、焦点返回和恶意/长reason文本安全。运行新QA、qa.issue-status-history、qa.issues、qa.issue-assignee及各自review、Node23、Django test_web、迁移check和system check，全部退出0。日志 `/tmp/workpal-a54c2-*.log`。
- [x] **Step 7:** 核对85项保护SHA256仅.gitignore既有差异。记录实际文件、命令、日志和真正残留；不运行并行未集成新app的全量发现，根npm由集成任务统一执行。不宣称A5、Runtime或首版完成。

## Independent review after delivery

新审查Agent补验只读来源/独立要求撤权、候选责任人撤成员/停用/撤源、确认前后权限变化、所有dialog与导航迟到、真实双用户竞争、完整事务无副作用及自定义完成门禁。父代理只读差异、运行已提供测试和验收；不得因默认代码Done不可用而削弱后端门禁。

## Supervision acceptance — 2026-11-20

A5-4c2功能验收通过。实施前真实member已读Issue后缺Change status入口的红灯已记录；首交仅普通状态路径，不作整体交付。独立six review随后完成Blocked、custom/manual Done、默认完成与依赖拒绝、两种409、实际写成功后丢响应和导航迟到隔离；权限review追加三组真实服务场景，含Issue撤read/write、要求撤read、候选owner撤成员/停用/撤源，以及真实写后丢响应再撤权的原意图重试。SQL校验拒绝不写业务，已成功的事实精确一次。

合同澄清：转换要求当前Issue write与当前要求read；只撤独立要求write保留read不应拒绝，此项作为正向对照，未为通过测试放宽实现。完成仍服从人审、证据及依赖门禁，不推导PR合并或故障恢复。

父代理首次six review在登录前等待Username超时，尚未到业务断言。新的fixture失败诊断保留页面文本、console/pageerror、失败HTTP和本次server日志，仍抛原错误；没有增加自动重试或超时。该失败随后未复现，根因未确认，作为诊断残留保留，不标已修复。

父代理读取最终QA/fixture并实际复跑权限三组与apps Node23，退出0：`/tmp/workpal-a54c2-accepted-{permissions,node}.log`。子代理core+six、create/assignee core+review、web2、迁移/check、根npm和85项保护检查均通过，日志`/tmp/workpal-a54c2-permissions-*.log`。其中Node102属于根原型测试，不能与apps Node23混计。保护仅.gitignore既有差异。

共享people picker仅增加可选heading，默认Assignee保持；状态表单由外层Blocked owner命名，避免重复误导。父代理目视`outputs/workpal-web/a54c2-permissions-mobile.png`，390px无横向溢出；桌面和移动截图由子代理保存并目视。没有业务后端或真实Runtime改动，A5整体尚未完成。
