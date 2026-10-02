# M4 目标与范围（v1.0 · **执行基线**）

> 状态：**已冻结（2026-10-02 用户逐项确认）**。确认口径：
> ① G2/G3 判定方式（证据可追溯性门 / 用户声明 vs 证据支持门 + 四类矩阵）；
> ② 归属三层模型（source attribution / claim scope / capability ownership **不合并**）；
> ③ 再生成语义 = **history + current view**（不采用 replace / merge）；
> ④ **C5 = 上游最小修**（evkg 增加抽取 provenance 字段）；
> ⑤ claim ↔ capability mapping = **LLM 提议 + 确定性闸门**；
> ⑥ G3 实验 = **真实材料 + 受控构造 + 独立库运行**；
> ⑦ ROADMAP 交付物 2 由"摄入材料"调整为"**基于已准入证据生成可审计能力评估**"。
>
> 依据：`ROADMAP.md` M4 · `PRD.md` §8/§9/§10/§20/§33（2)(3) · `ARCHITECTURE.md` §3/§4.3/§5.3/§6 ·
> `ACCEPTANCE_GATES.md` G2/G3 与 QG1–QG5 · `M1-SPIKE-CONCLUSION.md`（C1–C5，尤 **C5**）·
> `M2-PLAN.md`（决策 4/5、再生成语义遗留）· `M3-PLAN.md` v1.0（硬规则、归属层、通道隔离、Gate 结果）·
> `DECISIONS.md`（M3 收口 / M3-e 历史越权决定 / 未决清单）
>
> 上游输入：M3 已收口（Gate 通过，EV-065）；历史越权主张处理决定（真实库不动）。

---

## 0. 一句话定义

> **M4 把"材料口径的证据"转成"有证据依据的能力判断"：对目标能力树上的能力点给出星级，
> 并显式回答"用户声明是否被证据支持"——但不生成任务、不做 UI。**

```text
M3（已收口）: 外部材料 → Source → Passage → Evidence → Material Claim
M4（本步）  : Material Claim → Capability Ownership → Assessment（星级 + 为什么） → Gap
M5         : Gap → Task → 新证据 → 重新评估
```

M4 是产品**立身之本**（PRD §33 第 3 条）的落地点，也是全项目最高的风险点之一；
验收门 G2/G3 用**抽样追溯 + A/B 对照实验**判定，不采信单点观察。

---

## 1. 硬边界（全部继承，M4 不得重开）

| # | 边界 | 来源 |
|---|---|---|
| 1 | **"存在证据" ≠ "证明能力"**：M4 的产物只能是 **assessment**，**不得反写回证据层**，不得再产生"用户具备 X"式 claim | `M3-PLAN.md` §1 |
| 2 | 归属三取值与消费规则；**三层概念（source attribution / claim scope / capability ownership）不得合并** | `M3-PLAN.md` §3；§3 本节 |
| 3 | **D6：星级不得由 `confidence` 线性映射**；由 G3 的 A/B 对照实验强制验证 | `DECISIONS.md` D6；`ARCHITECTURE.md` §3 |
| 4 | L1/L2 分层：星级规则属 Growth OS 自建层（`backend/growth_os/assessment/`），证据层不改、不 import | `ARCHITECTURE.md` §2 |
| 5 | 历史越权主张：**真实库保持原样**；机器化审计产出**独立 audit artifact**，不得写回原始 evidence store | `DECISIONS.md`（M3-e 收口决定） |
| 6 | evkg 为**有条件依赖**：C1–C5 继续生效；**C5 已冻结为上游最小修**（§5） | `M1-SPIKE-CONCLUSION.md` §6.3 |
| 7 | 数据边界：判据为**逐表内容哈希 + 计数**；真实库零污染；G3 实验在独立库上进行 | `M3-PLAN.md` §6.2 第 10 条 |
| 8 | 段落替换是**硬删除**（`supersede` 模式在 M4 之后实现）：M4 只能评价"当前证据图能支持什么" | `DECISIONS.md` 未决 |

---

## 2. 冻结点 1：G2 / G3 判定方式（已冻结）

### 2.1 G2 · 证据可追溯性门

* **判断对象**：`assessment` 是否有完整证据链支撑；
* **链路**：

  ```text
  assessment
    ↓
  capability claim
    ↓
  evidence
    ↓
  passage
    ↓
  source
  ```

* **任意一环缺失**：**不生成等级；不补推断；输出 `evidence insufficient`**（fail-closed）。

