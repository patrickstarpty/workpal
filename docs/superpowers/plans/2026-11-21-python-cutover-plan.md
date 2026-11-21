# Python 前后端切换实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留简单的 `npm start` 入口，完成 Python 前后端连接及数据验证，通过验收后退役 Node mock。

**Architecture:** React 通过同源 HTTP/WS 访问 FastAPI，SQLite 持久化业务数据，Redis 支撑现有 worker 和事件系统。开发使用 Vite 代理；构建后由 Python 提供前端文件。Node 可以保留为轻量进程启动器，但不再承载业务 API。

**Tech Stack:** React、Vite、Python 3.11、FastAPI、SQLAlchemy、Alembic、SQLite、Redis、pytest、Playwright。

**Spec:** `docs/superpowers/specs/2026-11-21-python-cutover-design.md`

## Global Constraints

- 先对接、再验证、最后删除 Node mock 服务、自动填充逻辑及专属测试，并调整关联脚本。
- 保留 `npm start`，不引入 Nginx 或要求用户分别启动前后端。
- 保留 Workpal 品牌、英文 UI、键盘与窄屏访问。
- 不执行技能安装命令，不调用真实模型。生产集成与生产身份提供商不在本次范围。
- 不覆盖已有 SQLite 数据、后续编辑、备份或归档审阅资料。
- 未实现操作明确失败；历史记录不能伪装成新生成的模型输出或测量值。

## Review Focus

- 已导入数据库有后续编辑或删除：现有证据不能识别历史合法删除，原因不明的缺行阻断，不重新灌入旧值（任务 1）。
- 空数据库：只迁移 schema，不自动生成项目或演示数据（任务 1、3）。
- 未知 API 与静态路径穿越：不得返回 SPA 成功页面或泄露文件（任务 2）。
- Redis 故障、端口冲突、启动失败与中断：明确退出且不遗留子进程（任务 3）。
- 登录失效、跨工作区访问、WS 重连：不得泄露或写入其他工作区数据（任务 4）。

- 预检后旧库继续写入：最终冻结重验摘要，差异使放行失效（任务 5）。
- 回退启动旧库导致分叉：只能回退到兼容当前 Python 库的已验证提交（任务 4、5）。

## Task 1：确认数据迁移完整性

**Files:** `server/src/workpal_backend/legacy_import.py`、`server/tests/test_legacy_import.py`；新增 `server/tools/audit_legacy_import.py` 和对应测试。

**Interfaces:** 审计工具接受源 SQLite 路径和目标 SQLite 路径，只读输出源摘要、manifest、分类型计数、ID 映射及原始内容差异；有不一致或缺行原因无法证明时以非零状态退出；不得以 already_imported 或 manifest 汇总作为完整性结论。复用现有显式 `import-legacy --source ... --owner-email ... [--dry-run]`，不在应用启动时自动导入。

- [x] 阅读已有导入测试与 manifest schema，补充只读审计、后续编辑、源变化与目标冲突的测试；特别覆盖导入 12 条后删除 1 条、manifest 不变且重跑仍报告 12 条时，审计必须非零退出并报告未知原因缺行；先确认新增测试失败。
- [x] 实现只读审计工具；以导入快照和 source_body 对账，分开报告当前业务记录变化，不能仅以总数判定迁移成功。当前缺少独立快照与逐条删除凭据，不自动判断合法删除；如需该能力须另行设计，不能事后补记来证明历史删除。
- [x] 在隔离数据库运行导入、幂等重跑及失败回滚测试；确认空库无自动种子数据。
- [x] 只读审计现有源库与 Python 库并记录结果。该报告仅为预检；只有不存在导入清单且无目标冲突时，协调写入进程、通过 SQLite backup API 备份后执行显式导入。
- [x] 验证：`server/.venv/bin/python -m pytest server/tests/test_legacy_import.py` 及新增审计测试全部通过；实际数据差异须有可验证证据；原因无法证明的缺行阻断验收，不能靠重新覆盖或口头解释放行。

