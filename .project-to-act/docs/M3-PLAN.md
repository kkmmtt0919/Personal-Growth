# M3 目标与范围（v1.0 · **执行基线**）

> 状态：**已冻结（2026-10-02 用户确认）**。6 项决策已定案。
> **补充（2026-10-02，用户指定，随基线生效）**：① 数据边界以「逐表内容哈希 + 计数」为准，
> 主库文件哈希**不再单独**作为"数据未变化"的判据；② M3-b 的实现约束见 §5.1。
>
> 依据：`ROADMAP.md` M3 · `PRD.md` §7.1/§7.2/§7.3、§22、§23 · `ARCHITECTURE.md` §3、
> §4.3 `g_` 表族、§6.1 · `ACCEPTANCE_GATES.md` G2/G3（负责里程碑 = M4）·
> `M1-SPIKE-CONCLUSION.md`（有条件依赖 C1–C5、B-g2、归属层须在 M3/M4 前定稿）·
> `M2-PLAN.md`（R5：JD 导入留 M3；能力模型纯 LLM 生成 + `unverified` 标注）。

---

## 0. 一句话定义

> **M3 建立"外部材料 → 可定位证据 → Evidence → Capability Claim"的可信准入链路，但不判断用户能力等级。**

```text
M2:  Goal → Capability Tree → 用户声明的目标能力
M3:  材料 → Source → Passage → Evidence → Capability Claim → audit / provenance
M4:  Capability Claim → 「证据够不够」→「能力处于什么水平」
```

---

## 1. 硬规则（写死）：**"存在证据" ≠ "证明能力"**

例：GitHub 上存在一个 RAG 项目 ——

| M3 **可以**得到 | M3 **不能**推出 |
|---|---|
| `Source`: GitHub repo | ❌ 用户具备 RAG 能力 |
| `Evidence`: 某 README / 代码 passage | ❌ 用户 RAG 能力 = 4/5 |
| `Claim`: **项目材料中出现 RAG 实现相关内容** | ❌ 用户独立完成了该项目 |

**执行方式（M3-e 落地）**：
1. claim 的对象只能是**材料/项目**口径（"材料中包含什么"）；不得以"用户具备/掌握/实现过/独立完成"为结论；
2. growth 领域包既有的「不作能力推断」规则继续生效（M1-c 已实测：抽取器会拒绝把项目成果归因为个人能力）；
3. M3-e 增加**可执行检查**：写入 claim 前校验 subject/predicate 是否越权；越权表述要么被拒绝、要么改写为材料口径，并保留原文 passage 供 M4 判断；
4. 归属层三条取值的消费规则（§3）与这条规则互为补充：前者管"这材料算不算用户的"，后者管"能不能从材料跳到能力结论"。

> 如实备注：M1-c 的真实抽取**曾**产出一条用户口径主张（"用户 实现过 RAG 检索服务"，自评 0.35），
> 随后被 M4 的攻击环节推翻。本规则要求 M3 起不再**创建**这类能力结论（改为材料口径）；
> 这需要在 M3-e 做一处小的产品侧校验改动 —— 实现时按惯例先报你确认，不在本次基线固化内。

---

## 2. 6 项决策（定案）

| # | 决策 | 定案 |
|---|---|---|
| 1 | M3 定位 | **证据准入 / Evidence Ingestion，不做能力评估**（星级与 G2/G3 门判定留 M4） |
| 2 | `evkg[office]` | **允许作为开发期依赖**（PDF/docx/xlsx 解析，会改 `uv.lock`）；发布前按既定方案切 `git + rev` |
| 3 | GitHub | **脚本 + 最小验证页面**；完整 UI 留 M8 |
| 4 | JD | **M3 接入 `domain_reference` 通道**，绝不进入用户能力断言 |
| 5 | 归属 | **先放 `Source.metadata`**（`growth_attribution`），暂不新增 `g_attributions` 表 |
| 6 | GitHub OAuth | **不作为 M3 开工前置**。先跑通本地文件 / GitHub 公共仓库 / PDF / JD 四条链路与数据模型；**只有当私有仓库或用户授权确实成为当前里程碑的必要路径时再接 OAuth**，届时再提供 `GITHUB_CLIENT_ID/SECRET` |

**第 6 项的意图（用户原话要点）**：不要让整个 M3 被一个外部认证依赖卡住。
M3-c 的 GitHub 通道在 M3 范围内**只做公共仓库**（用户提供 URL，无需凭据；注意未认证 API 的速率限制）。

---

## 3. 归属层（M3 的数据决策）

| 归属取值 | 产生方式 | 消费规则 |
|---|---|---|
| `user_declared` | **用户动作**：亲自上传某文件 / 明确指定某仓库为"我的" | 可作为实践/任务证据支撑 claim |
| `user_asserted` | 用户口头声称（聊天）但无产物 | 只能作弱证据，**不得单独支撑结论** |
| `unknown` | 第三方资料、领域参考（JD/论文/官方文档） | 仅作 `domain_reference`，**不参与**用户能力断言 |

纪律：归属是**用户声明的记录**，不是系统推断的结论；系统不得据其他线索自动升级归属。
落库：`Source.metadata.growth_attribution`（与 `growth_evidence_type` / `growth_channel` 并列）。

---

## 4. 范围

### 4.1 做