### 2.2 G3 · 用户声明 vs 证据支持门

* **不判断用户"强弱"**；判断：**用户声称的能力，是否存在允许归属的证据支撑**；
* 四类矩阵（冻结）：

  | 输入 | 结果 |
  |---|---|
  | `user_declared` + `user_evidence` + 完整链路 | **进入 assessment** |
  | `user_asserted` + 无产物 | 只能作为**待验证声明** |
  | `domain_reference` | **不能支撑**用户能力 |
  | 计划 / 学习目标 | **不是能力证据** |

* 形式门量级（沿用 `ACCEPTANCE_GATES.md`，判定标准不改）：
  G2 随机抽 **5 条 assessment** 逐跳追溯；G3 为 **A/B 对照实验**
  （A 弱证据 → 理解 ≥ ⭐⭐、实践 ≤ ⭐，且显式指出缺实践证据；B 强证据 → 实践 ≥ A + 2 级）。

### 2.3 判定纪律

- **星级由确定性规则引擎产出**（同输入同输出、可离线回归）；LLM 只用于
  ① evkg 攻击的独立 verifier（沿用 M1-d 机制）、② 解释文本与映射候选的草稿 ——
  **LLM 不得决定用户能力等级**。
- 负结论措辞："**证据不足 / 缺少实践证据**"，不说"能力不足"（`ARCHITECTURE.md` §6.1）。
- 评估后 `audit_store` 必须保持 `pass/0`（QG1）。

---

## 3. 冻结点 2：Assessment 归属模型（已冻结，三层不合并）

```text
Source Attribution          →  材料是谁提供 / 归属谁        （M3 已有）
        ↓
Claim Scope                 →  这句话在描述材料还是用户     （M3-e 已有）
        ↓
Capability Ownership        →  是否能归属于用户能力         （M4 新增）
```

> **核心规则（保留）**：**GitHub 仓库属于用户账号 ≠ 用户具备仓库中所有能力。**

分工：**M3 解决 `source → evidence → material claim`；M4 才解决 `material evidence → capability assessment`。**

### 3.1 判定对象与主体

- **对象** = `g_capabilities` 中的**能力点**（`depth=3`，来自 confirmed goal 的目标树）；
  M4 只评估 `status=active`（§4）的能力点，评估绑定 `goal_id`；
- **主体** = `user_id`（单用户 `local`）；"用户会 X"的结论只以 assessment 形式存在于 L2；
- M2 语义衔接：`target_level` 是目标要求、`current_level` M2 恒 NULL / `unassessed`；
  **M4 是第一个允许写 `current_level` / assessment 的里程碑**，写入必须携带
  rubric、支撑 claim 列表与证据链标识，可被 traceability 复核。

### 3.2 证据准入（admissibility）——合取链，fail-closed

一条证据要进入某个能力点的评估，必须**同时**满足（任一不满足即不进入）：

1. `channel = user_evidence`；
2. `attribution = user_declared`（`user_asserted` 只作**待验证声明**，不得单独支撑任何 ≥2 的判定；`unknown` 不进）；
3. 该 claim 是**材料口径**（`growth_claim_scope=material`）；
4. 证据链完整：`claim → evidence → passage → source` 逐跳存在；
5. 不属于越权表述；且未被攻击推翻（`broken`）——攻击裁决接入随 **M4-c**（本契约先留字段）。

**分桶映射**（PRD §10 四项 + 反向证据单列）：

| 桶 | 来源（`growth_evidence_type`） | 说明 |
|---|---|---|
| 知识 knowledge | `uploaded_doc`、`chat_assertion`（弱） | 笔记 / 论文 / 自述解释 |
| 行为 behavior | `probe_result` | 系统现场出题、用户作答 |
| 实践 practice | `repo_artifact` | GitHub / ZIP 项目代码 |
| 任务 task | `task_submission` | M5 起产生（M4 阶段可为空） |
| 反向 reverse | attack `refutes` / `disputed` | 只压低、不抬升（M4-c） |

空桶 ≠ 0 分证据（沿用 M1-b.5b「缺失值不参与加权」语义）。

### 3.3 与 M3 产物的关系（不重开 M3）

- M3 的 5 条材料口径 claim + 完整证据链 + 归属/通道标签 = M4 输入，不重做；
- 历史主张（真实库，**不改**）：
  - `clm_f138…`（用户/实现过，判越权）：按"越权 / 不成立"处理，不进入 supports；
  - `clm_29f5…`（用户/计划学习）：按计划语义 —— **不是能力证据**，不进任何等级支撑；
  - 机器化清单写入**独立 audit artifact**（`artifacts/m4*/`），不写回 store。

