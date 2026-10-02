# evkg 上游改动提案（待评审）

> 用途：把 Growth OS 在 M1-b.5 期间对 evkg 的三处改动整理成可直接提 issue / PR 的文本。
> 这些提交**只在本地**（`D:\projects\evkg`），**已确认不推送到** `redmaplewww/evkg`
> （用户 2026-10-01 指示）。
> 状态：待用户评审后决定是否建 issue/PR。

## 三个提交是一条链，请一并评审

单独看任何一个都会显得像局部修补；三个连起来才看得出是在补齐**证据落库的语义层**：

| Commit | 问题 | 修复 |
|---|---|---|
| `a4b15af` | 代码证据无法保留真实 locator（缩进被抹平、行号在归一化后失去意义） | `SourceKind.CODE` / `CodeReader` / `split_code_passages` / `ingest_code_file` |
| `e432c42` | 未评估的证据被错误降权（缺失值被当成 0.25 低分） | assessment lifecycle：缺失不带数字，且标明分级来源 |
| `068389d` | source 更新语义丢失（写入报成功但库里是旧值；换切分器后旧段落静默累积） | 逻辑身份 id + `content_hash` + 显式 upsert + 段落级联替换 |
| `28afbc0` | 下游不得不用裸 SQL 与自造路由才能用 evkg（前者改 payload，后者判后缀） | `ingest_path()` 统一路由 + `find_sources()` 按 metadata 检索 + `metadata` 透传 |

**为什么必须一起看**：`068389d` 是让下游能删掉自己那层裸 SQL 的**前提**，
`28afbc0` 才是**把那层裸 SQL 真正删掉**的那一步 —— 没有它，第三方依然需要
`json_extract` 与后缀判定，只是从"改 payload"变成"查 payload"而已。

四者的共同主题：**evkg 需要明确区分「证据是什么」「证据有多可靠」「证据属于哪一次内容」
「下游的领域标签是什么」，并让写入路径如实报告实际发生了什么。**

---

| 提交 | 主题 | 对应本文档 |
|---|---|---|
| `a4b15af` | `ingest: 源码作为一等来源（SourceKind.CODE / CodeReader / 行范围 locator）` | §提案一 |
| `e432c42` | `assessment: 未分级 ≠ 0.25（缺失值不参与加权，也不凭空抬高）` | §提案二 |
| `068389d` | `source: 逻辑身份 + content_hash + 显式 upsert（并修掉 passage 静默累积）` | §提案三 |
| `28afbc0` | `ingest/store: 补齐下游所需的两处公共入口（统一路由 + 按 metadata 检索）` | §提案四 |

四个提案可分别接受或拒绝。以下按"问题 → 证据 → 变更 → 行为变更与兼容性 → 已知限制 → 待决问题"组织。

---

## 提案四：补齐下游所需的公共入口

**建议标题**：`ingest/store: 统一路由 + 按 metadata 检索（让下游不必知道存储细节）`

### 问题

外部系统要基于 evkg 做一个领域应用（本例是个人能力成长系统）时，会发现自己不得不
自己做两件本该属于 evkg 的事：

1. **按内容类型路由**：判断一份文件是源码还是普通文本、该调用 `ingest_file` 还是
   `ingest_code_file`。这要求下游理解 `TEXT_SUFFIXES`、`CodeConfig.languages`、
   两套 reader 的能力差异 —— 这些都是实现细节。
2. **按 metadata 检索**：为了在 metadata 上打领域标签并在之后查回来，下游只能对
   `sources.payload` 写 `json_extract` 裸 SQL。

这两件事都会被"顺手"留在下游的适配层里，然后随时间变成对 evkg 内部结构的硬依赖。

### 证据

本仓下游（Growth OS）的适配层在本次改动前包含：

```sql
UPDATE sources SET payload = json_set(payload, '$.metadata.growth_evidence_type', ?, ...)
SELECT id FROM sources WHERE json_extract(payload,'$.metadata.growth_channel')=?
```

