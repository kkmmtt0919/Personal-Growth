# Growth OS 落地路线

> 把 PRD 的 P0 清单（§31）拆成可按顺序实施、每步都有可验证完成条件的里程碑。
>
> 状态：**待用户确认**
> 关联：`ARCHITECTURE.md`（怎么做）· `ACCEPTANCE_GATES.md`（怎么算做到了）· `DECISIONS.md`（为什么这么选）

---

## 0. 协作协议（重要）

用户要求：**一步一步来，每步汇报，确认后才继续。** 具体约定：

```
每一小步的循环：

  ① 我提出   这一步准备做什么、动哪些文件、完成条件是什么、预计产出什么证据
      ↓
  ② 你确认   （可以改范围、换优先级、否决）
      ↓
  ③ 我实施   只做这一步，不越界
      ↓
  ④ 我提交证据  实际运行的输出/测试结果/产物路径，不含"我跑通了"这类空口结论
      ↓
  ⑤ 你验收   通过 → 更新账本 → 进入下一步
             不通过 → 回到 ③（或重新定义这一步）
```

硬性约束：

- **不擅自跨步**：不把下一步的工作"顺手"做掉。
- **不虚报完成**：没有新鲜证据（实际命令输出、测试通过、产物文件）就不算完成。
- **发现冲突先停**：若实施中发现与 PRD 矛盾或需要改范围，先写 `DECISIONS.md` 并汇报，不自行决定。
- **每步结束更新账本**：`PROJECT_PROGRESS.md` 记进度，`PROJECT_ACCEPTANCE.md` 记证据。

---

## 1. 仓库与目录布局

```
D:\projects\
├── evkg\                     ← 独立仓库（已就位），作为模块依赖，不 fork
├── project-to-act\           ← 治理 skill 仓库（已就位）
└── Personal Growth\          ← Growth OS 主仓库（本仓库）
    ├── .project-to-act\      ← 治理账本（5 份受管文档 + docs/）
    ├── pyproject.toml
    ├── .env.example          ← LLM/GitHub 配置模板（不含密钥）
    ├── Makefile / tasks.ps1  ← 常用命令
    ├── backend\
    │   └── growth_os\        ← 单一安装包根（避免 app/agents/growth 这类通用名发生顶层包名冲突）
    │       ├── __init__.py
    │       ├── app\          ← L4 API（FastAPI）
    │       │   ├── main.py
    │       │   ├── routers\  ← goals / capabilities / assessments / tasks / chat / ...
    │       │   └── deps.py
    │       ├── growth\       ← L2 领域服务（自有语义层，本项目的核心）
    │       │   ├── goals.py
    │       │   ├── capabilities.py
    │       │   ├── assessment.py     ← ★ 五星评级规则（架构 §3）
    │       │   ├── tasks.py
    │       │   ├── memory.py
    │       │   └── repo.py           ← g_ 表族的建表与读写
    │       ├── agents\       ← L3 Agent 运行时
    │       │   ├── runtime.py
    │       │   ├── tools.py
    │       │   ├── context.py
    │       │   ├── tracer.py
    │       │   ├── orchestrator.py
    │       │   ├── goal_agent.py
    │       │   ├── assessment_agent.py
    │       │   ├── growth_agent.py
    │       │   └── scheduler.py
    │       ├── evidence\     ← L1 适配层（**evkg 的唯一入口，全项目只有这里 import evkg**）
    │       │   ├── adapter.py
    │       │   ├── profiles\growth_os.yaml   ← growth 领域包（M1-a 已建）
    │       │   └── github.py ← GitHub OAuth + 仓库读取
    │       └── db\
    │           ├── schema_growth.sql
    │           └── migrate.py
    ├── frontend\             ← L5（React + Vite + TS）
    │   └── src\pages\  Dashboard / EvidenceSpace / Mentor
    ├── scripts\              ← 冒烟脚本、演示脚本（verify_profile.py 已就位）
    ├── tests\
    └── data\                 ← SQLite（gitignore）
```

