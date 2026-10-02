# M1 技术 spike 结论（M1-g）

> 本文件是 M1 技术 spike 的收口文档：回答 R1–R4 与 D1，给出 evkg 依赖策略的判定依据、
> 已知缺陷与绕行代价、上游改进清单、以及阻塞/延后决策。
>
> 纪律声明（用户指定，本文遵守）：
> 证据只支持"当前路径可用"的地方，不写成"组件整体可靠"；D1 的全局 profile 未做
> 双实例实测前不得推定，现已实测（§6），结论以实测为准。
>
> 证据产物：`artifacts/m1g/`（脚本与 JSON，含逐项原始输出）；账本证据 EV-042…EV-046。

---

## 0. 结论摘要

**依赖策略判定：有条件依赖（conditional dependency）。**

Growth OS 可以依赖 evkg 跑通当前单进程 / 单领域包 / 单用户的证据路径 —— 该路径已在真实
材料上端到端验证（3 来源 / 109 段落 / 2 主张 / 6 证据行，audit pass）。但**不是**
"可直接依赖的组件整体"：存在一处已实测的进程级全局状态（D1 双实例污染）、三处已知上游
缺陷（其中两处已被本地绕行、一处要求改上游）、以及一类未被自动化测试持续覆盖的
LLM 路径（extract / attack）。这三类问题分别对应"有条件"的三个条件（§7）。

一句话版本：

> evkg 的**当前调用面**可用且证据链可信；evkg 的**整体**尚不可当作可直接依赖的组件
> —— 多领域包并行、抽取可复现性、部分渲染三处必须先改上游或显式绕行。

---

## 1. R1 · evkg 当前能力是否满足 Growth OS 的直接依赖需求？

**结论：当前调用面满足；未使用的能力面未经验证，不纳入结论。**

### 1.1 实际调用路径（产品代码只经适配层）

产品代码（`backend/growth_os/`）只允许 `adapter.py` import evkg（由 AST 边界检查锁定，
`tests/test_adapter_boundary.py`，14 项）。实际用到 6 个模块路径：

| 模块 | 使用的公开入口 | 用途 |
|---|---|---|
| `evkg.config` | `Profile` / `activate` | 激活成长领域包 |
| `evkg.domain` | `SourceKind` | 证据类型 → 来源类型映射 |
| `evkg.ingest` | `ingest_path` / `logical_source_id` | 统一路由入库 / 逻辑身份 |
| `evkg.store` | `KnowledgeStore`（`get_source` / `get_passages` / `find_sources` / `counts`） | 存储读写与检索 |
| `evkg.evidence.dossier` | `claim_dossier` | 结构化证据档案（**不用**其 Markdown 渲染器，见 §8.1） |
| `evkg.attack` | `audit_store` / `run_damage_selftest` | QG1 / QG2 |

脚本与验收产物另用到 `evkg.extract.extract_corpus`、`evkg.attack.verifier_gateway`、
`evkg.model_gateway.ModelGateway`、`run_attack`（`artifacts/m1b5`、`artifacts/m1d`）。

### 1.2 端到端证据（本次独立复跑）

| 检查 | 结果 | 证据 |
|---|---|---|
| 入库 → 抽取 → 攻击 → 档案全链路 | 3 来源 / 109 段落 / 60 实体 / 3 别名 / 1 事件 / 2 主张 / 6 证据行 / 4 攻击报告 / 2 冲突候选 | EV-044（`r4_evidence.json`） |
| 不变量审计（QG1） | `pass`，10 项检查 0 violation | EV-044 |
| 抽取账本覆盖 | 109/109 passage `complete` | EV-044 |
| 「计划学习」不被升级为「具备能力」 | 状态 `machine_reviewed`/0.697，对抗裁决 `sustained` | EV-032（沿用 M1-d） |
| 越权主张被独立推翻 | `disputed`/0.17，复核 `partial`、裁决 `broken` | EV-032（沿用 M1-d） |

### 1.3 明确未验证的部分（不得读成"能力不足"，只是没验）

- **V1 状态机 / 富格式**（PDF/docx/xlsx/OCR）：Growth OS 测试对 `ingest.pipeline`、
  `ingest.providers` 的覆盖分别只有 14.6% / 35.1%，且都是间接路径 —— **PDF 上传路径
  没有任何端到端验证**（M3 的 Upload 依赖它，见 §9 阻塞项 B-g2）。
- **索引/检索**（`index/fts`、`index/search`）：**已在真实材料副本上补齐验证**（EV-047：FTS5 模式、109 段落 + 2 主张建索引、重复重建幂等、索引后 audit 仍 pass、4/5 查询命中；`计划学习` 为 2 字查询，按设计回落 LIKE，且 predicate 不在索引字段内，故 0 命中 —— 这是已记录的检索边界）；产品路径（UI 检索）尚未接入，pytest 覆盖仍为 0%。
- **web / export 与 cli 其余子命令**：0% 覆盖，Growth OS 不使用（`init` 与 `reindex` 两个
  子命令已由 EV-047 实跑一次；`web` 的档案端点受 §8.1 缺陷影响）。
