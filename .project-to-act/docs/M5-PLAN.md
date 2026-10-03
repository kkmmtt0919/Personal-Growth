# M5 目标与范围（v1.0 · **执行基线**）

> 状态：**已冻结（2026-10-03 用户确认）**。范围与四条关键设计约束由用户逐项确认；
> 其余细节为提议值、随本文件冻结（可修订）。冻结记录 EV-072。
>
> **四条关键设计约束（用户 2026-10-03 新增冻结原则）**：
> ① **Task 不是能力判断** —— 任务只负责 `gap → evidence opportunity`，绝不产出 `task → skill score`；
> ② **完成任务 ≠ 自动提升** —— 提升必须经 `submission → evidence → claim → binding gate → assessment`，
>    任务完成只是产生**候选证据**；
> ③ **新证据必须保持 provenance** —— 可反向查询链
>    `task_id → submission → source_id → claim_id → assessment_id → level change`（G5 必须能反查）；
> ④ **M4 rating contract 不修改** —— 只复用已冻结阶梯（`practice 3 → task_submission → 4`；
>    `understanding 2 → probe_result → 3`），M5 不重新定义星级。
>
> 依据：`ROADMAP.md` M5 · `PRD.md` §11/§12/§26 · `ARCHITECTURE.md` §3.4/§4.3/§4.4/§5.3（Growth Agent 模式 A）·
> `ACCEPTANCE_GATES.md` G4/G5 · `M2-PLAN.md`（决定 3：最小运行时）· `M4-PLAN.md`（已封板，EV-066…EV-071）·
> `DECISIONS.md`（LLM 只提议、评级只基于已治理证据、派生数据可重建、缺失 ≠ 低能力）。
>
> 上游输入：M4 已封板（M4 Gate 21/21；G2/G3 通过）。

---

## 0. 一句话定义

> **M5 把 `g_gaps` 的"缺口"变成"能产出证据的任务"，并让提交自动走完
> 「新证据 → 绑定 → 重评」闭环 —— 只做任务闭环，不做 UI、Memory、主动 Agent。**

```text
M4（已封板）: Material Claim → Capability Ownership → Assessment（星级 + 为什么） → Gap
M5（本步）  : Gap → Task → 提交产物 → 新证据 → Claim → Binding Gate → 重新评估（等级变化 + 归因）
M6/M7      : Memory（时间线） → 主动 Agent（事件/提醒）
```

## 1. 硬边界（继承 + M5 新增）

| # | 边界 | 来源 |
|---|---|---|
| 1 | **"存在证据" ≠ "证明能力"**：M5 的提交只产生**候选证据**；等级只能由 M4 规则引擎给出 | `M3-PLAN` §1；M5 约束 ①② |
| 2 | 归属三层（source attribution / claim scope / capability ownership）**不合并** | `M4-PLAN` §3 |
| 3 | **D6**：星级不得由 `confidence` / LLM 判断线性映射；任务完成不改变定级规则 | `DECISIONS.md` D6 |
| 4 | **M4 rating contract 不修改**：`RULES_CONTRACT_VERSION`（`m4c-1`）与阶梯表原样复用 | 用户约束 ④ |
| 5 | 证据只经**单入口**入库（`adapter.ingest_document`）；`GrowthStore` 仍只碰 `g_` 表 | `M2-PLAN` 守卫 |
| 6 | 数据边界：判据 = 逐表内容哈希 + 计数；真实库零写入（G4/G5 在独立实验库） | `M3-PLAN` §6.2 |
| 7 | evkg 为有条件依赖（C1–C5）；**不修改 evkg**，不新增来源类型（`task_submission` 已在既有 6 类） | `M1-SPIKE-CONCLUSION` §6.3 |
| 8 | 任务**不是**学习提醒：不可验收的任务必须被拒或改造（PRD §12） | `ROADMAP` M5 |
| 9 | 缺口 ≠ 建议（继承 M4-e）：任务文本不得复述诊断；"缺什么"只来自 `rubric.gaps` | `M4-e` 决策 |

## 2. 冻结点 A：数据契约

### 2.1 `g_tasks`

