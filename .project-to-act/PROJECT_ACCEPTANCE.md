# 项目验收

> 当前验收与有效证据的紧凑视图。原始输出和完整报告以路径与哈希引用，不在此粘贴。

## 当前验收结论

- 结论：**M0–M3 通过并收口；M4 完成并封板；M5 进行中**（2026-10-03）。**M5 方案已冻结**（EV-072）；**M5-a 已验收**（EV-073）；**M5-b 已验收**（EV-074）：gap → task 生成器（LLM 提议 + 七步闸门）+ **G4 通过** —— 离线/真实各 14/14，真实运行 2/2 HTTP；**M5-c 已验收**（EV-075）：任务提交闭环（唯一入口 + 单入口证据 + 材料 claim + 绑定闸门 + M4-e 重评 + 归因/三联条件守卫）—— 离线 38/38、真实 12/12（真实运行 **1/1 HTTP**）。**M4 已封板**（M4 Gate 21/21，EV-071）。详见 `artifacts/m4e/README.md`、`artifacts/gates/M4/README.md`、`artifacts/gates/G4/README.md`、`artifacts/m5c/README.md`
- 验收范围：M0 收口项 + M1-a…M1-g（见下方历史行）+ **M2** + **M3（a/b、B-g2、c/d/e、M3 Gate）** + **M4（基线冻结 v1.0、M4-a…M4-e、M4 Gate）** + **M5（方案冻结、M5-a…M5-c）**
- 最后检查：2026-10-03
- 遗留问题：**M5 实施中** —— M5-a 与 **M5-b 已验收（G4 已通过）**；**M5-c 已验收**；**M5-d（G5 + M5 Gate）进行中**；**M4 保留边界（M5 沿用）** —— 评估在独立实验库产出、真实库不含 `g_` 表；G3 主体为 RAG 相关能力、A 臂笔记为受控构造（均已标注）；**已登记的推迟项** —— M4-b.1（`supersede_missing` 生成器接线）、M3 开放项（PDF 适配层 V1 入口、页码级 locator）；**归档第三副本**（抗物理损坏）待用户另存移动硬盘/云盘；**归档刷新**（bundle 指向 `28afbc0`，本地领先 6 个提交，含 `9a21552`）；**发布/CI 前**将 evkg 依赖切换为 `git + rev` 并复跑测试（须包含 `db2de3a` 与 `9a21552`）；**多领域包或并发 profile 前**必须改上游 profile 作用域；**G4、G5 与 M5 Gate 13/13 已通过**（EV-076）

## 验收标准

产品验收门（完整定义与判定方法见 `docs/ACCEPTANCE_GATES.md`）：

| 标准 ID | 标准 | 状态 | 验证方法摘要 | 证据 ID |
|---|---|---|---|---|
| G1 | Goal Clarification：模糊目标 → 明确目标 | **通过** | 冷启动 ≤6 轮产出含四要素的 confirmed goal；含反例检查（真实模型会话；截图豁免待 M8 补证） | EV-056 EV-057 |
| G2 | Evidence Traceability：能力判断可追溯 | **通过**（用户 2026-10-03 确认） | 抽 5 条 assessment 逐跳追溯至原文；`audit_store`=pass —— 7/7 评定行可追溯（5 条抽样，引文逐字） | EV-071 |
| G3 | Capability Audit：识别"自称会但证据不足" | **通过**（用户 2026-10-03 确认） | **A/B 对照实验**：A 弱证据（理解 2 / 实践无 ≥2 等级）vs B 强证据（实践 3）；C（JD）不进 supports | EV-071 |
| G4 | Task Quality：任务针对缺口且可验收 | **通过**（用户 2026-10-03 确认） | 每个 task 可反向映射到 gap 且含 {可交付物/时长/验收方式}；4 条反例（含字面"去学习 Agent Evaluation"）全部被拒并留档；逐条规则校验通过率 2/6（分母含注入对例，已注明） | EV-074 |
| G5 | Growth Loop：完成 → 新证据 → 能力变化自动发生 | **通过**（2026-10-04） | 单命令端到端：实践 3→4、缺口关闭、归因链可反查；2/3 HTTP | EV-076 |
| G6 | User Return Value：回来能看到变化与下一步 | 待检查 | snapshot diff + 变化摘要 + 下一步建议 + 引用长期偏好 | 无 |

质量门：

| 标准 ID | 标准 | 状态 | 验证方法摘要 | 证据 ID |
|---|---|---|---|---|
| QG1 | 证据不变量 | **通过** | `evkg audit_store` = pass，9 项检查 0 violation（M3 Gate 复核 pass/0） | EV-065 |
| QG2 | 攻击自测 | **通过**（M1-f 双向测量口径） | 伪造数据注入前/后双向测量（不采信内置 `status` 单值，C4）；三场景 caught 且清理后零差异 | EV-037…EV-041 |
| QG3 | 评级规则覆盖 | **通过** | `tests/test_assessment_rules.py` 覆盖含 G3 A/B 场景的决定性用例（M4-c 建立；M4-e 在真实材料上复核） | EV-069 EV-071 |
| QG4 | 无密钥入库 | **通过** | 仓库与账本无明文密钥；`.env` 已 gitignore；日志脱敏（M3 Gate：119 个跟踪文件 0 命中） | EV-065 |
| QG5 | 全量测试 | **通过** | `uv run pytest` 全绿（M3 Gate：Growth OS 267 项 + evkg 107 项 + ruff） | EV-065 |

治理门（M0）：

| 标准 ID | 标准 | 状态 | 验证方法摘要 | 证据 ID |
|---|---|---|---|---|
| A-001 | 治理账本结构合法 | **通过** | `--validate` 与 `--audit` 均 `valid=true, strict_valid=true, errors=[], warnings=[]` | EV-001 |
| A-002 | 规划文档齐备且索引一致 | **通过** | `docs/` 下 5 份内容文档全部登记于 `docs/README.md`，无未登记文件（差异仅为索引自身 README.md） | EV-002 |
| A-003 | 用户确认 Q1–Q4 选型 | **通过** | 4 项均选定并记录于 `docs/DECISIONS.md`，采纳推荐方案 | EV-003 |

## 证据索引

| 证据 ID | 时间 | 方法摘要 | 退出状态 | 版本或文件哈希 | 结果摘要 | 证据位置 | 有效期 |
|---|---|---|---|---|---|---|---|
> 历史归档：[2026-10](archive/acceptance/2026-10.md)（EV-001…EV-054；本页保留最近 20 条）

