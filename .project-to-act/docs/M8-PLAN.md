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

## 待确认

1. 前端继续使用已冻结的 React + Vite + TypeScript，不改成 Next.js。
2. M8-a 先固化 Demo 数据和只读 API 契约，M8-b 再做页面。
3. 部署先用本地 `uvicorn + vite preview`，不在 M8-a 引入容器或云部署。
