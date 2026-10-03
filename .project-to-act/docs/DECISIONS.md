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

**交付形式补充（B-g1，2026-10-02 用户确认）**：本地 Git bundle 归档（方案 A）+ 裸仓寻址；
维持"不推送 `redmaplewww/evkg`"约束；私有镜像（方案 B）暂缓，多机/CI 确有需要时再升级。
已执行：`D:\projects\_evkg-archive\evkg-28afbc0.bundle`（+ C: 第二副本），SHA-256
`10dafff4…3801`，commit `28afbc0`，`git bundle verify`/克隆/fsck 全部通过（EV-049）。
开发期保留 path 依赖（editable 循环）；**发布/CI 前切换为 `git + rev`** —— 该 pin 方式
已在 uv 层实测（`uv lock` 记录 URL+rev）；注意 `editable` 与 `git` 源互斥。

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
| 2026-10-02 | D1（依赖策略） | **由"需要改上游，但改法成立"细化为"有条件依赖（C1–C5）"** | M1-g 实测：当前调用面可用但整体不可直接依赖（双实例污染、抽取模型名缺失、渲染器丢 partial） | 不 fork 的决策不变；新增 5 个使用条件与 2 项阻塞（B-g1/B-g2）；M1 spike 结束 |
| 2026-10-02 | B-g1 / Q1 补充 | **evkg 交付形式 = 本地 Git bundle 归档（方案 A）**；维持不推送约束；外部私有镜像暂缓 | 用户确认：bundle 满足可获取/可校验/可复现且零授权；实测 bundle 字节可复现、uv `git + rev` pin 成立（`editable` 与 `git` 互斥） | 已执行归档 + 双副本 + 恢复验证（EV-049）；开发期保留 path 依赖，发布/CI 前切换 `git + rev`；M1 正式归档 |

---

## 附：M1 spike 待验证清单

进度随 M1 各小步更新（证据见 `PROJECT_ACCEPTANCE.md` 的 EV-004）：

- [x] R1：evkg 的模块级函数能否稳定地被外部调用？ —— **已闭环（M1-g）**。ingest 段与代码路径此前已验证；M1-c…M1-e 又验证了 `extract_corpus` / `run_attack` / `write_dossier` 的真实运行，M1-g 复跑全量测试（evkg 101 正/逆序 + 本仓 73）并界定未验证面：V1 富格式（PDF/docx/xlsx）路径 0 端到端验证、index/web/cli 未使用。结论：**当前调用面稳定可用；未使用面不纳入结论**
- [x] R2：`Source.metadata` 能无损携带成长标签，**且能按 metadata 做 SQL 过滤** —— **已闭环**（EV-006/007）。用 `json_extract(payload,'$.metadata.growth_channel')` 过滤可精确区分 `user_evidence`(2) 与 `domain_reference`(1)；b.5d 起改走公共 API `find_sources(metadata=...)`，适配层不再写裸 SQL。sources 表尚无该路径的表达式索引，走全表扫描；证据量小时可接受，量级上来需补索引
- [x] R3：6 个 source kind 的语义重映射机制成立 —— **已验证**（EV-004），且 b.5a 起代码有了专属 kind（`SourceKind.CODE`），不再需要把源码硬塞进文本路径。**陷阱仍在**：profile 里写自定义 kind 不报错，会被静默忽略（`policies.py:22` 的 `except ValueError: continue`），因此细粒度证据类型仍必须走 `Source.metadata.growth_evidence_type`
- [x] R4：evkg 的进程级全局 profile（`config._ACTIVE`）在单进程服务中是否会造成串扰？ —— **已闭环（M1-g 实测，不是推定）**：EV-043 用两个探针领域包 × 两个独立 DB 实测确认 —— profile 是模块级→进程级全局；storeA 在 B 激活后（不重新激活 A）再入库同一文件，段落由 4 变 2（同 `source_id`，被 B 的规则替换）；asyncio 强制交错下任务 A 也按 B 入库；实例挂 `profile` 属性被忽略；**per-call `activate` + try/finally 只能顺序隔离，并发隔离无公开 API，必须改上游**。另实测适配层 footgun：未 `configure()` 时静默按 evkg 默认领域包入库。当前单 profile 用法不受影响
- [x] D1 结论：evkg 是"直接依赖可用"还是"必须改上游"？ —— **最终结论（M1-g）：两者都不是，判定为"有条件依赖"**。D1 当初预测"MVP 大概率不需要改 evkg 源码"，该预测被 M1-b 证伪并已用 4 个上游提交修正（见 §2.2 的提交链）。M1-g 进一步确认：当前调用面端到端可用，但**整体不可直接依赖**（双实例污染、抽取模型名未持久化、上游渲染器丢 `partial`、无参 `KnowledgeStore()` TypeError、`.env.example` 变量名错误），也不到"必须改上游才能用"的程度 —— 以 C1–C5 五个条件约束使用（详见 `M1-SPIKE-CONCLUSION.md` §6.3）。D1 的决策（不 fork、改动作为上游 commit）继续成立

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

### M1-c 新增发现

1. **★ 抽取器正确地拒绝把项目成果归因为个人能力 —— 而这个"正确的拒绝"暴露了缺失的一层。**
   109 条 passage（含 57 条项目 README、9 条源码、43 条领域参考）只产出 **2 条**能力断言。
   其中一条的陈述是模型自己写的：

   > 「原文（README）描述的项目 MYtest 中实现了 RAG 检索服务…；**但未明确用户本人在项目中的
   > 具体角色与贡献，能力主张仅基于项目描述本身**。」

   这正是成长领域包里「不作能力推断」那条规则在起作用（b.5a 写入）。但它的后果是：
   **项目产物（README / 源码）无法自动变成"用户的能力证据"，除非先建立归属** ——
   "这份仓库确实出自用户"。

   **正确做法**：归属不该由 LLM 去推断（那会把"项目用了 RAG"变成"用户会 RAG"，
   正是 PRD 第 4 节问题三要防的），而应作为**证据层的显式、可审计决定**：
   `growth_evidence_type=repo_artifact` + `growth_channel=user_evidence` 这一组合本身
   就已经表达了"这是用户交给系统的一份仓库产物"。这是 ARCHITECTURE §3 那条 L1/L2 边界的
   又一体现 —— **LLM 只负责"文本说了什么"，Growth OS 负责"这对用户意味着什么"**。
   M3 的 GitHub 授权动作会天然提供归属（用户选择授权哪个仓库 = 归属声明）。

   **未决**：归属规则的具体形式（是否需要在 `metadata` 里显式记一条
   `attribution: user_provided`，以及它如何参与 M4 的评级）留待 M2/M4 决策。

2. **「严禁升级」规则验证通过。** README 的「未来规划」是未勾选 TODO 清单，被抽成
   `用户 | 计划学习 | Dubbo、gRPC 协议…`，且陈述明写"仅为计划事项，不代表已具备相应能力"。
   predicate 没有被升级成"具备能力"。这是 M1-c 最重要的单点验证。

3. **2 条主张对演示成长闭环偏薄。** 原因不是抽取失败，而是现有材料以"项目介绍"为主。
   按证据强度阶梯，能承载"用户能力"的材料是任务提交（`task_submission`）、
   现场作答（`probe_result`）、对话自述（`chat_assertion`）—— 这些是 M5 任务闭环自产的。
   **M4 的 G3 对照实验必须自造这类材料**，不能指望一个项目 README。

4. **evkg 自带 `.env.example` 对它的默认模型是无效的**（两处）：
   * 同时设置 `EVKG_REASONING_EFFORT=none` 与 `EXTRA_BODY={"thinking":{"type":"disabled"}}`，
     而 `glm-5.3` 实测返回 `400 code 1210: 该模型始终思考，不支持关闭思考；请使用 low、high 或 max`。
     → 改为 `EVKG_REASONING_EFFORT=low` 可用。
   * `EVKG_EXTRA_BODY={"thinking":{"type":"disabled"}}` 是**裸写**的，标准 dotenv 解析器
     （如 `uv --env-file`）会剥掉内部双引号，得到 `{thinking:{type:disabled}}`，
     `json.loads` 直接失败。必须整体加单引号。
   这是该文件第三处问题（前两处：`EVKG_VERIFIER_PROVIDER` 变量名错误、本次两处），
   建议在上游一并修正。