- **`SourceKind.UNKNOWN` 之外的 kind 扩展**：`growth_os.yaml` 里写自定义 kind 会被
  静默忽略（`policies.py` 的 `except ValueError: continue`），细粒度类型只能走
  `metadata.growth_evidence_type` —— 这是 M1-a 起就锁定的硬约束，不是新发现。

---

## 2. R2 · 哪些能力可通过适配层解决，哪些必须修改 evkg？

### 2.1 适配层可解决（无需改上游）

| 能力 | 落点 |
|---|---|
| 证据类型 → 来源类型的领域映射（6 类） | `adapter.EVIDENCE_KIND_MAP` |
| 领域标签（`growth_evidence_type` / `growth_channel`）随入库写入 | `ingest_path(..., metadata=...)` |
| 用户证据 / 领域参考通道隔离 | `adapter.sources_by_channel`（防"JD 要求"被读成"用户具备"） |
| 面向产品的错误类型 | `adapter.EvidenceError` |
| 档案的领域语义渲染（含 `partial`、两个"独立"、缺失证据措辞、3 位小数） | `growth_os.evidence.dossier` |
| 耦合防回潮（禁裸 SQL / 禁内联 SQL / 禁低层方法） | `tests/test_adapter_boundary.py` |

### 2.2 必须修改 evkg（M1-b.5 已完成 4 个上游提交）

这四处**无法**在适配层内正确解决 —— 适配层当时确实"绕"过，代价是裸 SQL、
错误权重或说谎的 locator，因此改为修上游：

| 上游提交 | 不修上游的后果（均已实测） |
|---|---|
| `a4b15af` `SourceKind.CODE` / `CodeReader` / 行范围 locator | 通用切分器折叠空白，8 行 Java 塌成 3 行，行号失去意义（locator 会说谎） |
| `e432c42` assessment 生命周期（`UNASSESSED ≠ 0.25`） | kind=code 来源无缓存分级时按 0.25 计权，同源同内容权重差 0.55 且静默 |
| `068389d` 逻辑身份 + `content_hash` + 显式 upsert + 段落级联替换 | 写入报成功而库里是旧值；换切分器后旧段落静默累积（实测混入 11 条撕裂片段） |
| `28afbc0` `ingest_path` 统一路由 + `find_sources` 按 metadata 检索 | 适配层必须自造后缀路由 + 对 `sources.payload` 写 `json_set`/`json_extract` |

（完整提案文本见 `UPSTREAM-evkg-commits.md`；**不得推送远程**，用户 2026-10-01 指示。）

### 2.3 必须修改 evkg（尚未修，见 §8）

1. 领域包作用域（进程级全局 → 实例级/显式传参）—— 多领域包并行的前提；
2. 抽取模型名持久化 —— 抽取可复现/可审计的前提；
3. `render_claim_markdown` 丢 `partial` —— 若要让 evkg 自己的渲染器/前端可用；
4. `caught` 判定依赖截断样本 —— QG2 结论稳健性；
5. `KnowledgeStore()` 无参 TypeError（`store.py:47` 用 `Path(path)` 而非 `Path(self.path)`）；
6. `.env.example` 复核模型变量名与代码不一致（`EVKG_VERIFIER_PROVIDER` vs 代码读取的
   `EVKG_VERIFIER_LLM_PROVIDER`）—— 照抄示例会让独立复核**静默失效**；
7. `KnowledgeStore` 无 `close()` / 上下文管理器，连接只能靠 GC 释放（Windows 上锁文件，实测 `WinError 32`）；
8. 检索字段不含 claim 的 `predicate`（§7-11，低severity）。

### 2.4 适配层自身的缺口（本地可修，代价低）

`adapter.ingest_document()` 不强制已 `configure()`。`open_store()` 会调用 `configure()`，
但调用方若自建 `KnowledgeStore` 再调 `ingest_document`，会**静默**使用 evkg 内置 default
领域包。实测（EV-043 part5，同一份笔记）：

| 路径 | 段落数 | 评级理由 |
|---|---|---|
| 未 `configure()` | 5 | "汇编或编纂材料，受编纂取舍影响"（evkg 默认） |
| 已 `configure()` | 2 | "用户整理或上传的笔记与文档。反映知识性理解，不足以证明实践能力。"（成长领域包） |

基线数值恰好相同（0.68）而理由与切分不同 —— 属于**静默错误**类型。建议在
`ingest_document` 入口加一条断言（`active().name == "growth_os"`，失败即报
`EvidenceError`），成本约 3 行。

---

## 3. R3 · 当前测试覆盖能否支撑集成结论？

**结论：能支撑"当前调用面已按当前需求验证"，不能支撑"evkg 组件整体可靠"；
对 LLM 路径而言，证据是"一次性验证"而非"持续验证"。**

### 3.1 本次独立复跑（EV-042）

