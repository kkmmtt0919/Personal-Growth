# 项目验收

> 当前验收与有效证据的紧凑视图。原始输出和完整报告以路径与哈希引用，不在此粘贴。

## 当前验收结论

- 结论：**M0 至 M1-e 全部通过**；M1 的三层基础已闭环；已产出首批可逐字回溯的能力断言（2 条）并经**独立复核**攻击验证；已产出可读的证据档案（含证据链、缺失证据、两类独立、证据局限）。M1-f（damage selftest）未开始
- 验收范围：M0 收口项 + M1-a（领域包生效、依赖解析）+ M1-b（双轨记录、真实材料入库、QG1）+ M1-b.5a（evkg 改造、locator 真值、旧数据不变性）+ M1-b.5b（缺失值语义、下游消费者）+ M1-b.5c（逻辑身份、content_hash、三态写入、级联替换、真实材料 A→B 性质）+ M1-b.5d（适配层边界、公共 API 补齐）+ M1-c（模型连通性、全量抽取、「严禁升级」与证据链回溯）+ M1-d（独立复核核对、攻击运行、样例留档、越权主张被推翻）+ M1-e（档案渲染、35 项一致性核对、partial 回归、真实库对照）
- 最后检查：2026-10-01
- 遗留问题：symbol 级代码精度需解析器（已明确排除）；G1–G6 与 QG2–QG5 未开始；**evkg 本地领先远程 4 个提交且不得推送**；归属层缺失使项目产物暂不能作为能力证据（M1-d 已能识别并推翻这类越权主张，M1-e 的档案也明示了该局限，但“如何正当地建立归属”仍待 M2/M4 决策）

## 验收标准

产品验收门（完整定义与判定方法见 `docs/ACCEPTANCE_GATES.md`）：

| 标准 ID | 标准 | 状态 | 验证方法摘要 | 证据 ID |
|---|---|---|---|---|
| G1 | Goal Clarification：模糊目标 → 明确目标 | 待检查 | 冷启动 ≤6 轮产出含四要素的 confirmed goal；含反例检查 | 无 |
| G2 | Evidence Traceability：能力判断可追溯 | 待检查 | 抽 5 条 assessment 逐跳追溯至原文；`audit_store`=pass | 无 |
| G3 | Capability Audit：识别"自称会但证据不足" | 待检查 | **A/B 对照实验**：弱证据组须得"理解高·实践低"，强证据组须显著更高 | 无 |
| G4 | Task Quality：任务针对缺口且可验收 | 待检查 | 每个 task 可反向映射到 gap；"去学习 X"类任务必须被拒 | 无 |
| G5 | Growth Loop：完成 → 新证据 → 能力变化自动发生 | 待检查 | 无人工干预的端到端运行；星级变化可归因到具体新证据 | 无 |
| G6 | User Return Value：回来能看到变化与下一步 | 待检查 | snapshot diff + 变化摘要 + 下一步建议 + 引用长期偏好 | 无 |

质量门：

| 标准 ID | 标准 | 状态 | 验证方法摘要 | 证据 ID |
|---|---|---|---|---|
| QG1 | 证据不变量 | 待检查 | `evkg audit_store` = pass，9 项检查 0 violation | 无 |
| QG2 | 攻击自测 | 待检查 | `evkg run_damage_selftest` = caught | 无 |
| QG3 | 评级规则覆盖 | 待检查 | `tests/test_assessment_rules.py` 覆盖含 G3 A/B 场景的决定性用例 | 无 |
| QG4 | 无密钥入库 | 待检查 | 仓库与账本无明文密钥；`.env` 已 gitignore；日志脱敏 | 无 |
| QG5 | 全量测试 | 待检查 | `uv run pytest` 全绿（含 evkg 自身 31 项） | 无 |

治理门（M0）：

| 标准 ID | 标准 | 状态 | 验证方法摘要 | 证据 ID |
|---|---|---|---|---|
| A-001 | 治理账本结构合法 | **通过** | `--validate` 与 `--audit` 均 `valid=true, strict_valid=true, errors=[], warnings=[]` | EV-001 |
| A-002 | 规划文档齐备且索引一致 | **通过** | `docs/` 下 5 份内容文档全部登记于 `docs/README.md`，无未登记文件（差异仅为索引自身 README.md） | EV-002 |
| A-003 | 用户确认 Q1–Q4 选型 | **通过** | 4 项均选定并记录于 `docs/DECISIONS.md`，采纳推荐方案 | EV-003 |

## 证据索引

