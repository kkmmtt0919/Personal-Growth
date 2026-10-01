# 项目进度

> 只记录当前执行状态和少量近期节点；详细工作日志保存在项目正常材料中。

## 当前任务

| 任务 ID | 任务 | 状态 | 负责人 | 完成条件 | 证据 ID | 最后更新 |
|---|---|---|---|---|---|---|
| M0 | 地基与治理：仓库、账本、架构/路线/验收/决策四文档、环境确认 | 已完成 | ZCode | `--validate` + `--audit` 均 strict_valid 通过；决策已确认 | 无 | 2026-10-01 |
| Q-01 | 用户决策 Q1–Q4（集成方式／模型／前端／多用户） | 已完成 | 用户 | 4 项均已选定 | 无 | 2026-10-01 |
| M1-a | 建 growth 领域包 + 项目 uv 环境（path 依赖 evkg）+ 验证实际生效 | 已完成 | ZCode | `scripts/verify_profile.py` 13/13 通过 | EV-004 | 2026-10-01 |
| M1-b | adapter.py 的 ingest 能力（收敛 evkg 单一入口 + 双轨记录写入） | 已完成 | ZCode | 22 项测试 + 冒烟 PASS + `audit_store` pass(0/10 violations) | EV-006 EV-007 EV-008 | 2026-10-01 |
| M1-b.5a | evkg 源码一等支持：`SourceKind.CODE` + `CodeReader` + 行范围 locator | 已完成 | ZCode | evkg 61 项 + 本仓 27 项全绿；lint 未新增；旧数据零变更 | EV-009…EV-012 | 2026-10-01 |
| M1-b.5b | evkg assessment 生命周期：`UNASSESSED ≠ 0.25` | 待确认 | ZCode | 缺失 assessment 不再被当作低分；复用 `ClaimStatus` 词汇 | 无 | 2026-10-01 |
| M1-b.5c | evkg 写入语义：逻辑身份 id + `content_hash` + 显式 upsert | 待确认 | ZCode | 换切分器后旧 passage 不再累积 | 无 | 2026-10-01 |
| M1-b.5d | adapter 变薄：删掉裸 SQL / metadata 补丁 | 待确认 | ZCode | `_tag_source` 的 SQL 修补可移除 | 无 | 2026-10-01 |
| M1-c | adapter.py 的 extract 能力（证据 → 能力断言） | 已挂起 | ZCode | 抽取产出可追溯的 claims；**需用户提供 LLM API Key** | 无 | 2026-10-01 |
| M1 | 证据底座打通（技术 spike） | 进行中 | ZCode | 见 `docs/ROADMAP.md` M1 完成条件 | EV-004…EV-012 | 2026-10-01 |
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

1. 待用户确认 M1-b.5b 开工。
2. M1-b.5b：改 evkg 的 assessment 语义 —— 区分「未评估」与「低分」。
   两处 `default=0.25`（`policies.py:36`、`verifier.py:87`）改为显式缺失语义；
   复用既有 `ClaimStatus` 词汇，不新造状态机；**不动 `unknown` kind 的先验**。
3. 验收要求（用户指定）：必须证明旧数据没有被错误升级 —— 尤其要证明
   `UNASSESSED` 不会被 extraction 当成高可信，而是**等待评估后才参与加权**。

## 进度历史

