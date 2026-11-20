# Workpal Issue Dependencies UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户能读取真实依赖、搜索选择其他Issue、添加和移除依赖，并从并发冲突和未知结果中恢复。

**Architecture:** 按codebase-design用一个深Module承载依赖读取、候选选择和稳定写意图。Issues只提供已读Issue、catalog能力和刷新回调；既有后端负责权限、环检测、来源继承、CAS和Done门禁，前端不重建关系图。

**Tech Stack:** 原生ES modules/DOM/CSS，Django静态白名单，现有Playwright隔离SQLite fixture；无新增依赖。

**Spec:** [设计派发规则](../specs/2026-11-20-workpal-software-development-design.md)、[A5](2026-11-20-workpal-phase-a-foundation.md)、[并行调度](2026-11-20-workpal-parallel-delivery.md)。A5-4c2已验收；本项编号A5-4d1，不包含parent/children或comments。

## Global Constraints

- “子任务依赖必须在同一工作区，拒绝依赖环。” “completed 不自动将 Issue 标为 Done。”
- English UI、Workpal品牌、中性紧凑布局、390px及键盘可用，所有外部内容作为文本。
- 不改业务后端、client/ui/people、旧QA或原型；不Git写入/建worktree/安装/npm exec/npx/外网/模型/Runtime。
- 用户已授权GPT6.1 Sol实施、父代理监工；.venv-workpal/bin/python、Node22.22.0、现有withBrowser loopback。85项保护基线仅.gitignore既有差异。
- 集成Agent只改settings/服务README/新集成测试，本任务独占web资产映射及UI；不要改公共服务README或配置。

## Review Focus

1. 候选列表可读不代表两端可写：真实403必须清受限内容，不能假成功。
2. 后端列表不含title或保存workflow label：只用issue.read授权读取，不能把category当自定义label。
3. 409来自revision、重复边或cycle：解释实际错误，回读不自动重试、不生成新边。
4. 服务端写成功后丢响应：同payload/revision/key重试，精确一条业务事实，再读实际最新状态。
5. 关闭/重开、搜索与分页、切Issue/工作区时迟到响应不得重现旧数据或覆盖新草稿。

## Task A5-4d1: Dependencies reader and editor

**Files:** Create `apps/workpal-web/src/features/issue-dependencies.js`、`apps/workpal-web/scripts/qa.issue-dependencies.mjs`、`qa.issue-dependencies.review.mjs`。Modify `features/issues.js`仅薄接线，`src/styles.css`仅必要样式，apps `package.json`/`README.md`，`services/workpal/workpal/web.py`和`services/workpal/tests/test_web.py`仅资产映射。先创建新Module再接import，避免并行回归读到缺文件。不得修改其他文件。

**Interface:** `createIssueDependencies({client,issue,actions,current,onError,onChanged})->HTMLElement`。返回`section[aria-label="Dependencies"]`；Module拥有baseline/游标/候选搜索/选择及操作intent。对父级成功只调用onChanged触发列表和详情真实回读，不用写响应覆盖当前事实。current须同时检查页面与Issue detail generation。

**Read contract:**
- catalog含`issue.dependency.list`才展示。先显示`Show dependencies`，展开后调用`issue.dependency.list {issue_id,cursor:0,limit:20}`；结果`items[{id,depends_on_id,status_key,status_category}],next_cursor`，游标按edge.id，不能用IssueID。`Load more dependencies`追加，`Refresh dependencies`从0重读。
- 每条依赖通过`issue.read {issue_id:depends_on_id}`取得title和自身保存workflow_snapshot的label；显示`title (#id)`与真实label/key。按需读取当前页，代际失效时丢弃；缺权限沿现有client/onError处理清除详情和dialog，网络失败保留可重试错误，不能补造标题或默默当空依赖。
- 使用文本显示空态`No dependencies.`；这里只呈现当前获授权的返回项，不宣称服务端没有隐藏记录。查询本身无业务写/outbox。

