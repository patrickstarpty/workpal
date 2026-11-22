# Workpal 第六轮审阅：侧栏、铅笔与搜索的界面对齐

评审日期：2026 年 11 月 19 日。Workpal 基线 `489fb4e`；参照本地 Multica 前端源码 `428ef30fe`。本轮聚焦界面还原与操作一致性，不扩展后端功能审计。仅新增评审文档和证据文件，没有修改产品源码。

**用户指出的差异成立：当前已有相似的导航框架，但铅笔图形、按钮最终尺寸、提示、搜索组件和导航状态没有完整对齐。只核对“有没有这个入口”不足以验收“是否做得一样”。**

先更正本轮初始判断：当前左轨已经有 New issue 和 Search，顺序也基本正确；不能沿用旧版本说它们不存在。当前默认主题已经是 Neutral，不能继续沿用第四轮的 Warm 默认结论。以下以当前源码与本轮浏览器实测为准。

## 对照口径与证据

- 参照对象是 Multica **产品应用**的 AppRail、Space panel、Global actions 和 Command bar，不是 multica.ai/docs 文档站的导航。
- Multica 一侧的尺寸和行为来自实际组件源码、样式与测试；未声称已对其线上登录后界面做逐像素截图比较。Tailwind 尺寸按默认 16px 根字号及 4px spacing 换算。
- Workpal 一侧使用重新构建的离线 HTML，在隔离 Chromium 中以 1440×900、390×844 检查。没有读取用户浏览器数据。
- 共享预览不支持本地 file URL，返回 `unsupported-protocol: file:` 后改用隔离 Playwright；没有为审阅启动服务器。临时打开的公共文档预览已关闭。
- Workpal 品牌保留；本轮不因品牌文字与 Multica 不同而判定还原失败，也不要求在产品界面增加 prototype/research/simulation 标签。

证据文件：

- [Workpal 桌面导航](review-assets/round-6/workpal-desktop.png)
- [Workpal 当前搜索弹窗](review-assets/round-6/workpal-search.png)
- [Workpal 手机菜单与背景焦点](review-assets/round-6/workpal-mobile-menu.png)
- [浏览器尺寸与交互观测](review-assets/round-6/observations.json)

## 已对齐的部分应保留

本轮桌面实测：左轨宽 56px、第二栏宽 280px、页头高 48px、左轨动作 SVG 为 18×18px、正文为 Inter 14/20，默认 Neutral。左轨顺序为 Workspace → New issue → Search → Work / Team / Chat / Auto；Auto 也是 Multica 的实际 rail 文案。

这些不是主要偏差来源。左轨按钮虽然在源码声明为 36×36，最终实际只有 36×32，属于另一层 CSS 覆盖问题，见 U01。验收必须读最终 computed style，不能只看某条声明。

## 第一优先级：用户直接指出的铅笔和搜索

### U01 · 铅笔不是同一个图形，点击区也被通用样式压矮

**Multica：** `SquarePen`，即圆角方框加短笔；点击区 36×36，SVG 18×18。证据为 `packages/views/layout/global-actions.tsx:49–58`、`layout/rail-styles.ts:25`、`packages/ui/icons/glyphs.ts:239`。

**Workpal：** 左轨调用 `icon('edit')`，路径是一整支斜向 Pencil，没有方框；实测点击区 36×32，SVG 仍为 18×18。证据为 `src/studio.js:883`、`src/icons.js:96`。

尺寸原因已确认：`btn()` 总是添加 `.btn`（`src/studio.js:30`）；`.dock-command` 在 CSS 第 18 行声明 height:36px，后面的 `.btn` 在第 31 行声明 height:32px。两者优先级相同，后者覆盖前者。左轨 Search 也受影响，下方导航的纵向位置随之改变。

**对齐要求：** 创建入口使用对应的 SquarePen 图形；全局图标按钮使用独立尺寸规则，最终 computed size 必须为 36×36。不要仅继续叠加局部 padding 来补偿。搜索图形还有细小轮廓差异，但优先处理铅笔语义、按钮尺寸和位置，而不是先纠结圆半径的细微差别。

