# 本地任务交互验证记录

最终状态：I1–I5在受控本地范围验证通过。I5总判定26项，本仓478项与上游111项当前回归通过，详见 [I5报告](i5/README.md)。下文保留各小步当时的结果与边界。

2026-10-06。独立实验库与任务状态 API、页面按钮已实现。提交与重评入口尚未实现；本轮没有真实模型请求，也没有浏览器实测，不以构建结果替代页面验收。

- 定向测试16项通过：独立种子、非法状态拒绝、原因必填、完成任务不可修改、外部Origin拒绝、原只读API无写路由、操作不写提交与评定。
- 全量执行456项：454项通过，2项预算测试因Windows输出编码与UTF-8读取不一致失败；设置项目约定的 `PYTHONUTF8=1` 后，预算测试文件5项全部通过。本轮未再次执行整个测试集合。
- 新增Python模块ruff通过，前端build/lint通过，git diff --check通过。
- `python -m growth_os.api.interactive` 已真实执行，创建 `data/interactive`。该种子使用FakeGateway验证受控历史旅程，不调用外部模型。

运行命令见根目录README；I2起需处理提交请求重复、并发、持久化归因及失败恢复，并补浏览器交互验收。

## I2–I3 理解回答提交与重评

同日继续实现文本提交接口与表单，调用既有TaskLoop；默认固定绑定规则，无真实模型请求。受控场景理解2→3，实践保持4。请求账本使用独立 `requests.db` 的 `g_submission_requests`，只由store模块访问；进程文件锁保证单写者。

- 最终UTF-8全量回归460项通过，XML见 `regression.xml`。随后新增并发用例；交互文件9项全部通过，验证提交中禁止第二次提交与状态操作。
- 同请求同内容重放返回持久化结果；不同内容冲突；重启后结果及归因仍可读。
- 普通链路失败不伪报完成，可手动重试；进程中断记录阻止以新请求ID绕过，需人工核对后恢复。
- API拒绝客户端source_id与artifact_path，本阶段只接受probe_answer。
- ruff、前端build/lint通过。12项真实浏览器检查通过，包含按钮链、原因必填、提交、理解变化、刷新持久化及桌面/390px无溢出。见 `browser-verification.json` 与四张截图。
- 原只读服务仍无写路由。实践文件提交与真实模型验收未交付。

## I4 实践产物文件提交

接入文档、代码、ZIP三类任务文件提交。文件内容通过严格JSON请求传入；请求体流式限制3 MB，解码后最大2 MB。服务器检查文件名、任务交付物匹配与文本编码，生成存储路径后仅调用既有TaskLoop。不接收客户端路径或source_id，不执行上传文件。

- 477项全量回归通过，见 `file-regression.xml`。随后增加失败重试用例，文件专项17项全部通过，见 `file-focused.xml`；未再重复全量测试。
- 文档、Python、Dockerfile和ZIP分别验证实践3→4、理解保持2、归因全通过、单提交、重放、重启读取与audit pass。
- 格式、空文件、二进制、路径、非法base64、伪造字段和超限输入拒绝；非法输入不改变证据库。缺少Content-Length时同样限制请求体。
- 绑定故障后任务保持active、无提交；手动重试保留相同source集合，完成后重放不再调用网关。
- 12项真实浏览器检查通过，使用原生文件选择、文件提交、刷新结果及1440/390px表单和结果无横向溢出，见 `file-browser-verification.json`、`file-form-*.png`、`file-result-*.png`。
- 浏览器提交后的实验库audit pass，见 `file-audit.json`。ruff、前端build/lint与diff检查通过。零真实模型请求，结果仅证明受控链路机制。

运行 `python -m growth_os.api.interactive --directory data/interactive-files --with-practice` 创建全新待提交实践场景，已有实验和只读种子保持兼容。I5完整阶段质量门与真实模型验收仍待后续，未宣称完整PRD MVP通过。
