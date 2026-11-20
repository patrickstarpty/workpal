# Workpal Issue Status History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 成员能阅读Issue当前阻塞原因及责任人，并按需查看真实状态变更历史，判断下一步由谁处理。

**Architecture:** 按codebase-design把历史加载、授权分页、展示和请求生命周期收进一个只读Module。Issues页面继续拥有当前详情；人员显示复用已验收people Module，状态标签仅取该Issue保存的工作流快照。复用已有issue.transitions.list，不改业务后端。

**Tech Stack:** 原生ES modules/DOM/CSS、Django静态白名单、SQLite与现有Playwright，无新增依赖。

**Spec:** [首版设计](../specs/2026-11-20-workpal-software-development-design.md)、[A5基础计划](2026-11-20-workpal-phase-a-foundation.md)、[负责人改派验收](2026-11-20-workpal-issue-assignment-ui.md)。沿用GPT 6.1 Sol实施、父代理监督的授权。

## Global Constraints

- “每一步都应回答：当前目标是什么、谁负责、依据是什么、产物在哪里、下一步由谁决定。”
- “Issue 使用稳定 status key，另设 unstarted、started、done、closed 生命周期分类。自定义状态仅归类，不隐含派发或完成行为。”
- “界面继续使用 Inter、中性表面、紧凑行、克制边框和阴影。”
- 仅显示真实保存事实，English UI，用户内容按文本渲染；保留390px、键盘及review notes。不从最后一条历史推算当前Issue状态，不把Done解释为PR已合并或环境已恢复。
- 不改旧原型/业务后端/公共client，不Git写操作、不安装、npm exec/npx、外网、模型或Runtime调用。仅原Node22.22.0、.venv-workpal/bin/python、已装Playwright与隔离loopback测试。

## Review Focus

1. 自定义status key/label：使用Issue保存快照，历史workflow_sha256不匹配时保留原key，不套用另一版本的名称。
2. 当前Blocked与历史阻塞责任人不是负责人：展示正确字段，人员不在目录或已离开时明确Unavailable person。
3. 授权过滤后的分页：显示服务端返回顺序与游标，不暴露被过滤记录数，不重复或跳过已授权页。
4. 隐藏/重开、刷新与切Issue/工作区时旧响应不能重现已关闭内容；错误重试不重复追加旧页。
5. 只读操作不得改变Issue、要求、状态历史、通知、outbox、幂等或确认；断网/撤权不能冒充空历史。

---

## Task A5-4c1: Current blocking facts and on-demand status history

**Files:**
- Create `apps/workpal-web/src/features/issue-status-history.js`：历史阅读Module。
- Modify `apps/workpal-web/src/features/issues.js`：当前阻塞事实与历史入口的薄接线，保留现有Status标签和所有写入口。
- Modify `apps/workpal-web/src/styles.css`：仅新历史区域的紧凑样式，不影响要求历史。
- Modify `services/workpal/workpal/web.py`、`services/workpal/tests/test_web.py`：仅新资产白名单及断言。
- Create `apps/workpal-web/scripts/qa.issue-status-history.mjs`；修改apps package新增qa:issue-status-history和apps/service README真实范围。
- 不改people/client/ui、创建/编辑/归档/改派Module、旧QA、业务后端或计划。

**Current facts:** 当真实issue.status_category==='blocked'，在当前Status附近显示`Blocking reason`及issue.blocked_reason，`Blocked owner`及createPersonLabel({userId:issue.blocked_owner_user_id,...})。不得用assignee_user_id代替。非blocked不显示过期阻塞字段。现有`Status: <saved label>`和Assignee保持独立；不增加状态写控件。

**History Interface:** `createIssueTransitionHistory({client,issue,current,onError}) -> HTMLElement`，issue为已读DTO，current绑定页面及detailSequence。返回带aria-label="Status history"的section，初始只有标题和Show status history；直到用户点击才请求，不为每个Issue预加载历史。内部复制issue.id及workflow_snapshot，拥有cursor、rows、loading/error与请求序号。

**Read contract:** `client.perform('issue.transitions.list',{issue_id,cursor,limit:20})`，completed后读取`{items,next_cursor}`，每条含id、from_key、to_key、actor_user_id、actor_executor_id、reason、before/after_blocked_owner_id、before/after_blocked_reason、requirements_version_id、workflow_sha256、revision、created_at，可能另有approval。保留服务端升序；若next_cursor非0显示Load more status history，加载中禁止重复点击。刷新从0清旧页，分页错误保留已读页并提供Retry，成功不重复追加。初次成功items空显示No status changes.；网络/非completed是错误，不显示伪空结果。403/404经现有访问丢失处理清旧内容。

展开后按钮改为Hide status history，另有Refresh status history。隐藏清空内容并使在途请求失效；重开从0真实读取。所有await/catch/finally检查current及request sequence/展开状态，刷新/隐藏或详情切换不能被旧响应覆盖；不缓存到浏览器存储。

