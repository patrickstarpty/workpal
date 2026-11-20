# Workpal Evidence Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将真实上传的UTF-8文本/JSONL在进入持久化前解析为有界、按显式策略删字段和掩码的副本，保留原始与副本各自hash及准确截取事实。

**Architecture:** 一个纯计算深Module隐藏解码、行数/字节上限、封闭策略、字段选择、字面掩码和hash规则，调用者只调用normalize_upload。它不接收Actor、不授予权限、不写文件或数据库；后续持久上传Interface先授权，再调用本Module，只保存返回的副本及原有来源限制。现有Artifact暂存会先存原始字节，因此本路径不能先将原日志交给Artifact再脱敏。

**Tech Stack:** Python3.11标准库、既有DomainError、Django SimpleTestCase；无依赖新增或外部调用。

**Spec:** [设计环境证据与数据权限](../specs/2026-11-20-workpal-software-development-design.md)、[D1](2026-11-20-workpal-phase-d-environment.md)、[并行计划](2026-11-20-workpal-parallel-delivery.md)。本任务D1b1为上传内容Module，D1b2另接EvidenceSnapshot/当前权限/幂等/预算和上传传输。

## Global Constraints

- “查询结果在进入模型上下文和持久化前做脱敏”。“仅掩码字符串不自动解除限制”。
- “单次最多 1000 条或 2 MiB”。“不能对某条上传日志进行分析后声称已读取整个环境。”
- 原始hash指本次提交的完整原始bytes，副本hash只指实际返回的UTF-8副本；不伪称副本为原件。
- 共享工作区；GPT6.1 Sol实施、父代理监督。禁止Git写操作/worktree/安装/网络/模型/Runtime，不改旧原型、公共配置或兄弟文件。
- 使用.venv-workpal/bin/python，不使用python。85项SHA256保护基线只允许.gitignore既有差异。

## Review Focus

1. 超过字节上限或掩码导致输出膨胀：分别拒绝，不先存原始内容或返回超限副本。
2. 1001条记录与空白行：明确截断及原始行号，不把上传片段当环境覆盖率。
3. 策略为空/错误/未批准文本：封闭校验；只做配置声明的字面掩码，不宣称自动发现全部秘密。
4. JSON重复key、NaN、非法Unicode、保留字段的嵌套值：拒绝且错误不包含原始数据或解码异常内容。
5. 字面值含正则/命令/提示注入、重叠掩码与可变输入：只作为数据，结果稳定且无外部副作用。

## Task D1b1: Normalize an uploaded excerpt before persistence

**Files:** Create `services/workpal/workpal/investigation/normalization.py`、`NORMALIZATION.md`、`services/workpal/tests/test_evidence_normalization.py`。只有这些文件；不改models/apps/actions/现有README、迁移、settings、Registry或现有测试。集成Agent会暂时排除此在途测试模块。

**Interface:** `normalize_upload(content: bytes, *, format: str, policy: dict) -> dict`。

输入合同：
- content只接受bytes，最长2097152字节，先检查长度再解码/JSON解析；大于上限抛DomainError `upload_too_large`，status413。类型错为`invalid_upload`400。不偷偷截取字节后称其为整个文件hash。
- format只允许`text`或`jsonl`。UTF-8严格解码，允许单个开头BOM（raw hash仍含它），非法编码拒绝。按LF分行，去CRLF末尾CR；跳过全空白行但保留其对原始1-based行号的影响，其余文本不trim。只取前1000条非空记录；后续记录不解析，仍在raw hash/总条数中，返回truncated。输入原始字节限制始终生效。
- policy封闭且四字段均必需：`{version:1, allow_text:bool, allow_fields:list[str], redact_literals:list[str]}`。version拒绝bool；两个list各最多100个唯一项。字段名1..128字符，literal1..256字符，不接受空串/无效Unicode；无需正则。allow_fields为精确顶层key列表，不做路径访问。为避免字段名本身携带待遮蔽值，allow_fields包含任何redact_literal时拒绝policy；不自动改名制造key碰撞。
- text仅在allow_text=true时接受，否则`text_upload_not_allowed`403。JSONL每条保留记录必须为JSON对象，拒绝重复key、NaN/Infinity及无法解析的JSON。只保留allow_fields中的现有key，遗漏不补值；被保留值只支持JSON scalar（null/bool/number/string），object/array拒绝为invalid_upload；未选字段完全丢弃，不把字段名或值放到返回元数据。异常消息不得带原行、secret或policy literal。
- 对保留的字符串值和text整行进行literal掩码，替换为固定`[REDACTED]`。按原输入从左到右取最长匹配，同长按字面值稳定排序；非重叠一次替换，替换标记不再次参与匹配。不解释正则、SQL、shell或其中指令。顺序不同的等价policy产生相同policy hash和结果。

