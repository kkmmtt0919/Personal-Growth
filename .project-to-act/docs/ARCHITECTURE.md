# Growth OS 架构规划

> 本文档把 PRD 的"产品意图"翻译成"可实施的系统结构"。它回答：系统分几层、每一层谁负责什么、evkg 在哪里接入、数据存在哪、以及哪些地方是我们必须自己写的。
>
> 依据：`PRD.md`（第 5、8、9、10、11、13、26、27、28、29、30 节）
> 状态：**待用户确认**（见 `DECISIONS.md` 的 Q1–Q4）

---

## 1. 一句话架构

> **evkg 提供"证据可信度"底座，Growth OS 在其上增加"能力评估"这一层自有语义，再用自建 Agent 运行时把 Goal / Capability / Evidence / Task / Growth 串成闭环。**

关键点：**证据可信度 ≠ 能力等级**。这是整个架构最重要的一条分界，第 3 节展开。

---

## 2. 分层结构

```
┌────────────────────────────────────────────────────────────────────┐
│ L5  前端 Web（3 个页面）                                            │
│     Dashboard │ Evidence Space │ AI Mentor                         │
├────────────────────────────────────────────────────────────────────┤
│ L4  Growth OS API（FastAPI）                                       │
│     /chat /goals /capabilities /assessments /tasks /evidence       │
│     /memory /growth /notifications /integrations/github            │
├────────────────────────────────────────────────────────────────────┤
│ L3  Agent 运行时（自建，薄）                                        │
│     Orchestrator                                                   │
│       ├── Goal Agent        （目标澄清 / 能力模型生成）              │
│       ├── Assessment Agent  （证据 → claim → attack → 评级）        │
│       ├── Growth Agent      （缺口 → 任务 → 每日分析 / AI Mentor）   │
│       └── Scheduler         （每日分析、事件检测、提醒）             │
│     公共件：ToolRegistry · ContextAssembler · Tracer                │
├────────────────────────────────────────────────────────────────────┤
│ L2  Growth 领域服务（自有语义层，本层是"我们真正写的东西"）           │
│     GoalService · CapabilityService · AssessmentService             │
│     TaskService · MemoryService · GrowthService                     │
├────────────────────────────────────────────────────────────────────┤
│ L1  证据底座 = evkg（复用为主 + growth 领域包）                      │
│     ingest → extract → attack → dossier → search                   │
├────────────────────────────────────────────────────────────────────┤
│ L0  存储：单 SQLite（WAL）                                          │
│     evkg 表族（不动）  +  g_ 表族（Growth OS 自建）                  │
└────────────────────────────────────────────────────────────────────┘
```

**分工原则**：L1 只管"这段文字说了什么、这条断言有多可信"；L2 才管"所以用户这个能力是几星"。两者不允许互相渗透。

---

## 3. 核心桥梁：从 Claim 到 Capability（本架构的关键设计）

### 3.1 问题

evkg 的 `Claim` 语义是**关于世界的断言**，它的 `confidence` 回答的是：

> "用户具备 RAG 工程基础能力" —— **这句话本身有多可信？**

而 PRD 第 9 节要回答的是：

> 用户的能力在 **五星量表** 上处于第几级？

这是两个不同的问题。**不能把 `confidence` 线性映射成星级**，否则：

- 一条由高可信来源（GitHub 代码）支撑的"用户会写 Hello World"会拿到高 confidence，被误判成高星级；
- 十条弱来源（聊天自述）互相印证也会推高 confidence，但实践能力仍然是零。

### 3.2 解法：三层分离

```
① 原语层（evkg 原生，不改）
   Claim: subject="用户", predicate="具备能力", object="RAG 工程基础能力"
   Evidence: 每条绑定真实 passage（GitHub 代码 / 任务提交 / 笔记 / 聊天）
   Attack:   质疑 → 裁决(sustained/weakened/broken) → 缺失证据清单
   ↓
② 评估层（Growth OS 新增，AssessmentService）
   输入：该能力下所有 claim 的 evidence 集合（按证据类型分层）+ attack 裁决
   规则：PRD §10  →  知识 + 行为 + 实践 + 任务 − 反向证据
   输出：assessment 行（level 1–5, rubric 分解, rationale, 支撑 claim 列表）
   ↓
③ 展示层
   星级 + "为什么是这个星级"  →  直接复用 evkg dossier 渲染
```

**结论**：`confidence` 只用来判断"这条证据值不值得采信"，**星级由证据能达到的层级决定**（见 3.4）。

### 3.3 硬约束：SourceKind 是封闭枚举（已实测确认）

