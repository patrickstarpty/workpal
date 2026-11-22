# Workpal 第七轮审阅 Multica 界面与交互还原

当前 Workpal 的应用外壳已经接近 Multica，但创建器、属性选择器、集合页和看板操作仍采用不同的组件结构。要达到一比一还原，需要按 Multica 的组件与状态逐项重做；仅继续调整颜色、圆角和间距不能完成这一目标。

本轮只新增审阅记录与证据，没有修改产品源码。

## 审阅基线

- Workpal：仓库根目录的 `index.html → src/studio.js → dist/Workpal.html`，HEAD `9f17ed6`，包含当前未提交更改。`apps/workpal-web` 是另一套前端，不属于本轮离线原型的结论范围。
- Multica：本地 `../multica`，HEAD `428ef30fe`。对照产品应用组件源码，不混用官网、文档站或旧版截图。
- Workpal 浏览器检查：重新构建的离线文件，隔离 Chromium，1440×900 与 390×844。查看 Issues、Projects、Agents、Skills、Squads、Chat、Autopilots、Inbox、Code settings、Analytics；重点操作搜索、创建、属性编辑、看板、侧栏与手机菜单。
- Multica 侧为源码核对，尚未运行同一数据集下的双方截图差分。因此这里能确认组件和操作路径的差异，不能宣称已完成逐像素验收，也不提供相似度百分比。源码中的 Tailwind 尺寸按默认 16px 根字号换算。
- 保留 Workpal 品牌、英文 UI、离线单 HTML、本地评审笔记。真实模型、远程授权和后台执行不属于本轮 UI 还原要求；不增加 prototype、research、simulation 产品标签，不伪造运行成果。

## 已对齐或已修复的部分

上一轮的结论不能直接照搬。本次重新确认：

- 默认 Neutral；Inter 正文；左轨 56px、第二栏 280px、页头 48px。
- 左轨铅笔已经采用 `squarePen`，最终点击区为 36×36px。
- 全局搜索已使用独立外壳，宽 640px，桌面顶部位于 20% 视口位置；自动聚焦、即时搜索、类型分组和 `>`、`#`、`@` 前缀已实现。
- 点击铅笔或按 C，均能从 Skill Hub 项目详情继承该项目。
- 侧栏分组已有真实折叠和持久化；项目与 Saved view 不再截断为固定前几项；当前项目已有高亮。
- 手机菜单打开时背景 `.main` 为 inert；连续 35 次 Tab 未进入背景。Escape 后回到菜单按钮。手机输入框实测为 16px。

以上应保留。搜索完整键盘行为、导航树、菜单组件和弹层动效仍有差距。

## 第一批调整 直接影响主要操作

### R01 新建 Issue 需要替换为对应创建器

Workpal 的普通新建窗口在桌面实测为 560×834px，包含可见标题栏、逐字段 label、两列原生 select、验收条件和执行选项，打开后先聚焦关闭按钮。Multica 的手动创建模式默认是约 672×384px 的紧凑编辑器：轻量面包屑、直接输入标题、描述编辑区、属性 pill 工具栏和底部动作，并支持展开。其 Agent 与手动模式共享同一个弹层，切换时保留内容。

**调整：** 让左轨、C、页头、项目和 Squad 的创建入口使用同一个创建器及其上下文参数。按参照模式还原标题、描述、属性工具栏、展开、草稿和提交状态。Workpal 特有字段要有明确位置，不应把默认创建器重新撑成长表单。初始焦点放标题；创建模式切换保留输入。

来源：Workpal `src/studio.js:211`、`:863`；Multica `packages/views/modals/create-issue.tsx:962`、`:1029`、`:1084`、`:1556`，`create-issue-dialog.tsx`。

证据：[当前桌面创建器](review-assets/round-7/new-issue.png)、[当前手机创建器](review-assets/round-7/mobile-new-issue.png)。

### R02 属性修改需要使用锚定选择器

Workpal 点击 Status 后打开 560px 宽的居中 `Issue property` 窗口，再操作系统 select 并点 Save。Assignee、Priority 和 Due date 也复用该路径。Multica 使用贴近触发字段的 PropertyPicker，包含相应图标、当前勾选、可选搜索和键盘选择；需要工作流交接确认时再进入对应确认步骤。

**调整：** 建立共用的 Status、Assignee、Priority、Project、Labels、Date picker，分别支持单选、多选或日期语义。详情、列表、看板与创建器复用它们。普通属性编辑应在原位置完成；工作流确认保留独立规则，不应每次修改都打开整张表单。原生 select 和 date 输入无法保证跨平台展示与 Multica 相同。

来源：Workpal `src/studio.js:615`；Multica `packages/views/issues/components/pickers/{property-picker,status-picker,assignee-picker,priority-picker,due-date-picker}.tsx`。

