# M8 产品化边界（v0.1 · 待确认，不开工）

M8 把已经验证的成长闭环变成一次可演示的产品体验。它不增加 Agent 能力。

## 范围

三个只读页面：

| 页面 | 回答 | 数据 |
|---|---|---|
| Growth Dashboard | 我现在是什么水平 | goal、capability、assessment、gap |
| Evidence Explorer | 为什么是这个等级 | assessment report 的支持证据、引用和绑定原因 |
| Growth Loop | 下一步做什么 | task、submission、重评前后等级 |

页面只调用新增的只读产品 API，不直接读数据库。

## Demo

固定一条受控旅程：AI Agent 工程师目标 → 能力树 → RAG 实践 3 → Agent Evaluation 缺口 → 任务 → 提交 → 实践 4。素材沿用已标注的受控证据，不伪装成真实用户成果。

## 冻结

不实现 Mentor Chat、自动学习规划、社区、外部通知、目标变化后的自动重建、Memory 演化或主动 Agent 扩展。

## 已确认（2026-10-04）

1. 前端继续使用 React + Vite + TypeScript，不迁移 Next.js。
2. M8-a 只做 Demo fixture、只读 API 和契约测试；M8-b 再做三个页面。
3. 部署留到 M8-c，使用本地 `uvicorn + vite preview`。

只读 API：

```text
GET /api/goals/{goal_id}
GET /api/capabilities/{capability_id}
GET /api/evidence/{capability_id}
GET /api/growth-loop/{goal_id}
```

API 不提供创建目标、上传材料、修改等级、创建任务或提交证据。写操作继续只走 Goal、TaskLoop、AssessmentPipeline 和 ClaimBinder。

## M8-b 页面边界（待确认，不开工）

三个只读页面依次回答：我处于什么成长状态、为什么是这个等级、基于证据缺口下一步做什么。文案使用“基于当前证据缺口生成任务”，不使用“AI 推荐任务”。

| 页面 | 展示 | 数据 |
|---|---|---|
| Dashboard | 目标、能力卡片、理解/实践等级、当前缺口 | goal 与 capability |
| Evidence Explorer | 等级、支持证据、来源、引用、绑定理由、不足 | evidence |
| Growth Loop | 缺口、任务、提交、重评前后等级 | growth loop |

前端目录限于 `src/api`、`src/pages`、`src/components`、`src/types`。视觉保持暖白、少量橙色强调和 Notion/Linear 式留白，不做驾驶舱或渐变后台。

开工前需要补两个只读字段，仍不增加写入口：

1. 一个目标下的能力列表。当前只能按 capability id 单查。
2. Evidence 响应中的 source 与 quote。当前只有 claim id 和绑定理由。

验收看 Demo 流程是否完整、字段是否来自 API、是否没有前端业务 mock、是否没有写请求，以及证据链是否可见。登录、编辑、上传、创建任务和 AI 对话继续不做。

## M8-c Demo 收口边界（待确认，不开工）

1. 增加只读应用启动入口，明确一条后端命令和一条前端命令。前端 API 基址改为 `VITE_API_BASE_URL`，默认 `http://localhost:8000`。
2. 提供一个受控 Demo 种子命令，自动写入目标、能力、证据、缺口和任务。用户不需要手工找数据库。
3. 新增根目录 README，只讲产品一句话、成长流程图、三条启动命令和三张页面截图。工程细节继续留在 `.project-to-act/docs/`。
4. 增加 `artifacts/m8/walkthrough.md`，记录 RAG 实践 3 → Agent Evaluation 缺口 → 任务 → 提交 → 实践 4 的受控旅程。
5. 第一轮不部署云端，不做登录、注册、上传、在线编辑或 Agent Chat。截图在页面可运行后补，不伪造。
