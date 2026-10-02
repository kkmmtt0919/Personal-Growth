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
| M1-b.5b | evkg assessment 语义：`UNASSESSED ≠ 0.25`（缺失值不参与加权、不凭空抬高） | 已完成 | ZCode | evkg 81 项 + 本仓 27 项全绿；前后对照实证；7 项下游消费者检查通过；lint 无新增 | EV-013…EV-016 | 2026-10-01 |
| M1-b.5c | evkg 写入语义：逻辑身份 id + `content_hash` + 显式 upsert + passage 级联替换 | 已完成 | ZCode | evkg 93 项 + 本仓 27 项全绿；三态循环与 A→B 性质在真实材料上验证；lint 未新增 | EV-017…EV-020 | 2026-10-01 |
| M1-b.5d | adapter 变薄：删除裸 SQL / metadata 补丁 / 自造路由；加边界检查防回潮 | 已完成 | ZCode | evkg 101 项 + 本仓 38 项全绿；边界检查 11 项；b.5b/b.5c 实证复跑通过 | EV-021…EV-024 | 2026-10-01 |
| M1-c | adapter.py 的 extract 能力（证据 → 能力断言） | 已挂起 | ZCode | 抽取产出可追溯的 claims；**需用户提供 LLM API Key** | 无 | 2026-10-01 |
| M1 | 证据底座打通（技术 spike） | 进行中（a/b/c 三层已闭环，M1-c 未启动） | ZCode | 见 `docs/ROADMAP.md` M1 完成条件 | EV-004…EV-024 | 2026-10-01 |
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

M1 的三层基础已闭环（用户 2026-10-01 确认）：**a 入库 → b 证据模型 → c 适配层边界**。
其中 b 层含四项：code（b.5a 的 `SourceKind.CODE` / `CodeReader` / 行范围 locator）、
locator（b.5a 起可无条件切回原文，由测试锁死）、assessment（b.5b 起缺失 ≠ 0.25 且标明
分级来源）、source lifecycle（b.5c 的逻辑身份 / `content_hash` / 三态写入 / 级联替换）；
c 层由 b.5d 完成，适配层只留领域语义，边界由 `tests/test_adapter_boundary.py` 守住。

1. **待用户确认进入 M1-c（extract）** —— 仍需用户提供 LLM API Key。
2. M1-c 前的可选事项：把 evkg 的 4 个上游提交整理为 issue/PR（提案文本已完备，
   见 `docs/UPSTREAM-evkg-commits.md`；**推送需用户另行指示**）。

### 重要约束（用户指定）

- **不把 evkg 的任何提交推送到 `redmaplewww/evkg`**。evkg 本地现领先远程 3 个提交
  （`a4b15af`、`e432c42`、`068389d`），远程停在 `a448f44`。改动提案见
  `docs/UPSTREAM-evkg-commits.md`（b.5c 的提案待补充）。

## 进度历史