### M1-d 新增发现

1. **★ 独立复核真的起作用了，而且推翻了一条越权主张。** 抽取器以自评 0.35 产出
   「用户 | 实现过 | RAG 检索服务」。独立复核（`deepseek-flash`）给出
   polarity=`partial`、置信度 **0.17**；对抗红队两次裁决均为 **`broken`**，理由：

   > 「主张将项目存在等同于用户个人实现，**加入了原文没有的信息（用户角色与贡献）**。
   > 攻击质疑成立，且无任何直接证据（如提交记录、署名、可运行产物）支持用户独立完成。」

   `missing_evidence` 明确列出缺失项。最终该主张 `disputed` / 0.17。
   **同一次攻击保住了**另一条措辞正确的主张：红队质疑「这只是计划，没有开始学习的证据」，
   裁决为 `sustained`，理由是"主张本身不声称已具备能力，缺失实践证据不削弱它；
   未勾选状态反而是支持『未完成』的反向证据"。
   → 这是 PRD §33 第 3 条（识别"用户说自己会但证据不足"）的**首次实证**，
   也是 M4/G3 的前身。红队质疑直接落实了 PRD §8 的清单（是否只是自述、是否只是调现成 API、
   有无独立设计、有无可运行产物）。

2. **两个"独立"概念必须分开记，否则会在 M4/G3 里被误读**：

   | 名称 | 位置 | 本次取值 | 含义 |
   |---|---|---|---|
   | `independent_verifier` | claim.metadata | **True** | **复核模型**与抽取模型不同（真正独立） |
   | `evidence.independent_source` | evidence 行 | False | 该主张的证据是否跨**多个来源** |

   两者都叫 "independent" 但毫不相关：前者衡量复核机制，后者衡量证据的互证程度。
   本次两条主张都只引用一个来源，故 `independent_source=False` —— 这是**正确的**，
   不应与"复核不独立"混淆。

3. **`independent=True` 不足以证明模型独立**（用户指出，实测确认）。
   `verifier_gateway()` 返回的布尔值只表示"有没有设置 overrides"，
   **不比对模型是否真的不同** —— 把 `EVKG_VERIFIER_MODEL` 设成与主模型同名也会得到 True。
   因此核实时必须同时检查解析后的模型名与 base_url（`artifacts/m1d/independence.json`
   即为此留档，并由 `genuinely_independent` 字段单独判定）。

4. **模型自称不能用来验证模型身份。** 实测问 `deepseek-flash`"你是谁"，它回答 `"ChatGPT"`。
   所以"配置了却没生效"这类问题**不能靠问模型**来排除，只能靠解析后的配置与接口返回元数据。

5. **`deterministic` 返回 `pending_model_review` 是正常状态**，不是错误或降级 ——
   它表示"规则扫描已生成冲突候选，等待模型复核"。本次该模块在 relation/statement/time/place
   四个维度上均未发现候选（两条主张主题不同，无同主谓异宾之类冲突）。

6. **本轮无降级复核**：独立性已核实，故 EV-030/031 的记录可作为**独立复核结果**使用，
   不需按用户要求的"非独立降级"方式标注。反之，若今后在未配 verifier 的机器上重跑，
   必须显式标注降级，且不得与本次结果混用。

### M1-e 新增发现

1. **★ evkg 自带的 `render_claim_markdown` 会漏掉 `partial` 极性的证据。**
   它只渲染 `dossier["supports"]` 与 `dossier["refutes"]` 两个列表
   （各由 `polarity == "supports"` / `"refutes"` 过滤），而 `partial` 会落在两者之外。
   实测本库里被推翻的那条主张证据分布是 `{'supports': 2, 'partial': 2}` ——
   **`partial` 正是独立复核的结论**，也就是关于该主张最重要的一条证据。
   若直接用它渲染，档案会把"复核认为只有部分支持"整段抹掉。
   → Growth OS 自建渲染器（`growth_os/evidence/dossier.py`）显式纳入所有极性，
   并加回归测试 `test_partial_polarity_evidence_is_rendered` 锁死。
   **该缺陷建议上报上游**（属渲染器 bug，不止影响本仓）。

2. **分数精度：档案用 3 位小数，不用 2 位。** 2 位会把库中的 0.697 显示成 0.70，
   读者拿档案与数据库对照时对不上 —— 对一个"可验收、可复核"的证据文档而言是失真。
   这条是核对脚本先报 FAIL 才发现的，说明"档案 ↔ 数据库一致性核对"本身是有价值的：
   它抓到了我自己的呈现缺陷，而不只是走一遍格式。

3. **抽取所用模型未入库，档案如实标注"未记录在案"。**
   `Claim.metadata` 只记了 `verifier_model`；抽取阶段的模型名没有被持久化。
   → 档案**不**用"当前配置值"冒充该次抽取的历史事实（那正是本档案反复强调的
   "不把推断写成事实"）。要根治需在抽取时把模型名写入 claim.metadata —— 属上游改进项。

4. **边界检查扩展到整个包，并当场抓到新代码。** D1 原本只在 `adapter.py` 上被检查。
   M1-e 新增 `dossier.py` 后，把检查扩为"整个 `growth_os` 包中只有 `adapter.py` 可 import evkg"，
   立刻报出我新加的 `evkg.evidence.dossier` 不在允许清单 —— 确认清单机制有效。
   `evkg.evidence` 是公开 API，已加入清单并写明"新增条目前必须先确认它是稳定公共入口"。

5. **档案的呈现纪律（用户要求，已写进模块文档与测试）**：
   不把模型判断写成已证实的客观事实；缺失证据 ≠ 造假；不把单条主张的状态外推为
   系统整体评估能力。三项都有对应测试。

### M1-f 新增发现

1. **内置 `run_damage_selftest` 有一个测量盲区，需要外部独立测量补上。**
   它把 **注入 → 审计 → 清理** 全放在一个函数里，`finally` 会立即删除注入行。
   因此在该函数返回之后再去数不变量违规条数，只能看到**已清理**的状态（0 条），
   **无法独立验证"注入期间确实产生了违规"** —— 只能采信它自报的 `caught`。
   → 为不依赖自述，另做两个**受控注入**（本脚本自己注入、自己前后测量、自己清理）：
   伪造引文 0→1、不存在的 passage_id 0→1，注入期间审计状态为 `fail`、样本点 named 注入行。
   内置自测自报的 `quote_violations_after_injection=1` 与受控测量的 0→1 **相互印证**。

2. **内置自测与用户指定的场景打的是不同不变量**，不能互相替代：

   | 场景 | 注入 | 触发的不变量 |
   |---|---|---|
   | evkg 内置 | 存在的 passage + **伪造引文** | `evidence_quote_not_in_passage`（引文保真） |
   | 用户指定 | **不存在的 passage_id** | `evidence_missing_passage`（引用完整性） |

   两者都跑了。这与"内置测试通过 ⇒ 数据一致性有保障"是不同的命题。

3. **`caught` 的判定依赖被截断的样本。** 内置测试用
   `evidence_id in report["checks"][...]["sample"]` 判定是否抓到，而 `sample` 只保留
   前 10 行。若库内本就有 ≥10 条同类违规，注入行可能落在样本之外而被误报为 `missed`；
   反之，若库本已因其他原因违规，也不会影响其判定。属**保守方向的脆弱**（可能漏报、
   不会虚报），本次库内该不变量为 0 条，故不触发。**建议上报上游**：应改为
   "违规条数是否增加"或直接按 id 查询，而不是依赖样本截断。