**架构约束**：`evkg` 只允许在 `backend/growth_os/evidence/adapter.py` 中被 import。其余代码一律通过适配层访问证据能力。这样 evkg 的耦合风险被限制在一个文件里。`scripts/verify_profile.py` 是 M1-a 阶段的临时例外（直接调用 evkg 做验证），M1-b 建好 adapter 后它应改为经 adapter 调用。

> **布局变更记录（2026-10-01，M1-a 实施时）**：原设计为 `backend/app`、`backend/growth`、`backend/agents` 平铺。实施时改为单一包根 `backend/growth_os/`，原因：平铺会让 `app`、`growth`、`agents` 这类极通用的名字成为顶层可导入包名，存在与第三方包冲突的风险，也不符合打包惯例。功能划分不变，只是多了一层包名前缀。

---

## 2. 里程碑总览

| # | 里程碑 | 目标 | 依赖 | 风险 |
|---|---|---|---|---|
| M0 | 地基与治理 | 仓库、选型、账本就位 | — | 低 |
| M1 | 证据底座打通 | 证明 evkg 可作模块被调用 | M0 | **高** |
| M2 | 目标澄清与能力模型 | 模糊目标 → 确认目标 + 能力树 | M1 | 中 |
| M3 | 证据接入 | Upload + GitHub 两条入口 | M1 | 中 |
| M4 | 能力审计 ★ | claim → attack → 五星 + 缺口 | M2 M3 | **高** |
| M5 | 任务闭环与成长循环 | gap → task → 提交 → 星级变化 | M4 | 中 |
| M6 | Memory 三层 | Profile / State / History | M4 | 低 |
| M7 | 主动 Agent | 每日分析 + 事件 + 提醒 | M5 M6 | 中 |
| M8 | UI 三页与端到端验收 | 6 条成功标准可演示 | M5–M7 | 中 |

**关键排序理由**：M1 优先于一切 —— 它是全项目最大的技术不确定性（evkg 能否当模块用、来源分级是否够用）。**先用最小成本证伪它**，避免在错误假设上盖楼。

---

## 3. 各里程碑详情

### M0 · 地基与治理 ✅ 已完成

**交付物**

- `D:\projects\evkg`、`D:\projects\project-to-act` 就位（独立仓库，非本仓库子目录）
- 本仓库初始化 git；`.project-to-act/` 治理账本建立并通过校验
- 架构 / 路线 / 验收 / 决策四份文档
- 环境确认：uv 0.12.10、Python 3.12（uv 托管）、Node 24、git 2.51

**完成条件**

- `init_project_management.py --validate` 通过
- 用户确认技术选型（`DECISIONS.md` Q1–Q4）

---

### M1 · 证据底座打通（技术 spike）★ 最高优先级

**目标**：用最小成本证明或证伪"evkg 可以作为模块被 Growth OS 调用"。

**交付物**

1. `backend/growth_os/evidence/profiles/growth_os.yaml` —— growth 领域包，包含 3.4 节的来源映射与中文 prompt
2. `backend/growth_os/evidence/adapter.py` —— 薄封装：`ingest_file / extract / run_attack / dossier / search / audit`
3. `scripts/smoke_evidence.py` —— 冒烟脚本，跑通全流水线
4. `tests/test_evidence_adapter.py`
5. **spike 结论记录**（写入 `DECISIONS.md`）：R1/R2/R4 是否成立

**完成条件（必须全部有实际输出）**

- [ ] 用一份真实中文资料（建议用用户自己的笔记或 PRD 本身）跑通 `init → ingest → extract → attack → reindex → dossier`
- [ ] `evkg audit_store` 返回 `status=pass`
- [ ] `evkg run_damage_selftest` 返回 `caught`（伪造引文必须被抓出）
- [ ] `Source.metadata` 能携带 `growth_evidence_type` 与 `growth_channel` 并落库可查
- [ ] 产出的一份 dossier markdown 可作为验收档案
- [ ] 结论：evkg 是"直接依赖可用"还是"必须改上游"

