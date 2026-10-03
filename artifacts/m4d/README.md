# M4-d 产物：能力解释报告 + `current_level` 回填

> 结果：**15/15 检查通过**（2026-10-03，离线；**不调用任何模型**）。
> 命令：`uv run python artifacts/m4d/run_report.py`

## 本步边界（用户 2026-10-03 冻结）

- **回填方案 A**：`g_capabilities` 新增 `current_level_understanding` / `current_level_practice`
  两个维度列；legacy `current_level` **保留、停用、不写**（deprecated）；
- `current_level_status` 扩为 `unassessed` / `assessed`（**允许部分评估**：
  理解有、实践无 → `assessed`）；
- 回填**只经显式方法** `apply_assessment_levels(capability_id)`；
  **不接入自动评级流程**（避免 `rater()` 的隐式副作用；统一编排放 M4-e）；
- **重建校验** `verify_assessment_levels`：回填列必须等于从评定行重算的结果；
- 解释输出 **Markdown + JSON 双份**；"为什么不是更高"**只来自 `rubric.gaps`**；
- **不做**：`g_gaps`、G3、真实 attack、任务生成、UI、Memory、evkg 修改。

## 场景与结果

| 场景 | 结果 |
|---|---|
| 弱证据 → 回填 | 理解 2 / 实践 NULL；`status=assessed`（部分评估） |
| 强证据（补项目材料）| 实践 3；重建校验一致 |
| `refutes` 封顶 | 实践 2（报告"反向证据"节含封顶值与 refutes 证据行） |
| `broken` 剔除 | 实践 NULL（回填跟随；报告"已排除"节含裁决与未确认项） |
| 无证据 | 两维度 NULL / `unassessed` |
| 草案 | 不影响当前视图（仍 `unassessed`；草案行保留） |
| 重建校验 | 4 个状态全部 consistent；人为篡改会被 `verify` 发现（测试锁定） |

## 用户验收序对应

| # | 验收项 | 位置 |
|---|---|---|
| 1 | report 六项组成完整 | `tests/test_assessment_report.py::test_report_has_all_required_sections` |
| 2 | support evidence 可回溯（claim + quote） | `::test_support_evidence_walks_back_to_source_quote` |
| 3 | confidence 隔离 | `::test_report_does_not_leak_model_scores`（JSON 扫描 + 源码 AST） |
| 4 | excluded / reverse evidence 展示正确 | `::test_excluded_and_reverse_evidence_rendered` + 两份报告示例 |
| 5 | current_level rebuild 一致 | `::test_current_level_rebuild_consistency`（含篡改检测） |
| 6 | 无评级 NULL/unassessed | `::test_no_rating_gives_null_and_unassessed` |
| 7 | draft 不影响 current view | `::test_draft_does_not_affect_current_view` |
| 8 | audit_store pass / 0 | 运行器 + `::test_audit_store_passes_after_backfill_and_report` |
| 9 | artifacts/m4d 完整 | 本目录（5 份报告 × MD/JSON + `result.json`） |

## 文件

| 文件 | 内容 |
|---|---|
| `run_report.py` | 离线运行器（弱/强/反向/无证据 + 回填与重建校验） |
| `report-weak-to-strong.{md,json}` | 弱 → 强阶段的解释报告 |
| `report-evaluated.{md,json}` | 强证据下的最终解释报告 |
| `report-reverse-evidence.{md,json}` | `refutes` 封顶状态的报告（反向证据节） |
| `report-excluded.{md,json}` | `broken` 剔除状态的报告（已排除节） |
| `report-no-evidence.{md,json}` | 无证据能力点的报告（两维度不足） |
| `result.json` | 完整报告（检查清单、回填值、重建校验、审计、数据边界） |

## 解释纪律（写死）

- 报告的"为什么不是更高"只允许来自 `rubric.gaps`（规则引擎的缺口记录），
  **不允许新增推断**（例如"看起来缺少工程经验"）；
- 报告不携带任何模型分值（D6）；不把材料存在读成用户独立完成；
- `insufficient_evidence` 只说明"现有材料不足以支持等级"，不是对用户的判定。