以及一份自造的 `TEXT_LIKE_SUFFIXES` 后缀表 + 分流逻辑。这几处正是我们要消灭的反模式的
实例 —— 业务层在替上游修补领域模型。

### 变更

- `ingest_path()`：按**内容类型**自动路由的唯一入口。
  * 源码/配置（命中 `Profile.code`）→ `ingest_code_file`，且 kind **一律取 `CODE`**。
    理由：源码之所以需要独立路径，正是因为读取与切分方式不同（保留缩进、记录行范围），
    这个区别属于"证据是什么"这一层，不该由调用方覆盖。
  * 普通文本 → `ingest_file`，kind 由调用方决定。
  * 其余 → `ValueError` 并提示走 V1 状态机。
- `ingest_file()` / `ingest_code_file()` 新增 `metadata` 参数：迁移调用方的领域标签，
  与 evkg 自己写的 `assessment` 合并（依赖 `save_source` 的 metadata 合并语义）。
- `KnowledgeStore.find_sources(metadata=None)`：按 metadata 键值对检索来源，
  替下游承担 `json_extract`。
- `ingest/__init__.py` 导出 `ingest_path` 与 `logical_source_id`。
- `cli.py` 改用 `ingest_path` —— 同一份"后缀→语言"知识不再有两处实现。

### 行为变更与兼容性

| 项 | 影响 |
|---|---|
| 新增 `ingest_path` | 纯增量 |
| `ingest_file` / `ingest_code_file` 新增 `metadata` 关键字参数 | 向后兼容（有默认值） |
| 新增 `find_sources` | 纯增量 |
| `cli ingest` 分派 | 行为等价（原分派逻辑搬到 `ingest_path`），代码量减少 |
| `ingest_path` 对源码**强制** `kind=CODE` | 这是有意的不变量：若调用方传入别的 kind 也会被覆盖，文档已写明 |

### 已知限制

- `find_sources` 目前是全表扫描后在 Python 侧过滤（未把 `json_extract` 推回 SQL）。
  对当前量级足够；来源数量级大时应补表达式索引或改为 SQL 侧过滤。
- `ingest_path` 仍不处理二进制格式（PDF/docx/xlsx/图片）—— 那需要 V1 状态机，
  而状态机目前有自身的已知问题（见提案一"已知限制"第 2 条）。

### 待决问题

- `ingest_path` 对源码强制 `kind=CODE` 是否可接受？替代方案是允许调用方覆盖，
  但那会让"源码"与"文本"的区别重新变成调用方的责任。
- 是否需要一个更明确的分层入口（例如 `evkg.public` 之类的门面模块）来固化"什么是
  公共 API"？当前的允许清单是下游自己维护的（见 Growth OS 的
  `tests/test_adapter_boundary.py`），若上游能给出一份显式清单会更可靠。

---

## 提案三：source 身份、内容变化与段落更新语义

**建议标题**：`source: 逻辑身份 + content_hash + 显式 upsert（并修掉 passage 静默累积）`

### 问题

四个相关问题，都属"数据库表面写入成功，实际证据图已过期"这一类：

1. **两套互不兼容的 source id 方案**：快路径用路径（`stable_id("src", 绝对URI)`），
   V1 状态机用内容哈希（`src_<hash20>`）。同一文件经两条路径得到两个 source。
2. **`content_hash` 在 `RawAsset → Source` 这一步被丢弃**，无法判断内容是否变化。
3. **`_put` 对 sources 用 `INSERT OR IGNORE`**：行已存在时**静默丢弃**新数据，
   调用方以为写成功而库里仍是旧值。
4. **passage 静默累积**：passage id 里含切分方式，换切分器后旧段落既不被覆盖也不被
   删除，只会累积。实测一个源里混进 11 条被旧切分器撕裂的片段（从表达式中间开始的
   文本），随后会被抽取成无意义主张并虚增证据计数。

### 证据

- 调试脚本直接抓到第 4 次 `save_source` 仍读到旧 `content_hash`（若沿用 OR-IGNORE 写法）
- 一个源里同时存在 9 条正确段落与 11 条被撕裂的旧段落

