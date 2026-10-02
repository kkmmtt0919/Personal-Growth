# 架构决策记录

> 记录**已经决定的**与**仍待决定的**事项。决定一旦落定，除非有新证据不轻易推翻；如推翻，追加记录而非删除。
>
> 状态：**Q1–Q4 已于 2026-10-01 由用户确认**；D1–D8 随之生效。M1 已解锁。

---

## 已确认决策（Q1–Q4，2026-10-01 用户确认）

### Q1 · evkg 集成方式 → **独立仓库 + path 依赖** ✅

**决定**：evkg 保留在 `D:\projects\evkg` 作为独立仓库；Growth OS 用 `uv` 的 editable path 依赖引入。

```toml
# pyproject.toml
[tool.uv.sources]
evkg = { path = "../evkg", editable = true }
```

**架构约束**：`evkg` 只允许在 `backend/growth_os/evidence/adapter.py` 中被 import；其余代码一律通过适配层。这样耦合风险被限制在单文件。

**理由**：已实测确认 evkg 的词表、prompt、来源分级、切分规则全部可在 YAML 领域包层覆盖（`config.py` 的 `Profile` 模型），MVP 大概率不需要改其源码。保持上游可同步，避免分叉 —— evkg 的定位就是"通用证据图谱"，Growth OS 只是它的一个领域包消费者。

**发布前动作**：`0.1.0` 前必须把 path 依赖改为 pin 到具体 commit SHA，并记录于 `PROJECT_VERSIONS.md`。

**放弃的选项**：vendor 进本仓库（与上游分叉、失去同步能力）；git 依赖 pin commit（开发期迭代太慢）。

---

### Q2 · LLM 模型 → **GLM 主模型 + 独立 verifier** ✅

**决定**：

- 主模型沿用 `openai_compatible` + `open.bigmodel.cn` + `glm-5.3`（与 evkg 现有配置一致）
- **另配一个不同的模型作为独立 verifier**（`EVKG_VERIFIER_*`），用于攻击环节的逐条复核与对抗裁决

**理由**：evkg 的 `verifier_gateway()` 返回的第二个布尔值就是"复核模型是否独立"。若抽取与攻击用同一模型，等于自己审自己，而 PRD §10 的能力判定质量直接取决于攻击质量。

**已知陷阱**：evkg 仓库自带的 `.env.example` 写的是 `EVKG_VERIFIER_PROVIDER`，**这是错的** —— 代码实际读取 `EVKG_VERIFIER_LLM_PROVIDER`（`attack/verifier.py:39-40` 的 `env(f"VERIFIER_{suffix}")`，suffix 为 `LLM_PROVIDER`）。照抄那个名字会导致复核模型静默失效。本项目的 `.env.example` 已使用正确名称，并建议向上游提 fix。

**模型分层**：`EVKG_*` 用于 evkg 流水线（批量抽取、攻击），可用较便宜的模型；`GROWTH_AGENT_*` 用于 Growth OS Agent 推理（目标澄清、能力审计、成长建议），可用更强的模型；后者留空则回落到前者。

---

### Q3 · 前端技术栈 → **React + Vite + TypeScript** ✅

**决定**：React + Vite + TS；图谱可视化用 Cytoscape；运行时 `Node 24.15.0`。

**理由**：与 evkg 的 `frontend/` 方案一致，可直接借鉴其已有的 Cytoscape 图谱实现，减少 M8 工作量。

**放弃的选项**：Next.js（MVP 是登录后应用，SSR 收益有限）；Jinja2 + HTMX（交互式图谱与聊天体验受限）。

---

### Q4 · 多用户 / 登录 → **单用户本地优先** ✅

**决定**：MVP 不做登录与权限体系；但**所有表带 `user_id`**，为将来留位。

**理由**：PRD §17 强调"允许低数据量启动"；多用户会把精力吸到权限、会话、隔离上，而这些不影响 PRD §33 的 6 条成功标准。表结构已预留 `user_id`，迁移成本可控。

**已记录的代价**：evkg 侧目前没有用户概念（`Source` 无 user_id，只有自由 `metadata`）。将来要做多用户，需按用户分库或在 `metadata` 上打标。选此项时该代价被推迟，不属于 MVP 范围。