| 日期 | 会话或任务 ID | 工作内容摘要 | 关键确认或纠正 | 证据 ID | 遗留问题 | 下一步 |
|---|---|---|---|---|---|---|
| 2026-10-01 | M0 | 读取 PRD 全文；克隆并分析 evkg 与 project-to-act；确立分层架构与 Claim→Capability 桥梁设计；建立治理账本；产出 4 份规划文档 | 实测确认 `SourceKind` 为封闭枚举（`domain.py:10`、`policies.py:28`），据此采用双轨记录方案；发现 evkg `.env.example` 的 verifier 变量名与代码不一致（`EVKG_VERIFIER_PROVIDER` 实为 `EVKG_VERIFIER_LLM_PROVIDER`） | 无 | Q1–Q4 待决策 | 等待用户决策后进入 M1-a |
| 2026-10-01 | Q-01 | 用户确认 Q1–Q4，全部采纳推荐方案 | evkg 用独立仓库 + path 依赖；GLM 主模型 + 独立 verifier；前端 React + Vite + TS；单用户本地优先 | 无 | 无 | M1-a 待开工确认 |
| 2026-10-01 | M1-a | 建 `pyproject.toml`、`growth_os.yaml` 成长领域包、`scripts/verify_profile.py` | ① 实测确认策略覆盖机制：可覆盖内置 kind 的 baseline/rationale，但**新增 kind 会被静默忽略**（`except ValueError: continue`）；② 布局微调为单包根 `backend/growth_os/` | EV-004 EV-005 | — | M1-b 待开工确认 |
| 2026-10-01 | M1-b | 建 `evidence/adapter.py`（evkg 唯一入口）、`scripts/smoke_ingest.py`、`tests/test_evidence_adapter.py`；用真实仓库 `mytset-rag` 入库 | ① V1 `IngestionService` 把 kind 硬编码为 `UNKNOWN` 且不写 `metadata.assessment`；② `_put` 对 sources 是 `INSERT OR IGNORE`；③ `extract.py:105-106` 依赖 `metadata.assessment` | EV-006 EV-007 EV-008 | M1-c 起需要 API Key | M1-c 待开工确认 |
| 2026-10-01 | 架构评审 | 用户指出 adapter 正在替 evkg 打业务补丁，应改为修 evkg 通用能力、让 adapter 变薄；据此把 M1-c 挂起，改为 M1-b.5（四小步） | 我核实后收窄范围并提出三点修正：`Passage.locator` 本就存在（缺的是填充而非结构）；三个"缺口"实为 `_save_source_passages` 单一有损交接点；`SourceKind.UNKNOWN`（类型未知，合理低先验）与"未评估"（缺失值）是两件事。用户接受修正并选定 b.5c 用方案 (a) | — | — | M1-b.5a 开工 |
| 2026-10-01 | M1-b.5a | 修 evkg：`SourceKind.CODE`、`CodeConfig`+`code_language_for`、`CodeReader`、`split_code_passages`、`ingest_code_file`、CLI 分派、默认 readers 顺序；本仓：growth 领域包加 code、adapter 改走 `ingest_code_file` 并**删掉自造 text_like 路由** | ① `normalize_document` 会折叠空白并重排行（8 行 Java 塌成 3 行、缩进全失）→ 经 V1 状态机无法保真行号；② passage id 含切分方案 → 换切分器后旧 passage 只累积不替换（实测混入 11 条被撕裂的旧片段）→ 移入 b.5c；③ 切分器经四轮实测修正才收敛；④ **D1 的预测被证伪**（"MVP 大概率不需要改 evkg"），但 D1 的决策成立 | EV-009…EV-012 | symbol 级精度需解析器；累积问题待 b.5c | M1-b.5b 待开工确认 |
| 2026-10-01 | M1-b.5b | 修 evkg assessment 语义：`ASSESSED`/`UNASSESSED` 与 `assess_unassessed()`/`resolve_source_assessment()`；两处 `default=0.25` 移除；`Confidence.score`/`source_reliability` 与 `EvidenceLink.confidence` 可空并加 `assessment_status`；三个消费者同步 | ① **危害实测**：kind=code 来源无缓存分级就按 0.25 计权，同源同内容差 **0.55** 且静默 → 修复后 0.00；② 按 kind 推导不是"发明数字"（同一份策略表的确定性函数），并用 `origin` 标出"未逐来源评估"；③ 缺失必须**双向设防**：既不得兜底低分，也不得兜底高分；④ 未新建 claim 生命周期（沿用 `ClaimStatus`，未分级记为 `DISPUTED`）；⑤ 测试按"先写后改"，并用实证脚本单独留证旧行为 | EV-013…EV-016 | — | M1-b.5c 待开工确认 |
| 2026-10-01 | M1-b.5d | 适配层变薄：删掉 `_tag_source` 的裸 SQL、自造后缀路由与 metadata 补丁；evkg 补 `ingest_path()` 统一路由与 `find_sources()` 按 metadata 检索；新增边界检查测试防止耦合回潮 | ① 用户把目标收窄为「**证明 Growth OS 不再需要知道 evkg 内部存储细节**」，并要求加一项**适配层依赖检查** —— 我做成静态 AST 检查（禁 `sqlite3` / `.db.execute` / `json_set` / `json_extract` / 内联 SQL / 下划线成员 / `evkg.ingest.connectors`），因为"M1-b.5c 期间我自己就复用了 OR-IGNORE 的 helper"，证明靠小心守不住；② `IngestResult.route` 被删除：路由是 evkg 的实现细节，`kind=="code"` 已能表达同一事实；③ 检查最初误报文档字符串（我写的"不做什么"说明里含这些词）→ 改为先剥 docstring 再匹配 | EV-021…EV-024 | symbol 级精度待解析器；evkg 不得推送远程 | 待用户确认进入 M1-c |
| 2026-10-01 | M1-b.5c | 修 evkg 写入语义：`logical_source_id()` 统一两套 id 方案、`Source.content_hash`（基于换行规范化文本）、`save_source` 返回 inserted/updated/unchanged 且 metadata 合并、`_put` 对 sources 改真 upsert、`save_passages` 整体替换、新增 `purge_passages()` 级联清理；pipeline 透传 kind 与 content_hash | ① **我自己踩了用户警告过的坑**：更新分支复用了 `_put`（`INSERT OR IGNORE`），`save_source` 报 updated 但库里仍是旧值 → 已把 `_put` 对 sources 改成真 upsert 从根上消除；② **content_hash 不能用原始字节**：manifest 路径早已按规范化文本取哈希，而快路径用原始字节，两条路径互相矛盾；且原始字节哈希会让一次 git checkout 换行把所有来源判成"已变"→ 统一为「content_hash 相同 ⟺ 段落所依据的文本相同」；③ **新增发现：删 passage 必须级联**，否则同时点亮四条不变量（留下自己审计不过的库）→ 实现 `purge_passages()` 并返回各表清理数量（级联删除是真实数据损失，必须可见）；④ `read_bytes().decode()` 不做换行翻译，CRLF 会让 `\r` 混进 passage 文本并让 locator 校验失败 → 新增 `decode_text()` 显式统一换行 | EV-017…EV-020 | symbol 级精度需解析器；evkg 不得推送远程 | M1-b.5d 待开工确认 |