| 套件 | 收集/通过 | 说明 |
|---|---|---|
| evkg | **101 / 101**，exit 0 | 含正序与**逆序**文件顺序两轮，均全绿 |
| Growth OS | **73 / 73**，exit 0 | 14 边界 + 10 故障自测 + 22 档案 + 27 适配层 |

用户提供的 M1-f 数字（evkg 101 / Growth OS 73）经独立复跑核对一致。

### 3.2 行级覆盖（EV-046，AST 语句行近似口径）

| 文件 | 覆盖 | 未覆盖的**逻辑**分支（已扣除 docstring 行） |
|---|---|---|
| `backend/growth_os/evidence/adapter.py` | 83.3%（70/84） | 领域包路径不存在/名称不符两个错误分支；`logical_id_for`；`damage_selftest` 转发 |
| `backend/growth_os/evidence/dossier.py` | 96.1%（174/181） | 对象名超 44 字符截断；无来源时的"（无）"；引文超 6 行截断；`score=None` 的 "-"；非数值兜底 |

**LLM 依赖路径没有自动化测试**（这是本阶段最重要的覆盖结论）：

| evkg 模块 | Growth OS 测试覆盖 | 实际验证方式 |
|---|---|---|
| `extract.py` | 0% | M1-c 一次性全量跑（109/109），输出留档 |
| `attack/verifier.py` | 18.2% | M1-d 一次性真实跑，含独立模型核对 |
| `attack/adversarial.py` / `deterministic.py` / `contradiction.py` | 15–28% | 同上 |
| `model_gateway.py` | 18.8% | 探针 + 上述运行 |

即：抽取与攻击的集成结论建立在**一次性、消耗 API 的真实运行**上，不在可重复的
测试保护之下。模型输出不稳定、上游模型换代、提示词调整都不会被测试拦住。

### 3.3 已知盲区与误报/漏报风险

1. **审计的引文校验是子串匹配**（`instr(passage.text, quote) ≠ 0`）：只证明"引文是真
   子串"，不证明"引文完整"或"主张被原文蕴含"。M1-f 有意保留（`子串引文不得被误判`
   有测试锁定），属于必要非充分检查。
2. **`caught` 判定依赖截断样本**：已实测复现（§8.3）。方向是保守的（脏库上可能报
   `missed`），但同一个机制也可能让"caught"来自错误的理由。
3. **测试顺序依赖在结构上存在**：全局 profile + 个别测试 `set_active` 后不恢复现场。
   实测正序/逆序均全绿，因为各测试模块用 autouse fixture 显式重置 —— 这是被测试
   自律掩盖，不是被结构防止。
4. **无端到端 PDF/富格式路径**（§1.3）。
5. `dossier` 的 `score=None` 渲染分支未被 Growth OS 测试覆盖 —— 而"未分级"是
   b.5b 引入的重要状态，建议补 1 项测试。

---

## 4. R4 · 当前数据与证据链是否具备可追溯性？

**结论：在"claim → evidence → passage → source"这一层，可追溯性成立且逐字可核验；
在"抽取运行 → 模型/提示词版本"这一层，可追溯性**不成立**（模型名未持久化）。**

### 4.1 实库核验（EV-044）

| 检查项 | 结果 |
|---|---|
| 全部 evidence 的 quote 逐字存在于所引 passage | 通过（6/6） |
| 全部 evidence 都指向存在的 passage 与 claim | 通过 |
| 全部 evidence 都带 `growth_evidence_type` + `growth_channel` 标签 | 通过 |
| 全部 claim 都有证据、`passage_ids` 全部存在 | 通过（2/2） |
| 抽取账本覆盖 | 109/109 `complete` |
| 代码来源 locator 可回磁盘逐字核对 | 通过（M1-b.5a EV-012 已锁） |
| 不变量审计 | `pass`，0/10 |
| 审计对证据数据的影响 | 逐表 payload sha256 前后一致；仅 `audit_log` +1 行（审计流水本身） |

### 4.2 可追溯性的三个缺口（如实记录）

1. **无归属层**：`repo_artifact` 只能证明材料内容，不能证明"用户本人实现"。
   这是 L1/L2 边界的产品问题（M2/M4 决策），不是数据缺陷；档案已明示该局限，
   且 M1-d 已实测该机制能推翻越权主张。
2. **抽取模型未记录**（§8.2）：档案只能写"未记录在案"。对照：复核模型**有**记录
   （`metadata.verifier_model` / `verifier_independent`），抽取模型没有 —— 不对称。
3. **领域包身份未持久化**：source/passage 均未记录"由哪个 profile 切分/评级"。
   当前只有一个 profile，影响有限；一旦 `growth_os.yaml` 修改，旧数据无法自证由
   哪一版规则产生（`content_hash` 只覆盖文本，不覆盖规则）。
4. （记录在案、有意为之）段落替换是硬删除，不保留旧文本历史；上游提案已声明该
   限制与 `supersede` 演进方向。

---

## 5. D1 · 依赖边界、维护成本、兼容性与全局状态影响

### 5.1 依赖边界

- 依赖方式：独立仓库 + uv editable path（Q1），**不 fork**；耦合收敛到
  `adapter.py` 单一文件，由 14 项 AST 边界检查防回潮。
