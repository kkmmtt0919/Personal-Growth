# I5 · 本地交互阶段验收

2026-10-06。范围：独立受控实验库中的任务操作、理解回答与实践文件提交、既有TaskLoop重评和持久化归因。固定绑定规则、零真实模型请求；完整PRD MVP、真实模型效果与发布尚未验收。

## 验收内容

- 新实验从实践3/理解2开始，文件提交得到实践4/理解2，理解回答提交得到实践4/理解3。两条链都有来源、主张、绑定、前后评定与完整trace。
- 子进程重开库后，两次请求重放与原结果一致，各只有一条提交；重放前后领域库逐表内容不变。
- QG1：用户库及新实验的独立副本，故障注入前后audit均pass。
- QG2：副本伪造引文均caught，清理后除audit_log外内容与计数恢复。原库不注入故障。
- QG3：完整回归包含无证据不判零级、两维度独立、完成不等于升级及TaskLoop不得直接写等级或绑定的守卫。
- QG4：扫描Git跟踪和未忽略文件，仅记录命中位置，不保存凭据；.env须被忽略且未跟踪。
- QG5：本仓及上游完整回归、Python静态检查、前端build/lint。
- 原用户库、只读Demo、返回Demo与现有交互库四份逐表内容不变。

result.json为最终判定，scenario.json为新实验与子进程核对，两个JUnit为本轮完整回归。I3/I4两份浏览器报告各12项本轮读取核对，不冒充重拍或重执行；截图保留在上级目录。最终源码SHA记录在result.json。

## 复现

项目根目录使用现有Python环境：

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/verify_interaction_final.py --prepare
.\.venv\Scripts\python.exe -m pytest tests -q --junitxml=artifacts/interaction/i5/growth-regression.xml
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -m pytest D:/projects/evkg/tests -q -p no:cacheprovider -o addopts='' --basetemp=tmp/i5-upstream --junitxml=artifacts/interaction/i5/evkg-regression.xml
.\.venv\Scripts\python.exe scripts/verify_interaction_final.py
```

--prepare只创建本工作区临时实验；原库只读核对，故障审计仅在副本执行。普通模型失败可手动幂等重试；进程中断请求继续fail-stop，拒绝新ID绕过，自动恢复未交付。

文本须UTF-8，文件最大2MB，仅本地单进程服务，开发期path依赖保留。实时目标澄清、独立通用材料上传、Mentor Chat、OAuth、外部通知、依赖发布pin与真实模型交互验收仍开放。本轮不重执行或续期历史G1–G6真实模型记录。