### 变更

- `Source.id` 统一为**逻辑身份**（同一文件/URL 恒定，与内容无关）。
  新增 `connectors.logical_source_id()` 作为唯一入口，快路径/状态机/manifest 共用。
  副作用（正向）：同一文件经快路径与经状态机现在得到**同一个** id。
- `Source.content_hash` 新增。契约是
  **content_hash 相同 ⟺ 段落所依据的文本相同**，因此基于**换行规范化后**的文本，
  不是磁盘原始字节。详见"两个 hash 的分工"。
- 新增 `decode_text()`：显式统一换行。`read_bytes().decode()` 不做换行翻译，
  Windows 上 CRLF 会让每行多出 `\r` 混进 passage 文本（实测让 locator 回原文的
  逐字校验失败）。
- `save_source()` 返回 `WriteOutcome` = `inserted` / `updated` / `unchanged`：
  * `metadata` **合并**而非整体替换 —— 这是 `unchanged` 能成立的前提，也让 evkg 自己的
    `assessment` 与下游写的自定义键互不覆盖
  * `access_date` 表示**首次落库时间**，不参与变更判定，`unchanged` 时保留原值
  * `_put` 对 sources 改为真 upsert（`ON CONFLICT DO UPDATE`），从根上消除 OR-IGNORE 的坑
- `save_passages(..., replace_source=True)`：按**整体**替换各来源的段落集合
  （所有既有调用方本就一次传入完整集合）。
- 新增 `purge_passages()`：删段落时**级联清理**依赖行并返回各表数量（见下）。
- `pipeline._save_source_passages()` 透传 kind 与 content_hash，不再硬编码 UNKNOWN。

### 两个 hash 的分工（容易被误用，建议在文档里写死）

```
RawAsset.content_hash  = 原始字节哈希  → ingestion 层去重 / 资产寻址
Source.content_hash    = 规范化文本哈希 → evidence 层"语义是否变化"检测
```

不区分会出问题：一次 `git checkout` 把 CRLF 换成 LF，若按原始字节比较，**所有来源都会
被判成"内容已变"并触发整轮重新抽取**，而文本一字未改。

### 为什么删除段落必须级联

实测只删 passage 会**同时点亮四条不变量**：

- `evidence_missing_passage`（evidence 指向已删 passage）
- `claims_without_evidence`（删掉 evidence 之后）
- `events_missing_passage`
- `ledger_complete_passage_missing`

也就是留下一个**自己审计不过的库**。而且级联在语义上也是正确的：原文已经不在了，
依赖它的证据、以及失去全部证据的主张都失去了依据，留着就是无依据的断言。

`purge_passages()` 的顺序：evidence → 因失去全部证据而孤儿化的 claim 及其 relation →
幸存 claim 的 `passage_ids` 剪除已删 id → events 及其派生的 timeline/place 行 →
抽取账本 → entity_aliases → 最后 passages。**返回各表清理数量并写审计日志**：
级联删除是真实的数据损失，必须让调用方看见。

### 行为变更与兼容性

| 项 | 影响 |
|---|---|
| `save_source` 返回值 | 从 `None` 变为 `WriteOutcome`。**向后兼容**（原调用方忽略返回值） |
| `save_passages` 返回值 | 从 `None` 变为计数 dict。**向后兼容** |
| `save_passages` 默认改为替换 | 既有调用方本就传完整集合；对"追加写入"的用法是**破坏性**的，但本仓无此用法 |
| `Source` 新增 `content_hash` | 纯增量，旧数据读回为 `None` |
| source id 方案统一 | **会改变**经 V1 状态机入库的 source id。若已有这类数据需迁移 |
| `access_date` 语义固化 | 从"每次写入的时间"变为"首次落库时间"（实际旧行为因 OR-IGNORE 本就如此） |

### 已知限制

- 级联删除是**硬清理**，不保留被失效主张的历史。若将来需要"曾经有过什么主张"的审计
  视图，需要引入 `supersede` 模式（标记失效而非删除）。**本提案不引入**，仅记下这个
  演进方向。
