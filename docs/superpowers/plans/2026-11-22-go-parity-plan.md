# Multica Go 逐项等价复刻实施计划（已批准，实施中）

> **For agentic workers:** 用户已在三项审阅修订后回复“可以了，你自己来做”，批准实施。使用 executing-plans 逐项执行，未批准的行为差异仍须停下提交审核。

**Goal:** 按固定 Go 源码实现 Python 后端，每个入口及其权限、数据、事务、事件和错误均有验收证据；仅数据库并发和快照语义适用用户已批准的 SQLite 差异。

**Architecture:** Python/FastAPI 按 Go 领域模块实现，复用经核验的基础设施；SQLite/Redis 适配必须逐项验证 Go 可观测语义；SQLite 并发/快照按[已批准方案 B](2026-11-22-python-database-parity-decision.md)记录差异，其余要求不变。外部调用使用隔离测试依赖，真实模型和生产服务不调用。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、Alembic、SQLite、Redis、pytest、Playwright；Go 与隔离 PostgreSQL 用于基准/差分验证。数据库语义无法等价时先提交方案审核，不擅自改变范围。

**Spec:** [逐项等价设计](../specs/2026-11-22-go-parity-design.md)

**最新验收调整：** 用户要求“功能尽量对齐，要做好并发锁，性能上可以稍微妥协”。保留 Python + SQLite；功能差异逐项披露，未实现项不伪装完成。并发正确性、事务原子性和数据完整性不豁免；适度性能让步须有同条件实测，不能虚构统一容差。数据库并发/快照差异按已批准方案 B 单列。

## 全局约束

- 当前已批准实施。真实停写、数据切换及 Node 退役仍须满足计划末尾的全部适用验收门槛。
- Go 文件及 SHA256 是行为基线；前端页面和 Node mock 不是 Go 的替代规范。
- 保留用户数据、上传文件、归档和此前未提交改动。实现时只提交本任务明确拥有的文件。
- 未实现不等于范围外；临时 501、空数组、通用 CRUD 不能标记等价。
- 不调用真实模型、生产集成，不执行技能安装命令；协议和状态机通过隔离依赖验证。
- 每项偏离 Go 的决定都须列出并获用户批准，不能仅写进日志就视为批准。

## 重点审查

1. 工作区成员读取私有项目/任务/附件：分别验证列表计数、分页和详情均不泄漏，不能只检查 workspace membership。
2. 会话、PAT、daemon/task token 混用及伪造头：按 Go 每条路由验证身份种类和拒绝语义。
3. 写入后事件失败或 worker 崩溃：验证事务、幂等、顺序、重试和重连，不把发布成功等同于用户收到。
4. PostgreSQL 锁、搜索、JSON/null 和 SQLite 差异：用相同输入、并发调度及边界验证；已批准的并发/快照差异保留双端证据，搜索、JSON/null、约束及业务正确性仍须对齐。
5. 附件写入/关联/删除中断和私有权限变化：验证字节、元数据、引用、下载和回收一致性。

## 任务 0：用户批准与工作区基线

**Files:** 本设计/计划、`docs/superpowers/evidence/2026-11-22-go-source-sha256.json`、现有工作区差异清单。

- [x] 用户明确批准设计、范围和实施计划；后续明确选择保留 SQLite，允许数据库并发和快照差异。批准边界见数据库方案及 `server/contracts/database-exceptions.json`，其他差异不自动豁免。
- [ ] 校验完整受保护输入集合、摘要、固定 build profile 和 Git 基线，记录已有未提交代码；不把它们当作本次新实现或等价证据。
- [ ] 确认隔离实现/验证工作区，真实服务和数据库保持原状。

## 任务 1：重建可验证的完整契约账本

**Files:** `server/contracts/{routes,go-registrations,frontend-calls,frontend-call-sites,backend-events,event-producer-sites}.json`、`server/contracts/schema-map.md`、`server/contracts/batches/`、`server/tools/check_contracts.py`、`server/tests/test_contract_inventory.py`（按现有测试位置合并）。

**Interfaces:** 每条以 method+规范 path 为稳定键；非 HTTP 以 producer/job+Go 函数为键。字段按设计第 6 节；摘要变化自动使证据失效。