| 列 | 语义 | 约束 |
|---|---|---|
| `id` | `task_` + sha256(`gap_id｜deliverable_type｜run_id｜index`) | 同一次生成幂等；跨生成 = 新任务（任务可累积，不是能力点） |
| `user_id` / `goal_id` / `capability_id` / `gap_id` | 主缺口（生成来源，必填）；G4 的"反向映射 ≥1 gap"由主缺口满足 | `gap_id` 必须存在且 `status='open'`（生成时）；`capability_id` 必须 `active` |
| `title` / `objective` | 标题 / 目标（objective 必须表述"产出什么"） | 非空 |
| `deliverable_type` | `markdown` / `code` / `archive` / `probe_answer` | 枚举；决定入库证据类型（§5） |
| `est_minutes` | 预计时长（分钟） | 整数，10–600（G4 只要求"存在且合理"） |
| `acceptance_type` | `artifact_check` / `test_run` / `probe_rubric` | 枚举 |
| `acceptance` | 验收方式文本 | 非空；命中反例模式表即拒（§4） |
| `origin` / `generated_by_run_id` | `generated` / `adjusted`；生成运行 id | 与能力树同款纪律 |
| `status` | `proposed` / `active` / `blocked` / `done` / `abandoned` | 状态机（§4） |
| `blocked_reason` / `abandoned_reason` | 原因 | 进入 `blocked` / `abandoned` 时必填 |
| `created_at` / `updated_at` | 时间戳 | — |

### 2.2 `g_task_submissions`

`id` / `task_id` / `source_id`（→ evkg sources）/ `note` / `created_at`。

**不变式**：一个 task 的 `done` 必须绑定 ≥1 条 submission；`source_id` 必须真实存在（跨表族引用由应用层保证）。

### 2.3 `g_events`（复用 ARCHITECTURE §4.3）

`id` / `user_id` / `kind` / `severity` / `payload_json` / `created_at`。
M5 冻结的 `kind`：`task_status_changed`（payload = `{task_id, from, to, reason}`）。
M7 起追加自己的 kind，不复用本表的语义做别的事。

## 3. 冻结点 B：gap → task 映射边界

1. **输入 fail-closed**：只对 `g_gaps.status='open'` ∧ 能力点 `active` 生成；**无缺口不生成任务**；
2. **维度决定任务形态（冻结）**：`practice` 缺口 → `deliverable_type ∈ {markdown, code, archive}`；
   `understanding` 缺口 → **只允许 `probe_answer`**（理解侧只有 `probe_result` 能升级 2 → 3）；
3. **severity 只决定优先级**（`level_gap_2plus` > `level_gap_1` > `evidence_gap`），不作过滤；
4. **去重**：同一缺口已有未关闭任务（`proposed/active/blocked`）→ 不再生成；
5. 任务文本只定义"做什么、产出什么、怎么验"，不复述缺口诊断。

## 4. 冻结点 C：task generator = LLM 提议 + 确定性闸门

```text
gap（open, active）
   ↓
LLM 提议 {title, objective, deliverable_type, est_minutes, acceptance_type, acceptance}
   ↓
确定性闸门（七步，逐步留档；任一步失败即返回、不落库）
   ↓
g_tasks（status=proposed）
```

闸门步骤（**七步**，固定顺序；M5-b 冻结的命名收口：缺口存在 / open / 能力点 active 合并为
`gap_taskable`，`reject_reason` 仍区分三种情形）：

```text
1 schema                 （extra="forbid"；能力判断与排序字段进不来）
2 gap_taskable           （缺口存在 ∧ status='open' ∧ 能力点 active ∧ 有 assessment_id，provenance 完整）
3 deliverable_allowed    （维度 ↔ 交付物枚举匹配）
4 acceptance_verifiable  （acceptance_type 枚举 + 文本 ≥8 字符 + 反例模式）
5 est_minutes_range      （10–600；**越界只做形式夹取**并记 adjustment_note）
6 duplicate              （同缺口存在 proposed/active/blocked 任务 → 拒）
7 persisted              （唯一写入点：store.create_task → status='proposed'）
```

**adjustment 只允许形式夹取**（`est_minutes` clamp）；**禁止**改写 title / objective / acceptance
（闸门是 validator，不是第二个生成器）。**declined 是运行结果、不是任务状态**：
LLM 无法为该缺口设计可验收任务时给出 `decline_reason` → 记 `declined` + reason，不落 `g_tasks`。

**M5-b 实现约束（用户 2026-10-03 补充冻结）**：

1. **Generator 不直接拥有 `create_task` 权限** —— 链为 `generator → TaskProposal → gate → create_task()`；
   `LLM output ≠ database mutation`（与 M4-b ClaimBinder 同构）；
2. **accepted task 的 provenance 必须完整** —— 每条 `g_tasks` 可回溯
   `task_id → gap_id → assessment_id → claim/evidence`；M5-b 不实现 claim 链，但不得破坏入口
   （闸门第 2 步强制 `assessment_id` 存在）；
