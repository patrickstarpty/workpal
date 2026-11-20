# Workpal Issue Hierarchy UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接通真实父任务阅读、子任务分页、改挂/解除与创建子任务。

**Architecture:** 独立深Module拥有层级读取、选择与写意图；Issues只接详情代际、导航与刷新。复用真实创建composer，不复制后端权限、环检测或工作流状态机。

**Tech Stack:** 原生ES modules/DOM、Django、现有Playwright临时SQLite/member session；无新依赖。

**Spec:** `docs/superpowers/specs/2026-11-20-workpal-software-development-design.md`、`2026-11-20-workpal-phase-a-foundation.md`末尾A5-4d2、`2026-11-20-workpal-issue-dependencies-ui.md`及本轮用户范围。

## Global Constraints

- 本轮仅设计；父代理评审后编码，沿已批准并行执行方式，不重新询问。不得委派、Git写入、安装、npm exec/npx、外网、模型或真实Runtime。
- English UI、Workpal、Inter中性紧凑行；textContent/el文本节点；键盘Tab/Enter/Escape与焦点返回；1440/390不溢出。无模拟事实、隐藏总数、人审新门禁或Run派发。
- 独立后端/apps已授权；旧原型及85项原基线保护继续生效。仅接受`2026-11-20-workpal-protection-exceptions.json`列出的.gitignore和src/studio.js精确hash；保留用户确认的移动菜单单行变化，不重建/回退基线。
- Node命令一律`/Users/patrick/.nvm/versions/node/v22.22.0/bin/node`；Python一律`.venv-workpal/bin/python`。根`npm run check`由父代理执行。

## Verified backend Interface

已读`work/hierarchy.py`、`issue_actions.py`、`issues.py`及`tests/test_hierarchy.py`：
- `set_parent(actor,issue_id,parent_issue_id,revision)`；Registry `issue.set_parent` payload `{issue_id,parent_issue_id}`，client options `{revision,key}`。revision为child当前revision，0解除；返回完整Issue VIEW。父项同workspace、双方当前write权限、父项未归档、无环由后端检查。只递增child revision；register_object追加来源，解除不删除旧SourceLink，assignee授权会重查。
- `children(actor,issue_id,**filters)`；Registry `issue.children.list`只接受`{issue_id,cursor,limit,include_archived}`，返回`{items,next_cursor}`。items为PROPS，**没有workflow_snapshot**；按当前Issue和要求来源授权过滤，无total。禁止给该动作加query。父项用`issue.read {issue_id:parent_issue_id}`精确读取，0才是无父项。
- 父候选`issue.list {query,cursor,limit,include_archived:false}`跨当前workspace项目；客户端仅排除自身，不能靠候选可见判断可写或检测环。
- `create(actor,project_id,title,description='',criteria=None,assignee_user_id=0,source_refs=None,parent_issue_id=0)`；`issue.create`已有parent_issue_id、无需revision，需key。要求独立创建，workflow_snapshot与初始backlog取自所选project，非父项。创建不启动Run。
- `client.perform(actionId,payload,{revision,key,confirmationId,current}={})`已隔离workspace/auth generation；current是已实现的同步本地有效性回调，不序列化、不授予服务端权限。feature须隔离详情/对话框/读取代际；cached写响应不能当最新事实，成功后真实回读。

## Review Focus（五项自审风险）

1. children无snapshot且无隐藏总数：只展示title/#id、真实status_key；不借父workflow解释子状态。Task 1覆盖。
2. 列表空页、网络失败、403/404不可混淆；撤权清旧内容/缓存/dialog，不能声称没有子项。Task 1、2覆盖。
3. 409包含cycle/归档父项/CAS：保留选择并显式Reload，绝不自动写。Task 2覆盖。
4. 关闭重开时写可能已提交：原payload/revision/key冻结，旧响应不碰新dialog；重试后回读。Task 2、3覆盖。
5. 普通创建与不同父项草稿串context：每个草稿固定parent，不把context写成composer全局默认值。Task 3覆盖。

## Task 1: Authorized hierarchy reader

