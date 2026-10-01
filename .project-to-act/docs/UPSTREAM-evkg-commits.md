# evkg 上游改动提案（待评审）

> 用途：把 Growth OS 在 M1-b.5 期间对 evkg 的两处改动整理成可直接提 issue / PR 的文本。
> 这两个提交**目前只在本地**（`D:\projects\evkg`），**尚未推送**到 `redmaplewww/evkg`。
> 状态：待用户评审后再决定是否推送或建 issue。

| 提交 | 主题 | 对应本文档 |
|---|---|---|
| `a4b15af` | `ingest: 源码作为一等来源（SourceKind.CODE / CodeReader / 行范围 locator）` | §提案一 |
| `e432c42` | `assessment: 未分级 ≠ 0.25（缺失值不参与加权，也不凭空抬高）` | §提案二 |

两个提案相互独立，可分别接受或拒绝。以下按"问题 → 证据 → 变更 → 行为变更与兼容性 → 已知限制 → 待决问题"组织。

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
