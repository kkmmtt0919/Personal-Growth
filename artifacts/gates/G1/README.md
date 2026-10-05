# G1 判定记录 · Goal Clarification

> 验收门定义见 `.project-to-act/docs/ACCEPTANCE_GATES.md` G1；本记录是**实际判定**，证据可复核。

## 场景

冷启动用户，只说一句：「我想成为 AI Agent Engineer」。

## 判定标准

系统在 **≤6 轮**内产出 confirmed goal，且目标包含 **{方向, 目的, 时间周期, 可衡量结果}**。

## 方法（真实模型，非模拟）

- 模型：`openai_compatible` / **`glm-5.3-flash`** @ `open.bigmodel.cn`（经适配层实例级 override；`REASONING_EFFORT=low`）
- 用户侧：确定性脚本应答（`tests/goal_flow_fixtures.py`：按问题语义匹配，不含第二个模型）
- 运行：`artifacts/m2/run_goal_flow_offline.py --gateway real --model glm-5.3-flash --http-cap 8`
- 预算纪律：应用层 6 次结构化调用（上限 8）、HTTP 6 个请求（上限 8）、**零额外重试**（`EVKG_HTTP_RETRIES=1`）

## 结果：**通过**

| 项 | 实测 |
|---|---|
| 轮次 | **4 轮**（3 轮要素澄清 + 1 轮确认问句），≤6 ✓ |
| 方向 | 成为 AI Agent Engineer，找到一份 AI 应用工程师的工作 |
| 目的 | 求职：获得 AI 应用工程师岗位 |
| 时间周期 | 六个月 |
| 可衡量结果 | 完成两个可演示的 Agent 项目并通过 20 道面试题 |
| 显式确认 | `source_quote = "好，就以这个为目标"`（写回确认问句，轨迹为完整往返） |
| 每轮回答匹配 | 4/4 匹配，0 次 inferred，0 次未匹配 |

逐轮轨迹（完整原文见 `artifacts/m2/session-real.json`）：

| 轮 | 追问要素 | 模型问的 | 脚本用户答的 |
|---|---|---|---|
| R1 | purpose | 你想成为 AI Agent Engineer 的主要原因或动机是什么（比如职业发展、做出某个产品、解决某类问题）？ | 找一份 AI 应用工程师的工作 |
| R2 | horizon | 你希望在多长时间内找到这份 AI 应用工程师的工作？ | 六个月 |
| R3 | measurable_result | 你希望用什么样的可衡量结果来标志目标达成，比如在六个月内拿到至少一个 AI 应用工程师岗位的 offer？ | 完成两个可演示的 Agent 项目并通过 20 道面试题 |
| R4 | confirmation | 方向定为"成为 AI Agent Engineer、找到一份 AI 应用工程师的工作"，完整目标为：在六个月内…是否以此为当前目标？ | 好，就以这个为目标 |

## 反例（必须不通过，逐条给判定依据）

| 反例 | 判定依据 |
|---|---|
| ① 系统直接落库一个模糊目标 | **不通过（即被拒绝）**：存储层强制 `confirmed` 必须四要素齐全 + `source_quote`；且"确认过的目标不可被清空"。测试：`test_confirmed_goal_requires_all_four_elements`、`test_confirmed_goal_requires_source_quote`、`test_confirmed_goal_cannot_be_emptied` |
| ② 未经用户确认就进入能力分析 | **不通过（即被拒绝）**：`require_confirmed_goal()` 是能力分析唯一入口；测试 `test_unconfirmed_goal_is_rejected_before_calling_the_model` 还断言**拒绝发生在调用模型之前**（不浪费 API 调用）；另有"手工改库造出 confirmed 但缺要素"的纵深用例 |

## 轮次上限的实测行为

- 上限用尽仍未就绪 → 抛 `ClarificationLimitReached`，**不自动补齐四要素**。
- 该路径已在真实会话中实测触发（尝试 5：模拟用户答错导致 6 轮耗尽 —— 第 7 个问题未发出，goal 四要素保持为 None，模型还主动指出"回答与问题重复"并列出缺失要素）。诊断见 `artifacts/m2/failure-diagnosis-m2d-04.json`。

## 截图豁免（用户 2026-10-02 确认）

2026-10-05 补充：`session-replay.html` 与 `session-replay.png` 按原始 `session-real.json` 生成，完整展示四轮澄清、用户确认与目标四要素。页面明确标注历史会话、用户侧测试脚本与源文件哈希。此为历史回放可视证据，不是实时交互界面；原截图豁免与实时界面边界保持在案。复现：运行 `scripts/audit_mvp_acceptance.py` 后用浏览器打开回放 HTML。

- **原因**：M2 无 UI（M8 才做界面）。
- **替代形式**：完整会话轨迹导出 —— `artifacts/m2/session-real.json` 含
  `g_goal_clarifications` 全部轮次、`g_agent_runs` 每条运行记录（含实际 provider/model）、
  会话文本与关联标识（`goal_id` / `run_id` / `correlation_id`）。
- **补证计划**：M8 补界面截图；本豁免**只替代截图形式，不豁免 G1 本身的验收要求**。

## 实际 provider/model 记录（可追溯性）

6 条运行记录全部为 `provider=openai_compatible`、`model=glm-5.3-flash`、
`model_source=result`（取自实际返回值，非配置默认值）；`goal_id` 关联到同一次会话。

## 附：本判定的达成路径（如实记录）

澄清能力与能力树**分别**先通过真实验证（尝试 3：澄清 4 轮通过 + 三层树 13 点通过），
但直到**尝试 6** 才在同一次端到端运行内闭环。其间 4 次失败与修复（诊断 m2d-01…04）
均为夹具/提示词/硬编码问题，产品侧逻辑未被降级或绕过。