**当前验收：通过。** 依据末尾2026-11-20监督验收记录；下方原执行清单与历史过程保留，不把未预录的红灯补记为测试先行。

**Files:** Create `apps/workpal-web/src/features/issue-hierarchy.js`、`apps/workpal-web/scripts/qa.issue-hierarchy.mjs`、`apps/workpal-web/scripts/qa.issue-hierarchy.review.mjs`。Modify `apps/workpal-web/src/features/issues.js`仅薄接线、`services/workpal/workpal/web.py` ASSETS新增该Module、`services/workpal/tests/test_web.py`资产GET/HEAD最小接线；`apps/workpal-web/src/styles.css`仅必要布局。后续两项沿用这些文件。不改browser-fixture、client、dependencies或B/D文件。

**Consumes:** 现存`createIssueDependencies`接线方式、`el`、`openDialog`、`withBrowser(run)`/`signIn(page,base,username,password)`；真实catalog/read/children合同如上。

**Produces (新增):** `createIssueHierarchy({client,issue,actions,current,onError,onChanged,onNavigate,onCreateChild}) -> HTMLElement`。返回section aria-label `Issue hierarchy`；onNavigate(id)交Issues既有read(id)，onChanged()真实刷新列表/详情；current同时检查页面和详情generation。onCreateChild(parent,returnFocus)仅Task 3接通，之前不展示入口。Module私有baseline、read/search/dialog generation、cursor、selection、intent，不导出服务端状态机。

- [ ] 写浏览器命名场景`member_parent_children_navigation_pagination`、`hierarchy_read_revocation_and_late_navigation`：member真实session，跨项目父子、22个可读子项和受限项，20+2分页、include archived切换重置cursor、父子导航重新授权、parent=0；搜索只测父候选（Task 2）。空态文案`No visible subtasks.`，失败显示Retry而非空态；当前403/404清section/已缓存列表并沿onError清详情。延迟读后切Issue/workspace/logout不重现旧内容。
- [ ] 运行Node上述新QA脚本；预期红灯为缺少`Issue hierarchy`入口，不以import错误充当业务红灯。
- [ ] 实现读Module与薄接线；heading `Parent issue`/`Subtasks`，父0显示`No parent issue.`；加载当前授权父事实和children分页，无总数。文本只用el/textContent。每页原子接纳，失败不追加半页；Retry保留原cursor，刷新从0开始。
- [ ] 同命令转绿；真实SQLite快照证明Issue/IssueRequirements/SourceLink、Outbox、IdempotencyResult无写变化（read AuditEvent允许准确追加）。保存1440和390截图及无横溢出断言，不为低影响样式新增单测。

## Task 2: Explicit reparent and detach

**Files:** Task 1 Module和两份QA；必要样式仍在同一styles.css；Issues不接编辑内部状态。

**Consumes:** Task 1 Interface；`issue.list`、`issue.read`、`issue.set_parent`上述精确合同。

**Produces:** Interface不扩张；Module内部新增`Change parent` dialog、`Remove parent`显式提交（payload parent_issue_id=0），catalog有issue.set_parent才显示。内部intent `{payload:{issue_id,parent_issue_id},revision,key}`，selection/conflict在关闭重开保留。

- [ ] 新增`reparent_detach_sql_persistence`、`parent_search_permissions_cycle_cas`、`parent_lost_response_replay_and_dialog_generation`场景；运行两QA预期缺Change parent红灯。
- [ ] 实现父候选搜索Search parent issues、20项Load more issues、query变化归零与请求代际；选择后提交。两侧权限由后端判定。409保留selection，禁提交，`Reload current`读取child及真实父项显示最新值/revision，再由用户显式提交新意图；关闭重开仍保留冲突，不自动回读后写。归档父项/cycle的409也遵循此流程。
- [ ] 未知结果锁输入，`Retry original request`完全相同payload/revision/key；关闭不取消已发业务事实，重开可原意图重试，旧dialog响应不覆盖新视图。400可修订；当前403/404清选择/intent/缓存/dialog。current失效后迟到结果静默隔离，不错误清新context。
- [ ] 两QA转绿：使用第二独立browser context重新登录读取持久关系；runPython精确断言Issue.parent_id（解除为NULL）、child revision+1、父revision不变、current_requirements_id/全部criteria keys及IssueRequirements行、status_key/workflow_snapshot/blocked字段不变，SourceLink追加且解除保留。对比AuditEvent action_id/object refs、Outbox、IdempotencyResult：失败无业务写，成功一次写缓存，丢响应重放无额外成功写审计/outbox/cache；读审计分开计数。真实第二context制造CAS、self/间接cycle、归档父项、跨workspace和源权限撤销；候选25项分页/字面搜索/乱序响应，选择不授write。注入“服务端收到并执行后丢响应”，不可只在执行前abort。

