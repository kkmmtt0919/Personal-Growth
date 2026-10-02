# M2 验收报告（AC1–AC12 逐项对照）

> 判定日期：2026-10-02 · 计划基线：`docs/M2-PLAN.md` v1.0（用户确认）
> 结论：**AC1–AC12 全部满足 → M2 可正式收口**（另见"遗留与观察"，不阻塞收口）

## 一、验收项逐项对照

| ID | 验收标准 | 证据（可复核） | 结果 |
|---|---|---|---|
| AC1 | ≤6 轮产出含四要素的 confirmed goal | 真实会话 4 轮（`artifacts/m2/session-real.json` → `clarification.rounds_used=4`）；测试 `test_converges_within_six_rounds_and_confirms` | ✅ |
| AC2 | 未确认不得进入能力分析 | `test_unconfirmed_goal_is_rejected_before_calling_the_model`（并断言拒绝发生在调用模型前：`g_agent_runs=0`）、`test_guard_also_rejects_incomplete_confirmed_rows` | ✅ |
| AC3 | ≥3 领域 / ≥12 能力点 / ≤3 层；每点有 `target_level` + 来源 + 校验状态 | 真实会话：6 领域 / 12 能力组 / **31** 个三层能力点（`capabilities`、`capability_report_second`）；`test_valid_tree_is_persisted_with_provenance`、`test_shape_violations_are_rejected_without_partial_writes`（5 类违规整体拒绝） | ✅ |
| AC4 | `adjusted` 不被再生成覆盖（C1） | 真实会话：调整的节点在再生成后仍为 `target_level=5` / `origin=adjusted` / 保留调整理由；**同 id 覆盖尝试的强证据**来自 `test_regeneration_keeps_adjusted_target_level_and_note`（存储层）与 `test_regeneration_keeps_adjusted_value_and_reports_protection`（生成器层） | ✅ |
| AC5 | G1 通过（含两条反例） | `artifacts/gates/G1/README.md`（判定 + 轨迹 + 反例依据 + 截图豁免） | ✅ |
| AC6 | 全量回归 + lint | Growth OS **143 项全绿**；evkg **101 项全绿**；`ruff` 全过；账本 validate/audit 无告警 | ✅ |
| AC7 | LLM 路径离线可回归（C3） | `tests/test_agent_runtime.py`（fake 注入 + 无密钥 + `httpx` 实例化即失败）；`tests/test_http_budget.py` 5 项 | ✅ |
| AC8 | `g_agent_runs` 记录**实际** provider/model、状态、错误（C2） | 真实会话 6 条记录：`openai_compatible` / `glm-5.3-flash` / `model_source=result`；`test_run_records_model_from_result`、`test_failure_is_recorded_with_config_label_and_error`、`test_real_mode_requires_explicit_authorization` | ✅ |
| AC9 | `capability → goal → agent_run` 可追溯 | 真实会话 `checks.lineage_complete=true`（每个节点的 `generated_by_run_id` 都能追到同一 goal 的运行）；`test_lineage_and_reports`（同 `test_valid_tree_is_persisted_with_provenance`） | ✅ |
| AC10 | 第 7 轮必须失败或降级为 `proposed` | `test_seventh_round_is_rejected_not_silently_continued`（断言第 7 个问题**从未发给模型**）；真实会话尝试 5 实测触发 | ✅ |
| AC11 | 能力点不得伪装已验证；人工修改保留来源 | 真实会话全部 `verification_status=unverified` + 来源含"未校验"；`test_model_cannot_claim_verified_source`（模型自称"已核实"仍写 unverified）；调整必须写 `adjustment_note` | ✅ |
| AC12 | 不触碰 evkg 证据层 | `test_growth_store_only_touches_g_tables`、`test_m2_flow_does_not_write_evkg_tables`、`test_evidence_layer_does_not_touch_sqlite_directly`；真实库：哈希 `6ca3205f…` 未变、无 `g_` 表、`sources/passages/claims/evidence = 3/109/2/6` 未变、QG1 `pass=0/10` | ✅ |

## 二、ROADMAP M2 完成条件对照

| 完成条件 | 证据 | 结果 |
|---|---|---|
| 模糊目标 ≤6 轮 → confirmed goal（四要素） | G1 记录（4 轮） | ✅ |
| 未确认不得进入能力分析 | AC2 | ✅ |
| 能力树落库可读回、每个能力点有 `target_level` | AC3；`g_capabilities` 读回 | ✅ |
| 能力模型可人工调整且不被下次生成覆盖 | AC4 | ✅ |
| 验收门 G1 通过 | `artifacts/gates/G1/README.md` | ✅ |

ROADMAP M2 交付物对照：① `g_goals`/`g_goal_clarifications`/`g_capabilities` 建表读写 ✓（另加 `g_agent_runs`）；
② Goal Agent + 状态机 `draft→clarifying⇄proposed→confirmed` ✓；③ 能力模型生成（真实会话 6 领域/31 能力点）✓；
④ R5 选型落地 ✓（纯 LLM + `unverified` 标注；JD 导入留 M3；内置领域图谱另行决策）；
⑤ 测试文件 ✓（`test_goal_clarification.py` 29 项、`test_capability_model.py` 11 项）。

## 三、事实判断（用户指定保留）

> **「澄清能力通过」与「能力树通过」已经分别被真实模型验证过**（尝试 3：澄清 4 轮通过 + 三层树 13 点通过；
> 尝试 4：澄清通过 + 结构基本通过）。**本次（尝试 6）验证的是两者能否在同一次端到端运行内闭环** —— 结果：闭环成立。

## 四、真实消耗（M2-d 全部尝试，如实累计）

| 尝试 | 调用 | tokens | 结果 |
|---|---|---|---|
| 1 | 3 | ~2.3k | 脚本回答与提问错位（夹具缺陷） |
| 2 | 5 | 4634 | 澄清成功；树两层（提示词层级约定未写清） |
| 3 | 7 | 7196 | 澄清 + 树形状通过；runner 硬编码路径（夹具缺陷） |
| 4 | 6 | 6036 | 澄清通过；一个节点名含「/」（提示词补丁） |
| 5 | 6 | 5367 | 模拟用户答错致 6 轮耗尽（夹具缺陷，产品行为正确） |
| **6** | **6** | **6993** | **端到端通过（G1 通过）** |
| 合计 | 33 | ~32.5k | ≈ 0.04 元（glm-5.3-flash 价目） |

每次尝试均满足：应用层调用数 == HTTP 请求数（零额外重试）、未触碰真实库、失败即停并留诊断。

## 五、遗留与观察（不阻塞收口，但需在 M4 前决策）

1. **再生成目前是"并集"语义**：第二次生成给出不同的领域/能力组命名（6 领域/12 组/31 点），与第一次
   （3/6/16）合并后库中共 49 个节点。稳定 id 保证"同名不重复"，但**不同命名会累积**。
   AC 未要求替换语义，故不阻塞；但 M4（能力审计）前必须决定：再生成是**替换、合并还是保留历史**
   （与 M1 记录的 hard-cleanup / supersede 议题同源）。
2. **AC4 证据强度分层**（如实标注）：真实会话里被调整的节点在再生成后保住了值/理由/`origin`，
   但那次再生成恰好生成了不同路径，未真正攻击同一 id；**"同 id 覆盖"的强证据来自自动化测试**。
3. 真实会话中 `direction` 由模型从用户原话（"我想成为 AI Agent Engineer"）提炼，用户侧未单独提供该要素 ——
   这是"复述用户已表达的内容"，不属于臆造；四要素齐全的判定基于库中累积状态。