- [ ] 从 router 的嵌套 group、With/Use、委托注册及 main 后台注册重新提取，不只扫描顶层路由字符串。
- [ ] 交叉核对现有逐路由附录；新增、删除、重名和条件注册逐条解释。所有 Go 服务入口均有来源；前端未知调用另列。
- [ ] 逐条追踪 handler→service→query→DDL→事件；记录成功及每个错误分支、身份矩阵、依赖和源码测试。
- [ ] 审计现有 batch 证据和 Python 实现；只有来源和运行证据完整才能更新状态，不能照抄旧标签。
- [ ] 先给检查器增加失败用例：受保护非 Go/SQL 文件或依赖锁变化、文件新增/删除、构建标签/环境漂移、把 !oss 与 oss 混用、同名不同 receiver 或测试替身误认入口、漏路由、缺中间件、遗漏非 HTTP producer、空夹具、陈旧摘要、未执行测试、无批准的排除项必须阻断。观察失败，再实现检查，验证通过。
- [ ] 运行 `server/.venv/bin/python server/tools/check_contracts.py --require-complete --build-profile docs/superpowers/evidence/2026-11-22-go-build-profile.json`。本阶段仍有待实现条目时应失败；不能为通过检查而删项。

## 任务 2：基准和差分验证框架

**Files:** 新建 `server/tests/parity/{conftest,normalization}.py`、`server/tests/parity/cases/`、`server/tools/run_go_parity.py`、`docs/verification/go-parity.md`。

**Interfaces:** 同一 case 输入 Go 与 Python，输出 HTTP 状态/头/body、规范化数据库结果、事件、外部依赖调用记录；归一化仅限审批过的随机 ID/时钟表示。

- [ ] 给 runner 写自测：字段缺失、null/空数组、401/403差异、漏事件和多余外部调用均失败；先红后绿。
- [ ] 按 Go 构建要求建立隔离 PostgreSQL/Redis/字节存储和离线外部依赖，不改共享容器或真实数据。
- [ ] 针对无法运行的 Go 分支保存原因及阻塞状态；不得用源码摘录假装执行通过。
- [ ] 记录 Go/Python 版本、源码摘要、夹具、命令、退出码、结果和产物路径。

## 任务 3：配置、生命周期、持久化及认证权限基础

**Files:** `server/src/workpal_backend/{config,app,cli}.py`、`infrastructure/`、`auth/`、`workspaces/`、`server/migrations/`、对应 `server/tests/` 与 parity cases；`scripts/python-web-dev.mjs`、`.env.example` 相关配置文档。

**Interfaces:** 保留 Go 配置名与优先级；principal 包含 Go 对应身份与作用域；业务 service 不信任客户端伪造身份头；事务和授权接口供后续模块使用。

- [ ] 对 main/router/auth/middleware 逐项派生环境、启动失败、JWT/PAT/task、Cookie/CSRF、权限撤销和工作区角色测试，先红后绿。
- [ ] 对 Go 数据约束、锁/重试和时间精度建立 SQLite 测试。并发/快照按已批准方案 B 显式分类并验证 SQLite 原子性、回滚和安全性；其他无法等价的条目仍作为阻塞提交用户。
- [ ] 配置使用上游 `.env` 首次初始化并复用，旧 Python 名称若保留只作明确兼容别名；不默默重置密钥。
- [ ] 验证认证全部协议；固定开发账户模式仅作为单独适配，不代替其他协议验收。

## 任务 4：按完整路由批次复刻业务

**Files:** `server/contracts/batches/<batch>.json`；`server/src/workpal_backend/<feature>/{routes,schemas,service,repository}.py`；`server/tests/parity/test_<feature>.py`；所需迁移和现有业务回归测试。候选 Go 入口及本轮修正见源码附录；附录不是全量语义解析结果，开工前必须按注册 receiver 的包/类型和固定构建 profile 解析精确入口；现有详细端点清单 `2026-11-21-python-route-batches.md` 仅作未验收索引。

**Interfaces:** 入口、业务返回、权限及事件逐条来自账本，不由通用 CRUD 接口反向决定。每个批次开工前列清实际文件和依赖，禁止只创建空模块。

每个批次必须执行以下完整循环，不能批量勾选：

- [ ] 阅读本批全部 Go handler/service/query/tests，补齐任务 1 契约分支和具体文件清单。
- [ ] 先写 Go 派生的成功、非法输入、权限、私有资源、分页/null、事务/重启和事件测试，运行证明现有 Python 差异。
- [ ] 实现该行为及相应查询/约束/事件；替换现有不等价适配，不通过削弱测试维持旧实现。
- [ ] 运行该批差分/契约和相关产品测试；失败修复到通过，未执行项仍阻塞。
- [ ] 保存逐入口证据，审查剩余差异，更新账本并窄范围提交。没有批准的差异不能算完成。

依赖顺序：工作区/成员及私有资源 → 项目/工作流/任务/评论/标签/关系 → agents/runtimes/skills/squads → chat/session/history → files → search/inbox/notifications/preferences → dashboard/其他业务 → plugins/apps/channels/外部协议。任何路由的服务端配置、回调、webhook、只读历史及权限都不能仅因“生产集成不调用”被跳过。

