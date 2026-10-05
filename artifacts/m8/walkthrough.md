# M8-c · 本地受控 Demo

日期：2026-10-05。范围：本地只读体验与受控旅程，无真实模型请求。

## 启动与数据

根目录 README 提供三个命令：种子、后端、前端。依赖为已有 `.venv`（Growth OS + 本地 evkg editable 依赖）及 `frontend/node_modules`；首次安装可按项目 `pyproject.toml` 建立 Python 环境，并运行 `npm.cmd --prefix frontend ci`。换机交付仍依赖 evkg 归档与恢复，不宣称已完成发布。

种子默认写入 `data/demo/`：`demo.db`、受控 Markdown 材料、评估报告、归因 manifest。用户库 `data/growth.db` 不参与。
重复种子命令拒绝覆盖已有数据库。已有 `demo.db` 和 `manifest.json` 时直接启动；需要独立新样本可用 `--directory`，后端通过 `GROWTH_DEMO_DIRECTORY` 指向同一目录。

服务命令：`python -m uvicorn growth_os.api.local:create_local_app --factory --host 127.0.0.1 --port 8000`。
未创建完整种子时服务拒绝启动，不自动写入演示数据。关闭服务时连接由 lifespan 清理。
前端使用 `VITE_API_BASE_URL`，默认 `http://localhost:8000`；它是构建时配置，修改后需重新构建。
只允许本地 4173/5173 来源的 GET 跨域访问，产品 API 无写入口。

## 旅程

1. 创建已确认的“成为 AI Agent 工程师”目标，以及 RAG 实践能力点，目标等级为 4。
2. 受控笔记和项目材料经 adapter 单入口入库，材料主张经 ClaimBinder 八步闸门绑定。提议使用 FakeGateway，不调用真实模型。
3. AssessmentPipeline 产出理解 2、实践 3，以及各自证据缺口；不直接手填星级。
4. 为实践缺口创建预设的 Agent Evaluation 评测任务并激活。任务为受控预设，不能据此宣称验证了真实模型任务生成质量。
5. 提交十条样本与判定标准的受控报告，唯一入口 `TaskLoop.complete_task` 执行材料入库、claim、绑定、重评和归因。
6. 结果：实践 3 → 4，实践缺口关闭；理解维持 2、理解缺口开放。全量归因守卫通过。
7. Dashboard 展示重评后的状态；点击“查看证据”核对引文、来源与绑定理由；任务页展示原缺口、交付要求、提交与实践 3 → 4。

归因报告来自该次种子执行的 manifest，由启动入口读取后交给只读 API；普通任务若没有报告则不展示前后等级，避免凭任务完成状态推断成长。

## 验证

- 新增 Demo 端到端测试覆盖实际重评 3 → 4、缺口关闭、引文来源非空、POST 拒绝、本地 CORS、外部来源拒绝、已有数据库零覆盖、未种子时拒绝启动。
- 全量 Growth OS 测试在 `PYTHONUTF8=1` 下通过。首轮两个历史子进程测试失败来自 GBK 输出被 UTF-8 解码，统一环境后通过。
- 最终 API 调整后，Demo/API 定向回归 3 项通过；后端 ruff、前端 build 和 lint 通过。
- 三张截图均由本地 Edge 无界面浏览器访问实际运行页面生成，并逐张检查。

## 保留边界

这里只完成 M8-c 冻结的本地只读 Demo。G6 的隔天 Agent 回答验收仍未完成；不将这三张只读页面截图作为 G1 交互澄清截图补证。云端发布、登录、上传写入口、在线编辑、Agent Chat、外部通知和自动重建不在此阶段。