4. **清理完整性的判据必须排除 `audit_log`。** 审计流水本就应记录"发生过什么"，
   要求它复原等于要求"事后不留痕迹"。正确性质是：**除 `audit_log` 外表计数零差异**。
   这一点在脚本与测试里都已显式写明（测试里第一次断言包含了 audit_log 而失败，
   修正后语义才对）。

5. **注入在真实库的副本上执行**，并逐表核对真实库零差异。万一清理失败也不会污染
   真实证据；同时这也验证了"副本与真实库等价"这一前提（真实库本身未被写入）。

### M1-g 新增发现（技术 spike 收口，2026-10-02）

完整结论与证据见 `docs/M1-SPIKE-CONCLUSION.md`（EV-042…EV-046）。此处只记决策级要点：

1. **D1 特别检查（进程级全局 profile）已实测，不再是不确定性**：profile 是模块级 →
   进程级全局；两个不同配置的实例在同一进程内**不能**独立运行（同 `source_id` 的段落
   会被"最后一次 activate"的规则替换）；初始化顺序不起作用，"最后 activate"才起作用；
   实例挂属性无效；per-call `activate` + try/finally 可顺序隔离，**并发隔离必须改上游**。
   当前单 profile 用法不受影响，因此不阻塞，但写入条件 C1。
2. **适配层 footgun（本地可修）**：`ingest_document` 不校验 profile，绕过 `open_store`
   时会静默用 evkg 默认领域包（实测：5 段/默认理由 vs 2 段/成长理由，基线数值恰好同 0.68）。
   建议加 3 行断言。
3. **依赖策略 = 有条件依赖（C1–C5）**，写入 `PROJECT_ACCEPTANCE.md` 与结论文档：
   C1 单进程单领域包；C2 不用 evkg 的 `render_claim_markdown`；C3 发布前 pin commit；
   C4 QG2 用双向测量而非内置 `status` 单值；C5 M4 前解决抽取模型持久化。
4. **三项上游缺陷已复现并列入清单**：`partial` 渲染丢失（哨兵+阳性对照复现）、
   抽取模型名未持久化（对照：verifier 有记录、extractor 无）、`caught` 判定依赖前 10 行
   sample（预置 12 条违规 → `violations=13` 但 `status=missed`；干净库同代码 `caught`）。
5. **覆盖盲区的定性**：adapter 83.3% / dossier 96.1%，但 **LLM 路径无自动化测试**
   （extract 0%、verifier 18.2%）—— 抽取/攻击结论是"一次性真实运行已验证"，不是
   "持续验证"；V1 富格式路径（M3 的 PDF 上传）0 端到端验证，列为阻塞 B-g2。
6. **在案阻塞**：B-g1（evkg 本地领先远程 4 提交且不得推送 → 换机/CI 前必须决定可获取
   形式并 pin commit）；B-g2（M3 开工前富格式 spike）。
7. **M1 完成条件复核（自查发现缺口并补齐）**：ROADMAP M1 第 1 条含 `init → … → reindex`，
   而 R3 覆盖实测显示 cli（0%）与 index/search（0%）从未被跑过 —— 收口前补跑（EV-047）：
   `evkg init` 建 35 张 schema 表；`rebuild_index` = FTS5 模式、109 段落 + 2 主张入索引、
   重复重建幂等、索引后 audit 两轮均 pass、5 个真实词条 4 命中（`计划学习` 为 2 字词按设计
   回落 LIKE 且 predicate 不在索引字段 → 0 命中，记为检索边界）。**不把"没跑过的步骤"算作
   通过**；顺带发现 `KnowledgeStore` 无 `close()`/上下文管理器（Windows 锁文件）。
8. **M1 可正式归档**：完成条件 6/6 均有实际输出（EV-008/013/037/044/047 覆盖 audit、
   damage、metadata、dossier、reindex、结论文档）；交付物清单中 `scripts/smoke_evidence.py`
   实际落地为 `scripts/smoke_ingest.py` + 各步 artifacts 运行器（M1-b 起的既有偏差，
   功能等价，此处如实登记）。

### M2-a 新增发现与设计决定（2026-10-02）

1. **边界守卫的收窄必须带补偿**：M1 的"全包禁 sqlite3/裸 SQL"与 M2 自建 `g_` 表直接
   冲突。收窄为「证据层（`evidence/`）全禁 + `store/` 白名单」，并同时加三项补偿：
   静态守卫（`store/` 内 SQL 的表名必须全部 `g_` 前缀）、功能断言（M2 流程跑完后
   库中不得出现任何 evkg 表）、D1 导入边界继续对全包生效。**缺任何一项即为放宽边界。**
2. **网关接缝放在 Growth OS 一侧**：`agent/` 只依赖 `StructuredGateway` Protocol 与
   自己的 `GatewayResult`，evkg 的 `ModelResult` 由适配层转换 —— 否则 `agent/` 会被迫
   import evkg，违反 D1；这也让 fake gateway 离线回归（C3）成为可能。
3. **失败路径的记录也要有语义**：成功时 provider/model 取自返回值（实际生效，`result`）；
   失败时没有返回值，只能取当时配置并**显式标注** `config_on_error`。存储层用
   `model_source` 与 `status` 的匹配不变式把这条锁死（错配直接报错）。
4. **把上游缺陷变成自己的设计约束**：M1-g 记录 evkg `KnowledgeStore` 缺 `close()`
   导致 Windows 锁库（§7-10）。自有 `GrowthStore` 因此必须提供 `close()` 与上下文
   管理器，并有"关闭后可删除库文件"的回归测试。
5. **稳定身份规则复用 M1-b.5c 的教训**：能力点 id = hash(goal_id + path + name)，
   与生成批次/模型/时间无关 —— 否则每次重新生成都会新增一批能力点，`adjusted`
   保护也会失去稳定的作用对象。

### M2-b / M2-c 新增发现与设计决定（2026-10-02）

1. **状态迁移不交给模型**：提示词只负责"问什么"与"提炼四要素"；`draft→clarifying→
   proposed→confirmed` 的迁移与校验写在代码里（`GoalAgent` + 存储层双层）。这样
   「未确认不得进入能力分析」是**可执行约束**，而不是靠模型自律。
2. **确认是一次状态迁移，不该花一次 API 调用**，也不该让模型"代用户同意"：
   `confirm()` 不调模型；用户原话被补记到确认问句上，使 G1 的会话轨迹成为完整往返。
3. **增量累积语义**（修掉一个真实缺陷）：后续轮次未重述的要素曾被 `None` 擦掉，
   现改为"本轮没提到就保留既有值"，并加回归用例。这类"部分更新覆盖全量"的坑
   与 M1-b.5c 的 `INSERT OR IGNORE` / metadata 覆盖问题同源：**部分信息不得擦除既有事实**。
4. **能力树的形状校验先于写入，且整体拒绝**：五种违规（领域不足 / 能力点不足 / 超 3 层 /
   缺父节点 / 等级越界）都在写库前判定，拒绝时能力表为 0、运行记录保留 ——
   半个能力模型比没有更难发现。
5. **"未校验"由写入端强制标注**：模型即使自称"已核实"，`verification_status` 仍写
   `unverified`，并把模型原话与"未校验"标记并列保留（不删改模型说法，也不让它伪装）。
6. **运行号必须回传**：`AgentRuntime.call_model_with_run()` 返回 `RunOutcome`，
   使能力节点能写入 `generated_by_run_id` —— 这是 AC9（capability → goal → agent_run）
   能成立的前提，也是 M1-g "抽取模型未持久化"教训在 M2 的对应要求。

### M2-d 与 M2 收口：新增发现与设计决定（2026-10-02）

