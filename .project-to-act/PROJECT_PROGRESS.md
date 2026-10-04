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
| M2 | 目标澄清与能力模型 | **已完成（2026-10-02 收口）** | ZCode | AC1–AC12 全部满足 + ROADMAP 完成条件 5/5 + G1 通过（含反例） | EV-050…EV-057 | 2026-10-02 |
| M2-a | `g_` 四表 + `growth_store` + 最小运行时（含网关接缝/fake）+ 边界守卫收窄与补偿检查 | 已完成 | ZCode | 测试 97 项全绿（新增 24）；AC7/AC8/AC12 通过；真实库零改动（QG1 pass/0） | EV-051 | 2026-10-02 |
| M2-b | Goal Agent + 澄清状态机（≤6 轮硬上限、显式确认、未确认拒绝能力分析） | 已完成 | ZCode | 8 项新测试；第 7 轮被拒且未发模型、确认需原话、增量累积不被擦除 | EV-052 | 2026-10-02 |
| M2-c | 能力树生成 + 形状校验（≥3 领域/≥12 能力点/≤3 层）+ 调整保护 + 来源与校验标注 | 已完成 | ZCode | 11 项新测试 + 离线端到端演练 11/11；测试总数 116 全绿；不写半棵树 | EV-053 | 2026-10-02 |
| M2-d | G1 证据产出（真实模型会话） | **已完成** | ZCode | 尝试 6 端到端通过（13/13 自检、6 次调用、真实库未变）；G1 判定与截图豁免记录已产出 | EV-056 EV-057 | 2026-10-02 |
| M3 | 证据接入（Evidence Ingestion） | **已完成（2026-10-02 收口，Gate 通过）** | ZCode | 完成条件 1–5 + 质量门 13/13；`artifacts/gates/M3/` | EV-058…**EV-065** | 2026-10-02 |
| M3-a | Evidence 基础模型与归属层（三取值 + 消费规则 + 越权校验） | 已完成 | ZCode | 新增 44 项测试（归属 24 / 越权 20）；全量 187 项全绿；逐表内容哈希与 M1-g 基线一致 | EV-058 | 2026-10-02 |
| M3-b | 本地材料 ingestion（MD/TXT/代码/ZIP；ZIP 为容器级封装，逐条目走单入口） | 已完成 | ZCode | 新增 35 项测试；全量 222 项全绿；归属/通道贯穿 + 无旁路断言；真实库逐表哈希与计数对基一致 | EV-059 | 2026-10-02 |
| B-g2 | PDF spike（独立验证：入库 / audit / locator 可核对性） | **已完成（通过，含明确边界）** | ZCode | 上游一行修复（evkg `db2de3a`）+ 6 项真实读取测试；重跑入库 40 段、audit pass/0、两轮交叉印证一致 | EV-060 EV-061 | 2026-10-02 |
| M3-c | GitHub 公共仓库接入（浅克隆；逐文件走单入口；技术栈清单） | 已完成 | ZCode | 真实公共仓库 20 文件入库 / 179 段 / audit pass-0 / 幂等 / 归属通道贯穿；新增 21 项离线测试 | EV-062 | 2026-10-02 |
| M3-d | 外部参考通道（JD / domain_reference；通道锁定 + 抽取只读） | 已完成 | ZCode | 8 项边界检查全过（含不能支撑用户断言、user_evidence 为空、claims=0）；27 个技术词带 passage 证据 | EV-063 | 2026-10-02 |
| M3-e | 材料口径 claim + audit + provenance（越权校验接线；历史主张只读 dry-run） | 已完成 | ZCode | 5 条材料口径 claim、audit pass-0、provenance 可走通、越权闸门零写入；顺带修掉校验器否定语境假阳性 | EV-064 | 2026-10-02 |
| M4 | 能力审计（产品内核：assessment / 证据充分性 / 星级） | **已完成并封板（M4-a…M4-e 已验收；M4 Gate 21/21 通过）** | — | 验收门 G2 / G3 通过；M4 Gate 完成条件 1–6 + QG1–QG5 + 数据边界全通过；下一步 M5（任务闭环）待用户确认 | EV-066 EV-067 EV-068 EV-069 EV-070 EV-071 | 2026-10-03 |
| M4-a | Assessment 基础模型与 provenance 前置（契约 + 最小闭环 + 独立 audit artifact；不做星级/LLM/UI/G3） | **已完成（已验收，用户 2026-10-02 确认）** | ZCode | 11/11 检查：草案契约（level=NULL）、四类矩阵准入、history+current view、C5 上游修（`9a21552`）、零写回证据库、audit_store pass/0；真实库对基一致 | EV-067 | 2026-10-02 |
| M4-b | 证据绑定与分桶（LLM 提议 + 八步确定性闸门 + 映射落库；离线闭环 + 1 次真实模型运行） | **已完成（已验收，用户 2026-10-03 确认）** | ZCode | 离线 9/9 + 真实 8/8：schema 三字段 / 八步闸门逐步对例 / LLM 无直接落库路径 / 真实运行 1 次调用 1 个 HTTP 请求（3 接受 1 拒绝）/ 真实库零写入 / audit_store pass | EV-068 | 2026-10-03 |
| M4-c | 评级与反向证据（两维度星级规则引擎 + attack 结算 + rated 写入路径；离线，不调用模型） | **已完成（已验收，用户 2026-10-03 确认）** | ZCode | 离线 12/12：弱 → 理解 2/实践不足；强 → 实践 3；refutes ≤2 且不跨维度；broken 剔除；无证据均不足；同输入同输出；分数隔离（含源码静态检查）；history 保留；audit_store pass/0 | EV-069 | 2026-10-03 |
| M4-d | 可解释输出 + `current_level` 回填（解释报告 + 两维度回填与重建校验；离线，不调用模型） | **已完成（已验收，用户 2026-10-03 确认）** | ZCode | 离线 15/15：报告六项组成 + 逐字引文可回溯 + 无模型分值；反向/已排除分节；回填只经显式方法、legacy 列停用；重建校验（篡改可发现）；无评级 NULL/unassessed；草案不影响当前视图；audit_store pass/0 | EV-070 | 2026-10-03 |
| M4-e | 统一编排 + 缺口 `g_gaps` + 真实 attack 运行 + G2/G3 门证据（独立实验库；真实运行 ≤17 HTTP/次） | **已完成（已验收，用户 2026-10-03 确认）** | ZCode | 离线 25/25、真实 23/23：编排 fail-stop + 缺口三档派生（唯一写路径 + 重建校验）；真实 attack（verifier 独立复核 6 条 + adversarial 两轮；17/17 HTTP、零重试）；G3 A/B/C 判定通过；G2 7/7 可追溯（5 条抽样 + dossier 6 份）；audit_store pass/0；真实库对锚一致、`g_` 全空 | EV-071 | 2026-10-03 |
| M4 Gate | 封板验证（完成条件 1–6 + QG1–QG5 + 数据边界；离线，副本新鲜复核） | **已完成（21/21 通过，用户 2026-10-03 确认）** | ZCode | 3 能力点出星级 / 7-7 可追溯 / PRD §10 分离结论 / 报告七节 / audit pass-0 / G2-G3 通过；QG1–QG5（含 damage caught + 双向测量、200 文件 0 密钥、359 + 111 全绿）；真实库对锚、`g_` 全空 | EV-071 | 2026-10-03 |
| M5 | 任务闭环与成长循环（`g_tasks` / 生成器 / 状态机 / 提交→重评闭环 / G4-G5） | **已完成（用户已确认；M5 Gate 13/13；G4/G5 通过）** | ZCode | M5-a…M5-c 已验收；G5 真实闭环实践 3→4、归因可反查（2/3 HTTP）；M5 Gate 完成条件 + QG1–QG5 + 数据边界 13/13 | EV-072 EV-073 EV-074 EV-075 EV-076 | 2026-10-04 |
| M5-c | 提交 → 单入口证据 → 材料 claim → 绑定闸门 → M4-e 重评 → 归因链（唯一入口 `TaskLoop.complete_task`；三联条件守卫） | **已完成（已验收，用户 2026-10-03 确认）** | ZCode | 离线 38/38、真实 12/12（真实 **1/1 HTTP**）；实践 3→4 + `level_gap_1` 关闭 + 理解保持 open；binding_missed / 失败重跑幂等 / 守卫对例全过；无新表、无新 event kind；真实库对锚、`g_` 全空 | EV-075 | 2026-10-03 |
| M5-b | gap → task 生成器（LLM 提议 + 七步闸门 + 反例拒绝 + 全量留档）+ G4 门证据 | **已完成（已验收，用户 2026-10-03 确认；G4 通过）** | ZCode | 离线/真实各 14/14；真实 2/2 HTTP；七步闸门逐步对例；禁止字段静态检查；`est_minutes` 只夹取；decline 不落库；行数==accepted；G4：映射完整/四要素/4 反例全拒/provenance 可反查 | EV-074 | 2026-10-03 |
| M5-a | 数据契约 + 状态机 + 工具注册（`g_tasks`/`g_task_submissions`/`g_events`；模式 A 四工具） | **已完成（已验收，用户 2026-10-03 确认）** | ZCode | 离线 17/17：冻结词表与转移表 / `g_tasks` 无等级字段（AST）/ 维度↔交付物 / 反例被拒（含字面"去学习 X"）/ 主缺口 open + 去重 / `done` 唯一入口（AST 守卫）/ 事件链有序 / 跨表族 source 校验 / **完成 ≠ 提升**（评定零变化）/ 真实库对锚一致 | EV-073 | 2026-10-03 |
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
| B-06 | 富格式（PDF/docx/xlsx）上传路径 0 端到端验证（V1 状态机 + providers 未被 Growth OS 测试覆盖） | M3（Upload）无法验收 | M3 开工前先做 spike：真实 PDF 走 V1 状态机入库 + audit + locator 可核对性结论 | **已解除**（B-g2 两轮：EV-060 定位一行缺陷 → 上游 `db2de3a` 修复 → EV-061 三项验证通过；**边界**：PDF 无页码级 locator、适配层 V1 入口未建，均保持开放） |