---

## 4. 冻结点 3：M2 再生成语义 = history + current view（已冻结）

**采用**：

```text
CapabilityRecord
  generation_id
  status: active | superseded | archived
```

**原则（写死）**：

- **不删除历史**；
- **当前视图单独查询 `active`**；
- **assessment 绑定逻辑 capability id**；
- **generation 记录变化来源**。

**不采用**（理由记录在案）：

- `replace`：丢失演化过程；无法解释"为什么能力变化"；
- `merge`（M2 现状）：历史状态污染当前状态；无法回答"现在依据什么"。

落地细节（M4-a 随 assessment 表一并实施）：

- `g_capabilities` 增加 `generation_id` 与 `status`（`active/superseded/archived`，默认 `active`）；
- 再生成 = 新批次：旧批次中不在新树的 `generated` 节点 → `superseded`；
  **`adjusted` 节点默认保留 `active`**（不自动降级，延续 C1 纪律）；
- 当前视图 = `status=active`；新 assessment 只对 active 节点；
- 与 M6 的关系：成长时间线直接读历史 assessment + 节点状态，无需另造历史表。

**落地结果（2026-10-02，M4-a，EV-067）**：`generation_id` / `status` 与 `supersede_missing()`
已落地并有测试（不删除历史、`adjusted` 不自动降级、旧库打开自动补列；当前视图 =
`list_capabilities(goal_id, status="active")`）。**生成器接线留 M4-b**（M2 的生成路径本轮未改）。

---

## 5. C5 前置：抽取 provenance = 上游最小修（已冻结）

**决定**：**上游最小修**（仿 B-g2 先例：发现真实缺陷 → 最小修改 → 增加真实测试 → 本地提交、不推送）。

**问题**：`extract._call` 丢弃 `ModelResult`（`extract.py:86-92`），claim metadata 只写
`{model_claim_id, review_state}`（`:182`），批账本只写计数（`:257-260`）—— 换过模型无法知道
哪条主张由哪个模型产出（M1-g §8.2 复现）。**审计要求结论可复核，所以这是 provenance 缺失。**

**最小范围（写死）**：

- **不改抽取逻辑；不改 claim 结构；只增加 provenance 字段；增加读取测试**；
- 落点：claim metadata 增写 `extractor_provider` / `extractor_model` /
  `extractor_prompt_hash`（抽取 prompt 的确定性哈希）/ `extractor_profile`（领域包名）；
  成功批次的账本 payload 同步记录同一组字段；
- 说明（与用户建议 JSON 的对应）：evkg 的 `ModelResult` 只有 `provider/model`，**没有模型版本概念**，
  故"version"由 `extractor_profile + extractor_prompt_hash` 表达可复现性；键名采用**扁平式**，
  与既有 `verifier_model` / `verifier_independent` 惯例一致（同一读取路径，不引入第二套形状）。
- 读取侧：Growth OS 自建档案渲染器（`evidence/dossier.py`）优先显示记录的抽取模型；
  未记录的旧主张继续如实写"未记录在案"，**不拿当前配置冒充历史事实**。

**落地结果（2026-10-02，M4-a，EV-067）**：evkg 本地提交 `9a21552`（未推送）已实现 ——
字段写入 claim metadata 与成功批次账本；4 项读取测试（evkg 111 项全绿）；
Growth OS 档案渲染器三态显示（已记录 / 材料口径"不适用" / 修复前"未记录在案"）。

---

## 6. claim ↔ capability mapping（已冻结）

```text
Evidence
   ↓
LLM candidate capability mapping      （LLM 提议：能力类别 / 解释 / 关联关系）
   ↓
Rule Gate                            （确定性闸门：§3.2 合取链 + 目标树校验）
   ↓
Capability mapping                   （写入 g_capability_claims；记录提议者与依据）
```

**LLM 可以**：提议能力类别、提议解释、提议关联关系。
**LLM 不可以**：决定用户能力等级、补充不存在证据、修改 attribution。
**最终写入必须经过规则检查。**

- 闸门是确定性的（可离线回归），提议与拒绝都留档（`rationale` + run id）；
- M4-a 落地**契约与闸门**；LLM 提议链路随 M4-b（此时才引入 LLM，且仅提议）。

---

## 7. G3 实验设计（已冻结）

**采用**：`真实材料 + 受控构造 + 独立库运行`。

