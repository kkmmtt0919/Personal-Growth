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
| M1-c | extract：证据 → 能力断言（用户已提供 API Key） | 已完成 | ZCode | 109/109 passage 完成抽取；claim 可逐字回溯；QG1 pass | EV-025…EV-028 | 2026-10-01 |
| M1-d | attack：对能力断言做攻击（deterministic/verifier/contradiction/adversarial/audit） | 已完成 | ZCode | 攻击样例与复核结果留档；QG1 pass；独立复核已核实生效 | EV-029…EV-032 | 2026-10-01 |
| M1-e | dossier：能力证据档案（含证据链、缺失证据、两类独立、证据局限） | 已完成 | ZCode | 两份档案 + 索引产出；35/35 核对通过；QG1 pass | EV-033…EV-036 | 2026-10-01 |
| M1-f | damage selftest：伪造数据能否被发现、拒绝并恢复一致 | 已完成 | ZCode | 三个场景全部 caught；清理后 audit=pass/0 且数据表零差异；真实库未被触碰 | EV-037…EV-041 | 2026-10-01 |
| M1-g | 技术 spike 结论收口：R1–R4 + D1 依赖边界（含双实例隔离实测） | 已完成 | ZCode | 结论文档落盘；evkg 101（正/逆序）+ 本仓 73 全绿；D1 污染实测；三项上游缺陷复现；策略判定=有条件依赖 | EV-042…EV-046 | 2026-10-02 |
| M1 | 证据底座打通（技术 spike） | **已完成（spike 结束）** | ZCode | R1–R4/D1 已收口；依赖策略 = 有条件依赖（C1–C5） | EV-004…EV-046 | 2026-10-02 |
| M2 | 目标澄清与能力模型 | 进行中（基线已冻结，2026-10-02） | ZCode | 通过验收门 G1；完成条件见 `docs/M2-PLAN.md` §5（12 条验收项，含 C1–C3 补充约束） | 无 | 2026-10-02 |
| M2-a | `g_` 四表 + `growth_store` + 最小运行时（含网关接缝/fake）+ 边界守卫收窄与补偿检查 | 已完成 | ZCode | 测试 97 项全绿（新增 24）；AC7/AC8/AC12 通过；真实库零改动（QG1 pass/0） | EV-051 | 2026-10-02 |
| M2-b | Goal Agent + 澄清状态机（≤6 轮硬上限、显式确认、未确认拒绝能力分析） | 已完成 | ZCode | 8 项新测试；第 7 轮被拒且未发模型、确认需原话、增量累积不被擦除 | EV-052 | 2026-10-02 |
| M2-c | 能力树生成 + 形状校验（≥3 领域/≥12 能力点/≤3 层）+ 调整保护 + 来源与校验标注 | 已完成 | ZCode | 11 项新测试 + 离线端到端演练 11/11；测试总数 116 全绿；不写半棵树 | EV-053 | 2026-10-02 |
| M2-d | G1 证据产出（真实模型会话） | 暂停中（尝试 2–5 已跑；尝试 5 失败于模拟用户匹配缺陷，待你确认修复） | ZCode | 产品侧行为正确（6 轮上限生效、不自动补齐、模型主动指出回答重复）；缺口在 `tests/goal_flow_fixtures.py` 的模拟用户。**未自动重试** | EV-055；诊断 `m2d-02/03/04.json` | 2026-10-02 |
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
| B-05 | evkg 依赖不可从他机复现：本地领先远程 4 个提交且不得推送，依赖为 worktree path | 换机/CI/发布时构建不可复现；M8 端到端验收必然触发 | 用户确认交付形式并执行归档 | **已解除**（B-g1：用户 2026-10-02 确认方案 A —— 本地 bundle 归档 + 双副本 + 恢复验证完成，见 EV-049；维持不推送；发布/CI 前切换 `git + rev` pin） |
| B-06 | 富格式（PDF/docx/xlsx）上传路径 0 端到端验证（V1 状态机 + providers 未被 Growth OS 测试覆盖） | M3（Upload）无法验收 | M3 开工前先做 spike：真实 PDF 走 V1 状态机入库 + audit + locator 可核对性结论 | **未解除**（B-g2，见 §9.1） |