- `manifest` 的 Wiki 词条身份是「api + 页名」复合键，不是路径也不是 URL，因此显式传入
  `source_id`，不走 `logical_source_id` 的路径分支。
- 段落在物理上被删除后，`RawAsset` 仍保留原始内容；重建段落需要重新 ingest。

### 待决问题

- 段落替换的默认值应该是 `replace_source=True`（当前）还是必须显式声明？考虑到"静默
  累积"是本提案要修的 bug 之一，我倾向让"替换"成为默认（安全的那一侧）。
- 长期是否需要 `source_version` 表来保留内容变更历史？当前用 `content_hash` + 每条
  写入的审计日志覆盖了"什么时候变成什么"，但不保留旧文本。**本提案刻意不引入**，
  留待真正需要时再加。

---

## 提案一：源码作为一等来源

**建议标题**：`SourceKind.CODE / CodeReader / 行范围 locator：不要把代码当"文本的特例"`

### 问题

代码此前只能靠"扩展名不在 `TEXT_SUFFIXES` 里就走不通"或"伪装成 `text/*` 让 `PlainTextReader` 接住"两条路进入系统。两条路都有实质缺陷：

1. **通用文本切分会摧毁代码。** `split_passages` 执行 `re.sub(r"\s+", " ", part)`，把缩进抹平、把整个方法压成一行。缩进在代码里承载语义。
2. **行号会失去意义。** 实测 `normalize_document` 把一份 8 行带缩进的 Java 片段变成 3 行：
   `'public class A { private int x;\n\npublic int get() { return x; } }'`。
   而 `_save_source_passages` 切的正是归一化后的文本，因此在该路径上算出的行号是虚构的。
3. `PlainTextReader.supports` 把两个不同的问题（"我是不是纯文本" / "我支持哪些类型"）用 `or` 混成一个判断，导致 `text/x-java` 会被它先认领 —— 顺序敏感但没有任何地方说明。

**为什么这很重要**：证据系统的核心承诺是"这条结论的依据可以点回去核对"。如果行号不可核验，这个承诺就是空的；一个说谎的 locator 比没有 locator 更糟。

### 证据

- 8 行 Java → 归一化后 3 行、缩进全失（`cleaning.py:9-30` 的 `re.sub(r"[ \t]+", " ", text)` 与按行 `" ".join`）
- 文本切分器在 `RagService.java` 上产出 `'= null) { List<VectorSearchResult> vecto'` 这类从表达式中间开始的片段

### 变更

- `domain.SourceKind.CODE`：与 `primary` 同属第一手产物，但需要独立读取与切分
- `config.CodeConfig`：`languages`（后缀→语言）、`filenames`（无扩展名的构建/配置文件）、`max_lines_per_passage`、`coalesce_blocks_up_to_lines`。
  **语言表放在 `Profile` 而非硬编码** —— 遵循本仓"领域假设住在领域包"的既有原则，下游可扩展而不必改源码
- `config.code_language_for()`：单一判定入口，供 reader / 连接器 / CLI 复用，避免多处后缀表漂移
- `providers.CodeReader`：只按后缀表声明能力（**不接受 `text/*`**），只做 UTF-8 解码，不做空白归一化
- `splitting.split_code_passages()`：保留空白切分 + 行范围 locator
  - 块边界 = 空行 ∪ **退格到主体层**（`_body_indent`）；退格到方法体内部**不切**（否则方法体会碎成一堆只含 `}` 的片段，实测出现 16 段里 5 段是括号）
  - 块缩进取**块内最小缩进**（否则 `}` 之后的成员边界不可见，实测出现 50 行巨型块）
  - 合并小同缩进块时按**合并后总行数**设上限，防止小块无界滚成大块
- `connectors.ingest_code_file()`：与 `ingest_file` 并列的同步快路径；**刻意不经过 V1 状态机**（因为归一化会破坏行结构）
- `policies` / `Profile` / `default.yaml`：`code` 基线 0.80，rationale 明确"存在≠达成"
- `cli`：`ingest` 按语言表自动分派；`--kind` 帮助补全
- `pipeline`：`CodeReader` 加入默认 readers，并注释说明为何必须排在 `PlainTextReader` 之前