- **版本边界风险**：evkg 本地领先远程 4 个提交（`a448f44` → `28afbc0`），远程不含
  任何 M1 所需改动；当前依赖是"本机路径 + 4 个未推送提交"。发布前必须把依赖
  pin 到具体 commit SHA（`pyproject.toml` 注释与 DECISIONS 已记）。
- 上游无兼容性承诺：`evkg/__init__.py` 不导出任何公共 API，下游只能按模块路径
  import（6 个路径已由边界检查固定）。这是架构风险 R1（无 library facade）的具体形态。

### 5.2 维护成本

- 已完成 4 个上游提交 + 101 项 evkg 测试全绿，属于一次性成本，已沉没且可复用。
- 长期成本主要是**跟随成本**：本地领先远程意味着每次上游更新都需要自己 rebase
  这 4 个提交；建议按 §8 的清单一次性把剩余修复也提给上游，避免本地分支越走越远。
- 绕行成本见 §8 表格（自建渲染器、一次性注入流程、档案如实声明缺失）。

### 5.3 全局状态影响（D1 特别检查，已实测）

**问题 1：profile 是什么级别的状态？**
**进程级全局。** `evkg.config._ACTIVE` 是模块级变量（`config.py:278`），
`activate()`/`set_active()` 直接改写它；`active()` 被 12+ 处调用点在执行时读取
（切分、策略表、提示词、实体消解、日期标注等）。`KnowledgeStore.__init__` 只有
`path` 参数、实例上没有 `profile` 属性 —— store 与 profile 无绑定关系。

**问题 2：两个不同配置的实例能否在同一进程独立运行？**
**不能。** 实测（EV-043，两个探针领域包 A/B + 两个独立 DB）：

| 步骤 | 期望 | 实测 |
|---|---|---|
| storeA 在 A 激活时入库（4 段落） | 4 | 4 |
| storeB 在 B 激活时入库（2 段落） | 2 | 2 |
| **不重新激活 A**，storeA 再入库同一文件 | 4 | **2（被 B 污染）** |
| 重新激活 A 后 storeA 再入库 | 4 | 4（恢复） |

同一 `source_id`、同一内容，段落集合被"最后一次 activate"改写 —— 污染发生在
**写入时**（replace 语义），已写入的数据在读取时不受后续 activate 影响。

**问题 3：初始化顺序是否改变另一个实例的行为？**
**会，但不是"创建顺序"而是"最后一次 activate"**：先建 store 后建 store 都一样；
谁最后 `activate()`，下一次写入就按谁。实测 part2：在 B 激活后新建 store 并用它入库 → 用 B 的规则。

**问题 4：测试是否存在顺序依赖？**
**结构上存在，实测未触发。** 正序与逆序两轮 evkg 101 项均全绿；各测试模块用
autouse fixture 显式 `activate("default")` 并在结束时重置。个别测试
（如 `test_profile_can_extend_code_languages`）`set_active` 后不恢复原对象，
靠 fixture 兜底。结论：顺序依赖被测试自律掩盖，没有结构性防护。

**问题 5：能否用现有公开 API 隔离？**
**顺序执行可以，并发不行。**
- 顺序：每次调用前 `activate(profile)` + `try/finally` 复原 —— 实测有效（part4）。
  代价：全局写操作散落在调用点，异常/遗漏即污染，且无法防并发。
- 并发：无任何公开 API 可把 profile 绑定到 store 或调用 ——
  `ingest_path` / `ingest_file` / `KnowledgeStore.__init__` 均无 `profile` 参数；
  给实例挂 `store.profile` 属性被完全忽略（实测）。asyncio 交错实验（part3）
  用事件强制顺序：任务 A 期望 4 段，实际得到 2 段（被任务 B 的 activate 覆盖）。
- **因此：真正的隔离必须改上游**（实例级 profile 或显式 profile 参数）。
  D1 的最终判定是"尚未具备隔离能力，但当前单 profile 用法不受影响"，
  **不推定安全、也不推定为缺陷** —— 以实测的双实例污染为准。

**适配层层的后果**（§2.4）：`ingest_document` 不校验 profile，忘记 `configure()`
会静默使用 evkg 默认领域包。这是全局状态设计在 Growth OS 自身 API 面上的具体风险。

---

## 6. 依赖策略判定（三种情形的判定依据）

### 6.1 可直接依赖 —— **不成立**

要把 evkg 当作可直接依赖的组件整体，至少需要：多实例/多领域包可隔离、关键结论
（抽取、攻击、质检）有可重复的自动化验证、公开入口的行为与其文档一致。当前：
- 双实例隔离**已实测不成立**（§5.3）；
- 抽取模型不可追溯（§8.2）；
- 上游渲染器在 `partial` 上静默丢数据（§8.1）；
- 无参 `KnowledgeStore()` 直接 TypeError、`.env.example` 变量名与代码不一致（§2.3）；
- LLM 路径无自动化测试（§3.2）。
因此"整体可直接依赖"没有证据支撑。