| 证据 ID | 时间 | 方法摘要 | 退出状态 | 版本或文件哈希 | 结果摘要 | 证据位置 | 有效期 |
|---|---|---|---|---|---|---|---|
| EV-001 | 2026-10-01 | `uv run python init_project_management.py --project-root "D:/projects/Personal Growth" --validate`（另跑 `--audit`） | exit 0 | `.project-to-act/` 首次提交 | `valid=true, strict_valid=true, schema_version=2, mode=managed, errors=[], warnings=[]`；5 份文档字节数均在阈值内 | 命令输出（见 `PROJECT_PROGRESS.md` 进度历史） | 90d |
| EV-002 | 2026-10-01 | 对比 `grep -oE '\[`*.md`\]' docs/README.md` 与 `ls docs/*.md` | exit 0 | 同上 | 5 份内容文档（PRD/ARCHITECTURE/ROADMAP/ACCEPTANCE_GATES/DECISIONS）全部登记，无未登记文件；差异仅为索引自身 | `docs/README.md` | 90d |
| EV-003 | 2026-10-01 | 用户在 AskUserQuestion 中确认 Q1–Q4 | — | 同上 | Q1 独立仓库+path 依赖；Q2 GLM 主模型+独立 verifier；Q3 React+Vite+TS；Q4 单用户本地优先 | `docs/DECISIONS.md` §已确认决策 | 长期（决策类） |
| EV-004 | 2026-10-01 | `PYTHONIOENCODING=utf-8 uv run python -X utf8 scripts/verify_profile.py` | exit 0 | profile `5637583bfbef`；script `1cdca5bd9a57`；evkg `a448f44` | **13/13 通过**。关键项：`folk` 覆盖为「用户自述」且 baseline=0.35；`primary` 覆盖为「实践产物」；`modern_study` 标注「不参与用户能力评级」；6 kind 全覆盖；自定义 kind 确认被静默忽略；红队 prompt 命中 PRD §8 全部 5 个抽查角度；段落切分 4/4；`Source.metadata` 可携带 `growth_evidence_type`/`growth_channel` | 命令输出；profile 与脚本见 `backend/growth_os/evidence/profiles/`、`scripts/` | 90d |
| EV-005 | 2026-10-01 | `uv sync --python 3.12` | exit 0 | uv.lock | 24 个包安装成功；`evkg==0.1.0 (from file:///D:/projects/evkg)` 与 `growth-os==0.0.0` 均以 editable/path 方式解析，Q1 的依赖方式验证可行 | 命令输出；`pyproject.toml` + `uv.lock` | 90d |
| EV-006 | 2026-10-01 | `uv run pytest tests/ -v` | exit 0 | adapter `f73bff7e5010`；tests `bb3dfa894969` | **22 passed**。覆盖：两条 ingest 路由选择、二进制后缀拒绝、未知类型/通道拒绝、**成长标签与 `metadata.assessment` 共存**、6 种证据类型→baseline 映射（0.82/0.82/0.78/0.68/0.62/0.35）、评估理由来自成长领域包、通道过滤、按类型过滤、幂等（重复入库不新增行）、重打标签生效且不新增行 | 命令输出；`tests/test_evidence_adapter.py` | 90d |
| EV-007 | 2026-10-01 | `uv run python -X utf8 scripts/smoke_ingest.py`（真实材料） | exit 0 | smoke `baf17e2c8a6b` | **PASS**。用用户真实仓库 `mytset-rag` 入库：README.md(57 passages, 快路径)、`RagService.java`(11 passages, 文本兜底路由)、`evkg/README.md`(43 passages, 领域参考)。计 3 sources / 111 passages。**三条记录的 `growth_evidence_type`+`growth_channel`+`assessment` 三者共存**，baseline 分别 0.82/0.82/0.62；通道过滤 user_evidence=2、domain_reference=1；幂等复跑 sources 3→3 且 source_id 不变 | 命令输出；`data/growth.db` | 90d |
| EV-008 | 2026-10-01 | `adapter.audit('data/growth.db')` → `evkg.attack.audit_store` | pass | 同上 | **status=pass, total_violations=0**，10 项不变量检查全部 0 violation。证明适配层的 `json_set` 定向修补**未破坏** evkg 的任何证据完整性约束（引文∈原文、claim 必有证据、passage 必有 source 等）。此即质量门 QG1 在 M1-b 范围的首次通过 | 命令输出；`data/growth.db` | 90d |
| EV-009 | 2026-10-01 | `uv run pytest ../evkg/tests`（evkg 上游，commit `a4b15af`） | exit 0 | evkg `a4b15af` | **61 passed**（原有 31 + 新增 30）。新增覆盖：`SourceKind.CODE` 与策略表、**既有 6 个 kind 基线未被改动**（旧数据不可被顺手改）、语言判定（后缀/URI/无扩展名文件/拒绝散文与数据）、`CodeReader` 不被 `PlainTextReader` 遮蔽、保留缩进、**locator 不许说谎**、方法内空行+嵌套块不切碎、行范围有序不重叠、max_lines 上限、类第二成员可分离、退格到主体层切/退格到方法体内部不切、仅括号噪声为零、`ingest_code_file` 幂等与拒绝非源码 | 命令输出；`../evkg/tests/test_code_ingest.py` | 90d |
| EV-010 | 2026-10-01 | `uv run pytest tests/`（本仓） | exit 0 | adapter `1138da7bed90`；tests `586993f0cc2b` | **27 passed**。新增覆盖：源码走 `evkg.ingest_code_file` 且 kind=`code`、**kind 由 primary 改判为 code 时基线保持 0.82（评分中性）**、passage 带 path/language/line_start/line_end、locator 回原文逐字一致、缩进保留、无扩展名构建文件（Dockerfile）不漏 | 命令输出；`tests/test_evidence_adapter.py` | 90d |
| EV-011 | 2026-10-01 | 旧数据不变性检查：升级 evkg 后**不做任何重新入库**，逐字段对比 `artifacts/m1b5/before_sources.json` | 一致 | adapter `1138da7bed90` | **逐字段完全一致，表计数无差异**（3 sources / 111 passages / 其余表同）。证明本次 evkg 升级本身不触碰已落库数据 | `artifacts/m1b5/before_sources.json`、`after_upgrade_no_reingest.json` | 90d |
| EV-012 | 2026-10-01 | locator 真值校验：对每条带行范围的 passage，按 locator 回磁盘切原文并逐字比对；随后 `adapter.audit` | exit 0 | 重建后 `data/growth.db` | 重建后 3 sources / 109 passages，形态全部一致（code 源 9 段全带行范围；两个文档源 0 段带行范围）。**代码源 9 条 locator 回磁盘核对，不一致 0 条**。`audit_store` = pass，0/10 violations。切分质量：RagService.java 9 段 / 最大 25 行 / 仅括号噪声 0 条 | 命令输出；`data/growth.db`。重建前的库备份为本机取证材料 `artifacts/m1b5/*.db.bak`（二进制，已 gitignore 不入库） | 90d |
| EV-013 | 2026-10-01 | `uv run pytest ../evkg/tests`（evkg 上游，commit `e432c42`） | exit 0 | evkg `e432c42` | **81 passed**（b.5a 后 61 + 新增 20）。新增 `tests/test_assessment_lifecycle.py` 为**成对对照**：缺失不产出 0.25；缺失也不产出高分（抽取质量 0.99 仍 `score=None`）；`SourceKind.UNKNOWN` 的 0.25 先验保持不变且与 `unassessed` 可区分；**已评估情形 7 个 kind 数值逐位不变**；旧 `Confidence` 行（无 `assessment_status`）仍可读回。lint 26→25，未新增 | 命令输出；`../evkg/tests/test_assessment_lifecycle.py` | 90d |
| EV-014 | 2026-10-01 | 前后对照实证：`artifacts/m1b5/check_b5b_after.py`（同一脚本在改动前亦运行过，见进度历史） | exit 0 | script `72c3f13627a8` | 改动前：无缓存 assessment 的 **kind=code** 来源被按 **0.25** 计权（策略表应为 0.80，**差 0.55**）；改动后：加权值 = 0.80，**差 0.00**，`origin=derived_from_kind`。来源记录丢失时抽取质量 0.99 仍 `score=None`（未被"未评估"抬成高分）。`SourceKind.UNKNOWN` 仍为 0.25 且 `status=assessed`。7 个 kind 的已评估数值全部逐位不变 | 命令输出；`artifacts/m1b5/check_b5b_after.py` | 90d |
| EV-015 | 2026-10-01 | 下游消费者检查：`artifacts/m1b5/check_b5b_consumers.py`（构造 `score=None` 的 claim 走真实存储与渲染） | exit 0 | script `73fd88c7c8ad` | **7/7 通过**：claim 读回 `score=None`/`status=unassessed`；`relations.confidence` 列接受 NULL；dossier 渲染不崩；`adversarial.claim_score` 对 None 不抛错；`storage_status` 通过；索引检索（含 `ORDER BY json_extract(confidence.score)`）不崩；`audit_store` 仍 pass(0/10)。覆盖了改动前识别出的 6 个消费者 | 命令输出；`artifacts/m1b5/check_b5b_consumers.py` | 90d |
| EV-016 | 2026-10-01 | 真实库旧数据不变性：逐字段对比 `artifacts/m1b5/before_sources.json` + `adapter.audit` | 一致 | adapter `1138da7bed90` | 3 个来源的 `assessment_baseline` 全部与基线快照一致，且解析后 `origin=cached`（未被重新推导）。唯一差异 `src_bb2159281c69a158.kind: primary→code` 是 **b.5a 已记录的刻意变更**（基线不变，评分中性），非本次引入。claims=0，故无 claim 级置信度被改写。`audit_store` = pass | 命令输出；`artifacts/m1b5/before_sources.json` | 90d |
| EV-017 | 2026-10-01 | `uv run pytest ../evkg/tests`（evkg 上游，commit `068389d`） | exit 0 | evkg `068389d` | **93 passed**（b.5b 后 81 + 新增 12）。新增 `tests/test_source_identity.py` 覆盖用户指定的核心性质：同一 source_id 下内容 A→B 重新 ingest 后仍只有一个逻辑 source、旧 passage 不残留、**新 passage 集合与用当前内容重新切分的结果完全一致**、content_hash 变化、下游引用不变；另含三态循环（inserted→unchanged→updated）、unchanged 不刷新 access_date、metadata 合并、级联后审计仍 pass、幸存 claim 的 passage_ids 剪除、级联数量可观测。lint 25（HEAD 26），未新增 | 命令输出；`../evkg/tests/test_source_identity.py` | 90d |
| EV-018 | 2026-10-01 | 端到端实证 `artifacts/m1b5/check_b5c.py`（真实材料，两部分） | exit 0 | script `f474ae3d1d62` | **全部通过**。A 部分（真实库 3 份证据）：source 身份稳定（3 个全部保留 id）、unchanged 时 passage 数不增长（9/57/43）、`content_hash` 全部写入、QG1 pass；其中「首次写入 → updated」的迁移在字段引入后的首次运行中观测（那次 output 显示 3 个来源由 `content_hash=None` 变为有值），本机此后已处稳态，脚本会如实说明而不再报假 OK。B 部分（真实 `RagService.java` 副本，**替换**一句方法体使旧段落真正失效）：8/8 通过 —— 一个逻辑 source、source_id 不变、content_hash 变化、新 passage 集合与重新切分一致、确有旧 passage 被清理（1 条）、被清理的 id 已不在库、新内容已落库、库自洽 | 命令输出；`artifacts/m1b5/check_b5c.py` | 90d |
| EV-019 | 2026-10-01 | 下游消费者复检 + 冒烟：`check_b5b_consumers.py`、`scripts/smoke_ingest.py` | exit 0 | consumer script `73acf21c2e61` | 消费者检查 **7/7 通过**（`score=None` 下 claim 读回、`relations.confidence` 写 NULL、dossier 渲染、`claim_score` 守卫、`storage_status`、索引检索、`audit_store` pass）；`smoke_ingest.py` = **PASS**（3 sources / 109 passages / 通道过滤 / 幂等）。证明 b.5c 改写入语义后既有适配层流程未破 | 命令输出 | 90d |
| EV-020 | 2026-10-01 | 真实库最终状态复核：逐字段对比基线快照 + `adapter.audit` | 一致 | adapter `92e850102897` | 3 个来源的 **source id 全部未变**（逻辑身份方案的关键保证），`kind`、`assessment_baseline` 与基线快照一致（唯一差异仍是 b.5a 已记录的 `kind: primary→code`）。新增 `content_hash` 字段已写入。`audit_store` = pass，0/10 violations | 命令输出；`data/growth.db` | 90d |
| EV-021 | 2026-10-01 | `uv run pytest ../evkg/tests`（evkg 上游，commit `28afbc0`） | exit 0 | evkg `28afbc0` | **101 passed**（b.5c 后 93 + 新增 8）。新增 `tests/test_ingest_boundary.py`：源码经 `ingest_path` 自动落为 `CODE` 且带行范围、普通文本的 kind 由调用方决定、不支持格式报错指向状态机、**调用方领域标签与 evkg 的 assessment 共存**、重新 ingest 时标签不丢且判 `unchanged`、`find_sources` 单键/多键/空结果。lint 25，未新增 | 命令输出；`../evkg/tests/test_ingest_boundary.py` | 90d |
| EV-022 | 2026-10-01 | `uv run pytest tests/`（本仓，含新增边界检查） | exit 0 | adapter `bbfd5412fea6`；boundary `10de9f47ff22` | **38 passed**。新增 `tests/test_adapter_boundary.py` **11 项静态 AST 检查**：可执行代码中不得出现 `sqlite3` / `.db.execute` / `.db.commit` / `json_set` / `json_extract` / 内联 SQL 关键字 / 下划线成员；只允许导入 evkg 的公共模块；不得依赖 sqlite3/sqlalchemy/peewee；不得调用 store 低层方法；不得再有私有辅助函数（`_tag_source` 已删除）。检查先剥 docstring 再匹配，避免把"不做什么"的说明文字误判 | 命令输出；`tests/test_adapter_boundary.py` | 90d |
| EV-023 | 2026-10-01 | 回归复跑 b.5b / b.5c 的全部实证脚本 | exit 0 | 同 EV-014 / EV-018 | b.5c 端到端：**全部通过**（真实库三态循环 + RagService.java 替换式改写 8/8）；b.5b 消费者检查：**全部通过**（7/7）。证明 b.5d 删除裸 SQL 与 metadata 补丁后，既有写入语义与下游路径均未破 | 命令输出 | 90d |
| EV-024 | 2026-10-01 | 真实库复核：source id 稳定性 + 通道过滤改走 `find_sources` + `adapter.audit` | pass | adapter `bbfd5412fea6` | 旧 id 全部仍在；相对基线的字段差异**仅** `src_bb2159281c69a158.kind`（b.5a 已记录的刻意变更，基线未动）。通道过滤经**公共 API** 得到 user_evidence=2 / domain_reference=1，repo_artifact=2、external_ref=1，与改动前一致。`audit_store` = pass，0/10 violations | 命令输出；`data/growth.db` | 90d |
| EV-025 | 2026-10-01 | 模型连通性探针 `artifacts/m1b5/probe_model.py`（1 次极小结构化请求） | exit 0 | probe `9a3335fec358` | **PASS**。provider=openai_compatible, model=glm-5.3, tokens in/out=193/30, 中文与 schema 约束均正常。过程中修掉两处配置问题：`EVKG_REASONING_EFFORT=none` 与 `EXTRA_BODY={"thinking":{"type":"disabled"}}` 被模型以 `400 code 1210 该模型始终思考` 拒绝 → 改用 `low`；`EVKG_EXTRA_BODY` 裸写在 dotenv 下会被剥掉内部引号而 JSON 解析失败 → 整体加单引号 | 命令输出；`artifacts/m1b5/probe_model.py` | 90d |
| EV-026 | 2026-10-01 | 小样本试跑（12 条 passage，库副本） | exit 0 | 副本库（已清理） | 12 条 = 全部 9 条代码 passage + README 前 3 条；产出 **0 条主张**（9 entities / 2 aliases）。**这是正确行为**：`package com.hw.service;`、`import …` 不含能力断言，README 描述的是项目而非个人 —— 即成长领域包「不作能力推断」规则生效。先试跑再全量的做法在此避免了直接对真实库跑 109 条的盲跑 | 命令输出 | 90d |
| EV-027 | 2026-10-01 | 全量抽取 `uv run --env-file .env python artifacts/m1b5/run_extract.py data/growth.db` | exit 0 | script `9f9319a3984c` | **109/109 passage 完成**（6 批，0 失败批）。产出 **2 claims / 60 entities / 3 aliases / 1 event / 3 evidence / 2 relations**；抽取账本覆盖 109/109。`audit_store` = pass，0/10 violations | 命令输出；`data/growth.db` | 90d |
| EV-028 | 2026-10-01 | 两条主张的证据链逐字回溯 + 引文完整性 + 「严禁升级」实例验证 | pass | 同上 | ① **「严禁升级」通过**：README「未来规划」的未勾选 TODO 被抽为 `用户 \| 计划学习 \| Dubbo、gRPC…`，陈述明写"仅为计划事项，不代表已具备相应能力"，predicate **未**被升级为"具备能力"；② 另一条 `用户 \| 实现过 \| RAG 检索服务` 的陈述自带限定"**但未明确用户本人在项目中的具体角色与贡献，能力主张仅基于项目描述本身**"（抽取质量自评 0.35，受来源基线 0.82 上限约束）；③ 3 条 evidence 的引文**逐字**存在于对应 passage；④ 每条主张都能沿 claim → evidence → passage → source 走通，代码来源的 passage 带 `line_start/line_end` 与 `language` | 命令输出；`data/growth.db` | 90d |
| EV-029 | 2026-10-01 | 独立复核核对 `artifacts/m1b5/probe_verifier.py`：对主网关与复核网关各发一次真实请求，比对**实际生效**的 provider/模型名/base_url | exit 0 | probe `cf0a5b313bea`；`artifacts/m1d/independence.json` | **真正独立**。主=glm-5.3 @ open.bigmodel.cn；复核=deepseek-flash @ api.deepseek.com；模型名与端点均不同，`independent_flag_from_evkg=True`，`genuinely_independent=True`。四项断言全过：independent 标志、模型名差异、base_url 差异、复核网关确有真实响应（非回落）。**顺带实测**：问 deepseek-flash“你是谁”它回答 “ChatGPT” → 模型自称不可用于验证身份 | 命令输出；`artifacts/m1d/independence.json` | 90d |
| EV-030 | 2026-10-01 | `uv run --env-file .env python artifacts/m1d/run_attack.py data/growth.db`（5 模块，不含 damage） | exit 0 | runner `e2141c6af6d2`；`attack_result.json` | summary：deterministic=`pending_model_review`（正常状态：候选已生成待复核）、verifier=`complete`、contradiction=`complete`、adversarial=`complete`、audit=`pass`。**无模块级错误**（`failures_and_details.json` 的 module_errors 为空）。产出 4 条对抗报告、2 条冲突候选（均来自对抗模块对 broken 主张的记录）、0 条已确认冲突。QG1 = pass，0/10 violations | 命令输出；`artifacts/m1d/` | 90d |
| EV-031 | 2026-10-01 | 攻击样例留档：红队质疑 + 裁决全文 | — | `attack_reports.json` `2860ad893982` | 4 条 probe/verdict 全部留档。`clm_f138…`（`实现过`）两次 `broken`，质疑角度为「仅基于 README 自述、用户角色不明」与「代码独立性与二手资料风险（是否只是调现成 API 的教程式组合、92% 指标有无代码与实验佐证）」——**直接落实 PRD §8 的质疑清单**；`clm_29f5…`（`计划学习`）两次 `sustained` | `artifacts/m1d/attack_reports.json` | 长期 |
| EV-032 | 2026-10-01 | ★ 攻击判别结果：越权主张被推翻、措辞正确的主张被保住 | pass | `claims_after_attack.json` | **`实现过 RAG 检索服务`**：抽取自评 0.35 → 复核 polarity=`partial`、0.17 → 对抗裁决 `broken` → 最终 `disputed`/0.17；理由写明“README 属于项目自述，**不能证明用户本人承担开发角色**”（`review_state=disputed_by_adversarial`，`verifier_model=deepseek-flash`，`verifier_independent=True`）。**`计划学习`**：`machine_reviewed`/0.697，裁决 `sustained`，理由“缺失实践证据不削弱该主张，因为其核心是『仅为计划』”。→ 同一次攻击同时做到“推翻越权”与“保住正确”，即 PRD §33 第 3 条的首次实证 | `artifacts/m1d/claims_after_attack.json` | 长期 |
| EV-033 | 2026-10-01 | `uv run pytest tests/test_dossier.py`（M1-e 新增 22 项） | exit 0 | `tests/test_dossier.py` `843910021c54` | **22 passed**。覆盖用户五条标准：六环节证据链齐全；模型判断被标注为判断（"模型产出，非事实"/"不是已被证实的事实"/"可复核的判断，而非定论"）；final status 推导过程；状态与分数与库一致（3 位小数）；`verifier_independent` 取自 metadata（用 SQL 改成 0 后档案随之变 0，证明非渲染时臆测）；缺失证据单列且含"不等于造假""不构成用户没做过的判断"；两个"独立"分别给值且声明不可互换；生成信息五字段；**抽取模型缺失被如实标注**；标题用三元组而非整段 statement；无攻击/无复核时的降级文案；未知主张报错；`write` 落盘一致 | 命令输出；`tests/test_dossier.py` | 90d |
| EV-034 | 2026-10-01 | `uv run --env-file .env python artifacts/m1e/run_dossier.py`（生成 + 核对） | exit 0 | runner `c23a3bc9815a`；`verification.json` | **核对 35/35 通过**。产出 2 份档案 + 1 份索引，并逐项核对：claim 状态/分数/`verifier_independent` 与库一致；每条 attack 的 verdict 与 `missing_evidence` 与 `artifacts/m1d/attack_reports.json` 一致；**`partial` 复核证据未被漏掉**；并含空跑防护（先断言 M1-d 留档非空）。`audit_store` = pass，0/10 violations | `artifacts/m1e/` | 90d |
| EV-035 | 2026-10-01 | ★ 回归：`partial` 极性证据必须被呈现 | pass | `dossier.py` `dabe53d1b567` | 两条用例锁死 —— `test_partial_polarity_evidence_is_rendered`（`polarity=\`partial\`` 与复核意见正文都在档案里）与 `test_partial_is_not_listed_as_support`（不得被误标成反对证据）。**这是本模块存在的直接原因**：evkg 的 `render_claim_markdown` 只输出 supports/refutes，会漏掉 `partial`，而被推翻的真实主张恰恰是 `partial` | 命令输出；`tests/test_dossier.py` | 长期 |
| EV-036 | 2026-10-01 | 真实产物 ↔ 真实库一致性（`skipif`，本机执行） | pass | `artifacts/m1e/dossier-*.md` | `test_committed_dossiers_match_real_database` 对真实库中每条主张逐项核对已提交的档案：主张 ID、最终状态、3 位小数置信度、`independent_verifier` 取值，以及**真实 `partial` 复核意见的正文必须出现**。真实库已 gitignore，缺失时该用例自动跳过；本机已实际执行并通过。另：`adapter.audit` = pass | `artifacts/m1e/`；`data/growth.db` | 90d |

