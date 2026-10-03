# 项目版本

> 只记录版本状态、兼容性和少量近期发布摘要；工作包与补丁过程保存在发布材料中。

## 当前版本

- 版本号：`0.0.0`
- 发布状态：未发布（M0 + M1 技术 spike + M2 + M3 已完成并收口；**M4 进行中**：M4-PLAN v1.0 已冻结、M4-a / M4-b / M4-c 均已验收）
- 兼容性说明：无对外接口，无兼容性承诺
- 最后更新：2026-10-03（M4-b / M4-c 通过用户验收，EV-068/EV-069）

## 下一版本计划

- 目标版本：`0.1.0`（MVP 内核可演示）
- 计划内容：M1–M5 完成 → 跑通 `Goal → Evidence → Capability → Task → Growth` 闭环，对应验收门 G1–G5
- 发布条件：
  - G1–G5 全部通过且证据未过期
  - 质量门 QG1–QG5 通过（含 evkg 自身测试全绿；b.5d 后为 101 项）
  - `evkg audit_store` = pass；`run_damage_selftest` = caught

## 兼容性与迁移政策

- **evkg 版本**：当前以 `path` 依赖指向 `D:\projects\evkg`（本地已领先远程 **6** 个提交，最新 `9a21552` 为 M4-a 的抽取 provenance 修复；`db2de3a` 为 B-g2 的 PDF 修复）。**归档待刷新**：B-g1 的 bundle 指向 `28afbc0`，不含 `db2de3a`/`9a21552`；需要时按 B-g1 流程重新生成 bundle、更新哈希与 manifest。（未发布版本，无语义化版本号）。开发期允许跟随 `main`；首次发布 `0.1.0` 前必须 pin 到具体 commit SHA 并记录于本表。**交付形式（B-g1，2026-10-02 用户确认）**：本地 Git bundle 归档 + 裸仓寻址（方案 A），维持不推送约束；发布/CI 时切换为 `git + rev` 固定到已验证的 commit SHA（uv 层已实测可行；`editable` 与 `git` 源互斥，故开发期保留 path 依赖）。
- **数据库 schema**：`g_` 表族由本项目自管，MVP 期间允许破坏性变更，但每次变更须在 `PROJECT_FEATURES.md` 或进度历史中留痕。
- **evkg 表族**：只读叠加，不改其 schema；若确需扩展 `SourceKind` 等上游结构，作为上游 commit 提交而非就地修改（决定 D1）。
- **配置**：`EVKG_*` 沿用 evkg 命名空间；Growth OS 自有配置用 `GROWTH_*`。**注意** evkg 仓库 `.env.example` 中的 `EVKG_VERIFIER_PROVIDER` 为错误名称，实际变量是 `EVKG_VERIFIER_LLM_PROVIDER`（已核实 `attack/verifier.py:39-40`）。
- 未定义 API 兼容性承诺：MVP 阶段 APIs 无版本前缀，随时可变。

依赖基线（作为兼容性约束的一部分）：