## 任务 5：附件完整行为（明确阻塞项）

**Files:** Go `internal/handler/file.go` 及其 tests 对应 Python `files/`、相关业务关联及 `server/tests/parity/test_files.py`。

- [ ] 复刻 100 MiB 边界、缺文件/坏表单、类型检测/扩展名、个人和工作区上传以及 Go 附件响应。
- [ ] 复刻 issue/comment/chat/task 关联、task token 限制、软删对象和私有项目可见性；关联写入和事件一致。
- [ ] 复刻下载、内容预览、删除、能力链接及 Go 实际支持的 range/缓存行为。
- [ ] 对 staging→ready、进程崩溃、重复回收和权限撤销写先失败后通过测试；内部可靠性机制不得改变 Go 的失败语义。
- [ ] 对 Go file.go:616–651 普通元数据失败注入错误：断言 HTTP 200、空 id、原链接/文件名、无成功附件事件、不删除上传字节；重启后核对字节及实际链接访问。S3/CDN 和 LocalStorage 分别建夹具，本地 /uploads GET/HEAD 保持 Go 的 404，不宣称所有链接必可用。
- [ ] 分别测试评论锁 ErrNoRows 的删除调用与 403，以及取消分支的响应和字节保留；不能把可能提交的取消写入自动回收。
- [ ] 若拟改变上述响应、字节保留、访问或回收策略，先提交逐项待批准差异；未批准不得实现或记为等价。
- [ ] 当前新增 5 MiB 图片兼容实现须被核验/扩展，不能以头像浏览器通过替代以上任务。

## 任务 6：非 HTTP 行为、WS 和后台协议

**Files:** `realtime/`、`worker.py`、`infrastructure/outbox.py`、每个业务 producer、Go scheduler/main 注册对应测试及 `server/contracts/event-producer-sites.json`。

- [ ] 所有任务/producer 分别核对触发条件、授权范围、payload、顺序、保留期、重试和去重；定义“不发事件”的来源证据。
- [ ] 随业务事务实现生产者，逐个验证 commit/rollback、Redis 故障恢复、重复和 stale-worker fencing。
- [ ] 验证 WS 身份、租户/私有范围、撤权、过期、重连、慢客户端及实际用户可见更新。
- [ ] 任务状态机和外部执行边界使用离线替身验证；不运行模型、不伪造产品执行记录。

## 任务 7：产品扩展与旧数据兼容

**Files:** `legacy_import.py`、`legacy_audit.py`、`workspace_content/`、前端调用模块、`scripts/*-qa.mjs`、`tests/python-web/`。

- [ ] 把 Go 标准业务和本地扩展区分标注；迁移现有记录到规范关系时保留 ID 映射、原始内容和用户后续编辑。
- [ ] 补齐转换、幂等、删除/冲突拒绝、失败回滚和逐行对账测试；不在真实库上试验。
- [ ] 保留已迁移的头像/统计/贡献/导航回归，并补 Go 完整行为对应 UI 验证。
- [ ] 前端不得用固定数据掩盖后台缺失；源码中的安装命令始终视为文本。

## 任务 8：全量等价验收（禁止跳过）

- [ ] 逐入口及非 HTTP 账本无未核对、待实现、待验证；全部批准差异单独列出，未批准差异为零。
- [ ] 完成检查器和受保护源码摘要检查通过；检查器本身不得接受空证据。
- [ ] `server/.venv/bin/python server/tools/check_contracts.py --require-complete --build-profile docs/superpowers/evidence/2026-11-22-go-build-profile.json`、全量 Python/差分、`npm run check` 通过；跳过和环境故障不算通过。
- [ ] Playwright 验证各业务关键路径、权限、写入、刷新/重启、错误恢复、键盘/窄屏；局部 smoke 不替代契约验收。
- [ ] 在隔离环境分别通过真实 `npm run dev` 与 `npm start` 的登录、上传/下载、WS、重启、Redis 不可用、端口冲突、SIGINT/SIGTERM 及子进程清理。
- [ ] 交付逐项差异和证据，依本轮获批准的方案进入切换；若出现未批准的差异则停下提交审核。此门槛之前禁止以“还差备份”描述状态。

## 任务 9：仅在批准的计划通过等价验收后退役

**Files:** 另行更新 cutover 计划、备份/审计报告、Node 消费者清单及文档；此时才允许删除源文件。

