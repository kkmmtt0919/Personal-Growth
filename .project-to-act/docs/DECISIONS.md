# 架构决策记录

> 记录**已经决定的**与**等待用户决定的**事项。决定一旦落定，除非有新证据不轻易推翻；如推翻，追加记录而非删除。
>
> 状态：D1–D3、D6–D8 已拟定待确认；**Q1–Q4 必须由用户决定后才能进入 M1**。

---

## 待用户决策（阻塞 M1 开工）

### Q1 · evkg 如何集成？

现状：evkg 位于 `D:\projects\evkg`（独立仓库，单一 commit，版本 0.1.0）。它没有 library facade，`web/queries/dossier/audit` 等模块直接写 SQL；但领域包（YAML）可定制词表、prompt、来源分级、切分规则。

| 选项 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| **A（推荐）** | 保持独立仓库，Growth OS 用 `uv` path 依赖（`evkg = { path = "../evkg", editable = true }`） | 边界清晰；evkg 保持通用性；改动走上游 commit 可追溯 | 需要同步维护两个仓库；发布时需 pin 到 commit |
| B | 把 evkg 源码 vendor 进本仓库 `vendor/evkg/` | 单仓库、改动自由 | 与上游分叉，失去同步能力；evkg 的通用性卖点被浪费 |
| C | 作为 git 依赖 pin 到 commit | 可复现最好 | 开发迭代慢，每次改动要 push |

**推荐 A**。理由：evkg 的价值在于"通用证据图谱"，Growth OS 只是它的一个领域包消费者。分叉会让两边都变差。已确认 evkg 的 prompt / 词表 / 来源分级全部可在 YAML 层覆盖，MVP 阶段大概率不需要改它的源码。

**请确认**：A / B / C？

---

### Q2 · LLM 供应商与模型

evkg 的 `ModelGateway` 支持两类协议：

- `anthropic`（默认）：`EVKG_ANTHROPIC_*`
- `openai_compatible`：任意 OpenAI 兼容端点（含 Ollama 本地、智谱、DeepSeek 等），支持 `EVKG_OLLAMA_NATIVE=1`

另外支持配置**独立的第二模型**做核查（`EVKG_VERIFIER_*`），避免"自己审自己"。

需要确定：

1. 主模型用哪个供应商 + 模型名？
2. 是否配置独立的 verifier 模型（建议配，能显著提升攻击环节的可信度）？
3. 是否允许在开发期使用本地模型（Ollama）以控制成本？

**背景因素**：中文抽取与攻击对模型能力敏感；PRD §10 的能力判定质量直接取决于攻击环节质量。

---

### Q3 · 前端技术栈

| 选项 | 说明 |
|---|---|
| **A（推荐）** | React + Vite + TypeScript（与 evkg 的 `frontend/` 一致）；图谱可视化用 Cytoscape |
| B | Next.js（SSR + 路由约定，但 MVP 是登录后应用，SSR 收益有限） |
| C | 服务端渲染（Jinja2 + HTMX），最省事，但交互式图谱和聊天体验受限 |

**推荐 A**。理由：与 evkg 前端方案一致，可以借鉴其已有的 Cytoscape 图谱实现，减少 M8 的工作量。

---

### Q4 · MVP 是否需要多用户 / 登录？

| 选项 | 说明 |
|---|---|
| **A（推荐）** | 单用户本地优先，无登录；但所有表带 `user_id`，为将来留位 |
| B | MVP 就做多用户 + 注册登录 |

**推荐 A**。理由：PRD §17 强调"允许低数据量启动"，多用户会把精力吸到权限、会话、隔离上，而这些不影响 PRD §33 的 6 条成功标准。表结构已经预留 `user_id`，将来迁移成本可控。

**风险提示**：evkg 侧目前没有用户概念（`Source` 无 user_id，只有自由 `metadata`）。若将来要多用户，evkg 侧需要按用户分库或在 `metadata` 上打标。选 A 时这个代价可以推迟。

---

## 已拟定决策（待用户确认）

### D1 · 证据层复用 evkg，只在一个文件里 import

**决定**：Growth OS 通过 `backend/evidence/adapter.py` 这一个适配层访问 evkg，其余代码不得直接 import evkg。

**理由**：evkg 是 0.1.0 版本、无 library 契约、raw SQL 分散。把耦合收敛到单文件，将来若需替换或升级，改动面可控。

### D2 · 单 SQLite，双表族

**决定**：一个 SQLite 文件（WAL），evkg 表族 + Growth OS 的 `g_` 前缀表族共存。跨表族引用（`claim_id` / `source_id`）由应用层保证。

**理由**：PRD §27 明确单 SQLite 思路；evkg 建表全部是 `CREATE TABLE IF NOT EXISTS`，幂等可叠加，无外键约束，物理共存无冲突。避免为了 MVP 引入 Postgres / Neo4j。

### D3 · 复用 evkg 的 ModelGateway，不引入第二个网关

**决定**：`from evkg.model_gateway import ModelGateway`，用显式 `overrides={...}` 传入 Growth OS 自己的配置。

**理由**：已支持 Anthropic + OpenAI 兼容 + 第二验证模型 + 重试/超时/结构化输出。用 overrides 而非环境变量，是为了避开 evkg 的进程级全局配置（`config._ACTIVE`）。

### D4 · Agent 运行时自建，不用框架

**决定**：自建薄运行时（`AgentRuntime` + `ToolRegistry` + `ContextAssembler` + `Tracer`），不引入 LangGraph / AutoGen / CrewAI。

**理由**：① PRD §29 只要 3 个逻辑 Agent；② PRD §33 把 Evaluation 列为成功标准，自建才能产出可评估的完整轨迹；③ 避免框架锁死与隐藏行为。

**代价**：需自己处理工具调用的解析与循环收敛。可接受。

### D5 · 证据来源采用"双轨记录"

**决定**：粗粒度 `Source.kind`（6 个固定值，驱动 evkg 的 confidence）+ 细粒度 `Source.metadata.growth_evidence_type`（驱动 Growth OS 的星级规则）。另加 `metadata.growth_channel` 区分 `user_evidence` / `domain_reference`。

**理由**：**已实测确认** `SourceKind` 是封闭 StrEnum（`domain.py:10`），且 `assess_source` 用 `_policy_table()[kind]` 直接索引（`policies.py:28`），传入未知 kind 会 KeyError。因此不能新增来源类型。双轨方案零改动达成目标。

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
| 2026-10-01 | Q1–Q4 | 提出 | 阻塞 M1 开工 | 待用户决策 |

---

## 附：M1 spike 待验证清单

M1 完成后需回头更新本文件：

- [ ] R1：evkg 的模块级函数（`ingest_file` / `extract_corpus` / `run_attack` / `write_dossier` / `audit_store`）能否稳定地被外部调用？
- [ ] R2：`Source.metadata` 能否无损携带 `growth_evidence_type` / `growth_channel` 并可在查询中过滤？
- [ ] R3：growth 领域包的 6 个 source kind 语义重映射是否够用，还是必须扩展上游 enum？
- [ ] R4：evkg 的进程级全局 profile（`config._ACTIVE`）在单进程服务中是否会造成串扰？
- [ ] D1 结论：evkg 是"直接依赖可用"还是"必须改上游"？