1. **端到端闭环已用真实模型验证**（EV-056）：澄清 4 轮 → 四要素 + 用户原话确认 → 能力树
   6 领域/12 组/31 个三层能力点 → 人工上调为 5 → 再生成后保留。事实判断：**"澄清通过"与
   "能力树通过"此前已分别验证，尝试 6 验证的是两者在同一次运行内闭环**。
2. **失败链的教训（4 次失败全部落在夹具/提示词/硬编码，产品逻辑未降级）**：
   ① 用户侧回答不得与提问轮次硬绑定，也**不能只靠宽泛关键词**——最终实现为"有状态 +
   意图候选 + 未答要素优先 + 问句主干焦点 + 显式未匹配"（尝试 5 的失败正是宽泛匹配导致）；
   ② 提示词的隐含约定必须写全（"第三层才算能力点"、节点名内禁止「/」）——模型会合理地
   按字面理解；③ 演练脚本不得硬编码模型输出中的标识（领域/能力点命名每次不同）。
3. **两层预算成为常设纪律**：应用层结构化调用上限与传输层 HTTP 请求硬上限分别设定、
   分别记录；真实运行关闭传输层重试（`EVKG_HTTP_RETRIES=1`）；失败即停并写诊断
   （`session-<mode>-failed.json`），不自动重跑。
4. **待 M4 前决策：再生成的"并集"语义**。稳定 id 保证"同名不重复"，但两次生成若命名不同
   会累积节点（真实会话两次生成合并为 49 个节点）。PRD §25 说能力模型是"动态可演化对象"，
   但审计前必须明确：再生成是**替换、合并还是保留历史**（与 M1 记录的 hard-cleanup /
   supersede 议题同源）。
5. **AC4 的证据强度分层（如实记录）**：真实会话中调整过的节点在再生成后保住了值/理由/`origin`，
   但那次再生成未攻击同一 id；"同 id 覆盖"的强证据来自两级自动化测试。

### M3 决策记录（2026-10-02 用户定案，`docs/M3-PLAN.md` v1.0）

| # | 决策 | 定案 |
|---|---|---|
| 1 | M3 定位 | 证据准入 / Evidence Ingestion，**不做能力评估**（星级与 G2/G3 门判定留 M4） |
| 2 | `evkg[office]` | 允许作为开发期依赖；发布前按 B-g1 切 `git + rev` |
| 3 | GitHub | 脚本 + 最小验证页面；完整 UI 留 M8 |
| 4 | JD | 接入 `domain_reference` 通道，绝不进入用户能力断言 |
| 5 | 归属 | 先放 `Source.metadata.growth_attribution`，暂不新增 `g_attributions` |
| 6 | GitHub OAuth | **不作为 M3 开工前置**；先跑通本地文件 / 公共仓库 / PDF / JD 四条链路，私有仓库或用户授权确有必要时再接 |

**写死的硬规则**：**"存在证据" ≠ "证明能力"**。M3 的 claim 只能以材料/项目为对象
（"项目材料中出现 RAG 实现相关内容"），不得以"用户具备 X 能力 / 用户独立完成"为结论；
越权表述在 M3-e 被拒绝或改写为材料口径，原文 passage 保留供 M4 判断。
（如实备注：M1-c 的真实抽取曾产出用户口径主张并被 M4 攻击推翻；本规则要求 M3 起不再"创建"这类结论，
M3-e 需要一处小的产品侧校验改动，实现前会单独确认。）

**步骤结构**（用户指定，仅到步骤级）：M3-a 基础模型与归属层 → M3-b 本地材料 → **B-g2 PDF spike**
→ M3-c GitHub 公共仓库 → M3-d JD → M3-e Claim + audit + provenance → M3 Gate → M4。

### M3-a 新增发现与设计决定（2026-10-02）

1. **复用优先，只加"策略与校验层"**：`Source / Passage / Evidence / Claim` 结构 evkg 已有，
   M3-a 不另造模型，只新增：归属标签（`Source.metadata.growth_attribution`）、
   归属消费规则（合取：`user_declared` + `user_evidence`）、越权校验器（纯函数）。
   证据链的遍历与 provenance 呈现留给 M3-e。
2. **归属读取 fail-closed**：未声明或非法取值一律读作 `unknown` —— 默认成 `user_declared`
   会把"没声明"读成"用户声明过"，正是归属层要防的越权；默认 `unknown` 只会更保守。
3. **越权校验按 claim 三元组判定，不只看陈述字面**：同一条陈述，主语是材料即合规
   （"原文描述的项目实现了 RAG 检索服务"），主语是用户即越权（"用户实现过 RAG 检索服务"）——
   这正是 M1-c 实测到的分界。校验器只判定不追改：把 M1-c 那条历史上的用户口径主张
   接进写入路径处理的职责在 **M3-e**（用户明确要求不提前扩大范围）。
4. **数据边界的新认识：文件哈希是弱不变量**。M3-a 复核时发现主库文件哈希变化
   （`6ca3205f…` → `56695a20…`），原因是 audit_log 追加（QG1 审计）与 WAL 检查点；
   而**逐表内容哈希与 M1-g 基线逐项一致**（6/6 evidence、2/2 claim）。
   结论：判断"库未被污染"应使用**逐表内容哈希 + 计数**；文件级哈希只在"预期零写入"的
   场景（如 M1-g 的 D1 实验）才有意义。锚点存 `artifacts/m3a/evidence-anchors.json`。

### M3-b 新增发现与设计决定（2026-10-02）

1. **先核对支持范围再动手**（用户指定的第一步）：读源码确认文本路由仅
   `.txt/.md/.markdown/.text/.csv/.json/.log`；代码路由取 `Profile.code` 的语言表与无扩展名
   文件名单一入口（`code_language_for`）；其余一律 `ValueError`（PDF 等走 V1 状态机）。
   **ZIP 此前完全未支持** —— 这是 M3-b 的真正新增点，其余三类主要是测试补强。
2. **ZIP 用"容器级封装"而不是新入口**：`evidence/archive.py` 不 import evkg、不解析内容，
   逐条目调用 `adapter.ingest_document`（唯一入口）。这样 M3-a 的归属/通道策略**结构上**
   不可能被绕过，并有 spy 测试断言"调用次数 = 可入库条目数"。
3. **稳定解包目录 = 幂等的前提**：解包到 `<归档名>-<内容哈希前 8 位>`，否则临时目录每次都变，
   同一份归档会不断制造新来源（身份按路径这一既有约定会被无声破坏）。代价：归档改名视为新来源、
   旧目录不自动清理（已记录为限制）。
4. **逐条目结果必须可见**：`ok / skipped / failed` 全留档（含原因），单条目失败不中断整份归档；
   安全规则（路径穿越、绝对路径、四道上限）一律走"跳过并说明"，不静默丢弃。
5. **`extra_metadata` 的保留键保护**：调用方可附加上来源信息（归档路径/条目名），但不得覆盖
   `growth_evidence_type` / `growth_channel` / `growth_attribution` —— 那三者的唯一决定者是
   具名参数，防止"顺手改标签"绕过策略。
6. **记入待办（上游）**：本仓的 ZIP 预筛表与 evkg 的路由表是两处知识，上游扩展语言表时预筛会漏判
   （后果只是跳过并报告）。彻底解法需要上游提供"某文件是否可入库"的公共判定入口。

### B-g2 新增发现与决策待办（2026-10-02）

1. **PDF 目前 100% 无法经 V1 状态机入库，原因是一行缺陷**：`providers.py` 的 `PdfReader.read`
   把 `bytes` 直接交给 `pypdf.PdfReader`（需要流/路径）→ `AttributeError: 'bytes' object has no attribute 'seek'`。
   同文件的 `OfficeReader` 已正确使用 `io.BytesIO`；evkg 测试对 PDF **零覆盖**（`test_ingest_boundary.py`
   只用假 PDF 测路由、不读内容）。最小修复：`Reader(io.BytesIO(content))`。
   → **待用户决策**：提交上游修复后重跑 B-g2（建议），或维持 PDF 不支持并留档。
