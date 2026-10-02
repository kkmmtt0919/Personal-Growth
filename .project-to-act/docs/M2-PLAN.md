# M2 目标与范围（v1.0 · **执行基线**）

> 状态：**已冻结（2026-10-02 用户确认）**。5 项决策全部确认并附补充约束；C1–C3 已写入（§6）；
> 开工前 4 项检查已完成且全部通过（§0.2，均为**设计级**检查，实现后在 M2-a…d 中转为可执行断言）。
>
> 依据：`ROADMAP.md` M2 · `PRD.md` §16/§17/§24/§25 · `ARCHITECTURE.md` §3/§4.3/§5.3/§6.1/§8 R5 ·
> `ACCEPTANCE_GATES.md` G1 · `M1-SPIKE-CONCLUSION.md`（有条件依赖 C1–C5、R3 覆盖盲区）。
>
> 边界声明：M1 已归档，本文件不重开 M1 结论；M2 不修改 evkg，只经适配层复用其 `ModelGateway`
> 的**实例级 overrides**（M1-g 已验证为安全的部分）。

---

## 0. 冻结状态

### 0.1 已确认决策（5 项）

| # | 决策 | 确认结果与用户补充约束 |
|---|---|---|
| 1 | R5 外部知识来源 | **有条件通过**：首版纯 LLM 生成，能力点标记 `unverified`，记录来源类型、生成模型、校验状态；`target_level` 是**建议值**而非客观评估。**LLM 生成的能力点不得伪装成已验证的行业标准；人工修改后保留修改来源。** M3 再接用户上传 JD；内置领域图谱另行决策 |
| 2 | G1 会话截图证据 | **确认豁免**：用完整会话轨迹导出替代截图，导出含 `g_goal_clarifications`、`g_agent_runs`、会话文本及关联标识，并记录豁免原因与补证计划（M8 补界面截图）。**豁免只替代截图形式，不豁免 G1 本身的验收要求** |
| 3 | 最小 Agent 运行时 | **确认**：落地 registry、tracer、context，接入 `g_agent_runs`；M4 可复用。**只实现 M2 需要的最小能力，不提前建设通用多 Agent 编排平台** |
| 4 | `target_level` 与树形态 | **确认**：LLM 建议 + 用户可调（`origin=adjusted`）；树最多 3 层（领域 → 能力组 → 能力点）。**再生成不得覆盖已调整值；建议值与人工值要有明确优先级与持久化规则** |
| 5 | 首版"已有能力" | **确认**：固定为 `尚未评估`，不推断用户现状、不生成星级；M4 接入证据后回填。**`尚未评估` 必须与真实低等级区分，不得用 `target_level` 填充当前能力水平** |

### 0.2 开工前 4 项检查（设计级）

| # | 检查 | 结果 | 依据 / 需要落地的动作 |
|---|---|---|---|
| 1 | 验收标准能否逐项映射到自动化测试或可归档证据 | **通过** | §5 映射表：12 条验收项全部有测试或归档位置 |
| 2 | 数据结构能否区分建议值 / 人工调整值 / 未评估 | **通过（需增补字段）** | §3.1：`g_capabilities` 增补 `generated_by_run_id`、`verification_status`、`adjustment_note`、`current_level` + `current_level_status`；并定义**稳定 id 规则**防再生成累积 |
| 3 | fake gateway 测试能否在无真实模型调用下独立运行 | **通过（设计前提已由 M1-g 验证）** | §3.3：运行时依赖 `StructuredGateway` Protocol，默认实现由适配层工厂给出，测试注入 fake；离线三保险 = 注入 + 无密钥 + httpx 阻断断言 |
| 4 | 代码变更是否越界、是否触碰 evkg 证据层 | **通过（需收窄既有守卫并新增 3 项检查）** | §3.2：M1 的"全包禁 sqlite3"与自建 `g_` 表冲突 → 收窄为"证据层全禁 + `store/` 白名单"，并新增 `g_` 前缀守卫与"证据层零写入"功能断言 |

> 说明：以上为**设计级**检查（代码尚未写）。它们不是验收结论；M2-a…d 必须把每条转成
> 能跑的断言与可归档输出，否则不得声称通过。

---

## 1. 目标

把一句模糊目标变成两样可读回、可调整、可验收的产物：

