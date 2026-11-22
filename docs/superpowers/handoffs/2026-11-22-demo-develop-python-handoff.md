# 演示交付与 Python 后端交接

日期：2026-11-22。本文件在 develop 合并并推送后编写。

## 当前交付状态

- 用户最新指令是暂停 Python 开发，优先保护演示，提交推送全部变更、合并 develop，然后交接。原完整复刻目标已暂停，未完成。
- 全部非忽略工作文件已提交：`afc30ac787ac14525ca7241c9bc558f1cdd588af`，已推送 `feat/python-fastapi-backend`。
- 合并提交：`0f1c5a954375bdfe9281e5d0313cdffad4057c1b`，已推送 `origin/develop`。此前远端没有 develop；合并保留本地旧 develop 的历史与文件。
- 合并在 `/tmp/workpal-demo-integrate-20261122` 独立副本完成，避免把正在运行的目录切到旧版 develop。活动 apps/web、packages、server 和启动脚本与 checkpoint 一致。冲突保留当前根 package.json，修正 README，合并忽略规则；旧 backend-storage 保留在原型 src，历史归档原件也保留。旧 apps/workpal-web、services/workpal、backend 为历史实现，不是当前服务入口；锁文件仅增加旧工作区空 importer。
- 未提交真实数据库、上传数据、.env、虚拟环境、依赖或忽略的 .superpowers 派生环境。公开的 disposable RSA 测试私钥有配套 README，是测试 fixture。归档构建文件的既有空白警告未批量重写。

## 演示入口和已验证范围

当前 `4174` 是 Vite 前端，API 代理连接 Python。`npm run dev`、`dev:web`、`start` 默认均为 Python；不是 Node mock。此前 README 的默认 mock 说明已经修正。

本轮没有停止或重启现有 Vite PID 39416，没有更改真实 SQLite、现有配置或上传记录。浏览器实测 `4174/#/home` → Enter Workspace → `#/review/issues` 能加载首页、任务列表和项目导航；这是基础浏览验证，不能推导全部业务操作可用。

独立 Node mock 使用当前前端构建，在 24284 + 内存数据库验证：首页、进入工作区、任务列表、TAP-029 详情及已有评论、项目列表正常加载。临时 QA 服务和自建浏览器标签已关闭。HTTP 自动测试另覆盖 CRUD、输入验证、重启后持久化、明确拒绝执行。

如需独立 mock 演示（保留当前 4174）：

```sh
npm run build
WORKPAL_DB=/tmp/workpal-demo.sqlite node --input-type=module -e 'import {createServer} from "./server/api.mjs"; createServer().listen(4184, "127.0.0.1")'
```

访问 `http://127.0.0.1:4184/#/home`，点击 Enter Workspace，演示期间保持进程运行。该命令使用独立临时 SQLite，不导入真实数据库。4184 没有在本轮额外常驻启动。

已知演示边界：mock 任务详情 Quick Actions 显示 `Could not load. Retry`；Agent 显示离线。真实模型执行、技能安装、生产集成等不可演示为已实现，不得虚构输出。已验证基础页面不等于所有按钮正常，也不等于完整 Python 验收。

## 本轮验证证据

- 原工作树 `npm run check` 退出 0：Node 9/9，Python 1921 + 30 subtests，启动器 16/16，前端构建通过。日志 `/tmp/workpal-demo-merge-check.log`。
- 合并副本完整检查先通过 Node 9/9、Python 1921 + 30 subtests；两项生产启动器测试因新副本没有 apps/web/dist 失败。脚本把 build 排在启动器测试之后，这个首次运行前提仍需注意。
- 在副本运行 `npm run build` 退出 0 后，`npm run test:launcher` 16/16、退出 0。没有改变业务代码或放宽断言。合并后的各检查组成项均通过；不把第一次失败的整条命令描述为退出 0。日志 `/tmp/workpal-demo-merged-check.log`、`/tmp/workpal-demo-merged-build.log`、`/tmp/workpal-demo-merged-launcher.log`。
- 合并副本 `npm run prototype:check` 退出 0：102/102 测试，离线 HTML 构建成功。日志 `/tmp/workpal-demo-merged-prototype-check.log`。
- `pnpm install --frozen-lockfile --ignore-scripts --offline --lockfile-only` 退出 0，为历史工作区增加空 importer；复用本机依赖，未验证全新机器在线安装。
- 构建仍有大 chunk 提示；Python 有依赖弃用 warning，均非测试失败。
- 完整契约门槛本轮重跑仍退出 1：frontend source coverage、非 HTTP producer 来源/证据、pending routes/缺失执行记录等。日志 `/tmp/workpal-demo-parity-gate.log`。**Go 自测通过不代表 Python 一比一复刻完成。**

## 后端方向与用户决策

后端实现全部使用 Python，Go 仅参考。SQLite 已被明确选择，允许其数据库并发及快照语义差异；最新优先级为“功能尽量对齐，要做好并发锁，性能可以稍微妥协”“不出错是第一步，性能是下一步”。不再要求高并发写吞吐和尾延迟严格等同 PostgreSQL，但不允许丢更新、重复领取、断裂引用等正确性问题。

