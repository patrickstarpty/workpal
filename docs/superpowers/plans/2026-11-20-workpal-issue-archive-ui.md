# Workpal Issue Archive and Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 有权限的成员可从真实Issue详情归档或恢复记录，在冲突和未知结果时保留准确意图，状态及要求历史保持不变。

**Architecture:** 按codebase-design将归档/恢复两种实际操作放在同一Module的小Interface后，内部持有目标、revision、幂等意图和dialog生命周期。Issues页面只负责入口及安全回读；复用现有client、Registry和SQLite，不改变业务后端、不引入泛化写入框架。

**Tech Stack:** 原生ES modules/DOM/CSS、Django静态白名单、SQLite、既有Playwright；无新依赖。

**Spec:** [首版设计](../specs/2026-11-20-workpal-software-development-design.md)、[主计划](2026-11-20-workpal-software-development.md)、[编辑验收](2026-11-20-workpal-issue-requirements-edit-ui.md)。沿用用户指定GPT 6.1 Sol实施、父代理监工的执行方式。

## Global Constraints

- “归档是可见性属性，不新增状态。”
- “所有可变主实体带 revision；旧 revision 写入返回冲突，并允许用户比较后重试。”
- “界面继续使用 Inter、中性表面、紧凑行、克制边框和阴影。”
- 英文Workpal UI；用户内容仅按文本显示；390px、Tab/Enter/Escape及焦点返回可用。不写浏览器存储，不改变旧review notes。
- 限定apps/workpal-web、Django静态资产映射及两份README；不改旧原型、业务后端或client。无Git写操作，无外网/模型/Runtime调用。
- 只用既有Node v22.22.0、`.venv-workpal/bin/python`及已安装Playwright。禁止npm exec/npx、安装或升级任何包；测试仅loopback及独立临时SQLite。

## Review Focus

1. 归档隐藏活动列表但不改status、workflow、assignee、要求版本、通知或子任务；恢复后历史仍可读。
2. 真实提交丢响应以及在途关闭重开：只重试原action/payload/revision/key，不能再次增加revision。
3. 两人同时操作：409必须回读；若目标已达到只刷新，不重复写；若仍未达到，用户看过当前事实后显式重试。
4. 当前Issue或独立要求撤权：立即清除旧内容，授权失败不误称成功；catalog仅为能力提示。
5. 切Issue、工作区、筛选或关闭dialog后迟到响应不覆盖新选择，成功后的列表刷新也不能重新打开旧详情。

---

## Files and Interfaces

- Create `apps/workpal-web/src/features/issue-archive.js`：归档/恢复交互及意图状态。
- Modify `apps/workpal-web/src/features/issues.js`：catalog能力入口与回读；保持既有创建、编辑、历史读取。
- Modify `apps/workpal-web/src/styles.css`：仅必要scoped布局，可复用既有dialog样式。
- Modify `services/workpal/workpal/web.py`、`services/workpal/tests/test_web.py`：只增加新资产白名单及对应断言。
- Create `apps/workpal-web/scripts/qa.issue-archive.mjs`：真实浏览器核心及下述失败场景；父代理另建review脚本。
- Modify `apps/workpal-web/package.json`、`apps/workpal-web/README.md`、`services/workpal/README.md`：新增`qa:issue-archive`及真实范围。子代理不改计划/旧QA/公共client/ui/form。

**Module Interface:** `createIssueArchiveControl({client, issue, current, onError, onChanged}) -> {open(returnFocus)}`。issue来自当前真实issue.read，内部复制id、revision、title、archived；固定目标为`!issue.archived`，单个已加载详情一个实例。current同时绑定页面上下文与detailSequence。open返回标题为`Archive issue`或`Restore issue`的dialog；显示真实Issue标题及`Archiving hides this issue from active lists. Its status and requirements stay unchanged.`或对应恢复说明，提交按钮同名，另有Cancel。无需填写ID，也不请求服务端confirmation token。

**Registry Adapter consumption:** 已有`client.perform(action,{issue_id},{revision,key})`，action仅为`issue.archive`或`issue.restore`，普通member也在目录中。后端以Issue write及当前要求read授权，revision CAS；成功返回完整Issue DTO，归档不新增要求版本。不得从是否member推断写权限，不在客户端绕过后端校验。

**Intent and lifecycle:** 点击提交前固定action/payload/revision/key；本dialog忙碌时禁用重复提交。仅completed确认本次动作提交。网络未知/503/非completed保留原意图，显示`Retry original request`，禁止回读替换未知key；同详情Cancel/Escape后重开仍可原意图重试。busy属于单个dialog；关闭后的每个await/catch/finally必须忽略，不能让旧结果关闭或改变新dialog。400确定失败清意图并显示真实错误；403/404清旧内容并走现有onError。不要把未知结果自动解释为未归档。

**409:** 清除确定失败的意图，保持原目标，禁用提交，提供`Reload current`。读取真实issue.read，显示当前title及Active/Archived，更新baseline revision但不自动发送。若当前状态已等于目标，显示`Already archived`/`Already active`并只提供`Refresh issue`调用onChanged，不生成key或副作用；若目标未达到，重新启用原操作，下一次用户点击才以新revision/new key发送。Reload失败保持冲突；关闭重开后可重新reload，旧dialog的回读不能替换新baseline。

