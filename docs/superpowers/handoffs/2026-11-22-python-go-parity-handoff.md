# Python 一比一复刻 Multica Go 后端：交接

日期：2026-11-22。工作区：`/Users/patrick/Desktop/Workspace/ai-native/workpal`。分支：`feat/python-fastapi-backend`。交接时 HEAD：`1bf9b525`，存在尚未提交的工作，不能只检出 HEAD 后假定接收了全部成果。

## 用户目标和当前结论

用户要求：**用 Python 一比一还原 Multica 的 Go 后端实现**。以仓库 `server/go/` 为行为基准，包括接口、中间件、认证授权、请求解析、数据库约束和事务、错误分支、文件、事件、后台任务及后续可访问性。不是翻译 Node mock，不是只满足前端页面，也不是接口存在就算完成。

**目标尚未完成。最近一轮没有完成新的 Python 业务模块复刻，主要完成了参考基线修复、入口绑定和验证工具。** Python 已有代码不能据此视为 Go 等价实现。完整契约门槛仍退出 1。没有可支持“全部复刻”“可以切换”“只剩备份”的证据。

此前执行的错误：把大量审计、文档和 Go 自身测试作为阶段交付后停止，没有持续完成用户授权的 Python 实现；还容易让 Go 测试通过被误解为 Go/Python 差分通过。接手者应纠正这个执行方向，不能重复要求用户解释目标或重新批准已经批准的工作。

用户最后要求本轮写交接文档；本轮只整理交接，不继续修改业务实现。

## 授权与不能越过的边界

- 用户已批准修订后的设计和实施计划，并要求自行继续实施。此前“审核后才实施”的暂停已经解除。
- 用户另行明确批准：仅在独立参考副本修复 3 文件的 6 处标准库方法名，并记录派生基线。仓库 Go 原件必须保留；未授权任意修改 Go 来迁就 Python。
- 对未批准的行为差异不能自行宣布等价。可靠性增强也可能改变 Go 的失败语义。
- 真实 SQLite、上传字节、归档笔记和现有服务必须保留；完整等价及切换门槛前不得删除 Node mock 或执行最终停写迁移。
- 不调用真实模型或生产集成，不执行用户输入的技能安装命令。应使用隔离依赖验证对应协议，不能把这些限制当成永久 501 即完成的理由。
- 保留 Workpal 品牌、英文 UI、现有视觉与键盘/窄屏访问。遵守仓库 AGENTS.md。
- 不读取或输出密钥到交接/聊天。早期 AUTH_SECRET 输入阻塞记录不是现在可以停止全部实现的依据；配置状态需安全核实，不能擅自覆盖已有凭据。

## 首先读取的文档与代码

- [批准设计](../specs/2026-11-22-go-parity-design.md)
- [批准实施计划及后续执行记录](../plans/2026-11-22-go-parity-plan.md)
- [源码审计](../evidence/2026-11-22-go-parity-source-audit.md)
- [原始输入摘要](../evidence/2026-11-22-go-source-sha256.json)
- [派生基线](../evidence/2026-11-22-go-derived-baseline.json)
- 本地进度账本：`.superpowers/sdd/2026-11-22-go-parity-plan/progress.md`
- Python 实现：`server/src/workpal_backend/`；测试：`server/tests/`；迁移：`server/migrations/`。
- 契约账本：`server/contracts/routes.json`；检查器：`server/tools/check_contracts.py`。

文档中仍有历史时态未统一：设计正文的“待批准/尚未构建”、计划“审核交付”下的“未开始/没有授权”，以及旧编译阻塞段的“未应用/等待批准”，均已被文件顶部批准状态、后续执行记录及本交接中的用户授权覆盖。不要按这些旧段落再次停下来请求同一授权。整份计划尚未完成这一点仍成立。

## 实际完成了什么

