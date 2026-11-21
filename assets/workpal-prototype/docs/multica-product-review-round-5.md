# Workpal 第五轮评审：代码交付与执行上下文

评审日期：2026 年 11 月 19 日。相关代码基线为 `8ee1be9`（Add environment chat, workspace connections, and delivery context）。本轮仅修改评审文档，没有修改产品源码。

**最新实现已补上资源、Runtime 权限记录、PR 记录、交付规则和连接设置，上一条审阅中“缺少这些入口”的结论已经过时。现在的核心问题是对象关系：批准没有绑定代码版本，同一个 PR 不能跨返工尝试，项目资源也没有被解析为本次工作范围。**

本轮确认 7 项发现：1 项 P1、6 项 P2；另列 1 项应调整的产品规则。分类同时注明行为问题、契约不明确或设计缺口，避免把所有差异都当成意外程序错误。没有真实模型执行、仓库操作、授权连接或 PR 合并，复现中的 SHA 和 PR 均为本地记录。

## 先更新已有结论

下列能力已有实质实现，不再列为缺失：

- Project Resources 支持 Repository、Starting ref、Local folder、Owning machine 和 In place/Worktree。
- Workspace 的仓库目录支持 HTTPS/SSH、编辑、去重和删除；项目可从该目录选取资源。
- Runtime 可保存完整机器配置和人工记录的 read/push/PR/tool 状态。
- 项目可配置 PR target、分支约定、检查说明和完成规则；普通项目编辑会保留资源与交付规则。
- Issue 已有 PR 记录，包含源/目标分支、SHA、合并、CI、Review、Conflicts；Delivery approval 与合并状态已开始分离。
- Settings → Code 和 Connected apps 已有入口。GitHub/Jira setup 显示 Authorization required / Not connected；Runtime 显示 Reported ready，而非已验证授权。
- 普通 Issue 执行会复制完整 `machine/resourceMachines`。第四轮 N07 对普通执行的原始 Runtime 快照缺口已有修复；新的环境会话入口仍有遗漏，见 C07。

没有把未连接 GitHub、未执行 checkout、未执行真实检测当成本阶段缺陷。当前 AGENTS.md 要求离线单 HTML、英文 UI、保留本地笔记、无真实后端；这些边界继续有效。第三、四轮其他问题没有在本轮逐条复测，不应自动关闭，也不应直接把旧行号当成新代码的证据。

## 发现概览

| 编号 | 级别 | 类型 | 结论 |
| --- | --- | --- | --- |
| C01 | P1 | 行为与数据关系 | 批准提交 A 后，PR 改成 B 仍可完成 |
| C02 | P2 | 返工流程 | 同一个 PR 不能关联后续尝试，被要求另开 PR |
| C03 | P2 | 规则契约 | 配置 target=main，交付到其他分支仍可完成 |
| C04 | P2 | 输入关系 | 切换仓库保留旧 ref；分支 URL 不能拆解 |
| C05 | P2 | 执行计划 | 机器和目录被并列展示，没有说明本次适用资源 |
| C06 | P2 | 追溯与导出 | 代码报告漏 PR 事实，环境报告漏已保存的调查上下文 |
| C07 | P2 | 跨入口一致性 | 环境请求绕过普通 Run 的完整 Runtime 快照 |

## C01 · P1 · 批准没有绑定到具体代码版本

**证据：隔离 VM 与 Playwright。模型方法建立基础场景，关键 PR 更新与完成操作经现有 UI 执行。**

1. 创建完成规则为 Approved delivery + merged PRs 的任务。
2. Delivery 的 Artifact 明确写入提交 A；关联 PR 的 SHA 也为 A。
3. 批准 Delivery，评审备注为 `Reviewed commit A`。
4. 进入 Issue → PR → Update，将 SHA 改为 B，并记录为 Merged；其他字段保持不变。
5. 点击 Record completion，填写理由并提交。