**Page integration:** catalog包含对应动作时，详情仅显示当前适用的Archive issue或Restore issue。onChanged只触发真实列表刷新：保留query和Include archived筛选。默认活动筛选下归档后清详情；Include archived下安全回读同ID以展示当前事实（包括幂等重放之后他人再次修改的状态），不能直接用缓存的成功DTO覆盖。复用detail/list序号，用户已换选就不重开旧Issue。dialog关闭后若原按钮因刷新消失，焦点移到仍存在的Refresh issues按钮；不得抢走用户已移动的焦点。

## Task A5-4b4a: Working archive and restore flow

- [x] **Step 1:** 新QA用withBrowser建立真实Project、父Issue和子Issue，父Issue包含两个要求历史版本和非默认status；以member登录并读真实详情。点击Archive issue，在实现前记录缺入口行为失败至`/tmp/workpal-a54b4a-red.log`。fixture/导入/启动失败不是红灯；禁止实施后临时关闭入口冒充测试先行。
- [x] **Step 2:** 实现上述Interface、薄入口、资产映射、脚本及文档，使同一测试转绿；只做到既有动作对应的归档属性，不加Run或新状态。
- [x] **Step 3:** 完成核心场景：Cancel/Escape无请求且焦点回按钮；member归档→活动列表消失→Include archived找到→历史可读→独立context持久化→Restore→活动列表可见。断言Issue revision仅两次写入各+1、旧要求行及current要求版本不变、status/workflow/assignee/parent关系/子Issue/通知不变；每个动作业务audit/outbox/cache只一条。记录1440/390截图`outputs/workpal-web/a54b4-archive-{desktop,mobile}.png`并测长恶意标题只显示文本。
- [x] **Step 4:** 真实两context竞争：A归档成功，B旧revision归档409，Reload显示Already archived，Refresh不再发写入；另一个Issue中A编辑要求，B归档409，Reload显示A的新标题及Active，显式再次点击成功，要求历史无额外版本。保存前后SQL事实及网络请求核对action/revision/key。
- [x] **Step 5:** 真实归档commit后截断响应，原意图重试且只一次revision/事件；另测在途保存关闭重开，原重试可点，迟到旧响应不关闭新dialog。route.fetch取得实际成功再丢弃，不mock成功DTO、不绕开UI发变更。所有自建进程/浏览器/临时库finally清理。
- [x] **Step 6:** 运行`node apps/workpal-web/scripts/qa.issue-archive.mjs`、`qa.issue-edit.mjs`、`qa.issue-edit.review.mjs`、`qa.issues.mjs`、`node --test apps/workpal-web/tests/*.test.mjs`、`.venv-workpal/bin/python services/workpal/manage.py test tests.test_web --noinput`、同manage.py的`makemigrations --check --dry-run`及`check`。核对`/tmp/workpal-supervision-baseline-20261120.json`的85项SHA256（仅.gitignore既有差异）。日志`/tmp/workpal-a54b4a-*.log`，交付文件/实际红绿/命令退出码/真正残留；不提交、不只写红灯就停止。业务后端未变不要求本轮重复604全量。

## Task A5-4b4b: Independent supervision

父代理独立补验Issue/source和要求撤权、只读grant、未知结果后他人反向修改再重放、在途Reload关闭重开、多Issue/工作区/列表刷新竞争、授权筛选及长文本键盘。逐项核对保存历史与事件唯一性；再跑创建/其余旧浏览器、根npm、保护基线并目视截图。父代理可以拒绝本单元但不删合同；A5仍包含重新分配、状态协作、Delivery/Review等后续工作，不以本单元宣布首版完成。


## Supervision acceptance — 2026-11-20

A5-4b4监督验收通过。Sol先在真实member读取要求版本2后观察缺Archive issue入口的红灯（`/tmp/workpal-a54b4a-red.log`），随后实现并验证归档/恢复、两类409、真实丢响应和关闭重开、历史及事件唯一性。父代理增加`qa.issue-archive.review.mjs`的12条独立场景，起始11通过/1失败：成功冲突回读后，关闭重开的dialog丢失已确认的Active/Archived说明，日志`/tmp/workpal-a54b4-review-first.log`。修复将该可见性事实与revision/title一起保留；同时强化测试等待真实新标题后再关闭，避免初始Active文本让测试误认为回读已结束。首次修复后该测试出现的等待竞争保留在`review-green.log`，最终12条全部通过见`/tmp/workpal-a54b4-review-final.log`，核心复跑见`/tmp/workpal-a54b4-core-green.log`。

独立验证包括Issue只读拒写、要求只读允许归档元数据、Issue与要求撤权后的拒绝/回滚、撤权后缓存重放仍拒绝、归档及恢复两方向的丢响应后反向修改再原意图重放并回读当前状态、在途Reload关闭重开、跨Issue/工作区及列表刷新/焦点竞争、私有要求混排的授权分页、长恶意文本与Escape。真实SQL对比证明要求历史、其他属性和通知保持，实际写入的audit/outbox/cache精确一次。除上述展示缺陷外，补测首跑绿，不追认测试先行。

父代理最终通过：归档核心+12补验，编辑核心+11补验、创建核心+13补验、Issue核心+8补验、shell+9补验、项目核心+9补验；Node23、Django test_web2、迁移/check及根npm run check退出0。日志`/tmp/workpal-a54b4-accepted-*.log`；85项保护SHA256仅.gitignore既有差异，见`/tmp/workpal-a54b4-protection.log`。已目视1440/390截图`outputs/workpal-web/a54b4-archive-{desktop,mobile}.png`，长文本正常换行、要求历史及归档状态可见。业务后端未改，全量604仍沿用A5-4b1基线。无Git写操作、包安装、外网或真实模型/Runtime调用。A5及首版未完成。