| 日期 | 会话或任务 ID | 工作内容摘要 | 关键确认或纠正 | 证据 ID | 遗留问题 | 下一步 |
|---|---|---|---|---|---|---|
| 2026-10-01 | M0 | 读取 PRD 全文；克隆并分析 evkg 与 project-to-act；确立分层架构与 Claim→Capability 桥梁设计；建立治理账本；产出 4 份规划文档 | 实测确认 `SourceKind` 为封闭枚举（`domain.py:10`、`policies.py:28`），据此采用双轨记录方案；发现 evkg `.env.example` 的 verifier 变量名与代码不一致（`EVKG_VERIFIER_PROVIDER` 实为 `EVKG_VERIFIER_LLM_PROVIDER`） | 无 | Q1–Q4 待决策 | 等待用户决策后进入 M1-a |
| 2026-10-01 | Q-01 | 用户确认 Q1–Q4，全部采纳推荐方案 | evkg 用独立仓库 + path 依赖；GLM 主模型 + 独立 verifier；前端 React + Vite + TS；单用户本地优先 | 无 | 无 | M1-a 待开工确认 |
| 2026-10-01 | M1-a | 建 `pyproject.toml`（uv path 依赖 evkg）、`growth_os.yaml` 成长领域包、`scripts/verify_profile.py` | ① 实测确认策略覆盖机制：可覆盖 6 个内置 kind 的 baseline/rationale，但**新增 kind 会被静默忽略**（`except ValueError: continue`）→ 双轨记录方案获机制验证；② 布局微调为单包根 `backend/growth_os/`，避免顶层包名冲突 | EV-004 EV-005 | — | M1-b 待开工确认 |
| 2026-10-01 | M1-b | 建 `evidence/adapter.py`（evkg 唯一入口）、`scripts/smoke_ingest.py`、`tests/test_evidence_adapter.py`；用用户提供的真实仓库 `mytset-rag` 入库 | ① **V1 `IngestionService` 不可用于成长证据**：`pipeline.py:221` 把 kind 硬编码为 `UNKNOWN` 且不写 `metadata.assessment`；② `_put` 对 sources 是 `INSERT OR IGNORE`，"落库后重存改 metadata"会被静默忽略；③ `extract.py:105-106` 依赖 `metadata.assessment`，覆盖它会静默退化置信度 | EV-006 EV-007 EV-008 | M1-c 起需要 LLM API Key | M1-c 待开工确认 |
| 2026-10-01 | 架构评审 | 用户指出 adapter 正在替 evkg 打业务补丁，应改为修 evkg 通用能力、让 adapter 变薄；据此把 M1-c 挂起，改为 M1-b.5（四小步） | 我核实后收窄了范围并提出三点修正：`Passage.locator` 本就存在（缺的是填充而非结构）；三个"缺口"实为 `_save_source_passes` 单一有损交接点；`SourceKind.UNKNOWN`（类型未知，合理低先验）与"未评估"（缺失值）是两件事。用户接受修正并选定 b.5c 用方案 (a) 逻辑身份 + content_hash | — | — | M1-b.5a 开工 |
| 2026-10-01 | M1-b.5a | 修 evkg：`SourceKind.CODE`、`CodeConfig`+`code_language_for`、`CodeReader`、`split_code_passages`、`ingest_code_file`、CLI 分派、默认 readers 顺序；本仓：growth 领域包加 code 基线、adapter 改走 `ingest_code_file` 并**删掉自造 text_like 路由** | ① **新增发现：`normalize_document` 会折叠空白并重排行**（实测 8 行 Java 塌成 3 行、缩进全失）→ 经 V1 状态机无法保真行号，因此 `ingest_code_file` 刻意绕开它；② **新增发现：passage id 含切分方案**，换切分器后旧 passage 不被替换只累积（实测一个源里混入 11 条被撕裂的旧片段）→ 该问题正式移入 b.5c；③ 切分器经三轮修正才正确（块缩进取最小值 → 退格到主体层才切 → 合并按总行数设上限），最终 RagService.java 9 段/最大 25 行/0 条仅括号噪声/0 条说谎 locator；④ **D1 的预测被证伪**：D1 曾判断"MVP 大概率不需要改 evkg"，实际需要；但 D1 的决策（不 fork、走上游 commit）成立，本次即为上游 commit `a4b15af` | EV-009 EV-010 EV-011 EV-012 | symbol 级精度仍需解析器（已明确排除）；跨切分器重入库的累积问题待 b.5c | M1-b.5b 待开工确认 |