| 工作 | 已有结果 | 不代表什么 |
| --- | --- | --- |
| 保护输入基线 | 覆盖 Go、SQL、嵌入资源、依赖及相关配置/构建输入，校验新增/删除/内容/profile | 不证明业务等价 |
| handler 绑定 | Go/types 得到 574 个注册位置，匹配现有账本 584 个 Go 路由；包括插件双挂载、factory、closure | 不证明账本穷尽全部动态入口、中间件或行为分支 |
| 验收门槛 | 增加类型绑定、产物摘要和执行证据校验；拒绝空证据和 TestMain 未执行测试却退出 0 | 不能用工具测试数量代替业务实现 |
| 观察比较工具 | 状态、头、body、事件、状态变化、外部调用比较；仅允许显式 ID/时间归一化 | 尚未完成逐接口双端执行 harness 和业务差分 |
| Go 参考修复 | 仅副本恢复标准库原方法名；原件未改 | 未授权修改其他 Go 行为 |
| Go 运行验证 | cmd/server 测试二进制编译；选定健康/实时指标测试及子测试 25 项通过，0 skip/fail | **这是 Go 自测，不是 Python 等价测试** |
| 原有 Python 兼容工作 | 图片上传、配置加载、本地数据导入和 QA 等已存在 | 不等于 Go 附件、认证或全后端复刻完成 |

账本的旧 implemented/pending 标签不是完成率。最近一次完整检查仍因前端来源覆盖、非 HTTP producer 覆盖、未执行的契约证据等失败；不要修改标签或放宽门槛以制造通过。

## 已知具体差异及待核验风险

1. Python 图片上传在 `server/src/workpal_backend/files/routes.py`，此前实现为 5 MiB、仅图片。Go 通用附件上传支持 100 MiB 和关联等行为；不能把现有图片接口算成附件复刻完成。
2. Go `server/go/internal/handler/file.go` 的上传流程在部分元数据写入失败时仍返回 200、空 id 和可用链接。需复刻该分支的响应、字节保留、后续可访问性；改成失败或自动回收属于需批准差异。
3. Go readiness 检查 DB/migrations；现有 Python readiness 包含 Redis，Redis 不可用时的结果可能不同。live 时间格式也需对照 Go UTC RFC3339 秒精度。不能仅改测试期望掩盖差异。
4. Go/PostgreSQL 与 Python/SQLite 的约束、锁、数组/JSON、排序、搜索、事务和 job claim 等尚未逐项证明等价。无法等价的项应提交具体存储方案，不得用通用 JSON CRUD 绕过。
5. 完整认证、权限边界、业务服务、后台 producer/consumer、WS、文件生命周期和各类外部协议仍须逐模块实施及验证。不能因前端不调用就遗漏。
6. 早期上传测试曾在默认上传目录留下孤立测试图片字节，未写真实数据库记录；已在此前切换记录说明，未擅自删除。后续清理先辨认来源和引用，勿批量删除真实上传目录。

## Go 派生参考环境

参考根目录：`.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1/`，Go 模块在其 `server/go/` 下。

获批补丁：[2026-11-22-go-baseline-build-fix.patch](../evidence/2026-11-22-go-baseline-build-fix.patch)。涉及 `pkg/remotemcp/client.go`、`internal/integrations/wecom/media_guard.go`、`internal/handler/file.go`，只恢复 IsMulticast、IsLinkLocalMulticast、IsInterfaceLocalMulticast 原名。补丁和逐文件摘要已记录。

固定 profile：Go 1.26.9，GOOS=linux，GOARCH=amd64，CGO_ENABLED=0，GOWORK=off，GOFLAGS 空，tags=[]，默认 !oss（含 EE），module_mode=readonly。不能改用 oss 减少范围。

宿主没有直接安装 Go；使用 Docker。原生 linux/arm64 编译器交叉编译目标 amd64。amd64 仿真工具曾出现退出 137、TLS x509 SIGSEGV、test2json int32 overflow；不能把这些算作通过。最终直接执行 amd64 测试二进制成功，再由原生工具转换原始输出。

- 测试二进制：`.superpowers/sdd/2026-11-22-go-parity-plan/go-binaries/server.test`。
- 原生 `golang:1.26.9` 本地 tag 为 arm64；amd64 镜像 ID：`sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0`。
- 缓存卷：`workpal-go-parity-modcache`、`workpal-go-parity-buildcache`，保留供后续使用。
- 测试 PostgreSQL 曾用 postgres:17-alpine、tmpfs、内部网络、无发布端口，迁移到 682；测试后已删除 `workpal-go-parity-postgres` 和 `workpal-go-parity-net`。重新跑需重建隔离环境。
- Go TestMain 在某些数据库不可用情况下会直接 exit 0 且不执行测试。必须验证实际 run/pass、无 skip、包级通过，不能只看退出码。

