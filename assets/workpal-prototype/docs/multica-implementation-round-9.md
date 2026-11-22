# 第九轮实施与验证

本轮按“全部补齐”的指示完成第八轮列出的功能缺项，保留 Workpal 品牌、英文 UI、本地评审笔记、现有工作区数据和离线单文件交付。参照源码仍为本地 Multica `428ef30fe`。

## 已补齐的操作

| 范围 | 实现 |
| --- | --- |
| 共享控件 | 新增 `src/ui.js` 与 `src/ui.css`；可搜索单选/多选、日期面板、延迟 Tooltip、菜单方向键、Escape/outside click、焦点恢复、边界翻转、visualViewport 调整、reduced motion。创建、详情、列表、看板和表单复用；原生 select 保留为隐藏的数据控件。 |
| 创建器 | 紧凑标题/描述、属性工具栏、工作区面包屑、展开、Manual/Agent 切换、内容保留、草稿提示与侧栏圆点、可展开附加字段。Agent 模式只记录排队请求，不生成假回复。 |
| 属性 | 状态、负责人、优先级、项目、日期与多标签；标签可新增文本。一般变更直接保存；交接、活动运行或手动完成通过独立确认弹窗，取消不修改记录。 |
| 看板 | 卡片负责人/优先级/日期独立操作；鼠标拖动预览、目标列与落位线、同列排序；触摸操作菜单与 M 键移动；Space 打开 Peek。 |
| Peek / 详情 | 前后切换与方向键、边界禁用、打开完整页面；标题/描述直接编辑与 Escape 取消；嵌套创建器取消返回 Peek；交付证据附加区；保留评论和评审笔记。 |
| Issues 布局 | List、Board、Table、Swimlane；状态/负责人/项目/优先级/无分组，Swimlane 的项目/负责人/父 Issue 分道，排序方向、列控制、已加载可见行选择、批量属性修改和完成项归档。Done 仍保留分页和归档保护。 |
| 集合页 | Projects、Agents、Skills 的标题范围、搜索、Filter、Display 移入共享页头；列配置、按列排序、行菜单、多选；项目批量设负责人、Agent 批量设 harness、Skill 批量收藏/取消收藏和附加到 Agent；恢复头像编辑入口与保存后焦点。 |
| 导航 | 持久化项目树、子 Issue、项目操作；大树按需展开并分批加载；220–420px 侧栏鼠标/键盘调宽，宽度持久化；收起后悬停/聚焦临时展开；保留手机背景隔离。 |
| 搜索 | 输入焦点与结果选择分离；Recent、图标、高亮、辅助类别；补会话和 Saved view；空结果和 IME 连续输入；Escape 返回。 |
| Chat | 会话列表与搜索、Agent 选择、欢迎内容、输入器；环境调查改为可选上下文；手机会话/返回和短视口输入。 |

## 功能验证

- `npm run check`：102 项前端测试、离线构建、2 项后端测试通过。
- `node scripts/round-9-qa.mjs`：1440×900、390×900；创建模式与草稿、日期/多标签、直接编辑、四种布局、批量修改、Peek、工作流取消、集合页、头像编辑与焦点、侧栏、Chat、短视口输入通过。
- `node scripts/round-9-states-qa.mjs`：1440、768、390 三种宽度，每种查看 Issues、Projects、Agents、Skills、Squads、Chat、Autopilots、Inbox、Settings、Analytics 十页。页面无横向溢出或 JS 异常；另验证 IME、空结果、长内容、展开、嵌套返回、取消编辑、必填校验、普通拖动、触摸操作入口。
- `node scripts/round-8-qa.mjs`：原搜索、焦点、草稿和卡片路径通过。
- `node scripts/archive-qa.mjs`：桌面/手机的 10,000 条 Done 数据分页、归档、恢复、持久化和评审笔记保留通过。
- 状态测试阻断 HTTP(S) 请求；无真实模型调用。所有数据操作在隔离浏览器上下文中进行，未修改用户浏览器存储。

[主路径验证](review-assets/round-9/verification.json) · [三种宽度状态验证](review-assets/round-9/states-verification.json)

## 原始控件对照与像素证据

`outputs/multica-reference` 使用 Multica 原始 PropertyPicker、Button、Dialog 与真实主题 CSS；仅为控件提供固定数据和英文翻译，不重画参照控件，也不接生产服务。`scripts/build-reference.mjs` 验证参照提交并输出可离线打开的控件夹具。开发验证依赖不进入 Workpal 的离线交付。

同一组六个状态、同一视口及 DPR=1，执行相同的“输入 In → ↓ → 继续输入 x”操作；双方均保持输入焦点并更新查询。截图等待字体和动效稳定。

| 视口 | Multica Picker | Workpal Picker | 结论 |
| --- | --- | --- | --- |
| 1440×900 | 256×233 | 256×233 | 宽高、32px 行高、14px 行字体和主文字色对齐；仍有像素差异。 |
| 390×900 | 256×234 | 256×233 | 存在 1px 高度差异；Workpal 搜索输入保持 16px，以保留手机输入要求。 |

[几何与键盘记录](review-assets/round-9/controls-comparison.json) · [像素差异统计](review-assets/round-9/pixel-comparison.json) · [桌面叠图](review-assets/round-9/1440-picker-overlay.png) · [桌面差分](review-assets/round-9/1440-picker-difference.png) · [手机差分](review-assets/round-9/390-picker-difference.png)

默认页面和交互截图在 `docs/review-assets/round-9/`。像素统计只描述该控件夹具，不转换成全产品相似度，也不代表所有页面、状态都已完成一比一验收。

## 验收边界

功能缺项已实现。完整产品的同数据双端截图差分仍未建立：本轮实际运行的是原始控件夹具，没有运行带相同数据的完整 Multica 应用。因此不能认定全产品逐像素通过。

手机检查使用 Chromium 触摸模拟和缩短视口；没有真实 iOS/Android 设备的系统软键盘证据。缩短视口通过不能替代真机输入法验收。

交付仍是 `dist/Workpal.html`，无需安装依赖、后端服务或联网即可打开。运行请求、交付和审阅均为本地记录；没有增加真实 Agent 执行能力。