证据：[Status 的当前弹层](review-assets/round-7/status-property.png)。

### R03 看板卡片的局部操作和拖动行为不同

实测点击卡片上的负责人头像会进入整个 Issue 详情，不能直接改派。聚焦卡片后按 Space 同样进入详情，没有 Peek。把 Backlog 卡片拖入 To do，会打开含标题、描述、项目等全部字段的编辑窗口。Multica 卡片内的负责人、优先级、日期有独立选择器；另有 Issue Peek、键盘切换及排序交互。不能把“卡片能点、能拖”视为还原完成。

**调整：** 区分卡片导航和字段操作，补齐局部 hover、popup-open、selected、dragging、drop target 和 peeked 状态。还原拖动预览、落位及工作流确认路径；不需要交接确认的移动不应变成完整需求编辑。为鼠标、键盘和触摸操作分别验收。

来源：Workpal `src/studio.js:163`、`:1211`；Multica `packages/views/issues/components/board-card.tsx`、`issue-peek.tsx`。

证据：[当前看板](review-assets/round-7/board.png)、[拖动后的编辑窗口](review-assets/round-7/board-drag.png)。

### R04 集合页没有使用同一套页面结构

Projects 当前是有留白和外框的 Project directory 卡片。Agents 是四列静态表头，缺少页面搜索、筛选、Display、列排序和批量选择；实测按 `/` 没有打开页面搜索。Skills 首屏是统计与趋势图，下方才是目录。这与 Multica 三者共用的 CollectionPageHeader、CollectionSearch、CollectionList、Display 和批量工具条不同。

**调整：** 先还原共用集合页：标题与范围切换、筛选、可展开搜索、Display、新建入口、紧凑行、列控制、排序、行菜单和选择状态，再填入各对象的列。Skill Hub 的使用统计与榜单应移到独立入口或详情，保持主列表的参照布局。保留这些业务内容，不让它们占据一比一页面的默认首屏。

来源：Workpal `src/studio.js` 中 `projects`、`agentsView`、`skillsView`；Multica `packages/views/layout/collection-page.tsx`、`layout/collection-list/`、`projects/components/projects-page.tsx`、`agents/components/agents-page.tsx`、`skills/components/skills-page.tsx`。

证据：[Projects](review-assets/round-7/projects.png)、[Agents](review-assets/round-7/agents.png)、[Skill Hub](review-assets/round-7/skills.png)。

### R05 搜索外壳修好了 但选择状态还没有还原

输入 Engineering 后能即时得到 Engineering partner。按 ArrowDown 后，真实焦点移到结果按钮；继续输入 `x`，查询仍是 Engineering。结果表现为按钮的蓝色焦点框，而不是输入框保持可编辑、结果行独立高亮。首次空查询渲染 341 个结果，没有 Recent。结果还缺少图标或头像、匹配高亮与辅助信息。

**调整：** 将输入焦点与结果选中状态分离；方向键切换选中项时仍可继续输入，Enter 打开选中项，Esc 逐层退出。空查询按参照提供上下文动作和最近访问。复原分组语义、结果行信息和键位提示；补全本地已有的会话与 Saved view 对象搜索。不能仅凭宽度和位置相同验收 Command bar。

来源：Workpal `src/studio.js:672`、`:1279`；Multica `packages/views/search/{search-command,root-view,rows}.tsx`。

证据：[结果被实际聚焦后的搜索](review-assets/round-7/search.png)，`observations.json` 的 `search`，`verification.json` 的 `searchEmpty`。

### R06 Issue 详情仍有不同的编辑路径与内容层级

Workpal 的标题与描述为静态展示，修改要点 Edit issue，再进入完整表单；Project 和 Labels 在属性区仍是纯文本。默认首屏还依次展示 Code delivery、Deliveries、Sub-issues 等区块及较大的空状态。Multica 详情中标题和描述是直接编辑入口，属性具有各自控件，并按同一详情组件服务完整页面和 Peek。

**调整：** 先还原标题、描述、属性和 Activity 的位置与编辑方式，再安排 Workpal 的交付证据扩展。必要的证据与本地评审笔记继续保留；可通过附加区或折叠区域承载，避免挤占参照页面的主内容。标题、描述、属性改动后应维持当前阅读与评论位置。

来源：Workpal `src/studio.js:232`；Multica `packages/views/issues/components/issue-detail.tsx:3792`、`:3958`、`:4160`。

证据：[当前 Issue 详情](review-assets/round-7/issue-detail.png)。

## 第二批调整 补齐组件状态和页面覆盖

