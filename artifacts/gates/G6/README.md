# G6 · 用户隔天返回

2026-10-05：**G6-c 已在冻结的确定性只读范围内验证通过（EV-086）**。本仓452项、上游111项回归通过，QG1–QG5新鲜复核、两份原数据库零变更。最终判定与范围见 [G6-c 报告](g6c/README.md)。下文保留 G6-a/b 阶段的历史验证口径；完整 PRD MVP 与发布未验收。

## 已实现

`GrowthReturnAgent.summarize` 使用确定性模板，返回能力变化、当前状态、下一步与长期偏好。理解/实践分别比较；NULL 表示缺少评级，不冒充 0 或低能力。

快照包含评定历史集合，读取时逐项与源评定核对，再按现有 `created_at + rowid` 顺序恢复对应快照的最新结果。当前快照必须包含目标的最新评定；跨用户、目标不匹配、伪造/重复记录、倒序基线、未来快照与过时快照拒绝。原 `latest_assessment` 无过滤参数时行为保持原样。

下一步来自已存在的 active/proposed/blocked 任务或 open gap，携带 task/gap/assessment 标识。原缺口已关闭而任务仍待执行时只提示核对任务，不重复宣称缺口。长期偏好只引用 active profile 的明确偏好文本与 `statement_` 用户陈述；缺少基线或偏好会明确说明。

新增只读 API：

```text
GET /api/return/{goal_id}?current_snapshot_id={id}&baseline_snapshot_id={id}
```

基线参数可省略；当前快照必须指定。参数缺失或来源无法核验返回 422，POST 返回 405。默认服务用户仍为 local。

## 复现与证据

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe artifacts/gates/G6/run_g6a.py
.\.venv\Scripts\python.exe -m pytest tests/test_return_summary.py -o addopts='' -q
```

- `g6a-result.json`：受控提交经过真实业务闭环后，返回实践 3→4、理解维持 2、下一步引用理解缺口、偏好引用记忆与用户陈述；六项检查全部通过。
- `g6a-regression.xml`：返回摘要及相关存储/Memory/API 回归 **37 项通过**。
- `g6a-full-regression.xml`：Growth OS 全量 **449 项通过**。
- 后端/tests/运行器 ruff 通过，`git diff --check` 通过。
- 零写入用 `PRAGMA query_only=ON` 与前后完整数据库 dump 比较验证。

这是受控业务演练，使用 FakeGateway、零真实模型请求，时间通过注入模拟。本阶段没有关闭后重新打开连接，也没有 UI 截图；不声称完成真实模型导师推理或完整 G6。

## 下一步

G6-c：核对三项输出与反例，对 G6 作实际判定；再复核 G1–G5 证据有效性与 QG1–QG5（含上游测试），保留完整 PRD 与冻结交付范围的区别。

## G6-b · 新进程持久化与页面（已完成）

运行器：

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe artifacts/gates/G6/run_g6b.py
```

默认创建 `data/demo-return`，不覆盖原 `data/demo` 或用户库。首次运行由种子记录长期偏好、前快照，经过现有提交闭环生成后快照；种子关闭连接后，运行器启动全新 Python 进程，只从 manifest 与数据库读取来源。后续运行复核已有场景，不覆盖数据。

十项检查全部通过：不同进程、两份快照、实践 3→4、理解保持2、下一步引用开放理解缺口、偏好来源持久化、前后评定可核对、API 零写入、POST拒绝、模拟标记明确。

首页通过新增只读 `GET /api/return-demo/{goal_id}` 加载三项输出与来源引用。旧 Demo 未提供返回上下文时返回404，页面不编造摘要；上下文过时返回422。长期偏好不会因返回请求被修改，也不会自动生成任务。

验证结果：定向回归 **26 项通过**，最终全量 **452 项通过**，后端 ruff 与前端 build/lint 通过。全量首轮发现快照篡改反例偶尔把维度改成原值，已修成必定切换维度并全量重跑通过。

证据：`g6b-result.json`、`g6b-regression.xml`、`g6b-full-regression.xml`、`g6b-verification.json`。
截图：`screenshots/return-desktop.png`、`return-mobile.png`、`return-sources.png`；均来自实际 API 页面，逐张查看。`viewport-checks.json` 验证1280px与390px宽度不溢出，同时核对三项标题与来源文本。

截图复现需先运行两端与本机无界面 Edge（仅本地调试端口9227），再执行 `node scripts/capture_g6b.cjs`。该工具设定精确视口，并展开来源详情；不生成或替换页面业务数据。首次窄屏命令截图受浏览器窗口最小宽度影响，已用精确视口重新生成。浏览器首次加载时曾出现跨域失败，最终实际加载和截图均成功，网络错误会使截图脚本退出失败。

材料、偏好和次日时钟均明确受控；零真实模型请求。完整 G6 的实际判定仍待 G6-c。