## 下一步

M1 技术 spike 已结束并**正式归档**（用户 2026-10-02 确认）。B-g1 已按用户选择落定为
**本地 Git bundle 归档（方案 A，维持不推送）**，归档、双副本与恢复验证完成（EV-049）。
依赖策略保持**有条件依赖（C1–C5）**，条件见 `docs/M1-SPIKE-CONCLUSION.md` §6.3。

1. **M2 已完成并收口**（2026-10-02，EV-050…EV-057）；**M3 已完成并正式收口**
   （2026-10-02，Gate 13/13 通过，EV-058…EV-065；`artifacts/gates/M3/`）。
   M3 六步全部通过：归属层、本地材料（含 ZIP）、B-g2 PDF、公共仓库、JD 外部参考、材料口径 claim + audit。
2. **M4 能力审计已完成并封板**（2026-10-03，M4 Gate 21/21 通过；EV-066…EV-071；`docs/M4-PLAN.md` v1.0、
   `artifacts/gates/M4/README.md`）。M4-a…M4-e 全部验收：契约与 provenance、绑定与分桶、两维度评级、
   解释与回填、统一编排与缺口 + 真实 attack + G2/G3 门证据。**保留边界**：评估在独立实验库产出、
   真实库不含 `g_` 表；G3 主体为 RAG 相关能力、A 臂笔记为受控构造；`M4-b.1` 生成器接线保持推迟登记。
