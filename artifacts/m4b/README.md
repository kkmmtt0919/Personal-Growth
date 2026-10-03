# M4-b 产物：证据绑定与分桶（LLM 提议 + 确定性闸门 + 映射落库）

> 结果：**离线 9/9 + 真实运行 8/8 检查通过**（2026-10-03）。
> 命令：`uv run python artifacts/m4b/run_binding.py`（离线）／
> `M4_ALLOW_REAL_MODEL=1 uv run --env-file .env python artifacts/m4b/run_binding.py --mode real`（真实，需授权）。

## 本步边界（用户 2026-10-02 冻结）

- **LLM 仅作为候选绑定提议器**（schema 只有 `claim_id` / `capability_path` / `rationale`，
  置信度 / 等级 / 分值字段一律 `extra="forbid"` 拒绝）；
- **确定性闸门八步裁决**：`schema → claim_exists → capability_exists → capability_active →
  bucket_allowed → attribution_unchanged → duplicate → persisted`，**失败不落库**；
- proposal / reject / accept **全量留档**（拒绝记录含 `proposal_id` / `reject_reason` /
  `gate_stage` / `timestamp` / `run_id`）；
- **不做**：星级/评分、attack/反向证据、解释输出、G3 实验、UI；
- **生成器接线推迟**（用户决定）：`supersede_missing` 仅契约层可见，
  `CapabilityModelGenerator.generate` 未改 —— 记 `M4-b scope: generator wiring = deferred`。

## 验收序列与结果

| # | 验收项 | 结果 |
|---|---|---|
| 1 | fake gateway 离线回归 | ✅ 9/9：四类提议（通过 / 路径杜撰 / 归属不通过 / 桶不通过）→ 1 接受 3 拒绝；桥表行数 == 接受数（LLM 无直接落库路径）；二次运行全 duplicate |
| 2 | reject case | ✅ 每一步都有对例：`schema`（confidence/level/score 注入）、`claim_exists`（未知 / 越界）、`capability_exists`（杜撰路径）、`capability_active`（superseded）、`bucket_allowed`（external_ref）、`attribution_unchanged`（user_asserted）、`duplicate` |
| 3 | artifact 清单 | ✅ `binding-offline.json` / `binding-real.json`（proposal / reject / accept 全量，`read_only: true`） |
| 4 | 独立库 hash/count 对锚 | ✅ 真实库逐表内容哈希 + 计数与 `artifacts/m3a/evidence-anchors.json` 一致（运行全程 `mode=ro` 拷贝副本，真实库零写入） |
| 5 | audit_store pass | ✅ 离线与真实运行后均 `pass / 0 violations` |
| 6 | 真实模型一次运行记录 | ✅ 见下 |

## 真实运行记录（2026-10-03）

- 模型：`openai_compatible / glm-5.3`（`model_source=result`；GROWTH_AGENT_* 未设置，按适配层规则回落 `EVKG_*`）
- 预算：应用层 **1 次**结构化调用 / 传输层 **1 个** HTTP 请求（硬上限 1 + 零额外重试）；1364 tokens；4.2s
- 素材：公共仓库 `kkmmtt0919/mytset-rag`（浅克隆 `c417a09692`，20 文件）；能力树 = M2 真实会话
  **首版**树（`session-real.json` 的 `capability_report_first`：3 领域 / 6 组 / 16 个三层点，25 节点）
- 输入：6 条候选（5 条仓库材料口径 claim + 1 条构造的对话自述 claim）
- 产出：LLM 提议 4 条 → **3 接受**（RAG×2、MCP×1）+ **1 拒绝**
  - 拒绝记录：`gate_stage=attribution_unchanged`，理由"准入复核未通过：pending_declaration
    （归属不是 user_declared（实际：['user_asserted']））"
  - 如实记录两点提议质量问题：① LLM 把"测试用例"相关的一条 rationale 写到了自述 claim 上
    （id 与理由错配）；② 5 条仓库 claim 只提议了 3 条 —— **治理边界不依赖提议质量**，
    错配与漏提议都不会造成错误落库（前者被闸门拦下，后者只是未绑定）。
- 落库的每条绑定 rationale 均含：`run=m4b_real_run_001`、`proposer=openai_compatible/glm-5.3`、提议理由。

## 文件

| 文件 | 内容 |
|---|---|
| `run_binding.py` | 双模式运行器（offline fake / real 授权），含真实库只读对锚 |
| `binding-offline.json` / `binding-real.json` | 提议审计产物（全量 proposal / reject / accept） |
| `result-offline-fake.json` / `result-real.json` | 完整运行报告（检查清单 / 计数 / 运行记录 / 预算） |
| `tmp/` | 运行期材料与副本（gitignore；库文件与克隆目录运行后清理） |

## 数据边界

- 真实运行在**真实库副本**上进行（`sqlite3 mode=ro` 读取 + backup 拷贝），真实库未打开写入；
- 临时库运行后删除；克隆目录用 `force_remove_tree`（Windows git pack 只读）清理；
- 构造素材只有一条对话自述样本（`chat-note.md`），已在 artifact 中标注"构造样本"。