- 真实材料验证：系统面对真实输入是否保守（复用本机真实项目与真实笔记/聊天）；
- 受控构造验证：边界条件是否有效（构造部分必须在产物中如实标注，沿用 M3-d 合成 JD 纪律）；
- 独立库运行：G3 的 A/B 对照在独立实验库（或临时库）上进行，与真实库物理隔离。

三类输入的预期（与 §2.2 四类矩阵一致）：

| 类型 | 输入 | 进入能力评估 |
|---|---|---|
| A | 用户上传的 GitHub RAG 项目材料 | **可以进入证据审计** |
| B | 用户声明"我会 RAG"、无项目 | **不足（待验证声明）** |
| C | JD（要求 RAG 经验） | **不可作为用户能力** |

形式判定仍按 `ACCEPTANCE_GATES.md` G3：A/B 对照（弱证据组理解 ≥2 / 实践 ≤1 且显式指出缺实践证据；
强证据组实践 ≥ +2）。

---

## 8. 范围

### 8.1 做

- **ROADMAP 交付物 2 调整（已冻结）**：原"摄入材料"已由 M3 完成，M4 阶段收敛为
  **"基于已准入证据生成可审计能力评估"**；
- `g_assessments` / `g_gaps` / `g_capability_claims` 建表与读写（`ARCHITECTURE.md` §4.3）；
- 证据准入与分桶（§3.2，确定性、fail-closed）；
- **五星评级规则引擎**：知识 + 行为 + 实践 + 任务 − 反向证据（PRD §10；`ARCHITECTURE.md` §3.4）；
- claim ↔ 能力点映射（§6：LLM 提议 + 确定性闸门，全量留档）；
- 反向证据处理：`refutes` / `disputed` 压低评级，攻击结果进入解释；
- 评级可解释输出：支持证据 / 不足 / 攻击结果（**自建渲染器**，C2；UI 留 M8）；
- 缺口识别（`g_gaps`）——只到"缺口"；任务生成留 M5；
- 再生成语义落地（§4）；
- G2/G3 证据产出（§7）。

### 8.2 不做

- 不生成任务（M5）、不做 UI（M8）、不做 Memory / 主动 Agent（M6/M7）；
- 不修改 evkg 证据存储；不新增用户口径 claim；不改写历史越权主张（§3.3）；
- 不做 `confidence → 星级` 线性映射；星级不由 LLM 直接产出（§2.3）；
- 不引入段落 `supersede` 历史模式（M4 之后）；
- 不接 PDF 产品入口、不做页码级 locator（M3 两个开放项保持开放，不阻塞 M4）；
- 不做任务质量门 G4/G5（M5）。

---

## 9. 步骤结构

```text
M4-a  Assessment 基础模型与 provenance 前置   ← 已完成（2026-10-02，EV-067）
      ↓
M4-b  证据绑定与分桶（LLM 提议 + 确定性闸门 + 映射落库）
      ↓
M4-c  评定与反向证据（星级规则引擎 + attack 接入 + refutes/disputed 压低）
      ↓
M4-d  可解释输出（assessment dossier：支持 / 不足 / 攻击结果）
      ↓
M4-e  缺口识别 + G2/G3 证据产出（独立库 A/B 对照；真实运行留档）
      ↓
M4 Gate（G2 + G3 + 质量门）
```

**M4-a 边界（用户指定，写死）**：

- **做**：模型契约；**claim/evidence → assessment draft → audit artifact 的最小闭环**；
  C5 上游最小修（provenance 前置，§5）；再生成语义的 schema 落地（§4，与 drafts 同批）；
- **不做**：星级算法；LLM；UI；G3 实验。

---

## 10. 验收标准

### 10.1 ROADMAP M4 完成条件（硬性）

1. 对 **≥3 个能力**给出星级，每级可追溯到原始证据（G2 抽样要求实际样本 **≥5 条 assessment**）；
2. **复现 PRD §10 判定**：仅有聊天自述 + 论文笔记，无代码/项目/任务证据 →
   **理解 ≥ ⭐⭐、实践 ≤ ⭐** 的分离结论；
3. 有 GitHub 项目证据时，实践星级**显著高于**上一条（≥ +2 级）；
4. 能回答"为什么是这个星级"：列出支持证据 / 不足 / 攻击结果；
5. 每次评估后 `audit_store` 仍为 `pass`；
6. 对应验收门 **G2、G3** 通过。

### 10.2 验收项映射（自动化验证 / 归档证据）

