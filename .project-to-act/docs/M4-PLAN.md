# M4 目标与范围（v0.1 · **范围冻结草案 —— 待用户确认**）

> 状态：**草案（2026-10-02）**。本文件只冻结**范围与判定方式**；按用户指定，
> **不写代码、不跑实验**。用户确认后转 v1.0 执行基线，再进入 M4-a。
>
> 依据：`ROADMAP.md` M4 · `PRD.md` §8/§9/§10/§20/§33（2)(3) · `ARCHITECTURE.md` §3/§4.3/§5.3/§6 ·
> `ACCEPTANCE_GATES.md` G2/G3 与 QG1–QG5 · `M1-SPIKE-CONCLUSION.md`（有条件依赖 C1–C5，尤 **C5**）·
> `M2-PLAN.md`（决策 4/5、遗留"再生成并集语义"）· `M3-PLAN.md` v1.0（硬规则、归属层、通道隔离、Gate 结果）·
> `DECISIONS.md`（M3 收口 / M3-e 历史越权决定 / 未决清单）
>
> 上游输入：M3 已收口（Gate 通过，EV-065）；历史越权主张处理决定（用户 2026-10-02，真实库不动）。

---

## 0. 一句话定义

> **M4 把"材料口径的证据"转成"有证据依据的能力判断"：对目标能力树上的能力点给出星级，
> 并显式回答"用户声明是否被证据支持"——但不生成任务、不做 UI。**

```text
M3（已收口）: 材料 → Source → Passage → Evidence → 材料口径 Claim → audit / provenance
M4（本步）  : 材料口径 Claim（+归属/通道） → 证据准入与分桶 → 规则引擎
              → Assessment（星级 + 为什么） → Gap（缺什么）
M5         : Gap → Task → 新证据 → 重新评估
```

M4 是产品**立身之本**（PRD §33 第 3 条）的落地点，也是全项目最高的风险点之一：
做假的方式很多（把 confidence 当星级、把"材料存在"当"用户会"、把无证据说成低能力），
因此验收门 G2/G3 用**抽样追溯 + A/B 对照实验**判定，不采信单点观察。

---

## 1. 硬边界（全部继承，M4 不得重开）

| # | 边界 | 来源 |
|---|---|---|
| 1 | **"存在证据" ≠ "证明能力"**：M4 的产物只能是 **assessment**（对能力点的现状判定，带等级、理由与支撑链），**不得反写回证据层**，不得再产生"用户具备 X"式 claim | `M3-PLAN.md` §1 |
| 2 | 归属三取值与消费规则：仅 `user_declared` + `user_evidence` 可支撑用户能力判定；`user_asserted` 只能作弱证据、**不得单独支撑结论**；`unknown` / `domain_reference` 不参与 | `M3-PLAN.md` §3；`attribution.can_support_user_claim` |
| 3 | **D6：星级不得由 `confidence` 线性映射**；由 G3 的 A/B 对照实验强制验证 | `DECISIONS.md` D6；`ARCHITECTURE.md` §3 |
| 4 | L1/L2 分层：星级规则属 Growth OS 自建层（规划位 `growth/assessment.py`），证据层不改、不 import | `ARCHITECTURE.md` §2 |
| 5 | 历史越权主张：**真实库保持原样**；若需机器化审计，产出**独立 audit artifact**，不得写回原始 evidence store | `DECISIONS.md`（M3-e 收口决定） |
| 6 | evkg 为**有条件依赖**：C1–C5 继续生效；**C5 —— 抽取模型持久化必须在 M4 验收前解决** | `M1-SPIKE-CONCLUSION.md` §6.3 |
| 7 | 数据边界：判据为**逐表内容哈希 + 计数**（不用文件哈希）；真实库零污染；G3 实验在独立库上进行 | `M3-PLAN.md` §6.2 第 10 条 |
| 8 | 已知限制如实带过：段落替换是**硬删除**（见 `DECISIONS.md` 未决清单），M4 只能评价"当前证据图能支持什么"；`supersede` 历史模式在 M4 之后实现 | `DECISIONS.md` 未决 |

---

## 2. 冻结点 1：G2 / G3 判定方式

### 2.1 形式门（沿用 `ACCEPTANCE_GATES.md`，不改判定标准）