---

## 架构决策（D1–D8，已生效）

### D1 · 证据层复用 evkg，只在一个文件里 import

**决定**：Growth OS 通过 `backend/growth_os/evidence/adapter.py` 这一个适配层访问 evkg，其余代码不得直接 import evkg。

**理由**：evkg 是 0.1.0 版本、无 library 契约、raw SQL 分散在 `web/queries/dossier/audit` 等模块。把耦合收敛到单文件，将来若需替换或升级，改动面可控。

### D2 · 单 SQLite，双表族

**决定**：一个 SQLite 文件（WAL），evkg 表族 + Growth OS 的 `g_` 前缀表族共存。跨表族引用（`claim_id` / `source_id`）由应用层保证。

**理由**：PRD §27 明确单 SQLite 思路；evkg 建表全部是 `CREATE TABLE IF NOT EXISTS`（`store.py:40-95`），幂等可叠加，无外键约束，物理共存无冲突。避免为了 MVP 引入 Postgres / Neo4j。

### D3 · 复用 evkg 的 ModelGateway，不引入第二个网关

**决定**：`from evkg.model_gateway import ModelGateway`，用显式 `overrides={...}` 传入 Growth OS 自己的配置。

**理由**：已支持 Anthropic + OpenAI 兼容 + 第二验证模型 + 重试/超时/结构化输出。用 overrides 而非环境变量，是为了避开 evkg 的进程级全局配置（`config._ACTIVE`）串扰。

### D4 · Agent 运行时自建，不用框架

**决定**：自建薄运行时（`AgentRuntime` + `ToolRegistry` + `ContextAssembler` + `Tracer`），不引入 LangGraph / AutoGen / CrewAI。

**理由**：① PRD §29 只要 3 个逻辑 Agent；② PRD §33 把 Evaluation 列为成功标准，自建才能产出可评估的完整轨迹；③ 避免框架锁死与隐藏行为。

**代价**：需自己处理工具调用的解析与循环收敛。可接受 —— `ModelGateway.structured()` 已解决"约束式 JSON 输出"。

### D5 · 证据来源采用"双轨记录"

**决定**：粗粒度 `Source.kind`（6 个固定值，驱动 evkg 的 confidence）+ 细粒度 `Source.metadata.growth_evidence_type`（驱动 Growth OS 的星级规则）。另加 `metadata.growth_channel` 区分 `user_evidence` / `domain_reference`。

**理由**：**已实测确认** `SourceKind` 是封闭 StrEnum（`domain.py:10-16`），且 `assess_source` 用 `_policy_table()[kind]` 直接索引（`policies.py:28`），传入未知 kind 会 KeyError。因此不能新增来源类型。双轨方案零改动达成目标。

**详见**：`ARCHITECTURE.md` §3.3、§3.4。

### D6 · 能力星级不由 confidence 线性映射

**决定**：`assessment.level` 由证据层级规则（知识 + 行为 + 实践 + 任务 − 反向证据）计算，`confidence` 只作为"该证据是否采信"的门槛。

**理由**：两者语义不同。线性映射会让"高可信来源支撑的简单断言"拿到高星级，也会让"多条弱来源互相印证"伪装成高能力 —— 后者正是 PRD 第 4 节问题三要防的。

**必须被 G3 的 A/B 对照实验证明**（见 `ACCEPTANCE_GATES.md`）。

### D7 · GitHub 接入用 OAuth App + 最小权限

**决定**：OAuth App，MVP 只申请读取公开仓库所需的最小 scope；token 只以引用形式存 `g_integrations`，不落明文。

**理由**：PRD §7.3 明确"最小权限原则""不要求密码""不默认使用 SSH Key"。私有仓库留待后续用 GitHub App 细粒度授权。

### D8 · 验收证据本身走 evkg 证据链

**决定**：项目验收用独立的 `data/acceptance.db` + `growth_acceptance.yaml` profile，把验收结论作为 claim、把测试输出/截图作为 evidence、跑 attack、产出 dossier 作为验收档案。**与用户证据库物理隔离。**

