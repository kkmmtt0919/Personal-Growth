# 项目进度

> 只记录当前执行状态和少量近期节点；详细工作日志保存在项目正常材料中。

## 当前任务

| 任务 ID | 任务 | 状态 | 负责人 | 完成条件 | 证据 ID | 最后更新 |
|---|---|---|---|---|---|---|
| M0 | 地基与治理：仓库、账本、架构/路线/验收/决策四文档、环境确认 | 已完成 | ZCode | `--validate` + `--audit` 均 strict_valid 通过；决策已确认 | 无 | 2026-10-01 |
| Q-01 | 用户决策 Q1–Q4（集成方式／模型／前端／多用户） | 已完成 | 用户 | 4 项均已选定 | 无 | 2026-10-01 |
| M1-a | 建 growth 领域包 + 项目 uv 环境（path 依赖 evkg）+ 验证实际生效 | 已完成 | ZCode | `scripts/verify_profile.py` 13/13 通过 | EV-004 | 2026-10-01 |
| M1-b | adapter.py 的 ingest 能力（收敛 evkg 单一入口 + 双轨记录写入） | 已完成 | ZCode | 22 项测试 + 冒烟 PASS + `audit_store` pass(0/10 violations) | EV-006 EV-007 EV-008 | 2026-10-01 |
| M1-c | adapter.py 的 extract 能力（证据 → 能力断言） | 待确认 | ZCode | 抽取产出可追溯的 claims；**需用户提供 LLM API Key** | 无 | 2026-10-01 |
| M1 | 证据底座打通（技术 spike） | 进行中 | ZCode | 见 `docs/ROADMAP.md` M1 完成条件 | EV-004…EV-008 | 2026-10-01 |
| M2 | 目标澄清与能力模型 | 已规划 | — | 通过验收门 G1 | 无 | 2026-10-01 |
| M3 | 证据接入（Upload + GitHub） | 已规划 | — | 见 `docs/ROADMAP.md` M3 | 无 | 2026-10-01 |
| M4 | 能力审计（产品内核） | 已规划 | — | 通过验收门 G2、G3 | 无 | 2026-10-01 |
| M5 | 任务闭环与成长循环 | 已规划 | — | 通过验收门 G4、G5 | 无 | 2026-10-01 |
| M6 | Memory 三层 | 已规划 | — | 见 `docs/ROADMAP.md` M6 | 无 | 2026-10-01 |
| M7 | 主动 Agent | 已规划 | — | 见 `docs/ROADMAP.md` M7 | 无 | 2026-10-01 |
| M8 | UI 三页与端到端验收 | 已规划 | — | G1–G6 + QG1–QG5 全通过 | 无 | 2026-10-01 |

## 阻塞项

| 阻塞 ID | 阻塞 | 影响 | 解除条件 | 状态 |
|---|---|---|---|---|
| B-01 | Q1 evkg 集成方式未定 | 无法建立依赖与适配层，M1 不能开工 | 用户选择 A/B/C | **已解除**（选独立仓库 + path 依赖） |
| B-02 | Q2 LLM 供应商与模型未定 | M1 的抽取与攻击无法实际运行 | 用户确认主模型与是否配 verifier | **已解除**（GLM 主模型 + 独立 verifier） |
| B-03 | Q3 前端技术栈未定 | 仅影响 M8，不阻塞前期 | 用户确认 | **已解除**（React + Vite + TS） |
| B-04 | Q4 多用户/登录未定 | 影响表结构与 API 设计基线 | 用户确认 | **已解除**（单用户本地优先，预留 user_id） |

## 下一步

1. 待用户确认 M1-c 开工，**并提供 LLM API Key**（M1-c 起需要真实模型调用，我无法代为申请）。
2. M1-c：在 adapter 上实现 extract —— 用 growth 领域包把 111 条 passages 抽成能力断言（claim），并核对抽取结果是否遵守"严禁升级"规则（计划/了解 ≠ 具备能力）。
3. `data/growth.db` 已含 3 份真实证据的 111 条 passages，M1-c 可直接在其上继续。

## 进度历史

| 日期 | 会话或任务 ID | 工作内容摘要 | 关键确认或纠正 | 证据 ID | 遗留问题 | 下一步 |
|---|---|---|---|---|---|---|
| 2026-10-01 | M0 | 读取 PRD 全文；克隆并分析 evkg 与 project-to-act；确立分层架构与 Claim→Capability 桥梁设计；建立治理账本；产出 4 份规划文档 | 实测确认 `SourceKind` 为封闭枚举（`domain.py:10`、`policies.py:28`），据此采用双轨记录方案；发现 evkg `.env.example` 的 verifier 变量名与代码不一致（`EVKG_VERIFIER_PROVIDER` 实为 `EVKG_VERIFIER_LLM_PROVIDER`） | 无 | Q1–Q4 待决策 | 等待用户决策后进入 M1-a |
| 2026-10-01 | Q-01 | 用户确认 Q1–Q4，全部采纳推荐方案 | evkg 用独立仓库 + path 依赖；GLM 主模型 + 独立 verifier；前端 React + Vite + TS；单用户本地优先 | 无 | 无 | M1-a 待开工确认 |
| 2026-10-01 | M1-a | 建 `pyproject.toml`（uv path 依赖 evkg）、`growth_os.yaml` 成长领域包、`scripts/verify_profile.py` | ① 实测确认策略覆盖机制：可覆盖 6 个内置 kind 的 baseline/rationale，但**新增 kind 会被静默忽略**（`except ValueError: continue`）→ 双轨记录方案获机制验证；② 布局微调为单包根 `backend/growth_os/`，避免顶层包名冲突 | EV-004 EV-005 | — | M1-b 待开工确认 |
| 2026-10-01 | M1-b | 建 `evidence/adapter.py`（evkg 唯一入口）、`scripts/smoke_ingest.py`、`tests/test_evidence_adapter.py`；用用户提供的真实仓库 `mytset-rag` 入库 | ① **V1 `IngestionService` 不可用于成长证据**：`pipeline.py:221` 把 kind 硬编码为 `UNKNOWN` 且不写 `metadata.assessment`，会让代码证据永久按 0.25 计权 → 改用快路径 + 文本类兜底路由；② `_put` 对 sources 是 `INSERT OR IGNORE`，所以"落库后重存改 metadata"会被静默忽略 → 必须用 `json_set` 定向修补；③ `extract.py:105-106` 依赖 `metadata.assessment`，覆盖它会静默退化置信度 | EV-006 EV-007 EV-008 | M1-c 起需要 LLM API Key | M1-c 待开工确认 |