**Rows:** 每条用可键盘操作的原生details/summary，summary显示`<from label> → <to label>`和实际created_at；仅当event.workflow_sha256===issue.workflow_snapshot.sha256且key在states中才用保存label，否则显示原key。展开行显示Issue revision N、Changed by（用createPersonLabel查询实际actor_user_id；仅首次展开该行才加载人员，避免默认并发读取20名人员）、非空Executor真实标识、非空Reason。若有before/after阻塞字段，分别显示Previous blocking reason / Blocking reason及Before blocked owner / After blocked owner，用真实字段及people标签。用户文字不innerHTML，缺失人员不冒名；不把requirements_version_id当要求number显示。approval内容暂由后续Delivery/Review界面处理，不生成执行或恢复结论。

Issues仅在catalog含issue.transitions.list时接入历史Module。历史刷新不替换当前Issue/要求内容；当前详情由既有Refresh issues回读。为每条展开人员标签传入当前历史请求生命周期，重读或隐藏后的旧人员结果不可重现。保持信息紧凑，长reason/label可换行；原生details使用Tab/Enter，Show/Hide按钮焦点不丢失。

- [ ] **Step 1:** QA用withBrowser建立真实Project和已发布custom workflow（含backlog/todo/blocked/done分类、不同key和label），通过workflows.service.create/publish、work.service.set_workflow绑定，再创建Issue并用transitions.transition生成真实记录。至少两次状态变化后以member登录读真实详情，实施前点击Show status history失败于缺入口，日志/tmp/workpal-a54c1-red.log；不得import失败或实现后临时隐藏入口。
- [ ] **Step 2:** 实现上述一个Interface、当前阻塞字段、薄详情接线、资产、文档及script，使同一测试转绿。不加写控件、通知模拟或客户端权限绕过。
- [ ] **Step 3:** 扩充真实26条转换记录（例如todo↔blocked往返，最后停在blocked），分页20+6无重复，与数据库有序ID/状态/revision/reason对应；custom label来自保存快照。当前阻塞owner与assignee不同，UI必须显示正确姓名。展开一行验证Changed by及前后阻塞事实，空Issue显示No status changes.；Hide再Show重新读。SQL对比Issue/IssueRequirements/IssueTransition/Notification/Outbox/IdempotencyResult/Confirmation不变，Registry read audit允许追加。
- [ ] **Step 4:** 验证初次断网错误→Retry恢复、长恶意reason/label只作文本、1440/390换行及Tab/Enter展开/隐藏，截图outputs/workpal-web/a54c1-status-history-{desktop,mobile}.png。自定义workflow通过正常Interface构建，不能mock成功响应；finally清理自有fixture资源。
- [ ] **Step 5:** 运行新qa.issue-status-history、qa.issues及qa.issues.review、qa.issue-assignee及qa.issue-assignee.review、Node23、Django test_web2、迁移/check；核对85项保护SHA256，仅.gitignore既有差异。日志/tmp/workpal-a54c1-*.log；根npm/其他浏览器和完整权限/迟到矩阵留父代理。后端未变不要求重复614全量。交付实际实现和绿灯，不仅建立红灯；不提交、不宣称状态转换写入或A5完成。

## Independent supervision and next work

父代理补验私有历史事件的授权分页、Issue/历史来源撤权、历史与人员标签迟到、刷新与翻页失败后重试、工作区切换、workflow SHA不匹配标签回退，运行必要集成与根npm后验收。随后A5-4c2另写状态转换、阻塞及完成门禁的交互计划；依赖、子任务和讨论继续按A5范围实施，不删减首版目标。

## Supervision result — 2026-11-20

功能验收通过。Step 2–5 对应实现和验证已完成；Step 1 的实施前红灯没有执行，保留未勾选，不追认完整TDD。父代理新增 `qa.issue-status-history.review.mjs` 的12条独立浏览器检查，发现解除阻塞的历史没有展示责任人新值Unassigned，并已在用户要求后续只监工之前修复。真实缺陷红灯为 `/tmp/workpal-a54c1-review-first.log`，修复后12条全部通过，见 `/tmp/workpal-a54c1-review-green.log`。首次运行另有一条在登录前置步骤超时，未到历史断言；未确认原因，不将其当作已修复产品缺陷，完整重跑该场景通过。

覆盖授权过滤后的20+5分页、历史/Issue撤源、翻页失败重试、隐藏/刷新/切Issue/切工作区后的旧响应隔离、人员标签局部重试、旧工作流SHA回退及离开工作区的人员显示。原core的26条真实转换、20+6分页、SQL只读不变量、文本安全、键盘和1440/390布局通过；桌面/手机截图已目视检查。

最终验证：历史core、Issues core及8项review、Assignee core及16项review、Node23、Django web2、迁移检查、system check和根npm全部退出0。日志 `/tmp/workpal-a54c1-accepted-*.log`；85项保护SHA256仅 `.gitignore` 既有差异。此次无业务后端变更，614项后端全量沿用A5-4b5a记录，没有声称本轮重跑。状态写入和A5整体仍未完成。