**PRD 依据**：§5、§7、§23
**为什么先做**：它决定 D1 决策是否成立。若 evkg 不可作模块用，整个 L1 层要重新设计。

---

### M2 · 目标澄清与能力模型

**目标**：从"我想成为 AI Agent Engineer"到"一个可用的能力树"。

**交付物**

1. `g_goals` / `g_goal_clarifications` / `g_capabilities` 建表与读写
2. Goal Agent + 澄清状态机（`draft → clarifying ⇄ proposed → confirmed`）
3. 能力模型生成：给定 confirmed goal + 外部参考 → 能力树（≥3 领域，≥12 能力点）
4. 外部参考来源选型落地（R5）
5. `tests/test_goal_clarification.py`、`tests/test_capability_model.py`

**完成条件**

- [ ] 输入模糊目标，系统在 **≤6 轮**内产出 confirmed goal，且目标含{方向, 目的, 时间周期, 可衡量结果}四项
- [ ] 目标未经用户确认时，不会进入能力分析（PRD §16 硬约束）
- [ ] 能力树落库并可读回；每个能力点有 `target_level`
- [ ] 能力模型可人工调整（`origin=adjusted`）而不被下次生成覆盖
- [ ] 对应验收门 **G1** 通过

**PRD 依据**：§4 问题一、§16、§17、§24、§25

---

### M3 · 证据接入（Upload + GitHub）

**目标**：两条 P0 输入通道可用。

**交付物**

1. Upload API + 管线：PDF / Markdown / TXT / 代码 / ZIP
   - 需装 `evkg[office]` 以支持 PDF
2. GitHub OAuth（`g_integrations`，token 只存引用）+ 仓库选择 UI + 项目分析
3. 证据入库时写入 `growth_evidence_type` / `growth_channel`
4. `tests/test_upload_pipeline.py`、`tests/test_github_ingest.py`

**完成条件**

- [ ] 上传一份 PDF 与一份 Markdown，均能产出 passages 且可检索
- [ ] 上传一个代码 ZIP，能抽取技术栈证据
- [ ] GitHub 授权后选择一个仓库，系统自动产出该项目的技术栈清单与 **≥3 条 capability claim**
- [ ] 未授权仓库的数据不被读取；token 不以明文出现在账本或日志中
- [ ] 上传的领域资料（如岗位 JD）被标为 `domain_reference`，**不产生**用户能力断言

**PRD 依据**：§7.1 §7.2 §7.3、§22、§23

---

### M4 · 能力审计 ★ 产品内核

> 状态：**已完成并封板**（2026-10-03，M4 Gate 21/21 通过；证据 EV-066…EV-071，
> 判定记录 `artifacts/gates/M4/README.md`）。保留边界：评估在独立实验库产出、真实库不含 `g_` 表；
> 产品入口（UI）留在 M8。

**目标**：实现"用户说自己会，但证据不足"的识别能力 —— 这是 PRD 定义的立身之本。

**交付物**

1. `g_assessments` / `g_gaps` / `g_capability_claims` 建表与读写
2. Assessment Agent 两阶段流程（摄入 → 审计）
3. **五星评级规则引擎**（架构 §3.4）：知识 + 行为 + 实践 + 任务 − 反向证据
4. 评级可解释输出：复用 evkg dossier 渲染"为什么是这个星级"
5. 反向证据处理：`refutes` / `disputed` 的 claim 必须压低评级
6. `tests/test_assessment_rules.py`（决定性用例）

**完成条件**

- [x] 对 ≥3 个能力给出星级，每级可追溯到原始证据 —— **M4 Gate 通过（2026-10-03，EV-071）**：
      3 个能力点出星级；7/7 评定行可追溯（G2 抽 5 条逐跳 + 引文逐字）
- [x] **复现 PRD §10 的判定**：仅有聊天自述 + 论文笔记，无代码/项目/任务证据
      → 必须给出 **理解 ≥2 星、实践 ≤1 星** 的分离结论 —— G3-A：理解 2 / 实践 `insufficient_evidence`
      （"实践 ≤1" 口径 = 不存在 ≥2 的实践等级；缺失 ≠ 低能力）