## 下一步

M1 技术 spike 已结束并**正式归档**（用户 2026-10-02 确认）。B-g1 已按用户选择落定为
**本地 Git bundle 归档（方案 A，维持不推送）**，归档、双副本与恢复验证完成（EV-049）。
依赖策略保持**有条件依赖（C1–C5）**，条件见 `docs/M1-SPIKE-CONCLUSION.md` §6.3。

1. **M2 进行中**：基线冻结（EV-050），M2-a/b/c 已完成（EV-051/052/053），
   M2-d 演练脚本修复已完成并离线验证（EV-054）。**M2-d 暂停中，等待真实调用授权**：
   第 1 次真实尝试失败（脚本缺陷）已按用户要求保留原始记录未改写；
   修复后离线演练 13/13、测试 128 项全绿、真实库哈希与证据计数未变。
   重跑所需：`--gateway real --model glm-5.3-flash` + `M2_ALLOW_REAL_MODEL=1`。
   **两层预算**（EV-055）：应用层 ≤8 次结构化调用（澄清 ≤6 + 生成 2）；
   传输层 HTTP ≤8 且 `EVKG_HTTP_RETRIES=1`（零额外重试），触顶抛异常立即停止；
   失败即停并写 `session-<mode>-failed.json`（含两层计数、tokens、失败原因），不自动重跑。

   **提示词补丁已生效**（节点名禁「/」），尝试 5 已用它跑过：树未及生成，澄清先失败。
   **当前待你确认的下一项修复**（见 `artifacts/m2/failure-diagnosis-m2d-04.json`）：
   模拟用户改为「意图候选 + 未答要素优先 + 位置消歧 + 显式未匹配」，并把尝试 4/5 的
   真实问句逐条作为回归用例 —— 这正是你早先要求的"不能只靠宽泛关键词匹配"。
   继承边界：M2 不产生用户星级、不触碰 evkg 证据层（有零写入断言）；归属层须在 M3/M4
   前定稿；`g_agent_runs` 记录实际 provider/model（C2）；LLM 路径离线回归（C3）。