结果：出现 `Completion recorded.`，Issue 为 Done；唯一批准仍是 Reviewed commit A，而 PR 已是 B。没有重新评审提示，没有被批准的 SHA 集合，也没有证明 B 与 A 之间的关系。

证据位置：`src/model.js:665` 的批准只存 decision/note/reviewer/time/destination；`src/code-delivery.js:55–57` 更新 PR 当前 SHA；`:12–21` 的完成校验只看 Delivery 批准、任务要求、PR 合并及仓库覆盖。人工和自动完成均依赖这一检查，见 `src/studio.js:993–997`。

**改进：批准必须绑定可识别的代码交付版本。** 至少包含 Repository、PR、reviewed head SHA、Delivery ID 和所审证据。PR head 变化后保留旧批准，但把新版本显示为待审；合并提交与被审 head 的关系另行记录，不能简单要求 merge commit 等于 head SHA。

离线阶段可以要求用户记录这些事实及来源，不必调用 GitHub。真正需要防止的是把“曾批准过这条 Delivery”当成“已批准 PR 的任何后续修改”。

验收：A 已批准、head 变 B 时，不得继续沿用 A 的批准完成任务；批准 B 后可继续；历史仍能分别看到 A、B 的交付与决策。

## C02 · P2 · 一次正常返工被迫创建新的 PR

**证据：隔离 VM 与 Playwright，关键重新关联动作经 UI 执行。**

Run 1 提交 v1 并关联 PR #7；Request changes 后启动 Run 2，提交并批准 v2。随后 Update 原 PR，把 Delivery run 改为 Run 2 并填写新 SHA，系统拒绝：

```text
This PR is linked to another attempt. Use a new PR for the new attempt.
```

原 PR 仍属于 Run 1；v2 的完成检查只看 Run 2，因而找不到它的 merged PR。界面没有解除旧关联或让同一 PR 服务多个尝试的操作。用户只能改变实际交付方式，另开一个 PR 来配合原型。

证据位置：`src/code-delivery.js:53–54` 强制同一 Issue 的 PR URL 只能属于一个 Run；`:15–16` 只认当前 Delivery Run 的 PR。`src/studio.js:361–363` 提供了可选择的 Delivery run，但选择返工 Run 后仍会失败。

**改进：PR 的身份应独立于 Run。** PR 持续演进；每次 Run/Delivery 引用它的某个版本。多次尝试可以引用同一 PR 的不同 SHA，旧交付保留旧引用，当前交付引用新版本。不要为了绑定新尝试而改写历史，更不要强迫用户关闭、重开真实 PR。

验收：v1 → Request changes → 同一 PR 推送新提交 → v2 → 新批准 → 合并，可以走完；v1 仍能追溯到原 SHA。

## C03 · P2 · PR target 是约束还是默认建议，没有讲清楚

**证据：隔离 VM，分离其他变量。**

当次输入快照中的 `deliveryRules.target=main`；关联 PR 的 target 为 `release/legacy`。同仓库、同 Run，CI 为 passed、Review 为 approved、Conflicts 为 clear。批准后 `blocker=''`，任务可进入 Done。

证据位置：`src/studio.js:352–354` 将字段放在 Delivery rules 中并命名 PR target branch；`src/code-delivery.js:8–22` 的完成校验不读取 target；`:55` 保存实际 target。

这里需要先修正产品契约：

- 如果它是必须满足的交付目标，完成前应比较当次预期目标和 PR 事实；例外需要明确理由。
- 如果只是新建 PR 记录时的默认值，应在界面中说清楚，不要让用户误以为已经成为完成门槛。
- 多仓库项目应允许每个变更仓库有自己的目标，不能默认所有仓库都使用一个分支名。