输出合同（只这些字段）：
- `origin:'user_upload'`，`coverage:'uploaded_excerpt'`；`format`；`status:'ok'|'no_data'|'truncated'`。
- `content`：text为选中行掩码后用LF连接；jsonl为每个保留对象的canonical JSON（UTF-8、sort_keys、紧凑分隔、ensure_ascii=False、allow_nan=False）用LF连接；均无额外尾LF。空输入或全空白返回空content/no_data。只剩空对象仍是实际保留的记录，不捏造有效诊断结论。
- `raw_sha256`（完整content输入bytes）、`content_sha256`（返回content的UTF-8bytes）、`policy_sha256`（四字段规范化、两个list排序后的canonical JSON）；不返回policy原始literal。
- `raw_bytes`、`content_bytes`、`total_records`（原输入非空行数）、`included_records`、`included_line_numbers`（最多1000原始行号）、`truncated`严格bool、`redaction_count`（实际非重叠替换次数）、`omitted_fields`（被丢弃顶层字段总数，text为0）。JSONL仅统计前1000条被解析的字段，不猜被截断部分内容。
- 输出UTF-8内容也必须≤2097152字节；掩码或JSON转义膨胀超限抛`normalized_upload_too_large`413，无部分副本返回。status由truncated优先，否则空记录为no_data，其他ok。
- 所有返回容器独立，不持有policy可变列表引用。既有DomainError用于错误；解析/编码异常转为`invalid_upload`400或`invalid_redaction_policy`400，短通用消息，禁止原始异常链泄露内容。不打印、记录、写临时文件、联网或调用模型。

这里的policy是后续管理员配置传入的事实，不是由上传人自行授予的发布许可。字面掩码不是通用秘密检测器；即使清洗后也必须继承环境/来源权限。此Module不推断事件时间、request ID、部署SHA、完整时间覆盖或根因；D1b2保存明确元数据并作当前授权。查询30分钟默认/显式时间、30秒timeout/10次预算属于后续采集账本，不用纯函数伪装已执行。

- [x] **Step 1:** 建立只含明确NotImplementedError的Interface，并写`test_text_excerpt_masks_and_hashes_real_bytes`，调用公开Interface断言实际文本掩码、两种不同hash、来源和范围。先运行记录真实缺行为红灯，不用ImportError；日志`/tmp/workpal-d1b1-red.log`。
- [x] **Step 2:** 完成上述一个Module和文档，使同一测试转绿；保留原始值仅在调用内存，不创建文件/ORM对象。
- [x] **Step 3:** 写独立Interface测试：JSONL字段删除/保留scalar和稳定canonical hash；恰好2097152与2097153字节（超大且无效UTF-8仍先413）；1000/1001记录、空文件/空白、BOM/CRLF原行号；无效format/bytes/UTF8/JSON/重复key/nonfinite/保留nested及脱敏错误；policy缺字段/额外/类型/bool/上限/Unicode/禁文本；正则元字符仅字面匹配和最长重叠不重替换；policy列表重排/输入输出突变隔离；输出膨胀413、stdout/stderr为空、秘密不出现在错误message/details。至少八个独立test方法，可用subTest表达同类输入，不按子case虚增数量。
- [x] **Step 4:** `.venv-workpal/bin/python services/workpal/manage.py test tests.test_evidence_normalization --noinput`与Django check退出0，核对85项保护。日志`/tmp/workpal-d1b1-{green,check,hashes}.log`。不跑全量（集成Agent正在跑已验收模块），不改config或根npm。
- [x] **Step 5:** 报告精确Interface/文件、真实红绿和独立测试数、限制及待接线。先红后绿缺失如实记录，不回退功能伪造。完成解析Module不等于用户已可HTTP上传、Evidence已入SQLite、模型可读或故障已确认。

## Supervision acceptance — 2026-11-20

D1b1纯计算Module验收通过。Sol原公开Interface真实NotImplementedError红灯后实现，10项专项、check和85项保护通过。父代理复跑10项并额外调用公开Interface，发现未选字段中1e999被解析为Infinity、非法Unicode值被忽略而未拒绝；这违反保留记录须为合法JSON的合同，不能以字段随后删除为由跳过验证。

父代理新增`tests/test_evidence_normalization_review.py`三个独立测试：被丢弃字段（含嵌套）依然拒绝非有限数/非法Unicode；合法未选嵌套仍正常丢弃；100个字段/128字符及100个字面值/256字符的准确上界可用。前一测试四个subcase实际断言失败，`/tmp/workpal-d1b1-review-red.log`；最小修复为解析后遍历JSON值校验，再按策略选择字段，未增加任何公开Interface。

原10+新增3=13项退出0，`/tmp/workpal-d1b1-review-green.log`；Django check及保护核对退出0，`/tmp/workpal-d1b1-review-{check,hashes}.log`。新测试未继承含test方法的类；没有把四个subcase计为四个独立测试。没有数据库/HTTP/模型/文件原始内容持久化，保留所有来源限制，仍不保证发现未配置的秘密。

下一D1b2先冻结管理员来源策略、不可变Evidence、当前授权/幂等/预算和文件传输的合同；当前默认配置集成仍在进行，不能同时改investigation模型和迁移。可并行准备计划，实施在集成审查之后接续。