1. **一个 confirmed goal** —— 含四要素：方向 / 目的 / 时间周期 / 可衡量结果（PRD §16）；
2. **第一版动态能力模型** —— ≥3 个领域、≥12 个能力点，每点带 `target_level`（建议值）、
   来源与校验状态，可由用户调整且不被再生成覆盖。

一句话：**从"我想成为 AI Agent Engineer"到"一个可用的能力树"。**

---

## 2. 范围

### 2.1 要交付

- 模糊目标经 **≤6 轮**澄清，形成结构化 `confirmed goal`：方向、目的、时间周期、可衡量结果。
- 生成 **≥3 领域、≥12 能力点**的动态能力树。
- 能力点具备 `target_level`、来源、校验状态与**人工调整保护**。
- 最小 Agent 运行时（registry / tracer / context）、运行记录、**fake gateway 离线回归**。
- 可审计的会话轨迹，满足 G1 截图豁免的证据要求。

### 2.2 明确不做

- **不计算用户能力星级，不访问或写入 evkg 证据层**（只读零写入，且有自动化断言守着）。
- 不接入 JD 导入、不建内置领域知识库。
- 不做完整 UI；不提前建设通用多 Agent 编排平台。
- 不在 M2 解决归属层设计；但**保留其在 M3/M4 前定稿的依赖门槛**。
- 不修改 evkg 仓库；不新增进程级 profile 用法。

---

## 3. 数据与设计约束（冻结，实现须照此）

### 3.1 数据结构（检查 2 的落地）

`g_capabilities`（ARCHITECTURE §4.3 基础上增补）：

| 字段 | 规则 |
|---|---|
| `id` | **稳定逻辑标识**：`cap_<sha256(goal_id + "/" + path + "/" + normalize(name))[:20]>`。与生成批次、模型、时间无关 —— 再生成走 upsert，不得重复累积（M1-b.5c 的教训：id 含内容/批次会导致静默累积） |
| `parent_id` / `path` / `depth` | `depth ∈ {1,2,3}`（领域 / 能力组 / 能力点），≥3 个 `depth=1` 领域、≥12 个 `depth=3` 能力点 |
| `target_level` | 目标要求值（**建议值**），非用户现状 |
| `origin` | `generated` \| `adjusted`。**`adjusted` 行在再生成时 target_level 与 adjustment_note 一律保留** |
| `verification_status` | `unverified` \| `verified`。M2 一律写 `unverified`；不得把 LLM 生成描述成行业标准 |
| `source_note` | 来源说明（如"LLM 生成，未校验外部来源"） |
| `adjustment_note` | 人工调整的来源/理由（`origin=adjusted` 时必填） |
| `generated_by_run_id` | 指向 `g_agent_runs.id`，用于可追溯（AC9） |
| `current_level` | M2 **恒为 NULL**（不推断现状） |
| `current_level_status` | M2 恒为 `unassessed`（**显式状态**）。禁止用 0、`target_level` 或任何数字代替 —— 沿用 M1-b.5b「缺失 ≠ 低分」的语义 |
| `weight` | M2 置 NULL（不发明数字；M4 需要时再定） |

`g_agent_runs`（ARCHITECTURE §4.3 基础上增补，C2）：

| 字段 | 规则 |
|---|---|
| `provider` / `model` | **必须取自实际执行的 gateway 返回值**（`ModelResult.provider/model`），不得读配置默认值或预设标签 |
| `model_source` | `result`（成功，来自返回值）\| `config_on_error`（失败，来自当时的 gateway 配置并明确标注） |
| `status` | `ok` \| `error`；失败运行同样落库，`error` 保留可诊断信息（M1-g 教训：失败不能只存在于控制台） |
| 既有字段 | `agent` / `input` / `tool_calls_json` / `output` / `tokens` / `latency_ms` / `created_at` |

`g_goals` / `g_goal_clarifications`：按 ARCHITECTURE §4.3；`round` 从 1 递增，
`confirmed` 只能由显式确认动作产生并记录 `source_quote`。

### 3.2 边界守卫的收窄与补偿（检查 4 的落地）

M1 的 `tests/test_adapter_boundary.py::test_no_package_module_touches_sqlite_directly` 是
**全包**禁用 `sqlite3` 与裸 SQL —— 与 M2 自建 `g_` 表直接冲突。收窄方案（必须同时落地补偿检查）：

