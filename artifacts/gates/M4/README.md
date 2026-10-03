# M4 Gate 判定记录：能力审计（Capability Assessment）

> 判定日期：2026-10-03 · 计划基线：`docs/M4-PLAN.md` v1.0（用户确认）
> 执行：`artifacts/gates/M4/run_m4_gate.py`（**离线，不调用模型**；对已归档的 M4-e 门证据
> 逐条断言 + 在真实库**副本**上新鲜复核质量门）；原始结果 `m4-gate-result.json`；账本 **EV-071**
> 结论：**通过（21/21）**

## 一、ROADMAP M4 完成条件逐项

| # | 条件 | 实测 | 结果 |
|---|---|---|---|
| 1 | 对 ≥3 个能力给出星级，每级可追溯到原始证据 | 3 个能力点出星级（RAG 系统搭建与调优 / 自定义工具集成与 MCP / 记忆机制·向量检索）；**7/7** 评定行可追溯（G2 抽 5 条，逐跳 + 引文逐字） | ✅ |
| 2 | 复现 PRD §10 判定：仅聊天自述 + 笔记、无代码/项目/任务 → 理解 ≥2、实践 ≤1 | A 轮：理解 **2**（`rated`）、实践 **`insufficient_evidence`**（"不存在 ≥2 的实践等级"，报告显式写"缺少可起评的实践证据"） | ✅ |
| 3 | 有 GitHub 项目证据时实践星级显著更高（≥ +2） | B 轮：实践 **3**（`rated`）—— 相对 A 的"无 ≥2 等级"提升；**增强观测：B 实践 ≥3 成立** | ✅ |
| 4 | 星级页能回答"为什么是这个星级"：支持 / 不足 / 攻击结果 | 4 份报告（A 轮 1 + B 轮 3）全部含七节：生成信息 / 两维度评定 / 支持证据（逐字引用）/ 不足 / 反向证据 / 已排除 / 规则版本与复算 / 本报告不能成立的结论 | ✅ |
| 5 | 每次评估后 `evkg audit_store` 仍为 `pass` | 归档：实验库 **pass / 0 violations**；新鲜复核：真实库副本 **pass / 0 violations** | ✅ |
| 6 | 对应验收门 **G2、G3** 通过 | G2：7/7 可追溯（5 条抽样 + dossier 6 份）；G3：A/B/C 对照全部符合 | ✅ |

## 二、质量门

| 门 | 实测 |
|---|---|
| QG1 证据不变量 | 实验归档 `pass/0`；真实库副本新鲜复核 `pass/0` |
| QG2 攻击自测 | 副本上 `run_damage_selftest` = **caught**（注入引文违例被审计捕获）；**双向测量**：注入前 `pass` → 自测清理后 `pass`（不采信内置 status 单值） |
| QG3 评级规则覆盖 | `tests/test_assessment_rules.py`（18 项）存在；真实运行复核 A/B 判定（`g3a_practice_not_ge_2`、`g3b_practice_ge_2` 均为真） |
| QG4 无密钥入库 | 被跟踪文件扫描 **200 个文件 / 0 命中**（占位符放行） |
| QG5 全量测试 | Growth OS **359 passed** + ruff `All checks passed!`（本脚本子进程新鲜跑）；evkg **111 passed**（`uv run --extra dev --extra office pytest`） |

## 三、数据边界与预算

| 项 | 实测 |
|---|---|
| 真实库未被污染 | 逐表内容哈希 + 计数对 `artifacts/m3a/evidence-anchors.json` **一致**；`g_tables_in_real_db = []` |
| 构造素材标注 | 笔记 `constructed=true`、仓库摘要（离线）`constructed=true`、合成 JD `constructed=true`；真实仓库记录 `sha=c417a096…` |
| 临时库 | 实验库 / 封板副本均已删除 |
| 真实运行预算 | 单次 **17/17 HTTP**、零额外重试、逐阶段硬上限（单次运行口径，见下） |

## 四、真实运行成本口径（用户 2026-10-03 确认）

- 预算表述 = **「单次真实运行 ≤17 HTTP」**；允许因代码修复 / 预算硬停 / 重新验证重跑，**每次运行独立记录**；
  不再表述为"整个开发阶段累计 ≤17"。
- M4-e 实测：6 次真实进程运行（2 次代码缺陷早停、2 次预算硬停、1 次完成但 G2 追溯器语义不足、1 次通过），
  合计 ≈53 HTTP；**每一次运行都 ≤17**，失败运行的成本被封在 17 以内（fail-stop 的价值）。

## 五、必须保留的边界（Gate 通过 ≠ 这些事情已解决）

1. **真实库仍不含 `g_` 表**：M4 的全部评估在独立实验库产出，门证据 = 归档产物；
   把评估写进真实库是产品化决定（M5 起）。
2. **G3 主体是 RAG 相关能力**（与真实仓库材料对应）；`ACCEPTANCE_GATES` 示例中的 "Agent Memory" 未作第二主体。
3. **A 臂笔记为受控构造**（本机无真实笔记）：G3 测的是"知识材料 vs 实践产物"的证据强度区分，
   构造部分已如实标注。
4. **已登记推迟项**：`M4-b.1`（`supersede_missing` 生成器接线）、M3 两个开放项（PDF 适配层 V1 入口、页码级 locator）。

## 六、M4 总验收索引

| 步骤 / 门 | 内容 | 证据 |
|---|---|---|
| M4-PLAN v1.0 | 七项冻结（G2/G3 判定、三层归属、history+current view、C5 上游修、LLM 提议 + 确定性闸门、G3 实验设计、交付物口径） | EV-066 |
| M4-a | Assessment 契约 + provenance（C5，evkg `9a21552`）+ 最小闭环 | EV-067 |
| M4-b | 证据绑定与分桶（LLM 提议 + 八步确定性闸门 + 映射落库） | EV-068 |
| M4-c | 两维度星级规则引擎 + attack 结算 + `rated` 写入路径 | EV-069 |
| M4-d | 能力解释报告 + `current_level` 维度化回填与重建校验 | EV-070 |
| M4-e | 统一编排（fail-stop）+ `g_gaps` + 真实 attack + G2/G3 证据 | EV-071 |
| G2 | 证据可追溯性门（7/7 逐跳、5 条抽样、dossier 6 份、audit pass/0） | `artifacts/gates/G2/`；EV-071 |
| G3 | 能力审计门（A/B 对照 + C 负对照） | `artifacts/gates/G3/`；EV-071 |
| M4 Gate | 完成条件 1–6 + QG1–QG5 + 数据边界（本文件） | `m4-gate-result.json`；EV-071 |

**M4 治理闭环**：Evidence → Binding → Assessment → Explanation → Current View → Gap Detection → Audit / Gate Evidence。
