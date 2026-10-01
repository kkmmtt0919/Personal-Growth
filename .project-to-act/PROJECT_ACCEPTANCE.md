# 项目验收

> 当前验收与有效证据的紧凑视图。原始输出和完整报告以路径与哈希引用，不在此粘贴。

## 当前验收结论

- 结论：**M0 地基与治理已验收通过；M1-a 成长领域包已验收通过**；M1 其余小步与产品功能（G1–G6、QG1–QG5）尚未开始
- 验收范围：M0 收口项（账本合法性、文档索引、选型确认）+ M1-a（领域包实际生效、path 依赖可解析）
- 最后检查：2026-10-01
- 遗留问题：R1/R2(过滤)/R4 待 M1-b…M1-g 验证；G1–G6 与 QG1–QG5 全部未开始

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

## Gate 记录

| Gate ID | 日期 | Gate | 对象 | 结果 | 证据 ID | 豁免与确认人 |
|---|---|---|---|---|---|---|
| A-001 | 2026-10-01 | 治理账本合法性 | `.project-to-act/` | 通过 | EV-001 | — |
| A-002 | 2026-10-01 | 文档索引一致性 | `docs/` | 通过 | EV-002 | — |
| A-003 | 2026-10-01 | 选型确认 | Q1–Q4 | 通过 | EV-003 | 用户 |
| M1-a | 2026-10-01 | 成长领域包实际生效（非仅可加载） | `growth_os.yaml` | 通过 | EV-004 | — |
| M1-a | 2026-10-01 | evkg path 依赖可解析 | `pyproject.toml` | 通过 | EV-005 | — |

## 验收记录

| 日期 | 检查范围 | 证据 ID | 结果 | 遗留问题 | 结论 |
|---|---|---|---|---|---|
| 2026-10-01 | M0 收口（账本/索引/选型） | EV-001 EV-002 EV-003 | 通过 | G1–G6、QG1–QG5 全部未开始 | **M0 验收通过**，M1 可开工 |

验收方式说明、证据格式与证据链自举机制见 `docs/ACCEPTANCE_GATES.md`（§1 原则、§2 自举机制、§5 记录格式）。约束：验收证据库 `data/acceptance.db` 与用户证据库物理隔离，项目验收证据不得进入用户能力断言通道，否则会污染 G3 的判定。