| 动作 | 内容 |
|---|---|
| 收窄 | 该检查改为：**证据层（`evidence/` 全部模块，含 adapter）保持全禁**；仅 `backend/growth_os/store/` 允许 `sqlite3` 与裸 SQL |
| 补偿 1 | 新增 `test_growth_store_only_touches_g_tables`：`store/` 内 SQL 中 FROM/INTO/UPDATE/JOIN 后的表名必须全部 `g_` 前缀（静态提取） |
| 补偿 2 | 新增 `test_m2_flow_does_not_write_evkg_tables`（功能断言）：在临时库上跑完 M2 流程（fake gateway），**evkg 表族计数必须全为 0** |
| 保留 | "只有 adapter.py 可 import evkg"（D1）对全包继续生效 → `store/` 天然不得 import evkg |

### 3.3 网关接缝与离线回归（检查 3 的落地，C3）

- 运行时依赖 Protocol：`async structured(*, system, user, schema, task) -> ModelResult`；
  默认实现由**适配层工厂**给出（读取 `GROWTH_AGENT_*` 并作为**实例级 overrides** 传入，
  不写进程级 env 覆写；M1-g 已验证 `ModelGateway` 的 overrides 是实例级安全路径）。
- 测试注入 fake（同 Protocol）：成功 / 失败 / 异常三条路径都要有（C2）。
- 离线三保险：① 注入 fake 后不发生真实调用；② 测试运行时清空 `EVKG_API_KEY` /
  `OPENAI_API_KEY` / `GROWTH_AGENT_*`；③ fixture 断言 `httpx.AsyncClient` 未被实例化。

---

## 4. 交付物（文件级）

| # | 交付物 | 说明 |
|---|---|---|
| 1 | `backend/growth_os/store/growth_store.py` | `g_` 表建表（幂等）与读写；**只碰 `g_` 前缀表** |
| 2 | `backend/growth_os/agent/runtime.py` | 最小运行时：工具注册、上下文装配、轨迹记录（含实际 provider/model） |
| 3 | `backend/growth_os/agent/gateway.py` | `StructuredGateway` Protocol + fake 实现（测试用） |
| 4 | `backend/growth_os/goal/agent.py` | Goal Agent + 澄清状态机 + 轮次上限与确认语义 |
| 5 | `backend/growth_os/goal/capability_model.py` | 能力树生成、人工调整、再生成保护、来源/校验标注 |
| 6 | `backend/growth_os/evidence/adapter.py`（增补） | 暴露网关工厂；边界检查允许清单同步更新 |
| 7 | `tests/test_agent_runtime.py`、`test_goal_clarification.py`、`test_capability_model.py`（+ 边界检查增补） | 见 §5 |
| 8 | `artifacts/m2/`、`artifacts/gates/G1/` | 会话运行器、轨迹导出、能力树快照、G1 判定与豁免记录 |
| 9 | 文档 | 本文件；`DECISIONS.md` 增补；`PROJECT_FEATURES.md` 状态推进 |

---

## 5. 验收标准与逐项映射（检查 1 的落地）

### 5.1 硬性（ROADMAP 完成条件 + G1）