证据：[验证摘要](../evidence/2026-11-22-go-derived-validation.json)、[原始测试事件](../evidence/2026-11-22-go-derived-health-tests.jsonl)、[类型注册审计](../evidence/2026-11-22-go-typed-registration-audit.json)、[审计工具源码](../evidence/2026-11-22-go-typed-registration-audit.go.txt)。本地参考副本和二进制不保证随 Git 迁移；另一台机器需依据受保护原件、获批补丁和 profile 重建。

## 验证结果的准确含义

最近实施轮已记录 `npm run check` 通过：765 Python tests、30 subtests，以及 Node/launcher 检查和前端构建。它验证现有项目回归，**并非全量 Go/Python 等价验收**。本次只写交接，未重跑应用测试。

完整门槛命令（当前预期仍失败，接手后读取具体失败）：

```sh
server/.venv/bin/python server/tools/check_contracts.py --require-complete --build-profile docs/superpowers/evidence/2026-11-22-go-build-profile.json
npm run check
```

关键新测试：`server/tests/test_go_parity_baseline.py`、`test_contract_inventory.py`、`test_go_execution_evidence.py`、`test_typed_handler_evidence.py`，以及 `server/tests/parity/` 下的 normalization 和 go_results 测试。

## Git 与数据交接

已提交检查点：

- `3f59fd11`：保护基线和 handler 证据门槛。
- `6e21ae2e`：批准设计/计划及输入基线。
- `e47d49d3`：此前本地兼容工作，明确不是 Go 等价完成。
- `1bf9b525`：执行证据门槛及 Go 编译阻塞记录。

交接前未提交的本任务改动：`server/contracts/routes.json`、`server/tools/check_contracts.py`、`server/tests/test_contract_inventory.py`、`server/tests/test_typed_handler_evidence.py`、`server/tests/parity/go_results.py` 及测试；计划与编译阻塞 JSON；新增派生基线、类型审计及 Go 测试证据；本交接文档。接手必须先看 `git status` 和 diff，保留它们。

工作区还存在用户/历史未跟踪目录：`outputs/`、`assets/workpal-prototype/outputs/`、`assets/workpal-prototype/assets/archives/`、`assets/workpal-prototype/docs/review-assets/`。不要清理、重置或使用 `git add .` 混入提交。

真实数据在 `server/data/`，之前 Python 配置指向 `server/data/python/workpal.sqlite`。现有配置可能在被忽略的根 `.env` 中；仅安全使用，不把内容写入文档。真实服务未在此轮停止或切换，Node mock 未删除；本交接没有重新探测进程，不声称具体 PID/端口当前健康。

## 接手后的实际执行要求

1. 阅读批准设计/计划、检查现有 diff、验证原始和派生基线，复用已有参考环境与检查器；不要重新从零做同一轮审计。
2. 完成可重复的 Go/Python 双端隔离执行，按相同输入比较响应、数据库变化、事件和外部调用。保留原始观察，不能过度归一化隐藏差异。
3. 按批准计划直接推进 Python 业务实现。每个模块从 Go 入口追踪到服务、SQL 和失败分支，先用对照用例暴露现有差异，再实现并验证；产出应是 Python 代码和对应差分证据。
4. 同步补齐非 HTTP 入口及完整分支清单，但不要让文档/索引工作代替业务实现，也不要把有限测试当成整个模块完成。
5. 尚未支持的功能保持诚实状态，不虚构输出；未批准差异保持阻断。阶段汇报说明具体实现了什么、对照了哪些行为、还缺什么。
6. 全量等价、回归和隔离切换演练通过后，才按计划进行真实停写、备份、最终对账、切换和 Node 退役。现在远未到这个阶段。

交接完成不表示复刻完成。下一位执行者的交付目标仍是完整 Python 后端，不是再交一份准备工作报告。
