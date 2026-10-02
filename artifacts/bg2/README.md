# B-g2 判定记录：PDF spike（独立验证）—— **通过（含明确边界）**

> 依据 `docs/M3-PLAN.md` v1.0 §5；两项独立问题按用户要求**分开记录**，不互相包装。
> 素材：真实中文 PDF（5 页行政通知，文字型，132,946 字节）——用户文档**只读**，
> 产物只含结构性事实（**无正文**）；临时库用完即删（已确认删除）。
> 命令：`python artifacts/bg2/run_pdf_spike.py "<pdf 路径>"`；原始结果 `pdf-spike-result.json`。

## 一、三项验证结果（在修复后的真实代码上重跑）

| # | 验证项 | 结果 |
|---|---|---|
| 1 | 真实中文 PDF 能否通过 V1 状态机入库 | ✅ **能**：`awaiting_clarification`，建立 source（`kind=compilation`），**40 个段落** |
| 2 | `audit_store` 是否通过 | ✅ **pass / 0 violations**（10 项不变量检查全 0；counts：1 source / 40 passages） |
| 3 | locator 能否定位并核对原文 | ⚠️ **如实记录**：`40/40` 段落只有 `ordinal` → **不具备 page-level locator**；对**原始 PDF 不保证逐字**；但对**归一化文本**是完整分区（去空白后逐字一致，缺失 0 / 多余 0），即**内容不丢** |

**交叉印证**：`as-is`（修复后的 evkg 代码）与 `diagnostic_equivalent`（脚本内等价实现）两轮完全一致
（状态、段落数、source id 相同）——证明上游那一行修复就是关键改动，且可防将来回归。

## 二、问题 #1：`bytes` 缺陷（**已修复上游**）

| 项 | 内容 |
|---|---|
| 症状 | 修复前 `PdfReader.read` 把 `bytes` 直接交给 `pypdf.PdfReader`（需要流/路径）→ `AttributeError: 'bytes' object has no attribute 'seek'`，**PDF 入库 100% 失败** |
| 为什么没被发现 | evkg 测试对 PDF **零覆盖**（既有测试只用假 PDF 测路由，从不读内容）；同文件 `OfficeReader` 反而正确使用了 `io.BytesIO` |
| 修复 | `Reader(content)` → `Reader(io.BytesIO(content))`（1 行）· **evkg `db2de3a`** |
| 配套 | 新增 `tests/test_pdf_reader.py` **6 项真实读取测试**（手工构造最小合法 PDF 含正确 xref，不依赖 pypdf 私有 API；每页一个带页码的 span；无文本 → `needs_review`；`supports` 契约） |
| 范围纪律 | **只改这一行 + 补测试**：未动 locator 设计 / V1 状态机 / completeness / `audit_store` / 适配层 / M3-c |
| 验证 | evkg **107 项全绿**（原 101 + 新 6）；ruff **未新增**（存量 25） |

## 三、问题 #2：页码级 locator 缺失（**独立开放项，不因 #1 修复而视为通过**）

* passage 由 `split_passages` 生成，locator 只有 `{"ordinal": n}`；
* 而识别阶段的 `RecognitionSpan` 已经带 `page` 与 `bbox`（本素材 5 个 span，5 页均有文本）——**信息在，只是没写进 locator**；
* 后果：**PDF 内容可验证（对归一化文本逐字核验），但无法自动定位回 PDF 页码/坐标**；
* 定位：这是独立的上游改进项（上游清单**第 14 项**），**不阻止**"PDF 基础 ingestion 是否可用"的判断
  —— 按 M3-PLAN §5 第三项的要求（"如实说明 locator 能否回原文核对"），本项已按要求如实记录，**既不伪装为失败，也不说成完整通过**。

## 四、PDF 的支持边界（据此写入 M3 基线）

* **能**：经 V1 状态机入库并产出段落；段落内容可对归一化文本**逐字核验**；审计通过；识别失败/无文本会 `needs_review`；入库失败会在库中留档（`processing_errors`）。
* **不能**：页码/坐标级 locator；对原始 PDF 的逐字还原保证。
* **入库后会要求澄清**：本素材产生 **3 个 blocking** 完整性问题（作者/时间/来源等维度），上传流程必须处理这一步。
* **尚未接入产品策略**：V1 路径的 source metadata 仍只有 `{ingestion_job_id, completeness_pending}`，**没有成长标签**（`growth_evidence_type` / `growth_channel` / `growth_attribution`）→ PDF 若要进产品，适配层需新增 V1 入口并保证归属/通道贯穿（**M3 后续步骤**，不在 B-g2）。
* **本次未判定**：PDF 段落的"可检索"（FTS）—— 那是 M3 Gate 的完成条件之一，B-g2 只回答上述三项。

## 五、附带记录

1. **环境陷阱**：`uv sync --extra office` 会**移除 dev 工具**（本项目把 `dev` 也定义为可选 extra）。
   正确命令：`uv sync --extra dev --extra office`。已实测踩到并恢复；**`uv.lock` 未变**，依赖策略不变。
2. **pypdf 告警**：对部分 PDF 会向 stderr 打印 `Multiple definitions in dictionary...` 之类的解析告警；
   批量入库时应收进日志，不要任其噪声化。
3. **归档待刷新（待办）**：B-g1 的 bundle 归档指向 `28afbc0`，本地现领先 **5** 个提交（新增 `db2de3a`）；
   需要时按 B-g1 流程重新生成 bundle 并更新哈希（不在本次范围）。