3. **禁止任务排序字段** —— `priority` / `difficulty` / `learning_value` 等不得进入 schema：
   M5-b 只解决「gap exists → task exists」，不解决「哪个任务先做」。

**反例必须被拒（G4 硬要求）**：冻结反例模式（"去学习 X"、纯"了解/熟悉/掌握"且无产出物名词、
验收为空/不可操作）→ 拒绝并记录 `reject_reason`（含字面反例"去学习 Agent Evaluation"）；
允许**改造**（改造成含交付物的任务，必须写 `adjustment_note` 与改造理由）。

**LLM 不可以**：决定证据类型（只能选枚举）、跳过闸门、写 gap/assessment；`run_id` 由运行记录补。

## 5. 冻结点 D：task 状态机

```text
proposed ──activate──▶ active ──complete_task──▶ done（终态）
   │                     │  ▲
   │                     │  └──unblock──┐
   │                     └──block(reason)┘
   └──────────▶ abandoned（reason）◀── active / blocked
```

- **`done` 唯一入口 = `complete_task(task_id, source_id, note)`**（提交即完成）；
  手工把状态改成 `done` / 直接写库 → 报错；
- `blocked` / `abandoned` 必填 reason；非法转移直接报错（不做静默兜底）；
- 每次转移写 `g_events`（`kind=task_status_changed`，含 from/to/reason）；
- 缺口在任务进行中被关闭 → 任务不自动改状态（提交仍照常产生证据）。

## 6. 冻结点 E：submission → evidence → reassessment 闭环

`complete_task` 的固定链（**无手工步骤**；M5-c 落 `assessment/task_loop.py`）：

```text
提交物（文件路径 / probe 作答文本）
  ↓ ① 单入口入库：adapter.ingest_document（channel=user_evidence，attribution=user_declared）
     证据类型由 deliverable_type 决定：markdown/code/archive → task_submission；
     probe_answer → probe_result
  ↓ ② 材料 claim：adapter.create_material_claim（越权前置拒绝；材料口径）
  ↓ ③ 绑定：ClaimBinder 提议 → 八步闸门 → g_capability_claims（缺口所属能力点）
  ↓ ④ 重评：assess_capability（M4-e 编排；fail-stop）
  ↓ ⑤ g_task_submissions + 状态 → done + 归因链
```

- **等级预期（复用 M4 阶梯，不新增规则）**：实践侧 `task_submission` → 基线 4（3 → 4）；
  理解侧 `uploaded_doc` 起评、`probe_result` 升 3（2 → 3）；
- **归因产物**：`{task_id, source_id, 新增 claim_ids, 前后 {assessment_id, level, status}, 支撑集差异}`；
- **反例守卫**：变化找不到新增 source/claim → 报错；任何一步需手工改库 → G5 判不通过。

## 7. 冻结点 F：G4 / G5 验收条件

| 门 | 判定 | 归档 |
|---|---|---|
| **G4** | ① 每个 task 反向映射 ≥1 gap（映射表）；② 每个 task 含 {可交付物 / 预计时长 / 验收方式}；③ **反例被拒或改造**（含字面反例）；④ 逐条规则校验通过率 + 拒绝日志 | `artifacts/gates/G4/` |
| **G5** | 端到端一次：gap → 任务 → 提交 → 新证据 → 重评 → **≥1 个能力等级变化**（主轴：实践 3 → 4，`level_gap_1` 缺口关闭）；前后两份 assessment（时间戳）+ 新 source + 归因链；**全程无人工干预**（单条运行命令，无手工改库） | `artifacts/gates/G5/` |

**"无人工干预"口径**：无手工 SQL / 无手工改库 / 无中途人工补步骤；LLM 提议与闸门裁决属自动化流程
（真实模型调用按 M4 同款授权开关执行）。

## 8. 范围

### 8.1 做

- `g_tasks` / `g_task_submissions` / `g_events` 契约与读写；状态机与守卫；
- gap → task 生成器（LLM 提议 + 七步确定性闸门 + 反例拒绝 + 全量留档）；
- 提交 → 单入口证据 → claim → 绑定 → 重评 → 归因链（`task_loop`）；
- Growth Agent 模式 A 四工具：`list_gaps` / `create_task` / `complete_task` / `write_event`；
- G4/G5 门证据（独立实验库；真实运行留档）。

### 8.2 不做（冻结）

| 项 | 去向 |
|---|---|
| UI | M8 |
| Memory（Profile / State / History） | M6 |
| 主动 Agent（事件检测 / 提醒） | M6/M7 |
| 任务排序 / 推荐 | 后续 |
| 学习路径 / 课程化 | 后续 |
| 多任务 DAG / 依赖图 | 后续 |
| 任务质量评分（"任务好不好"） | 后续（G4 只测可验收性） |
| evkg 修改 / 新增来源类型 | **不做** |