3. **M5 任务闭环与成长循环：方案已冻结（用户 2026-10-03 确认，EV-072；执行基线 `docs/M5-PLAN.md` v1.0），
   M5-a、M5-b 已验收**（任务契约 + 状态机 + 工具注册，离线 17/17，EV-073；生成器 + 七步闸门 + G4，离线/真实各 14/14、真实 2/2 HTTP，EV-074）。四条关键设计约束：任务不是能力判断
   （`gap → evidence opportunity`，不产出 `task → skill score`）；完成任务 ≠ 自动提升
   （必须经 `submission → evidence → claim → binding gate → assessment`）；
   新证据 provenance 可反查（`task_id → submission → source_id → claim_id → assessment_id → level change`）；
   **M4 rating contract 不修改**（复用 `practice 3 → task_submission → 4`、`understanding 2 → probe_result → 3`）。
   步骤：~~M5-a 契约与状态机~~（已验收）→ ~~M5-b 生成器（LLM 提议 + 七步闸门 + G4）~~（已验收，G4 通过）→ **M5-c 提交→重评闭环（已验收，EV-075）** → **M5-d G5 + M5 Gate（13/13，EV-076）**。
4. **C5 已解决**（evkg `9a21552`，本地未推送）：抽取 provenance（provider/model/prompt 哈希/领域包）写入 claim metadata 与批账本，
   档案渲染器优先显示；发布/CI 前 pin `git + rev` 时须包含该提交。
