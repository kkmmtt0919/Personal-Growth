# M3 Gate 判定记录：证据接入（Evidence Ingestion）

> 判定日期：2026-10-02 · 计划基线：`docs/M3-PLAN.md` v1.0（用户确认）
> 执行：`artifacts/m3gate/run_m3_gate.py`（同一临时库端到端；无模型调用）；
> 原始结果 `m3-gate-result.json`；账本 **EV-065**。
> 结论：**通过（含两条已记录的边界）**

## 一、ROADMAP 完成条件逐项

| # | 条件 | 实测 | 结果 |
|---|---|---|---|
| 1 | 上传 PDF 与 Markdown，均产出 passages **且可检索** | Markdown 1 段；PDF（真实中文通知，5 页）**40 段**；FTS 索引重建 `mode=fts`（237 段 + 5 claim）；查询命中：Markdown 1 段、PDF **1 段**（检索词"关于做好"由 PDF 原文派生） | ✅ |
| 2 | 代码 ZIP 能抽取技术栈证据 | 归档 3 个文件全部入库（0 跳过）；code-kind passages 带 `language` locator：**java / python** | ✅ |
| 3 | 公共仓库产出技术栈清单与 ≥3 条 capability claim | `kkmmtt0919/mytset-rag`：20 文件入库；技术栈 **java / python / xml / yaml**；**5 条材料口径 claim**（RAG/Java 源码/MCP/测试用例/向量检索）；仓库证据可检索（查询 RagService 命中 4 段） | ✅ |
| 4 | 未授权仓库数据不被读取；token 不以明文出现在账本或日志 | 克隆环境禁用交互（`GIT_TERMINAL_PROMPT=0`、`GIT_ASKPASS=echo`）；对不存在的仓库**快速失败**（`rc=128 not found`，无凭据、无提示）；**119 个被跟踪文件全量扫描：0 处明文密钥**（占位符放行） | ✅ |
| 5 | 上传的领域资料（JD）标为 `domain_reference`，不产生用户能力断言 | JD（合成样本）通道 = `domain_reference`，`can_support_user_claim=False`，**不在** `user_evidence`；抽取 27 个技术词（外部参考用途） | ✅ |

## 二、质量门

| 项 | 实测 |
|---|---|
| `audit_store` | **pass / 0 violations**（10 项不变量全 0） |
| 真实库边界 | 逐表**内容哈希**与计数与 M3-a 锚点**一致**（`artifacts/m3a/evidence-anchors.json`） |
| 回归 | Growth OS **267 项**、evkg 107 项全绿；ruff 全过 |
| 临时库 | 已删除（无残留） |

## 三、两条必须保留的边界（Gate 通过 ≠ 这两件事已解决）

1. **PDF 的适配层入口仍未建**：条件 1 的 PDF 部分是通过 **V1 状态机直接驱动**达成的（B-g2 范围）；
   产品上传路径需要适配层新增 V1 入口并让 attribution/channel 策略贯穿（见 `M3-PLAN` §5 的 PDF 支持边界）。
   —— 因此"Gate 通过"不表示"PDF 已可作为产品上传功能可用"。
2. **页码级 locator 仍缺**（上游清单第 14 项）：PDF 段落只有 `ordinal`，对原 PDF 不保证逐字；
   内容可对归一化文本完整核验。

## 四、Gate 过程中发现并修掉的两个问题（如实记录）

1. **git 子进程解码崩溃**：中文 Windows 上 git 的错误输出不是 UTF-8，`subprocess.run(text=True, encoding="utf-8")`
   在 reader 线程抛 `UnicodeDecodeError`——它把"仓库不存在"这种可解释的失败变成了难诊断的崩溃。
   已抽出 `github.run_command()`（`errors="replace"`）并补回归测试（非 UTF-8 字节 → 替换而非崩溃）。
2. **密钥扫描的两处误报**：① 扫描范围应是**被 git 跟踪的文件**（`data/`、`.env`、`artifacts/**/tmp/`、`*.bak`
   都已 gitignore，不属于提交物）；② 正则 `\s*` 会跨行，把 `.env.example` 里**空值**后面的下一行变量名当成值。
   修正后：119 个跟踪文件、0 命中。

## 五、判定

**M3 Gate 通过，M3 正式收口。** 四个通道（本地材料 / 公共仓库 / JD 外部参考 / PDF）均已验证；
证据链 `source → passage → evidence → material claim` 端到端可走通且审计通过。
用户能力分级（assessment）不在 M3，属 **M4**。