## Task 3: Child creation through the real composer

**Files:** Modify `apps/workpal-web/src/features/issue-create.js`、`features/issues.js`、Task 1 Module及QA；回归运行已有`qa.issue-create.mjs`/`qa.issue-create.review.mjs`。不扩展people/requirements-form，已有消费者只需要现有稳定key与真实人员选择。

**Consumes:** 现存`createIssueComposer({client,current,onError,onCreated})->{open(returnFocus)}`、`createRequirementsForm()`、`createPersonPicker({client,value,current,onChange,onError,heading})`；现有project.list分页与真实issue.create。

**Produces (新增兼容扩展):** composer构造参数可选`parentIssue=null`，值仅`{id,title}`的创建时快照；open签名不变。Issues为每个详情创建独立child composer实例，普通toolbar composer继续无parentIssue。onCreateChild(parent,returnFocus)打开该实例，current绑定该详情；成功onCreated刷新并导航新Issue。parent不是共享picker状态或全局默认值。

- [ ] 新增`child_create_independent_requirements_project_and_assignee`、`child_draft_context_unknown_replay_and_access_loss`；运行QA预期缺Create subtask红灯。
- [ ] catalog有issue.create显示`Create subtask`；composer显示文本Parent issue及固定父title/#id，草稿空要求、不复制父状态/criteria/项目；保留真实project和assignee选择。提交冻结payload包括parent_issue_id；普通创建不携带旧父ID。关闭重开同实例保留草稿/原意图；切详情使实例失效，旧实例响应不清新草稿、不导航、不通知新详情。新父实例和普通创建分别拥有draft/intent；权限失效清受限草稿。
- [ ] QA转绿：跨项目不同自定义workflow创建，SQLite精确断言parent_id、project_id、assignee_id、独立requirements version/稳定criteria keys、所选project初始status/snapshot；父事实全不变，无Run/交付新增。验证真实创建通知/outbox按已有合同、audit/cache仅一次；服务端提交后丢响应、关闭重开原key重试、两context持久化、父/项目/要求撤权和归档拒绝、切父/普通创建/工作区/登出迟到隔离。
- [ ] 对Task 1–3完整键盘操作Tab/Enter/Escape、返回触发按钮焦点、长恶意文本纯文本、390无横溢出保留截图；旧创建两QA回归。

## Execution commands and acceptance

以上每个新QA命令均为`/Users/patrick/.nvm/versions/node/v22.22.0/bin/node apps/workpal-web/scripts/qa.issue-hierarchy.mjs`及同目录`qa.issue-hierarchy.review.mjs`。命名场景在脚本输出独立PASS证据；先只加入当前Task场景，再扩充。fixture必须复用withBrowser真实迁移临时SQLite、loopback服务、reader member登录/CSRF及runPython检查，禁止HTML字符串替代。无Playwright则报告验证缺失，不安装或伪造通过。

实施末尾由执行者运行`.venv-workpal/bin/python services/workpal/manage.py test tests.test_hierarchy tests.test_web --noinput`、Node `--test apps/workpal-web/tests/*.test.mjs`与上述浏览器/旧创建QA；父代理负责完整集成回归、根npm和85项保护hash按已确认精确例外核对。记录真实红/绿日志、SQL前后证据、截图；起始即绿不追认红灯。资产白名单及test_web只增加hierarchy路径，不放宽路径/CSP保护。

