# G6-c · 用户返回总验收与冻结范围复核

2026-10-05。**G6 在已冻结的确定性只读范围内验证通过**；完整 PRD MVP 和发布仍未验收。

## 本轮结果

- 持久化重开十项检查全部通过：实践 3→4、理解保持 2、下一步引用开放理解缺口、长期偏好引用持久化用户陈述。
- 当前 Growth OS 全量 452 项、上游 evkg 全量 111 项通过；无失败、跳过或错误。
- QG1：用户证据库与返回 Demo 的独立副本，故障注入前后 audit 均 pass / 0 violations。
- QG2：两个副本均 caught，清理后除允许追加的 audit_log 外数据表内容与计数恢复。
- QG3：当前完整回归包含评级规则与返回摘要反例；没有把缺少评级解释成零级。
- QG4：扫描 Git 已跟踪和未忽略的新文件，零密钥命中；.env 被忽略且未跟踪。报告不保存任何匹配的凭据值。
- QG5：本仓与上游全量测试通过。backend/tests/G6 verifier 的 ruff，以及前端 build/lint 均通过。
- 用户库与返回 Demo 的逐表内容和计数在本轮前后完全一致。
- 改版页面已有 53 项浏览器断言通过，1440 / 1024 / 390px 三页均无横向溢出；当前源码与实截图哈希记录在 result.json。

## 历史门的复核口径

G1–G5 的历史通过记录和产物重新读取、记录 SHA-256，日期均在 90 天有效期内。当前回归重新验证相关业务行为；历史真实模型会话不在本轮重新执行，也不续期。

G1 截图仍为历史回放；G2 是冻结基线中的全量七条追溯、确定性抽五条；G3 使用 RAG 材料和 NULL/证据不足语义。它们不冒充原 PRD 的实时 UI、随机抽样或 Memory 示例。

## 范围与复现

返回输出使用确定性模板；材料、长期偏好及次日时钟为受控构造。零真实模型请求。上传写入口、实时目标澄清、OAuth/私有仓库、Evidence 攻击详情、Mentor Chat、外部通知与自动重建仍未实现；依赖归档刷新、发布 commit pin、独立验收证据库自举也保留。

新增只读核对脚本：scripts/verify_g6_final.py。它先读取当前两份回归 XML，再核对持久化来源并审计临时副本，不覆盖旧 G6-a/b 报告。

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pytest tests -p no:cacheprovider -o addopts='' --junitxml=artifacts/gates/G6/g6c/growth-regression.xml -q
# evkg 回归在其仓库运行，但 JUnit 和临时目录均指向本工作区；详见 validation.json。
.\.venv\Scripts\python.exe scripts/verify_g6_final.py
```

result.json 是本轮机器判定，validation.json 记录工程检查；growth-regression.xml / evkg-regression.xml 为本轮完整测试结果。当前 UI 截图引用 artifacts/frontend-redesign，旧 G6 来源展开截图保留为历史证据，不代表新布局。