2. **V1 段落的 locator 不含页码**（`{"ordinal": n}`），而 `RecognitionSpan` 已带 `page`/`bbox`。
   后果：PDF 证据无法自动定位回页，只能人工核对（原文字节、识别 span、归一化文档都在库里）。
   已登记为上游第 14 项（建议把页码写进 passage locator）。这是"M1-b.5a 的 locator 纪律"在
   V1 路径上的同类问题：**locator 必须能定位回原文，否则承诺是空的** —— 当前 PDF 路径做不到。
3. **段落对归一化文本是完整分区**（去空白后逐字一致，缺失 0/多余 0）：说明当前 PDF 路径
   **不丢字**，问题只在"定位粒度"与"对原始 PDF 的逐字还原不保证"（PDF 抽取 + 归一化双重转换）。
4. **V1 入库不带成长标签**（metadata 只有 `{ingestion_job_id, completeness_pending}`）：
   若 PDF 要进产品，适配层需要新增 V1 入口并保证归属/通道策略贯穿（M3 后续步骤）。
5. **环境陷阱**：`uv sync --extra office` 会移除 dev 工具（本项目把 `dev` 也定义为可选 extra）；
   正确命令 `uv sync --extra dev --extra office`。已实测踩到并恢复；`uv.lock` 未变。

### B-g2 收口（2026-10-02，用户选 A）：PDF 基础 ingestion 可用（含边界）

1. **上游最小修复已落地**（evkg `db2de3a`，未推送）：`PdfReader.read` 的 `bytes → io.BytesIO(bytes)`，
   并补 `tests/test_pdf_reader.py` 6 项**真实内容读取**测试（覆盖空洞已填：原测试只用假 PDF 测路由）。
   范围纪律：只改这一行 + 补测试，未动 locator 设计 / V1 状态机 / completeness / `audit_store` / 适配层 / M3-c。
2. **三项验证在修复后的真实代码上重跑，全部达标**：入库（40 段）、`audit_store` pass/0、
   locator 按要求**如实说明**。**交叉印证**：as-is 与脚本内等价实现两轮结果完全一致。
3. **两个问题分离记录**（用户指定，不互相包装）：
   * 问题 #1 `bytes` 缺陷 → **fixed @ db2de3a**；
   * 问题 #2 **页码级 locator 缺失** → **独立开放项**（上游清单第 14 项）。passage 仅 `ordinal`，
     无 page-level 定位、对原始 PDF 不保证逐字；但 passage 是归一化文本的**完整分区**（去空白逐字一致、缺失 0）
     → **内容可验证、定位粒度不足**。按 M3-PLAN §5 第三项（"如实说明"）该项达标，**既不伪装失败，也不说成完整通过**。
4. **PDF 支持边界已写进 M3-PLAN §5**：能入库并产出段落、内容可对归一化文本核验、审计通过、失败/无文本会留档或转 review；
   不具备 page-level locator 与对原 PDF 的逐字保证；入库后产生 blocking 澄清；
   **产品接入前仍需适配层新增 V1 入口并保证归属/通道策略贯穿**（M3 后续步骤）。
5. **待办**：归档刷新（B-g1 的 bundle 指向 `28afbc0`，本地现领先 5 个提交）；PDF 段落的"可检索"（FTS）留 M3 Gate 判定。

### M3-c 新增发现与设计决定（2026-10-02）

1. **用 git 浅克隆代替 REST API**（实测决定）：无凭据的 GitHub API 配额（60/h/IP）在本机**已耗尽**
   （`403` 且 `x-ratelimit-remaining: 0`）。git 协议无凭据、无该配额，并能拿到**提交 SHA**（可追溯的关键）；
   私有/不存在的仓库因"不交互"（`GIT_TERMINAL_PROMPT=0`、`GIT_ASKPASS=echo`）而**快速失败**，
   不会卡在输入提示上。代价：拿不到只有 API 才有的元数据（stars/language 统计等），本步不需要。
2. **克隆目录按 `owner-name-ref` 稳定，SHA 写 metadata 而非路径**：与 ZIP 的处理同源 ——
   若把 SHA 放进路径，每次提交都会产生一批新来源（身份按路径）；放进 metadata 才能让
   "同一仓库同一 ref"重复接入命中同一批 `source_id`（实测幂等），内容变化由 `content_hash` 表达。
3. **技术栈清单是确定性的、带证据路径**：语言判定复用 `adapter.code_language_for`（转发 evkg 语言表，
   不再抄第三份后缀表）；框架/工具用文件名与路径标记（requirements.txt、package.json、Dockerfile、
   `.github/workflows/` 等）。检测覆盖**全部跟踪文件**（含未入库的大文件），与入库选择解耦。
4. **Windows 的 git pack 只读坑**：`git clone` 会把 `.git/objects/pack/*.idx` 设为只读，
   `shutil.rmtree` 因此以 `WinError 5` 失败（实测踩到）→ 实现 `force_remove_tree()`（先清只读位再删），
   删不掉时给出可操作的产品错误而不是裸 OSError。
5. **`audit_store` 不关连接的问题再次咬人**（M1-g 上游清单 §7-10 的又一实例）：它内部打开的
   `KnowledgeStore` 不关闭，Windows 上锁住临时库（本次以 `gc.collect()` + 重试处理，并确认无残留）。
   这为上游那条"给 `KnowledgeStore` 加 `close()`/上下文管理器"增加了第二个真实案例。
6. **边界守恒**（按用户锁定项）：本步**未**接 OAuth / 私有仓库 / 完整 UI / 能力评估；
   **≥3 条 capability claim 与"可检索"分别留给 M3-e 与 M3 Gate** —— 不因"接入跑通"而替代证据链验收。

### M3-d 新增发现与设计决定（2026-10-02）

1. **"不得进入 user_evidence" 用结构保证，而不是靠约定**：`ingest_reference_document()` 的签名
   **没有** `channel`/`evidence_type` 参数 —— 调用方无法表达"把它当用户证据入库"这件事；
   消费侧再由 M3-a 的合取规则（`can_support_user_claim` 要求通道为 `user_evidence`）一票否决。
   两层都不依赖"记得传对参数"。有测试断言签名与消费行为（含"落在 domain_reference、不在 user_evidence"）。
2. **抽取只读**：`extract_reference_profile()` 只读 passage，产出「技术词 + 要求条目」并逐条附 passage 证据，
   **不写 claim / evidence / entity**，也不做评分或差距（有计数前后一致的测试）。边界 4 允许"抽取为外部参考"，
   但这与"得出能力结论"是两件事 —— 后者属 M4。
3. **归属仍如实记录为 `user_declared`**：attribution 回答的是"材料是不是用户交出来的"（此处确实是他给的），
   而**通道**才是禁止支撑用户断言的那一票。两者各司其职，测试同时锁住了这两点。
4. **ASCII 词用边界匹配**：`go` 不得被 `google` 命中 —— 技术词表若用朴素子串匹配会产生假阳性，
   而这类"技术栈清单"会被用作外部参考，假阳性会污染参考画像。
5. **素材如实标注**：本机没有现成真实 JD，冒烟使用写实合成样本；政策边界验证不依赖文本真实性，
   这一点写进了产物（`artifacts/m3d/reference-ingest-result.json` 的 `material.note`）。

### 治理维护：账本体积与归档（2026-10-02）

1. **触发**：PROJECT_ACCEPTANCE.md 达到 65,738 字节，超过 65,536 告警阈值。
2. **实测发现治理脚本的保留规则**：`--compact` 按"表格**前 N 行**（文档顺序）"保留、把其余移入
   `archive/acceptance/2026-10.md`（有 manifest 可 `--restore-compaction`）。因此它默认把**最旧**的记录
   留在活动视图、把最新（M2/M3）移走 —— 与"当前状态视图"的意图相反；把表倒序后它又判定"无可归档"。