- [ ] 保存经验证的 Python 兼容提交、构建、配置和 schema；隔离演练新增记录后同库回退与继续写入。
- [ ] 确认进程归属和自动重启设置，停止所有源/目标写入者；一致备份 SQLite/上传字节，绑定时间、摘要、提交及 schema。
- [ ] 冻结后逐行对账；摘要变化、缺行、无法解释的编辑使放行失效，禁止自动覆盖/重导入。
- [ ] 仅恢复 Python，封存旧库；保留数据和回归测试，移除旧 Node 运行时与失效消费者。
- [ ] 删除后再次执行任务 8 的完整验收及真实数据只读核对。最终报告明确批准差异及回退方式。

## 审核交付

用户审核本文件和设计后再开始任务 0。当前没有开始上述任务，也没有因为本计划存在而获得实施授权。旧切换计划的未勾选项不能绕过本计划的 Go 等价门槛。

## 执行记录（2026-11-22）

已开始任务 1；整份计划未完成。保持当前 feature 分支和真实服务，测试使用隔离状态。先前配置/图片兼容/QA 改动保存为独立 checkpoint e47d49d3，不能记为 Go 等价。新门槛及绑定修正为 3f59fd11，批准文档和完整输入基线为 6e21ae2e。

基线和绑定测试先红后绿，81 项及 30 subtests 通过；全量 npm run check 退出 0（713 Python tests + 30 subtests，Node 9，launcher 16，frontend build）。完整契约门槛仍失败，不能切换或删除 Node。

Go 1.26.9 工具链已取得；linux/amd64 镜像在宿主仿真下曾退出 137，重试发生 TLS 证书解析 SIGSEGV。改用原生 linux/arm64 编译工具进程并显式保持目标 GOOS=linux / GOARCH=amd64，不改变基准目标。目标依赖图解析通过，默认 EE 包已确认，证据见 go-build-selection.json。尚无 Go 业务差分测试通过的声明。

### Go 基线编译阻塞（原记录；已批准参考副本修复，见下）

实际 Go 类型审计失败于 `server/go/pkg/remotemcp/client.go:91`：`netip.Addr.IsLinkLocalWorkpalst` / `IsWorkpalst` 不存在。检查还发现 `internal/integrations/wecom/media_guard.go` 与 `internal/handler/file.go` 有同类品牌替换。原始受保护文件未修改。

已准备 `../evidence/2026-11-22-go-baseline-build-fix.patch`，仅将 3 文件中的 6 处调用恢复为标准库 `IsLinkLocalMulticast`、`IsInterfaceLocalMulticast`、`IsMulticast`。补丁只做了适用性检查，未应用；也没有声称修复后可完整编译。等待用户批准在独立参考副本应用并记录派生基线，不擅自更改已批准的 Go 源码基准。该阻塞不抹去已完成的检查器工作，也不能作为跳过 Go 验证的理由。

### 已批准派生基线执行记录

用户随后明确允许修复参考副本并记录派生基线。补丁已应用到 `.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1`，原始 Go 不变，逐文件验证只有获批 3 文件/6 调用不同。完整派生文件摘要、原始/候选摘要与补丁摘要见 `../evidence/2026-11-22-go-derived-baseline.json`。

Go/types 审计退出 0，产物及可复现审计工具文本见 `go-typed-registration-audit.json` 与 `.go.txt`。所有现有 Go 路由账本条目都有类型解析支持的 handler 绑定，包括两组公共插件 API 前缀、health factory 和 WS closure；这证明入口声明绑定，不代表继承中间件、完整输入分支、SQL 和副作用已经等价。完成检查仍保留阻断。

Go 测试结果判定器已补充 TestMain 以 0 退出却未执行任何测试、skip、未完成及包级失败的拒绝测试。仅进程 exit 0 不构成测试通过。

参考副本验证继续完成：保持 Go 1.26.9、linux/amd64、CGO=0、默认 !oss 构建目标，cmd/server 测试二进制编译成功；独立 PostgreSQL tmpfs 数据库运行 Go 迁移至 682。实际执行健康检查及实时指标选定测试，25 个测试/子测试通过、0 跳过、0 失败。原生 arm64 工具仅负责交叉编译和输出解析，实际运行的测试二进制为 amd64；仿真 Go 工具的 int32 overflow 单独记录。原始事件和验证摘要见 `../evidence/2026-11-22-go-derived-validation.json`。这不是 Python 差分通过，整体任务 1/2 仍在进行。

本轮 npm run check 通过（765 Python tests、30 subtests，Node/launcher 检查和前端构建通过）。再次核验原始受保护输入和派生全文件摘要，原件未变，参考副本仅获批 3 文件不同。没有停止现有服务、迁移真实数据库或删除 Node。
