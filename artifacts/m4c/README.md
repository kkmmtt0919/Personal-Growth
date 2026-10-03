# M4-c 产物：评级与反向证据（星级规则引擎 + attack 结算接入）

> 结果：**12/12 检查通过**（2026-10-03，离线；**不调用任何模型**）。
> 命令：`uv run python artifacts/m4c/run_rating.py`

## 本步边界（用户 2026-10-03 冻结）

- **两个独立维度**：`knowledge + behavior → understanding`；`practice + task → practice`，不合并成单一等级；
- **基线规则**：仅自述 → 不足；`uploaded_doc` → 理解 2；`+probe_result` → 3；
  `repo_artifact` → 实践 3；`+task_submission` → 4；**显式优化/诊断/设计取舍信号** → 5；
- **反向证据结算**：`broken` → 主张剔除；`refutes`/`disputed` → 对应维度封顶 ≤2；
  `weakened` → 封顶 ≤3；**封顶只作用于该主张覆盖的维度**；
- **不做**：`current_level` 回填（推迟 M4-d）、M2 生成器、evkg 修改、解释输出（M4-d）、
  G3（M4-e）、UI、**真实 attack 调用**（推迟 M4-e）。

## 场景与结果

| 场景 | 结果 |
|---|---|
| 弱证据（自述 + 笔记） | 理解 **2**；实践 `insufficient_evidence`（显式缺实践证据，不是低星） |
| 强证据（补项目材料） | 实践 **3** → 相对弱场景 **+2 成立** |
| 反向证据 `refutes`（挂在被质疑主张上） | 实践封顶 **2**；理解保持 **2**（无跨维度污染） |
| 反向证据 `broken` | 主张剔除 → 实践回落 `insufficient_evidence`；历史行保留 |
| 无证据能力点 | 理解 / 实践均 `insufficient_evidence`（`level = NULL`） |
| 确定性 | 重复运行命中同一批行（幂等）；结论变化 = 新行（history preserved） |

## 用户验收序对应

| # | 验收项 | 位置 |
|---|---|---|
| 1 | deterministic rule tests | `tests/test_assessment_rules.py`（理解 / 实践两条阶梯） |
| 2 | reverse evidence cases | 同上（broken / refutes / disputed / weakened / 封顶不跨维度） |
| 3 | no-evidence case | 同上 + 本目录 `no_evidence` 场景 |
| 4 | same-input same-output | 同上（逐字段相等 + 幂等行数断言） |
| 5 | confidence isolation | 同上（分数 0.99 vs 0.05 同结论 + 规则引擎源码 AST 静态检查） |
| 6 | audit_store | `audit_store = pass / 0 violations`（临时库） |
| 7 | artifact integrity | 本目录 `rating-artifact.json`（`read_only: true`，含 rubric 与行历史） |

## 文件

| 文件 | 内容 |
|---|---|
| `run_rating.py` | 离线运行器（弱 / 强 / 反向 / 无证据 / 幂等 + 边界检查） |
| `rating-artifact.json` | 评级产物：每能力点两维度的 level / rationale / rubric / 行历史 |
| `result.json` | 完整报告（检查清单、证据库计数、真实库对锚） |
| `tmp/` | 运行期材料（gitignore；临时库运行后删除） |

## 关键实现契约（供 M4-d 消费）

- `g_assessments` 增 `dimension`（`understanding` / `practice`）；`status` 增加 `rated`；
  `level` 仅 `rated` 可写（1–5），`insufficient_evidence` 恒 NULL；
- **历史语义**：`draft → rated → history preserved`；评定不覆盖旧草案；
  等级变化 = 新行（id 含等级），当前视图用 `GrowthStore.latest_assessment(capability, dimension)` 查询；
- **level 5 的载体**：主张 metadata `growth_practice_signal ∈ {optimization, diagnosis, design_tradeoff}` ——
  **不允许**由项目规模、代码量、时间长度或任何模型分值推导（D6 静态 + 功能双重锁定）；
- **attack 结算读路径**：`claims_overview` → `attacks[].verdict` + `claim.status` + 证据极性 `refutes`。