| ID | 验收标准 | 自动化验证 | 归档证据 |
|---|---|---|---|
| AC1 | ≤6 轮产出 confirmed goal，含四要素 | `test_goal_clarification.py::test_converges_within_six_rounds`（fake gateway 确定性会话） | `artifacts/gates/G1/session-*.json` + `g_goals` 记录 |
| AC2 | 未确认不得进入能力分析（硬约束） | `test_capability_model.py::test_unconfirmed_goal_is_rejected`（负面用例） | 测试输出 |
| AC3 | ≥3 领域、≥12 能力点；每点有 `target_level` + 来源 + 校验状态 | `test_capability_model.py::test_tree_shape_and_metadata` | `artifacts/m2/capability-tree-*.json` |
| AC4 | `adjusted` 不被再生成覆盖（**C1**） | `test_capability_model.py::test_adjusted_value_survives_regeneration` | 测试输出 + 再生成前后快照 |
| AC5 | G1 通过（含两条反例：直接落模糊目标 / 未确认就进能力分析） | 反例写成自动化测试；正例由真实会话产出 | `artifacts/gates/G1/README.md`（判定 + 截图豁免记录与补证计划） |
| AC6 | 全量回归 + lint | Growth OS 全部测试 + evkg 101 项 + `ruff` 不新增 | 命令输出 |
| AC7 | LLM 路径离线可回归（**C3**） | `test_agent_runtime.py`（fake gateway；无网络无密钥；httpx 阻断断言） | 测试输出 |
| AC8 | `g_agent_runs` 记录**实际** provider/model + 状态 + 错误（**C2**） | `test_agent_runtime.py::test_run_records_model_from_result`、`test_failed_run_is_recorded_with_error` | `g_agent_runs` 导出（成功/失败各一） |
| AC9 | `capability → goal → agent_run` 可追溯 | `test_capability_model.py::test_lineage_is_queryable` | `artifacts/m2/lineage-*.json` |
| AC10 | 第 7 轮必须失败或降级为 `proposed` | `test_goal_clarification.py::test_seventh_round_is_rejected` | 测试输出 |
| AC11 | 能力点不得伪装已验证；人工修改保留修改来源 | `test_capability_model.py::test_unverified_marking_and_adjustment_source` | tree 快照 |
| AC12 | **不触碰 evkg 证据层** | `test_adapter_boundary.py`（收窄后）+ `test_m2_does_not_write_evkg_tables`（零写入断言） | 测试输出 + 计数快照 |

### 5.2 质量门（沿用 M1 纪律）

- QG1 `audit_store` = pass（M2 不改证据层，跑一次确认"零写入"即可）；
- QG4 无密钥入库：`.env` 已 gitignore；运行记录不含密钥；
- lint 不新增；测试计数只增不减。

---

## 6. 补充约束 C1–C3（冻结，含验收方式）

| 编号 | 约束 | 验收方式 |
|---|---|---|
| **C1** | **重新生成不得覆盖人工修改**：明确能力点稳定标识、`origin` 与覆盖规则 | 修改某能力点后重新生成，验证修改值仍在；且 `target_level`/`adjustment_note` 逐字段不变（AC4） |
| **C2** | **运行记录必须可追溯**：`g_agent_runs` 持久化实际 provider/model、运行状态、关联标识与必要错误信息；**provider/model 必须来自实际执行的 gateway 配置，而非默认值或预设标签**；失败运行也要有可诊断记录 | fake gateway 跑成功、失败、异常三条路径，检查记录完整性（AC8）；`model_source` 区分 `result` 与 `config_on_error` |
| **C3** | **离线回归与真实模型留档分离**：fake 用于确定性自动化测试；真实模型用于生成效果验证 | 离线测试不依赖外网与真实密钥（三保险，§3.3）；真实运行单独留档于 `artifacts/m2/` 与 `artifacts/gates/G1/` |

---

## 7. 工作分解

| 步骤 | 内容 | 完成条件 |
|---|---|---|
| M2-a | `g_` 四表 + `growth_store` + 最小运行时 + 网关接缝/ fake + 边界守卫收窄与补偿检查 | 表可建可读回；轨迹含实际 provider/model；fake 注入就位；AC7/AC8/AC12 通过 |
| M2-b | Goal Agent + 澄清状态机（轮次上限、确认语义、拒绝未确认的能力分析） | AC1/AC2/AC10 通过（含负面用例） |
| M2-c | 能力树生成 + 人工调整与再生成保护 + 来源/校验标注 | AC3/AC4/AC9/AC11 通过 |
| M2-d | G1 证据产出（真实模型会话留档）+ 收口 | AC5/AC6 + 账本更新 + 全量回归 |

---

## 8. 风险与前置

- **前置**：无（5 项决策已确认；R5 已按"纯 LLM + 未校验标注"冻结）。
- 归档第三副本（抗物理损坏）仍是用户动作，与 M2 无关。
- LLM 输出结构不稳定 → 结构化 schema + 重试 + 失败留档（沿用 M1-c 做法）。
- 边界守卫收窄是**有意的、被补偿检查约束的**改动 —— 评审时必须同时看到三项补偿（§3.2），
  否则视为放宽了 D1 边界。
- 若真实会话在 ≤6 轮内不收敛 → 调整提问策略而非放宽上限（上限是硬约束）。