```
src/evkg/domain.py:10   class SourceKind(StrEnum):  primary | contemporary |
                                                    compilation | modern_study |
                                                    folk | unknown
src/evkg/policies.py:28 score, rationale = _policy_table()[kind]   ← 直接字典取值
```

`_policy_table()[kind]` 是直接索引，**传入未知 kind 会直接 KeyError**。因此：

> **不能新增 `github_code` / `task_submission` 这类来源类型，除非修改 evkg 源码。**

### 3.4 应对：粗粒度 kind 驱动 confidence，细粒度类型驱动星级

采用**双轨记录**，零 evkg 改动：

| 用途 | 存放位置 | 谁消费 |
|---|---|---|
| 粗粒度来源可信度 | `Source.kind`（6 个固定值之一） | evkg 的 confidence 计算 |
| 细粒度成长证据类型 | `Source.metadata.growth_evidence_type`（自由 JSON） | Growth OS 的星级规则 |
| 证据归属通道 | `Source.metadata.growth_channel` | 防止领域资料污染能力断言 |

**种类映射表**（定义在 growth 领域包 `source_policy` 的 `rationale` 文案里，做到"看配置就懂语义"）：

| growth_evidence_type | 中文 | 映射到 kind | baseline | 在 PRD §10 公式中的角色 |
|---|---|---|---|---|
| `task_submission` | 任务提交产物 | `primary` | 0.82 | 任务证据（最强，闭环自产） |
| `repo_artifact` | GitHub / ZIP 项目代码 | `primary` | 0.82 | 实践证据 |
| `probe_result` | 系统现场出题、用户作答 | `contemporary` | 0.78 | 行为证据 |
| `uploaded_doc` | 用户上传笔记/文档/代码 | `compilation` | 0.68 | 知识证据 |
| `chat_assertion` | 对话中的自述"我会 X" | `folk` | 0.35 | 弱证据：只能触发澄清，不可单独支撑结论 |
| `external_ref` | 岗位 JD / 官方文档 / 论文 | `modern_study` | 0.62 | **不参与能力评级**，只用于生成能力模型 |
| （未分类） | — | `unknown` | 0.25 | — |

`growth_channel` 取值：

- `user_evidence` —— 关于用户本人的证据，参与能力断言
- `domain_reference` —— 关于领域/岗位的参考资料，只喂给能力模型生成

> **为什么必须分通道**：如果把岗位 JD 和用户笔记放进同一个 claim 空间，"AI 工程师需要会 RAG"会被误读成"用户会 RAG"。这个 bug 会直接击穿 PRD §33 第 2 条（证据可追溯）。

---

## 4. 数据模型

### 4.1 存储选型

单 SQLite（WAL），两个表族共存。可行性依据：evkg 的 `KnowledgeStore._migrate()` 全部使用 `CREATE TABLE IF NOT EXISTS`（`store.py:40-95`），幂等且可叠加；无外键约束，因此跨表族引用由应用层保证。

### 4.2 evkg 表族（直接复用，不修改）

`sources` `passages` `entities` `entity_aliases` `events` `relations` `timeline_entries` `place_assertions` `claims` `evidence` `conflicts` `conflict_candidates` `attack_reports` `audit_log` `review_feedback` `ingestion_*` `*_extraction_passages` `extraction_batches`

### 4.3 Growth OS 表族（自建，统一 `g_` 前缀）

| 表 | 关键列 | 说明 |
|---|---|---|
| `g_users` | id, display_name, created_at | MVP 单用户，但所有表带 `user_id`，为多用户留位 |
| `g_goals` | id, user_id, title, direction, purpose, horizon, measurable_result, status, source_quote | status: `draft/clarifying/proposed/confirmed/archived` |
| `g_goal_clarifications` | id, goal_id, round, question, answer, created_at | 澄清轨迹，验收 G1 的证据 |
| `g_capabilities` | id, goal_id, parent_id, name, aliases, weight, target_level, origin | 树形；origin: `generated/adjusted` |
| `g_capability_claims` | capability_id, claim_id, role | 桥表；role: `supports/gap`；claim_id 指向 evkg claims |
| `g_assessments` | id, user_id, goal_id, capability_id, dimension, status, level, rubric_json, rationale, created_at | 两维度（理解 / 实践）评定；`status: draft/insufficient_evidence/rated`；rubric_json 记录可复算依据（无模型分值） |
| `g_gaps` | id, user_id, goal_id, capability_id, dimension, current_level, target_level, severity, rationale, assessment_id, status | 缺口（M4-e）：severity `evidence_gap/level_gap_1/level_gap_2plus`；只从评定行派生、可重建校验；status `open/closed`（M5 起流转） |
| `g_tasks` | id, user_id, gap_id, capability_id, title, objective, est_minutes, deliverable_type, acceptance, status | status: `proposed/active/blocked/done/abandoned` |
| `g_task_submissions` | id, task_id, source_id, note, created_at | source_id 指向 evkg sources → 完成即产生新证据 |
| `g_memories` | id, user_id, layer, key, value_json, updated_at | layer: `profile/state`（Growth History 见快照表） |
| `g_events` | id, user_id, kind, severity, payload_json, created_at | 主动 Agent 的事件源 |
| `g_growth_snapshots` | id, user_id, taken_on, scores_json | 成长曲线；PRD §13.3 |
| `g_notifications` | id, event_id, channel, read_at, dismissed_at | 用户可关闭 |
| `g_agent_runs` | id, user_id, agent, input, tool_calls_json, output, tokens, latency_ms, error, created_at | 轨迹与 Evaluation 地基 |
| `g_integrations` | id, user_id, provider, secret_ref, scopes, meta_json | GitHub OAuth；**只存引用，不存明文 token** |