## Self-review and dependencies

五项风险均已分配真实浏览器场景；所有新增Interface已标新增，children搜索/snapshot限制与现存合同一致。普通composer与child实例隔离是必要扩展，无万能picker、后端变更或新增人审合同。任务依次承接同一Module，单项可独立验收；与B租约/D查询文件互斥。本轮只写本计划，未执行测试/浏览器/保护验证，不声称验收通过。后续依赖只有父代理设计评审、已存在的Registry和本地Playwright环境；**无Runtime依赖**。

## 父代理审查与 Task1 准入 — 2026-11-20

已核对现有Issues详情代际/导航接线与hierarchy动作合同。批准Task1实施，Task2/3仍等前项验收。Task1只读，不展示Change parent/Remove parent/Create subtask；缺少onCreateChild时不做占位入口。Module失败必须保留真实错误状态，不能把父项不可读误报无父项。子项只有status_key时按事实显示，不借父快照猜label。

Task1列明文件之外，允许apps/workpal-web/package.json及同目录README仅增加本专项脚本和真实范围说明；公共服务README留集成，不改browser-fixture/client/旧QA/业务后端。新两QA按core与review分组，先让真实member/真实数据到达缺入口红灯，再实现并完成本Task授权/分页/只读/迟到矩阵。无浏览器预览工具或真实外网调用；使用既有本地Playwright CLI fixture。截图属于验收产物，不修改原型。

## Task1 基础实施复核与独立补齐 — 2026-11-20

基础只读Module及新core/review已落盘，父代理阅读完整代码和两QA，独立core退出0，/tmp/workpal-a54d2-reader-parent-core.log。目前只证明22项20+2分页、空父、筛选重置、断网Retry、文本及尺寸；review只验证当前根撤read清详情，不能代表完整矩阵。Show hierarchy按需加载沿既有读取页方式保留，避免强制新增详情请求。

Task1未验收，下一独立补齐仅扩展新qa.issue-hierarchy.review.mjs，实际缺陷最小修issue-hierarchy.js和Issues薄接线；不改旧QA/backend/browser-fixture/client。四组独立场景：①真实受限子项/归档/跨项目/自定义状态、父子导航与空态且不会显示隐藏总数；②真实独立子要求或父/当前来源撤read与只撤write正向对照，失败不当空态；③hold/release真实响应后切Issue/workspace/logout、filter翻页乱序，不覆盖新context，finally释放；④所有读取前后完整业务表行不变（AuditEvent精确只读追加、Outbox/cache不变），键盘Tab/Enter与导航后的合理焦点，1440/390无溢出。显式Refresh hierarchy应更新当前父关系，不能一直依赖初读issue的parent_issue_id；需用另context真实改父再刷新验证。可复用已验收后端建立fixture，测试写入与被测读操作快照时点分开。Task2/3写界面仍不实施。

父代理已补入真实刷新回归：另一后端调用改父后，Refresh hierarchy仍显示初读parent=0，qa.issue-hierarchy原其余断言不改，新增期望真实新父项失败（/tmp/workpal-a54d2-reader-parent-refresh-red.log，exit1）。最小修复为每次层级加载先重新issue.read当前主体，再按当前parent ID加载，且读后检查代际再继续。后续独立review须保留此新增core断言，不把旧父快照当刷新事实。

刷新修复后新core（含原断言及新父关系断言）和原权限review均退出0，/tmp/workpal-a54d2-reader-parent-refresh-green.log、/tmp/workpal-a54d2-reader-parent-review.log。这只验收该小修复，不替代上文四组完整补齐。

Task1补齐检查点：独立Agent仅新增Show hierarchy的Enter焦点断言，实际红→绿，并最小改为隐藏Show后将焦点转至Refresh hierarchy；父代理静态复核保留。日志/tmp/workpal-a54d2-reader-review-focus-{red,green}.log。原四组尚未交付，不能据此验收。为形成明确增量，剩余拆成R1真实层级/权限/只读事实与R2迟到响应/导航焦点两段；原总体验收合同不减少。