### 6.2 必须改上游 —— **部分成立（已完成 4 项，尚有 8 项）**

- 已完成：§2.2 的四个提交。它们是"当前路径可用"的前提，缺任何一个适配层都会
  退化为裸 SQL / 错误权重 / 说谎 locator。
- 未完成：§2.3 的八项。其中**profile 作用域**与**抽取模型持久化**影响后续阶段的
  验收门槛（§9）。

### 6.3 有条件依赖 —— **成立（本阶段采纳）**

条件（缺一不可，写进 DECISIONS 与检查清单）：

| 条件 | 内容 | 判定方式（tripwire） |
|---|---|---|
| C1 | 单进程只激活一个领域包；profile 切换只允许在"无并发写入"的初始化阶段发生 | 代码审查 + §5.3 实验脚本可作为回归工具 |
| C2 | 不使用 evkg 的 `render_claim_markdown`（增长域档案一律走自建渲染器，回归测试锁定） | `tests/test_dossier.py` 的 partial 回归 |
| C3 | 发布/换机前把 evkg 依赖 pin 到 commit SHA（含本地 4 个提交的可获取副本） | `pyproject.toml` + 构建可复现性检查 |
| C4 | QG1 以 `audit_store` 为准；QG2 不采信内置自测的 `status` 单值，采用 M1-f 的"注入前/后双向测量"流程 | `tests/test_damage_selftest.py` + M1-f 脚本 |
| C5 | 能力档案必须如实标注"抽取模型未记录"；在 M4 验收前解决抽取模型持久化（上游修或本地记录） | 档案文本核对；M4 门检查。**已解决（2026-10-02，M4-a）**：evkg `9a21552` 起抽取 provenance（provider/model/prompt 哈希/领域包）写入 claim metadata 与批账本，档案渲染器优先显示；修复前的历史主张继续如实写"未记录在案" |

---

## 7. 已知缺陷、临时绕行及其代价

| # | 缺陷（上游） | 严重度 | 现有绕行 | 绕行代价 | 上游修复成本 |
|---|---|---|---|---|---|
| 1 | `render_claim_markdown` 静默丢弃 `polarity=partial` 的证据行（`evidence/dossier.py:80-81,171-180`） | 高（会抹掉"复核认为只部分支持"，且 evkg 自己的 web/CLI 档案同样受影响，`web.py:280`） | Growth OS 自建渲染器显式纳入 `partial`，并有 2 项回归测试（EV-035） | 多维护一份渲染器；若上游渲染器行为变化需人工跟进；evkg 前端不可直接复用档案页 | 小：把 `evidence` 里非 supports/refutes 的极性单列一节 |
| 2 | 抽取模型名未持久化：`extract._call` 丢弃 `ModelResult.model`（`extract.py:86-92`），claim metadata 只写 `{model_claim_id, review_state}`（`:182`），批账本只写计数（`:257-260`） | 高（能力结论不可复现/不可审计：换过模型无法知道哪条主张由哪个模型产出） | 档案如实写"未记录在案"（不拿当前配置冒充历史） | 无法回答"这次抽取用的哪个模型"；M4 若要"可复核"，缺一环 | 小：仿照 verifier 的做法（`verifier.py:130`）写入 metadata；更好的位置是批账本/逐 passage |
| 3 | `run_damage_selftest` 的 `caught` 用"注入 id ∈ 前 10 行 sample"判定（`damage.py:56`），而 auditor 的 sample 截断为 10（`auditor.py:26`） | 中（脏库上假 `missed`；已实测复现） | M1-f 的受控注入 + 注入前/后计数与内容级哈希（不采信单值 `status`） | 需自建并维护注入流程；不能直接用内置自测作为 QG2 唯一判据 | 小：按 `violations` 计数变化或按 id 直查判定 |
| 4 | profile 为进程级全局（`config.py:278`），无实例级绑定 | 中（当前单 profile 不受影响；多领域包/并发切换即污染） | 单进程单 profile + 初始化时 `configure()`；顺序场景可 per-call re-activate | 无并发安全；适配层需自加 profile 断言（尚未加） | 中：`Profile` 显式传参或 store 绑定；涉及 12+ 调用点 |
| 5 | `KnowledgeStore()` 无参直接 TypeError（`store.py:47` 用 `Path(path)`） | 低 | 适配层永远显式传路径 | 下游第一次调用即踩坑，报错信息不指向真实原因 | 极小：`Path(self.path)` |
| 6 | `.env.example` 复核变量名错误（`EVKG_VERIFIER_PROVIDER` vs 代码读 `EVKG_VERIFIER_LLM_PROVIDER`） | 高（照抄示例 → 独立复核静默回落到主模型 = "自己审自己"） | Growth OS 的 `.env.example` 已写正确名字并加警示 | 新下游用户仍会踩；安全属性（独立复核）静默失效 | 极小：改一行文档 |
| 7 | `.env.example` 的 `REASONING_EFFORT=none` + 裸 JSON `EXTRA_BODY` 对 glm-5.3 无效（400 / dotenv 剥引号） | 低（与具体模型绑定） | Growth OS 侧改为 `low` 并整体加单引号 | 无（配置层已解） | 小：示例加注或改为通用默认 |
| 8 | V1 状态机 `normalize_document` 折叠空白，无法保真代码行号；`ingest_file` 的 `.html` 分支是死代码 | 低（当前不使用） | 代码一律走 `ingest_code_file` 快路径 | M3 富格式上传与代码无法共用一条路径 | 中（需让归一化对代码无损） |
| 9 | `_load_cached` 为 `lru_cache(maxsize=8)` 按路径缓存：进程运行中修改领域包不生效 | 低 | 重启进程 | 开发期"改了 profile 没反应"的困惑 | 小：提供清缓存入口或按 mtime 失效 |
| 10 | `KnowledgeStore` 没有 `close()` / 上下文管理器：连接只能靠 GC 释放（`audit_store`、`search` 内部打开的连接尤其如此） | 低（Windows 上表现为文件被锁，实测 `WinError 32`；长驻进程下连接累积） | 调用方自行 `store.db.close()`（触及内部属性，与适配层边界冲突） | 产品代码无法在不碰内部属性的前提下释放连接；删除/轮换 DB 文件会失败 | 小：加 `close()` 与 `__enter__/__exit__` |
| 11 | 检索字段不含 claim 的 `predicate`，且 trigram FTS 对 <3 字查询回落 LIKE | 低（按能力名/对象检索不受影响；按"计划学习"这类谓词检索会 0 命中） | 无（属检索语义边界，已记录） | 无 | 小：把 predicate 纳入索引字段 |