### 4.4 关键关系

```
g_goals ──1:N──> g_capabilities ──1:N──> g_assessments
                        │                      │
                        │                      └──> g_gaps ──> g_tasks ──> g_task_submissions
                        │                                                     │
                        └──N:M── g_capability_claims ──> claims(id)  <────────┘
                                                             │         (新的 source → 新 claim)
                                                             └──> evidence ──> passages ──> sources
```

跨表族引用（`claim_id` / `source_id`）由应用层保证一致性，并在评估后跑 `evkg audit_store` 校验。

---

## 5. Agent 运行时

### 5.1 决策：自建薄运行时，不引入框架

理由：

1. PRD §29 明确 MVP 只需 3 个逻辑 Agent，框架带来的抽象成本大于收益；
2. PRD §33 把 Capability Audit 和 Evaluation 列为成功标准 —— 自建 loop / tool / trace 才拿得到可评估的轨迹数据；
3. evkg 的 `ModelGateway` 已是可复用网关（支持 Anthropic 与 OpenAI 兼容、支持独立第二验证模型），无需再引入一层。

**代价**：需要自己处理重试、超时、工具调用解析。可接受，因为 `ModelGateway` 已经用 `structured()` 把"约束式 JSON 输出"这件事解决了。

### 5.2 组件

| 组件 | 职责 | 说明 |
|---|---|---|
| `Orchestrator` | 路由：判断一条用户消息进哪个 Agent | 首版用规则 + 轻量 LLM 分类 |
| `AgentRuntime` | 单轮循环：装配上下文 → LLM → 工具调用 → 回灌 → 收敛 | 有最大轮次与 token 预算 |
| `ToolRegistry` | 工具声明（name / JSON schema / handler / 是否写库） | 写操作工具需显式标注，便于审计 |
| `ContextAssembler` | 从 Goal/Memory/Capability/Evidence 组装上下文 | 按优先级裁剪，防 token 爆炸 |
| `Tracer` | 每次运行落 `g_agent_runs` | 是 Evaluation 与"为什么这样回答"的依据 |

**Provider 复用**：直接 `from evkg.model_gateway import ModelGateway`。它用 `EVKG_` 前缀的环境变量配置；Growth OS 侧用显式 `overrides={...}` 传入自己的配置，避免与 evkg 的进程级全局配置互相污染。

### 5.3 三个 Agent 的职责与工具

**Goal Agent —— 目标澄清（PRD §16）**

```
状态机：draft → clarifying ⇄ proposed → confirmed
工具：get_memory(profile) · save_goal_draft · confirm_goal
      · generate_capability_model · list_capabilities
约束：模糊目标不得进入能力分析（PRD §16 结尾）；必须用户显式确认才落 confirmed
```

**Assessment Agent —— 证据到能力（PRD §8、§9、§10）**

```
阶段一（证据摄入）：evkg_ingest · evkg_extract · create_claim
阶段二（审计）：     run_attack · get_dossier · write_assessment · update_gaps
约束：每条 claim 必须引用真实 passage（evkg 已强制）；无证据的能力不得给出星级
```

**Growth Agent —— 成长与导师（PRD §11、§14、§15、§21）**

```
模式 A（有任务）：list_gaps · create_task · complete_task · write_event
模式 B（对话）：  检索 Goal+Memory+Capability+Evidence+History 后回答"我距离 X 还有多远"
模式 C（定时）：  daily_analysis → 事件检测 → 必要时 notify
```

### 5.4 主动模式的 4 类事件（PRD §15）

| 事件 | 检测条件 | 动作 |
|---|---|---|
| 能力出现新证据 | 新增 assessment 导致 level 上升 | 更新能力 + 提示 |
| 长期停滞 | 窗口期内理论证据增加、实践任务完成数 = 0 | 行动建议 |
| 发现能力缺口 | 某能力 target_level − current_level ≥ 2 且长期无 task | 生成任务 |
| 目标变化 | 用户声明目标改变 | 重新生成能力模型 |