**理由**：① 让"我们做完了"这个断言也可审计，符合 project-to-act 的完成门契约；② 在 M1 阶段顺带加压测试 evkg 全链路。

---

## 决策变更日志

| 日期 | 编号 | 变化 | 原因 | 影响 |
|---|---|---|---|---|
| 2026-10-01 | D1–D8 | 初次拟定 | 架构规划 | 待用户确认 |
| 2026-10-01 | Q1–Q4 | 提出 | 阻塞 M1 开工 | — |
| 2026-10-01 | Q1–Q4 | **全部确认，采纳推荐方案** | 用户决策 | M1 解锁；D1/D2/D3/D4/D6 随之确定 |

---

## 附：M1 spike 待验证清单

进度随 M1 各小步更新（证据见 `PROJECT_ACCEPTANCE.md` 的 EV-004）：

- [~] R1：evkg 的模块级函数能否稳定地被外部调用？ —— **ingest 段与代码路径已验证**（EV-006/007/009/010/012：`ingest_file`、`ingest_code_file`、`split_code_passages`、`stable_id`、`assess_source`、`KnowledgeStore` 均可用，`audit_store` 在适配层写入后仍 pass）。`extract_corpus` / `run_attack` / `write_dossier` 待 M1-c…M1-e
- [x] R2：`Source.metadata` 能无损携带成长标签，**且能按 metadata 做 SQL 过滤** —— **已闭环**（EV-006/007）。用 `json_extract(payload,'$.metadata.growth_channel')` 过滤可精确区分 `user_evidence`(2) 与 `domain_reference`(1)。sources 表尚无该路径的表达式索引，走全表扫描；证据量小时可接受，量级上来需补索引
- [x] R3：6 个 source kind 的语义重映射机制成立 —— **已验证**（EV-004），且 b.5a 起代码有了专属 kind（`SourceKind.CODE`），不再需要把源码硬塞进文本路径。**陷阱仍在**：profile 里写自定义 kind 不报错，会被静默忽略（`policies.py:22` 的 `except ValueError: continue`），因此细粒度证据类型仍必须走 `Source.metadata.growth_evidence_type`
- [ ] R4：evkg 的进程级全局 profile（`config._ACTIVE`）在单进程服务中是否会造成串扰？ —— **风险已具象化**：`_policy_table()` 与 `code_language_for()` 都读 `active()` 进程全局状态，同一进程内两个领域包/两个用户库无法并存。MVP 单用户单库可接受；多用户阶段必须每库独立进程或改造上游（M1-g 收口）
- [x] D1 结论：evkg 是"直接依赖可用"还是"必须改上游"？ —— **结论已修正为"需要改上游，但改法成立"**。D1 当初预测"MVP 大概率不需要改 evkg 源码"，**该预测被 M1-b 证伪**：pipeline 丢 kind、`_put` 用 `INSERT OR IGNORE`、`normalize_document` 破坏行结构，三处都必须动上游。但 D1 的**决策**（不 fork、改动作为上游 commit）成立且已被执行 —— b.5a 即为上游 commit `a4b15af`。这正说明"先把 M1 排在一切之前"的排序是对的：用最小成本证伪了假设

### M1-a 新增发现

- `uv` 的 path 依赖解析正常：`evkg==0.1.0 (from file:///D:/projects/evkg)`，editable 模式可用（EV-005）
- evkg 的 `ingest` 快路径只接受 `.txt/.md/.markdown/.text/.csv/.json/.log`；**PDF/docx/xlsx 必须走 V1 `--service` 状态机**（且 PDF 需 `evkg[office]`）。M3 做 Upload 时必须据此选择路径
- `_load_cached` 是 `lru_cache(maxsize=8)` 按路径字符串缓存；`load_profile` 会先看 `Path(name).exists()`，所以传绝对路径最稳，传相对路径依赖 cwd

### M1-b 新增发现（三处必须"绕开"上游的行为）

