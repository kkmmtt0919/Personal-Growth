# 项目验收

> 当前验收与有效证据的紧凑视图。原始输出和完整报告以路径与哈希引用，不在此粘贴。

## 当前验收结论

- 结论：**M0 至 M1-g 全部通过；M1 技术 spike 已结束并正式归档**。evkg 依赖策略判定为**有条件依赖（C1–C5）**；交付形式已按用户确认落定为**本地 Git bundle 归档（方案 A，维持不推送）**，归档与双副本验证完成（EV-049）。完整判定见 `docs/M1-SPIKE-CONCLUSION.md`
- 验收范围：M0 收口项 + M1-a…M1-f（见下方历史行）+ **M1-g（R1–R4 收口、D1 双实例实测、上游缺陷复现、覆盖盲区界定、M1 完成条件补跑 init/reindex、依赖策略判定）+ B-g1（bundle 归档与恢复验证）**
- 最后检查：2026-10-02
- 遗留问题：**B-g2** 富格式（PDF/docx/xlsx）上传路径 0 端到端验证，M3 开工前须先 spike；**归档第三副本**（抗物理损坏）待用户另存移动硬盘/云盘；**发布/CI 前**将 evkg 依赖切换为 `git + rev` 并复跑测试；**M4 前**必须解决抽取模型持久化；**多领域包或并发 profile 前**必须改上游 profile 作用域；归属层缺失使项目产物暂不能作为能力证据（待 M2/M4 决策）；G1–G6 与 QG2–QG5 未开始

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
| EV-037 | 2026-10-01 | `uv run --env-file .env python artifacts/m1f/run_damage.py`（副本库上三场景） | exit 0 | `run_damage.py` `a99704c8b50d`；`damage_result.json` `c08102b731aa` | **三场景全部 caught**：① evkg 内置自测 `status=caught`（`quote_violations_after_injection=1`）；② 受控伪造引文 0→1 违规、审计 `fail`、样本点名注入行；③ 受控 dangling passage（用户指定场景）0→1、`fail`、点名。三场景清理后均 `audit=pass`、总违规 0、数据表零差异（`audit_log` 增量来自本流程自身审计，已注明）。**真实库逐表计数零差异** | 命令输出；`artifacts/m1f/` | 90d |
| EV-038 | 2026-10-01 | `uv run pytest tests/test_damage_selftest.py`（新增 10 项） | exit 0 | `tests/test_damage_selftest.py` `7c4ed1888835` | **10 passed**。每场景断言三件事：注入确实落库（防「没抓到」实为假阴性）、目标不变量违规条数上升且审计转 `fail`、清理后回到 `pass`/0 且数据表计数复原。另含：干净图自身必须 pass、注入前目标不变量必须为 0、**子串引文不得被误判为伪造**（防检查过宽）、内置自测无残留、空库应如实 `skipped`、以及两项**内容级**断言（逐行 payload 哈希） | 命令输出 | 90d |
| EV-039 | 2026-10-01 | 交叉印证：内置自测的自报 vs 受控注入的独立测量 | 一致 | 同上 | 内置自测自报 `quote_violations_after_injection=1`，与受控伪造引文注入独立测得的 0→1 **数值一致**。说明其 `caught` 结论可被外部测量印证，而非仅凭自述。同时记录脆弱点：`caught` 依赖被截断到 10 行的 sample（保守方向：可能漏报、不会虚报），建议上游改为按违规条数或 id 直接查询 | 命令输出 | 90d |
| EV-040 | 2026-10-01 | 真实库未被触碰 + 全量回归 | pass | `data/growth.db`；Growth OS 73 项 / evkg 101 项 | 三场景全程在真实库**副本**上执行，执行后真实库逐表计数与基线**零差异**。全量回归：Growth OS **73 passed**、evkg **101 passed**、lint 全过、`audit_store` = pass/0 | 命令输出 | 90d |
| EV-041 | 2026-10-01 | **内容级**恢复核对 `artifacts/m1f/verify_no_content_change.py`（计数级加固） | exit 0 | script `b782aa143533`；`recovery_content_check.json` `94fe6e6d71a4` | **通过**。按用户给定最小攻击重跑：基线 sources=3 / passages=109 / claims=2 / evidence=6 / audit=PASS → 注入（已存在 claim+source、`passage_id=p_nonexistent`、引文「代码证明用户完成实现」）→ `evidence_missing_passage` 0→1、audit=FAIL → 清理后四张表**逐行 payload sha256 完全一致**（新增 0 / 删除 0 / 内容变更 0）、audit 回到 PASS/0；真实库同样**内容级一致**。补这一步的原因：计数级核对验不出「条数不变但既有行被改写」 | 命令输出；`artifacts/m1f/recovery_content_check.json` | 90d |
| EV-042 | 2026-10-02 | 独立复跑全量测试：evkg `pytest -q`（正序 + 逆序文件顺序两轮）、Growth OS `pytest -q` | exit 0（两套、三轮） | evkg @ `28afbc0`；Growth OS `backend/growth_os/` | **evkg 101/101（正序与逆序均全绿）、Growth OS 73/73**，与用户提供的 M1-f 数字一致。收集计数独立核对：14 边界 + 10 故障自测 + 22 档案 + 27 适配层 = 73。M1-g 的全部结论建立在此回归基线上 | 命令输出 | 90d |
| EV-043 | 2026-10-02 | **D1 双实例隔离实测** `artifacts/m1g/run_d1_profile_isolation.py`（两个探针领域包 × 两个独立 DB） | exit 0 | script `135dd3a5c31f`；`d1_profile_isolation.json` `dee378cf7a22` | **全局 profile 被实测证实为进程级、且双实例互相污染**：① 静态：`_ACTIVE` 是模块属性，`KnowledgeStore.__init__` 只有 `path`，`ingest_path` 无 profile 参数；② storeA 在 A 激活时入库 4 段 → B 激活后**不重新激活 A** 再入库同一文件 → 变 2 段（B 规则，同 source_id）；重新激活 A 后恢复 4 段；③ asyncio 事件强制交错：任务 A 期望 4 段、实得 2 段（跨任务污染）；④ 给实例挂 `profile` 属性被忽略，per-call `activate` + try/finally 可顺序隔离，并发无解 → 必须改上游；⑤ 适配层 footgun：未 `configure()` 时静默按 evkg 默认领域包入库（5 段 + 默认理由 vs 2 段 + 成长理由）。全程真实库哈希前后一致 | 命令输出；`artifacts/m1g/` | 长期（D1 判定依据） |
| EV-044 | 2026-10-02 | **R4 实库审计 + 追溯链核验** `artifacts/m1g/run_r4_evidence.py` | exit 0 | script `c02e211877d1`；`r4_evidence.json` `27139373f82e` | **audit = pass / 0 violations（10/10 检查）**；逐表 payload sha256 前后一致（审计只追加 `audit_log` 1 行，证据数据零变化）；`claim→evidence→passage→source` 全链核验：6/6 引文逐字在原文、证据全部有来源与 `growth_evidence_type`/`growth_channel` 标签、2/2 主张有证据、抽取账本 109/109 `complete` | 命令输出；`artifacts/m1g/r4_evidence.json` | 90d |
| EV-045 | 2026-10-02 | **三项上游缺陷在真实数据/副本上复现**（同 `run_r4_evidence.py` 的三段实验） | 复现成立 | 同上 | ① **partial 渲染**：副本上给 `partial` 证据行打哨兵，上游 `render_claim_markdown` 输出中**无**该哨兵，而 supports 阳性对照哨兵**有** → 静默丢弃（结构化 dossier 里该行仍在，supports=2/refutes=0）；② **抽取模型名**：claim metadata 有 `verifier_model`、**无**任何 extraction 模型键；批账本 payload 仅计数；唯一带 `model` 列的 `v2_reading_steps` 为 0 行；③ **caught 截断**：副本预置 12 条伪造引文后跑内置自测 → `quote_violations_after_injection=13`、审计 `fail`，但 `status=missed`（注入 id 不在前 10 行 sample）；干净副本同代码 `caught`/1 | 命令输出；`artifacts/m1g/r4_evidence.json` | 长期（上游清单依据） |
| EV-046 | 2026-10-02 | **R3 行级覆盖实测** `artifacts/m1g/line_coverage_plugin.py`（`sys.settrace`，零新依赖） | exit 0 | plugin `971a1fad02b0`；`r3_coverage.json` `22b7f1ce87ff` | Growth OS 自身：`adapter.py` **83.3%**（未覆盖仅 4 处逻辑：两个错误分支、`logical_id_for`、`damage_selftest` 转发）、`dossier.py` **96.1%**（未覆盖为截断与 `score=None` 等展示分支）。**LLM 路径无自动化测试**：`extract.py` 0%、`verifier.py` 18.2%、`model_gateway.py` 18.8% —— 抽取/攻击结论系一次性真实运行，非持续验证。V1 富格式路径（PDF/docx）亦未端到端验证 | 命令输出；`artifacts/m1g/r3_coverage.json` | 90d |
| EV-047 | 2026-10-02 | **M1 完成条件补跑：`init`（CLI）与 `reindex`（FTS5）** `artifacts/m1g/run_reindex_search_check.py`（真实材料副本 + 临时空库） | exit 0 | script `8532375183a8`；`reindex_search_evidence.json` `316a1fb1af07` | ROADMAP M1 第 1 条含 `init → … → reindex`，此前两步均无实际输出（R3 覆盖显示 cli/index 0%），本次补齐：① `evkg --db <tmp> init` = exit 0，**建立 35 张 schema 表**、全部计数为 0、profile=default；② `rebuild_index` = `mode=fts`，**109 段落 + 2 主张**入索引，重复重建**幂等**；③ 索引后 `audit_store` 两轮均 **pass/0**；④ 检索 5 个真实词条 4 命中（RAG/ChromaDB/Dubbo/检索服务 均有 passage 与 claim 命中），`计划学习` 为 2 字词按设计回落 LIKE 且 predicate 不在索引字段 → 0 命中（记为检索边界）。真实库哈希前后一致。**顺带发现**：`KnowledgeStore` 无 `close()`/上下文管理器，Windows 上连接泄漏会锁库文件（首次运行 `WinError 32`） | 命令输出；`artifacts/m1g/reindex_search_evidence.json` | 90d |
| EV-048 | 2026-10-02 | **B-g1 交付方案实测**（临时目录，未改动工程文件）：`git bundle` 生成/校验/克隆 + 裸仓镜像 + uv `file://`+`rev` pin 探针 | exit 0 | bundle SHA-256 `10dafff49bb8e627007c4bb5cc3ddfcfce1108ef9b97c42763bf93a8b8c13801`（238,807 字节） | ① bundle 重新生成**字节一致**；`git bundle verify` = 完整历史/ok；从 bundle 克隆 HEAD=`28afbc0db7061d9717e307bf2bd0833f59fd8f51`、5 提交、fsck 无异常；② 裸仓 `git ls-remote` 可解析 HEAD/main；③ **uv 层 pin 成立**：scratch 项目 `{ git = "file:///…", rev = "28afbc0…" }` → `uv lock` 解析 24 包，lock 记录 URL+rev；④ `editable` 与 `git` 互斥（uv 报 `cannot specify both`）→ pin 与开发期 editable 循环不可兼得，故建议开发期保留 path、发布/CI 前再 pin。比较与建议见 `docs/M1-SPIKE-CONCLUSION.md` §9.1 | 命令输出（本会话）；`docs/M1-SPIKE-CONCLUSION.md` §9.1 | 长期（B-g1 决策依据） |
| EV-049 | 2026-10-02 | **B-g1 方案 A 落地：bundle 归档 + 双副本 + 恢复验证**（用户确认后执行） | exit 0 | bundle SHA-256 `10dafff4…3801`（238,807 字节）；manifest SHA-256 `969d20764db6…`（3,480 字节） | **归档完成并逐项验证**：① 主副本 `D:\projects\_evkg-archive\evkg-28afbc0.bundle`，第二副本 `C:\Users\Lenovo\evkg-archive\`（两副本 SHA-256 一致）；② `git bundle verify` = 4 refs（main/HEAD=`28afbc0`，origin/main=`a448f44`）、"complete history"、ok；③ 临时目录从归档克隆：HEAD=`28afbc0db7061d9717e307bf2bd0833f59fd8f51`、5 提交、`git fsck` 零输出；④ 同目录 `evkg-bundle-manifest.txt` 登记归档位置、哈希、commit、验证日期、恢复命令与约束。**未完成项（如实登记）**：第二副本仍在 C: 盘，若与 D: 同物理盘则不具备抗物理损坏能力——需用户另存移动硬盘/云盘 | `D:\projects\_evkg-archive\`、`C:\Users\Lenovo\evkg-archive\`（含 manifest） | 长期（依赖交付） |

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
| M1-f | 2026-10-01 | 伪造数据可被发现 + 清理可恢复（3 场景） | `artifacts/m1f/` | 通过 | EV-037 | — |
| M1-f | 2026-10-01 | 检测行为被测试固化（10 项，含内容级） | `tests/test_damage_selftest.py` | 通过 | EV-038 | — |
| M1-f | 2026-10-01 | 自报与独立测量交叉印证 | 副本库 | 通过 | EV-039 | — |
| M1-f | 2026-10-01 | 真实库未被触碰 + 全量回归 | `data/growth.db` | 通过 | EV-040 | — |
| M1-g | 2026-10-02 | 全量回归独立复跑（evkg 101 正/逆序、Growth OS 73） | 两个仓库 | 通过 | EV-042 | — |
| M1-g | 2026-10-02 | **D1 进程级全局 profile 实测**（双实例污染、并发交错、公开 API 隔离、适配层 footgun） | `evkg.config` | 通过（实测，结论见结论文档 §5.3） | EV-043 | — |
| M1-g | 2026-10-02 | R4 实库审计 + 证据链逐字核验 | `data/growth.db` | 通过 | EV-044 | — |
| M1-g | 2026-10-02 | R2 上游缺陷复现（partial 渲染 / 抽取模型名 / caught 截断） | evkg @ `28afbc0` | 复现成立（已列入上游清单） | EV-045 | — |
| M1-g | 2026-10-02 | R3 覆盖实测与盲区界定（含 LLM 路径无自动化测试） | `backend/growth_os/` | 通过（结论含限制） | EV-046 | — |
| M1-g | 2026-10-02 | **R1–R4/D1 收口 + 依赖策略判定** | `docs/M1-SPIKE-CONCLUSION.md` | 通过（判定：有条件依赖 C1–C5） | EV-042…EV-046 | 用户（待确认收口） |
| M1-g | 2026-10-02 | M1 完成条件补跑：`reindex`（FTS5 索引 + 检索）在真实材料上产出实际输出 | `data/growth.db` 副本 | 通过 | EV-047 | — |
| B-g1 | 2026-10-02 | **evkg 依赖交付**：bundle 归档 + 双副本 + 恢复验证（用户确认方案 A） | evkg @ `28afbc0` | 通过 | EV-048 EV-049 | 用户（已确认方案 A） |

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
| 2026-10-01 | M1-f（damage selftest：伪造数据发现与恢复） | EV-037 EV-038 EV-039 EV-040 | 通过 | 上游两项建议（partial 渲染、caught 样本截断） | **M1-f 验收通过** |
| 2026-10-02 | M1-g（技术 spike 收口：R1–R4 + D1 依赖边界） | EV-042 EV-043 EV-044 EV-045 EV-046 EV-047 | 通过 | 阻塞：B-g1（evkg 依赖 pin/可获取）、B-g2（M3 富格式路径未验证）；延后：实例级 profile、抽取模型持久化（M4 前）、渲染器 partial、caught 判定等（见结论文档 §9） | **M1-g 验收通过；M1 技术 spike 结束，依赖策略 = 有条件依赖（C1–C5）** |
| 2026-10-02 | B-g1（evkg 交付：方案 A 本地 bundle 归档） | EV-048 EV-049 | 通过 | 第二副本与主副本可能同物理盘，抗物理损坏的异地/离线副本待用户另存（未计入验收）；发布/CI 前切换 `git + rev` pin | **B-g1 已解除（交付形式落定并验证）；M1 正式归档** |

验收方式说明、证据格式与证据链自举机制见 `docs/ACCEPTANCE_GATES.md`（§1 原则、§2 自举机制、§5 记录格式）。约束：验收证据库 `data/acceptance.db` 与用户证据库物理隔离，项目验收证据不得进入用户能力断言通道，否则会污染 G3 的判定。