| 门 | 判定 | 证据 |
|---|---|---|
| G2 · Evidence Traceability | 随机抽 **5 条 assessment**，每条沿 `assessment → claim → evidence → passage → source` 逐字追溯到原文；`audit_store` 9 项不变量 0 violation | 逐跳追证明细 ×5 + `audit_store=pass`；解释输出走 **Growth OS 自建渲染器**（C2：不用上游 `render_claim_markdown`）；`artifacts/gates/G2/` |
| G3 · Capability Audit | **A/B 对照实验**：A（仅自述 + 笔记，无代码/项目/任务）→ 理解 ≥ ⭐⭐、实践 ≤ ⭐，且理由显式指出"缺少实践证据"；B（补充含实现的 GitHub 项目）→ 实践星级比 A **≥ +2 级** | 两份 assessment + 两份解释输出 + 输入源清单；`artifacts/gates/G3/` |

> G3 必须 A、B **同时**成立：只有 A 通过可能是"分数都低"，只有 B 通过可能是"分数都高"。

### 2.2 内部拆成两个判定问题（实现与测试按此拆，呼应"拆开"的判断）

**问题 A —— "一个能力判断是否有足够证据支持？"（关注可追溯性与充分性）**

```text
assessment.level
   ↓ 每一跳都必须存在且可核对
claim（材料口径） → evidence（逐字 quote） → passage → source（含归属/通道标签）
```

规则要点：
- **fail-closed**：证据链走不通、或支撑桶为空 → 不产出星级（`unassessed` / "证据不足"），
  而不是给低分（沿用 M1-b.5b「缺失 ≠ 低分」）；
- 每个 assessment 的 `rubric_json` 记录四桶贡献（知识 / 行为 / 实践 / 任务）与**缺口**，
  反向证据（refutes / disputed）单独列出；
- 判定样本必须 ≥5 条（G2 要抽 5 条）。

**问题 B —— "用户声明能力是否被证据支持？"（关注区分能力，支撑 G3）**

| 类型 | 示例 | M4 结果 |
|---|---|---|
| 用户声明 + 项目证据 | "我实现了 RAG 系统" + GitHub 项目材料 | **可进入审计**（仍须看证据桶是否覆盖目标等级） |
| 用户声明、无证据 | "我熟悉 Agent"（仅聊天自述） | **不足**：输出分离结论（理解 / 实践分开），显式指出缺哪类证据 |
| 材料存在但非用户归属 | JD 要求 Agent / 第三方资料 | **不支持**（通道/归属准入否决） |
| 用户计划 | "准备学习 LangChain" | **非能力证据**（延续 M1-c「严禁升级」） |

**GitHub 例（两个概念不能混）**：`attribution=user_declared` 只说明"材料是用户交出来的"；
它**不**自动给出 `claim:"用户掌握 RAG"` —— 材料到能力维度仍须经**显式映射 + 证据桶判定**（见 §3.3）。

### 2.3 判定纪律

- **星级由确定性规则引擎产出**（同输入同输出、可离线回归）；LLM 只用于
  ① evkg 攻击的独立 verifier（沿用 M1-d 机制）、② 解释文本与映射候选的草稿 ——
  **LLM 不得直接决定 level**（R6 的稳定性风险因此不进定级路径）。
- 负结论措辞：说"**证据不足 / 缺少实践证据**"，不说"能力不足"（低数据量启动原则，`ARCHITECTURE.md` §6.1）。
- 评估后 `audit_store` 必须保持 `pass/0`（QG1）。

---

## 3. 冻结点 2：Assessment 归属模型（capability ownership）

### 3.1 三个不能混的概念

| 概念 | 归属 | 回答的问题 | 落点 |
|---|---|---|---|
| **source attribution** | M3 已有 | 这份**材料**是不是用户交出来的 | `Source.metadata.growth_attribution` |
| **claim scope** | M3-e 已有 | 这条 **claim** 说的是材料还是用户 | `claim.metadata.growth_claim_scope = material` |
| **capability ownership** | **M4 新增** | 这条判断说的是**谁**的**哪项**能力 | `g_assessments(user_id, capability_id)` + `g_capability_claims` |

三者是递进的过滤链，不是同一个标签：材料属于用户 ≠ claim 有资格 ≠ 能得出该能力点的等级。

### 3.2 判定对象与主体

- **对象** = `g_capabilities` 中的**能力点**（`depth=3`，来自 confirmed goal 的目标树）；
  M4 只评估 `status=active`（见 §4）的能力点，评估必须绑定 `goal_id`。
- **主体** = `user_id`（单用户 `local`）；"用户会 X"的结论只以 assessment 形式存在于 L2，
  不写回证据层、不生成新的用户口径 claim。
