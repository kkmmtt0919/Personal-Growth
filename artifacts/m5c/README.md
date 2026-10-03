# M5-c 产物：任务提交闭环（TaskLoop）—— 提交 → 证据 → claim → 绑定 → 重评 → 归因

> 结果：**离线 38/38；真实 12/12**（2026-10-03）。真实运行 **1/1 HTTP**（单次上限 1，零额外重试）。
> 命令：`uv run python artifacts/m5c/run_task_loop.py --mode offline`
> 真实：`M5_ALLOW_REAL_MODEL=1 uv run --env-file .env python artifacts/m5c/run_task_loop.py --mode real`

## 本步边界（用户 2026-10-03 确认，`docs/M5-PLAN.md` v1.0 §6/§10/§12）

- **唯一入口** = `TaskLoop.complete_task(task_id, submission)`；**`source_id` 不属于调用契约**
  （由证据链内部产生）；`g_task_submissions` 只由本链写入；
- **done 在链尾落定**：②–⑤ 任一步失败 → 任务留在 `active`（可幂等重跑）；`done` 是闭环结果，
  不是提交动作的结果；一旦 `done` 即终态；
- **单入口入库**：markdown/code → `adapter.ingest_document`；archive → `evidence.archive.ingest_archive`
  （容器级封装，逐条目仍走单入口）；probe_answer → 物化后入库；`channel=user_evidence` /
  `attribution=user_declared` 写死；证据类型由 `deliverable_type` 决定（不因内容形态改变）；
- **材料 claim**：确定性模板（零 LLM；subject=提交材料）、逐字引文、越权前置拒绝、一次提交一条、幂等；
- **绑定**：`ClaimBinder.propose([新 claim])` → 八步闸门；**≤1 HTTP**；后置条件 = 任务能力点
  ≥1 条 accepted，否则记 `binding_missed`（不写 assessment、不报提升）；**不改 M4-b**；
- **重评**：`assess_capability(task.capability_id)`（M4-e 编排原样复用，含缺口重算；fail-stop）；
  等级只由该编排写；
- **归因**：`m5c-1` 派生产物（**不新增表、不新增 event kind**）；只读反查 `trace_task`；
  **三联条件守卫**（before assessment + 新证据 provenance + after assessment，缺一即 `LoopGuardError`）；
  本链只产生支持性证据，等级下降视为异常；
- **不做**：G5（M5-d）、真实库写入、evkg 修改、M4-b/M4-c/M4-e 代码修改、UI/Memory/Agent 主动化。

## 场景与结果（离线，38/38）

| 场景 | 结果 |
|---|---|
| 受控场景（M4-e 编排产出；材料受控构造并标注） | 实践 3 / 理解 2（目标 4）→ 实践 `level_gap_1`、理解 `level_gap_2plus` |
| 主链（markdown 提交） | 提交 → `task_submission` 来源（归属/通道写死）→ 材料 claim → 绑定（对例 1 次调用）→ 重评 → **实践 3 → 4**、`level_gap_1` 关闭；理解缺口保持 open（反向验证）；guard 全 true、trace 全链可反查 |
| probe 路径 | `probe_result` → 理解 2 → 3；缺口保持 open（目标 4） |
| archive 路径 | 2 条目入库 / 0 failed；主条目 = passage 最多者（确定性选取）；claim 逐字引用 |
| binding_missed | 提议绑到别的能力点 → **不写 assessment、不报提升**；任务照常 done；trace 不完整（如实记录） |
| 失败 + 重跑 | 网关失败 → 任务留在 active（零提交、零 done）；重跑幂等（同 source / 同 claim / 单提交） |
| 三联条件守卫 | 6 项对例：缺 before / 缺 provenance / 未绑定任务能力点 → 报错；无变化放行；等级下降 → 报错 |
| 数据边界 | 无新表（`g_` 仍 11 张）；event 仅 `task_status_changed`；`RULES_CONTRACT_VERSION=m4c-1`；真实库逐表哈希+计数对锚、`g_` 全空 |

## 真实运行（12/12，1 HTTP）

