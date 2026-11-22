# Delivery 与评审闭环：第一轮实现

> 历史实现记录。当前行为以 [第二轮实现说明](behavior-consistency-implementation.md) 为准：当前交付由显式选择决定，取消新尝试不再封锁原交付，界面已移除 walkthrough 标签。

本轮按 `multica-product-review.md` 的第一轮顺序修改模型与交互，没有重新开展 Multica 线上实测，也没有新增真实执行能力。

## 已实现

- `Run` 明确区分 execution、review、reply；正式委派不会复用评论回复。运行结束与 Issue 完成分开。
- 正式运行在创建时保存任务要求、Agent 配置、项目上下文、所选 Skill 的本地目录记录及版本标记（没有版本时如实标记；不下载外部 Skill 正文）、Workflow 和上一版交付的评审信息。
- `Delivery` 保存独立 ID、递增版本、来源 Run、替代版本、摘要、产物、逐条证据和限制。原文以文本展示，不执行内容或安装命令。
- 证据支持 provided / missing / not met / not applicable；不适用也需要说明。内容缺失时可提交并退回，不能批准。
- 评审针对一版 Delivery：旧交付、新的未解决执行、需求已改变、缺少原始快照、缺少产物或证据，均不能关闭当前任务；批准必须主动确认检查材料。
- 批准使用当前 Workflow 的 review.next，退回使用 review.rejected。按钮说明目标状态。Done 不再自动排入新的执行。
- Issue 中可以直接查看交付历史；Run 详情可检查输入快照、材料与评审，第二版可展开逐版比较。
- 报告引用运行输入快照和对应交付，不把后来修改的要求当作历史输入。
- 旧数据保留原有内容与评审笔记。缺失的历史要求不会补造，缺失输入的交付需要重新发起后才能批准。

## 离线边界与约定

遵循仓库英文、中性视觉、单 HTML 离线导出约定。产品不使用 research / prototype / simulation 分类标签，而以 `Offline · No agent execution`、`Offline walkthrough` 和 `No agent, code or tests run` 准确说明执行边界。QA 不再靠禁止 simulation 等词判断可信性，而验证离线说明、证据门禁和状态行为。

所有材料由评审者输入；没有自动生成 Agent 回答、真实代码修改或测试结果。产物支持文本内容和引用，不抓取引用内容，也不将用户输入转换成可执行 HTML。证据门禁只验证材料齐备，不代替人的专业判断。账号、多人权限与生产后端仍在范围外。

## 复查

- `npm run check`：语法、领域回归测试和自包含 HTML 构建。
- `scripts/qa.mjs`：现有路由与交互回归。
- `scripts/delivery-qa.mjs`：桌面/390px 的缺证据退回、v2、批准、历史报告、文本转义、本地笔记和导出。

第二至四轮未在本轮实现：决策首页、完整项目资源、恢复与 Inbox、Chat 边界、Skill 发布与跨任务复用，以及 Squad / Autopilot 的协作语义。

本轮实际验证结果：`npm run check` 通过，共 28 项测试；现有交互 QA 与新增 Delivery QA 均通过；布局 QA 的 1440×900、1280×720、390×844、390×600、960×480 五种尺寸通过。新增交付旅程在 1440px 和 390px 下验证了零网络请求。