1. **V1 `IngestionService` 不能用于成长证据**：`pipeline.py:221` 的 `_save_source_passages` 把
   `kind=SourceKind.UNKNOWN` **硬编码**，且只写 `metadata={ingestion_job_id, completeness_pending}`，
   **不写 `metadata.assessment`**。后果：经此路径入库的代码/项目证据，其 claim 置信度会永远按
   "未知来源 0.25" 计权 —— 与"代码是最强证据"的产品目标完全相反。
   → **b.5a 已改进该函数签名**（kind 可传、默认仍 UNKNOWN），但状态机路径仍未打通，见 M1-b.5a 第 1 条。
2. **`_put` 对 sources 是 `INSERT OR IGNORE`**（`store.py:124`），不是 `REPLACE`。
   所以"先落库、再改 metadata 重存"会被**静默忽略**（不报错）。
   → 暂以 `json_set` 定向 SQL 修补；**正式修复在 b.5c**（显式 upsert）。
3. **`extract.py:105-106` 依赖 `source.metadata["assessment"]`**。
   任何整体替换 metadata 的写法都会抹掉它，使 `preliminary_claim_confidence`
   落回 default=0.25，**静默**退化整条置信度链路。
   → b.5a 用 `json_set` 合并规避；**语义层修复在 b.5b**（`UNASSESSED` 不等于 0.25）。
4. `ingest_file` 内处理 `.html` 的分支是**死代码**：`.html/.htm` 不在 `TEXT_SUFFIXES` 里，
   函数在第 71 行就抛错了，第 88-92 行的 BeautifulSoup 分支永不可达。HTML 实际由
   `IngestionService` 的 `HtmlReader` 处理。
5. `PlainTextReader.accepts` **同时按 `media_type.startswith("text/")` 判断**
   （`providers.py:31`）—— 它把"我是不是纯文本"与"我支持哪些类型"用 `or` 混成一个判断。
   这是 b.5a 必须把 `CodeReader` 排在它之前的原因；更彻底的清理（拆分 capability 判定）
   尚未做。

### M1-b.5a 新增发现

1. **`normalize_document` 会摧毁代码的行结构**（`cleaning.py:9-30`）。实测一份 8 行、
   带缩进的 Java 片段经归一化后变成 3 行、缩进全失：
   `'public class A { private int x;\n\npublic int get() { return x; } }'`。
   原因有三：`re.sub(r"[ \t]+", " ", text)` 压平缩进、`re.sub(r"\n{3,}", "\n\n", text)`
   合并空行、以及把每段的行用 `" "` join 成一行。
   **后果**：`_save_source_passages` 切的是 `document.text`（归一化后），所以在 V1 状态机
   路径上算出来的行号是**虚构的**。
   → **决策：`ingest_code_file` 刻意不经状态机**，在原始文件文本上切分，因此 locator 可回
   磁盘逐字核对（EV-012 已证）。
   **要打通状态机，必须先让归一化对代码无损**，而 completeness 的史学期维度
   （作者/地点/事件）对代码是纯噪音 —— 两件事都还没做，不在 b.5a 范围。
2. **passage id 把切分方案编进了哈希**（`stable_id("p", f"{source_id}:{index}:{part}")` 对文本，
   `f"{source_id}:{start}:{end}:{body}"` 对代码），加上 `INSERT OR IGNORE`，导致
   **更换切分器后旧 passage 既不被替换也不被删除，只会静默累积**。
   实测：一个源里混进了 11 条被文本切分器撕裂的旧片段（如
   `'= null) { List<VectorSearchResult> vecto'`，从表达式中间开始）。
   **后果**：M1-c 会对这些垃圾片段做抽取，既产出无意义断言又虚增证据计数。
   → **该问题正式移入 b.5c**。b.5a 期间以显式重建证据库处理（有备份），
   **刻意不在适配层加"重入库前先删旧 passage"的补丁** —— 那正是"用业务适配层修补
   evkg 领域模型"的反模式，用户已明确要求刹住。