5. **M3 两个开放项保持开放、不阻塞 M5**：① PDF 适配层 V1 入口（产品上传链路未完成）；
   ② 页码级 locator（上游清单第 14 项）。历史越权主张：只读机器化审计已产出独立 artifact（`artifacts/m4a/historical-claims-audit.json`），真实库不动。
6. **在案维护**：归档刷新（B-g1 bundle 指向 `28afbc0`，本地领先 6 个提交）；
   归档第三副本（用户另存）；发布/CI 前 pin `git + rev` 并复跑两套测试；
   可选：M1-g §8 上游改进清单整理为 issue/PR 文本（**推送需用户另行指示**）。

### 重要约束（用户指定）

- **不把 evkg 的任何提交推送到 `redmaplewww/evkg`**。evkg 本地现领先远程 6 个提交
  （`a4b15af`、`e432c42`、`068389d`、`28afbc0`、`db2de3a`、`9a21552`），远程停在 `a448f44`。改动提案见
  `docs/UPSTREAM-evkg-commits.md`（b.5c 的提案待补充）。

## 进度历史

> 历史归档：[2026-10](archive/progress/2026-10.md)

| 日期 | 会话或任务 ID | 工作内容摘要 | 关键确认或纠正 | 证据 ID | 遗留问题 | 下一步 |
|---|---|---|---|---|---|---|
| 2026-10-01 | M0–M1（概要） | 治理账本建立；evkg 适配层与证据底座打通（领域包、双轨标签、四个上游提交、源码/文本/审计/故障注入、抽取与攻击、证据档案）；M1-g 收口：依赖策略判定为**有条件依赖 C1–C5**，交付形式 = 本地 bundle 归档（方案 A，不推送上游） | 详细过程与逐项证据见 `PROJECT_ACCEPTANCE.md` 的 EV-001…EV-049 与 `docs/M1-SPIKE-CONCLUSION.md`（本表只留近期节点，按治理约定压缩历史） | EV-001…EV-049 | — | M2 开工 |
| 2026-10-02 | M2-a…c（概要） | 基线冻结（5 项决策 + C1–C3 + 开工前 4 项检查）→ `g_` 表族与最小运行时 → Goal Agent 澄清状态机（≤6 轮、显式确认、未确认拒绝能力分析）→ 能力树生成（形状校验先于写入、`adjusted` 保护、`unverified` 标注） | 细节见 EV-050…EV-053 与 `artifacts/m2/`；本表只留近期节点，按治理约定压缩历史 | EV-050…EV-053 | — | M2-d |
| 2026-10-02 | M2-d（尝试 1–5） | 真实模型会话的五次尝试与修复：夹具人侧回答错位 → 提示词层级约定 → runner 硬编码 → 节点名含「/」 → 模拟用户宽泛匹配；每次都保存诊断并停止，未自动重试 | 五类问题全部落在夹具/提示词/硬编码上，产品侧逻辑未降级；诊断见 `artifacts/m2/failure-diagnosis-m2d-0{1,2,3,4}.json`；累计 27 次调用 / 约 25.5k tokens | EV-054 EV-055 | 模拟用户已改为有状态意图匹配 | M2-d（尝试 6） |
| 2026-10-02 | M2-d（尝试 6）+ M2 验收 | 模拟用户改为"有状态 + 意图候选 + 未答要素优先 + 问句主干焦点"（含尝试 4/5 真实问句回归用例）→ 离线回归 143 项 → **尝试 6 真实会话端到端通过** → G1 证据、AC1–AC12 对照、全量回归、数据边界核对 | ① **首次在同一次真实运行内闭环**：澄清 4 轮（purpose→horizon→measurable→确认）→ 四要素 + 用户原话 → 能力树 6 领域/12 组/31 个三层点 → 人工上调为 5 → 再生成后保留（5/理由/adjusted）；② 预算纪律：应用层 6 次 == HTTP 6 次、零额外重试、13/13 自检全绿；③ 全量回归 Growth OS 143 / evkg 101 / ruff 全过；QG1 pass/0；真实库哈希与计数 3/109/2/6 未变；④ **M2 正式收口**（AC1–AC12 全满足，逐项证据见 `artifacts/m2/acceptance-report.md`）；⑤ 如实记录遗留：再生成"并集"语义（49 节点）待 M4 前决策；AC4 的同 id 覆盖强证据来自自动化测试而非真实会话（该次再生成未攻击同一 id）；⑥ M2-d 全部尝试累计 33 次调用 / 约 32.5k tokens（约 0.04 元） | EV-056 EV-057 | 再生成语义待 M4 前决策 | **停在 M3 门前** |
| 2026-10-02 | M3-a | 归属层（`attribution.py`：三取值 + `attribution_of` fail-closed + `can_support_user_claim` 合取规则）与越权校验（`claims.py`：主语/谓词/等级三类越权判定，纯函数）；适配层 `ingest_document` 新增 `attribution` 参数并把标签写入 `Source.metadata` | ① **复用优先**：Source/Passage/Evidence/Claim 沿用 evkg 结构，本步只加策略与校验层，不另造模型；② 归属严格三取值并有词汇表测试；③ **fail-closed**：未声明/非法 → `unknown`（绝不默认成用户声明）；④ 消费规则矩阵 10 例 + JD 走 `domain_reference` 的端到端用例（通道过滤可分离）；⑤ 越权校验 20 例：M1-c 历史主张判越权（只判定、不追改，留 M3-e）、材料口径合规、材料成就/自述计划不误报、用户等级表述判越权；⑥ **数据边界复核发现**：主库**文件**哈希变化（audit_log 追加 + WAL 检查点），但逐表**内容**哈希与 M1-g 基线逐项一致（6/6 evidence、2/2 claim）→ 记录为"文件哈希是弱不变量，应以逐表内容哈希为准"；⑦ 全量回归 187 + evkg 101 + ruff 全过 | EV-058 | M3-b 待发话 | M3-b：本地材料 ingestion |
| 2026-10-02 | M3-b | 本地材料 ingestion：先核对 evkg 路由与 reader 的实际支持范围，再以「容器级封装 + 单入口」方式补 ZIP；`adapter.ingest_document` 新增 `extra_metadata`（保留键防覆盖）；35 项新测试覆盖格式识别/内容提取/来源定位/失败处理 + 归属通道贯穿 + 无旁路 | ① **不猜测支持范围**：读源码确认文本后缀表、代码语言表来源与"其余走 V1"的抛错路径，ZIP 此前完全未支持；② **ZIP 的安全与幂等**：路径穿越/绝对路径跳过、解包目标双重校验、四道上限可注入、稳定解包目录（同归档重复入库命中同一 source_id）；③ **逐条目可见**：ok/skipped/failed 与原因全部留档，单条目失败不中断；④ **无旁路**：spy 断言逐条目调用唯一入口；⑤ 归属/通道贯穿整条链路（含 domain_reference 不能支撑用户断言的用例）；⑥ 已知限制 6 条如实记录（含"预筛表与上游路由表两处知识"的上游待办）；⑦ 全量 222 + evkg 101 + ruff 全过；真实库逐表内容哈希/计数与 M3-a 锚点一致 | EV-059 | 预筛表与上游路由表的统一依赖上游入口（记入待办） | B-g2 / M3-c 待发话 |
| 2026-10-02 | B-g2（PDF，两轮） | 首轮发现 PDF 100% 无法入库（evkg `PdfReader` 的 bytes→BytesIO 一行缺陷）；按用户批准的最小范围修上游（`db2de3a`）+ 补 6 项真实读取测试 → 重跑三项验证通过（含边界） | ① 修复范围锁死（未动 locator/V1/completeness/audit_store/适配层）；② 重跑：入库 40 段、audit pass/0、as-is 与等价实现交叉印证；③ **页码级 locator 保持独立开放项**（仅 ordinal、对原 PDF 不保证逐字；内容不丢：归一化文本完整分区）；④ PDF 支持边界写入 M3-PLAN §5；细节见 EV-060/EV-061 与 `artifacts/bg2/` | EV-060 EV-061 | 页码级 locator（上游 14）；归档刷新 | M3-c |
| 2026-10-02 | M3-c | GitHub 公共仓库接入：先侦察（API 配额耗尽 → 改 git 浅克隆；用户仓库为公共）→ 实现 `evidence/github.py` （材料化/选择/技术栈/单入口）→ 21 项离线测试 → 对 `kkmmtt0919/mytset-rag` 真实冒烟 | ① 真实结果：35 文件→选中 20→**20 ok/0 failed**、179 段、audit pass/0、技术栈 java/python/xml/yaml、同 ref 幂等；② 设计决策：git 浅克隆替代 REST API（无凭据配额已耗尽；git 无该配额且可拿 SHA）；克隆目录按 owner-name-ref 稳定、SHA 写 metadata；③ Windows 坑：git pack 只读 → 加"先去只读位再删"；`audit_store` 不关连接再次锁库（M1-g 上游 §7-10 又一实例，已 gc 重试、无残留）；④ 边界守恒：未接 OAuth/私有仓库/UI/能力评估；claims 与可检索留 M3-e / Gate；⑤ 243 项测试 + ruff + 真实库对基全过 | EV-062 | ≥3 capability claim（M3-e）；归档刷新；页码级 locator（上游 14） | M3-d（待发话） |
| 2026-10-02 | M3-d | 外部参考通道：`evidence/reference.py`（入口无 channel/evidence_type 参数，通道结构锁定；技术词 + 要求条目抽取，只读且每条带 passage 证据）+ 8 项离线测试 + 合成 JD 冒烟 | ① 三条"不得"由结构保证（API 层不可达 user_evidence；消费侧合取规则否决；抽取不写任何 claim/evidence/entity）；② 冒烟：13 段 / 27 技术词（全带证据）/ 4 条要求条目 / audit pass-0 / 8 项边界检查全过 / 临时库已删；③ 用例覆盖 ASCII 词边界（"go" 不命中 "google"）、多份参考分别列出、非参考来源抽取被拒；④ 素材如实标注：本机无现成真实 JD，用写实合成样本（政策验证不依赖文本真实性）；⑤ 边界守恒：未接 UI/未做匹配评分与差距分析，capability claim 仍留 M3-e；⑥ 251 项 + evkg 107 + ruff + 真实库对基全过 | EV-063 | capability claim（M3-e）；M3 Gate 覆盖 | M3-e（待发话） |
| 2026-10-02 | M3 Gate | 完成条件 1–5 与质量门在同一临时库端到端验证（PDF/Markdown 可检索、ZIP 技术栈证据、公共仓库清单+5 claim、无授权与密钥、JD 隔离），并记录两条保留边界 | ① 13/13 全过：PDF 40 段/索引 237 段+5 claim/查询命中；ZIP java+python；仓库 20 文件+5 claim；不存在仓库 rc=128 快速失败；119 跟踪文件 0 密钥；JD 不能支撑用户断言；audit pass/0；真实库对基一致；② **修掉两处**：git 子进程非 UTF-8 输出致崩溃（`run_command(errors="replace")` + 回归测试）、密钥扫描误报（范围改跟踪文件 + 正则不跨行）；③ 边界保留：PDF 适配层 V1 入口未建、页码级 locator 仍缺；④ 267 项 + evkg 107 + ruff 全过 | EV-065 | PDF 适配层入口；页码 locator；归档刷新 | M4（待确认） |
| 2026-10-03 | M5-a 验收 | 用户确认 M5-a 通过（逐项核验 11 项）；特别确认两个设计点（`complete_task` 不直接触发重评、工具层/store 边界正确）；另登记两项 M5-b 约束 | 账本同步：M5-a 转"已验收"、Gate 与验收记录更新；两项 M5-b 约束入 DECISIONS；M5-b 边界提议提交 | EV-073 | M5-b 边界提议已提交 | M5-b（待确认后开工） |
| 2026-10-03 | M5-b（gap → task generator + G4 门证据） | 用户冻结七步闸门命名、schema 七字段与禁止字段、只做 `est_minutes` 夹取、duplicate 谓词、≤2 HTTP 预算、G4 五文件结构，并补充三条实现约束（Generator 不直接写库 / provenance 完整 / 禁止排序字段） → 更新 `M5-PLAN.md`（§4/§9/§12）→ 实现 `tasks/gate.py`（七步 + 留档）+ `tasks/generator.py`（LLM 提议）→ 24 项测试 → 离线 14/14 + 真实 14/14（2/2 HTTP）→ G4 五件套 | ① 缺口存在/open/active 合并为 `gap_taskable` 并强制 `assessment_id`（provenance 入口）；② 禁止字段静态检查（只允许出现在常量）；③ duplicate 谓词 done/abandoned 可再来；④ 真实提议质量良好：理解缺口→probe 现场问答（含评分细则）、实践缺口→可运行最小 RAG 系统（含一键运行验收）；两条全过闸门、无夹取；⑤ 4 条注入式对例（含字面"去学习 Agent Evaluation"）全部被拒且留痕；⑥ 404 + ruff 全绿、真实库对锚一致 | EV-074 | M5-b 待用户验收 | M5-c |
| 2026-10-03 | M5-b 验收 | 用户确认 M5-b 通过（离线/真实各 14/14、真实 2/2 HTTP、G4 PASS；逐项核验 10 项）；确认两处实现记录（`get_gap` 只读 getter 保留——不改变 M5-a 三表契约、不扩大 store 职责；`M5-PLAN` §4/§9/§12 修改已同步）；登记 M5-c 前置冻结约束（① 禁止 task complete → 直接升星，必须走 submission → source → claim → binding → assessment → gap recompute；② 能力变化必须同时具备 before assessment + 新证据 provenance + after assessment；通过率 2/6 口径保留并注明） | 账本同步：M5-b 转"已验收"、G4 转"通过"，Gate 与验收记录更新；M5-c 前置约束入 DECISIONS | EV-074 | M5-c 方案边界已提交 | M5-c（待确认后开工） |
| 2026-10-03 | M5-c（提交 → 重评闭环 + 归因） | 用户确认 M5-c 边界（唯一入口 `TaskLoop.complete_task`、`source_id` 不入调用契约；done 在链尾、失败留 active 可重跑；单入口入库四类交付物；材料 claim 确定性模板；绑定 ≤1 HTTP + 后置条件；M4-e 编排原样接入；三联条件守卫；G5 ≤3 HTTP）→ `M5-PLAN.md` §6/§10/§12 落地 → 实现 `assessment/task_loop.py`（固定链 + `verify_attribution` + `trace_task`）+ `agent/tools.py` 转发 + 12 项测试 → 离线 38/38 + 真实 12/12（1/1 HTTP）→ `artifacts/m5c/` 产物 | ① **done 在链尾**（失败 → 任务留 active，可幂等重跑；done 是闭环结果）；② 绑定后置条件 = 任务能力点 ≥1 accepted，`binding_missed` 不写 assessment、不报提升（八步闸门本身不拒"绑到别的能力点"，由 loop 后置条件拦住"报提升"）；③ 真实运行 `glm-5.3`：实践 **3 → 4**、`level_gap_1` 关闭、理解保持 2、guard 全 true、全链可反查；④ 真实运行两次（报告路径修正后重跑，两次各 1 HTTP、均 12/12；run1 记录保留）；⑤ 真实库对锚、`g_` 全空、无新表、无新 event kind、`RULES_CONTRACT_VERSION=m4c-1` | EV-075 | M5-d 进行中 | M5-d（G5 + M5 Gate） |
| 2026-10-04 | M5-d（G5 + M5 Gate） | 单能力点真实闭环：真实生成实践任务 + 提交受控构造产物 + 绑定 + M4-e 重评；随后离线封板复核已归档证据与真实库副本 | G5 11/11：实践 3→4、实践缺口关闭、理解缺口保持 open、trace complete、audit pass/0、2/3 HTTP；M5 Gate 13/13（QG1–QG5、真实库对锚、`g_` 全空） | EV-076 | 无 | M6 |
| 2026-10-04 | M5 Gate 验收 | 用户确认 M5-c、M5-d、G5 与 M5 Gate 完整闭环通过，允许进入 M6 | 账本状态由“已完成”转为“用户已确认”；M6 先提交方案边界，不开工 | EV-076 | M6 边界待确认 | M6 |