### 行为变更与兼容性

| 项 | 影响 |
|---|---|
| 新增 `SourceKind.CODE` | 纯增量。既有 6 个 kind 的基线**一格未动**（有测试锁定） |
| `_result()` 增加关键字参数 `language` | 向后兼容（有默认值） |
| `default.yaml` 增加 code 条目 | 新增一行 |
| `pipeline` 默认 readers 增加一项 | 顺序变化，但 CodeReader 只声明本仓此前无法处理的格式 |
| `cli ingest` 分派逻辑 | 原来对代码文件报错，现在能处理。**原报错路径的调用方需注意**，但那是失败路径 |

### 已知限制（有意为之，非缺陷）

1. **不解析 symbol/AST**。因此类的第一个成员会与类声明行合并成一块。试过更"聪明"的缩进启发式，会在"方法内含更深嵌套块"时误判并把方法切碎 —— 那个错误更严重，所以选择简单规则并记录限制。真正的修复需要符号解析。
2. **`normalize_document` 未改**。它仍会折叠空白并重排行，因此**经 V1 状态机无法保真行号**；`ingest_code_file` 绕开了它。要打通状态机需先让归一化对代码无损，且 `completeness` 的史学期维度（作者/地点/事件）对代码是噪音 —— 两件事都不在本次范围。
3. `ingest_file` 内处理 `.html` 的分支仍是**死代码**（`.html` 不在 `TEXT_SUFFIXES`，函数提前抛错）。本次未动，仅记录。

### 待决问题

- 是否愿意接受"`CodeReader` 只按后缀表声明能力、不接受 `text/*`"这一取舍？它把 `PlainTextReader` 的 capability 判定问题绕开了，但没有根治。更彻底的做法是拆分 `supports(media_type, name)` 为两个独立判据，那会是一次更大的接口变更。
- `CodeConfig.filenames` 的默认列表（Dockerfile / Makefile / Jenkinsfile / …）是否合适放在仓内默认值里？还是应该只留空表、由领域包提供？

---

## 提案二：未分级 ≠ 0.25

**建议标题**：`assessment: 把"未分级"从默认值改为缺失值（缺失不参与加权，也不凭空抬高）`

### 问题

`policies.preliminary_claim_confidence` 与 `attack.verifier.verify_claims` 各有**一处 `default=0.25`**，把"没有来源分级"这个**缺失值**当成了"低质量评分"。

**实测危害**：一个 `kind=code` 的来源（策略表基线 0.80）只要没有缓存 `metadata.assessment`，就会被按 **0.25** 计权。同源、同内容，仅因缓存有无，权重差 **0.55**，且**全程静默、无任何提示**。

反向的坑同样致命：若把缺失兜底成**高分**，未经核验的自述或自声明就能靠"未评估"这条通道凭空获得可信度 —— 这正是证据系统最该防的事。

### 证据

```
来源 kind=code，策略表基线=0.80
实际用于加权 = 0.25   →  候选分数 0.25
照：同一来源有缓存分级时 → 0.80
```

### 变更

- 新增 `ASSESSED` / `UNASSESSED` 两个状态常量，明确区分：
  - `SourceKind.UNKNOWN` = "来源类型未知"，是策略表里一条**明确的先验**，基线 0.25 是它的**正常取值**
  - `UNASSESSED` = "尚未分级"，**没有取值**