## Gate 记录

| Gate ID | 日期 | Gate | 对象 | 结果 | 证据 ID | 豁免与确认人 |
|---|---|---|---|---|---|---|
| A-001 | 2026-10-01 | 治理账本合法性 | `.project-to-act/` | 通过 | EV-001 | — |
| A-002 | 2026-10-01 | 文档索引一致性 | `docs/` | 通过 | EV-002 | — |
| A-003 | 2026-10-01 | 选型确认 | Q1–Q4 | 通过 | EV-003 | 用户 |
| M1-a | 2026-10-01 | 成长领域包实际生效（非仅可加载） | `growth_os.yaml` | 通过 | EV-004 | — |
| M1-a | 2026-10-01 | evkg path 依赖可解析 | `pyproject.toml` | 通过 | EV-005 | — |
| M1-b | 2026-10-01 | 双轨记录成立（成长标签与 evkg assessment 共存） | `adapter.py` | 通过 | EV-006 | — |
| M1-b | 2026-10-01 | 真实材料入库可用（含代码路由） | `mytset-rag` 3 文件 | 通过 | EV-007 | — |
| QG1 | 2026-10-01 | 证据不变量（M1-b 范围首跑） | `data/growth.db` | 通过 | EV-008 | — |
| M1-b.5a | 2026-10-01 | evkg 源码一等支持（61 项测试全绿、lint 无新增） | `../evkg` @ `a4b15af` | 通过 | EV-009 | — |
| M1-b.5a | 2026-10-01 | 适配层改走 evkg 原生代码路径且评分中性 | `adapter.py` | 通过 | EV-010 | — |
| M1-b.5a | 2026-10-01 | 旧数据未被错误升级（升级 evkg 后零变更） | `data/growth.db` | 通过 | EV-011 | — |
| M1-b.5a | 2026-10-01 | locator 可回磁盘核对（零说谎）+ 切分质量 | `RagService.java` | 通过 | EV-012 | — |
| M1-b.5b | 2026-10-01 | 缺失值语义（`UNASSESSED` 双向设防，已评估数值逐位不变） | `../evkg` @ `e432c42` | 通过 | EV-013 EV-014 | — |
| M1-b.5b | 2026-10-01 | 下游消费者在 `score=None` 下不崩 | 6 个消费者 | 通过 | EV-015 | — |
| M1-b.5b | 2026-10-01 | 旧数据未被错误升级 | `data/growth.db` | 通过 | EV-016 | — |
| M1-b.5c | 2026-10-01 | 逻辑身份 + content_hash + 显式 upsert（93 项全绿） | `../evkg` @ `068389d` | 通过 | EV-017 | — |
| M1-b.5c | 2026-10-01 | A→B 核心性质（真实材料端到端） | `RagService.java` 副本 | 通过 | EV-018 | — |
| M1-b.5c | 2026-10-01 | 下游消费者与冒烟未破 | adapter + 6 消费者 | 通过 | EV-019 | — |
| M1-b.5c | 2026-10-01 | source 身份稳定 + 库自洽 | `data/growth.db` | 通过 | EV-020 | — |
| M1-b.5d | 2026-10-01 | evkg 公共入口补齐（101 项全绿） | `../evkg` @ `28afbc0` | 通过 | EV-021 | — |
| M1-b.5d | 2026-10-01 | **适配层边界**：无裸 SQL / 无自造路由 / 无私有辅助 | `adapter.py` | 通过 | EV-022 | — |
| M1-b.5d | 2026-10-01 | 删补丁后既有写入语义与下游未破 | 回归脚本 | 通过 | EV-023 | — |
| M1-b.5d | 2026-10-01 | source 身份稳定 + 检索走公共 API | `data/growth.db` | 通过 | EV-024 | — |
| M1-c | 2026-10-01 | 模型可用（探针通过，含两处配置修正） | `glm-5.3` @ open.bigmodel.cn | 通过 | EV-025 | — |
| M1-c | 2026-10-01 | 抽取不越权（项目描述不产生个人能力断言） | 12 条试跑 | 通过 | EV-026 | — |
| M1-c | 2026-10-01 | 全量抽取完成且库自洽 | `data/growth.db` | 通过 | EV-027 | — |
| M1-c | 2026-10-01 | **「严禁升级」**（计划 ≠ 具备）+ 证据链逐字可回溯 | 2 条主张 | 通过 | EV-028 | — |
| M1-d | 2026-10-01 | 独立复核**真正生效**（非仅设变量） | GLM vs DeepSeek | 通过 | EV-029 | — |
| M1-d | 2026-10-01 | 攻击运行完整、无模块级错误、库自洽 | 5 个模块 | 通过 | EV-030 | — |
| M1-d | 2026-10-01 | 攻击样例留档 | `artifacts/m1d/` | 通过 | EV-031 | — |
| M1-d | 2026-10-01 | **越权主张被推翻 + 正确主张被保住** | 2 条主张 | 通过 | EV-032 | — |
| M1-e | 2026-10-01 | 档案渲染行为（22 项，含 partial 回归） | `tests/test_dossier.py` | 通过 | EV-033 | — |
| M1-e | 2026-10-01 | 档案 ↔ 数据库 ↔ M1-d 留档一致性（35/35） | `artifacts/m1e/` | 通过 | EV-034 | — |
| M1-e | 2026-10-01 | **partial 复核证据不被漏掉** | `dossier.py` | 通过 | EV-035 | — |
| M1-e | 2026-10-01 | 已提交档案与真实库一致 | `data/growth.db` | 通过 | EV-036 | — |

