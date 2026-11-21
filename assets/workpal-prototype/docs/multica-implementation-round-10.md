# 第十轮实施与整页对照

参照本地 Multica `428ef30fe` 原始组件，继续完成第七轮意见。本轮修改产品源码并重新构建 `dist/Workpal.html`；第八、九轮已实现的交互继续保留。

## 本轮实际修正

- 创建器缩至 600px，标题直接聚焦，描述区、带图标的属性按钮、展开和关闭位置重新对齐。模式切换移到底部；手机底部使用两行布局。附加字段与操作说明不再占据默认首屏。
- 补齐 Create another：创建后保留项目上下文，清空内容、重新聚焦标题，可以连续创建。支持 Ctrl/Cmd+Enter；空白标题禁用提交。模式切换保留输入，草稿标记继续工作。
- Projects 默认使用 Status、Priority、Progress、Lead、Due date、Recent activity、Created 列，增加状态徽标、进度环、负责人头像；历史数据缺失的日期显示破折号。
- Agents 默认使用 Status、Runtime、Model、Last active、Runs；Skills 使用 Used by、Added by、Updated，标题与描述同处紧凑单行。Publisher 与 Added by 分开，避免把技能原作者误写为添加人。已有扩展字段仍可在 Display 中选择。
- 集合页去除内容区额外留白，恢复紧凑表头和 36px 行高，修复侧栏 Agent 头像被拉宽的问题。Skills 默认按更新时间排列，Agents 默认显示 My agents；补上旧 Agent 数据缺少 owner 时的当前用户归属回退。表头全选、取消全选、过滤结果选择、行菜单及搜索保持可用。零选择时隐藏批量操作栏，选择后出现。Issues 的零选择工具栏同样收起，Display 保留全选入口。
- 用户输入继续转义；未新增运行时依赖；未修改用户浏览器数据或评审笔记。

## 完整参考页面

新增 `scripts/build-full-reference.mjs`、`scripts/round-10-comparison.mjs` 和 `scripts/diff-full-pages.mjs`。参考夹具直接挂载 Multica 原始 DashboardLayout 和十个页面组件，不是重新绘制的参考图。原始仓库未修改。

原始 React 页面使用本地 API 数据适配器，Workpal 使用同一份离线数据：282 个 Issues、3 个 Projects、4 个 Agents、30 个 Skills，以及 Squads、Autopilot、会话记录。缺失的创建时间、Skill 更新时间和添加者使用明确的固定 QA 元数据，双方同时应用；这些值只存在于隔离夹具，不写入用户工作区。状态、负责人和路由按两个模型映射。生产服务、外部模型与实际 Agent 执行均未连接。

对照范围为 Issues、Projects、Agents、Skills、Squads、Autopilots、Inbox、Chat、Settings、Analytics，视口为 1440×900、768×900、390×900。创建器额外截取相同的 Manual 状态。截图等待字体加载，统一 reduced motion，并阻断外部 HTTP(S) 请求。

- [30 组页面与创建器记录](review-assets/round-10/full-page-comparison.json)
- [整页原始像素差异](review-assets/round-10/full-page-differences.json)
- 每组的原图、差分和叠图保存在 `docs/review-assets/round-10/`，命名为 `multica-*`、`workpal-*`、`diff-*`、`overlay-*`。
- 参考版本与数据 SHA 在 `outputs/multica-reference/full-reference-manifest.json`。

整页差分包含 Workpal 品牌、原有导航内容、历史数据和专有交付区域等差异；不把原始像素差分换算为“相似度”，也不将测试通过描述为全产品逐像素一致。参考页面的数据适配器不代表线上 Multica 服务。

## 验证

- `npm run check`：102 项前端测试、离线构建、2 项后端测试。
- `node scripts/round-10-qa.mjs`：桌面/手机的禁用提交、连续创建、快捷键、焦点恢复、文本转义、集合全选/清除/空搜索。
- `node scripts/round-9-qa.mjs`：创建模式与草稿、日期/多标签、详情编辑、四种 Issues 布局、批量修改、Peek、工作流取消、集合页、头像、侧栏、Chat。
- `node scripts/round-9-states-qa.mjs`：三种宽度的十页、IME、空状态、长内容、展开、嵌套弹层返回、取消、校验、鼠标拖动和触摸移动。
- `node scripts/round-8-qa.mjs`：搜索连续键盘输入、焦点、属性浮层边界与草稿。
- `node scripts/archive-qa.mjs`：桌面/手机 10,000 条完成记录的分页、归档、恢复、持久化和评审笔记保留。

[最终验证汇总与源码哈希](review-assets/round-10/verification.json) · [新增交互结果](review-assets/round-10/interaction-verification.json) · [最终文件 SHA-256](review-assets/round-10/deliverable.sha256)

## 系统键盘的明确阻塞

尝试启动本机 iPhone 16 Pro / iOS 18 模拟器，编译了只加载离线 HTML 的 WKWebView 测试壳。设备成功启动，但 `simctl install` 超过 10 分钟无返回，`simctl listapps` 超过 7 分钟无返回；界面工具三次返回 `cgWindowNotFound`，无法操作系统键盘。已终止本轮挂起的安装/查询进程，保留[诊断记录](review-assets/round-10/ios-keyboard-blocker.json)。

因此系统软键盘仍未验收。当前通过的是 Chromium 触摸、短视口、浮层边界和嵌套焦点验证，不能替代可操作设备上的系统输入法。这一项需要可访问的 iOS/Android 设备环境。

交付继续是英文 Workpal 离线单文件。Agent 请求与交付为本地记录，本轮未增加真实后台执行。