2. **B-g2（M3 开工前）**：富格式（PDF/docx/xlsx）上传路径 spike。
3. **归档第三副本（用户执行）**：C:/D: 可能同物理盘，抗物理损坏需另存移动硬盘/云盘。
4. **发布/CI 前**：evkg 依赖切换为 `git + rev` 并复跑两套测试（步骤见归档 manifest）。
5. **可选**：把 M1-g §8 的上游改进清单（11 条）整理为 issue/PR 文本；**推送需用户另行指示**。

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
| 2026-10-01 | M1-f | 故障注入自测：跑 evkg 内置 damage 自测 + 两个**受控注入**（伪造引文 / 不存在的 passage_id），逐表核对清理恢复，并确认真实库未被触碰 | ① 用户把范围严格限定为「数据一致性」并要求 missed 不得修补；② **发现内置自测的测量盲区**：它把注入→审计→清理放在同一函数内，`finally` 立即删除注入行，故在其返回后数违规条数只见已清理状态，无法独立验证注入期间确有违规 → 另做两个受控注入自行前后测量（0→1）；③ 内置自报的 1 条与受控独立测得的 0→1 相互印证；④ 两个受控场景打的是**不同不变量**（引文保真 vs 引用完整性），与内置场景并不相同；⑤ 测试计数断言最初把 audit_log 也算进去而失败——审计流水本就该增长，改为只比对数据表；⑥ 全程在真实库副本上做，逐表确认真实库零差异；⑦ 事后按用户规格把「真实 evidence 不变」从**计数级加固到内容级**（逐行 payload 哈希，补上计数级验不出「条数不变但内容被改写」的盲区） | EV-037…EV-040 | 归属层待 M2/M4 决策；partial 渲染与抽取模型 metadata 记录为上游项，不在本步处理 | M1-g 待确认 |
| 2026-10-02 | M1-g | 技术 spike 收口：复跑两套测试 / D1 双实例隔离实测 / 实库 audit 与追溯链核验 / 三项上游缺陷复现 / 行级覆盖实测 / 补跑 init 与 reindex，结论文档落盘 | ① **D1 实测**：profile 为进程级全局 —— 未重激活 A 时 storeA 再入库同一文件段落 4→2；asyncio 交错同样污染；实例挂 `profile` 无效；per-call `activate` 仅顺序可用，**并发隔离必须改上游**；② 适配层 footgun：未 `configure()` 静默用默认领域包；③ partial 渲染哨兵复现（上游 Markdown 无 partial、有 supports 对照）；④ caught 截断复现（violations=13 但 missed）；⑤ 抽取模型名未持久化；⑥ 覆盖：adapter 83.3% / dossier 96.1%，**LLM 路径无自动化测试**；⑦ 判定 **有条件依赖 C1–C5**；⑧ 补跑 init（35 表）与 reindex（FTS5 109+2、幂等、audit pass）；⑨ 真实库哈希前后一致；⑩ B-g1 方案实测：bundle 字节可复现、uv `file://`+`rev` pin 成立、`editable` 与 `git` 互斥 | EV-042…EV-048 | 用户确认收口；B-g1 交付形式待定；B-g2 M3 前富格式 spike | M2 待确认开工 |
| 2026-10-02 | M2 基线冻结 | 将 5 项确认决策 + C1–C3 补充约束写入 `docs/M2-PLAN.md`，完成开工前 4 项检查（设计级）：验收→测试/证据映射、数据结构区分建议值/人工值/未评估、fake gateway 离线独立、变更不越界 | ① 发现并解决一处设计冲突：M1 的**全包禁 sqlite3** 与 M2 自建 `g_` 表冲突 → 收窄为"证据层全禁 + `store/` 白名单"，并新增 3 项补偿检查（`g_` 前缀静态守卫、证据层零写入功能断言、D1 导入边界继续全包生效）；② 增补字段锁定三条语义：稳定能力点 id（防再生成累积，M1-b.5c 教训）、人工值保护（C1）、`current_level` 恒 NULL + `unassessed`（决定 5）；③ 用户补充约束全部落地：R5 不得伪装已验证、failed run 也要可诊断、provider/model 必须取自实际 gateway | EV-050 | — | M2-a 开工 |
| 2026-10-02 | M2-a | `g_` 四表存储（`growth_os/store`）+ 最小运行时（`growth_os/agent`）+ 网关接缝（Protocol/Fake）+ 适配层网关工厂 + 边界守卫收窄与补偿检查 + 24 项新测试 | ① **不重蹈上游缺陷**：自有 `GrowthStore` 提供 `close()`/上下文管理器，并有"关掉后能删文件"的测试（对应 M1-g 记录的 evkg 无 close() 锁库问题）；② **运行记录按 C2 落地**：成功取自 `GatewayResult`（`model_source=result`），失败取自 `describe()` 并标 `config_on_error`，失败也落库；③ **离线按 C3 落地**：fake gateway + 无密钥 + `httpx.AsyncClient` 实例化即断言失败；④ **边界收窄有补偿**：静态守卫"`store/` 只碰 g_ 表"+ 功能断言"M2 流程后库中无任何 evkg 表"（AC12）；⑤ 冻结语义被测试锁定：confirmed 四要素+原话、确认过的目标不可清空、`adjusted` 不被再生成覆盖、`current_level` 非空即报错；⑥ 真实库零改动（g_ 表仍为空、证据表计数不变 3/109/2/6、QG1 pass/0） | EV-051 | M2-b 待推进 | M2-b：Goal Agent + 澄清状态机 |
| 2026-10-02 | M2-b | Goal Agent + 澄清状态机 + 8 项新测试；`FakeGateway` 支持响应序列/可调用响应，`AgentRuntime` 新增 `call_model_with_run`（运行号回传） | ① **状态迁移由代码决定，不交给模型**：提示词只负责"问什么"，`draft→clarifying→proposed→confirmed` 的迁移与校验在 `GoalAgent` 与存储层双层执行；② 三条硬约束测试锁定：第 7 轮抛 `ClarificationLimitReached` 且**第 7 个问题从未发给模型**（`gateway.calls==6`）、`proposed` 不自动确认（需显式 `confirm` + 用户原话，原话补记到确认问句使轨迹完整）、`require_confirmed_goal()` 为唯一前置门（含"手工改库造出 confirmed 缺要素"纵深用例）；③ 发现并修掉一个真实缺陷：后续轮次未重述的要素会被 `None` 擦掉 → 改为**增量累积**并加回归用例；④ 确认不调用模型（状态迁移不该花 API 调用，也不该让模型"代用户同意"） | EV-052 | — | M2-c |
| 2026-10-02 | M2-c | 能力树生成器（形状校验先于写入）+ `g_capabilities.target_level` 写入范围校验 + 11 项新测试 + 离线端到端演练 runner（`artifacts/m2/`） | ① 形状违规**整体拒绝、不写半棵树**（五种违规用例：领域不足/能力点不足/超 3 层/缺父节点/等级越界；拒绝时能力表为 0 而运行记录仍在）；② 合法树 4 领域 16 能力点（测试用 3/12），父链完整、逐行 `unverified` + 来源含"未校验"、`generated_by_run_id` 可追到 run；③ 再生成保护：人工上调为 5 后重新生成，目标值与理由保留、`origin=adjusted`，报告 `protected_adjusted` 给出 stored/proposed 对照，未调整节点跟随新值；④ "模型自称已核实"仍写 `unverified`（保留模型原话但不让它伪装已验证）；⑤ 离线演练 11/11 自检通过并产出 `session-fake.json`；⑥ runner 内置真实模型授权开关，未授权直接退出（为 M2-d 留出暂停点） | EV-053 | M2-d 需用户授权后才能跑真实模型 | M2-d（G1 证据） |
| 2026-10-02 | M2-d（尝试 5） | 提示词补丁（禁节点名内「/」）后重跑真实会话 | ① **澄清阶段失败**：模型 6 轮都在追问"目的"，而模拟用户连续 4 次回答"应用方向" （R2 问句含上下文"在这个方向上"，被粗匹配当成了焦点）→ 四要素始终不全 → 触发 6 轮硬上限；② **产品侧行为正确且有价值证据**：第 7 个问题未发出、四要素未被自动补齐、模型主动指出"你的回答和方向重复了"并在末轮列出还缺哪些要素；③ 根因是模拟用户匹配过粗（用户早先已提醒"不能只靠宽泛关键词"），属实现缺陷，非模型问题；④ 未自动重试（按指令停止）；预算内（6 次调用 == HTTP 6 次、零额外重试）；⑤ 累计 24 次 / 约 23.2k tokens（约 0.03 元）；⑥ 诊断存档并提出修复方案（待确认） | `failure-diagnosis-m2d-04.json`；EV-055 | 待确认模拟用户修复后执行尝试 6；M2 未收口 | M2-d（尝试 6） |
| 2026-10-02 | M2-d（尝试 2–4） | 真实会话连续三次推进：`glm-5.3-flash`、两层预算（≤8/≤8、零额外重试）、语义失败即停并留档 | ① **尝试 2**：澄清**成功**（4 轮、四要素齐全、显式确认）——真实模型下 M2-b 与修复后的语义用户均验证通过；能力树失败（4 领域/14 组/**1** 个三层点）→ 根因是提示词没写清"第三层才算能力点"；② **尝试 3**：补提示词后树变成 3 领域/6 组/**13** 个三层点，**形状校验通过**；失败于 runner 硬编码的能力点路径（已改为从生成的树里选真实节点）；③ **尝试 4**：澄清 5 轮通过；树 3 领域/8 组/15 点，但一个节点名内部含「/」（"框架使用（LangChain/LlamaIndex）"）被判为第 4 层 → 整体拒绝；④ 三次均**未自动重试**、未触碰真实库、应用层调用数与 HTTP 请求数逐次相等（零额外重试生效）；⑤ 累计 18 次调用 / 约 17.9k tokens（约 0.02 元）；⑥ 已存档两份诊断并提出提示词补丁（待确认） | `failure-diagnosis-m2d-02.json`、`m2d-03.json`；EV-055 | 待确认提示词补丁后重跑；M2 未收口 | M2-d（尝试 5） |
| 2026-10-02 | M2-d（尝试 1） | 真实模型会话（`glm-5.3-flash`，用户授权后执行）：给 runner 加 `--model` 显式覆盖参数；先自检授权开关（未设 `M2_ALLOW_REAL_MODEL` 时正确拒绝），再发起真实调用 | ① **第 3 次调用后失败**：`confirm()` 拒绝（目标仍在 `clarifying`）——模型三问依次追问「多长时间」「哪一类 Agent 工程师」「多长时间内找到工作」，而脚本用户回答是「应用方向」「找一份 AI 应用工程师的工作」，**回答与问题不对位** → 四要素始终不全，模型（正确地）不给出完整提议；② 离线 fake 之所以通过，是因为手写响应在第三轮直接给了含时间与可衡量结果的完整提议，而那两项信息从未由脚本用户提供 —— **离线脚本掩盖了这个缺口**；③ 已存档诊断（含 3 次调用的问答与根因）；④ 未自动重试（按约定停在报告处）；⑤ 数据边界复核：`data/growth.db` 哈希一致、无 `g_` 表、证据计数 3/109/2/6 未变，本尝试只写临时库；⑥ 成本：3 次调用、记录 tokens ≈2.3k（flash 价目下 <0.01 元） | 诊断 `failure-diagnosis-m2d-01.json` | 修复方案待用户确认；预算拟调整为最坏 8 次 | M2-d（待确认后重跑） |
| 2026-10-01 | M1-e | 新增 `growth_os/evidence/dossier.py`（Growth OS 档案渲染器）+ 生成两份档案与索引；扩展边界检查到整个包 | ① **发现上游缺陷并绕开**：evkg 的 `render_claim_markdown` 只输出 polarity 为 supports/refutes 的证据行，**`partial` 会落空** —— 而被推翻的主张恰恰是 `partial`，漏掉它等于把"复核认为只有部分支持"从档案抹掉 → 自建渲染器显式纳入，并加了回归测试；② 按用户四类要求组织档案：证据链六环节、缺失证据单列且声明"不等于造假"、两个"独立"分别给值、证据局限（不能由项目存在推出个人实现、不能外推为系统整体可靠）；③ 档案里如实写明"抽取所用模型未记录在案"，不用当前配置冒充历史事实；④ **分数精度从 2 位改 3 位**：2 位会把库中 0.697 显示成 0.70，读者无法与库对照，对证据文档是失真（这条是核对脚本先报 FAIL 才发现的）；⑤ 修掉标题用整段 statement 当 H1 的排版缺陷；⑥ 边界检查扩到整个包（只有 adapter.py 可 import evkg），并当场抓到我自己新增的 `evkg.evidence.dossier` 未在允许清单里 | EV-033…EV-036 | 归属层待 M2/M4 决策 | M1-f 待确认 |
| 2026-10-01 | M1-d | 配置独立复核模型（DeepSeek）；核对其**真正生效**；运行 5 个攻击模块；留档攻击样例与复核结果 | ① 用户要求先配独立复核并**核对实际生效的 provider/模型名**，理由是 `independent=True` 只检查变量是否设置 —— 实测确认：主 glm-5.3@bigmodel / 复核 deepseek-flash@deepseek，模型与端点均不同，`genuinely_independent=True`；② **实测发现模型自称不可靠**：问 deepseek-flash"你是谁"它回答 "ChatGPT"，故模型身份只能以解析后的配置与接口返回为准；③ 两个易混淆的"独立"概念须分开记：`independent_verifier`（复核模型不同→True）与 `evidence.independent_source`（证据跨多来源→False，本次两条主张都只引一个来源）；④ `deterministic` 的 `pending_model_review` 是**正常状态**（表示候选已生成待模型复核），非错误；⑤ 本次 0 冲突、2 条冲突候选均来自对抗模块对 broken 主张的记录 | EV-029…EV-032 | 归属层待 M2/M4 决策 | M1-e 待确认 |
| 2026-10-01 | M1-c | 配好 `.env`（用户提供 API Key）+ 探针 + 全量抽取：109/109 passage，2 claims / 60 entities / 3 aliases / 1 event | ① **evkg 自带 `.env.example` 对 glm-5.3 无效**：它同时写 `REASONING_EFFORT=none` 与 `EXTRA_BODY={"thinking":{"type":"disabled"}}`，而该模型实测返回 400「该模型始终思考，不支持关闭思考」→ 改为 `REASONING_EFFORT=low` 后可用；② 另一处：`.env.example` 里 `EVKG_EXTRA_BODY={...}` 裸写，标准 dotenv 解析器会剥掉内部双引号使其不是合法 JSON，必须整体加单引号；③ **抽取器正确地拒绝把项目成果归因为个人能力** —— 一条主张的陈述自己写明"未明确用户本人在项目中的具体角色与贡献，能力主张仅基于项目描述本身"，这是成长领域包「不作能力推断」规则在起作用，但也说明项目产物需要**显式的归属层**才能变成能力证据（属 L2 职责，不该让 LLM 推断）；④ 「严禁升级」规则验证通过：README 的「未来规划」TODO 被抽成 predicate=`计划学习` 且陈述明写"仅为计划事项，不代表已具备相应能力" | EV-025…EV-028 | 归属层待 M2/M4 决策；独立 verifier 未配置 | M1-d 待确认 |
| 2026-10-01 | M1-b.5d | 适配层变薄：删掉 `_tag_source` 的裸 SQL、自造后缀路由与 metadata 补丁；evkg 补 `ingest_path()` 统一路由与 `find_sources()` 按 metadata 检索；新增边界检查测试防止耦合回潮 | ① 用户把目标收窄为「**证明 Growth OS 不再需要知道 evkg 内部存储细节**」，并要求加一项**适配层依赖检查** —— 我做成静态 AST 检查（禁 `sqlite3` / `.db.execute` / `json_set` / `json_extract` / 内联 SQL / 下划线成员 / `evkg.ingest.connectors`），因为"M1-b.5c 期间我自己就复用了 OR-IGNORE 的 helper"，证明靠小心守不住；② `IngestResult.route` 被删除：路由是 evkg 的实现细节，`kind=="code"` 已能表达同一事实；③ 检查最初误报文档字符串（我写的"不做什么"说明里含这些词）→ 改为先剥 docstring 再匹配 | EV-021…EV-024 | symbol 级精度待解析器；evkg 不得推送远程 | 待用户确认进入 M1-c |
| 2026-10-01 | M1-b.5c | 修 evkg 写入语义：`logical_source_id()` 统一两套 id 方案、`Source.content_hash`（基于换行规范化文本）、`save_source` 返回 inserted/updated/unchanged 且 metadata 合并、`_put` 对 sources 改真 upsert、`save_passages` 整体替换、新增 `purge_passages()` 级联清理；pipeline 透传 kind 与 content_hash | ① **我自己踩了用户警告过的坑**：更新分支复用了 `_put`（`INSERT OR IGNORE`），`save_source` 报 updated 但库里仍是旧值 → 已把 `_put` 对 sources 改成真 upsert 从根上消除；② **content_hash 不能用原始字节**：manifest 路径早已按规范化文本取哈希，而快路径用原始字节，两条路径互相矛盾；且原始字节哈希会让一次 git checkout 换行把所有来源判成"已变"→ 统一为「content_hash 相同 ⟺ 段落所依据的文本相同」；③ **新增发现：删 passage 必须级联**，否则同时点亮四条不变量（留下自己审计不过的库）→ 实现 `purge_passages()` 并返回各表清理数量（级联删除是真实数据损失，必须可见）；④ `read_bytes().decode()` 不做换行翻译，CRLF 会让 `\r` 混进 passage 文本并让 locator 校验失败 → 新增 `decode_text()` 显式统一换行 | EV-017…EV-020 | symbol 级精度需解析器；evkg 不得推送远程 | M1-b.5d 待开工确认 |