| 依赖 | 当前指向 | 解析方式 | 备注 |
|---|---|---|---|
| evkg | `D:\projects\evkg` @ `9a21552`（未发布，worktree） | `path` + editable（Q1 已确认） | 开发期依赖。发布 0.1.0 前须改为 commit pin。本地已有 **6** 个上游提交（`a4b15af`、`e432c42`、`068389d`、`28afbc0`、`db2de3a`、`9a21552`），**用户明确要求不得推送到 `redmaplewww/evkg`**（远程停在 `a448f44`） |
| evkg 归档（B-g1） | `D:\projects\_evkg-archive\evkg-28afbc0.bundle`；第二副本 `C:\Users\Lenovo\evkg-archive\` | Git bundle（完整历史，含全部 5 个提交） | **2026-10-02 已归档并验证**：238,807 字节，SHA-256 `10dafff49bb8e627007c4bb5cc3ddfcfce1108ef9b97c42763bf93a8b8c13801`（重新生成字节一致），commit `28afbc0db7061d9717e307bf2bd0833f59fd8f51`；`git bundle verify` = 完整历史/ok，克隆 HEAD 一致、5 提交、fsck 无异常，两副本哈希一致。恢复命令与验证记录见同目录 `evkg-bundle-manifest.txt`（SHA-256 `969d20764db6…`）。**注意**：C:/D: 可能同盘，抗物理损坏需另存移动硬盘/云盘（待用户执行） |
| project-to-act | `D:\projects\project-to-act`；已装至 `~/.zcode/skills/project-to-act/` | 治理工具，非运行时依赖 | 仅用其脚本与约定 |
| Python | 3.12.14（uv 托管） | `requires-python >= 3.11` | 系统解释器为 3.7.8，必须走 uv |
| uv | 0.12.10 | — | 已验证可用 |
| Node | 24.15.0 | — | M8 前端使用 |

## 版本历史

| 版本号 | 日期 | 状态 | 主要变更摘要 | 兼容性 | 证据 ID | Gate 结果 |
|---|---|---|---|---|---|---|
| 0.0.0 | 2026-10-01 | 规划中 | M0 地基：仓库与治理账本建立；架构/路线/验收/决策四份规划文档；技术选型待确认 | 无接口 | 无 | 未执行 |
| 0.0.0 | 2026-10-02 | 规划中（spike 完成） | M1 证据底座打通与 spike 收口：evkg 4 个上游提交 + 适配层单入口；真实材料 3 来源/109 段落/2 主张全链路；D1 双实例实测；依赖策略判定 = 有条件依赖（C1–C5）；两项在案阻塞（B-g1 依赖 pin、B-g2 M3 前富格式 spike） | 无对外接口；evkg 依赖仍为本地 path（发布前须 pin commit） | EV-004…EV-046 | M1-g 通过，spike 结束 |
| 0.0.0 | 2026-10-02 | 规划中（内核前段完成） | M2 目标澄清与能力模型（G1 通过）+ M3 证据接入（Gate 13/13）：归属层与越权闸门、材料/PDF/GitHub 公共仓库/JD 四通道、材料口径 claim + audit + provenance；B-g2 上游一行修复；M4 范围冻结草案（`docs/M4-PLAN.md` v0.1）待确认 | 无对外接口；evkg 依赖仍为本地 path（领先 5 提交、未推送；bundle 归档待刷新） | EV-050…EV-065 | M2 收口、M3 Gate 通过 |
| 0.0.0 | 2026-10-02 | 规划中（M4 进行中） | M4-PLAN v1.0 冻结（七项确认）+ M4-a：Assessment 基础模型契约（草案 / 准入闸门 / 生命周期）、C5 抽取 provenance 上游修（evkg `9a21552`）、`claim/evidence → draft → 独立 audit artifact` 最小闭环 | 无对外接口；evkg 依赖仍为本地 path（领先 6 提交、未推送；bundle 归档待刷新） | EV-066 EV-067 | M4-a 通过（用户已验收） |
| 0.0.0 | 2026-10-03 | 规划中（M4 进行中） | M4-b：证据绑定与分桶（LLM 提议 + 八步确定性闸门 + 映射落库）—— 分桶映射、提议 schema 三字段、逐步 reject、离线闭环 9/9、1 次真实模型运行 8/8（3 接受 + 1 拒绝） | 无对外接口；evkg 依赖不变（本地 path，领先 6 提交） | EV-068 | M4-b 通过（用户已验收） |
| 0.0.0 | 2026-10-03 | 规划中（M4 进行中） | M4-c：评级与反向证据 —— 两维度（理解 / 实践）星级规则引擎、attack 结算（broken/refutes/disputed/weakened）、`rated` 写入路径（草案不覆盖、等级变化=新行） | 无对外接口；evkg 依赖不变（本地 path，领先 6 提交） | EV-069 | M4-c 通过（用户已验收） |