3. **切分器经三轮实测修正才正确**，每一轮都由具体失败驱动：
   - 第 1 版按"与 chunk 起点比缩进"→ 类成员全被并成一块（50 行）
   - 第 2 版改为"与上一个块比"→ 方法可分离，但块缩进取首行导致 `}` 之后的退格边界不可见
   - 第 3 版块缩进取**块内最小值** + **退格到主体层才切** → 又出现大量仅含 `}` 的片段
   - 第 4 版合并小同缩进块时按**合并后总行数**设上限 → 收敛
   最终在 RagService.java（79 行）上：9 段 / 最大 25 行 / 仅括号噪声 0 条 / 说谎 locator 0 条。
   结论：**没有解析器就无法做到 symbol 级精度，这是硬边界**；类的第一个成员仍会与类声明
   合并，已作为已知限制写进测试注释。
4. **`source_id` 方案的既有不一致**：快路径是 `stable_id("src", 文件绝对 URI)`（路径相关），
   V1 状态机是 `src_<content_hash[:20]>`（内容相关）。同一文件经两条路径会得到两个 source。
   → b.5a 让每种格式确定性只走一条路由；**统一方案在 b.5c**。
5. **无扩展名文件曾被我遗漏**：`Dockerfile`/`Makefile` 这类文件的 `Path(...).suffix` 为空串。
   b.5a 在 `CodeConfig.filenames` 里补了按小写文件名匹配的表，否则删掉旧的适配层兜底路由
   会造成能力回退（已加测试）。

### M1-b.5b 新增发现与设计决定

1. **缺失值必须双向设防。** 用户最初指出的是"未评估 ≠ 低分"，但实施时确认反过来同样致命：
   若把缺失兜底成**高分**，未经核验的自述/README 自声明就能靠"未评估"这条通道获得可信度。
   因此最终语义是「缺失不带数字」而不是「缺失换成另一个默认值」：
   `score=None` + `assessment_status='unassessed'`。
   对照测试在抽取质量 0.99 时仍断言 `score is None`。
2. **按 `kind` 推导 ≠ 发明数字。** `assess_source(kind)` 是同一份策略表的**确定性函数**，
   所以"没缓存分级"时按 kind 推导得到的是正确先验，而不是猜测。旧实现用固定 0.25 兜底，
   实测让一个 `code` 来源（策略表 0.80）被按 0.25 计权 —— **同源同内容仅因缓存有无差 0.55，
   且全程静默**。修复后差 0.00。
   为可审计，分级的 `origin` 如实标出来源：`cached` / `derived_from_kind` / `missing_source`
   / `missing_kind`。**"只用了类型先验"与"逐来源评估过"必须可区分。**
3. **`SourceKind.UNKNOWN` 的先验保持不变**（0.25，`status=assessed`）。
   按用户要求，它与 `unassessed` 是两种状态，测试成对锁定。
4. **未新建 claim 生命周期**（遵守用户指令）。`ASSESSED`/`UNASSESSED` 两个常量只描述
   **分级取值的形状**（有没有数字），claim 仍沿用既有 `ClaimStatus`：来源未分级时
   claim 记为 `DISPUTED`（不予采信），并在 `metadata.assessment_status` 单独标注，
   以免与"证据被反驳"混淆。
5. **`score` 可空的影响面已逐一核实**，改动前就识别出 6 个消费者，改动后逐个验证
   （EV-015）：`extract` 构造、`store.save_claim` 写 `relations.confidence` 列（接受 NULL）、
   `dossier` 渲染、`index/search` 与 `web` 的 `ORDER BY json_extract(confidence.score)`
   （NULL 在 DESC 下排最后，安全）、`adversarial` 的筛选排序（新增模块级 `claim_score()`
   守卫）、`audit_store` 不变量。
6. **`adversarial` 的 None 守卫只用于排序**：未分级按 0 参与筛选与排序，避免
   `None` 比较抛错、也避免未分级 claim 被当作高置信目标优先攻击；这**不代表**给它评了 0 分，
   其 `assessment_status` 仍是 `unassessed`。已在注释和测试中写明，防止后人误读。
7. **测试按"先写后改"执行**（用户指定顺序）。改动前新测试以 `ImportError` 失败，
   但这只证明函数缺失、不能证明旧行为有错，因此另外用一个实证脚本把旧行为
   （`0.25` vs 应有的 `0.80`，差 0.55）单独留证，见 EV-014。

### M1-b.5c 新增发现与设计决定

