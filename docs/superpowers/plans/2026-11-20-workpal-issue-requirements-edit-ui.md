# Workpal Issue Requirements Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 普通成员可以编辑已有Issue的标题、说明和验收标准，保留不可变要求历史，并正确处理并发冲突与未知保存结果。

**Architecture:** 按codebase-design抽出创建与编辑实际共用的要求表单Module；编辑Module集中CAS、差异载荷、草稿和幂等意图，Issues页面仅接入口和回读。复用已验收client与Registry，不复制后端权限或引入表单框架。

**Tech Stack:** 现有原生ES modules/DOM/CSS、Django静态白名单、SQLite和Playwright；无新依赖。

**Spec:** [首版设计](../specs/2026-11-20-workpal-software-development-design.md)、[主计划](2026-11-20-workpal-software-development.md)、[创建界面及验收](2026-11-20-workpal-issue-create-ui.md)。沿用用户已给出的GPT 6.1 Sol实施、父代理监工授权。

## Global Constraints

- “界面继续使用 Inter、中性表面、紧凑行、克制边框和阴影。”
- “授权快照用于解释历史，当前授权用于允许下一次副作用。”
- “completed 不自动将 Issue 标为 Done。” 编辑不启动Run、不自动转换状态。
- 英文Workpal UI；用户内容仅按文本渲染，390px和键盘可用；不写浏览器存储、不影响旧review notes。
- 不改旧原型src/backend、根package或业务后端；不Git写操作、不安装、不外网/模型/Runtime。真实验证使用隔离临时库及loopback。

## Review Focus

1. 两人同时编辑不同字段：409保留本地修改，Reload current合并未修改字段，不把旧字段静默写回。
2. 已提交却丢响应：保存的payload/revision/key原样重试，不能多追加要求版本。
3. 已有标准使用自定义key或含已删除编号：保留已有key，新条目不碰撞，删除不串文本。
4. 要求来源独立撤权、切换Issue/工作区：不复制受限内容到新版本，迟到响应不重新展示旧对象。
5. 无变化、清空字段及长恶意文本：不产生无意义版本，显式空值正确保存，表单不裁切、不执行输入。

## Files

- Create `apps/workpal-web/src/features/requirements-form.js`：共用要求表单Module。
- Create `apps/workpal-web/src/features/issue-edit.js`：仅编辑要求及冲突/重试状态。
- Modify `features/issue-create.js`：使用共用表单，保持所有现有Interface及创建行为。
- Modify `features/issues.js`：基于catalog加入Edit requirements，保存后安全刷新/回读。
- Modify styles.css（必要scoped样式）、web.py/test_web.py（仅新资产白名单）、apps package及apps/service README。
- Create `apps/workpal-web/scripts/qa.issue-edit.mjs`。client.js、ui.js、现有QA/业务后端/所有计划不改；共用缺陷交监工持真实证据处理。

## Interfaces

**Shared form:** `createRequirementsForm(value) -> {element, read(), replace(value)}`。value仅为`{title,description,criteria:[{key,text}]}`；创建时空值，编辑时实际要求。Module内部持有DOM输入和条目编号；read返回独立副本，不做网络或业务写入。element可在同一草稿的dialog关闭后重新挂载，保留输入和已消耗编号。replace(value)用于冲突合并后的内容替换，保留同一element及本草稿所有已消耗key和显示编号，不重新初始化标识账本。父级fieldset控制disabled，无需向caller暴露各input或key生成器。

保留现有可访问名称Title、Description、Acceptance criterion N、Add criterion、Remove criterion N；300/20000/100条/每条2000上限及100条禁用Add不变。已有criteria key完全保留（例如delivery_check），标签序号与业务key分开；新增用criterion_N，递增并跳过本次草稿曾出现的所有key，不能覆盖自定义key或复用本次已删除key。编辑初始按已有顺序显示序号1..n；创建原有criterion_1/3及Escape恢复的测试必须继续通过。

**Edit Module:** `createIssueRequirementsEditor({client, issue, current, onError, onSaved}) -> {open(returnFocus)}`。issue为真实issue.read DTO；内部复制baseline `{id,revision,title,description,criteria}`，保存草稿及意图，每个已加载Issue详情一个实例。current同时绑定页面上下文及当前详情序号，离开该详情即失效。open返回名为Edit requirements的dialog。仅编辑三项要求，不展示可写project、assignee、来源或状态字段；重新分配、归档及转换留后续任务。

Issues详情仅在catalog含issue.update时显示Edit requirements（member也可以）；按钮只是能力提示，保存时由后端实时授权。使用`client.perform('issue.update',{issue_id,...changedFields},{revision:baseline.revision,key})`。changedFields仅含相对于baseline实际变化的title/description/criteria，保留显式空description和空criteria；三项均未变时显示No changes to save，不发请求、不生成key。保存前检查非空白title/非空白标准，后台错误仍显示。

新意图固定payload/revision/key、锁定表单，双击不重复发送；仅completed表示已保存。未知响应/503/非completed保留原意图并提供Retry original request，禁止Reload current清空未知key；Cancel/Escape允许关闭，同详情重开仍保留草稿及原意图。400确定失败可改草稿再作为新意图；403/404按现有访问丢失路径清空。成功关闭后仅当前有效详情调用onSaved，旧dialog响应不覆盖另一个Issue/工作区。

**409 flow:** revision_conflict保留草稿，清该次已确定失败的意图，禁用Save changes并提供Reload current。Reload真实issue.read；针对三项字段记录“原baseline→当前草稿”的差异：未改字段采用新远端值，已改字段保留本地值（criteria按整项数组处理）。更新baseline revision及远端要求，在dialog显示Current saved requirements（只读标题/说明/标准）供比较，提示保留本地修改；不自动保存。用户再次点击Save changes后，用新revision、差异payload和新key发送。这样只改description的用户不会把别人刚改的title写回旧值。Reload失败继续保留冲突草稿；未知保存时Reload禁用，不能误把重放改成新写入。