同样应明确 Required checks 是 Agent 的工作说明、人工验收要求还是系统门槛。本轮没有把“PR 已合并但 CI failed 仍允许同步状态”单独认定为缺陷：Multica 的合并后状态同步本身不等于额外执行 CI 门禁。Workpal 新增的交付规则需要有自己的明确语义。[GitHub integration](https://multica.ai/docs/github-integration)

验收：规则的强制性在配置、启动预览、完成阻塞原因中一致；不能配置时像约束，完成时只当作被忽略的文字。

## C04 · P2 · 仓库 URL 与 Starting ref 没有一起管理

**证据：隔离 Playwright，项目资源表单实际保存。**

路径一：先保存 `Frontend / https://github.com/acme/frontend / release/2026`。重新编辑，通过 Workspace repository 改选 backend，URL 改变了，旧的 ref 和名称仍保留。最终保存为：

```json
{
  "name": "Frontend",
  "url": "https://github.com/acme/backend",
  "startingRef": "release/2026"
}
```

已确认的是新仓库未经确认继承了旧起点；没有声称该分支一定不存在。

路径二：粘贴 `https://github.com/acme/frontend/tree/develop`，被直接拒绝，没有拆出仓库和 ref。用户此前明确提出的分支链接输入尚未实现。

证据位置：`src/studio.js:1148` 选仓库时只更改 URL/type；`src/code-delivery.js:35–36` 保存旧 ref；`src/integrations.js:21` 拒绝 GitHub 两段路径以外的地址，Project resource 在 `src/code-delivery.js:32` 直接复用此校验。

**改进：把项目资源输入解析与 clone URL 校验分开。** 分支链接先解析，再交给仓库校验；仓库身份变化时清除或要求重新确认旧 ref。普通手输 URL 与从目录选择应该使用相同规则。Multica 文档也明确描述了分支 URL 拆解，以及换仓库时清除旧 starting branch 的行为。[Project resources](https://multica.ai/docs/project-resources)

验收：切换仓库不会默默带入原 ref；分支链接解析后的 URL/ref 都可检查；解析不了的输入给出具体说明，不猜测实际存在的分支。

## C05 · P2 · 执行预览没有说明哪些资源适用于这台机器

**证据：隔离浏览器，模型方法建立配置，通过 Start run → Start workflow 检查。**

Engineering partner 绑定 Mac A，机器默认目录为 `/tmp/default-a`；项目唯一 Local folder 属于 Mac B，路径为 `/Users/reviewer/project-b`，模式为 worktree。启动预览同时显示：

```text
Machine: Mac A
Working directory: /tmp/default-a
Project checkout on B · /Users/reviewer/project-b · Mac B · worktree
```

可以创建 Run，快照仍只是这几项配置的集合，没有说明 B 的目录不适用于 A，也没有显示本次的有效资源、回退仓库或计划目录。

证据位置：`src/code-delivery.js:4–6` 复制全部资源与所属机器；`src/studio.js:339–340` 将机器默认目录标为 Working directory，并并列展示项目资源；`:258–261` 直接用于启动预览。

**改进：配置目录与执行计划要分开。** 启动前根据所选 Runtime 解析适用资源，区分机器默认目录、项目本地目录及本次计划目录。其他机器的本地目录应明确标为不适用；有仓库时说明回退来源，没有可用代码来源时给出选择 Runtime 或资源的下一步。

这不要求真的建立 worktree。尚未执行时展示“计划”，并在执行后另行记录实际目录即可。不能仅凭配置就声称已检出代码。Multica 的本地目录同样只对绑定的 daemon 有效。[Project resources](https://multica.ai/docs/project-resources)

验收：切换 Agent/Runtime 时，预览中的适用资源和计划随之变化；不能把其他机器的目录当成当前可用目录。

## C06 · P2 · 报告遗漏支撑本次工作的已保存事实

### 代码交付：报告有 Done，没有对应 PR 证据

**证据：隔离 VM，调用界面所使用的当前模型操作。**

创建代码任务，提交并批准 Delivery；保存 PR #9123、源分支、40 位 SHA、CI passed、review approved 和 merged；按照合并完成规则记录 Done，再生成 Execution report。

实际：Issue 为 Done，工作区保存了一条 PR，Issue Activity 也记录 PR URL；但报告中没有 PR URL、SHA、源分支或 CI passed。completion 只记录一条通用的 manual reason，不能用它还原合并依据。

证据位置：`src/model.js:681–699` 导出输入快照、Run events、Artifact、Delivery decision 和当前完成记录，没有导出 `db.pullRequests`；`src/studio.js:998` 的 PR 更新日志属于 Issue Activity，不在上述 Run 事件中。

### 环境请求：数据存在，却被报告成未记录输入

**证据：完整 UI 路径。**

打开 UAT 会话，发送继续分析的请求；打开 Run inspector，再通过会话的 Workspace actions → Execution report 选择该 Run。`run.context.environment=UAT`，快照中有七条会话历史；Inspector 和报告不显示 UAT 或已有证据中的 `up_731`，报告还写着 `Original requirements were not recorded.`。

证据位置：`src/environment-chat.js:55–64`、`:76–82` 已保存调查上下文；`src/studio.js:294` 对无 Issue 的 Run 只显示少量属性与事件；`src/model.js:682–686` 只读取 `run.inputSnapshot`。

**改进：统一报告来源，但保留 Run 类型差异。** 代码执行报告应包含此次交付所引用的 PR revision、检查/评审记录、来源和记录时间，以及批准与完成的关系。环境调查报告应导出已经捕获的环境、历史材料和配置，不能用“没有 Issue inputSnapshot”推断“没有任何输入”。

新生成报告可以显示生成时事实，但必须与批准时的证据快照分开；已经保存的报告保持不可变。不同类型的 Run 不必硬套一个表单，却应遵守相同的可追溯要求。

验收：离开工作区只看导出报告，仍能知道审的是哪个版本、依据什么事实完成，或该调查请求继承了哪些材料；不能把人工记录写成外部系统已验证。

## C07 · P2 · 环境请求没有复用已修复的 Runtime 快照

**证据：隔离 VM 对照普通执行与环境请求。**

Quality partner 绑定 RUNTIME-001，名称 UAT laptop，目录 `/workspace/customer-a`。分别创建普通执行和环境请求，然后修改 Runtime 为 customer-b。

普通执行保留了原机器名称、平台、目录和访问状态；环境请求只保存 `agent.runtimeId`，原目录不在环境快照的任何字段中。

证据位置：`src/code-delivery.js:4–6`、`src/model.js:512–517` 为普通 Run 采集完整上下文；`src/environment-chat.js:55–64`、`:74–78` 使用独立路径，只复制项目设置和 Agent，漏掉 Runtime 实体。

**改进：共享创建运行上下文的规则。** 被调查的 DEV/UAT/PRD 与承载请求的 Runtime 是两种对象，应分别记录；环境入口也要捕获当时的机器配置，后续变更不能覆盖历史。

这与 C06 不同：C06 的环境历史已经保存，只是未显示和导出；C07 的机器配置从未被捕获，无法靠调整报告模板恢复。它是第四轮 N07 在普通执行修复后，新入口遗漏的旁路问题。

## 需要调整的产品规则：资源目录不等于变更范围

当前完成检查要求：本次 Run 快照里的每个 Repository，都必须有属于本次 Run 的 merged PR。现有测试明确要求这个行为，因此它是设计规则，不能误报成程序偶发错误。

隔离 VM 已确认：项目含 Application 和仅供参考的 Shared library，本次只修改 Application，PR 已合并，仍被要求为 Shared library 提供 merged PR。源码为 `src/code-delivery.js:17–21`。

项目仓库可能是依赖、规范、文档、只读参考，也可能是本次变更对象。需要分成：

- **项目资源目录：** 长期可用的代码和资料。
- **本次交付范围：** 哪些仓库实际修改，哪些只读取，是否存在无需 PR 的交付。
- **交付证据：** 每个修改仓库对应的 PR revision 或明确允许的其他交付形式。

Local folder 也应关联其代码身份或交付方式，否则路径只能说明文件在哪台机器，不能证明关联 PR 来自这份代码。不能通过强迫参考仓库制造空 PR 来满足检查。

## 下一版应先收敛的对象关系

以下是针对 Workpal 的设计建议，不是宣称 Multica 的内部数据结构与之完全相同。

| 对象 | 应表示什么 | 应保留的关系 |
| --- | --- | --- |
| Project resource | 长期代码来源或本地目录绑定 | 仓库身份、默认 ref；或机器、目录、模式 |
| Run context | 一次尝试的输入和计划 | 资源、规则、Agent/Runtime 当时值，实际适用范围 |
| PR | 持续演进的代码审阅对象 | 稳定身份，可被多个 Run/Delivery 引用 |
| PR revision | 某次代码版本及观察结果 | head SHA、base、检查、评审、来源、观察时间 |
| Delivery | 本次供人审阅的交付 | Artifact、验收证据、变更仓库及 PR revision 集合 |
| Approval | 对特定交付版本的判断 | Delivery ID、被审代码版本、评审人和说明 |
| Completion | 本次为何达到完成条件 | 所用规则、批准、合并事实、人工验收或例外 |

首先修 C01、C02：批准与代码版本绑定，允许同 PR 返工。随后用明确的“本次变更范围”替代“所有项目仓库都要 PR”，同时落实 target/checks 的规则含义。资源解析、机器适用性和统一快照应一起处理，最后让 Inspector 和报告呈现同一套事实。

DEV/UAT/PRD 的调查会话是 Workpal 新增的业务分类；Multica 文档中的 Environments 指运行产生的开发服务器、预览或应用，具有机器、运行、地址及进程生命周期。二者不能因为都叫 environment 就视为同一能力。未来若增加运行预览，应建独立对象并关联 Issue/Run，而不是把聊天分类直接当作已连接环境。[Environments](https://multica.ai/docs/environments)

## 最小完整验收流程

下一版先完整验证这一条代码交付路径：

1. 项目绑定应用仓库、参考仓库及某台机器的本地目录；明确本次只修改应用仓库。
2. 选择 Agent 后，预览能说明适用机器、代码来源、起点和计划目录；切换机器时适用性同步变化。
3. Run 1 交付 PR #7 / SHA A；评审请求修改。
4. Run 2 沿用 PR #7，交付 SHA B；历史 v1 仍引用 A。
5. 批准 B；若 head 再变 C，不能沿用对 B 的批准。
6. 按明确的目标分支与检查规则记录合并事实；参考仓库无需制造 PR。
7. 根据完成策略记录 Done 或等待人工验收，并保存关联证据。
8. 导出报告，能还原上述资源、版本、评审、合并与完成关系。

这条路径可以全部用本地人工记录和状态校验表达，不需要提前接入真实模型或 GitHub。运行速度、代码质量和真实授权能力仍留待后端阶段验证。

## 验证与范围

- `npm run check` 通过：85/85 项测试，语法检查和离线构建通过。
- `environment-chat-qa.mjs`、`code-delivery-qa.mjs` 在 1440px、390px 通过。
- `integrations-qa.mjs` 在 1440px、390px 通过，覆盖仓库和 setup 编辑、授权状态、键盘、文本转义、重载、工作区隔离及笔记保留。
- 新问题使用隔离 VM、独立浏览器上下文或源码验证，逐项注明。没有访问用户实际浏览器存储，没有执行安装、push、merge 或授权操作。
- 测试通过只说明现有断言成立；同 PR 返工、批准后的 head 变化、切换仓库保留旧 ref 等新场景尚未被这些断言保护。
- 审阅期间出现的 Analytics 源码改动不属于本轮工作，没有覆盖或回滚它们。本轮评审聚焦上述代码交付与环境上下文实现。
