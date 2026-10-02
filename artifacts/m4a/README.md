# M4-a 产物：Assessment 基础模型与 provenance 前置

> 结果：**11/11 检查全过**（2026-10-02）。命令：`uv run python artifacts/m4a/run_assessment_loop.py`

## 本步做了什么（用户指定的 M4-a 边界）

- **模型契约**：`g_capability_claims`（能力点 ↔ 主张桥表）+ `g_assessments`（草案；`level` 恒为 NULL）
  + `g_capabilities` 生命周期字段（`generation_id` / `status`，history + current view）；
- **provenance 前置（C5）**：evkg 上游最小修（本地提交 `9a21552`，未推送）——
  抽取阶段记录 `extractor_provider/model/prompt_hash/profile`，档案渲染器优先显示；
- **最小闭环**：`claim/evidence → 确定性准入闸门 → assessment draft → 独立 audit artifact`；
- **不做**：星级算法、LLM、UI、G3 实验。

## 运行结果（摘要）

| 检查 | 结果 |
|---|---|
| 有可准入证据 → `draft`（supports 非空，level=NULL） | ✅ |
| 只有待验证声明（`user_asserted`）→ `insufficient_evidence` | ✅ |
| 重复运行命中同一 assessment（幂等） | ✅ |
| 起草 + 审计**零写回证据库**（逐表计数前后一致） | ✅ |
| audit artifact：`read_only=true`、`mutated_evidence_store=false` | ✅ |
| 支撑链逐跳完整且引文逐字（`chain.complete=true`） | ✅ |
| provenance 如实：材料口径断言写"不适用"，不冒充记录 | ✅ |
| `audit_store` = pass / 0 violations | ✅ |
| 历史主张只读扫描：2 条，`overreach` 1 + `plan` 1（与 M3-e 判定一致） | ✅ |

## 文件

| 文件 | 内容 |
|---|---|
| `run_assessment_loop.py` | 离线运行器（无 LLM、无网络；临时库 + 真实库只读扫描） |
| `assessment-audit.json` | 独立审计产物（草案逐条：准入分类 / 链路 / provenance） |
| `historical-claims-audit.json` | 真实库历史主张的只读机器化审计（零写入，不写回原库） |
| `result.json` | 本次运行的完整报告（含检查清单与证据库计数前后对照） |
| `tmp/` | 运行期材料（gitignore；临时库运行后删除） |

## 数据边界

- 临时库：运行后删除（`temp_db_deleted` 记录在 `result.json`）；
- 真实库：`sqlite3 mode=ro` 只读扫描，未打开 `GrowthStore`（未触发列迁移）；
  逐表内容哈希 + 计数与 `artifacts/m3a/evidence-anchors.json` 一致，且真实库中没有任何 `g_` 表。