**Success:** 后端决定是否追加要求版本，UI不能自己加version。复用列表/详情请求序号刷新，列表标题和要求历史来自真实回读；迟到刷新不覆盖新选择。共享一个小的refresh/read helper给创建和编辑即可，不引入通用事务框架。

## Task A5-4b3a: Editing core and shared requirements form

- [ ] **Step 1:** 新qa.issue-edit用withBrowser创建真实Project/Issue（custom key delivery_check及criterion_1两项），以member登录读详情后点击Edit requirements。实施前观察缺入口行为红灯，不能用import/fixture错误；记录/tmp/workpal-a54b3a-red.log。
- [x] **Step 2:** 实现两个小Interface、创建接入共用表单、薄详情入口、资产及文档。不得改动既有创建QA断言或恢复已修复的宽度、名称、重试、取消body问题。
- [x] **Step 3:** 真实UI改title/description、保留一项custom key/移除一项/新增一项→保存；确认Issue revision及要求number各加一，project/assignee/status/workflow不变，旧要求仍可通过Previous version读取，新context持久化。无变化Save不请求；description和criteria可显式清空。创建核心+13条创建审查继续全绿。
- [x] **Step 4:** 两个真实context读同一revision；A只改title成功，B只改description遇409，保留B草稿→Reload current→A的新title进入未修改字段→B再次Save成功。断言最后title是A的新值、description是B草稿、每个要求版本唯一且v1/v2/v3完整，不能直接修改DB模拟成功响应。检查Cancel/Escape焦点及同详情草稿恢复、1440/390和恶意文本，截图outputs/workpal-web/a54b3-edit-{desktop,mobile}.png。
- [x] **Step 5:** 运行新qa.issue-edit、qa.issue-create、qa.issue-create.review、qa.issues、Node23、Django tests.test_web、迁移/check与保护SHA256。业务后端未变无需子代理重复全量604；其他旧QA及根npm交父代理批次。日志/tmp/workpal-a54b3a-*.log。该轮以真实编辑/冲突闭环交付，不只建立红灯就停止。

## Task A5-4b3b: Independent supervision

父代理补验真实提交后丢响应与原key/revision重试、独立要求撤权/只读grant、多个Issue和跨工作区/关闭dialog迟到、保存后列表竞争、旧key不适配新revision、criteria冲突及字段清空、完整事件/历史唯一性；运行其余旧浏览器/根npm并目视截图后才标记b3完整验收。b3a不承担该完整矩阵，整体合同不删减。重新分配、归档恢复及状态协作后续另做，A5仍未完成。

## Supervision acceptance — 2026-11-20

A5-4b3功能验收通过，A5仍进行中。Sol实现核心编辑及共享表单后，父代理新增独立`qa.issue-edit.review.mjs`，实际11条浏览器场景首次8通过、3失败：在途保存关闭重开后按钮仍忙碌；冲突回读关闭重开后无法继续；重建表单丢失本草稿已消耗的criterion key。日志`/tmp/workpal-a54b3-review-red.log`。父代理将busy限定为单个dialog，每个await及错误/完成分支检查dialog generation，并在共享表单增加保留key账本的replace(value)。同测11条全绿，原编辑核心全绿；日志`/tmp/workpal-a54b3-{review,core}-green.log`。

独立补验还验证：member可编辑、自定义key保留和字段显式清空、无变化不POST、各历史版本及旧内容不可变、元数据/通知不变；真实commit丢响应后即使已有更新版本，仍以原payload/revision/key重放并回读最新事实；标准数组冲突保持本地内容且展示真实远端；只读/撤权的要求拒绝写入；切Issue/工作区及保存后列表刷新隔离；390px、键盘焦点与恶意文本。写入audit/outbox/cache数量随实际版本精确增加。

最终在已安装Node v22.22.0重跑10个浏览器脚本：编辑核心+11补验、创建核心+13补验、Issue核心+8补验、shell+9补验、项目核心+9补验，全部退出0；Node23、Django test_web 2项、makemigrations --check --dry-run、Django check及根npm run check均通过。最终日志`/tmp/workpal-a54b3-accepted-*.log`；已目视1440/390截图`outputs/workpal-web/a54b3-edit-{desktop,mobile}.png`，无内容执行或横向裁切。85项保护SHA256仅.gitignore既有差异。业务后端未变，全量604沿用A5-4b1，未声称本轮复跑。

**流程偏差保留：** Step 1未完成有效的实施前红灯；子代理实施后临时关闭入口复现不能追认为TDD，故该勾选保留未完成。父代理上述三个缺陷有实际修复前失败及修复后通过，其他首次通过补测不追认红灯。

**命令偏差与处理：** 子代理误用`npm --prefix apps/workpal-web exec -- node scripts/qa.issue-edit.mjs`，真实访问npm registry并下载node@27.0.0-alpha.0.1.1及安装辅助包；不能描述为“仅尝试”或“无外网”。父代理核对npm日志及创建时间，将仅由此次命令新建的`/Users/patrick/.npm/_npx/1838e33cf768caf6`移至`/tmp/workpal-a54b3-unexpected-npm-1838e33cf768caf6`，原npm exec目录已不存在。未广泛清理共享缓存；仓库依赖/lock无变化，验收全部使用原有Node v22.22.0。后续任务明确禁止npm exec/npx和依赖安装。无Git写操作或真实模型/Runtime调用。