| 项 | 结果 |
|---|---|
| 调用 | `openai_compatible/glm-5.3`，**1/1 HTTP**（零额外重试、fail-stop） |
| 链 | active task → 提交（受控构造、标注）→ `task_submission` → 材料 claim → 绑定 accepted → 重评 |
| 判定 | **实践 3 → 4**；`level_gap_1` closed；理解保持 2（不会全能力自动提升）；guard 全 true；trace 可反查 |
| 归因产物 | `task-loop-real.json`（before/after、claim、binding、guard、报告路径） |
| 报告 | `reports/real/loop-task_*.{json,md}`（M4-d 可解释输出，随产物归档） |

**运行记录说明**：真实运行共两次（每次 1 HTTP、各自独立记录、均 12/12）。第一次的报告路径落在临时目录，
修正运行器把报告写入 `artifacts/m5c/reports/<场景>/` 后重跑；`result-real-run1.json` 保留第一次记录，
`result-real.json` 为最终记录。其后仅做过一次 lint 清理（删除失败分支中未使用的局部变量，本次运行未执行该分支）。

## 文件

| 文件 | 内容 |
|---|---|
| `run_task_loop.py` | 运行器（offline 场景族 + real） |
| `result.json` / `result-real.json`（+ `result-real-run1.json`） | 检查结果与明细 |
| `task-loop-real.json` | 真实运行归因产物（只读审计视图，`build_loop_artifact`） |
| `reports/<场景>/` | M4-e 能力解释报告（逐字引文可回溯） |
| `submission/rag-eval-set.md` | 真实运行的受控构造提交样例（如实标注 `growth_constructed`） |
| 代码 | `backend/growth_os/assessment/task_loop.py`；`agent/tools.py`（complete_task 转发闭环）；`assessment/__init__.py`（导出） |
| 测试 | `tests/test_task_loop.py`（11 项）、`tests/test_growth_loop.py`（1 项）、`tests/task_loop_fixtures.py`（夹具） |

## 验收序对应

| # | 验收项 | 位置 |
|---|---|---|
| 1 | 提交单入口（唯一入口 + done 在链尾 + 失败留 active 可重跑） | `tests/test_task_loop.py::test_complete_task_requires_active_and_matching_submission`、`::test_failure_leaves_active_and_retry_is_idempotent`；冒烟 `retry_*` |
| 2 | submission → evidence 类型映射（写死归属/通道；四类交付物） | `::test_single_entry_and_frozen_mapping`、`::test_probe_answer_uses_probe_result_and_lifts_understanding`、`::test_archive_primary_source_selection_and_entry_provenance` |
| 3 | 材料 claim 边界（确定性、材料口径、一条、幂等） | `::test_single_entry_and_frozen_mapping`；冒烟 `happy_single_submission_and_claim` |
| 4 | ClaimBinder 调用位置（candidate=新 claim；≤1 次；后置条件） | `::test_binding_missed_records_without_level_change`；冒烟 `happy_one_binding_call` |
| 5 | M4-e 接入（只重评任务能力点；fail-stop；缺口重算；报告落盘） | 主链测试；`tests/test_growth_loop.py`（报告路径断言） |
| 6 | 完成 ≠ 提升守卫（三态 + 三联条件 + 下降守卫 + AST 禁写） | `::test_verify_attribution_three_part_condition`、`::test_loop_never_writes_levels_or_bindings_directly` |
| 7 | 归因链 schema（字段 + 只读反查） | `::test_trace_task_reverse_query`；`task-loop-real.json` |
| 8 | 预算与数据边界 | `result-real.json.detail.requests == 1`；`real_db_*`；`boundaries_*` |

## 与 M5-a/b 的关系

- M5-a 的 `GrowthStore.complete_task` **原语不变**（仍要求 `source_id`、仍不触发重评），
  调用面收窄为「只由 `TaskLoop` 调用」（测试 AST 守卫）；
- M5-b 的生成器/七步闸门原样复用（`test_growth_loop.py` 走真实闸门路径）；
- Agent 工具 `complete_task` 改为转发闭环（签名：`task_id` + 提交物 + note；**`source_id` 不再出现在调用契约里**）。