1. **我自己踩了用户警告过的那个坑。** `save_source` 的更新分支复用了 `_put`，而
   `_put` 对 sources 是 `INSERT OR IGNORE` —— 于是 `save_source` 报 `updated`，
   **库里却仍是旧值**（调试脚本显示第 4 次调用仍读到 `h1`）。
   这正是 b.5b 里我判定为"危险状态"的同一类问题，说明"只在调用点小心"不可靠。
   → 把 `_put` 对 sources 改成真 upsert（`ON CONFLICT(id) DO UPDATE`），**从根上
   消除这个 helper 的陷阱**，而不是在更新分支绕开它。
2. **`content_hash` 不能用磁盘原始字节。** 两个理由：
   * 我引入的不一致：manifest 路径早已按规范化文本取哈希，而快路径按原始字节，
     两条路径对同一内容会得出不同哈希；
   * 实际危害：一次 `git checkout` 把 CRLF 换成 LF，所有来源都会被判成"内容已变"
     并触发整轮重新抽取，而文本一字未改。
   → 定一个可检验的契约：**`content_hash` 相同 ⟺ 段落所依据的文本相同**，
   实现为对换行规范化后的文本取哈希。并明确它与 `RawAsset.content_hash`
   （原始字节，服务任务去重与资产寻址）**不是同一个值**，不要互相比较。
3. **`read_bytes().decode()` 不做换行翻译。** 我从 `read_text()` 改为读字节后，
   Windows 上 CRLF 文件的每行行尾多出 `\r`，混进 passage 文本，**直接让 locator
   回原文的逐字校验失败**（被 b.5a 的既有测试当场抓到）。这不是测试太严，而是
   真实退化：`\r` 会污染抽取与引文比对。
   → 新增 `decode_text()` 显式统一换行。由此确立一条语义：**locator 的行号是相对
   换行规范化后的文本而言的**，与 git 惯例一致（规范化后行数不会因 CRLF 翻倍）。
4. **删除 passage 必须级联，否则会留下一个自己审计不过的库。** 实测：只删 passage
   会同时点亮四条不变量 —— `evidence_missing_passage`、`claims_without_evidence`
   （删掉 evidence 后）、`events_missing_passage`、`ledger_complete_passage_missing`。
   而且级联是**语义正确**的：原文已经不在了，依赖它的证据与失去全部证据的主张
   都失去了依据，留着就是无依据的断言。
   → 新增 `purge_passages()`，顺序为 evidence → 孤儿 claim 及其 relation →
   幸存 claim 的 `passage_ids` 剪除 → events 及其派生的 timeline/place →
   抽取账本 → entity_aliases → passages。**并返回各表清理数量**：级联删除是真实的
   数据损失，必须让调用方看见，不能悄悄发生。
5. **`access_date` 语义被钉死为"首次落库时间"**，且不参与变更判定。否则重复
   ingest 相同内容会刷新它，每次都判成 `updated`，`unchanged` 永远不可达。
   （这也与旧行为一致：旧实现是 `INSERT OR IGNORE`，本就"首次写入生效"。）
6. **"整体替换段落集合"作为默认语义**。所有既有调用方（快路径、状态机、manifest）
   本来就一次传入某来源的完整集合，因此默认 `replace_source=True` 不改变它们的
   行为；而它正是"段落不得静默累积"的实现。空集合无法推断来源，故不删除（已文档化）。
7. **manifest 的 Wiki 词条身份显式传入**。它的身份是「api + 页名」复合键，不是路径
   也不是 URL，若走 `logical_source_id` 的路径分支会得到完全不同的 id，且会让
   既有的 pending 判定失效 —— 因此改为显式传 `source_id`。
8. **同一文件经快路径与经状态机现在得到同一个 `source_id`**（旧实现是两套方案：
   路径式 vs 内容式）。这是逻辑身份的顺带收益，也是"下游引用稳定"的前提。

### M1-b.5d 新增发现与设计决定

