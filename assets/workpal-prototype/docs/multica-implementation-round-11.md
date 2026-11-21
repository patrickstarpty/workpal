# 第十一轮：Team 导航与集合比例

继续修正第十轮整页对照暴露的差异。

- Team 侧栏使用 All agents、My agents、Squads & members、Resources；移除重复的逐个 Agent 快捷项，保留集合页进入 Agent 的操作。Runs 与 Workflows 收到 More 中，原功能仍可访问。
- All agents / My agents 分别切换真实集合范围，同时同步导航高亮与人数。旧 Agent 缺少 owner 时仍按当前本地用户归属处理。
- Agents、Skills 默认列使用更接近原始表格的列宽；行菜单在悬停和键盘聚焦时出现，不再为菜单固定占用整列。自定义列组合继续使用可伸缩布局。

验证：`npm run check`（102 前端、2 后端、离线构建）；`round-10-qa.mjs`；新增 `round-11-qa.mjs` 在 1440/390 宽度验证不同 owner 的 All/My 切换、高亮、手机菜单、行菜单和页面溢出；`round-9-states-qa.mjs` 的三宽度十页回归通过。

Agents 与 Skills 的三宽度同数据参考截图保存在 `docs/review-assets/round-11/`，使用原始 Multica 页面及第十轮共享夹具。原始仓库未修改。交付仍为 `dist/Workpal.html`。

系统软键盘环境阻塞及全产品像素验收边界仍见第十轮报告；本轮没有将它们改为通过。