---

## 8. 上游改进建议清单（按建议优先级）

1. **`render_claim_markdown` 补齐 `partial`**（§7-1）。建议：在"支持证据/反对证据"
   之外单列"部分支持"，或直接渲染 `evidence` 全量并按极性分组。附 Growth OS 的
   回归用例思路：`partial` 行必须出现在 Markdown 且不得被标成"反对证据"。
2. **抽取模型名持久化**（§7-2）。建议：`_call` 返回 `ModelResult` 而非 `value`，
   在批账本 payload 记 `{provider, model}`，并把 `model` 合并进 claim metadata
   （与 verifier 的做法对称）。这是"能力结论可复核"的必要条件。
3. **`caught` 判定改为计数/直查**（§7-3）。建议：以注入前/后
   `violations` 差值判定，或提供 `include_ids` 之外的直接 id 查询；sample 截断
   只用于展示，不用于判定。
4. **profile 作用域**（§7-4）。建议：`ingest_*` / `KnowledgeStore` 接受可选
   `profile` 参数，缺省仍读全局，保证向后兼容；并在文档中写明"全局 profile 只适合
   单领域包进程"。
5. **`.env.example` 两处修正**（§7-5、§7-6）：无参 store 回退路径、复核变量名，
   并补一句"照此配置可让独立复核静默失效"的警示。
6. **把"未分级"的消费方检查固化**：b.5b 的 6 个消费者当时是人工核对的，建议补
   回归测试，防后续改动重新引入 `None` 崩溃。
7. **文档化两个 hash 的分工**（`RawAsset.content_hash` = 原始字节 / `Source.content_hash`
   = 规范化文本），避免下游误用。
8. **（可选）为 `find_sources` 加表达式索引**，当前全表扫描 + Python 过滤。
9. **（可选）清理 `ingest_file` 的 `.html` 死分支**与 `PlainTextReader.supports`
   的 capability 合并判定。
10. **给 `KnowledgeStore` 加 `close()` 与上下文管理器**（§7-10）。当前下游若想释放
   连接只能访问 `store.db`，而收紧边界后这又是不允许的。
11. **（可选）把 claim 的 `predicate` 纳入检索字段**（§7-11）。
12. **提供"某文件是否可入库"的公共判定入口**（M3-b 新增待办）：下游的归档/批量入库需要预筛，
    而 evkg 只把路由表藏在 `TEXT_SUFFIXES` / `Profile.code` 里。M3-b 因此在本仓复制了一份后缀表用于预筛，
    形成"两处知识"——上游扩展语言表时下游会漏判（当前后果只是跳过并报告，不是静默入库）。
    建议上游暴露一个 `ingestible_kind(path) -> "code" | "text" | None` 之类的判定函数，供下游预筛复用。
13. **【已在本地修复 @ `db2de3a`】** `PdfReader` 与声明依赖 pypdf 不兼容（1 行缺陷，B-g2 发现）：`providers.py` 把 `bytes`
    直接传给 `pypdf.PdfReader`，实测 `AttributeError: 'bytes' object has no attribute 'seek'`，
    **PDF 经 V1 状态机入库 100% 失败**；同文件的 `OfficeReader` 已正确使用 `io.BytesIO`。
    修复：`Reader(content)` → `Reader(io.BytesIO(content))`（本地提交 `db2de3a`，并补 `tests/test_pdf_reader.py`
    6 项真实读取测试 —— 覆盖空洞已填）。该提交**未推送**，与其余 4 个提交一样待用户决定去向。
