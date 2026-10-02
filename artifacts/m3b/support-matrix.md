# M3-b 汇总：本地材料 ingestion —— 实际支持范围、已知限制与验证结果

> 生成时间：2026-10-02 · 对应 `docs/M3-PLAN.md` v1.0 §5 的 M3-b
> 结论：**四类本地材料（MD / TXT / 代码 / ZIP）的可信准入链路已打通**，归属与通道策略全程保留，无旁路入口。

## 一、实际支持范围（以源码与测试为准，不凭文档推测）

| 材料 | 后缀 / 判定 | 路由（evkg 决定，非本仓猜测） | 来源类型 | 段落定位 |
|---|---|---|---|---|
| Markdown / 纯文本 | `.md` `.markdown` `.txt` `.text` `.csv` `.json` `.log` | `ingest_file`（文本快路径） | 由证据类型决定（`uploaded_doc` → `compilation` 等） | `{"ordinal": n}`；空白折叠（既有行为） |
| 源码 / 配置 | evkg 默认语言表：`.py` `.java` `.ts` `.go` `.rs` `.sh` `.yaml` `.toml` `.ini` `.sql` … + 无扩展名构建文件（`Dockerfile` `Makefile` …） | `ingest_code_file`（源码快路径，**强制 `kind=code`**） | `code` | `{"path","language","line_start","line_end"}`；缩进保留、可回原文逐字核对 |
| **ZIP（M3-b 新增）** | `.zip`（`zipfile.is_zipfile` 校验） | 容器级封装：**逐条目**调用唯一入口 `adapter.ingest_document` | 同上（逐条目继承调用方给的类型） | 条目自身的定位方式；另在 metadata 记录 `growth_archive_path` / `growth_archive_entry` |
| 富格式（PDF / docx / xlsx / HTML） | — | **不支持**（`ValueError` → 适配层翻译为 `EvidenceError`） | — | 属 **B-g2 / V1 状态机**范围，M3-b 明确跳过并报告 |

来源判定的单一事实来源仍是 evkg 的路由（`Profile.code` + `TEXT_SUFFIXES`）；本仓的预筛表只用于
"要不要解包尝试"，**不一致时以 evkg 为准**。

## 二、ZIP 处理规则（新增能力的边界）

| 规则 | 行为 |
|---|---|
| 逐条目结果 | `ok` / `skipped` / `failed` **每条都可见**，含跳过原因；不静默丢弃 |
| 单条目失败 | 记录后继续处理其他条目（`failed` 必须被调用方看见） |
| 路径安全 | 绝对路径 / 盘符 / `..` 穿越 → 跳过；解包目标必须落在工作目录内（双重校验） |
| 目录条目 | 跳过（不猜） |
| 体积与数量上限 | 归档 ≤20MB、条目 ≤5MB、解包总量 ≤50MB、条目数 ≤200（`ArchiveLimits` 可注入） |
| 稳定解包目录 | `<归档名>-<内容哈希前 8 位>` → 同一归档重复入库命中**同一批 `source_id`** |
| 格式不支持 | 跳过并说明（PDF 明确指向 B-g2） |

实测（真实运行，非手写）：5 条目归档 → **2 ok / 3 skipped / 0 failed**；
两个入库条目的 metadata 均为 `user_declared / user_evidence / repo_artifact` + 正确的归档条目名。

## 三、已知限制（如实记录）

1. **文本路径会折叠空白**：Markdown/TXT 经既有文本切分（`re.sub(r"\s+", " ")`），段落内换行变空格。
   这是 evkg 的既有行为，M3-b 未改动；代码路径不受影响（缩进与行号保真）。
2. **ZIP 预筛表与 evkg 路由表是两处知识**：若上游扩展语言表，本仓预筛会漏判（后果是**跳过并报告**，
   不是静默失败）。彻底解法需要上游提供"这个文件能不能入库"的公共判定入口 —— 记入上游/待办，
   M3-b 不做。
3. **归档改名 = 新来源**：身份按路径（既有约定，M1-b.5c），改名或换目录会产生新 source。
4. **旧解包目录不自动清理**：内容变化后新旧两个哈希目录并存（`data/extracted/`，已 gitignore）。
5. **嵌套归档不处理**：`.zip` 里的 `.zip` 按"格式不支持"跳过。
6. **压缩包内 PDF 不在本步**：明确留给 B-g2（V1 状态机路径尚未验证）。

## 四、验证结果

| 项 | 结果 |
|---|---|
| 新增测试 `tests/test_local_ingestion.py` | **35 项全绿**（格式识别 17 / 内容提取 2 / 来源定位 4 / ZIP 成功·跳过·失败·安全 8 / 归属通道贯穿 3 / 无旁路 1） |
| 全量回归 | Growth OS **222 项**全绿；evkg **101 项**全绿；ruff 全过 |
| 边界检查（随 pytest） | 证据层禁 sqlite3/裸 SQL、`store/` 只碰 `g_` 表、M2 流程零写入 evkg 表 —— 全部通过 |
| 归属 / 通道贯穿 | ZIP 逐条目 metadata 保留 `growth_attribution` / `growth_channel` / `growth_evidence_type`；保留键不可被 `extra_metadata` 覆盖（有测试） |
| 无旁路 | 用 spy 断言：归档路径逐条目调用 `adapter.ingest_document`（调用次数 = 可入库条目数，参数一致） |
| 数据边界 | 真实库逐表内容哈希与计数**与 M3-a 锚点逐项一致**（8/8 表；3/109/2/6）；未写入任何 `g_` 表 |