| EV-055 | 2026-10-02 | **M2-d 两层预算口径实现与验证**（应用层 ≤8 结构化调用；传输层 HTTP 硬上限 + 零额外重试；失败即停并留档） | exit 0（离线） | `tests/test_http_budget.py`；`tests/goal_flow_fixtures.py`（HttpRequestBudget）；`artifacts/m2/budget-and-limits.json`；测试 128→**133** | ① **包装器覆盖性先核对再定上限**：静态确认 evkg 网关唯一 HTTP 调用点是 `client.post`（三个 provider 分支共用重试循环），动态用 MockTransport 断言"计数=实际尝试数（重试也计入）"；② **零额外重试**：真实模式强制 `EVKG_HTTP_RETRIES=1`，单次调用只发 1 个请求（有测试）；③ **硬上限立即生效**：cap=2 且允许重试时第 3 次请求被拦下，`HttpBudgetExceeded` 穿透重试循环不再尝试（有测试）；④ **失败即停**：轮次耗尽 → 退出码 3 + 诊断记录（应用层 6 次、HTTP 0、tokens>0、失败原因、四要素未被自动补齐），不自动重跑（有测试）；⑤ 授权开关仍然有效：未设 `M2_ALLOW_REAL_MODEL` 时拒绝执行（subprocess 测试，且清空密钥双保险）；⑥ 真实库哈希与证据计数未变、**真实调用 0 次** | 命令输出；`artifacts/m2/budget-and-limits.json` | 90d |
| EV-056 | 2026-10-02 | **M2-d 真实会话端到端通过（G1 证据）**：`glm-5.3-flash`，应用层 6 次调用 / HTTP 6 个请求 / 零额外重试 | exit 0 | `artifacts/m2/session-real.json`；`artifacts/gates/G1/README.md`；测试 143 项 | **首次在同一次真实运行内闭环**：澄清 4 轮（3 要素 + 1 确认）→ 四要素齐全 + 用户原话确认 → 能力树 6 领域/12 组/31 个三层能力点 → 人工上调为 5 → 再生成后仍保留 5/理由/`origin=adjusted`；13/13 自检全绿（轮次、四要素、形状、未校验标注、`current_level=unassessed`、lineage、实际 provider/model、预算）；6 条运行记录均为 `openai_compatible/glm-5.3-flash`、`model_source=result`；真实库哈希与证据计数 3/109/2/6 未变 | 命令输出；`session-real.json`、`artifacts/gates/G1/` | 长期（G1 证据） |
| EV-057 | 2026-10-02 | **M2 验收（AC1–AC12 逐项 + 全量回归 + 数据边界）** | 全部满足 | `artifacts/m2/acceptance-report.md`；测试 143（Growth OS）/ 101（evkg） | **AC1–AC12 全部 ✅**（逐项证据见验收报告）：G1 通过；未确认拒绝发生在调用模型前；形状违规整体拒绝；`adjusted` 保护（同 id 覆盖的强证据来自自动化测试，已如实标注）；`g_agent_runs` 记录实际 provider/model；lineage 可追；离线三保险；证据层零写入。全量回归：Growth OS **143 项**、evkg **101 项**、ruff 全过、账本无告警；QG1 `pass/0`（10/10 检查），真实库未被污染。**遗留（不阻塞）**：再生成目前为"并集"语义（不同命名会累积，M4 前需决策替换/合并/留history） | `artifacts/m2/acceptance-report.md` | 长期 |
| EV-058 | 2026-10-02 | **M3-a 实现与验证**：归属层（三取值 + fail-closed 读回 + 消费规则）与越权校验（"存在证据 ≠ 证明能力"） | exit 0 | 新增 `growth_os/evidence/attribution.py`、`growth_os/evidence/claims.py`、`adapter.ingest_document(attribution=...)`；测试 144→**187**（新增 44：归属 24 + 越权 20） | ① 归属只进 `Source.metadata`（键 `growth_attribution`），不新增表；三取值严格限定并有词汇表测试；② **fail-closed**：未声明/非法值一律读作 `unknown`；③ **消费规则矩阵 10 例**：仅 `user_declared` + `user_evidence` 可支撑用户断言，`domain_reference` 无论如何都只作外部参考，`user_asserted` 不得单独支撑；④ **越权校验 20 例**：M1-c 历史主张判越权（只判定、不追改）、材料口径合规、材料成就与自述计划不误报、用户等级表述判越权；⑤ 复用优先：链路结构沿用 evkg，本步只加策略与校验层；⑥ 全量回归 187 + evkg 101 + ruff 全过；⑦ 数据边界：逐表内容哈希与 M1-g 基线逐项一致（6/6 evidence、2/2 claim），QG1 pass/0，无 `g_` 表写入 | 命令输出；`artifacts/m3a/evidence-anchors.json` | 90d |
| EV-059 | 2026-10-02 | **M3-b 实现与验证**：本地材料 ingestion（MD/TXT/代码/ZIP）—— 实际支持范围核对 + ZIP 容器级封装 + 归属/通道贯穿 | exit 0 | 新增 `growth_os/evidence/archive.py`；`adapter.ingest_document` 新增 `extra_metadata`（保留键防覆盖）；测试 187→**222**（新增 35） | ① 范围以源码为准：文本仅 `.txt/.md/.markdown/.text/.csv/.json/.log`，代码取 evkg 语言表 + 无扩展名构建文件，其余（PDF/docx/xlsx/HTML）一律 `EvidenceError`；ZIP 此前未支持；② ZIP 走唯一入口（spy 断言无旁路），ok/skipped/failed 逐条目可见且不中断；③ 安全：路径穿越与绝对路径跳过、解包目标双重校验、四道上限可注入、稳定解包目录使重复入库命中同一 `source_id`；④ 来源定位：metadata 记归档路径/条目名，代码 locator 可回原文逐字核对；⑤ 归属/通道贯穿（保留键不可被 `extra_metadata` 覆盖）；⑥ 实跑 5 条目 → 2 ok / 3 skipped / 0 failed；⑦ 全量 222 + evkg 101 + ruff 全过，真实库逐表内容哈希与计数对锚点一致 | 命令输出；`artifacts/m3b/support-matrix.md` | 90d |
| EV-060 | 2026-10-02 | **B-g2：PDF spike（独立验证）** —— 真实中文 PDF 经 V1 状态机入库 / audit / locator 可核对性 | exit 0 | `artifacts/bg2/run_pdf_spike.py`、`pdf-spike-result.json`、`README.md`；evkg @ `28afbc0` | **判定：不通过（现状）→ PDF 保留为不支持格式并记录缺口**，缺口是**一行缺陷**：① A 轮（现状）`failed`：`AttributeError: bytes has no attribute seek`（`PdfReader` 未把 bytes 包成 `BytesIO`；同文件 `OfficeReader` 却是对的；evkg 测试对 PDF 零覆盖）；② B 轮（仅脚本内打上该修复的诊断）：入库成功（40 段）、`audit_store` **pass/0**、**locator 仅 `ordinal`**（识别阶段 5 个 span 带页码但未写进 locator）→ 无页码级定位、对原 PDF 不保证逐字；段落对归一化文本是**完整分区**（去空白逐字一致）；③ 失败被 V1 如实记录在库；④ `uv sync --extra office` 会移除 dev 工具（须带 `--extra dev`；已恢复、`uv.lock` 未变）；⑤ V1 入库不带成长标签 → PDF 若进产品需适配层新增 V1 入口；⑥ 临时库已删、未触碰真实库 | 命令输出；`artifacts/bg2/` | 90d |
| EV-061 | 2026-10-02 | **B-g2 重跑（上游最小修复后）**：真实中文 PDF 三项验证 + 两个问题分离记录 | exit 0 | evkg @ `db2de3a`；`artifacts/bg2/pdf-spike-result.json`、`README.md`；evkg 测试 101→**107** | **判定：通过（含明确边界）**。① 上游修复**仅一行**（`Reader(io.BytesIO(content))`，evkg `db2de3a`）+ 6 项真实 PDF 读取测试；evkg **107 项全绿**、ruff 未新增；② 重跑：入库成功（40 段）、**audit pass/0**、**as-is 与等价实现两轮完全一致**（交叉印证）；③ **问题分离**：bytes 缺陷 fixed；**页码级 locator 为独立开放项**（第 14 项）—— 仅 ordinal、无 page-level、对原 PDF 不保证逐字，但对归一化文本是**完整分区**（缺失 0）；④ PDF 支持边界写入 M3-PLAN §5（能/不能 + blocking 澄清 + 适配层 V1 入口待接）；⑤ 范围锁死：未动 locator/V1/completeness/audit_store/适配层/M3-c；未推送远程；⑥ 附带：`uv sync --extra office` 会移除 dev 工具（须带 `--extra dev`；lock 未变）；归档待刷新 | 命令输出；`artifacts/bg2/` | 长期（PDF 支持依据） |
| EV-062 | 2026-10-02 | **M3-c：GitHub 公共仓库接入（无 OAuth）** —— 真克隆入库 / 技术栈清单 / 归属通道贯穿 | exit 0 | 新增 `growth_os/evidence/github.py`、`adapter.code_language_for`；`artifacts/m3c/`；测试 222→**243** | ① 真实冒烟（`kkmmtt0919/mytset-rag`）：无凭据浅克隆 `c417a096…`；35 文件 → 选中 20（12 条上限/3 条格式）→ **20 ok / 0 failed**、**179 段**、**audit pass/0**；技术栈 java/python/xml/yaml；同 ref **幂等**；② 归属/通道贯穿（`repo_artifact`/`user_evidence`/`user_declared`，`can_support_user_claim=True`）＋来源记 `growth_github_{repo,ref,sha,path,url}`；③ 无旁路：spy 断言逐文件走单入口；④ 决策：改 git 浅克隆（API 配额耗尽）、目录按 owner-name-ref 稳定、SHA 写 metadata；⑤ Windows pack 只读坑已处理；⑥ 边界：未接 OAuth/私有仓库/UI/评估，**claims 与可检索留 M3-e / Gate**；⑦ 243 + evkg 107 + ruff 全过、真实库对基一致 | 命令输出；`artifacts/m3c/` | 90d |
| EV-063 | 2026-10-02 | **M3-d：外部参考通道（JD / domain_reference）** —— 通道结构锁定 + 参考抽取只读 | exit 0 | 新增 `growth_os/evidence/reference.py`；`tests/test_reference_ingest.py`（8 项）；`artifacts/m3d/`；测试 243→**251** | ① 三条"不得"由**结构**保证：入口签名无 `channel`/`evidence_type`（API 层不可达 user_evidence）、消费侧 `can_support_user_claim` 一票否决、抽取只读（不写 claim/evidence/entity，不评分不差距）；② 冒烟（合成 JD）：13 段、**27 技术词**（全带 passage 证据）、4 条要求条目、`audit_store` pass/0；③ **8 项边界检查全过**（通道锁定、不在 user_evidence、不能支撑用户断言、抽取前后计数不变、claims/evidence/entities=0、reference_kind 记录）；④ 用例：ASCII 词边界（"go" 不命中 "google"）、多份参考分别列出、非参考来源抽取被拒；⑤ 素材如实标注：无现成真实 JD，用写实合成样本；⑥ 边界守恒：未接 UI、未做匹配评分/差距，claim 留 M3-e；⑦ 251 + evkg 107 + ruff 全过、真实库对基一致、临时库无残留 | 命令输出；`artifacts/m3d/` | 90d |
| EV-064 | 2026-10-02 | **M3-e：材料口径 claim + audit + provenance**（越权校验接线 + 历史主张只读 dry-run） | exit 0 | `adapter.create_material_claim`；`tests/test_material_claims.py`（9 项）、`test_claim_overreach.py` 扩充；`artifacts/m3e/`；测试 251→**266** | ① **越权校验接进写入路径**：写入前判定，越权即拒且**零写入**；置信度 `score=None`+`unassessed`；证据 quote 为逐字原文；claim id 由内容派生（幂等）；② **5 条材料口径 claim**（完成条件 3 的 claim 部分），`audit_store` pass/0，provenance 逐跳可走通；③ **历史主张只读 dry-run**（真实库零写入，`mode=ro`）：1 条判越权（用户/实现过，即 M1-d 被推翻那条）、1 条判干净（用户/计划学习）；④ **修掉校验器假阳性**：dry-run 首轮把"计划学习"误判（陈述含"不代表已具备"）→ 加否定语境识别 + 正反测试；⑤ 边界：材料口径为唯一形态，星级仍留 M4；⑥ 回归 266 + evkg 107 + ruff 全过、真实库逐表哈希与计数与 M3-a 锚点一致 | 命令输出；`artifacts/m3e/` | 90d |
| EV-065 | 2026-10-02 | **M3 Gate：证据接入（完成条件 1–5 + 质量门）端到端** | exit 0 | `artifacts/m3gate/`、`artifacts/gates/M3/README.md`；测试 266→**267** | **13/13 全过**：① PDF（真实中文 5 页 → 40 段）与 Markdown 均可检索（FTS：237 段 + 5 claim，查询各命中）；② ZIP → 3 文件全入库、code-kind 带 language（java/python）；③ 公共仓库 → 20 文件 + 技术栈 4 类 + **5 条材料口径 claim**；④ 克隆禁交互、不存在仓库 `rc=128` 快速失败、**119 跟踪文件 0 密钥**；⑤ JD 落 domain_reference 且不能支撑用户断言；质量门：audit pass/0、真实库逐表哈希与计数对基一致、临时库已删。**修掉两处**：git 非 UTF-8 输出致崩溃、密钥扫描误报。**边界保留**：PDF 适配层 V1 入口未建、页码级 locator 仍缺 | 命令输出；`artifacts/gates/M3/` | 长期 |
| EV-066 | 2026-10-02 | **M4 基线冻结（v1.0）**：用户逐项确认七项 —— G2/G3 判定方式、归属三层不合并、再生成语义 = history + current view、C5 = 上游最小修、claim↔capability = LLM 提议 + 确定性闸门、G3 实验 = 真实材料 + 受控构造 + 独立库、ROADMAP 交付物 2 由"摄入"改为"基于已准入证据生成可审计能力评估" | 通过 | `docs/M4-PLAN.md` v1.0（执行基线）；`docs/README.md` 索引同步 | 七项决定全部写入基线；M4-a 边界写死（模型契约 + provenance 前置；不做星级/LLM/UI/G3）；验收标准 12 项映射保留（AC1–AC12） | `docs/M4-PLAN.md`；账本 validate/audit 无告警 | 长期 |
| EV-067 | 2026-10-02 | **M4-a 实现与验证**：Assessment 基础模型 + provenance 前置（C5）+ `claim/evidence → draft → 独立 audit artifact` 最小闭环 | 冒烟 11/11；回归全绿 | 新增 `growth_os/assessment/{contract,draft,audit}.py`、`adapter.claims_overview`、`g_` 两表与生命周期字段、`tests/test_assessment_contract.py`（19 项）+ dossier 读取测试；evkg `9a21552`（4 项新测试）；Growth OS 267→**287**、evkg 107→**111** | ① 草案契约 `level` 恒 NULL（无星级算法）；② 准入闸门四类矩阵 + 越权 + 链完整性/逐字（fail-closed）；③ history + current view（superseded 不删除历史、`adjusted` 不自动降级、旧库自动补列）；④ 起草/审计**零写回证据库**、`audit_store` pass/0；⑤ 历史主张只读扫描（mode=ro）：overreach 1 / plan 1，与 M3-e 判定一致、零写入；⑥ C5 provenance 取自实际返回值，档案渲染器三态显示；⑦ 真实库逐表内容哈希 + 计数对 M3-a 锚点一致、真实库无任何 `g_` 表；⑧ 287 + evkg 111 + ruff 全绿。细节见 `artifacts/m4a/README.md` | 命令输出；`artifacts/m4a/` | 90d |
| EV-068 | 2026-10-03 | **M4-b 实现与验证**：证据绑定与分桶（LLM 提议 + 八步确定性闸门 + 映射落库）；离线闭环 + 逐步 reject 对例 + **1 次真实模型提议运行** | 离线 9/9；真实 8/8 | 新增 `growth_os/assessment/{buckets,binding}.py`、`store.get_capability_by_path`、`tests/test_assessment_binding.py`（20 项）、`artifacts/m4b/`；测试 287→**307** | ① 分桶映射确定性（6 类型全表；`external_ref` 不入桶）；② 提议 schema 仅三字段（confidence/level/score 注入 → schema 拒绝）；③ 八步闸门固定顺序、失败零写入；拒绝记录含 proposal_id/reject_reason/gate_stage/timestamp/run_id；④ **LLM 无直接落库路径**（桥表行数 == 接受数；二次运行全 duplicate）；⑤ 真实运行：`openai_compatible/glm-5.3`、1 次结构化调用 / 1 个 HTTP 请求（硬上限 1、零额外重试）、1364 tokens；6 候选 → 4 提议 → 3 接受（RAG×2、MCP×1）+ 1 拒绝（自述，attribution_unchanged）；⑥ 真实库逐表哈希 + 计数对锚一致（副本运行、`mode=ro`，真实库零写入）；audit_store pass/0；307 + ruff 全绿；⑦ 生成器接线按用户决定推迟（记 `M4-b.1`）。细节见 `artifacts/m4b/README.md` | 命令输出；`artifacts/m4b/` | 90d |
| EV-069 | 2026-10-03 | **M4-c 实现与验证**：星级规则引擎（理解 / 实践两维度）+ attack 结算接入 + `rated` 写入路径（历史保留）；离线冒烟 12/12 | 12/12；回归全绿 | 新增 `growth_os/assessment/{rules,rater}.py`、`g_assessments` dimension/rated 契约、`tests/test_assessment_rules.py`（18 项）、`artifacts/m4c/`；测试 307→**325** | ① 两维度不合并；基线规则按冻结表（自述不单独产等级 → 不足；`uploaded_doc` 2；`+probe` 3；`repo` 3；`+task` 4；显式信号 5）；② 反向证据：`broken` 剔除、`refutes`/`disputed` 封顶 ≤2、`weakened` ≤3，且**不跨维度污染**；③ 无证据 → `insufficient_evidence`（level NULL，"缺失≠低分"）；④ 同输入同输出 + 幂等；⑤ 分数隔离（0.99 vs 0.05 同结论 + 规则引擎源码 AST 检查）；⑥ 历史语义：草案不被覆盖、等级变化 = 新行、当前视图用 `latest_assessment`；⑦ audit_store pass/0、真实库对锚一致、325 + ruff 全绿；⑧ 推迟项：`current_level` 回填（M4-d）、真实 attack 运行（M4-e）。细节见 `artifacts/m4c/README.md` | 命令输出；`artifacts/m4c/` | 90d |
| EV-070 | 2026-10-03 | **M4-d 实现与验证**：能力解释报告（支持 / 不足 / 攻击 / 已排除 + 逐字引文）+ `current_level` 维度化回填与重建校验；离线冒烟 15/15 | 15/15；回归 335 全绿 | 新增 `growth_os/assessment/report.py`、`g_capabilities` 两维度列 + `apply_assessment_levels`/`verify_assessment_levels`、`tests/test_assessment_report.py`（10 项）、`artifacts/m4d/`；测试 325→**335** | ① 报告组成完整（capability/dimensions/supports/gaps/reverse_evidence/excluded/rule_version；含 level/status/base_level/rationale/why_not_higher）；② 支持证据可回溯：claim 三元组 + 绑定理由 + 逐字引文（quote_verbatim 全 True）；③ 不含模型分值（JSON 扫描 + 渲染器源码 AST）；④ 反向证据与已排除分别成节（含裁决与未确认项）；⑤ 回填只经 `apply_assessment_levels`（legacy 列保持 NULL，upsert 写入即报错）；⑥ 重建校验可发现篡改；⑦ 无评级 → NULL/`unassessed`，草案不影响当前视图；⑧ audit_store pass/0、对锚一致、335 + ruff 全绿。细节见 `artifacts/m4d/README.md` | 命令输出；`artifacts/m4d/` | 90d |
| EV-071 | 2026-10-03 | **M4-e 实现与验证**：统一编排（rate → report → 回填 → 校验 → 缺口 → 校验，fail-stop）+ `g_gaps` + **真实 attack 运行**（独立实验库）+ **G2/G3 门证据**；离线 25/25、真实 23/23 | 离线 25/25；真实 23/23；回归 359 全绿 | 新增 `growth_os/assessment/pipeline.py`、`g_gaps` 派生/回填/校验、`tests/test_{gaps,assessment_pipeline,traceability}.py`（22 项）、`artifacts/m4e/`、`artifacts/gates/G2|G3/`；测试 335→**359** | **G3** 通过：独立实验库（真实目标树 + 真实对话摘录 + 标注构造笔记 + 真实仓库 `mytset-rag@c417a096`）；A（弱）理解 2 / 实践无 ≥2 等级 → B（强）实践 3（增强观测 ≥3）；C（JD）`domain_reference` 未进 supports；待验证声明被闸门拒。**真实 attack**：verifier（独立 `deepseek-flash`）复核 6 条主张 + adversarial 两轮（3+4 probe，全 sustained）；**17/17 HTTP**、零重试。**G2** 通过：7/7 评定行可追溯（5 条抽样、引文逐字、两条追溯路径）+ dossier 6 份 + `audit_store` pass/0。**g_gaps**：三档 severity 从评定行派生、唯一写路径（AST 守卫）、可发现篡改。**边界**：真实库对锚一致、`g_` 全空、实验库即删。**待确认**：预算口径调整；真实 HTTP 合计 ≈53（单次 ≤17）。细节见 `artifacts/m4e/README.md` | 命令输出；`artifacts/m4e/`、`artifacts/gates/G2|G3/` | 90d |
| EV-072 | 2026-10-03 | **M5 方案边界冻结（计划基线）**：范围做/不做确认 + 四条关键设计约束 + `docs/M5-PLAN.md` v1.0（执行基线） | 冻结（用户逐项确认） | `docs/M5-PLAN.md` v1.0 | 四条关键设计约束：① **Task 不是能力判断**（`gap → evidence opportunity`，不产出 `task → skill score`）；② **完成 ≠ 自动提升**（必须经 `submission → evidence → claim → binding gate → assessment`）；③ **provenance 可反查**（`task_id → submission → source_id → claim_id → assessment_id → level change`）；④ **M4 rating contract 不修改**。范围：`g_tasks` 契约 / `g_task_submissions` / 状态机 / generator（LLM 提议 + 确定性闸门）/ submission → evidence / claim binding / reassessment / G4 / G5；其余口径随计划冻结 | `docs/M5-PLAN.md`；`DECISIONS.md` | 长期（计划基线） |
| EV-073 | 2026-10-03 | **M5-a 实现与验证**：任务数据契约（`g_tasks` / `g_task_submissions` / `g_events`）+ 状态机 + Growth Agent 模式 A 四工具；离线冒烟 17/17 | 17/17；回归 380 全绿 | 新增 `agent/tools.py`、`growth_store` 任务三表与状态机、`tests/test_task_contract.py`（14 项）+ `tests/test_task_state_machine.py`（7 项）、`artifacts/m5a/`；测试 359→**380** | ① 冻结词表与转移表写死；② **`g_tasks` 无等级/分值字段**（AST 抽取建表语句断言，Task ≠ 能力判断）；③ 维度 ↔ 交付物（understanding 仅 probe_answer）与交付物 → 证据类型映射；④ 不可验收反例必须被拒（含字面"去学习 Agent Evaluation"）；⑤ 主缺口 open + 能力点 active + 同缺口去重；⑥ **`done` 唯一入口 = `complete_task`**（AST 守卫 + 需 active + 需 source）；⑦ 事件链按发生顺序（from/to/reason）；⑧ 工具层跨表族校验 source 存在性；⑨ **完成 ≠ 提升**：提交前后评定行完全一致、能力点等级未被触碰；⑩ 真实库对锚一致、`g_` 全空、实验库即删。细节见 `artifacts/m5a/README.md` | 命令输出；`artifacts/m5a/` | 90d |
| EV-074 | 2026-10-03 | **M5-b 实现与验证**：gap → task generator（LLM 提议 + 七步闸门 + 反例拒绝 + 全量留档）+ **G4 门证据**；离线 14/14、真实 14/14（真实运行 **2/2 HTTP**，零额外重试） | 离线 14/14；真实 14/14；回归 404 全绿 | 新增 `growth_os/tasks/{gate,generator}.py`、`tests/test_task_generator.py`（24 项）、`artifacts/m5b/`、`artifacts/gates/G4/`；测试 380→**404** | ① 七步闸门固定顺序（缺口存在/open/active 合并为 `gap_taskable`，并强制 `assessment_id` 保证 provenance）；② proposal schema 七字段 `extra=forbid`，能力判断与排序字段结构性拒绝（静态检查只允许出现在 `FORBIDDEN_TASK_FIELDS`）；③ `est_minutes` 只做形式夹取、闸门不改写文本；④ `declined` 是运行结果不落库；⑤ Generator 不直接写库（唯一写库在闸门第 7 步；行数==accepted 数）；⑥ duplicate 谓词（done/abandoned 可再来）；⑦ 真实提议：理解缺口→probe 现场问答、实践缺口→可运行最小 RAG 系统（两条全过闸门）；⑧ G4：映射完整 / 四要素齐备 / 4 条反例（含字面"去学习 Agent Evaluation"）全部被拒 / provenance 可反查 / 禁止字段零命中；⑨ 真实库对锚一致、`g_` 全空、实验库即删。细节见 `artifacts/m5b/README.md` | 命令输出；`artifacts/m5b/`、`artifacts/gates/G4/` | 90d |
| EV-075 | 2026-10-03 | **M5-c 实现与验证**：任务提交闭环 —— 唯一入口 `TaskLoop.complete_task` + 单入口证据 + 材料 claim + 绑定闸门 + M4-e 重评 + 归因/三联条件守卫；离线 38/38、真实 12/12（真实运行 **1/1 HTTP**，零额外重试） | 离线 38/38；真实 12/12；回归 416 全绿 | 新增 `growth_os/assessment/task_loop.py`、`tests/test_task_loop.py`（11 项）+ `tests/test_growth_loop.py`、`artifacts/m5c/`；测试 404→**416** | 唯一入口 `TaskLoop.complete_task`（`source_id` 不入调用契约）；done 在链尾、失败留 active 可幂等重跑；单入口入库四类交付物（归属/通道写死；archive 主条目确定性选取）；材料 claim 确定性（零 LLM、越权前置、一条、幂等）；绑定 ≤1 HTTP + 后置条件（`binding_missed` 不写 assessment、不报提升）；重评只经 M4-e 编排；三态 + 三联条件守卫（缺一即 `LoopGuardError`）+ 下降守卫 + AST 禁写；归因 `m5c-1`（不新增表/事件）+ 只读 `trace_task`；真实 `glm-5.3` 1/1 HTTP：实践 **3 → 4**、`level_gap_1` 关闭、理解保持、guard 全 true、全链可反查；真实库对锚、`g_` 全空。细节见 `artifacts/m5c/README.md` | 命令输出；`artifacts/m5c/` | 90d |
| EV-076 | 2026-10-04 | **M5-d：G5 真实成长闭环 + M5 Gate 封板** | G5 11/11；M5 Gate 13/13；pytest 416；ruff 通过 | `artifacts/g5/`、`artifacts/gates/G5/`、`artifacts/gates/M5/` | 单命令完成 gap → 真实任务生成 → 提交 → 新证据 → 重评：实践 **3 → 4**，实践缺口关闭，理解缺口保持 open；2/3 HTTP、零重试；归因与 `trace_task` 全链可反查；`audit_store=pass/0`；真实库对锚、`g_` 全空。M5 Gate：完成条件 1–5 + QG1–QG5 + 数据边界 13/13。提交物与种子材料为受控构造并标注。 | 命令输出；`artifacts/gates/G5/`、`artifacts/gates/M5/` | 90d |
| EV-077 | 2026-10-04 | **M6 冻结范围验证**：契约、可重建投影、任务上下文 | pytest 423；ruff 通过 | `357a7f1`、`6c20033`、`13eec06` | 唯一写入与来源审计；state/history 删除后可由同一来源重建；confirmed memory 进入任务提示并保留 provenance；无记忆与有记忆 objective 差异可解释；七步闸门不变。自动演化、遗忘、冲突处理和权重不在范围内。 | 测试输出 | 90d |
| EV-078 | 2026-10-04 | **M7-a 主动事件检测** | pytest 425；ruff 通过 | `6a5f470` | 四类确定性事件；无变化不通知；7 天冷却；关闭提醒后检测仍运行但不写通知。分析不修改能力、目标或任务。 | 测试输出 | 90d |
| EV-079 | 2026-10-04 | **M7-b 每日调度** | pytest 426；ruff 通过 | `f7de6b0` | 可注入 UTC 时钟；同一用户同一自然日返回已有结果；失败写 `proactive_run_failed` 后停止，不重试、不伪成功。通知仍只写本地表。 | 测试输出 | 90d |
| EV-080 | 2026-10-04 | **M7-c 运行审计与离线复核** | 离线 5/5；pytest 426；ruff 通过 | `517b391` | 调度审计包含日期、状态、事件、通知 ID 和错误；同日复用原审计。前四项通过；目标变化后的自动重建明确未实现。 | `artifacts/m7/result.json` | 90d |