14. **V1 段落的页码级 locator**：`split_passages` 只产出 `{"ordinal": n}`，而识别阶段的
    `RecognitionSpan` 已带 `page`/`bbox`；结果是 PDF 证据无法自动定位回页，只能人工核对。
    建议在 `_save_source_passages` 里把 span 的页码（或页内偏移）写进 passage locator。

---

## 9. 决策记录：阻塞后续阶段 vs 可延后

### 9.1 阻塞（依赖它的阶段不能验收）

| ID | 事项 | 阻塞对象 | 解除条件 |
|---|---|---|---|
| B-g1 | evkg 依赖不可从他机复现：本地领先远程 4 个提交且不得推送 | 任何"可复现构建/换机/CI"要求（M2 起随时可能触发；M8 端到端验收必然触发） | 用户决定一种可获取形式（私有镜像 / 本地归档 / 允许推送），并把 `pyproject.toml` pin 到 commit SHA |
| B-g2 | 富格式（PDF/docx/xlsx）上传路径 0 端到端验证 | M3（Upload）开工 | M3 开工前先做一个 spike：真实 PDF 走 V1 状态机入库 + audit + locator 可核对性结论 |

#### B-g1 交付方案比较（2026-10-02 实测，evkg @ `28afbc0`，5 个提交）

判定标准（用户指定）：**可获取、可校验、可复现**。SHA 只解决"锁定哪一个版本"，
不解决"别处怎么拿到代码"，因此三者必须同时满足。

实测事实（全部在临时目录中完成，未改动任何工程文件）：

| 机制 | 实测结果 |
|---|---|
| `git bundle create --all` | **238,807 字节**；SHA-256 `10dafff49bb8e627007c4bb5cc3ddfcfce1108ef9b97c42763bf93a8b8c13801`；重新生成**字节一致**（同一状态可复现同一归档） |
| `git bundle verify` | HEAD = `28afbc0db7061d9717e307bf2bd0833f59fd8f51`，`records a complete history`，校验 ok |
| 从 bundle 克隆 | HEAD 与上述 SHA 一致，5 个提交，`git fsck` 无异常 |
| 裸仓镜像（bare clone） | HEAD 一致；`git ls-remote` 可解析 `HEAD`/`refs/heads/main` |
| **uv 层 pin**（scratch 项目，`file://` + `rev`） | `uv lock` 解析成功（24 包），`uv.lock` 记录 `source = { git = "file:///…?rev=28afbc0…#28afbc0…" }` —— **可复现 pin 在 uv 层成立** |
| `editable` + `git` | uv 拒绝：`cannot specify both git and editable` —— **pin 与当前 editable 开发循环不可兼得** |

方案对比：

| 方案 | 可获取 | 可校验 | 可复现 | 代价 | 需要授权 |
|---|---|---|---|---|---|
| **A. 本地归档**：bundle（传输/归档）+ 裸仓（git 可寻址） | 文件可放任意介质/共享盘；裸仓供 uv 寻址 | bundle SHA-256（字节可复现）+ commit SHA | 是（uv `file://`+`rev` 已实测） | 手工分发；无集中更新通道；每台构建机需放置裸仓 | 无 |
| **B. 私有镜像**（私有 GitHub / 自建 Gitea / NAS 裸仓 + ssh） | URL 克隆 | commit SHA（可加签名 tag） | 是（uv `git`+`rev`） | 需建服务/账号与凭据；代码离开本机；维护成本 | **需要**用户创建并授权 |
| C. 推送 `redmaplewww/evkg` | — | — | — | 违反现行约束，对外发布不可撤回 | 需明确授权（不建议） |
| D. vendor / 子模块 | 随主仓 | 随主仓 | 是 | 与 Q1「不 fork」冲突，失去上游身份与同步能力 | 无（不建议） |

**决定（用户 2026-10-02 确认）：维持"不推送"约束，采用方案 A；方案 B 作为出现多机/CI 时的
升级路径**（bundle 可作为 B 的初始种子：从 bundle 克隆 → 推入私有镜像）。理由：A 零授权、
零外部暴露、已验证；B 的价值（集中更新、CI 拉取）在单机阶段用不上。

pin 的时机与代价：**开发期继续用 path 依赖（保留 editable 循环），发布/CI 前再切换**
为 `git`+`rev`（步骤已实测）。切换后 evkg 变为只读依赖，改上游要走镜像仓并 bump rev ——
这是"可复现"的必要代价，应记入发布流程。

落地结果（**2026-10-02 已完成并验证**，EV-049）：