## 验收记录

| 日期 | 检查范围 | 证据 ID | 结果 | 遗留问题 | 结论 |
|---|---|---|---|---|---|
| 2026-10-01 | M0 收口（账本/索引/选型） | EV-001 EV-002 EV-003 | 通过 | G1–G6、QG1–QG5 全部未开始 | **M0 验收通过**，M1 可开工 |
| 2026-10-01 | M1-a（领域包生效、依赖解析） | EV-004 EV-005 | 通过 | R1/R2/R4 待后续小步 | **M1-a 验收通过** |
| 2026-10-01 | M1-b（入库、双轨记录、QG1） | EV-006 EV-007 EV-008 | 通过 | M1-c 起需 LLM API Key | **M1-b 验收通过** |
| 2026-10-01 | M1-b.5a（evkg 源码一等支持、适配层变薄、旧数据不变性） | EV-009 EV-010 EV-011 EV-012 | 通过 | symbol 级精度待解析器；跨切分器累积问题待 b.5c | **M1-b.5a 验收通过** |
| 2026-10-01 | M1-b.5b（缺失值语义、下游消费者、旧数据不变性） | EV-013 EV-014 EV-015 EV-016 | 通过 | — | **M1-b.5b 验收通过** |
| 2026-10-01 | M1-b.5c（逻辑身份、content_hash、显式 upsert、级联替换） | EV-017 EV-018 EV-019 EV-020 | 通过 | symbol 级精度待解析器；evkg 不得推送远程 | **M1-b.5c 验收通过** |
| 2026-10-01 | M1-b.5d（适配层边界、公共 API 补齐） | EV-021 EV-022 EV-023 EV-024 | 通过 | — | **M1-b.5d 验收通过；M1 的 a/b/c 三层闭环** |
| 2026-10-01 | M1-c（extract：证据 → 能力断言） | EV-025 EV-026 EV-027 EV-028 | 通过 | 归属层待 M2/M4 决策；独立 verifier 未配置 | **M1-c 验收通过** |
| 2026-10-01 | M1-d（attack：独立复核 + 对抗攻击） | EV-029 EV-030 EV-031 EV-032 | 通过 | 归属层待 M2/M4 决策 | **M1-d 验收通过（独立复核，结果可用）** |
| 2026-10-01 | M1-e（dossier：能力证据档案） | EV-033 EV-034 EV-035 EV-036 | 通过 | 归属层待 M2/M4 决策；抽取模型未入库 | **M1-e 验收通过** |

验收方式说明、证据格式与证据链自举机制见 `docs/ACCEPTANCE_GATES.md`（§1 原则、§2 自举机制、§5 记录格式）。约束：验收证据库 `data/acceptance.db` 与用户证据库物理隔离，项目验收证据不得进入用户能力断言通道，否则会污染 G3 的判定。