3. **采用的处理**：手工归档（不改写任何记录）—— 证据索引保留 **EV-045…EV-064**（最新 20 条，升序），
   **EV-001…EV-044** 移入 `archive/acceptance/2026-10.md`（文件头写明归档原因、恢复方式与"不改写内容"），
   并在活动文档留归档指针。处理前后 `--validate`/`--audit` 均为 `strict_valid`、无 errors/warnings。
4. **纪律**：归档只**搬移**记录，不改写内容；活动文档始终指向归档，保证可追溯。

### M3-e 收口决定：历史越权主张不就地标注（2026-10-02 用户决定）

* **决定**：真实库保持原样 —— **不新增 `growth_overreach_flagged` 元数据**。
* **理由**：① M3-e 的目标已达成（写入路径有越权闸门；dry-run 已证明历史问题可被识别；结论已进入
  诊断与验收记录）；② 真实库自 M3-a 起一直维持"逐表内容哈希 + 计数"锚点，M3-e 又专门验证了
  dry-run **零写入** —— 现在为"机器可读"去改 metadata 会引入新的写入事件，需要重新解释边界变化；
  ③ 越权标注更接近 **M4 的审计产物**：M3 的职责止于 `source → passage → evidence → material claim`，
  `claim → assessment → 证据充分性 → 能力判断` 属 M4。
* **记录方式**（结论在案、存储不变）：`clm_f13861f536d0ffedd12c` = `detected_overreach`（dry-run）+ storage 未变；
  `clm_29f55c14c2e760b75d18` = `clean` + storage 未变。
* **向前约束**：若 M4 需要机器化的越权审计，应产出**独立的 audit artifact**，不得把标注写进原始 evidence store。

### M3 收口（2026-10-02）：证据接入完成，Gate 通过

1. **Gate 结论**：完成条件 1–5 + 质量门 **13/13**（EV-065，`artifacts/gates/M3/README.md`）。
   四个通道全部验证：本地材料（含 ZIP）、公共仓库、JD 外部参考、PDF；证据链
   `source → passage → evidence → material claim` 端到端可走通且 `audit_store` pass/0。
2. **Gate 过程中修掉的两个问题**（都不是业务逻辑问题，但会掩盖真实失败）：
   * **git 子进程解码崩溃**：中文 Windows 上 git 的错误输出不是 UTF-8，严格解码会在 reader 线程抛
     `UnicodeDecodeError`，把"仓库不存在"这种可解释的失败变成难诊断的崩溃 → 抽出
     `github.run_command()`（`errors="replace"`）并补非 UTF-8 字节的回归测试；
   * **密钥扫描的两处误报**：扫描范围应为**被 git 跟踪的文件**（`data/`、`.env`、`artifacts/**/tmp/`、
     `*.bak` 都已 gitignore），且正则 `\s*` 会跨行把空值后面的下一行变量名当成密钥 → 改为
     `[ 	]*` 且占位符放行；修正后 119 个跟踪文件 0 命中。
3. **两条保留边界**（Gate 通过不等于它们已解决）：① **PDF 的适配层 V1 入口仍未建** ——
   条件 1 的 PDF 由 V1 状态机直接驱动达成；② **页码级 locator 仍缺**（上游第 14 项）。
4. **M3 之后**：`assessment`（证据充分性 → 星级）属 **M4**；M3 的产物（材料口径 claim + 证据链 + 归属/通道标签）
   就是 M4 的输入。M4 开工前建议先确认：G2/G3 的判定方式、**归属层的正式设计**、
   以及 M2 遗留的"再生成并集语义"决策。

### M4 决策记录（2026-10-02 用户定案，`docs/M4-PLAN.md` v1.0）

| # | 决策 | 定案 |
|---|---|---|
| 1 | G2/G3 判定方式 | G2 = 证据可追溯性门（assessment→claim→evidence→passage→source，任一环缺失即"不生成等级、不补推断、输出 evidence insufficient"）；G3 = 用户声明 vs 证据支持门（`user_declared+user_evidence+完整链路` → 进入 assessment；`user_asserted` 无产物 → 待验证声明；`domain_reference` → 不能支撑；计划/学习目标 → 不是能力证据） |
| 2 | 归属三层模型 | source attribution / claim scope / capability ownership **不合并**；核心规则保留：**GitHub 仓库属于用户账号 ≠ 用户具备仓库中所有能力**；M3 解决 `source → evidence → material claim`，M4 才解决 `material evidence → capability assessment` |
| 3 | M2 再生成语义 | **history + current view**（不采用 replace：丢失演化过程；不采用 merge：历史污染当前）。`CapabilityRecord`：`generation_id` + `status ∈ {active, superseded, archived}`；不删除历史、当前视图单独查 active、assessment 绑逻辑 capability id、generation 记录变化来源 |
| 4 | C5（抽取模型持久化） | **上游最小修**（仿 B-g2 先例）：不改抽取逻辑、不改 claim 结构、只增加 provenance 字段、增加读取测试 |
| 5 | claim ↔ capability mapping | **LLM 提议 + 确定性闸门**：LLM 可提议能力类别/解释/关联，不可决定等级、不可补不存在证据、不可改 attribution；写入必须过规则检查 |
| 6 | G3 实验设计 | **真实材料 + 受控构造 + 独立库运行**；三类输入（A 项目材料可进入 / B 纯声明不足 / C JD 不可作为用户能力）与四类矩阵一致 |
| 7 | ROADMAP 交付物 2 | 由"摄入材料"调整为 **"基于已准入证据生成可审计能力评估"**（摄入已由 M3 完成） |

冻结记录：EV-066。M4-a 边界（用户指定）：模型契约 + provenance 前置 + 最小闭环；**不做星级算法、不做 LLM、不做 UI、不接 G3 实验**。

### M4-a 新增发现与设计决定（2026-10-02）

1. **C5 的落点与形状**：`_call` 不再丢弃 `ModelResult` —— provenance **取自实际返回值**
   （`extractor_provider/model/prompt_hash/profile`），写入 claim metadata 与成功批次账本。
   与用户建议 JSON 的两处工程判断：① evkg 的 `ModelResult` 没有模型 version 概念，
   可复现性由 `profile`（领域包）+ `prompt_hash`（system+user 全文哈希）表达；
   ② 键名采用**扁平式**，与既有 `verifier_model` / `verifier_independent` 惯例一致（不引入第二套形状）。
   档案渲染器三态：已记录 / 材料口径"不适用" / 修复前"未记录在案"（不拿当前配置冒充历史事实）。
2. **准入闸门是纯函数**（`assessment/contract.py`）：四类矩阵 + 越权 + 链完整性/引文逐字，
   全部确定性、可离线回归；`unknown` 归属与未知通道一律 fail-closed。
   **攻击裁决（broken）不进入准入这一点明确留给 M4-c**，契约不假装已覆盖。
3. **草案契约**：M4-a 的 assessment `level` 恒为 NULL —— 写入任何数字都报错
   （没有规则就不许手填等级）；id 由「判定对象 + 证据集 + 状态」派生：证据集变化 = 新草案
   （历史保留），同一证据集重复运行 = 同一行（幂等）。
4. **生命周期落地**：`generation_id` / `status`；`supersede_missing()` 把不在新树中的 `generated`
   节点标 `superseded`，**`adjusted` 不自动降级**；旧库打开时自动补列。
   **生成器尚未接线**（M2 生成路径本轮未改）—— 接线随 M4-b 的映射/绑定一并做。
5. **历史越权主张的机器化审计 = 独立 artifact**（落实 M3-e 的向前约束）：
   `artifacts/m4a/historical-claims-audit.json`，`sqlite mode=ro` 零写入；
   `clm_f138…` 归 `overreach`、`clm_29f5…` 归 `plan` —— 与 M3-e dry-run 判定一致，真实库不动。