| 项 | 值 |
|---|---|
| 主副本 | `D:\projects\_evkg-archive\evkg-28afbc0.bundle`（238,807 字节） |
| 第二副本 | `C:\Users\Lenovo\evkg-archive\`（两副本 SHA-256 一致） |
| bundle SHA-256 | `10dafff49bb8e627007c4bb5cc3ddfcfce1108ef9b97c42763bf93a8b8c13801` |
| commit | `28afbc0db7061d9717e307bf2bd0833f59fd8f51`（5 提交，含基线 `a448f44`） |
| 验证 | `git bundle verify` = 完整历史/ok；克隆 HEAD 一致；5 提交；`git fsck` 零输出 |
| 登记 | 同目录 `evkg-bundle-manifest.txt`（含哈希、commit、验证日期、恢复命令、约束）；`PROJECT_VERSIONS.md` 依赖基线表 |
| **未完成项** | 第二副本仍在 C: 盘；若与 D: 同物理盘，抗物理损坏需另存移动硬盘/云盘（待用户执行，未计入验收） |

恢复命令（详见 manifest）：

```bash
sha256sum <bundle>                      # 期望 10dafff4…3801
git clone <bundle> evkg && git rev-parse HEAD   # 期望 28afbc0…
git clone --bare <bundle> evkg-mirror.git       # 供 uv git+rev 寻址
```

注意事项：① 方案 A 的"可获取"取决于归档文件放到对方能拿到的地方（CI 亦然）；
② 多机时裸仓路径应选**位置无关**的 URL（UNC / ssh），否则各机 `uv.lock` 里的 URL 会不同
（SHA 仍可校验，但锁文件会漂移）；③ 归档现存两处（D: 主 + C: 第二副本），
抗物理损坏的第三副本待用户放到移动硬盘/云盘。

### 9.2 可延后（附触发条件，触发即升级为阻塞）

| ID | 事项 | 延后理由 | 触发条件（tripwire） |
|---|---|---|---|
| D-g1 | 实例级 profile | Q4 已定单用户；当前单 profile 路径无污染 | 需要两个领域包并存、或并发切换 profile、或引入多用户 |
| D-g2 | 抽取模型持久化 | 档案已如实披露缺失；不伪造 | ~~**M4 验收前必须解决**~~ **已解决（2026-10-02，M4-a）**：evkg `9a21552`（本地提交，未推送）——provenance 取自实际返回值并写入 claim metadata 与批账本；4 项读取测试；档案渲染器三态显示 |
| D-g3 | evkg 渲染器 partial 修复 | 自建渲染器 + 回归已覆盖 | 若复用 evkg 前端档案页，或再有人调用 `render_claim_markdown` |
| D-g4 | `caught` 判定修复 | QG2 流程已改用双向测量 | 若想省掉自建注入流程、直接用内置自测 |
| D-g5 | 适配层 profile 断言 | 低概率（需绕过 `open_store`） | 修成本 ~3 行，建议随下一次 adapter 改动一并做 |
| D-g6 | 其余低severity项（§7-5/7/8/9） | 不影响当前路径 | 随上游提案批量提交 |

**M1 技术 spike 到此结束**：R1–R4 与 D1 已逐项给出结论与证据；依赖策略判定为
**有条件依赖**（§6.3 的 C1–C5）；spike 未发现"当前调用面不可用"的证据，
也未发现支持"组件整体可直接依赖"的证据。

---

## 10. 证据索引（本文件引用）

| 证据 ID | 内容 | 位置 |
|---|---|---|
| EV-042 | 独立复跑 evkg 101 项（正序 + 逆序）与 Growth OS 73 项，exit 0 | 本会话命令输出（见 `PROJECT_ACCEPTANCE.md`） |
| EV-043 | D1 双实例隔离实测（含并发交错、初始化顺序、公开 API 隔离、适配层 footgun） | `artifacts/m1g/run_d1_profile_isolation.py` `135dd3a5c31f`、`d1_profile_isolation.json` `dee378cf7a22` |
| EV-044 | R4 实库审计 + 追溯链核验（审计前后逐表 payload 哈希一致） | `artifacts/m1g/run_r4_evidence.py` `c02e211877d1`、`r4_evidence.json` `27139373f82e` |
| EV-045 | 三项上游缺陷在真实数据/副本上复现（partial 哨兵对照 / 模型名缺失 / caught 截断） | 同上 `r4_evidence.json` |
| EV-046 | R3 行级覆盖实测（无新依赖，`sys.settrace` 插件） | `artifacts/m1g/line_coverage_plugin.py` `971a1fad02b0`、`r3_coverage.json` `22b7f1ce87ff` |
| EV-047 | M1 完成条件补跑：`init`（CLI，35 张 schema 表）与 `reindex`（FTS5：109 段落 + 2 主张、幂等、审计仍 pass、检索 4/5 命中）在真实材料/临时空库上的实际输出 | `artifacts/m1g/run_reindex_search_check.py` `8532375183a8`、`reindex_search_evidence.json` `316a1fb1af07` |
| EV-048 | B-g1 交付方案实测：bundle 字节可复现（238,807 字节 / SHA-256 `10dafff4…3801`）、bundle 校验与克隆、裸仓镜像、uv `file://`+`rev` pin 成立、`editable` 与 `git` 互斥 | 见 §9.1 与 `PROJECT_ACCEPTANCE.md` EV-048（命令输出，临时目录已清理） |
