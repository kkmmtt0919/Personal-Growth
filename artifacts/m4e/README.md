# M4-e 产物：统一编排 + 缺口 `g_gaps` + 真实 attack + G2/G3 门证据

> 结果：**离线 25/25；真实运行 23/23**（2026-10-03）。
> 命令：`uv run python artifacts/m4e/run_m4e.py --mode offline`
> 真实：`M4_ALLOW_REAL_MODEL=1 uv run --env-file .env python artifacts/m4e/run_m4e.py --mode real`

## 本步边界（用户 2026-10-03 冻结）

- **编排**：`bind → attack → rate → report → apply_assessment_levels → verify_assessment_levels
  → apply_gaps → verify_gaps`；编排内**无 LLM、无网络**，`verify_*` 失败即 fail-stop；
- **`g_gaps`**：只表达「target − current + rubric 缺口」，不承担能力诊断 / 潜力判断 / 学习建议；
  只从**已存在的评定行**派生（无评定 → 不产生缺口）；唯一写路径 `apply_gaps`；
- **attack**：不改 evkg / verifier / 词表 / 结算规则；真实运行只验证「attack 输出 → 既有结算」；
- **真实库不写**：`data/growth.db` 全程只读，实验库独立、跑完即删；
- **构造如实标注**：笔记 / 仓库摘要（离线）标注 `growth_constructed=true`。

## 场景与结果

| 场景 | 结果 |
|---|---|
| 轮 A（弱证据：真实对话摘录 + 构造笔记） | 理解 2；实践 `insufficient_evidence` → 缺口 `evidence_gap` |
| 轮 B（强证据：真实仓库 `kkmmtt0919/mytset-rag`） | 实践 3（基线）；缺口重算为 `level_gap_1`（旧 `evidence_gap` 被同 id 覆盖为开放缺口） |
| 反向证据 | `weakened` → 封顶 ≤3（离线注入式等价物）；`broken` → 主张剔除、实践回到 `evidence_gap`（离线） |
| 待验证声明 | 对话材料（`user_asserted`）被闸门拒于 `attribution_unchanged`；JD 被拒于 `bucket_allowed` |
| G2 | 7/7 评定行可追溯（`supports` / `capability_bindings` 两条路径），引文逐字 |
| 质量门 | `audit_store` pass/0；真实库逐表内容哈希 + 计数对锚一致；`g_tables_in_real_db=[]` |

## 真实运行记录

| 阶段 | 调用 | 上限 | 实际 |
|---|---|---|---|
| 绑定 A / B | 1 / 1 | 1 / 1 | 1 / 1 |
| verifier A / B | 1 / 5 | 1 / 5 | 1 / 5 |
| adversarial A / B | 1 生成 + 3 裁决 / 1 生成 + 4 裁决 | 4 / 5 | 4 / 5 |
| **合计** | | **≤17** | **17**（零额外重试） |

- 模型：`openai_compatible/glm-5.3`（绑定提议）；独立复核 `deepseek-flash`（`independent_verifier=true`）；
- G3：A 实践无 ≥2 等级、B 实践 3（≥2；增强观察 ≥3 成立）；C（JD）分类 `domain_reference`、未进 supports；
- G2：抽样 5 条（来自 7 条可追溯行），dossier 见 `artifacts/gates/G2/dossiers/`；
- 门证据：`artifacts/gates/G2/`（traceability / audit / dossiers / README）、
  `artifacts/gates/G3/`（inputs / rounds / attack / comparison / reports / README）。

### 真实运行尝试记录（成本如实披露）

| # | 结果 | 消耗 | 原因 |
|---|---|---|---|
| 1 | 中止（0 次模型调用） | 0 | 代码缺陷：`adapter.ingest_reference_document` 不存在（应走 `evidence.reference`） |
| 2 | 中止 | 5 | 预算硬停：`run_adversarial` 的 probe 数不受 `max_probes` 约束（发现） |
| 3 | 中止 | 6 | 同上（复核发现：1 个目标返回 ≥3 条 probe） |
| 4 | 中止 | 8 | 代码缺陷：轮 B 候选集传入了 dict 列表（应传 claim_id 字符串） |
| 5 | 完成，但 **G2 不足** | 17 | 追溯器只认 `rubric.supports` → `insufficient_evidence` 行不计入（4/5） |
| 6 | **完成（本产物）** | 17 | 追溯器补 `capability_bindings` 路径；adversarial 两轮均完成 |

**本步真实 HTTP 合计 ≈53**（单次运行均 ≤17；冻结额度按"单次运行"理解，重跑次数超出预期，
需要在验收时确认）。教训记入 DECISIONS：预算表应写明"单次运行上限 + 允许的重跑次数"。

## 实施中发现（已登记 DECISIONS）

1. **evkg `run_adversarial` 的 `max_probes` 只限制目标 claim 数**：模型可对同一 claim 返回多条
   probe，裁决调用数 = probe 数（实测 3–4 条/目标）。冻结表假设的"1 目标 = 1 probe"不成立，
   两轮 adversarial 因此收窄为各 1 个目标（上限 4/5），覆盖由 verifier 承担。
2. **evkg `get_claims()` 按 id 排序（非插入顺序）**：verifier / adversarial 的覆盖目标确定但
   不可指定；本轮实际复核 6 条不同主张（含仓库主题与 JD 主张），adversarial 目标为对话/向量主题主张。
3. **`insufficient_evidence` 行没有支撑集**（"证据不足"本身是结论）→ G2 追溯补
   `trace_path=capability_bindings`（走能力点绑定的主张集合），证明"不足"判断是对真实、
   链路完整的已绑定证据做出的；无绑定也无支撑的行记 `none`，不计入抽样。
4. **记录更正**：`result-real.json` 中 `detail.budget_adjustment.coverage` 写于代码修正前的
   措辞（"verifier A 只复核笔记主张"）；按发现 2，实际复核目标是按 claim id 顺序取到的
   **对话材料主张**。判定与预算不受影响，以 `attack.json` 的实际目标记录为准。

## 文件

| 文件 | 内容 |
|---|---|
| `run_m4e.py` | 离线 / 真实双模式运行器（含预算硬上限与截断容错） |
| `reports/` | 离线模式的能力解释报告（JSON + Markdown 双份） |
| `result.json` / `result-real.json` | 两种模式的检查结果与明细 |
| `../gates/G2/` `../gates/G3/` | 两道门的证据归档（判定 + 输入源清单 + 攻击留档） |