6. **审计产物的形状**：`assessment-audit.json` 把每条草案的支撑主张逐条列出
   （准入分类 / 链路逐跳 / 引文逐字 / provenance），并附全库 `claims_scan`；
   显式声明 `read_only=true` / `mutated_evidence_store=false`。

### M4-b 新增发现与设计决定（2026-10-03）

1. **闸门是"治理边界"，不是"质量过滤器"**：八步固定顺序（schema → claim_exists →
   capability_exists → capability_active → bucket_allowed → attribution_unchanged →
   duplicate → persisted），任何一步失败即返回、**不落库**。真实运行暴露了 LLM 的两处提议
   质量缺陷（把"测试用例"的 rationale 写到自述 claim 上、5 条仓库 claim 漏提议 2 条）——
   结论：**治理边界不依赖提议质量**：错配被归属闸门拦下，漏提议只是未绑定，
   两者都不会造成错误数据。
2. **proposal schema 用 `extra="forbid"` 封死评价字段**：`confidence` / `level` / `score`
   一旦出现，schema 阶段直接拒绝 —— 结构性防住"提前引入评价体系"。
   `run_id` 不由 LLM 提供，由运行记录（`g_agent_runs`）补。
3. **分桶映射确定性且 fail-closed**：六个既有 `growth_evidence_type` 全表；
   `external_ref`（JD/论文）映射为 `None`（不入桶），未知类型同样拒绝 ——
   不静默丢证据、不硬塞进知识桶。
4. **LLM 输出没有直接落库路径**（结构性）：`ClaimBinder.propose()` 只返回决策；
   唯一写 `g_capability_claims` 的位置是闸门第 8 步，测试断言"桥表行数 == 接受数"。
5. **真实运行（1 次，用户授权）**：`openai_compatible/glm-5.3`、1 次结构化调用 /
   1 个 HTTP 请求（硬上限 1 + 零额外重试）、1364 tokens；6 候选 → 4 提议 → 3 接受 + 1 拒绝；
   真实库以 `mode=ro` 复制副本运行，逐表哈希 + 计数对锚一致（真实库零写入）。
6. **生成器接线推迟（用户决定）**：`M4-b scope: supersede_missing = contract visible only;
   generator wiring = deferred` —— 不把 `CapabilityModelGenerator.generate` 混进绑定的闸门，
   避免扩大 blast radius 与问题定位困难；后续单独开 `M4-b.1` 或并入 M4-c 前治理项。
7. **运行手册记一条**：本机 `uv` 不自动加载 `.env`，真实运行须用 `uv run --env-file .env`，
   否则网关回落到 anthropic 默认并报 `ANTHROPIC_AUTH_TOKEN missing`。

**关键设计结论（用户 2026-10-03 指定登记）**：

> **LLM 在 evidence → capability 映射中仅作为候选生成器；最终绑定必须经过确定性 Gate。
> Proposal 质量（漏提议、理由错误）不会直接影响知识库正确性。**

落地依据：M4-b 的八步闸门（唯一写入位置在第 8 步，测试断言"桥表行数 == 接受数"）；
真实运行中 LLM 的 id/理由错配与漏提议均未造成错误落库。

**对后续阶段的约束**：M4-c 的评级（星级规则引擎）与 attack 结算**不得建立在未经治理的
LLM 输出上**，而应建立在**已绑定、可审计的数据层**之上 —— 即
`g_capability_claims`（经闸门绑定）+ `claim → evidence → passage → source` 证据链
+ attack 裁决记录（`attack_reports`）。

### M4-c 决策记录与新增发现（2026-10-03）

**用户冻结口径**：两个独立维度不合并；基线表（自述 → 不足；`uploaded_doc` 2；`+probe_result` 3；
`repo_artifact` 3；`+task_submission` 4；显式优化/诊断/设计取舍信号 5）；反向证据
`broken` 剔除、`refutes` / `disputed` ≤2、`weakened` ≤3 且**不跨维度**；`current_level`
回填推迟 M4-d；"实践 ≤1"执行口径 = `insufficient_evidence`（缺失 ≠ 低分）；
真实 attack 运行推迟 M4-e（G3 实验 + A/B 证据产出）。

1. **基线按"能力点级证据集合"聚合**：`uploaded_doc + probe_result → 3` 是证据集合的组合，
   不要求落在同一张主张上 —— 引擎先聚合该维度覆盖主张的细粒度证据类型，再套基线表。
2. **理解维度必须按细粒度类型判定**（实施中发现的分界）：桶级（knowledge）聚合会把
   `chat_assertion` 误升为 2；改为只有 `uploaded_doc` 才起评后，"自述不单独产生等级"
   才真正成立。
3. **反向证据挂在被质疑的主张上**：`refutes` 是证据行极性，写在支持主张自己的证据里
   （不另造"支持型"的反向主张 —— 那会污染支撑集）。封顶按该主张覆盖的维度作用。
4. **level 5 的载体**：主张 metadata `growth_practice_signal ∈ {optimization, diagnosis,
   design_tradeoff}`；无此信号封顶 4，且不允许由规模 / 代码量 / 时长 / 模型分值推导。
5. **历史语义落地**：`g_assessments` 增 `dimension`；评定**不覆盖**旧草案；id 含等级 →
   结论变化即新行；当前视图用 `latest_assessment(capability, dimension)` 查询。
6. **D6 双重锁定**：功能对例（0.99 vs 0.05 同结论）+ 规则引擎源码 AST 静态检查
   （不得出现 `confidence` 标识符）。
7. **推迟项登记**：`current_level` 回填（M4-d，随展示形态一并定）；真实 attack 运行（M4-e）。

**关键设计结论（用户 2026-10-03 指定登记，M4-c 验收确认）**：

1. **能力评级必须基于 capability 级证据集合，而非单 claim** ——
   同一能力点下的多条证据共同支撑等级提升（如 `uploaded_doc + probe_result → 理解 3`，
   不要求两个证据属于同一条 claim）。
2. **Evidence type 不能直接等价于能力等级，必须经过维度规则** ——
   桶/类型只是输入；等级由维度基线表 + 显式信号 + 反向结算共同决定。
3. **反向证据属于 evidence 状态变化，不应制造新的支持/反支持 claim** ——
   `refutes` 挂在被质疑主张的证据行上，保持证据链闭合，避免主张膨胀与评级输入污染。
4. **评级结果是可重算派生数据，不覆盖历史事实** ——
   草案 → 评定是追加；等级变化 = 新行；当前视图用查询规则（`latest_assessment`）解决。

后续约束：M4-d 的可解释输出与 `current_level` 回填必须从**已存储的评定行 + 证据链**派生，
不得引入无法从评定重算的独立状态。

### M4-d 决策记录与新增发现（2026-10-03）

**用户冻结口径**：回填方案 A（`current_level_understanding` / `current_level_practice` 两维度列 + 重建校验）；
legacy `current_level` **保留、停用、不写**；`current_level_status` 扩为 `unassessed` / `assessed`
（允许部分评估：理解有、实践无 → `assessed`）；回填只经显式方法，不接入自动评级流程
（统一编排放 M4-e）；解释输出 Markdown + JSON 双份；"为什么不是更高"**只来自 `rubric.gaps`**。

1. **回填是派生缓存，不是新事实**：`apply_assessment_levels` 从 `latest_assessment` 取值；
   `verify_assessment_levels` 用同一重算比对列值（测试包含"人为篡改可被发现"）。
   这把 M4-c 结论 4（"评级结果是可重算派生数据"）在能力树上落成可校验的不变量。
2. **唯一写路径**：`upsert_capability` / `adjust_capability` / 生成器都不能写维度化等级列
   （写入即报错）；legacy `current_level` 保持 NULL —— schema 迁移不动历史数据。
3. **实施中收紧两处**（可读性/可复算）：① `rubric` 落 `base_level` 与 `level`
   （回填与报告都能从评定行复算，不靠推断）；② 报告的"已排除"按 claim 去重聚合
   （同一主张不再按维度重复列出），"反向证据"按（claim × 维度）带封顶值。