### U02 · 铅笔缺少配套的草稿状态、提示和上下文行为

**Multica：** New issue 有未提交草稿圆点，统一 tooltip 包含 C 快捷键；Search tooltip 包含 Cmd/Ctrl+K。项目详情页的全局新建动作继承当前项目，C 与按钮使用同一路径。

**Workpal：** 当前只有原生 title，没有草稿标记，没有 C 创建快捷键。实测在 Skill Hub 项目页点击左轨 New issue，表单 Project 默认是 TAP；本次在没有旧新建草稿的情况下复现。

证据：Multica `layout/global-actions.tsx:16–28,44–58,72–89`、`packages/core/shortcuts/definitions.ts:84–85`；Workpal `src/studio.js:883 → :614 → :211–220`，键盘处理 `:1260–1268`。

**对齐要求：** 左轨、页头和 C 共享明确的创建入口；项目页继承项目；草稿 dot 由真实草稿状态派生；tooltip 展示动作与快捷键。C 不应在输入框、textarea 或 contenteditable 内触发。

这与第四轮 N03 的旧草稿跨入口覆盖不同：即使没有草稿，当前全局入口也没有传递项目上下文。

### U03 · 全局搜索复用了普通编辑弹窗，组件结构没有对齐

**Multica：** 独立 Command bar，最大宽 640px，顶部约 20%；无可见的标题栏和关闭按钮。第一行直接放放大镜、透明输入和 Esc，下面是结果列表与键盘提示。源码：`packages/views/search/search-command.tsx:56–64,201–240`。

**Workpal：** 复用普通 560px dialog，包含 60px 标题栏、关闭按钮、24px 内容 padding、label、34px 边框输入、Search 提交按钮。初始空搜索实测为 560×220，1440×900 下 y=340，即垂直居中。源码：`src/studio.css:32,43`、`src/studio.js:667,863–864`。

**对齐要求：** 搜索单独成为组件，不套普通编辑表单的标题、label、提交按钮。采用搜索行 → 可滚动列表 → 固定操作提示的层级。输入文案采用与用途一致的 `Search, or type what needs doing...`，保留英文 UI。

这解释了用户直观看到的“搜索框不像”：问题涉及整个外壳和内容层级，单改 border、圆角或输入框宽度不够。

### U04 · 搜索的输入、结果、键盘和默认内容都需要对齐

浏览器已确认：

1. 打开搜索后，焦点在 Close dialog，而不是输入框。
2. 输入 Engineering，Agent 结果数量仍为零。
3. 提交 Search 后才出现 Engineering partner；重绘后焦点变成 BODY。

当前结果是一组可换行的小按钮，没有类型分组、匹配高亮、主次信息或选中行。方向键逻辑仅用于评论建议，并非搜索结果。空查询只有空表单。

Multica 的对应组件自动聚焦、输入即更新，有纵向结果列表、分组、图标/头像及匹配提示；↑↓选择、Enter打开、Escape关闭，底部展示操作说明。空查询包含上下文动作和 Recent；`>`、`#`、`@` 区分命令、Issue 和人员范围。

源码：Multica `search-command.tsx:215–229`、`search/rows.tsx:17–23,90–100`、`search/footer.tsx:45–71`、`search/root-view.tsx:695–750`、`search/matching.ts:47–63`；Workpal `src/studio.js:667,671,1077,1197–1203,1249–1268`、`src/studio.css:31`。

搜索对象目前只有页面、Issue 标题/ID、Skill 和 Agent；没有对应的 Project、Squad、Saved view 或会话对象搜索。命中“Projects”页面名不等于能够找到一个具体项目。

**对齐要求：** 先覆盖当前本地已有对象和动作，即可实现即时搜索、分组、最近访问及键盘选择。动作可以打开预填表单，不需要假装搜索已经执行 Agent 工作。