- M2 语义的衔接：`target_level` 是**目标要求**、`current_level` M2 恒 NULL / `unassessed`；
  **M4 是第一个允许写 `current_level` / assessment 的里程碑**，每次写入必须携带
  rubric、支撑 claim 列表与证据链标识，且可被 `test_traceability` 复核。

### 3.3 证据准入（admissibility）——合取链，fail-closed

一条证据要进入某个能力点的评估，必须**同时**满足（任一不满足即不进入，不做"差不多"放行）：

1. `channel = user_evidence`；
2. `attribution = user_declared`（`user_asserted` 只进"弱证据备注"且**不得单独支撑任何 ≥2 的判定**；`unknown` 不进）；
3. 该 claim 是**材料口径**（`growth_claim_scope=material`）；
4. 证据链完整：`claim → evidence → passage → source` 逐跳存在；
5. 不属于越权表述、且未被攻击推翻（`broken`）。

**分桶映射**（PRD §10 四项 + 反向证据单列）：

| 桶 | 来源（`growth_evidence_type`） | 说明 |
|---|---|---|
| 知识 knowledge | `uploaded_doc`、`chat_assertion`（弱） | 笔记 / 论文 / 自述解释 |
| 行为 behavior | `probe_result` | 系统现场出题、用户作答 |
| 实践 practice | `repo_artifact` | GitHub / ZIP 项目代码 |
| 任务 task | `task_submission` | M5 起产生（M4 阶段可为空） |
| 反向 reverse | attack `refutes` / `disputed` | 只压低、不抬升 |

映射表在 M4-a 冻结为常量 + 测试（沿用 M1-b.5b 的"缺失值不参与加权"语义：空桶 ≠ 0 分证据）。

### 3.4 与 M3 产物的关系（不重开 M3）

- M3 已有 5 条材料口径 claim + 完整证据链 + 归属/通道标签 —— 这就是 M4 的输入，不重做。
- 历史主张按 M3-e 决定处理，**不再改库**：
  - `clm_f138…`（判越权）：M4 按"越权 / 不成立"处理，不进入 supports；机器化清单写入
    **独立 audit artifact**（`artifacts/m4/`），不写回 store；
  - `clm_29f5…`（计划学习）：按 `user_asserted` 弱证据 + 计划语义处理 —— 非能力证据，不进任何等级支撑。

---

## 4. 冻结点 3：M2 再生成语义（M4 前置决策）

### 4.1 现状与问题（M2 实测）

稳定逻辑 id（`goal_id + path + normalize(name)`）保证"同名不重复"、`adjusted` 受保护；
但**两次生成命名不同会累积节点**（真实会话两次生成合并为 49 个节点）。
M4 的 assessment 要绑定能力点，因此必须在 M4-a 前定：再生成是**替换、合并还是保留历史**。

### 4.2 三个方向的后果

| 方向 | 语义 | 后果 |
|---|---|---|
| **replace** | 新树整体替换当前树 | 简单；历史 assessment / gap / task 的外键断裂（需级联删除或丢历史）；与 M6 成长时间线冲突；`adjusted` 保护出现例外 |
| **merge（现状）** | 并集累积 | 不丢调整；同义节点重复（"同一能力两个节点"），评估对象漂移；越积越乱 |
| **history + current view（推荐）** | 保留历史版本 + 维护当前视图 | 引用稳定、可回看；需要一次 schema 变更与再生成迁移规则 |

### 4.3 推荐：history + current view（最小实现）

- `g_capabilities` 增加生命周期：`generation_id`（生成批次）+ `status ∈ {active, superseded, archived}`；**不删除行**；
- 再生成 = 新批次：旧批次中不在新树的 `generated` 节点 → `superseded`；
  **`adjusted` 节点默认保留 `active`**（不自动降级 —— 不覆盖用户意志，延续 C1 纪律）；
- **当前视图 = `status=active`**；assessment 绑定**逻辑 id**，不因再生成断裂；新 assessment 只对 active 节点；
- 与 M6 的关系：成长时间线直接读历史 assessment + 节点状态，无需另造历史表；
- 代价：一次 schema 变更 + 迁移规则 + 回归测试，随 M4-a 一并落地（assessment 表本就要引用节点）。

### 4.4 待确认

> **建议冻结为"方向 3（history + current view）"**；若选 replace 或 merge，需同时给出
> 历史 assessment 的处置规则（级联删除或重建），M4-PLAN 会在 v1.0 前补齐。

---

## 5. 范围

### 5.1 做