**Write contract:**
- catalog分别控制`Add dependency`及每行`Remove dependency`入口。使用现有原生dialog工具，title分别为Add dependency/Remove dependency；移除先显示具体目标、`Remove dependency`提交与Cancel，可逆移除不用新增服务端confirmation流程。
- 添加dialog用`Search dependency issues`搜索框，调用`issue.list {query,cursor:0,limit:20}`，范围整个当前workspace（跨项目合法），排除自身，已加载现有依赖可禁用但不能据此判断完整关系。分页`Load more issues`保持游标，切query重置；显示候选真实title/#id，明确选择后才可提交。不为候选可写性猜角色。
- add/remove动作payload均为`{issue_id,depends_on_id}`；options `{revision:baseline.revision,key:<fresh UUID>}`。只有显式提交创建冻结intent。写两端权限由服务端负责，不能先改本地依赖列表假装成功。成功后onChanged真实回读。
- 409显示服务端原因，保留选择且提供`Reload current`。回读issue.read和依赖列表取得新revision；不自动重发。添加目标已存在/移除目标已不存在时显示事实并提供`Refresh issue`关闭刷新，不制造重复动作；新鲜请求只在用户再次明确提交时生成。
- 未知网络/5xx结果保留冻结intent并锁输入，`Retry original request`重用完全相同action/payload/revision/key；关闭重开仍可重试。确定400可清intent修订。403/404或会话失效调用现有onError清数据，不保留旧受限成功或dialog。
- 每次dialog独立generation/busy；Escape/Cancel不写、返回原入口焦点。旧搜索/分页/回读/写结果均检查dialog和父级current。无依赖条数前端假上限，服务端已有最多100条/环检测，直接展示其拒绝。

- [ ] **Step 1:** 用真实member+真实Project/两Issue，先确认Issue详情已加载，再点击Show dependencies建立缺入口红灯，保留`/tmp/workpal-a54d1-red.log`。不把fixture/导入失败当行为红灯。
- [ ] **Step 2:** 实现一个Module和薄接线，完成同一浏览器添加→刷新/独立context仍在→移除的闭环。真实SQL验证edge.active变化、仅主Issue revision增长，两端要求/状态/负责人不变；审计/outbox/cache每个意图一次，移除保留既有SourceLink（读取不代表解密或放宽授权）。
- [ ] **Step 3:** core验证22条真实依赖20+2分页、候选跨页搜索/清空重置、自身不可选、跨项目合法、保存custom状态label、空态/断网Retry、文本注入无执行、Tab/Enter/Escape和焦点。查询只读不产生业务outbox；截图1440/390并目视无横溢出。
- [ ] **Step 4:** review场景1–2：真实反向依赖造成cycle拒绝，另一个有效用户改revision后409→Reload保留选择且不自动写；另一个用户已经添加/移除目标时Refresh处理，无多余业务事件。各场景先有合法正向对照，SQL拒绝不变。
- [ ] **Step 5:** review场景3–4：add和remove都在route.fetch真实成功后丢弃响应，再原intent重试；核对请求action/payload/revision/key完全一致、edge和audit/outbox/cache不重复，显示后续真实回读状态。在途关闭/重开及旧Reload结果到达时不串草稿。
- [ ] **Step 6:** review场景5–6：选中后撤请求者对当前Issue/目标Issue的read或仅write，真实拒绝且无业务变更，丢响应后撤权的缓存重试不回显旧内容；切Issue/工作区及快速搜索的迟到结果被忽略。可用真实source grants做fixture，不合成成功响应。
- [ ] **Step 7:** 运行core+review、qa.issues及review、qa.issue-transition及review/permissions、Node23、Django tests.test_web、迁移dryrun/check、85项hash。不要跑全量后端或根npm（集成Agent负责）。保留`/tmp/workpal-a54d1-*.log`及`outputs/workpal-web/a54d1-dependencies-{desktop,mobile}.png`。补测首跑绿如实记录；全部六场景完成后交父代理审查，不把个别闭环当A5完成。

来源追加可能使主Issue继承目标Issue限制，移除关系不会移除历史来源。界面不能承诺移除后恢复更广可见性；children、comments、Delivery/Review页面仍在后续任务。

## Implementation checkpoint and bounded continuation — 2026-11-20

首次Sol交付仅新Module、Issues薄接线及静态白名单；Node23和web2通过，未建立实施前行为红灯，未写浏览器QA。不能验收，不能事后隐藏入口补造红灯。父代理静态复核作两处最小修正：搜索开始清空selected时同步禁用submit；冲突回读已经收集全部依赖后隐藏Load more，避免用cursor0再追加第一页。语法检查通过，但两项尚待真实浏览器证明，不计TDD。