## Task 2：Python 提供构建后的前端

**Files:** 新增 `server/src/workpal_backend/frontend.py`、`server/tests/test_frontend.py`；修改 `app.py`、`config.py`、`cli.py`。

**Interfaces:** 提供 `mount_frontend(app, directory)`，仅在显式配置前端目录时启用；CLI 支持 `serve --frontend-dir <path>`。API 路由优先；未知后端路径保留错误状态；普通前端导航允许 SPA 回退。

- [ ] 编写入口 HTML、静态资产、SPA 导航、未知 API、目录穿越、缺失产物及 HEAD 请求的测试，确认新增测试失败。
- [ ] 实现静态托管边界与 CLI 参数；限制访问到产物目录，保留正确 Content-Type，避免入口页面缓存导致发布后资源不一致。
- [ ] 验证：新增测试全部通过，既有 health/auth 路由仍正常；API 错误不能被 HTML 成功响应掩盖。

## Task 3：统一启动入口与环境配置

**Files:** `scripts/python-web-dev.mjs`、`apps/web/vite.config.mjs`、`package.json`；新增 `scripts/workpal-start.mjs`、对应 Node 测试和不含密钥的环境配置示例。

**Interfaces:** `npm run dev` / `dev:web` 启动 API、worker、Vite；`npm start` 启动 API、worker 并托管 `apps/web/dist`，不依赖 Vite 开发服务。复用启动器进程生命周期逻辑，避免复制两个不同的清理实现。

- [ ] 先检查现有启动器及相关测试位置，补充开发/构建模式、端口冲突、缺失配置/产物、Redis 不可用、子进程异常退出和中断清理测试；确认新增断言失败。
- [ ] 实现统一入口，保留 `npm run build` 与 `npm start` 使用方式；缺少产物提示先构建，缺少密钥或 Redis 配置明确报错，不静默回退 Node mock。
- [ ] Vite 默认完整代理 API/auth/WS 路径；保持同源会话和一致的 FRONTEND_ORIGIN。
- [ ] 保持 docs 原有开发能力或明确独立命令；配置示例说明一次性准备步骤，不硬编码密钥或自动生成业务数据。
- [ ] 在隔离环境验证开发入口和构建入口，确认退出后自有 API/worker/Vite 进程均清理，不影响外部进程。

## Task 4：前后端接口与浏览器验收

**Files:** `server/contracts/`、`server/tests/`、`apps/web/app/` 及相关请求调用模块；`scripts/python-workspace-import-qa.mjs`，必要的新 Python 浏览器验收脚本。

**Interfaces:** 以当前 React 请求为验收输入，记录方法、路径、身份、工作区、请求/响应与失败语义。已有 Python API 优先修正真实不匹配，不扩展模型执行或生产集成。

- [ ] 盘点当前应用请求及既有 contract 清单，列出已支持、需修复和明确不支持的操作。
- [ ] 每个真实缺口先补能复现的契约/接口测试，再修复后端或前端；覆盖认证、CSRF、跨工作区拒绝及错误后的 UI 恢复。
- [ ] Python 导入 QA 改用独立最小 SQLite 夹具，不再 import Node store；此时仍保留旧 Node 实现与专属测试。
- [ ] Playwright 验证登录→能力入口→原工作区，项目/任务/评论读取，代表性创建/编辑/删除，刷新与服务重启后持久化、退出登录、键盘访问及窄屏布局。写入测试只用隔离库。
- [ ] 验证 WS 订阅权限、事件送达、重连及登出后失效；验证未支持操作明确失败，不产生虚构结果。
- [ ] 将 `npm run check` 接入 Python 测试、相关脚本检查和前端构建；删除前仍运行旧回归测试作为对照。Redis 集成测试使用独立命名空间，禁止 flush 共享实例。
- [ ] 运行 `npm run check`、完整 Python 测试和浏览器验收。保存命令、环境要求、退出码、测试数、跳过项和结果。关键测试未执行或失败时，不进入任务 5。