## 9. 步骤结构

```text
M5-a  数据契约 + 状态机 + 工具注册（list_gaps / create_task / complete_task / write_event）
      ↓
M5-b  gap → task 生成器（LLM 提议 + 七步闸门 + 反例拒绝 + 全量留档）
      + **G4 门证据**（用户 2026-10-03 调整：G4 随 M5-b 产出，`artifacts/gates/G4/`）
      ↓
M5-c  提交 → 单入口证据 → claim → 绑定 → 重评 → 归因链
      ↓
M5-d  G5 门证据（独立实验库；真实运行）+ M5 Gate 封板
```

## 10. 验收标准映射（自动化验证 / 归档证据）

| ID | 验收标准 | 自动化验证 | 归档 |
|---|---|---|---|
| AC1 | 任务可反向映射 ≥1 gap；含 {交付物 / 时长 / 验收方式} | `tests/test_task_contract.py` + G4 运行器逐条校验 | `artifacts/gates/G4/` |
| AC2 | 状态机合法/非法转移（含 `done` 唯一入口） | `tests/test_task_state_machine.py` | 测试输出 |
| AC3 | 反例必须被拒（含字面"去学习 X"） | 生成器对例 + 拒绝日志 | `artifacts/gates/G4/` |
| AC4 | 提交产生真实证据链（source → claim → binding） | `tests/test_task_loop.py` | `artifacts/gates/G5/` |
| AC5 | 端到端 ≥1 能力等级变化 + 归因链可反查 | `tests/test_growth_loop.py` + G5 运行器 | `artifacts/gates/G5/` |
| AC6 | 全程无人工干预（单条命令；无手工改库） | 运行器（无 SQL 修改步骤）+ 审计 | `artifacts/gates/G5/` |
| AC7 | M4 rating contract 未被修改 | AST/常量检查（`RULES_CONTRACT_VERSION = "m4c-1"`；阶梯不变） | 测试输出 |
| AC8 | 证据层零写入、真实库对锚一致、`g_` 仍空 | 全量测试 + 锚点比对 | 命令输出 |
| AC9 | 全量回归 + ruff + 治理 | 全量测试 + `validate/audit` | 命令输出 |

## 11. 风险与开放问题

1. **probe 任务质量不可控**：M5 只保证"现场作答成为 `probe_result` 证据并被规则引擎结算"；
   作答正确性**不参与定级**（D6）；probe 评分若要进等级，需先改 M4 阶梯（另议）；
2. **提交类型口径**：markdown 提交按 `deliverable_type` 定为 `task_submission`（实践 4），
   **不因"看起来像笔记"降级为 `uploaded_doc`** —— 契约测试锁定；
3. **G4 只测可验收性**，不测"任务是否有意义"；意义由缺口映射 + 用户确认承担；
4. `est_minutes` 准确性无法在 M5 验证（无 UI 计时）；
5. 一对多（一任务多缺口）与任务依赖图留后续；
6. G5 的"无人工干预"依赖真实模型可用性（网关/预算）；离线等价运行作冒烟，
   **门证据必须来自真实运行**。

## 12. 真实运行预算（单次运行上限口径）

| 运行 | 调用 | 上限（M5-b 冻结，收紧） |
|---|---|---|
| M5-b 生成器（per-gap 1 次 × 前 2 个缺口） | ≤2 | **≤2 HTTP** |
| M5-c 提交后绑定（1 次/提交） | 1 | ≤1 HTTP（M5-c 冻结时确认） |
| 离线对例（fake gateway） | 0 | — |
| **M5-b 本步合计** | | **≤2 HTTP**，零额外重试、fail-stop、允许重跑但每次独立记录 |

## 13. 开工前检查（设计级）

| # | 检查 | 状态 |
|---|---|---|
| 1 | 验收标准逐项可映射到测试或可归档证据 | **已做**（§10，9 项全覆盖） |
| 2 | 数据结构能区分"任务"与"能力判断"（约束 ①） | **已做**：`g_tasks` 不含等级/分值字段；闸门 `extra="forbid"` |
| 3 | 证据链 provenance 可反查（约束 ③） | **已做**：`g_task_submissions.source_id` + 归因产物（§6） |
| 4 | 复用 M4 契约不被重定义（约束 ④） | **已做**：AC7 静态检查 |
| 5 | 真实库零写入、独立实验库运行 | **已做**：沿用 M4-e 模式 |