| 项目 | 当前差异 | 调整要求 |
| --- | --- | --- |
| 导航树与侧栏 | 当前项目已高亮，但项目不能展开其 Issue；Team 仍是两组平面入口；侧栏收起直接隐藏 | 对照 Work tree、All agents/My agents 等分组；还原树节点展开、对象菜单、侧栏调宽与收起后的临时预览 |
| Display 与列表 | Issues 只有 Board/List，Grouping 固定 Status；行是整行按钮 | 以当前参照的页面范围补齐 Table、Swimlane 和分组、排序、列与批量操作；Gantt 只在参照支持的 Project 页面出现 |
| Tooltip 与草稿提示 | 铅笔有原生 title 和 C 提示，但没有统一 Tooltip，也没有草稿 dot | 还原样式、延迟、方向、快捷键 keycap；已有草稿驱动圆点，弹出菜单时抑制同锚点 tooltip |
| Dialog 与菜单 | Workpal 遮罩为 30% 暗色，参照基础遮罩为 10%；实测点背景仍不关闭；普通窗口首焦点在 X | 对照具体弹层的 outside click、Escape、初始焦点、关闭后焦点与嵌套层级；分别实现 Dialog、Popover、Menu、Select 和 Sheet |
| 动效 | 有按钮 hover/press，但没有对应的弹层开合与侧栏宽度过渡 | 复用参照的 motion token。基础 Dialog 开合为 100ms，侧栏为 220ms，创建模式尺寸切换另为 300ms；保留 reduced motion |
| Chat 首屏 | 当前默认进入 DEV/UAT/PRD 调查选择页 | 对照 Multica 的 Agent、会话和输入区组织方式；把环境调查作为可选上下文，避免替换整个参照首屏。消息卡、输入器和浮窗另建状态清单 |
| 手机交互 | 菜单隔离和 16px 输入已修复，但新建窗口仍是几乎占满高度的长表单 | 继续验收 picker 边界翻转、软键盘、长标题、嵌套弹层、safe-area 和返回行为；桌面控件缩窄不等于手机效果相同 |

参照源码：`packages/views/layout/space-panel.tsx`、`global-actions.tsx`、`rail-styles.ts`，以及 `layout/panels/{work-tree,team-panel}.tsx`、`issues/components/issues-page.tsx` 与 `issues-header.tsx`、`chat/chat-page.tsx`、`chat/components/chat-empty-state.tsx`；基础控件在 `packages/ui/components/ui/`，动效参数在 `packages/ui/styles/tokens.css`。

## 建议实施顺序与验收口径

1. **固定参照和允许差异。** 使用 `428ef30fe` 的具体主题、字号、视口和页面状态建立参照集。Workpal 品牌与业务数据属于允许差异；独有业务内容应明确放在哪里，不能边还原边改参照的默认布局。
2. **先做基础组件。** 建立 Button、IconButton、Tooltip、Input、Menu、Popover、Dialog、Sheet、Picker 的共享规格与行为。当前 `studio.css` 末尾覆盖已经修复了部分尺寸，但继续靠追加覆盖无法保证组件变体、焦点和动效一致。
3. **完成一条代表路径。** Issues → New issue → 属性选择 → 看板局部操作/拖动 → Peek/详情 → 评论。整条路径经过验证后，再把基础组件用于 Projects、Agents、Skills 等集合页。
4. **补齐其余页面。** 导航、Chat、Inbox、Settings、Squads、Autopilots、Analytics 按同样方法逐页登记；没有完整状态证据的页面不得标记为一比一完成。
5. **以状态而非页面数量验收。** 每个组件至少检查 default、hover、focus-visible、pressed、selected、open、disabled，以及适用的 loading、empty、error、overflow。固定同一数据、时间、字体与 DPR，对双方截图做叠图/差分；交互用相同键鼠操作检查焦点、选中项、滚动、开合和返回位置。

视觉验收应分别记录布局边界、字体、图标路径、间距、色值、边框、阴影和动效。文本抗锯齿误差可单独识别，不能用它掩盖布局与组件结构不一致。搜索“输入 → ↓ → 继续输入 → Enter → 返回”、属性“打开 → 选项 → 确认/取消”、看板“局部编辑 → 拖动 → Peek”都应成为固定行为验收路径。

保持离线交付不要求所有源码挤在一个文件中：可以拆分共享控件与页面模块，再通过现有构建内联为一个 HTML。建议移植参照组件的展示和行为契约；在本阶段不必引入 Multica 的生产后端或整套运行时依赖。

## 验证记录

`npm run check` 通过：102/102 项前端测试、离线构建、2 项后端测试。专项浏览器观测未捕获页面异常；没有真实模型调用，也未修改用户的现有存储。共享预览两次截图超时后，改为隔离 Playwright 读取离线构建。

这些检查证明现有检查项通过，不证明视觉还原完成。完整记录见 [页面与交互观测](review-assets/round-7/observations.json)、[看板与补充验证](review-assets/round-7/verification.json)。