- [x] 有 GitHub 项目证据时，实践星级显著高于上一条 —— G3-B：实践 3（真实仓库 `mytset-rag@c417a096`；
      增强观测 ≥3 成立；判定口径 = A 无 ≥2 等级 → B ≥2）
- [x] 星级页能回答"为什么我只有三星"：列出支持证据 / 不足 / 攻击结果（PRD §20） ——
      能力解释报告七节齐全（支持 / 不足 / 反向证据 / 已排除 / 规则版本 / 本报告不能成立的结论）
- [x] 每次评估后 `evkg audit_store` 仍为 `pass` —— 实验归档 pass/0；真实库副本新鲜复核 pass/0
- [x] 对应验收门 **G2、G3** 通过 —— `artifacts/gates/G2|G3/`；M4 Gate 21/21 通过

**PRD 依据**：§8、§9、§10、§20、§33（2)(3)
**风险**：R6 中文 prompt 稳定性 —— 需建小规模评测集

---

### M5 · 任务闭环与成长循环

> 状态：**方案已冻结，M5-a、M5-b 已验收（G4 通过）；M5-c 提交→重评闭环已完成待验收；M5-d（G5 + M5 Gate）待推进**（2026-10-03，EV-072…EV-075；执行基线 `docs/M5-PLAN.md` v1.0）。
> 四条关键设计约束：task ≠ 能力判断；完成 ≠ 自动提升（须经 evidence → claim → binding → assessment）；
> provenance 可反查（`task_id → submission → source_id → claim_id → assessment_id → level change`）；
> **M4 rating contract 不修改**。

**目标**：把"缺口"变成"现实行动"，并让行动自动产生能力变化。

**交付物**

1. `g_tasks` / `g_task_submissions` 建表与读写
2. 任务生成器：gap → task，且 task 必须含 {可交付物, 预计时长, 验收方式}
3. 任务状态机（`proposed/active/blocked/done/abandoned`）
4. 提交 → 新的 evkg source → 新 claim → 自动重新评估
5. `tests/test_growth_loop.py`

**完成条件**

- [x] 每个 task 可反向映射到 ≥1 个 gap —— G4 通过（2026-10-03，EV-074）
- [x] **反例必须被拒**："去学习 Agent Evaluation"这类不可验收的任务不得生成（PRD §12）——
      G4：4 条注入式反例（含字面反例）全部被拒并留档（EV-074）
- [ ] 端到端跑通一次：gap → 生成任务 → 提交产物 → 新证据 → **至少一个能力星级发生变化**，且全程无人工干预
      —— 离线端到端已通过（实践 3→4、缺口关闭，EV-075）；**G5 真实运行待 M5-d**
- [ ] 星级变化能说明是哪条新证据导致的 —— 归因链（`m5c-1`）+ 只读反查 `trace_task` 已实现（EV-075）；
      G5 门证据待 M5-d
- [ ] 对应验收门 **G4、G5** 通过（G4 已通过 EV-074；G5 待 M5-d）

**PRD 依据**：§11、§12、§26

---

### M6 · Memory 三层

**交付物**

1. `g_memories`（profile / state）+ `g_growth_snapshots`
2. 三层读写与注入 ContextAssembler
3. 成长曲线数据接口
4. `tests/test_memory.py`

**完成条件**

- [ ] Long-term Profile：能记住并正确引用长期偏好（如"喜欢代码实践，倾向先看架构再看源码"）
- [ ] Short-term State：能回答"当前在学什么、已理解什么、未理解什么"
- [ ] Growth History：能展示 `RAG ⭐⭐☆ → ⭐⭐⭐☆ → ⭐⭐⭐⭐☆` 的时间线
- [ ] 三层互不覆盖（PRD §13 结尾硬约束）
- [ ] 隔天返回时，Agent 的回答包含长期偏好（对应 G6 的一半）

**PRD 依据**：§13、§21

---

### M7 · 主动 Agent

**交付物**