## Gate 记录

| Gate ID | 日期 | Gate | 对象 | 结果 | 证据 ID | 豁免与确认人 |
| M5（方案冻结） | 2026-10-03 | M5 边界冻结（四条关键设计约束 + 做/不做 + 步骤 M5-a…d + Gate + G4/G5 判定口径 + 运行预算） | `docs/M5-PLAN.md` v1.0 | 通过（用户已确认） | EV-072 | 用户 |
| M5-a | 2026-10-03 | 任务数据契约 + 状态机 + 工具注册（三表 / 冻结词表 / `done` 唯一入口 / 模式 A 四工具；离线，不调用模型） | `backend/growth_os/agent/tools.py`、`growth_store` 任务三表、`tests/test_task_{contract,state_machine}.py`、`artifacts/m5a/` | 通过（用户已确认） | EV-073 | 用户 |
| G5 | 2026-10-04 | **成长闭环门**：gap → 任务 → 提交 → 新证据 → 重评 → 实践 3→4（单命令，2/3 HTTP） | `artifacts/gates/G5/` | 通过 | EV-076 | — |
| M5 Gate | 2026-10-04 | **任务闭环完成条件 + QG1–QG5 + 数据边界**（13/13；离线，不调用模型） | `artifacts/gates/M5/` | 通过（用户已确认） | EV-076 | 用户 |
| M5-c | 2026-10-03 | 任务提交闭环（唯一入口 `TaskLoop` + 单入口证据 + 材料 claim + 绑定闸门 + M4-e 重评 + 归因/三联条件守卫；离线 38/38 + 真实 12/12） | `growth_os/assessment/task_loop.py`、`growth_os/agent/tools.py`、`tests/test_task_loop.py`、`tests/test_growth_loop.py`、`artifacts/m5c/` | 通过（用户已确认） | EV-075 | 用户 |
| M5-b | 2026-10-03 | gap → task generator（LLM 提议 + 七步闸门 + 反例拒绝 + 全量留档）+ G4 门证据（真实运行 ≤2 HTTP） | `growth_os/tasks/{gate,generator}.py`、`tests/test_task_generator.py`、`artifacts/m5b/`、`artifacts/gates/G4/` | 通过（用户已确认；G4 判定通过） | EV-074 | 用户（批准真实运行 ≤2 HTTP） |
| M4 Gate | 2026-10-03 | **能力审计完成条件 1–6 + 质量门 QG1–QG5 + 数据边界**（21/21；离线，不调用模型；真实库副本新鲜复核） | `artifacts/gates/M4/` | 通过 | EV-071 | 用户（M4 封板确认） |
| M4-e | 2026-10-03 | 统一编排 + 缺口 `g_gaps` + 真实 attack 运行 + G2/G3 门证据（独立实验库；真实运行 ≤17 HTTP） | `growth_os/assessment/pipeline.py`、`g_gaps`、`tests/test_{gaps,assessment_pipeline,traceability}.py`、`artifacts/m4e/`、`artifacts/gates/G2|G3/` | 通过（用户已确认） | EV-071 | 用户（含预算口径与成本披露确认） |
| G2 | 2026-10-03 | **证据可追溯性门**：抽 5 条 assessment 逐跳（assessment → claim → evidence → passage → source）+ 引文逐字 | `artifacts/gates/G2/` | 通过 | EV-071 | — |
| G3 | 2026-10-03 | **能力审计门**：A/B 对照（弱证据 → 理解 2 / 实践无 ≥2 等级；强证据 → 实践 3）+ C 负对照（JD 不进 supports） | `artifacts/gates/G3/` | 通过 | EV-071 | — |
| M4-d | 2026-10-03 | 可解释输出 + `current_level` 回填（报告 + 重建校验；离线，不调用模型） | `growth_os/assessment/report.py`；`artifacts/m4d/` | 通过（用户已确认） | EV-070 | 用户 |
| M4-c | 2026-10-03 | 评级与反向证据（星级规则引擎 + attack 结算 + `rated` 写入路径；离线，不调用模型） | `growth_os/assessment/{rules,rater}.py`；`artifacts/m4c/` | 通过（用户已确认） | EV-069 | 用户 |
| M4-b | 2026-10-03 | 证据绑定与分桶（LLM 提议 + 八步确定性闸门 + 映射落库；含 1 次真实模型运行） | `growth_os/assessment/{buckets,binding}.py`；`artifacts/m4b/` | 通过（用户已确认） | EV-068 | 用户（批准真实运行） |
| M4-a | 2026-10-02 | Assessment 基础模型与 provenance 前置（契约 + 最小闭环 + 独立 audit artifact） | `growth_os/assessment/`；evkg @ `9a21552` | 通过（用户已确认） | EV-067 | 用户 |
| M4 | 2026-10-02 | 计划基线冻结（七项确认，v1.0 执行基线） | `docs/M4-PLAN.md` | 通过 | EV-066 | 用户 |
| M3-e | 2026-10-02 | 材料口径 claim + audit + provenance（越权校验接线；历史主张只读标记） | `adapter.create_material_claim` | 通过 | EV-064 | — |
| M3 Gate | 2026-10-02 | **证据接入完成条件 1–5 + 质量门**（PDF/Markdown 可检索、ZIP、公共仓库、无授权与密钥、JD 隔离） | `artifacts/gates/M3/` | 通过 | EV-065 | 用户 |
| M3-d | 2026-10-02 | 外部参考通道（JD / domain_reference；通道结构锁定 + 抽取只读） | `growth_os/evidence/reference.py` | 通过 | EV-063 | — |
| M3-c | 2026-10-02 | GitHub 公共仓库接入（浅克隆、无凭据、无 OAuth；归属/通道贯穿） | `growth_os/evidence/github.py` | 通过 | EV-062 | — |
| B-g2 | 2026-10-02 | PDF spike 重跑（上游 `db2de3a` 最小修复后三项验证） | evkg @ `db2de3a` | 通过（含明确边界） | EV-061 | 用户（批准选项 A） |
| B-g2 | 2026-10-02 | PDF spike（三项验证 + 缺陷定位；未修改 evkg） | `artifacts/bg2/` | 不通过（现状）/ 缺口为 1 行缺陷 | EV-060 | 用户（是否提交上游修复待定） |
| M3-b | 2026-10-02 | 本地材料 ingestion（含 ZIP 容器级封装；复用单入口、无旁路） | `growth_os/evidence/archive.py` | 通过 | EV-059 | — |
| M3-a | 2026-10-02 | 归属层与越权校验（三取值 + 消费规则 + "存在证据 ≠ 证明能力"） | `growth_os/evidence/{attribution,claims}.py` | 通过 | EV-058 | — |
| M2 | 2026-10-02 | **M2 验收（AC1–AC12 + ROADMAP 完成条件）** | `docs/M2-PLAN.md` v1.0 | 通过 | EV-057 | — |
| G1 | 2026-10-02 | **Goal Clarification（真实模型会话，含两条反例）** | `artifacts/gates/G1/` | 通过 | EV-056 | 用户（截图豁免） |
| M2-d 预备 | 2026-10-02 | 演练脚本修复 + 两层预算（应用层 ≤8 / 传输层 HTTP ≤8 + 零额外重试 + 失败即停留档） | `tests/goal_flow_fixtures.py`、`tests/test_http_budget.py`、`artifacts/m2/` | 通过（离线） | EV-054 EV-055 | — |
| M2-c | 2026-10-02 | 能力树生成（≥3 领域/≥12 能力点/≤3 层）+ 调整保护 + 未校验标注 | `growth_os/goal/capability_model.py` | 通过 | EV-053 | — |
| M2-b | 2026-10-02 | Goal Agent 与澄清状态机（≤6 轮硬上限、显式确认、未确认拒绝能力分析） | `growth_os/goal/agent.py` | 通过 | EV-052 | — |
| M2-a | 2026-10-02 | `g_` 表族 + 最小运行时 + 网关接缝 + 边界守卫收窄（含 3 项补偿检查） | `growth_os/{store,agent}` | 通过 | EV-051 | — |
| M2 | 2026-10-02 | 计划基线冻结（5 项决策 + C1–C3 + 开工前 4 项检查） | `docs/M2-PLAN.md` | 通过 | EV-050 | 用户 |
| B-g1 | 2026-10-02 | **evkg 依赖交付**：bundle 归档 + 双副本 + 恢复验证（用户确认方案 A） | evkg @ `28afbc0` | 通过 | EV-048 EV-049 | 用户（已确认方案 A） |
| M1-g | 2026-10-02 | M1 完成条件补跑：`reindex`（FTS5 索引 + 检索）在真实材料上产出实际输出 | `data/growth.db` 副本 | 通过 | EV-047 | — |
| M1-g | 2026-10-02 | R3 覆盖实测与盲区界定（含 LLM 路径无自动化测试） | `backend/growth_os/` | 通过（结论含限制） | EV-046 | — |
| M1-g | 2026-10-02 | **R1–R4/D1 收口 + 依赖策略判定** | `docs/M1-SPIKE-CONCLUSION.md` | 通过（判定：有条件依赖 C1–C5） | EV-042…EV-046 | 用户（待确认收口） |
| M1-g | 2026-10-02 | R2 上游缺陷复现（partial 渲染 / 抽取模型名 / caught 截断） | evkg @ `28afbc0` | 复现成立（已列入上游清单） | EV-045 | — |
| M1-g | 2026-10-02 | R4 实库审计 + 证据链逐字核验 | `data/growth.db` | 通过 | EV-044 | — |
| M1-g | 2026-10-02 | **D1 进程级全局 profile 实测**（双实例污染、并发交错、公开 API 隔离、适配层 footgun） | `evkg.config` | 通过（实测，结论见结论文档 §5.3） | EV-043 | — |
| M1-g | 2026-10-02 | 全量回归独立复跑（evkg 101 正/逆序、Growth OS 73） | 两个仓库 | 通过 | EV-042 | — |
| M1-f | 2026-10-01 | 真实库未被触碰 + 全量回归 | `data/growth.db` | 通过 | EV-040 | — |
| M1-f | 2026-10-01 | 自报与独立测量交叉印证 | 副本库 | 通过 | EV-039 | — |
| M1-f | 2026-10-01 | 检测行为被测试固化（10 项，含内容级） | `tests/test_damage_selftest.py` | 通过 | EV-038 | — |
| M1-f | 2026-10-01 | 伪造数据可被发现 + 清理可恢复（3 场景） | `artifacts/m1f/` | 通过 | EV-037 | — |
| M1-e | 2026-10-01 | 已提交档案与真实库一致 | `data/growth.db` | 通过 | EV-036 | — |
| M1-e | 2026-10-01 | **partial 复核证据不被漏掉** | `dossier.py` | 通过 | EV-035 | — |
| M1-e | 2026-10-01 | 档案 ↔ 数据库 ↔ M1-d 留档一致性（35/35） | `artifacts/m1e/` | 通过 | EV-034 | — |
| M1-e | 2026-10-01 | 档案渲染行为（22 项，含 partial 回归） | `tests/test_dossier.py` | 通过 | EV-033 | — |
| M1-d | 2026-10-01 | **越权主张被推翻 + 正确主张被保住** | 2 条主张 | 通过 | EV-032 | — |
| M1-d | 2026-10-01 | 攻击样例留档 | `artifacts/m1d/` | 通过 | EV-031 | — |
| M1-d | 2026-10-01 | 攻击运行完整、无模块级错误、库自洽 | 5 个模块 | 通过 | EV-030 | — |
| M1-d | 2026-10-01 | 独立复核**真正生效**（非仅设变量） | GLM vs DeepSeek | 通过 | EV-029 | — |
| M1-c | 2026-10-01 | **「严禁升级」**（计划 ≠ 具备）+ 证据链逐字可回溯 | 2 条主张 | 通过 | EV-028 | — |
| M1-c | 2026-10-01 | 全量抽取完成且库自洽 | `data/growth.db` | 通过 | EV-027 | — |
| M1-c | 2026-10-01 | 抽取不越权（项目描述不产生个人能力断言） | 12 条试跑 | 通过 | EV-026 | — |
| M1-c | 2026-10-01 | 模型可用（探针通过，含两处配置修正） | `glm-5.3` @ open.bigmodel.cn | 通过 | EV-025 | — |
| M1-b.5d | 2026-10-01 | source 身份稳定 + 检索走公共 API | `data/growth.db` | 通过 | EV-024 | — |
| M1-b.5d | 2026-10-01 | 删补丁后既有写入语义与下游未破 | 回归脚本 | 通过 | EV-023 | — |
| M1-b.5d | 2026-10-01 | **适配层边界**：无裸 SQL / 无自造路由 / 无私有辅助 | `adapter.py` | 通过 | EV-022 | — |
| M1-b.5d | 2026-10-01 | evkg 公共入口补齐（101 项全绿） | `../evkg` @ `28afbc0` | 通过 | EV-021 | — |
| M1-b.5c | 2026-10-01 | source 身份稳定 + 库自洽 | `data/growth.db` | 通过 | EV-020 | — |
| M1-b.5c | 2026-10-01 | 下游消费者与冒烟未破 | adapter + 6 消费者 | 通过 | EV-019 | — |
| M1-b.5c | 2026-10-01 | A→B 核心性质（真实材料端到端） | `RagService.java` 副本 | 通过 | EV-018 | — |
| M1-b.5c | 2026-10-01 | 逻辑身份 + content_hash + 显式 upsert（93 项全绿） | `../evkg` @ `068389d` | 通过 | EV-017 | — |
| M1-b.5b | 2026-10-01 | 旧数据未被错误升级 | `data/growth.db` | 通过 | EV-016 | — |
| M1-b.5b | 2026-10-01 | 下游消费者在 `score=None` 下不崩 | 6 个消费者 | 通过 | EV-015 | — |
| M1-b.5b | 2026-10-01 | 缺失值语义（`UNASSESSED` 双向设防，已评估数值逐位不变） | `../evkg` @ `e432c42` | 通过 | EV-013 EV-014 | — |
| M1-b.5a | 2026-10-01 | locator 可回磁盘核对（零说谎）+ 切分质量 | `RagService.java` | 通过 | EV-012 | — |
| M1-b.5a | 2026-10-01 | 旧数据未被错误升级（升级 evkg 后零变更） | `data/growth.db` | 通过 | EV-011 | — |
| M1-b.5a | 2026-10-01 | 适配层改走 evkg 原生代码路径且评分中性 | `adapter.py` | 通过 | EV-010 | — |
| M1-b.5a | 2026-10-01 | evkg 源码一等支持（61 项测试全绿、lint 无新增） | `../evkg` @ `a4b15af` | 通过 | EV-009 | — |
| QG1 | 2026-10-01 | 证据不变量（M1-b 范围首跑） | `data/growth.db` | 通过 | EV-008 | — |
| M1-b | 2026-10-01 | 真实材料入库可用（含代码路由） | `mytset-rag` 3 文件 | 通过 | EV-007 | — |
| M1-b | 2026-10-01 | 双轨记录成立（成长标签与 evkg assessment 共存） | `adapter.py` | 通过 | EV-006 | — |
| M1-a | 2026-10-01 | evkg path 依赖可解析 | `pyproject.toml` | 通过 | EV-005 | — |
| M1-a | 2026-10-01 | 成长领域包实际生效（非仅可加载） | `growth_os.yaml` | 通过 | EV-004 | — |
| A-003 | 2026-10-01 | 选型确认 | Q1–Q4 | 通过 | EV-003 | 用户 |
| A-002 | 2026-10-01 | 文档索引一致性 | `docs/` | 通过 | EV-002 | — |
| A-001 | 2026-10-01 | 治理账本合法性 | `.project-to-act/` | 通过 | EV-001 | — |
|---|---|---|---|---|---|---|