- `g_assessments` / `g_gaps` / `g_capability_claims` 建表与读写（`ARCHITECTURE.md` §4.3）；
- 证据准入与分桶（§3.3，确定性、fail-closed）；
- **五星评级规则引擎**：知识 + 行为 + 实践 + 任务 − 反向证据（PRD §10；`ARCHITECTURE.md` §3.4）；
- claim ↔ 能力点映射：**显式、可审计**（谁提出、依据、run id 全部落库；桥表 `role=supports/gap`）；
- 反向证据处理：`refutes` / `disputed` 必须压低评级，攻击结果进入解释（ROADMAP 交付物 5）；
- 评级可解释输出：支持证据 / 不足 / 攻击结果 —— 走**自建渲染器**（C2：不用上游 `render_claim_markdown`），
  输出归档到 `artifacts/gates/G2|G3/`（"为什么我只有三星"的数据形态，UI 留 M8）；
- 缺口识别（`g_gaps`）——只到"缺口"；任务生成留 M5；
- 再生成语义落地（§4 确认后）；
- G2/G3 证据产出：独立库上的 A/B 对照 + 真实运行留档。

### 5.2 不做

- 不生成任务（M5）、不做 UI（M8）、不做 Memory / 主动 Agent（M6/M7）；
- 不修改 evkg 证据存储；不新增用户口径 claim；不改写历史越权主张（§3.4）；
- 不做 `confidence → 星级` 线性映射；星级不由 LLM 直接产出（§2.3）；
- 不引入段落 `supersede` 历史模式（用户已确认方向，M4 之后）；
- 不接 PDF 产品入口、不做页码级 locator（M3 两个开放项保持开放，不阻塞 M4，见 §8）；
- 不做任务质量门 G4/G5（M5）。

> **对 ROADMAP 交付物 2 的落地细化**（请确认）：架构写的"两阶段（摄入 → 审计）"中，
> "摄入"链路已由 M3 完成；M4 阶段一收敛为**证据 → 能力点的绑定**（映射 + 准入闸门），
> 阶段二为**审计**（攻击补充 + 规则评级 + 缺口 + 解释）。

### 5.3 输入与前置

- 输入：M3 材料口径 claim（5 条）+ 证据链 + 归属/通道标签；M2 能力树（真实库 6 领域 / 31 个三层点）。
- **阻塞 Gate（不阻塞 M4-a 开工）**：**C5 抽取模型持久化**（上游最小修 or 本地记录 —— 需选择）。
- **设计冻结前置**：§2 / §3 / §4 三处确认。

---

## 6. 步骤结构（确认后进入 M4-a；仅到步骤级）

```text
M4-a  数据模型与规则引擎骨架（g_ 三表 + 再生成语义落地 + 确定性规则 + fake gateway 离线回归）
      ↓
M4-b  证据准入与绑定（分桶映射、claim ↔ 能力点映射、provenance 逐跳可走）
      ↓
M4-c  攻击与反向证据（evkg 攻击接入；refutes/disputed 压低；攻击结果入解释）
      ↓
M4-d  可解释输出（assessment dossier：支持 / 不足 / 攻击结果）
      ↓
M4-e  缺口识别 + G2/G3 证据产出（独立库 A/B 对照；真实运行留档）
      ↓
M4 Gate（G2 + G3 + 质量门）
```

---

## 7. 验收标准

### 7.1 ROADMAP M4 完成条件（硬性）

1. 对 **≥3 个能力**给出星级，每级可追溯到原始证据（G2 抽样要求实际样本 **≥5 条 assessment**）；
2. **复现 PRD §10 判定**：仅有聊天自述 + 论文笔记，无代码/项目/任务证据 →
   **理解 ≥ ⭐⭐、实践 ≤ ⭐** 的分离结论；
3. 有 GitHub 项目证据时，实践星级**显著高于**上一条（≥ +2 级）；
4. 能回答"为什么是这个星级"：列出支持证据 / 不足 / 攻击结果（PRD §20 的数据形态）；
5. 每次评估后 `audit_store` 仍为 `pass`；
6. 对应验收门 **G2、G3** 通过。

### 7.2 验收项映射（自动化验证 / 归档证据）