1. Scheduler（进程内定时，每日一次）
2. 4 类事件检测（架构 §5.4）+ 冷却抑制
3. `g_events` / `g_notifications` + 用户可关闭
4. `tests/test_proactive.py`

**完成条件**

- [ ] 构造"窗口期内理论证据增加、实践任务完成数 = 0"的场景 → 产出行动建议
- [ ] 无变化时不产生通知（**每日分析 ≠ 每日骚扰**）
- [ ] 同一类事件在冷却期内不重复提醒
- [ ] 用户可关闭主动提醒，关闭后不再产生通知
- [ ] 目标变化时触发能力模型重新生成

**PRD 依据**：§14、§15、§30

---

### M8 · UI 三页与端到端验收

**交付物**

1. Dashboard：目标 / 当前阶段 / 能力画像 / 系统发现 / 下一步（PRD §19）
2. Evidence Space：知识分类 + 证据图 + "为什么我只有三星"（PRD §20）
3. AI Mentor：对话入口，背后接入 Goal+Memory+Capability+Evidence+History（PRD §21）
4. 端到端演示脚本 + 录屏或截图
5. 完整验收记录（含 evkg 验收档案）

**完成条件**

- [ ] `ACCEPTANCE_GATES.md` 的 **G1–G6 全部通过**
- [ ] 首页只回答"目标 / 状态 / 缺口 / 下一步"四件事，不堆知识
- [ ] 全部质量门 QG1–QG4 通过
- [ ] 可以在无人工干预下完整演示"首次使用 → 证据接入 → 审计 → 任务 → 成长"全流程

**PRD 依据**：§18–§21、§33、§38

---

## 4. 阶段产出与 PRD P0 对照

| PRD §31 P0 项 | 落在 | 状态 |
|---|---|---|
| Goal（澄清/确认/存储） | M2 | 待办 |
| Knowledge（PDF/MD/TXT/代码/抽取/检索） | M1 M3 | 待办 |
| GitHub（OAuth/选仓库/分析） | M3 | 待办 |
| Evidence（Claim/Evidence/Source/Provenance/Attack/Confidence） | M1 M4 | 部分（内核完成：M1 证据图谱 + M4 attack 结算与 provenance；UI/产品入口待 M8） |
| Capability（动态模型/五星/差距） | M2 M4 | 部分（内核完成：M2 能力模型 + M4 两维度星级与 `g_gaps`；UI 待 M8） |
| Task（生成/状态/完成/重评） | M5 | 部分（生成器 + 状态机 + G4 已验收；提交→重评闭环与 G5 待后续） |
| Memory（Profile/State/History） | M6 | 待办 |
| Proactive（每日分析/事件/可关闭） | M7 | 待办 |
| UI（三页） | M8 | 待办 |

PRD §32 的"不做什么"已按原样保留为架构非目标（见 `ARCHITECTURE.md` §9）。

---

## 5. 里程碑粒度与汇报节奏

每个里程碑内部按"小步"实施，**每小步单独汇报**。以 M1 为例：

```
M1-a  建 growth_os.yaml 领域包并加载成功        → 汇报：profile 加载输出的 JSON
M1-b  adapter.py 的 ingest 能力                → 汇报：一份文件落库后的 sources/passages 计数
M1-c  adapter.py 的 extract 能力               → 汇报：抽取出的 claims 数量与样例 3 条
M1-d  adapter.py 的 attack + audit             → 汇报：attack 报告 + audit status
M1-e  dossier 输出                             → 汇报：dossier markdown 文件
M1-f  damage selftest                          → 汇报：caught/missed
M1-g  spike 结论写入 DECISIONS                 → 汇报：R1/R2/R4 结论
```

其余里程碑同理，在开工前拆好小步并汇报。

---

## 6. 待用户确认事项

见 `DECISIONS.md` 的 **Q1–Q4**：

1. evkg 集成方式（独立仓库依赖 vs 内置 vendor）
2. LLM 供应商与模型选型
3. 前端技术栈
4. MVP 是否需要多用户/登录

确认后即可进入 **M1-a**。