- [ ] 保存删除前已通过验收的 Python 兼容回退版本：记录具体提交 SHA、构建产物、配置、当前数据库规范路径与 schema revision。即使该提交还保留 Node 源文件，其 npm start 也必须走 Python。
- [ ] 在隔离库演练切换后新增记录，再停止写入并回退至上述提交；确认新增记录仍可读，后续写入仍进入同一 Python 库，旧库摘要不变。若 schema 不兼容或演练失败，不得进入删除阶段。

### Task 4 scoped closure — 2026-11-21

- [x] 对六项剩余读取缺口逐项对照客户端与旧 Node；真实空态和明确 501 分别记录，并验证工作区权限。
- [x] 普通评论持久化、CSRF/非成员拒绝、字段不支持 501、identifier 工作区隔离后端回归。
- [x] 隔离浏览器验证 WS 断开重连后第二事件、登出关闭；服务端验证非成员订阅拒绝。
- [x] 本范围最终 npm run check 一次通过；只运行受影响 realtime 浏览器场景。详见 evidence/2026-11-21-python-contract-realtime-status.md。

上方广义验收及回退条目不因本范围通过而自动勾选；父代理继续负责剩余门槛。

## Task 5：最终冻结、重新对账后退役 Node mock

**Files:** `server/api.mjs`、`store.mjs`、`start.mjs`、`fixtures.mjs`、`mock-content.mjs`、`contribution.mjs`、`seed.json`、对应旧测试；消费它们的 `scripts/`、`package.json`、README、server README 和适用仓库说明。

**Interfaces:** 活跃应用和脚本不再导入旧模块；迁移工具与独立测试夹具保留；数据库、备份、Go 参考代码和历史文档原位保留。

- [x] 先用隔离副本测试“预检后旧库新增/编辑/删除”三种场景：最终源摘要变化必须撤销早期放行；测试冻结后再次出现旧写入也必须阻断。
- [ ] 进入最终维护窗口：停止旧 Node 及所有旧库写入者、禁用自动重启，并暂停 Python API/worker 等目标写入者；记录时间及停写证据。旧行为对照只用隔离副本，不能再连接原库。
- [ ] 通过 SQLite backup API 备份冻结的源与目标；按导入器逻辑重新计算源摘要，对比预检和 manifest，并运行目标逐条审计。摘要变化或原因不明缺行使旧证据失效，停止切换与删除，不自动重导入。
- [ ] 将最终审计报告绑定源摘要、目标快照、schema revision、应用提交及时间；对照全部删除门槛与回退演练证据。通过后只恢复 Python 写入，旧库持续封存；无法维持旧库停写就不得放行。
- [ ] 用 `rg` 盘点旧模块及 seed 的所有活跃消费者；保留仍有价值的产品验收，将其切换为 Python；删除真正只针对旧实现的测试和脚本。
- [ ] 删除 Node mock 服务与业务自动填充模块，清理旧启动/检查引用。检查 `server/python/tests` 后仅整理确认重复或失效的内容。
- [ ] 更新文档，清晰区分 npm 启动器与已退役 mock 服务；说明 SQLite 路径、迁移命令、配置要求和未实现能力。
- [ ] 再次运行 `npm run check`、Python 测试、开发/构建启动验收和 Playwright 回归；扫描活跃引用确保无失效导入。
- [ ] 交付删除前后验证记录及限制说明。需要恢复时只使用任务 4 记录并演练通过的具体 Python 兼容提交，继续指向当前 Python 数据库；不得回退到 npm start 打开旧库的版本。若后续迁移破坏兼容性，重新选择和验证回退点；无可用版本则保持维护状态，不降级 schema 或覆盖当前数据。

## 完成定义

`npm start` 打开真实 Python 后端支持的完整应用；已迁移数据可核对且持续写入 SQLite；全部删除门槛通过；旧 mock 仅在验证后退役；删除后的完整验证再次通过。此计划尚未执行，不能把设计中的验收条件当作已完成结果。