### M4 总验收索引（封板）

> M4 已全部完成并封板（2026-10-03）。治理闭环：Evidence → Binding → Assessment → Explanation →
> Current View → Gap Detection → Audit / Gate Evidence。详细判定见 `artifacts/gates/M4/README.md`。

| 步骤 / 门 | 内容 | 结果 | 证据 |
|---|---|---|---|
| M4-PLAN v1.0 | 七项冻结（G2/G3 判定、三层归属不合并、history + current view、C5 上游最小修、LLM 提议 + 确定性闸门、G3 实验设计、交付物口径） | 冻结 | EV-066 |
| M4-a | Assessment 契约 + C5 provenance（evkg `9a21552`）+ 最小闭环（11/11） | 通过 | EV-067 |
| M4-b | 证据绑定与分桶（LLM 提议 + 八步确定性闸门；离线 9/9 + 真实 8/8） | 通过 | EV-068 |
| M4-c | 两维度星级规则引擎 + attack 结算 + `rated` 写入路径（离线 12/12） | 通过 | EV-069 |
| M4-d | 能力解释报告 + `current_level` 维度化回填与重建校验（离线 15/15） | 通过 | EV-070 |
| M4-e | 统一编排（fail-stop）+ `g_gaps` + 真实 attack（17/17 HTTP）+ G2/G3 证据（离线 25/25、真实 23/23） | 通过 | EV-071 |
| G2 | 证据可追溯性门：7/7 逐跳（5 条抽样、引文逐字）+ dossier 6 份 + `audit_store` pass/0 | 通过 | EV-071 |
| G3 | 能力审计门：A（理解 2 / 实践无 ≥2 等级）→ B（实践 3；增强观测 ≥3）；C 不进 supports | 通过 | EV-071 |
| QG1–QG5 | 证据不变量 / 攻击自测（双向测量）/ 规则覆盖 / 无密钥 / 全量测试（359 + 111 + ruff） | 通过 | `m4-gate-result.json` |
| M4 Gate | 完成条件 1–6 + 质量门 + 数据边界（21/21、真实库对锚、`g_` 全空） | 通过 | 判定记录 + EV-071 |

