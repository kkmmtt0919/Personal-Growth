# M5-a 产物：任务数据契约 + 状态机 + 工具注册

> 结果：**17/17 检查通过**（2026-10-03，离线；**不调用任何模型**）。
> 命令：`uv run python artifacts/m5a/run_task_contract.py`

## 本步边界（用户 2026-10-03 冻结，`docs/M5-PLAN.md` v1.0）

- **Task 不是能力判断**：`g_tasks` 不含 level / score / confidence 字段；完成任务**不产生、不修改**任何评定；
- **`done` 唯一入口 = `complete_task`**（提交即完成，需 `source_id`）；非法转移报错；
- 转移写 `g_events`（`kind=task_status_changed`，含 from/to/reason，按发生顺序）；
- 维度 ↔ 交付物：`understanding` 只允许 `probe_answer`；`practice` 只允许 `markdown/code/archive`；
- 交付物 → 证据类型：`markdown/code/archive → task_submission`；`probe_answer → probe_result`；
- 不可验收表述（含字面"去学习 Agent Evaluation"）必须被拒；
- **不做**：LLM 生成器（M5-b）、提交→重评闭环（M5-c）、G4/G5（M5-d）。

## 场景与结果

| 场景 | 结果 |
|---|---|
| 真实缺口（M4-e 编排产出） | 理解 2 / 实践 3 → 缺口：实践 `level_gap_1`、理解 `level_gap_2plus`（两个 open） |
| `list_gaps` → `create_task` | 任务 `proposed`；`gap_id` / `capability_id` 正确挂到主缺口 |
| 契约拒绝（5 类） | 字面反例（去学习 X）✅ 拒；维度错配 ✅ 拒；同缺口重复 ✅ 拒；时长越界 ✅ 拒；未知缺口 ✅ 拒 |
| 状态机路径 | `proposed → active → blocked → active → done`；非法转移（active→active、done→active、done→abandoned、done 后再提交）全部拒绝 |
| 提交 | 空 `source_id` ✅ 拒；不存在的 `source_id` ✅ 拒（工具层跨表族校验）；提交记录 1 条 |
| 事件链 | `[None→proposed, proposed→active, active→blocked(等用户时间), blocked→active, active→done]` |
| **完成 ≠ 提升** | 提交前后评定行完全一致（`completion_does_not_create_or_change_assessments`）；能力点等级未被触碰 |
| 数据边界 | 真实库逐表哈希 + 计数对锚一致、`g_tables_in_real_db=[]`、实验库跑完即删 |

## 用户验收序对应

| # | 验收项 | 位置 |
|---|---|---|
| 1 | 三张表建齐、冻结词表与转移表写死 | `tests/test_task_contract.py::test_tables_and_frozen_vocabularies`；`::test_transitions_table_is_frozen` |
| 2 | `g_tasks` 无等级/分值字段（Task ≠ 能力判断） | `::test_task_table_has_no_grade_fields`（AST 抽取建表语句） |
| 3 | 维度 ↔ 交付物、交付物 → 证据类型 | `::test_dimension_deliverable_mapping_is_enforced`；常量断言 |
| 4 | 不可验收任务必须被拒（含字面反例） | `::test_unverifiable_tasks_are_rejected` |
| 5 | 主缺口 open、能力点 active、同缺口去重 | `::test_create_task_requires_open_gap_and_active_capability`；`::test_duplicate_open_task_per_gap_is_rejected` |
| 6 | 状态机合法/非法 + reason 必填 + 终态 | `tests/test_task_state_machine.py`（6 项） |
| 7 | `done` 唯一入口（AST 守卫 + 需 active + 需 source） | `::test_only_complete_task_can_set_done`；`::test_complete_task_requires_source_and_active` |
| 8 | 事件链按发生顺序、from/to/reason 完整 | `::test_every_transition_writes_an_event` |
| 9 | 工具注册（模式 A 四工具）+ 跨表族 source 校验 | `tests/test_task_contract.py::test_growth_tools_registered_and_cross_table_check` |
| 10 | 任务完成不触碰评定（完成 ≠ 提升） | `::test_tools_do_not_touch_assessments`；冒烟 `completion_does_not_create_or_change_assessments` |
| 11 | 真实库对锚一致、`g_` 仍空、无密钥 | 冒烟 `real_db_untouched` / `real_db_has_no_g_tables` |

## 文件

| 文件 | 内容 |
|---|---|
| `run_task_contract.py` | 离线运行器（真实缺口场景 + 工具路径 + 拒绝用例 + 事件链 + 边界） |
| `result.json` | 17 项检查结果与明细（含拒绝原因、非法转移原因、事件链） |
| 代码 | `backend/growth_os/store/growth_store.py`（三表 + 状态机）、`backend/growth_os/agent/tools.py`（模式 A 四工具） |
| 测试 | `tests/test_task_contract.py`（14 项）、`tests/test_task_state_machine.py`（7 项） |