初始焦点问题在第四轮 N08 已提出，本轮再次验证并纳入组件对齐清单，不重复宣称为全新发现。

## 第二优先级：统一导航与搜索的真实行为

### U05 · 页面内搜索与全局搜索没有各自一致的组件规则

Multica 的 Skills/Agents/Projects 集合页使用头部可展开搜索，支持 `/` 打开、Esc/清除按钮；Issue 表格另有紧凑搜索。相关控件采用约 28px 高的页面过滤规格。

Workpal 的 Skill Hub 使用永久展开的独立工具栏输入；Issue 搜索藏在状态/负责人过滤栏里；没有统一清除按钮或 `/` 操作。页面过滤与全局命令搜索的外观、清除和焦点规则均未建立。

源码：Multica `layout/collection-page.tsx:237–242,270–285,303–355`、`issues/components/table-view.tsx:609–648`；Workpal `src/studio.js:352–354,498–500`、`src/studio.css:32,41`。

**对齐要求：** 全局 Command bar 和页面过滤分别实现；页面过滤使用统一的展开、清除、Esc 和焦点恢复规则。不能用同一个通用 input 在每页随意改变布局。

### U06 · 侧栏分组画出了箭头，没有实现折叠

Workpal 的 Inbox、Views、Projects、Workspace 分组标题是普通 DIV；hover 出现 ChevronDown，但不能折叠，也没有 aria-expanded。本轮浏览器确认这些标题没有按钮语义。

Multica 的可折叠分组使用真实按钮，具有展开状态，并保留折叠偏好。

源码：Multica `layout/panel-nav.tsx:89–136`、`panels/work-tree.tsx:299–302`、`panels/views-section.tsx:136–138`；Workpal `src/studio.js:876–880`、`src/studio.css:24`。

**对齐要求：** 箭头对应真实的鼠标和键盘操作，显示当前展开状态，并按 Workspace 保存。如果某组不支持折叠，不应给它同样的可折叠外观。

### U07 · 项目导航缺少当前对象状态与树形关系

Workpal 只显示前六个项目和前三个 Saved view；项目行是平面按钮，没有具体项目的 active 状态。进入项目详情时高亮的是泛化的 Projects 项，而不是当前项目，也不能展开项目下的 Issue。

Multica 项目节点分别保留 active、expanded 和当前 Issue 的位置；相关上下文操作属于项目节点。Team 的分组也包括 All agents/My agents、Squads & members、Resources，当前 Workpal 的两组平面入口尚未对应这个层级。

源码：Multica `panels/work-tree.tsx:727–742`、`panels/work-panel.tsx:99–118`、`panels/team-panel.tsx:368–452`；Workpal `src/studio.js:32,878–880`。

**对齐要求：** 首先保证当前项目明确高亮、全部项目可发现、展开后当前任务仍可定位；不要通过静默截取数量控制侧栏长度。树形层级和项目行操作再按同一规则补齐。

### U08 · 收起只做了隐藏，缺少临时展开和可调宽度

Workpal 默认第二栏宽 280px，在中等宽度直接变成 240px；收起后 `display:none`，通过页头按钮重新展开。

Multica 默认同为 280px，但可在 200–320px 调整并保存；收起后有临时预览 panel 的机制，也考虑键盘焦点进入。

源码：Multica `layout/space-panel.tsx:37–42,85–102`、`packages/ui/components/ui/sidebar.tsx:29,188,302`；Workpal `src/studio.css:8,28,52`、`src/studio.js:1125`。

**对齐要求：** 区分固定展开、收起和临时预览；宽度调整有范围、持久化和窄屏回退。此项属于尚未实现的交互能力，不能只以默认宽度相同判定完成。

## 第三优先级：基础组件与窄屏状态

### U09 · 通用按钮与输入混合了不同尺寸层级

Workpal 默认按钮高 32px，但字号为 13/18、图标 16px；Multica 默认同高 32px，使用 14/20 和 18px 图标，小按钮才使用更紧凑的文字和图标规格。