1. **删掉"补丁"的前提是上游提供了等价能力，而不是下游变得更小心。**
   b.5d 的目标不是"重构 adapter"，而是**证明 Growth OS 不再需要知道 evkg 内部存储细节**。
   为此先在 evkg 补了两个公共入口，下游才可能真正删干净：
   * `ingest_path()` —— 按内容类型自动路由。此前适配层必须自己判后缀、自己决定调用
     `ingest_file` 还是 `ingest_code_file`，等于把 `TEXT_SUFFIXES` 与 `CodeConfig.languages`
     复制了一份到下游。
   * `find_sources(metadata=...)` —— 按标签检索。此前适配层只能对 `sources.payload`
     写 `json_extract` 裸 SQL。
   加上 b.5c 的 metadata 合并语义与 `ingest_path(..., metadata=...)` 的透传，适配层的
   `_tag_source`（`json_set` 改 payload）才有存在理由消失。
2. **`IngestResult.route` 被删除。** 它暴露的是 evkg 的实现路由（"走了哪个函数"），
   属于实现细节；而 `kind == "code"` 已经表达了同一事实，且是**领域可见**的语义。
   保留 `route` 就等于在适配层 API 上固化上游的内部结构。
3. **边界检查做成静态 AST 检查，而不是靠约定。** 理由是实证的：M1-b.5c 期间我自己就
   复用了 `INSERT OR IGNORE` 的 helper，导致 `save_source` 报 `updated` 而库里是旧值 ——
   说明"写的时候小心"守不住这类约束。检查内容：可执行代码（先剥 docstring）中不得出现
   `sqlite3` / `.db.execute` / `.db.commit` / `json_set` / `json_extract` / 内联 SQL 关键字 /
   下划线成员；只允许导入 evkg 的公共模块；不得调用 store 低层方法；不得再有私有辅助函数。
4. **检查最初误报了文档字符串。** 第一版按行匹配，把适配层文档里"**不**写任何裸 SQL、
   不使用 `sqlite3`"这类**说明性文字**当成了违规。修正方式是用 AST 剥掉 docstring 后
   `ast.unparse` 重新生成代码再匹配 —— 只检查可执行代码。记录此事是因为它说明
   "静态检查"本身也需要被验证，否则会逼着作者把解释性文字删掉。

### 未决 / 留给后续

- **`purge_passages` 的两种模式（用户已确认方向，M4 之后再实现）**：
  当前是 **hard cleanup** —— 删除段落、级联删除失去全部证据的主张，保证
  「当前 Evidence Graph 不含已失效证据」。这对 M1 的目标是对的。
  但 M4 的攻击环节可能希望看到**历史**（"过去曾有一个 claim『召回率 92%』，
  依据是 README v1，后来代码更新、README 被改"）—— 那时删除就不够了。
  收敛方向（**现在不引入**）：

  ```
  purge mode
  ├── cleanup    （MVP 当前实现：硬清理）
  └── supersede  （审计历史：标记失效而非删除）
  ```

- **locator 的 invariant（用户已确认为必须保留的约束）**：

  > **locator 不只是位置描述，而必须能够重新定位到同一份证据文本。**

  即 locator 必须能无条件地把原文切回来并与 `passage.text` 逐字相等。
  这条是 b.5a 引入、由测试锁死的（`test_locators_are_truthful`、
  `test_code_locators_round_trip_to_original_file`）。
  它也解释了为什么 CRLF 污染必须修：若放任 `\r` 混进文本，就会出现
  "line_start 看起来对、passage 内容已被污染"的假绿 —— 对代码证据不可接受。

- **`RawAsset.content_hash` 与 `Source.content_hash` 的分工**（用户已确认为正确划分，
  必须保留）：

  ```
  RawAsset.content_hash = 原始字节哈希   → ingestion 层：这个输入资产是不是同一个字节文件
  Source.content_hash   = 规范化文本哈希 → evidence 层：影响证据理解的文本是否变化
  ```

  混用会让一次 `git checkout` 的换行变化触发全部来源重新抽取，造成大量无意义成本。

- **symbol 级代码精度**仍需解析器，b.5a 起即为明确的已知限制。
- **evkg 不得推送到 `redmaplewww/evkg`**（用户 2026-10-01 明确指示）。本地领先
  远程 3 个提交。改动提案见 `docs/UPSTREAM-evkg-commits.md`（已含三个提交的完整链）。