参见 [数据库决策](../plans/2026-11-22-python-database-parity-decision.md)、[实施计划](../plans/2026-11-22-go-parity-plan.md)、[设计](../specs/2026-11-22-go-parity-design.md)、`server/contracts/database-exceptions.json`。原 [交接](2026-11-22-python-go-parity-handoff.md) 是更早快照，不能把其中“没有新实现”当作当前事实。

## 已有实现与未完成项

Python 实现在 `server/src/workpal_backend`，测试在 `server/tests`，迁移在 `server/migrations`。本 checkpoint 保存了认证、权限、工作区、实时事件、运行时、PAT、技能/聊天/项目搜索、附件及相关原语的大量实现与测试；不是对所有线上路由完成声明。

最近完成的具体切片：

- 附件上传绑定、元数据、签名下载、内容读取、删除、owner 锁控制流、事件，以及 request-scoped AttachmentMutations 组装；上传事件显式传入原始 uploader，删除事件保留请求 member 归属。
- 提取 `infrastructure/wakeup_transactions.py` 处理 actor/handoff 设置、提交及 finally 回滚；AttachmentWriter 使用共享事务。
- `comments/deletion.py` 实现 receipt 阻断、tombstone/leaf 分支、附件和 reaction 删除、祖先清理与 issue touch；有 14 项单测，尚未完成实际 SQL 接入及 Go 完整差分。
- `infrastructure/sqlite_write.py` 与 `Database.begin_write()`：在读取前 BEGIN IMMEDIATE，有限 busy_timeout，BUSY/LOCKED 映射 DatabaseBusy，不自动重放可能带外部副作用的回调；连接级 actor/handoff 设置通过 SQLite UDF 提供给触发器，关闭后清除。
- 新增 5 项真实 SQLite 事务测试覆盖写锁等待/释放、回滚、独立连接抢单一次、触发器归属信息与清理、不支持的 SQL 显式失败。尚未把全部业务写操作接入该事务层。

核心剩余工作：

1. 完成 canonical issue/comment/task/attachment/reaction/membership 的实际 schema、迁移和 SQL queries；若干 query 测试仍使用 fixture 表，不能代替正式迁移。
2. 把服务层接入真实认证、中间件、SQL transaction-bound queries、应用路由、事件和存储生命周期。当前 live 图片上传仍是旧的 5 MiB/图片限定流程；通用附件服务存在不代表路由已切换。canonical relay 也未全面激活。
3. 完成 comment deletion 实际事务/差分，补物理并发与失败恢复验证。SQLite 单写者串行化允许，但必须证明正确性。
4. 检查所有来源摘要和执行证据，补前端及非 HTTP producer 覆盖，逐条完成 584 路由账本验收；禁止通过删项、改标签、忽略所有数据库差异来制造通过。
5. 完整复刻与切换验收前保留 Node mock、真实 SQLite 和上传字节；不得自动停写迁移。
6. 正确性稳定后再做代表性日常负载性能测试；高并发写差异单列，不宣称已达到未测指标。

## 差分证据注意事项

docs/superpowers/evidence 中保存了大量切片证据。例如最近附件上传 228、删除 276、owner-lock 403、signed metadata 132、listing 98、metadata 348、content 509、issue loader 293、wakeup actor 327，UUID7 为 24 fixtures / 17252 attempts。这些是各自记录时的局部差分规模，不能累加成端到端完成率。

共享 WakeupTransactions 提取发生在上传/删除/owner-lock 最后一次差分之后，相关旧来源摘要应视为过期，接手需把共享模块加入来源并重新运行。signed metadata/listing 增加了 raw JSON bytes 对比，但仍不证明物理 PostgreSQL 锁语义、真实 HTTP 全链路或全后端等价。运行 oracle 期间不要编辑绑定模块，避免启动时导入的代码和结束时记录的摘要不一致。

Go 原件保持只读。仅授权派生参考副本中 3 文件 6 处标准库方法名修复；不是授权改变参考行为。Go 工具链/派生输入和批次执行细节看旧交接及 evidence。使用隔离 Redis 命名空间/实例，不能 FLUSH 现有 26379 服务。Python 当前为 server/.venv 的 3.11；uv 位于 /Users/patrick/.local/bin/uv。

## 接手要求

当前是演示保护暂停点，不应自行继续 backend 大改或重启 4174。用户恢复实现后按现有决策推进 Python：优先实际 schema/事务/路由闭环和失败分支，随后性能。不要重复询问已批准的 Python、SQLite 选择，也不要把大量 Go 自测或文档整理当成 Python 实现交付。

本次交接提交后的确切 HEAD 以 `git log -1` 和 `origin/develop` 为准；交接文档提交本身随后推送。真实运行数据不在 Git，拉取代码不会自动携带演示数据或本机环境。
