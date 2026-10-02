# M2 目标与范围（草案 v0.1 · 待用户确认）

> 状态：**草案，未开工**。确认后本文件转为 M2 的执行基线；未确认项不得进入实现。
>
> 依据：`ROADMAP.md` M2（目标/交付物/完成条件）· `PRD.md` §16 目标澄清、§17 首次使用流程、
> §24/§25 能力模型来源 · `ARCHITECTURE.md` §3 桥梁、§4.3 `g_` 表族、§5.3 Goal Agent、
> §6.1 首次使用、§8 风险 **R5** · `ACCEPTANCE_GATES.md` **G1**（含反例）。
>
> 边界声明：M1 已完成并归档，本文件不重开 M1 的任何结论；M2 不需要修改 evkg
> （只经适配层复用其 `ModelGateway`，且用**实例级 overrides**——M1-g 已验证为安全的部分）。

---

## 1. 目标

把一句模糊目标变成两样可读回、可调整、可验收的产物：

1. **一个 confirmed goal** —— 含四要素：方向 / 目的 / 时间周期 / 可衡量结果（PRD §16）；
2. **第一版动态能力模型** —— ≥3 个领域、≥12 个能力点，每个能力点带 `target_level`，
   可由用户人工调整且不被后续再生成覆盖（`origin=adjusted`）。

一句话：**从"我想成为 AI Agent Engineer"到"一个可用的能力树"。**

---

## 2. 范围

### 2.1 做

| 项 | 内容 |
|---|---|
| 数据 | `g_goals` / `g_goal_clarifications` / `g_capabilities` / `g_agent_runs` 四张表建表与读写（其余 `g_` 表留给 M3+） |
| 运行时 | 最小 Agent 运行时（D4）：ToolRegistry + ContextAssembler + Tracer，轨迹落 `g_agent_runs` |
| 澄清 | Goal Agent + 状态机 `draft → clarifying ⇄ proposed → confirmed`；**未确认不得进入能力分析** |
| 能力模型 | 给定 confirmed goal → 生成能力树；支持人工调整；再生成不覆盖 `adjusted` 节点 |
| 网关 | 适配层新增对 `ModelGateway` 的暴露（沿用单一 import 边界），使用**实例级 overrides** 承载 `GROWTH_AGENT_*` 配置 |
| 证据产出 | G1 所需的完整往返轨迹导出（`artifacts/gates/G1/`） |
| 测试 | `tests/test_goal_clarification.py`、`tests/test_capability_model.py`、`tests/test_agent_runtime.py` |

### 2.2 不做（明确排除，防范围蔓延）

- **证据收集与星级评估**（M3/M4）—— M2 不产生任何"用户能力星级"，能力模型的
  `target_level` 是"目标要求"，不是"用户现状"。
- **归属层**（项目存在 ≠ 用户个人实现）—— M2 不接触用户证据，**不阻塞**；
  它必须在 M3（用户证据进入）与 M4（能力审计）之前定稿。
- **UI**（M8）—— G1 的"会话截图"证据形式需要单独确认，见 §5 决策 2。
- **evkg 证据层写入**：M2 不 ingest、不 extract、不切换 profile，因此 D1 的
  进程级 profile 风险在 M2 不触发。
- 多用户、登录（Q4 已定单用户本地优先）。

---

## 3. 交付物（文件级）

| # | 交付物 | 说明 |
|---|---|---|
| 1 | `backend/growth_os/store/growth_store.py` | `g_` 表建表与读写（幂等迁移；与 evkg 表族同库不同前缀，D2） |
| 2 | `backend/growth_os/agent/runtime.py` | 最小运行时：工具注册、上下文装配、轨迹记录（含真实 provider/model） |
| 3 | `backend/growth_os/goal/agent.py` | Goal Agent + 澄清状态机 + 轮次上限与确认语义 |
| 4 | `backend/growth_os/goal/capability_model.py` | 能力树生成、人工调整、再生成保护 |
| 5 | `backend/growth_os/evidence/adapter.py`（增补） | 暴露 gateway 工厂；边界检查允许清单同步更新 |
| 6 | `tests/test_agent_runtime.py`、`test_goal_clarification.py`、`test_capability_model.py` | 见 §4 |
| 7 | `artifacts/m2/` + `artifacts/gates/G1/` | 会话运行器、轨迹、能力树快照、G1 判定记录 |
| 8 | 文档 | 本文件定稿；`DECISIONS.md` 增补 R5 选型与 G1 证据形式；`PROJECT_FEATURES.md` F-001/F-002 状态推进 |

---

## 4. 验收标准

### 4.1 ROADMAP 完成条件 + G1（硬性）