## 验收记录

| 日期 | 检查范围 | 证据 ID | 结果 | 遗留问题 | 结论 |
| 2026-10-03 | M5 方案边界冻结（范围 + 四条设计约束 + 执行基线 v1.0） | EV-072 | 通过（用户已确认） | M5-a（数据契约 + 状态机 + 工具注册）开工；M5-b…d + M5 Gate 待推进 | **M5 开工条件成立，`M5-PLAN.md` v1.0 生效** |
| 2026-10-03 | M5-a（数据契约 + 状态机 + 工具注册） | EV-073 | 通过（用户已确认） | M5-b 边界提议提交中；生成器 / 闭环 / G4-G5 未开始；两项 M5-b 约束已登记（生成器不得引入能力判断字段；任务质量 ≠ 学习价值） | **M5-a 验收通过** |
| 2026-10-04 | G5 + M5 Gate（任务闭环封板） | EV-076 | 通过（用户已确认） | 实践 3→4；归因可反查；M5 Gate 13/13；真实库对锚、`g_` 全空；允许进入 M6 | **M5 验收通过** |
| 2026-10-04 | M6（契约、投影、任务上下文） | EV-077 | 通过（用户已确认） | G6 的隔天 Agent 回答留 M7/M8；长期演化不纳入 M6 | **M6 封板通过** |
| 2026-10-04 | M7-a（主动事件检测） | EV-078 | 通过（用户已确认） | 调度、通知投递和能力模型重生成留 M7-b 边界 | **M7-a 验收通过** |
| 2026-10-04 | M7-b（每日调度与失败即停） | EV-079 | 通过（用户已确认） | 外部通知、UI 和目标变化后的自动重建不在 M7-b | **M7-b 验收通过** |
| 2026-10-04 | M7-c（运行审计与离线复核） | EV-080 | 通过（用户已确认） | 自动重建、外部通知、UI、Memory 和主动 Agent 继续冻结 | **M7-c 验收通过** |
| 2026-10-03 | M5-c（提交 → 重评闭环 + 归因） | EV-075 | 通过（用户已确认） | 真实运行 1/1 HTTP：实践 3→4、`level_gap_1` 关闭、guard 全 true、全链可反查；允许进入 M5-d（G5 + M5 Gate） | **M5-c 验收通过** |
| 2026-10-03 | M5-b（gap → task generator + G4） | EV-074 | 通过（用户已确认） | 真实运行 2/2 HTTP；G4 判定通过；确认两处实现记录（`get_gap` 只读 getter 保留；`M5-PLAN` §4/§9/§12 已同步）；登记 M5-c 前置约束（完成 ≠ 直接升星；能力变化须同时具备 before assessment + 新证据 provenance + after assessment）；M5-c 方案边界已提交、待确认后开工；M5-d（G5 + M5 Gate）待推进 | **M5-b 验收通过；G4 通过** |
| 2026-10-03 | M4-e 验收 + **M4 Gate 封板**（完成条件 1–6 + QG1–QG5 + 数据边界，21/21） | EV-071 | 通过 | 两项设计记录确认（单次运行预算口径、多次运行成本披露）；M4 保留边界：真实库不含 `g_` 表、G3 主体为 RAG 能力、A 臂笔记受控构造；下一步 M5 待用户确认 | **M4 正式收口；G2 / G3 通过** |
| 2026-10-03 | M4-d（可解释输出 + `current_level` 回填与重建校验） | EV-070 | 通过（用户已确认） | 缺口表（`g_gaps`）、真实 attack 运行与 G2/G3（M4-e）未开始；统一编排（回填自动化）留 M4-e | **M4-d 阶段检查通过** |
| 2026-10-03 | M4-c（评级与反向证据：规则引擎 + attack 结算 + rated 写入路径） | EV-069 | 通过（用户已确认） | `current_level` 回填（M4-d）、真实 attack 运行与 G3（M4-e）未开始 | **M4-c 验收通过** |
| 2026-10-03 | M4-b（证据绑定与分桶：LLM 提议 + 确定性闸门 + 映射落库） | EV-068 | 通过（用户已确认） | 星级算法 / 攻击与反向证据（M4-c）未开始；生成器接线按用户决定推迟（`M4-b.1`） | **M4-b 验收通过** |
| 2026-10-02 | M4-a（Assessment 基础模型与 provenance 前置） | EV-067 | 通过（用户已确认） | 星级算法 / LLM / UI / G3 未开始（按边界）；M4-b（证据绑定与分桶）待推进 | **M4-a 验收通过** |
| 2026-10-02 | M4 计划基线冻结（七项确认） | EV-066 | 通过 | 三项冻结点 + C5 / 映射闸门 / G3 实验 / 交付物 2 全部定案；实施随 M4-a…e | **M4 开工条件成立，`M4-PLAN.md` v1.0 生效** |
| 2026-10-02 | M3-e（Claim + audit + provenance） | EV-064 | 通过 | 仅剩 **M3 Gate**（含 PDF/Markdown 可检索性、证据链逐项核对）；历史主张是否就地标注待用户决定 | **M3-e 阶段检查通过** |
| 2026-10-02 | **M3 Gate（证据接入）** | EV-065 | 通过 | 边界保留：PDF 适配层 V1 入口未建、页码级 locator 仍缺；M4 待确认 | **M3 正式收口** |
| 2026-10-02 | M3-d（JD / domain_reference） | EV-063 | 通过 | capability claim 留 M3-e；M3-e（Claim + audit + provenance）待推进 | **M3-d 阶段检查通过** |
| 2026-10-02 | M3-c（GitHub 公共仓库接入） | EV-062 | 通过 | ≥3 条 capability claim 与可检索性留 M3-e / Gate；M3-d（JD）待推进 | **M3-c 阶段检查通过** |
| 2026-10-02 | B-g2 重跑（PDF，上游修复后） | EV-061 | 通过（含边界） | 页码级 locator 为独立开放项；PDF 接入产品需适配层 V1 入口（后续步骤） | **B-g2 通过；PDF 基础 ingestion 可用（边界见 M3-PLAN §5）** |
| 2026-10-02 | B-g2（PDF spike） | EV-060 | 不通过（现状） | 待用户决定：提交 1 行上游修复后重跑，或维持 PDF 不支持；页码级 locator 为独立上游项 | **B-g2 验证完成，结论待用户决策** |
| 2026-10-02 | M3-b（本地材料 MD/TXT/代码/ZIP） | EV-059 | 通过 | B-g2（PDF spike）与 M3-c 待推进；越权接线与历史主张仍留 M3-e | **M3-b 阶段检查通过** |
| 2026-10-02 | M3-a（归属层与越权校验） | EV-058 | 通过 | M3-b 待推进；接线到写入路径留 M3-e（用户明确不提前处理历史问题） | **M3-a 阶段检查通过** |
| 2026-10-02 | **M2 验收（AC1–AC12 + 回归 + 数据边界）** | EV-057 | 通过 | 再生成"并集"语义待 M4 前决策；归档第三副本待用户另存 | **M2 正式收口** |
| 2026-10-02 | M2-d（G1 真实会话端到端） | EV-056 | 通过 | 无 | **G1 通过（截图豁免，M8 补证）** |
| 2026-10-02 | M2-d 预备（脚本修复 + 两层预算与失败留档） | EV-054 EV-055 | 通过（离线） | 真实会话仍未执行：需用户再次授权；两层上限 = 应用层 8 次结构化调用 / HTTP 8 个请求（零额外重试） | **准备就绪，等待真实调用授权** |
| 2026-10-02 | M2-c（能力树生成、调整保护、来源与校验标注） | EV-053 | 通过 | **M2-d（G1 真实会话）未开始，真实模型调用需用户明确授权**（预估 5 次结构化调用） | **M2-c 阶段检查通过** |
| 2026-10-02 | M2-b（澄清状态机与三条硬约束） | EV-052 | 通过 | M2-c 待推进 | **M2-b 阶段检查通过** |
| 2026-10-02 | M2-a（g_ 表族、最小运行时、网关接缝、边界守卫收窄） | EV-051 | 通过 | M2-b…d 待推进 | **M2-a 阶段检查通过** |
| 2026-10-02 | M2 计划基线冻结（决策 / 约束 / 开工前检查） | EV-050 | 通过 | 4 项检查为设计级，须在 M2-a…d 转为可执行断言 | **M2 开工条件成立，`M2-PLAN.md` v1.0 生效** |
| 2026-10-02 | B-g1（evkg 交付：方案 A 本地 bundle 归档） | EV-048 EV-049 | 通过 | 第二副本与主副本可能同物理盘，抗物理损坏的异地/离线副本待用户另存（未计入验收）；发布/CI 前切换 `git + rev` pin | **B-g1 已解除（交付形式落定并验证）；M1 正式归档** |
| 2026-10-02 | M1-g（技术 spike 收口：R1–R4 + D1 依赖边界） | EV-042 EV-043 EV-044 EV-045 EV-046 EV-047 | 通过 | 阻塞：B-g1（evkg 依赖 pin/可获取）、B-g2（M3 富格式路径未验证）；延后：实例级 profile、抽取模型持久化（M4 前）、渲染器 partial、caught 判定等（见结论文档 §9） | **M1-g 验收通过；M1 技术 spike 结束，依赖策略 = 有条件依赖（C1–C5）** |
| 2026-10-01 | M1-f（damage selftest：伪造数据发现与恢复） | EV-037 EV-038 EV-039 EV-040 | 通过 | 上游两项建议（partial 渲染、caught 样本截断） | **M1-f 验收通过** |
| 2026-10-01 | M1-e（dossier：能力证据档案） | EV-033 EV-034 EV-035 EV-036 | 通过 | 归属层待 M2/M4 决策；抽取模型未入库 | **M1-e 验收通过** |
| 2026-10-01 | M1-d（attack：独立复核 + 对抗攻击） | EV-029 EV-030 EV-031 EV-032 | 通过 | 归属层待 M2/M4 决策 | **M1-d 验收通过（独立复核，结果可用）** |
| 2026-10-01 | M1-c（extract：证据 → 能力断言） | EV-025 EV-026 EV-027 EV-028 | 通过 | 归属层待 M2/M4 决策；独立 verifier 未配置 | **M1-c 验收通过** |
| 2026-10-01 | M1-b.5d（适配层边界、公共 API 补齐） | EV-021 EV-022 EV-023 EV-024 | 通过 | — | **M1-b.5d 验收通过；M1 的 a/b/c 三层闭环** |
| 2026-10-01 | M1-b.5c（逻辑身份、content_hash、显式 upsert、级联替换） | EV-017 EV-018 EV-019 EV-020 | 通过 | symbol 级精度待解析器；evkg 不得推送远程 | **M1-b.5c 验收通过** |
| 2026-10-01 | M1-b.5b（缺失值语义、下游消费者、旧数据不变性） | EV-013 EV-014 EV-015 EV-016 | 通过 | — | **M1-b.5b 验收通过** |
| 2026-10-01 | M1-b.5a（evkg 源码一等支持、适配层变薄、旧数据不变性） | EV-009 EV-010 EV-011 EV-012 | 通过 | symbol 级精度待解析器；跨切分器累积问题待 b.5c | **M1-b.5a 验收通过** |
| 2026-10-01 | M1-b（入库、双轨记录、QG1） | EV-006 EV-007 EV-008 | 通过 | M1-c 起需 LLM API Key | **M1-b 验收通过** |
| 2026-10-01 | M1-a（领域包生效、依赖解析） | EV-004 EV-005 | 通过 | R1/R2/R4 待后续小步 | **M1-a 验收通过** |
| 2026-10-01 | M0 收口（账本/索引/选型） | EV-001 EV-002 EV-003 | 通过 | G1–G6、QG1–QG5 全部未开始 | **M0 验收通过**，M1 可开工 |
|---|---|---|---|---|---|

验收方式说明、证据格式与证据链自举机制见 `docs/ACCEPTANCE_GATES.md`（§1 原则、§2 自举机制、§5 记录格式）。约束：验收证据库 `data/acceptance.db` 与用户证据库物理隔离，项目验收证据不得进入用户能力断言通道，否则会污染 G3 的判定。