R1仅扩展qa.issue-hierarchy.review.mjs，两个独立命名场景：①22可读+私有/独立要求受限/真实归档子项，当前授权后20+2和归档筛选、跨项目父子导航、空态、不透露隐藏项；②只撤write仍可读、独立子要求撤read过滤、当前来源撤read清详情，读取前后全表不变（仅AuditEvent准确追加，旧行不变），fixture写入与快照分开。可最小修hierarchy Module/Issues薄接线中实际复现缺陷，保留core和原review。R2在R1验收后补hold/release、切Issue/workspace/logout和键盘导航焦点，不占用R1实现范围。

R1已监督验收：父代理读完新增2场景，独立重跑review旧1+新2均PASS，/tmp/workpal-hierarchy-r1-parent.log，exit0。真实private/要求受限/archived、父子导航、只撤write可读、撤read过滤/清空及业务全行与读取审计验证成立；scope检查没有纳入隐藏子项。下一R2仅扩充同review脚本，完成hold/release迟到隔离和键盘导航焦点（真实产品缺陷可最小修Module/薄接线），保留core/R1。新3代际场景可合为一命名组，键盘为另一组，不扩Task2/3。

## R2 迟到结果监督修复 — 2026-11-20

子Agent最初新增三切换草稿未完成。父代理先修测试：等待初始详情渲染再安装拦截，避免把Show出现的前置issue.read截住；每分支独立context；另造不继承已撤权根的导航目标，补member第二workspace成员资格；所有ready有界，hold/route/context在finally释放。这些是fixture问题，不作为产品红灯。

改正后实际复现旧层级403清掉新Issue详情，/tmp/workpal-hierarchy-r2-parent-first.log exit1。根因是客户端全局onAccessLost先于feature代际判断。最小Interface扩展：client.perform可选同步current()->bool，缺省true，局部所有权不序列化；在发请求及响应/JSON解析/错误回报前复查。层级读取把页面/详情+加载代际组合传入，旧上下文响应释放流并报context_changed，不通知新视图；当前403保留原清屏行为。未将此回调当服务端授权或中止已经提交的操作。

新增client.request-context.test.mjs三项真实传输合同测试先红后绿，原23全部保留，App Node26/26退出0，/tmp/workpal-hierarchy-context-node-{red,green}.log。review原3+切Issue/工作区/logout各成功/真实403共9命名PASS，/tmp/workpal-hierarchy-context-browser-green.log exit0。当前撤权清屏正向对照仍通过。

最后R2收尾仅补filter/分页乱序与完整键盘导航两组。允许qa.issue-hierarchy.review.mjs及实际缺陷最小修hierarchy/Issues薄接线；client已冻结，不改动其Interface或旧测试。原9分支全部保留；完成core、Issues/Dependencies各core+review、Node26、web资产与保护核验、1440/390截图后交Task1整体监督验收。


## Task1 监督验收与 Task2a 准入 — 2026-11-20

独立R2补齐filter首屏/下一页双向乱序和真实键盘操作，修复Load more后的焦点与父子导航后的heading焦点；父代理读实现和QA，11场景复跑exit0，/tmp/workpal-hierarchy-r2-parent-final.log，1440/390截图均目视无溢出。随后父代理新增一条真实子任务导航403迟到场景，复现旧详情拒绝清除当前新详情；/tmp/workpal-hierarchy-navigation-denial-red.log退出1。最小修Issues.call支持传递已冻结current回调，issue.read及project.read绑定当前详情代际，client未再改。12命名场景全部转绿，/tmp/workpal-hierarchy-navigation-denial-green.log；Issues review独立回归、Node26也exit0，/tmp/workpal-hierarchy-navigation-{issues-review,node}.log。Task1功能验收通过；没有把修复后补测冒称实施前红灯。其余根检查与保护按parallel-delivery本批记录。