Workpal 通用输入高 34px；Multica Input 默认 32px。背景和 focus ring 也不同：Workpal 为 surface 背景、brand 色 2px 环；Multica 为透明背景和 ring token 的 3px 环。搜索 Command input 又有独立规则，不等于通用 Input。

源码：Workpal `src/studio.css:31–32`；Multica `packages/ui/components/ui/button.tsx:9,49`、`input.tsx:12`、`styles/tokens.css:148`。

**对齐要求：** 明确默认按钮、小按钮、图标按钮、通用输入和页面过滤输入各自的规格；修正级联关系。比较最终渲染出的高度、字号、图标、focus 和 disabled 状态，不能只让所有控件“看起来都很紧凑”。

### U10 · 手机菜单缺少完整模态行为，外壳也仍沿用桌面

**浏览器已复现：** 390×844 打开 Workspace menu 后连续 Tab，焦点从菜单链接进入后面的 Workspace menu、Filter issues、Display、New issue 和任务列表。菜单仍覆盖在前面，背景控件却可以获得焦点；证据截图中可见背景任务的焦点边框。

当前只是将 aside 固定定位覆盖；未建立背景 inert、完整焦点约束和 Sheet 语义。Multica 的 CompactNavSheet 使用 Sheet 容纳 AppRail 和 panel，并在导航后统一关闭。

同时，Workpal 手机页面仍保留桌面式留白、圆角和边框；Multica 将这些卡片外壳规则放在 md 以上，窄屏填满窗口并处理 safe-area。

源码：Multica `layout/compact-nav-sheet.tsx:28–60`、`packages/ui/components/ui/sheet.tsx:32–34`、`layout/dashboard-layout.tsx:35,63`；Workpal `src/studio.css:53`、`src/studio.js:1124–1125,1252`。

**对齐要求：** 菜单打开后焦点进入菜单并保持在其中；背景不可交互；关闭回到触发按钮；选中目的地后关闭。窄屏应使用独立布局规则，而不只是把桌面侧栏盖到页面上。

源码还显示 Multica 对手机可编辑文本设置至少 16px，Workpal 没有对应保护。这属于需要补充移动端验收的风险，本轮没有实测 iOS 自动缩放，不把它写成已发生事故。

## 建议实施顺序与验收

第一批做 U01–U04：铅笔图形、真实按钮尺寸、tooltip/草稿/C/项目上下文，以及完整的 Command bar。这是用户已明确指出、且每天会触达的部分。

第二批做 U05–U07：页面过滤、分组折叠、当前项目与树形导航。第三批做 U08–U10：侧栏预览/调宽、基础控件规格和窄屏 Sheet。基础样式修正应同时回归第一批，避免再次出现 `.btn` 覆盖专用组件尺寸。

验收应固定 Workspace、页面、主题、视口和状态，对照下列路径：

1. 左轨默认、hover、focus、pressed、有草稿；确认最终 36×36 点击区和对应图形。
2. 项目详情点击铅笔与按 C，均打开属于当前项目的新建表单；输入文字时 C 不触发。
3. Cmd/Ctrl+K 后立即输入，看到即时分组结果；↑↓、Enter、Esc 全程可用，关闭后焦点可恢复。
4. 空搜索、无结果、长结果、不同对象类型及本地动作，不出现普通编辑表单的提交按钮布局。
5. 页面内 `/` 搜索、清除和退出只影响当前列表，与全局搜索互不混淆。
6. 折叠分组、切换项目、打开任务、返回和刷新后，位置与展开状态仍可理解。
7. 390px 菜单打开后，Tab 无法进入背景页面；关闭和导航行为可预测。

本轮 `npm run check` 通过：102/102 项测试，离线构建成功。另完成上述隔离浏览器检查。现有测试通过不能证明界面对齐；本轮已经出现“源码声明 36px、最终只有 32px”的明确反例。后续需要把组件几何和关键键盘路径纳入验收，而不是只检查页面能否打开。