- `assess_source()` 增加 `status` / `origin` 字段
- 新增 `assess_unassessed()`：`baseline_score` 为 `None`，**不携带任何数字**
- 新增 `resolve_source_assessment(source)`：有缓存用缓存；否则按 `kind` **确定性推导同一份策略表**（不是猜测）；来源缺失则 unassessed。`origin` 如实标出 `cached` / `derived_from_kind` / `missing_source` / `missing_kind`，便于审计区分"逐来源评估过"与"只用了类型先验"
- `preliminary_claim_confidence()`：无可用基线时返回 `score=None` + `assessment_status='unassessed'`，不再发明数字
- `domain.Confidence`：`score` / `source_reliability` 改为可空，新增 `assessment_status`（缺省 `'assessed'`，**旧数据仍可读回**）；`EvidenceLink.confidence` 同样可空
- `extract` / `verifier` / `adversarial`：同步处理 `None`
  - 未分级时不做可靠性加权，claim 记为 `DISPUTED`（不予采信），并在 `metadata.assessment_status` 单独标注，避免与"证据被反驳"混淆
  - `adversarial` 新增模块级 `claim_score()`：未分级按 0 参与**筛选与排序**（仅排序用途，不改变其 unassessed 状态），避免 `None` 比较抛错

### 行为变更与兼容性

| 项 | 影响 |
|---|---|
| `Confidence.score` / `source_reliability` 可空 | **潜在破坏性**。受影响的读取方：`extract` 构造、`store.save_claim`（写 `relations.confidence` 列，接受 NULL）、`dossier` 渲染、`index/search` 与 `web` 的 `ORDER BY json_extract(confidence.score)`（NULL 在 DESC 下排最后，安全）、`adversarial` 筛选排序、`audit_store`。**这 6 处在本次改动中逐个验证过** |
| `assessment_status` 缺省 `'assessed'` | 旧行读回时视为已评估，**不改变旧数据语义** |
| 已评估情形的数值 | **逐位不变**（7 个 kind 全部有测试锁定） |
| 未分级情形的行为 | 从"静默 0.25"变为"显式 `None` + 状态标注"。**这是本次唯一有意的行为变更** |

### 已知限制

- `ORDER BY score DESC` 下 NULL 排最后（安全方向），但查询侧没有显式 `NULLS LAST`，依赖 SQLite 默认行为。
- `assessment_status` 是自由字符串而非枚举（为保持 `Confidence` 的 `extra="forbid"` 下向后兼容）。若希望强类型化可以再改。

### 待决问题

- **是否接受 `score` 可空？** 这是本次唯一的破坏性 schema 变更。若不接受，替代方案是保留 `float` 并把未分级压到某个值 —— 但那等于回到"用一个数字代表缺失"，正是本提案要消除的问题。
- 未分级时 claim 记为 `DISPUTED` 是否合适？它复用了既有 `ClaimStatus`（未新增生命周期），但 `DISPUTED` 字面含义是"有争议"。另一种选择是保留 `EXTRACTED` 不动、仅靠 `assessment_status` 标注。
- `resolve_source_assessment` 的 `origin=derived_from_kind` 是否应该也反映在 claim 上（即"这条 claim 只用了类型先验、未逐来源核验"）？目前只在来源分级层记录。

---

## 两提案共同的测试与质量情况

- evkg 测试 **31 → 81 项**（新增 `tests/test_code_ingest.py` 30 项、`tests/test_assessment_lifecycle.py` 20 项）
- lint：存量 26 项，改动后 25 项（**未新增**，顺带修掉 `ingest/__init__.py` 的 I001）
- 全部既有测试保持通过，无跳过、无 xfail

### 与既有行为的兼容性验证方式

Growth OS 侧对"旧数据不能被顺手改动"做了独立验证：升级 evkg 后**不做任何重新入库**，逐字段比对快照 —— 完全一致、表计数无差异；3 个既有来源的分级解析后 `origin=cached`，基线未变。

---

## 一份需要单独确认的小修正

`README`/`.env.example` 里文档化的复核模型变量名与代码不一致：

- 代码读取的是 `EVKG_VERIFIER_LLM_PROVIDER`（`attack/verifier.py:39-40` 用 `env(f"VERIFIER_{suffix}")`，suffix 为 `LLM_PROVIDER`）
- 而 `.env.example` 写的是 `EVKG_VERIFIER_PROVIDER`

按示例文件配置会导致**独立复核模型静默失效**（回落到主模型，即"自己审自己"）。这一条我未改动，仅在此记录，建议单独提交修正。
