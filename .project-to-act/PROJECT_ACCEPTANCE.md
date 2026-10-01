# 项目验收

> 当前验收与有效证据的紧凑视图。原始输出和完整报告以路径与哈希引用，不在此粘贴。

## 当前验收结论

- 结论：**M0 / M1-a / M1-b / M1-b.5a / M1-b.5b 均通过**；M1-b.5c、M1-b.5d 与 M1-c 未开始
- 验收范围：M0 收口项 + M1-a（领域包生效、依赖解析）+ M1-b（双轨记录、真实材料入库、QG1）+ M1-b.5a（evkg 改造、适配层变薄、旧数据不变性、locator 真值）+ M1-b.5b（缺失值语义、下游消费者、旧数据不变性）
- 最后检查：2026-10-01
- 遗留问题：symbol 级代码精度需解析器（已明确排除）；跨切分器重入库的 passage 累积待 b.5c；G1–G6 与 QG2–QG5 未开始

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

## 验收记录

| 日期 | 检查范围 | 证据 ID | 结果 | 遗留问题 | 结论 |
|---|---|---|---|---|---|
| 2026-10-01 | M0 收口（账本/索引/选型） | EV-001 EV-002 EV-003 | 通过 | G1–G6、QG1–QG5 全部未开始 | **M0 验收通过**，M1 可开工 |
| 2026-10-01 | M1-a（领域包生效、依赖解析） | EV-004 EV-005 | 通过 | R1/R2/R4 待后续小步 | **M1-a 验收通过** |
| 2026-10-01 | M1-b（入库、双轨记录、QG1） | EV-006 EV-007 EV-008 | 通过 | M1-c 起需 LLM API Key | **M1-b 验收通过** |
| 2026-10-01 | M1-b.5a（evkg 源码一等支持、适配层变薄、旧数据不变性） | EV-009 EV-010 EV-011 EV-012 | 通过 | symbol 级精度待解析器；跨切分器累积问题待 b.5c | **M1-b.5a 验收通过** |
| 2026-10-01 | M1-b.5b（缺失值语义、下游消费者、旧数据不变性） | EV-013 EV-014 EV-015 EV-016 | 通过 | — | **M1-b.5b 验收通过** |

验收方式说明、证据格式与证据链自举机制见 `docs/ACCEPTANCE_GATES.md`（§1 原则、§2 自举机制、§5 记录格式）。约束：验收证据库 `data/acceptance.db` 与用户证据库物理隔离，项目验收证据不得进入用户能力断言通道，否则会污染 G3 的判定。