**Task2a现在冻结并授权实施。** 为避免读取Module被对话框状态撑大，新增独立深Module `features/issue-parent.js`，公开 `createIssueParentEditor({client,issue,current,onError,onChanged})->{open(returnFocus)}`，保存该Issue的baseline、选择、候选搜索/分页、dialog代际、冲突和不可变intent；不导出内部picker/请求状态。issue-hierarchy只按catalog显示Change parent、创建editor并传入回调；Issues只接onChanged真实刷新列表和当前详情，保持已验收导航及current检查。

允许文件：新issue-parent.js、新scripts/qa.issue-parent.mjs；修改issue-hierarchy.js、Issues薄接线、必要styles.css、web.py/test_web.py只增加新资产、apps package/README。原hierarchy两QA、client、browser-fixture、后端业务和其他编辑器不改。新脚本避免将写场景混进已验收只读脚本；后续独立qa.issue-parent.review.mjs归Task2b。

行为沿Task2原合同完整实现：Search parent issues/20项Load more issues、排除自身但不自行判环或write；保存父项及Remove parent显式提交；服务端CAS/循环/权限负责最终判断。Remove parent在同一对话框内明确发起parent_issue_id=0意图，不能静默解除。成功后真实回读最新状态；409保留选择、显式Reload current、再由用户提交；400允许修改；403/404清受限状态；网络未知保持完全相同payload/revision/key并锁输入，关闭重开不抹掉请求意图。所有读取和写请求用现有client current回调隔离页面/详情/dialog代际，关闭不声称取消服务端写入。

本段三组真实浏览器core必须完成：①member跨项目改挂→独立context持久读回→解除，精确SQL验证child revision、父不变、要求/criteria/status/workflow/blocked不变、SourceLink追加及解除保留、业务audit/outbox/cache各一次；②至少25个候选真实搜索/分页、自身排除、取消/Escape保留选择与焦点、恶意长标题纯文本、1440/390；③真实CAS 409显式Reload后人工重提，以及route.fetch服务端写成功后丢响应的原请求重试与精确一次事实。先对缺入口建立真正红灯，再实施并原脚本转绿，不能停在读取/占位。只实现Task2a，不创建子任务；完整权限、循环、关闭在途和乱序矩阵另由Task2b独立验收，不宣称Task2整体完成。

显式回归：新parent core，hierarchy core+12场景review，Issues core+review，App Node26，tests.test_hierarchy与test_web，迁移check/system check及85精确保护。保存/tmp/workpal-parent-editor-core-*.log与outputs/workpal-web/a54d2-parent-{desktop,mobile}.png，截图目视；根npm和全量留父代理。无Git写、安装或真实外部调用。


### Task2a 草稿监督检查与可验收续作

首轮仅写入issue-parent.js、hierarchy/Issues接线和静态资产，未建立实施前红灯、无真实浏览器写流程；不验收、不把语法检查当闭环。父代理静态复核修正两处小接线：onChanged先等待列表刷新且核对详情代际，再读当前Issue；父候选search将自己的请求代际传给client current，避免旧搜索403先触发全局清屏。这两项不冒称新行为红绿；Node26和test_web2通过，日志/tmp/workpal-parent-draft-{node,web}.log；真实写入仍未验证。

下一Task2a1只完成原三组中的第一组纵向闭环：新qa.issue-parent.mjs，真实member跨项目改挂→第二context读取→解除，以及精确关系/版本/来源/审计持久化断言。允许在原Task2a文件范围完成草稿所需修复、package/README与1440/390截图；不扩Task2a2候选完整矩阵、Task2a3故障矩阵或Task3创建子任务。原三组总要求不删减，完整Task2a仍要后续两组。现已有UI入口，不能移除入口造红灯；实际失败先保存，现有正确行为首绿如实记录。父代理当前没有确认的外部阻塞，续作必须交付可运行真实流程，不再以仅阅读/语法/占位结束。


### Task2a1 监督验收与 Task2a2 准入 — 2026-11-20