**抑制规则**：每日分析 ≠ 每日打扰。仅当检测到有意义变化才落 `g_events` 并生成 `g_notifications`；同类事件设冷却期。

---

## 6. 关键数据流

### 6.1 首次使用（PRD §17）

```
用户自然语言描述目标
  → Goal Agent 多轮澄清 → g_goals(status=confirmed)
  → generate_capability_model(external_refs, channel=domain_reference) → g_capabilities
  → 邀请提供证据（上传 / GitHub / 继续聊天）
  → evkg ingest(channel=user_evidence) → passages
  → Assessment Agent: extract → claims → attack → assessments
  → Dashboard: 能力画像 + 第一个 task
```

**允许低数据量启动**：即使只有聊天，也必须能产出第一版画像（星级可能普遍偏低，但必须标注"证据不足"而非"能力不足"）。

### 6.2 日常循环

```
聊天 → Orchestrator → 目标 Agent → 工具 → 落库 → 回复
定时 → Scheduler → Growth Agent → 事件检测 →（有条件）通知
任务完成 → g_task_submissions + evkg source → 新 claim → 重新评估 → 星级变化
```

---

## 7. 必须由我们自己写 / 直接复用 evkg

| 能力 | 来源 | 备注 |
|---|---|---|
| 文档解析、切分、来源分级 | **evkg 复用** | PDF 需 `evkg[office]` |
| Claim 抽取、实体消解 | **evkg 复用** | YAML 领域包可定制 prompt |
| 攻击五件套（deterministic/verifier/contradiction/adversarial/audit/damage） | **evkg 复用** | 直接对应 PRD §8 |
| 证据档案（dossier，"为什么我只有三星"） | **evkg 复用** | PRD §20 的透明性由它提供 |
| 全文检索 / 图查询 | **evkg 复用** | 自带 Web API 可参考 |
| LLM 网关 | **evkg 复用** | `ModelGateway` |
| 能力模型生成 | **自写** | 目标 → 能力树 + 外部参考 |
| 五星评级规则 | **自写** | 本架构 3.4 节 |
| 能力缺口识别 | **自写** | |
| 任务生成与闭环 | **自写** | |
| Memory 三层 | **自写** | |
| Agent 运行时与轨迹 | **自写** | |
| 调度与主动提醒 | **自写** | |
| 用户 / 认证 / GitHub OAuth | **自写** | evkg 无用户概念 |
| 前端三页 | **自写** | 图谱可视化可复用 Cytoscape 方案 |

---

## 8. 已知风险与待验证假设

| ID | 风险 | 影响 | 应对 | 何时验证 |
|---|---|---|---|---|
| R1 | evkg 无 library facade，raw SQL 分散在 `web/queries/dossier/audit` | 若需深度定制会被耦合 | MVP 只调用其模块级函数；如需改 evkg，作为上游 commit 而非就地改 | M1 spike |
| R2 | `SourceKind` 封闭（已确认） | 细粒度证据类型无法进 confidence 计算 | 双轨记录（3.4 节）；若证明太粗，再向上游提扩展 | M1 spike |
| R3 | 系统 Python 仅 3.7.8，evkg 需 ≥3.11 | 环境不可用 | 已用 uv 管理 3.12（已验证）；锁定 `requires-python` | 已缓解 |
| R4 | evkg 进程级全局 `_ACTIVE` profile、`web._STORES` 无上限 | 多用户/多库并发不安全 | MVP 单用户单库；Growth OS 侧不并发切 profile | M1 |
| R5 | 能力模型生成的"外部知识"来源未定义（PRD §24 只说"官方文档/岗位/论文"） | 能力模型质量不稳定 | M2 需选型并冻结来源清单 | M2 前 |
| R6 | 中文 prompt 在抽取/攻击上的稳定性 | 证据质量 | 用 evkg 第二模型机制做交叉验证；建立小规模评测集 | M4 |
| R7 | LLM 成本不可控（每份资料都要抽取 + 攻击） | 体验与费用 | 批处理 + 断点账本（evkg 自带）；限制单次资料体量 | M1 起持续 |

---

## 9. 非目标（架构层面）

明确不在 MVP 架构中引入（对应 PRD §32）：

- Neo4j 或其他图数据库（关系在 SQLite + 应用层维护）
- 向量数据库（先用 evkg 的 FTS5 + 结构化查询；Embedding 仅按需引入）
- 多 Agent 编排框架（LangGraph / AutoGen 等）
- 微服务拆分、消息队列、容器编排
- 多租户与权限体系