| ID | 验收标准 | 自动化验证 | 归档 |
|---|---|---|---|
| AC1 | ≥5 条 assessment，每条逐跳可追溯 | `tests/test_traceability.py`（抽样 + 逐跳校验） | `artifacts/gates/G2/` |
| AC2 | PRD §10 决定性用例：弱证据 → 理解 ≥2 / 实践 ≤1 + 显式缺实践证据 | `tests/test_assessment_rules.py`（A 场景） | `artifacts/gates/G3/` |
| AC3 | 强证据 → 实践 ≥ A + 2 | `tests/test_assessment_rules.py`（B 场景） | 同上 |
| AC4 | 每级可解释（支持 / 不足 / 攻击） | 渲染器回归 + 快照 | `artifacts/gates/G2|G3/` |
| AC5 | 评估后 `audit_store = pass/0` | 流程内置 QG1 检查 | 命令输出 |
| AC6 | 准入 fail-closed（四类矩阵 + 越权不进入） | `tests/test_assessment_contract.py` | 测试输出 |
| AC7 | 反向证据（refutes/disputed）压低评级 | 确定性用例：同一输入 + 反向证据 → level 下降 | 测试输出 |
| AC8 | 无证据不给星：`insufficient_evidence` 与低星显式区分 | 负面用例 + 状态断言 | 测试输出 |
| AC9 | 确定性：同输入同输出（不依赖模型随机性） | 规则引擎重复运行断言 | 测试输出 |
| AC10 | **C5**：抽取 provenance 可追溯（模型 / provider / prompt 哈希 / 领域包） | evkg 读取测试 + 门检查 | `artifacts/gates/G2/` |
| AC11 | 全量回归 + ruff + 数据边界 | 全量测试 + 逐表内容哈希与计数（真实库零污染） | 命令输出 |
| AC12 | G2/G3 门判定记录 | 门 README（判定 + 输入源清单 + 豁免） | `artifacts/gates/G2|G3/` |

> M4-a 只落地其中与模型契约 / provenance / 最小闭环直接相关的部分（AC6 的判定函数、
> AC8 的状态语义、AC10 的读取路径、AC11 的回归），其余随对应步骤落地。

### 10.3 质量门

- **QG1** 每次评估后 `audit_store = pass/0`；
- **QG2** 沿用 M1-f 的"注入前/后双向测量"口径（C4）；
- **QG3** `tests/test_assessment_rules.py` 覆盖决定性用例（含 G3 A/B）——M4-c 建立；
- **QG4** 无密钥入库；**QG5** 全量测试（Growth OS + evkg + ruff）。

### 10.4 数据边界

- G3 的 A/B 对照在独立实验库（或临时库）上进行；
- 真实库判据 = **逐表内容哈希 + 计数**（锚点 `artifacts/m3a/evidence-anchors.json`，M4 结束时更新）；
- 构造素材必须如实标注（沿用 M3-d 纪律）。

---

## 11. 风险与开放问题

1. **攻击裁决接入的时机**：§3.2 第 5 条（`broken` 不进入准入）随 **M4-c** 接入；
   M4-a 的契约先留字段，不假装已覆盖。
2. **映射的提议质量**：LLM 提议可能错配；闸门保证"错配进不了 supports"，但
   提议覆盖率需在 M4-b 用真实材料评估。
3. **M3 两个开放项**（PDF 适配层 V1 入口、页码级 locator）保持开放、不阻塞 M4。
4. **R6（中文 prompt 稳定性）**：定级不依赖 prompt（§2.3），风险降到解释文本质量层面。
5. **`g_capabilities` 生命周期字段**是唯一一次 schema 变更（M4-a）；旧行迁移规则见 §4。

---

## 12. 开工前检查（设计级）

| # | 检查 | 状态 |
|---|---|---|
| 1 | 验收标准逐项可映射到测试或归档证据 | **已做**（§10.2，12 项全覆盖） |
| 2 | 数据结构能区分目标要求 / 用户现状 / 未评估 | **已具备**（M2）+ M4 增补 assessment / 生命周期字段 |
| 3 | fake gateway 离线回归可独立运行（无网络无密钥） | **可复用**（M2-a 三保险接缝） |
| 4 | 代码变更不越界（证据层零写入、独立实验库、`g_` 前缀守卫） | **可复用**（M2-a 守卫与补偿检查） |
| 5 | 再生成语义冻结后才写入 assessment 外键 | **已冻结**（§4），M4-a 与 drafts 同批落地 |