新core真实复现初次dialog当前父事实为空并修复loadFact，Sol最终两次core绿。父代理阅读全部Module与QA，独立重跑改挂→第二context读回→解除→原context刷新，/tmp/workpal-parent-vertical-parent.log退出0。SQL中child两次revision、父及其余业务事实不变，SourceLink只追加一次且解除保留，Audit/Outbox/cache两次写、回读不增写均通过。父代理目视390图，无横溢出。根npm退出0，/tmp/workpal-abc-next-parent-npm.log；85保护零意外差异。Task2a1验收通过，不替代剩余两组。

Task2a2现在仅准入候选和键盘组，新增scripts/qa.issue-parent.review.mjs，允许发现真实问题最小修issue-parent.js、必要styles.css及层级薄接线，apps package/README登记。原qa.issue-parent核心、hierarchy两QA、client/browser-fixture/后端均冻结。本轮真实25个以上同workspace跨项目候选，完整20+后页、排除自身但不假定页满20（过滤后按服务端cursor继续）；搜索按文本、query变化归零、无重复、Load more在末页隐藏，读失败不是空态。用真实route.fetch响应hold/release覆盖旧搜索和旧下一页对新query的隔离，finally有界释放，不合成业务响应。

键盘Tab/Enter/Escape/Cancel、焦点回Change parent，close/reopen保留已选目标和query，选择后不提交则所有业务表不变（只读审计精确区分）；长恶意标题纯文本、1440/390无横溢出并截图目视。本组不发业务写，用旧core验证写路径保持；当前写权限最终裁决由后续Task2b验证，不以候选可见代表可写。冲突/丢响应Task2a3仍后续，创建子任务未开始。日志/tmp/workpal-parent-candidates-*.log；运行新review+原parent core、hierarchy core+review12、Node26、tests.test_web、85保护；未修改后端模型无需重复迁移制造工作量。

### Task2a2 监督验收与 Task2a3 准入 — 2026-11-20

父代理读完候选QA与Module并独立重跑两个命名组，/tmp/workpal-parent-candidates-parent-review.log exit0；Node26独立复跑/tmp/workpal-parent-candidates-parent-node.log exit0；390截图目视，无溢出且恶意标题为文本。候选分页、真实旧搜索/下一页响应隔离、键盘翻页焦点、取消草稿及全表只读断言通过。子Agent焦点红灯文件路径报告不一致，本次仅采信实际可重跑绿灯与代码，不补认准确红灯文件。Task2a2功能验收通过，Task2整体未完成。

Task2a3现冻结：新增scripts/qa.issue-parent.recovery.mjs，允许实际缺陷最小修features/issue-parent.js，apps package/README仅登记此QA。原parent core/review、hierarchy QA、client、browser-fixture、Issues和业务后端不改；需要超出范围先把具体缺陷交监督。仅两组闭环，分别覆盖改挂与解除，不扩创建子任务：

1. 真实独立操作改变child revision，再提交导致409。保留选择、禁用原Save、显式Reload current真实读取，任何回读不能自动写。目标尚未达成时用户可重新Save并验证新revision；目标已由另一操作者达成时展示当前事实并提供Refresh issue结束编辑，不能再次调用set_parent增写。精确检查两类路径的payload/revision/key、父关系/要求/history/SourceLink及audit/outbox/cache，测试fixture写与UI写分开计数。
2. route.fetch使真实服务端写入完成后丢弃响应，UI显示未知结果，冻结原payload/revision/key并锁定输入；点击Retry原封不动重放，业务事实仅一次。未知状态关闭重开仍保留意图；持有旧dialog真实响应再重开，旧结果不关闭或覆盖新dialog，finally有界释放全部route/hold/context。另一操作者之后改变关系时，原key重放成功后必须重新issue.read显示最新事实，不把幂等缓存当当前父关系。用SQL完整业务行对照与精确增量证明无额外写，包含独立context读回。

每组独立fixture、正向可写对照，真实产品失败先记录再修；现有行为首绿不倒造红灯。运行新recovery、原parent core+review、hierarchy core+review、Node26、tests.test_web与85精确保护，日志/tmp/workpal-parent-recovery-*.log；无需新后端迁移。完整权限/循环/跨workspace矩阵仍属Task2b后续，Task3未准入。