| ID | 验收标准 | 自动化验证 | 归档 |
|---|---|---|---|
| AC1 | ≥5 条 assessment，每条逐跳可追溯 | `tests/test_traceability.py`（抽样 + 逐跳校验，失败即红） | `artifacts/gates/G2/` |
| AC2 | PRD §10 决定性用例：弱证据 → 理解 ≥2 / 实践 ≤1 + 显式缺实践证据 | `tests/test_assessment_rules.py`（A 场景） | `artifacts/gates/G3/` |
| AC3 | 强证据 → 实践 ≥ A + 2 | `tests/test_assessment_rules.py`（B 场景） | 同上 |
| AC4 | 每级可解释（支持 / 不足 / 攻击） | 渲染器回归 + 快照 | `artifacts/gates/G2|G3/` |
| AC5 | 评估后 `audit_store = pass/0` | 流程内置 QG1 检查 | 命令输出 |
| AC6 | 准入 fail-closed：`unknown` / `domain_reference` / `user_asserted` 单独来源不进支撑 | `tests/test_assessment_rules.py`（负面用例） | 测试输出 |
| AC7 | 反向证据（refutes/disputed）压低评级 | 确定性用例：同一输入 + 反向证据 → level 下降 | 测试输出 |
| AC8 | 无证据不给星：`unassessed` 与低星显式区分 | 负面用例 + 状态断言 | 测试输出 |
| AC9 | 确定性：同输入同输出（不依赖模型随机性） | 规则引擎重复运行断言 | 测试输出 |
| AC10 | **C5**：评估所依赖的抽取/攻击模型可追溯 | 门检查（claim/run 记录模型名） | `artifacts/gates/G2/` |
| AC11 | 全量回归 + ruff + 数据边界 | Growth OS + evkg 全量、逐表内容哈希与计数（真实库零污染） | 命令输出 |
| AC12 | G2/G3 门判定记录 | 门 README（判定 + 输入源清单 + 豁免） | `artifacts/gates/G2|G3/` |

### 7.3 质量门

- **QG1** 证据不变量：每次评估后 `audit_store = pass/0`；
- **QG2** 攻击自测：沿用 M1-f 的"注入前/后双向测量"口径（不采信内置 `status` 单值，C4）；
- **QG3** 评级规则覆盖：`tests/test_assessment_rules.py` 覆盖决定性用例（含 G3 A/B）——本步建立；
- **QG4** 无密钥入库；**QG5** 全量测试（Growth OS + evkg + ruff）。

### 7.4 数据边界

- G3 的 A/B 对照在**独立实验库**（或临时库）上进行，与真实库物理隔离；
- 真实库判据 = **逐表内容哈希 + 计数**（锚点沿用 `artifacts/m3a/evidence-anchors.json`，M4 结束时更新锚点）；
- 素材如实标注：A/B 场景中"同一用户"为受控构造；可复用本机真实项目与真实笔记，
  构造部分必须在产物中标注（沿用 M3-d 对合成 JD 的处理纪律）。

---

## 8. 风险与开放问题（需在 v1.0 前确认）

1. **三处冻结确认**：§2（G2/G3 拆问与纪律）、§3（capability ownership 与准入链）、§4（再生成语义推荐方向 3）。
2. **C5 解法选择**：抽取模型持久化 —— 上游最小修（仿 B-g2 先例）或本地记录（把模型名写进 claim metadata）。
   不解决则 M4 Gate 无法通过（C5 是写死的门检查）。
3. **G3 A/B 素材来源**：建议用本机真实材料（`mytset-rag` 项目、真实笔记/聊天）+ 受控构造，
   在独立库运行；构造部分如实标注。
4. **映射提出者**：claim ↔ 能力点的绑定由谁提出 —— 建议"LLM 提议 + 确定性闸门校验 + 全量记录"
   （或纯规则匹配）；无论哪种，**最终定级必须是规则引擎**。
5. **M3 两个开放项保持开放、不阻塞 M4**：PDF 适配层 V1 入口（产品上传链路未完成）、
   页码级 locator（上游第 14 项）。M4 的输入是已入库证据，不依赖新上传入口。
6. **R6（中文 prompt 稳定性）**：因定级不依赖 prompt（§2.3），风险降到"解释文本质量"层面，
   由渲染回归覆盖。

---

## 9. 开工前检查（设计级，进入 M4-a 前必须通过）

| # | 检查 | 状态 |
|---|---|---|
| 1 | 验收标准逐项可映射到测试或归档证据 | **已做**（§7.2，12 项全覆盖） |
| 2 | 数据结构能区分目标要求 / 用户现状 / 未评估 | **已具备**（M2：`target_level` / `current_level` / `current_level_status`）+ M4 增补三表与生命周期字段 |
| 3 | fake gateway 离线回归可独立运行（无网络无密钥） | **可复用**（M2-a 的三保险接缝） |
| 4 | 代码变更不越界（证据层零写入、独立实验库、`g_` 前缀守卫） | **可复用**（M2-a 的守卫与补偿检查） |
| 5 | 再生成语义冻结后才写入 assessment 外键 | 待 §4 确认 |
