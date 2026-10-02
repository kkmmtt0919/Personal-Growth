# B-g2 判定记录：PDF spike（独立验证）

> 依据 `docs/M3-PLAN.md` v1.0 §5（三项验证 + 结果分支）；**独立验证，不是 M3-b 的扩展**。
> 素材：真实中文 PDF（5 页行政通知，文字型，132,946 字节）——用户文档**只读**，
> 产物只记录结构性事实，**不含任何正文**；临时库用完即删（已确认删除）。
> 命令：`python artifacts/bg2/run_pdf_spike.py "<pdf 路径>"`；原始结果 `pdf-spike-result.json`。

## 结论（按分支规则）：**不通过（现状）→ PDF 保留为不支持格式并记录缺口**

**但缺口是一行可修的缺陷，不是根本限制** —— 下面同时给出"现状"与"若修好后会怎样"的两轮证据。

## 一、发现的缺陷（阻塞 PDF 入库的唯一原因）

| 项 | 内容 |
|---|---|
| 位置 | `evkg/src/evkg/ingest/providers.py` 的 `PdfReader.read` |
| 症状 | **A 轮（现状）**：`job.status=failed`，`AttributeError: 'bytes' object has no attribute 'seek'`（失败已如实记录在库 `processing_errors`） |
| 根因 | 把 `bytes` 直接传给 `pypdf.PdfReader`；pypdf 需要流或路径 |
| 为什么一直没被发现 | **evkg 测试对 PDF 零覆盖**；而同一文件里的 `OfficeReader` 反而正确地用了 `io.BytesIO(content)` |
| 最小修复 | `Reader(content)` → `Reader(io.BytesIO(content))`（**1 行**） |

## 二、三项验证结果

### 第一项：真实中文 PDF 能否通过 V1 状态机入库

| 轮次 | 结果 |
|---|---|
| **A（现状）** | ❌ **不能**：`failed`，错误同上；无 source、无 passage |
| **B（打上那一行修复的诊断轮）** | ✅ **能**：`status=awaiting_clarification`，建立 source（`kind=compilation`），**40 个段落** |

（B 轮只在 spike 脚本内用等价 reader 替换，**未修改 evkg 源码**。）

### 第二项：`audit_store` 是否通过（B 轮库）

✅ **pass / 0 violations**，10 项不变量检查全部 0（counts：1 source / 40 passages）。

### 第三项：locator 能否定位并核对原文

| 检查 | 结果 |
|---|---|
| locator 形状 | **40/40 只有 `ordinal`**（归一化文本内的序号） |
| 页码级定位 | ❌ **不可用** —— 识别阶段确实拿到了 5 个带 `page`/`bbox` 的 span，但**没有写进 passage locator** |
| 对原始 PDF 逐字还原 | ❌ **不保证** —— 文本经过 `normalize_document`（空白折叠、重排行） |
| 对归一化文本的完整性 | ✅ **完整分区**：40 个段落拼接后与归一化文本**去空白后逐字一致**（字符数 2127 = 2127，缺失 0 / 多余 0）；98.6% 的"覆盖差"全部是空白 |
| 可核对性（缓解） | 库内保留 `raw_asset`（原始字节）、`recognition spans`（含页码）、`normalized_document` → **可人工核对页级来源**，但不能自动回页 |

## 三、PDF 的支持边界（若采纳那一行修复）

* **能**：入库并产出段落；段落内容可对归一化文本逐字核验；审计通过；失败会在库中留档。
* **不能**：页码/坐标级 locator；对原始 PDF 的逐字还原保证。
* **入库后会要求澄清**：该素材产生 3 个 blocking 问题（完整性维度），上传流程需要处理这一步。
* **尚未接入产品策略**：V1 路径的 source metadata 只有 `{ingestion_job_id, completeness_pending}`，
  **没有成长标签**（`growth_evidence_type` / `growth_channel` / `growth_attribution`）——
  若 PDF 要进产品，适配层需要新增 V1 入口并保证归属/通道贯穿（后续步骤，不在 B-g2）。

## 四、附带发现（环境与集成）

1. **`uv sync --extra office` 会移除 dev 工具**：本项目把 `dev` 也定义为可选 extra，正确命令是
   `uv sync --extra dev --extra office`。已实测踩到并把环境恢复（pytest/ruff/pypdf 均在位）；`uv.lock` 未变。
2. **pypdf 对部分 PDF 会打印解析告警**（`Multiple definitions in dictionary...`）到 stderr，不影响本次结果，
   但批量入库时应把它们收进日志而不是任其噪声化。

## 五、需要你决策（B-g2 的下一步）

| 选项 | 内容 | 代价 |
|---|---|---|
| **A（建议）** | 为这一行缺陷提交**上游修复**（evkg commit），然后**重跑 B-g2** 得到真正的"通过"判定与产品级结论 | 1 行上游改动（按 M1 惯例需你确认）；重跑一次 spike（纯本地，无模型调用） |
| B | 维持现状：PDF 记为**不支持格式**，缺口按本记录留档 | 上传 PDF 的功能要等到缺陷修复后才能做 |

无论选哪个，**页码级 locator** 都是独立的上游改进项（已登记）：建议上游把 recognition span 的页码写进 passage locator，
否则 PDF 证据永远只能人工核对页码。