后续分两个有界验收任务，原合同与六组review保持：

**A5-4d1a core（本次新Agent）**：只新增qa.issue-dependencies.mjs并在允许UI文件内修复真实失败、更新apps README/package。一个脚本四组场景：①真实member只读22条依赖20+2、授权issue.read保存custom label、空态/刷新/断网Retry，SQL业务及outbox不变；②真实add→独立context回读→remove，主Issue revision、edge.active、来源历史保留及精确audit/outbox/cache增量，要求/状态/assignee不变；③候选22+分页与字面搜索，选中后延迟新的搜索响应时submit立即disabled且零POST，旧结果不覆盖新query，排除自身且跨项目合法；④Cancel/Escape/焦点、390/1440长文本安全布局和截图目视。已存在实现的补测首跑绿正常，无需另造红灯。运行core、既有Issues/transition core、Node、web2、迁移/check/hash，全绿并提交日志。只做这四组，避免再次停在未验证代码。

**A5-4d1b review（core后新Agent）**：新增qa.issue-dependencies.review.mjs，按上文Step4–6完成六组故障/撤权/迟到矩阵，并验证冲突回读全页后Load more隐藏；保持全部旧QA。其余回归和根npm随集成结果统一验收。core通过不等于A5-4d1整体验收。

A5-4d1a四组core已完成：父代理读取真实HTTP/SQLite脚本、核对SQL断言并实际复跑，四组PASS，`/tmp/workpal-a54d1a-parent-core.log`退出0；目视390px长恶意标题仅为文本，无横溢出。Sol测试中观察到并发目标读取连接重置，将每页目标读取改为顺序后通过，不把测试环境现象推断为生产网络根因。原Implementation之前没有红灯，保持流程缺口记录。子代理旧Issues/transition、Node23、web2、迁移/check及85项保护通过，`/tmp/workpal-a54d1a-*-final.log`与hash日志；六组review仍未完成，不能标A5-4d1整体完成。

A5-4d1b已交付六组完整review，无UI实现变更，子代理core/六组review/Issues和transition各相关QA/Node23/web2/迁移/check/hash最终通过；其transition review首跑Username超时后独立复跑绿，原失败保留。父代理读取67行实际HTTP/SQL脚本并复跑，在已完成cycle、409、未知写重试和旧搜索隔离后，新context启动失败：静态JS模块请求ERR_SOCKET_NOT_CONNECTED、页面只剩Workpal，随后Username等待超时。日志`/tmp/workpal-a54d1b-parent-review.log`。此前“登录根因未明”现已缩小到本次静态模块传输/初始化失败，尚未证实传输原因；本项整体保持待验收，不能把这次失败计为认证逻辑失败或直接忽略。

启动诊断任务可新增`apps/workpal-web/scripts/qa.startup.mjs`并最小修复`browser-fixture.mjs`；先通过多个独立context的真实模块加载复现、保留请求失败/页面/服务器证据，核对本fixture的ThreadingMixIn/WSGIServer队列等实际配置。候选原因需用证据验证，不能直接抬超时或自动重试。若证实只属隔离服务器承载问题，可修改该fixture承载参数，不能修改业务UI来隐藏失败。完成后重新运行完整依赖review及transition review，原断言保持，所有页面/context/route/子进程仍finally清理；日志`/tmp/workpal-startup-*.log`。无法证实时报告未知，不宣称已修复。

## 监督验收 — 2026-11-20

A5-4d1依赖界面验收通过。启动诊断在原默认backlog=5下首次6个并行context中5个失败，复现ERR_SOCKET_NOT_CONNECTED；隔离fixture设置request_queue_size=128后连续两轮各36个context通过，未添加重试或放宽断言。父代理startup日志也完整记录36个context无错误，随后独立复跑完整六组dependency review退出0，`/tmp/workpal-a54d1b-accepted-parent.log`。先前四组core已独立通过；子代理同时完成transition/core/review与相关回归，原失败日志保留。证据支持测试服务器承载修正，不能据此声称历史每次启动失败都只有这一个原因。

本验收不改变最初未建立实施前红灯的流程记录。A5仍需层级、评论/Inbox、Delivery/Review及后续Runtime等界面，依赖页面通过不等于首版完成。
