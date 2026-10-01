# 项目版本

> 只记录版本状态、兼容性和少量近期发布摘要；工作包与补丁过程保存在发布材料中。

## 当前版本

- 版本号：`0.0.0`
- 发布状态：未发布（M0 地基阶段，仅规划文档与治理账本）
- 兼容性说明：无对外接口，无兼容性承诺
- 最后更新：2026-10-01

## 下一版本计划

- 目标版本：`0.1.0`（MVP 内核可演示）
- 计划内容：M1–M5 完成 → 跑通 `Goal → Evidence → Capability → Task → Growth` 闭环，对应验收门 G1–G5
- 发布条件：
  - G1–G5 全部通过且证据未过期
  - 质量门 QG1–QG5 通过（含 evkg 自身测试全绿；b.5b 后为 81 项）
  - `evkg audit_store` = pass；`run_damage_selftest` = caught

## 兼容性与迁移政策

- **evkg 版本**：当前以 `path` 依赖指向 `D:\projects\evkg`（未发布版本，无语义化版本号）。开发期允许跟随 `main`；首次发布 `0.1.0` 前必须 pin 到具体 commit SHA 并记录于本表。
- **数据库 schema**：`g_` 表族由本项目自管，MVP 期间允许破坏性变更，但每次变更须在 `PROJECT_FEATURES.md` 或进度历史中留痕。
- **evkg 表族**：只读叠加，不改其 schema；若确需扩展 `SourceKind` 等上游结构，作为上游 commit 提交而非就地修改（决定 D1）。
- **配置**：`EVKG_*` 沿用 evkg 命名空间；Growth OS 自有配置用 `GROWTH_*`。**注意** evkg 仓库 `.env.example` 中的 `EVKG_VERIFIER_PROVIDER` 为错误名称，实际变量是 `EVKG_VERIFIER_LLM_PROVIDER`（已核实 `attack/verifier.py:39-40`）。
- 未定义 API 兼容性承诺：MVP 阶段 APIs 无版本前缀，随时可变。

依赖基线（作为兼容性约束的一部分）：

| 依赖 | 当前指向 | 解析方式 | 备注 |
|---|---|---|---|
| evkg | `D:\projects\evkg` @ `068389d`（未发布，worktree） | `path` + editable（Q1 已确认） | 发布 0.1.0 前须改为 commit pin。本地已有 3 个上游提交（`a4b15af`、`e432c42`、`068389d`），**用户明确要求不得推送到 `redmaplewww/evkg`**（远程停在 `a448f44`） |
| project-to-act | `D:\projects\project-to-act`；已装至 `~/.zcode/skills/project-to-act/` | 治理工具，非运行时依赖 | 仅用其脚本与约定 |
| Python | 3.12.14（uv 托管） | `requires-python >= 3.11` | 系统解释器为 3.7.8，必须走 uv |
| uv | 0.12.10 | — | 已验证可用 |
| Node | 24.15.0 | — | M8 前端使用 |

## 版本历史

| 版本号 | 日期 | 状态 | 主要变更摘要 | 兼容性 | 证据 ID | Gate 结果 |
|---|---|---|---|---|---|---|
| 0.0.0 | 2026-10-01 | 规划中 | M0 地基：仓库与治理账本建立；架构/路线/验收/决策四份规划文档；技术选型待确认 | 无接口 | 无 | 未执行 |