- 三条材料通道：**本地文件**（PDF / Markdown / TXT / 代码 / ZIP）、**GitHub 公共仓库**、**Chat 材料化**（自述入库为弱证据）；
- **JD / 领域资料**：入库标 `domain_reference`，不产生用户能力断言；
- **归属层**（§3）与通道隔离；
- **证据 → 断言绑定**：`claim → evidence → passage → source` 逐跳可追溯；
- 检索：入库后可检索（metadata 过滤 + FTS 索引）；
- 运行与证据记录：实际 provider/model、失败留档（沿用 M2 纪律）。

### 4.2 不做

- 不评星级、不做 assessment、不判定 G2/G3（M4）；
- 不生成任务（M5）、不做完整 UI（M8；仅"最小验证页面"）；
- 不做向量检索 / RAG 问答（架构非目标：FTS5 + 结构化查询）；
- 不把 JD 转成用户能力断言；不由"项目存在"推断"用户实现"；
- **不接 OAuth / 私有仓库**（决策 6：需要时再接）；
- 不碰 M2 遗留的"再生成并集语义"（留能力审计/演化模型统一决策）；
- 不改 evkg 上游逻辑（保持有条件依赖 C1–C5；如需改动走上游提案）。

---

## 5. 步骤结构（用户指定顺序；仅到步骤级，不拆实现任务）

```text
M3-a  Evidence 基础模型与归属层
      ↓
M3-b  本地材料 ingestion（MD / TXT / 代码 / ZIP）
      ↓
B-g2  PDF spike（独立前置验证）
      ↓
M3-c  GitHub ingestion（公共仓库；无 OAuth）
      ↓
M3-d  JD / domain_reference
      ↓
M3-e  Claim + audit + provenance（含 §1 的越权校验）
      ↓
      M3 Gate
      ↓
      M4 Assessment
```

### 5.1 实现约束（进入各步骤前必读）

- **M3-b（本地材料 ingestion）**：必须**复用现有单入口**（`adapter.ingest_document`）与既有链路模型
  （`Source / Passage / Evidence / Claim`）；**新增文件格式不得绕过 M3-a 的归属（`attribution`）
  与通道（`growth_channel`）策略**，也不得为支持新格式而自造旁路入口。
  —— 用户 2026-10-02 指定。
- **留到 M3-e**：把越权校验（`claims.check_overreach`）接进写入路径、以及处理 M1-c 那条历史上的
  用户口径主张。M3-b…M3-d 不得顺带处理这两件事（避免提前扩大变更范围）。

**B-g2 通过标准三条**：① 真实中文 PDF 经 evkg V1 状态机入库、产出 passages；
② `audit_store` = pass（不变量 0 violation）；③ **如实说明该路径下 locator 能否回原文核对**
（V1 归一化会重排文本 —— 不能含糊；不能核对就标注局限，不硬撑）。
不通过则 PDF 降级为"仅 MD/TXT/代码/ZIP"并报告缺口。

---

## 6. 验收标准

### 6.1 ROADMAP M3 完成条件（硬性）

1. 上传一份 PDF 与一份 Markdown，均产出 passages **且可检索**；
2. 上传一个代码 ZIP，能抽出技术栈证据；
3. GitHub 公共仓库（无需授权）能产出技术栈清单与 **≥3 条 capability claim**；
4. 未授权/未指定的仓库数据不被读取；token（若将来接入）不以明文出现在账本/日志；
5. 上传的领域资料（如 JD）标为 `domain_reference`，**不产生**用户能力断言。

> 与 ROADMAP 原文的差异（决策 6 的结果）：第 3 条由"GitHub 授权后选仓库"改为
> **公共仓库、无需授权**；OAuth 与私有仓库留待其成为必要路径时再做。

### 6.2 本步质量门

6. `claim → evidence → passage → source` 逐跳可追溯（自动化）+ `audit_store` = pass/0；
7. **§1 硬规则可执行**：越权表述（"用户具备/独立完成"）被拒绝或改写为材料口径，有测试锁定；
8. 归属层三条取值的消费规则各有测试（`unknown` 不得支撑用户断言；`user_asserted` 不得单独支撑结论）；
9. LLM 路径离线回归（fake gateway）+ 真实运行单独留档；两层预算与"失败即停"沿用 M2；
10. 数据边界：测试不污染真实库（零写入断言）；**以逐表内容哈希为准**
    （锚点 `artifacts/m3a/evidence-anchors.json`；`audit` 前后逐表哈希一致）。
    **主库文件哈希不作为单独判据** —— 审计日志追加与 WAL 检查点都会改变文件字节
    （2026-10-02 已实测解释：内容级逐项一致，文件哈希变化）；
11. 运行记录记实际 provider/model，失败也留档。

### 6.3 不在 M3 判定的

G2（可追溯）与 G3（A/B 对照）的**门判定**仍属 M4；M3 只产出它们所需的证据。

---

## 7. 前置与风险

- **前置**：无外部认证前置（决策 6 已移除）。B-g2 是 M3-b 与 M3-c 之间的独立验证点。
- 依赖：新增 `evkg[office]`（决策 2 已允许）→ 会改 `uv.lock`。
- 富格式 locator 的诚实性：见 B-g2 标准 ③；这是 M1-b.5a 纪律（"一个说谎的 locator 比没有更糟"）的延续。
- GitHub 公共 API 速率限制：M3-c 需退避与增量策略（实现细节，步骤内定）。
- ZIP 规模控制：逐文件走 `ingest_path`，需设体积/文件数上限（实现细节，步骤内定）。
- 不把 M2 的并集语义带进 M3：新证据与 `g_capabilities` 的关联不得做出与未来决策冲突的假设。