4. **报告纪律**：只复制规则引擎产出的等级与依据；不携带任何模型分值（JSON 扫描 + 渲染器源码
   AST 双重检查）；不把材料存在读成用户独立完成；`insufficient_evidence` 不读成低能力。

### M4-e 决策记录与新增发现（2026-10-03）

**用户冻结口径**：M4-e = 缺口 `g_gaps` + 真实 attack 运行 + G2/G3 证据产出 + 回填统一编排；
G3 主体 = `RAG 系统搭建与调优`（`cap_72c5cf53e0af7188`，不追加第二主体）；
A/B 判定 = 「A 实践不存在 ≥2 等级（`insufficient_evidence` 也算符合）且 B 实践 ≥2」，
B 实际等级 ≥3 只作增强观测、不作门条件；A 臂笔记在无真实笔记时受控构造并标注 `constructed=true`；
真实运行 ≤17 HTTP、零额外重试、fail-stop、不降级为无 attack；真实库不写；
编排顺序 `bind → attack → rate → report → apply → verify → gaps → verify_gaps`；
`g_gaps` 只表达 target − current + rubric 缺口（gap ≠ recommendation）；不修改 evkg / verifier / 词表 / 结算规则。

**实施中发现（三处，均已按最小方式处理并留档）**：

1. **evkg `run_adversarial` 的 `max_probes` 只限制目标 claim 数，不限制 probe 数** ——
   模型可对同一 claim 返回多条质疑，裁决调用数 = probe 数（实测 1 个目标返回 3–4 条）。
   冻结表假设的"1 目标 = 1 probe"不成立 → 两轮 adversarial 各只针对 1 个目标
   （单轮上限 A=4 / B=5，含 1 次 probe 生成），覆盖由 verifier 承担；
   总预算 ≤17 与零额外重试不变。**该调整需要用户在验收时确认**。
2. **evkg `get_claims()` 按 id 排序（非插入顺序）** —— verifier / adversarial 的覆盖目标
   确定但不可指定；本轮实际复核 6 条不同主张（含仓库主题与 JD 主张），adversarial 目标为
   对话材料与向量主题主张。材料的"创建顺序"不构成覆盖顺序保证。
3. **`insufficient_evidence` 行按设计没有支撑集**（"证据不足"本身是结论）→ G2 追溯补
   `trace_path=capability_bindings`（走该能力点绑定的主张集合），证明"不足"判断是对真实、
   链路完整的已绑定证据做出的；既无支撑也无绑定的行记 `none`，不计入抽样。
   `tests/test_traceability.py` 同时锁定"待验证声明可被追溯暴露"（`pending_declaration` → 不完整）。

**真实运行成本（如实披露）**：M4-e 共发起 6 次真实进程运行（2 次因代码缺陷在模型调用前/早期中止，
2 次因上述发现触发预算硬停，1 次完成但 G2 追溯器语义不足，1 次最终通过），
**真实 HTTP 合计 ≈53**；单次运行均 ≤17。教训：预算表应表述为"**单次运行**上限 + 允许的重跑次数"，
预算硬上限的价值在于把每次失败的成本封在 17 以内。

**编排口径（落地）**：`assess_capability` 只做 rate → report → apply → verify → gaps → verify 六步，
**无 LLM、无网络**；`verify_*` 失败即 `PipelineError`（fail-stop，不写缺口、不返回半成品结果）；
重复运行幂等（评定 id 由证据集派生；缺口行按（能力点 × 维度）唯一键 upsert）。
G2/G3 证据在**独立实验库**上产出，跑完即删；门证据 = `artifacts/gates/G2|G3/` 的 JSON/Markdown 归档。

**M4 封板（2026-10-03，用户确认）**：

- **M4-e 验收通过**；**M4 Gate 通过（21/21）**：完成条件 1–6 + QG1–QG5 + 数据边界，
  判定记录 `artifacts/gates/M4/README.md`、原始结果 `artifacts/gates/M4/m4-gate-result.json`；
  G2/G3 状态登记为"通过（用户已确认）"；M4 总验收索引入 `PROJECT_ACCEPTANCE.md`。
- **两项设计记录（用户 2026-10-03 确认登记）**：
  1. **预算口径**：**单次真实运行 ≤17 HTTP**；允许因代码修复 / 预算硬停 / 重新验证重跑，
     但**每次运行独立记录**；不再表述为"整个开发阶段累计 ≤17"（累计调用不能代表单次实验成本）。
  2. **成本披露**：M4-e 共 6 次真实进程运行（失败/修复运行单独归档，完成实验仍满足 ≤17）；
     该披露方式被确认为正确做法。
- **M4 保留边界（封板后仍成立）**：评估在独立实验库产出、**真实库不含 `g_` 表**（产品化写入是 M5 起的决定）；
  G3 主体为 RAG 相关能力（非 "Agent Memory"）；A 臂笔记为受控构造（已标注）；
  `M4-b.1` 生成器接线与 M3 两个开放项保持推迟登记。

### M5 边界冻结与关键设计约束（2026-10-03，用户确认）

**范围冻结（做）**：`g_tasks` 契约 / `g_task_submissions` / 状态机 / gap → task generator /
**LLM proposal + deterministic gate** / submission → evidence / claim binding / reassessment / G4 / G5。

**不做（冻结）**：UI → M8；Memory → M6；主动 Agent → M6/M7；任务排序 / 学习路径 / 多任务 DAG /
任务质量评分 → 后续；evkg 修改 → **不做**。

**四条关键设计约束（新增冻结原则）**：

1. **Task 不是能力判断** —— 任务只负责 `gap → evidence opportunity`，
   **绝不产出 `task → skill score`**（`g_tasks` 不含等级/分值字段）；
2. **完成任务 ≠ 自动提升** —— 提升必须经 `submission → evidence → claim → binding gate → assessment`；
   任务完成只是产生**候选证据**；
3. **新证据必须保持 provenance** —— 可反向查询链
   `task_id → submission → source_id → claim_id → assessment_id → level change`，**G5 必须能反查**；
4. **M4 rating contract 不修改** —— 只复用已冻结阶梯（`practice 3 → task_submission → 4`；
   `understanding 2 → probe_result → 3`），M5 不重新定义星级。

**其余随 `docs/M5-PLAN.md` v1.0 冻结的口径**（提议值，可修订）：`deliverable_type` 四枚举与证据类型映射
（`markdown/code/archive → task_submission`；`probe_answer → probe_result`）；`acceptance_type` 三枚举；
`est_minutes` 10–600；状态机 `proposed/active/blocked/done/abandoned` 且 **`done` 唯一入口 = `complete_task`**
（转移写 `g_events`，`kind=task_status_changed`）；理解缺口只允许 `probe_answer`（probe 评分不进等级）；
G4/G5 在独立实验库运行、真实库继续零写入；真实运行预算 ≤4（G4）+ ≤3（G5）、合计 ≤7。

冻结记录：EV-072。开局步骤 **M5-a：数据契约 + 状态机 + 工具注册**。

### M5-b 约束登记（用户 2026-10-03 确认，随 M5-a 验收一并冻结）

1. **任务生成器不得引入能力判断字段**：禁止 `expected_level` / `confidence` / `difficulty_score`
   之类字段（proposal schema 用 `extra="forbid"` 结构性拒绝，并有静态检查）；
   只允许描述"做什么 / 产出什么 / 怎么验"（`deliverable_type` / `acceptance_type` / `acceptance`）。
2. **任务质量 ≠ 学习价值**：M5-b 的闸门只验证「可交付 / 可验收 / 来源于 gap / 能进入证据闭环」，
   **不评价**"是否最佳学习路径 / 是否最有效任务 / 是否符合个人规划"——这些留给 M6/M7。

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