1. 输入模糊目标，系统在 **≤6 轮**内产出 confirmed goal，且含{方向, 目的, 时间周期, 可衡量结果}。
2. **未确认不得进入能力分析**：`status != confirmed` 时调用能力模型生成必须被拒绝
   （要有**负面测试**，不能只测 happy path）。
3. 能力树落库并可读回；**≥3 领域、≥12 能力点**；每个能力点有 `target_level`。
4. 能力模型可人工调整（`origin=adjusted`）**且不被下次生成覆盖**（要有回归测试）。
5. **G1 通过**（含反例：直接落库模糊目标、或未确认就进入能力分析 —— 两种都必须不通过）。

### 4.2 本步质量门（沿用 M1 纪律，且针对 M1-g 的 R3 盲区补强）

6. 全量回归：Growth OS 全部测试 + evkg 101 项全绿；`ruff` 不新增。
7. **LLM 路径必须可离线回归**。M1-g 的覆盖实测（EV-046）显示 LLM 路径无自动化测试；
   M2 起改变这一点：Agent 与能力模型生成的测试通过**注入 fake gateway** 实现确定性、
   无网络的自动化回归，与真实模型运行（留档）分开记录。
8. `g_agent_runs` 必须记录**实际使用的 provider/model**（必要时含 prompt 版本）；
   不允许重蹈 M1-g 发现的"抽取模型未持久化"（缺陷 #2）。
9. 可追溯性：任一能力节点都能沿 `capability → goal → agent_run` 走通；
   能力模型的生成输入（goal + 参考来源标注）与输出都可读回。
10. 轮次上限是硬约束：第 7 轮必须失败或降级为 `proposed`，不得静默继续追问。

---

## 5. 待用户确认的决策（确认后本文件才生效）

| # | 决策 | 选项与推荐 |
|---|---|---|
| 1 | **R5：能力模型的"外部知识"来源**（ARCHITECTURE §8 要求 M2 前冻结） | (a) 内置领域能力图谱种子；(b) 用户上传 JD/文档（最小版）；(c) **纯 LLM 生成 + 显式标注"未校验"**。<br>**推荐 c 起步**：M2 先把闭环与"来源可追溯"跑通，能力点标注来源与校验状态、`target_level` 标为 LLM 建议值；b 随 M3 接入；a 视实际需要再补。R5 的实质风险是"来源不明/质量不稳"，本步应保证**可见与可改**，而不是先建知识库。 |
| 2 | **G1 的"会话截图"证据形式** | M2 无 UI。建议接受"完整会话轨迹导出"（`g_goal_clarifications` + `g_agent_runs` + 会话文本）替代截图，并在 G1 记录中标注豁免，M8 补界面截图。<br>若不同意，M2 需追加最小可交互界面，范围显著变大。 |
| 3 | **最小 Agent 运行时的范围** | 建议 M2 落地最小版（registry + tracer + context，加 `g_agent_runs`），避免 M4 大改；另一选项是先写函数、M4 再重构（更快但返工）。 |
| 4 | **`target_level` 的产生方式与能力树形态** | 建议：LLM 建议 + 用户可调（调整记 `origin=adjusted`）；树最多 3 层（领域 → 能力组 → 能力点）。 |
| 5 | **首版能力模型是否纳入"已有能力"**（PRD §25 四要素之一） | 冷启动时为空。建议 M2 固定为空并在模型上标注"尚未评估"，M4 回填；避免在无证据时编造现状。 |

---

## 6. 建议的工作分解（确认后执行）

| 步骤 | 内容 | 完成条件 |
|---|---|---|
| M2-a | `g_` 四表 + `growth_store` + 最小运行时（含 model/provider 轨迹） | 表可建可读回；轨迹含真实模型标识；fake gateway 注入机制就位 |
| M2-b | Goal Agent + 澄清状态机（轮次上限、确认语义、拒绝未确认的能力分析） | 单元测试 + 负面测试通过；≤6 轮可复现 |
| M2-c | 能力树生成 + 人工调整与再生成保护 | ≥3 领域/≥12 点；`adjusted` 不被覆盖的回归测试 |
| M2-d | G1 证据产出（真实模型会话留档）+ 收口 | G1 判定（含反例）+ 全量回归 + 账本更新 |

---

## 7. 风险与前置

- **前置**：决策 1（R5）未定则不开工；决策 2 决定 M2 是否包含界面工作。
- LLM 输出结构不稳定 → 结构化 schema + 重试 + 失败留档（沿用 M1-c 的做法）。
- "轮"的计数与"确认"的落库语义易含糊 → 在 M2-a 写死并用测试锁定（`round` 自增、
  `confirmed` 需显式用户动作 + `source_quote`）。
- 若决策 2 不接受轨迹替代截图 → M2 范围显著变大，需重排里程碑。
