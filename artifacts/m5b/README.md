# M5-b 产物：gap → task generator（LLM 提议 + 七步闸门）+ G4 门证据

> 结果：**离线 14/14；真实 14/14**（2026-10-03）。真实运行 **2/2 HTTP**（硬上限 2，零额外重试）。
> 命令：`uv run python artifacts/m5b/run_task_generation.py --mode offline`
> 真实：`M4_ALLOW_REAL_MODEL=1 uv run --env-file .env python artifacts/m5b/run_task_generation.py --mode real`

## 本步边界（用户 2026-10-03 冻结，`docs/M5-PLAN.md` v1.0 §4）

- **七步闸门（固定顺序）**：`schema → gap_taskable → deliverable_allowed → acceptance_verifiable
  → est_minutes_range → duplicate → persisted`（缺口存在/open/active 合并为 `gap_taskable`；
  第 2 步强制 `assessment_id` 存在，保证 provenance 完整）；
- **proposal schema 七字段**（`extra="forbid"`）：禁止能力判断字段（`expected_level` / `confidence` /
  `difficulty_score` / `level` / `score` / `rating`）与排序字段（`priority` / `priority_score` /
  `learning_value`）—— 静态检查锁定这些名字只出现在 `FORBIDDEN_TASK_FIELDS` 常量里；
- **adjustment 只允许 `est_minutes` 形式夹取**（不改写 title / objective / acceptance；
  闸门是 validator，不是第二个生成器）；
- **`declined` 是运行结果、不是任务状态**（LLM 无法设计可验收任务时给 `decline_reason`，不落 `g_tasks`）；
- **Generator 不直接拥有 `create_task` 权限**：`generator → TaskProposal → gate → create_task()`；
  唯一写库在第 7 步（新增行数 == accepted 数）；
- **不做**：提交 → 重评闭环（M5-c）、G5、任务排序 / 学习路径 / 难度评分（后续）、evkg 修改、真实库写入。

## 场景与结果

| 场景 | 结果 |
|---|---|
| 缺口（M4-e 编排产出） | 理解 2 / 实践 3（目标 4）→ 理解 `level_gap_2plus`、实践 `level_gap_1` |
| 目标缺口选取 | 按 severity 排序（`2plus` > `1` > `evidence_gap`）取前 2（`MAX_TARGET_GAPS=2`） |
| 真实 LLM 提议（glm-5.3，2 次调用） | ① 理解缺口 →「RAG 系统设计决策现场问答」（`probe_answer` / 30 分钟 / `probe_rubric`，含 6 题与权衡分析的评分细则）；② 实践缺口 →「搭建并调优一个可运行的最小 RAG 问答系统」（`archive` / 240 分钟 / `test_run`，含一键运行与 5 个测试问题的验收标准） |
| 闸门裁决 | 2 条提议 **全部 accepted**（`persisted`，无夹取、无拒绝）；写入 2 条 `g_tasks(status=proposed)` |
| 注入式对例（4 条） | 字面反例「去学习 Agent Evaluation」→ `acceptance_verifiable` 拒；能力判断字段 → `schema` 拒；维度错配（理解缺口给 `markdown`）→ `deliverable_allowed` 拒；空洞验收（"看看"）→ `acceptance_verifiable` 拒 |
| provenance | 两条任务均可反查：`task → gap → assessment → claim → evidence → passage → source`（`traceable=true`） |
| 边界 | 真实库逐表哈希 + 计数对锚一致、`g_tables_in_real_db=[]`、实验库跑完即删 |

## G4 门证据（`artifacts/gates/G4/`）

| 文件 | 内容 |
|---|---|
| `inputs.json` | 目标 / 能力点 / 缺口清单 + 目标缺口选取规则 + 材料标注（受控构造，`growth_constructed=true`） |
| `tasks.json` | 生成的 2 条任务全量（title / objective / deliverable_type / est_minutes / acceptance_type / acceptance / status） + `gap_id` 映射 |
| `rejections.json` | 4 条注入式对例的完整裁决（proposal_id / gate_stage / reject_reason / stages_passed / run_id / timestamp / origin） |
| `checks.json` | G4 判定：映射完整 / 四要素齐备 / 反例被拒（4 项逐条）/ 通过率（2/6）/ provenance / 禁止字段零命中 / 行数==accepted |
| `README.md` | 判定：**通过**（模式 real） |

**逐条规则校验通过率**：`2/6`（2 条真实提议 accepted + 4 条注入式对例全部被拒；分母含对例，如实记录）。

## 运行记录

| 文件 | 内容 |
|---|---|
| `task-generation-real.json` | 真实运行产物：proposal / decision / accept 全量 + provider/model（取自实际返回值）+ gap 上下文 |
| `task-generation-offline.json` | 离线对例产物（确定性提议，用于闸门回归） |
| `result.json` / `result-real.json` | 两种模式的检查结果（各 14 项） |

## 验收序对应

| # | 验收项 | 位置 |
|---|---|---|
| 1 | proposal schema 七字段 + 禁止字段被结构性拒绝 | `tests/test_task_generator.py::test_forbidden_fields_are_rejected`（9 个字段逐个参数化） |
| 2 | 禁止字段名只出现在常量里（静态检查） | `::test_forbidden_names_live_only_in_the_constant` |
| 3 | 七步闸门固定顺序 + 逐步对例 | `::test_happy_path_persists_task`；`::test_schema_stage_rejects_extra_field`；`::test_gap_taskable_stage`；`::test_deliverable_and_acceptance_stages` |
| 4 | `est_minutes` 只做形式夹取 | `::test_est_minutes_is_clamped_not_rejected` |
| 5 | 闸门不改写文本（拒绝而非润色） | `::test_gate_never_rewrites_text` |
| 6 | duplicate 谓词（done/abandoned 可再来） | `::test_duplicate_predicate` |
| 7 | `declined` 不落库、记 reason | `::test_decline_records_reason_without_task` |
| 8 | Generator 不直接写库 + 每缺口 1 次调用 | `::test_generator_proposes_through_the_gate`；`::test_propose_many_is_one_call_per_gap` |
| 9 | 写入不变式（行数 == accepted） | `::test_new_task_rows_equal_accepted_count` |
| 10 | G4 五件套 + 反例被拒 + 映射 + provenance | 冒烟 14/14 + `artifacts/gates/G4/` |
| 11 | 真实预算 ≤2 HTTP、零重试 | `result-real.json.detail.budget`（2/2） |
| 12 | 真实库对锚一致、`g_` 仍空 | `result-real.json.detail.real_db_anchors` |
