# 项目总览

> 当前项目方向与边界的紧凑视图。详细设计在 `.project-to-act/docs/`，此处只记短摘要与引用。

## 基本信息

- 项目名称：Growth OS（AI Personal Growth OS）
- 项目 ID：growth-os
- 项目负责人：用户（产品决策）／ZCode（实施）
- 风险等级：中（含一项技术依赖：evkg 作为模块可用性 —— M1-g 已实测收口，判定为**有条件依赖（C1–C5）**，见 `docs/M1-SPIKE-CONCLUSION.md`）
- 当前阶段：M0 地基与治理（已完成）；**M1 证据底座打通 / 技术 spike（已完成，2026-10-02 收口）**；M2 待开工
- 当前状态：M1-g 结论文档已产出（`docs/M1-SPIKE-CONCLUSION.md`），待用户确认收口；在案阻塞：B-g1（evkg 依赖 pin / 可获取性）、B-g2（M3 前富格式 spike）
- 最后更新：2026-10-02

## 项目目标

构建一个以证据图谱为可信底座的个人成长操作系统，跑通并证明：

> 一个 AI Agent 能否仅通过少量个人资料、GitHub 项目和对话，建立**有证据依据**的个人能力模型，并据此**持续生成有意义的成长任务**。

可验证结果：`docs/ACCEPTANCE_GATES.md` 的 G1–G6 全部通过且证据未过期。

## 范围

### 包含

- 目标澄清 → 动态能力模型 → 证据收集 → 证据攻击 → 五星能力审计 → 缺口 → 任务 → 新证据 → 能力更新的完整闭环
- 三类证据输入：Chat、Upload（PDF/Markdown/TXT/代码/ZIP）、GitHub（OAuth + 选仓库）
- 三个核心页面：Dashboard、Evidence Space、AI Mentor
- Memory 三层（Long-term Profile / Short-term State / Growth History）
- 主动 Agent：每日分析 + 4 类有意义事件提醒（用户可关闭）

### 非目标

PRD §32 全部条目照原样保留，另加架构层面非目标（见 `docs/ARCHITECTURE.md` §9）：

- 不做 Neo4j 等重型图数据库；不做向量数据库（先用 FTS5 + 结构化查询）
- 不引入多 Agent 编排框架（LangGraph/AutoGen 等）；不做微服务与容器编排
- MVP 不做多用户与权限体系（但表结构预留 `user_id`）
- 不 fork evkg（见决定 D1）

## 技术路线与关键约束

- 技术栈：Python 3.12（uv 托管）· FastAPI · SQLite(WAL) · React + Vite + TS · Node 24 —— 选型已确认，见 `docs/DECISIONS.md` Q1–Q4
- 证据底座：复用 evkg（`D:\projects\evkg`，独立仓库，非 fork），以 uv editable path 依赖引入，只允许经 `backend/growth_os/evidence/adapter.py` 单一入口 import（决定 D1/Q1）
- LLM：GLM（`open.bigmodel.cn` / `glm-5.3`）作主模型，另配独立 verifier 模型用于攻击复核（决定 Q2）；`EVKG_*` 供流水线、`GROWTH_AGENT_*` 供 Agent 推理，分层配置
- 存储：单 SQLite，evkg 表族 + Growth OS `g_` 前缀表族共存，跨表族引用由应用层保证（决定 D2）
- Agent：自建薄运行时，产出完整轨迹用于评估（决定 D4）
- **硬约束**：`evkg.domain.SourceKind` 是封闭 StrEnum，`assess_source` 直接字典索引，未知 kind 会 KeyError → 细粒度证据类型必须走 `Source.metadata`（决定 D5）
- **硬约束**：能力星级不得由 `confidence` 线性映射（决定 D6），由 G3 的 A/B 对照实验强制验证

## 数据与安全边界

- 数据分类：用户个人学习资料与对话属**个人数据**；GitHub token 属**凭证**；LLM 调用内容属**外发数据**
- GitHub token 只以引用形式存 `g_integrations`，明文不入库、不入账本、不入日志
- 验收证据库（`data/acceptance.db`）与用户证据库**物理隔离**，防止项目资料污染用户能力断言
- 账本与文档只保留脱敏摘要、证据 ID、路径与哈希；`data/`、`.env` 已 gitignore

## 当前焦点

- 已完成：**M1 技术 spike**（R1–R4 + D1 收口；依赖策略 = 有条件依赖）；M1-g 已提交（`8e104b7`）
- 当前工作重点：B-g1 交付形式待用户确认（方案比较与实测见 `docs/M1-SPIKE-CONCLUSION.md` §9.1；建议：维持不推送 + 本地归档）
- 主要阻塞：B-g1（换机/CI 前必须解决，待确认交付形式）；B-g2（M3 开工前富格式 spike）

## 路线变更记录

| 决定 ID | 日期 | 决定摘要 | 原因与影响 | 证据 ID | 确认来源 |
|---|---|---|---|---|---|
| D1–D8 | 2026-10-01 | 拟定 8 项架构决策，见 `docs/DECISIONS.md` | 架构规划产物；D1/D5/D6 影响证据层实现方式 | 无 | 用户已确认（随 Q1–Q4） |
| Q1 | 2026-10-01 | evkg 采用独立仓库 + uv editable path 依赖 | 保持上游可同步，耦合收敛到单个适配层 | 无 | 用户确认 |
| Q2 | 2026-10-01 | GLM 主模型 + 独立 verifier 模型 | 避免"自己审自己"削弱攻击环节可信度 | 无 | 用户确认 |
| Q3 | 2026-10-01 | 前端 React + Vite + TypeScript | 与 evkg 前端一致，可复用其 Cytoscape 图谱实现 | 无 | 用户确认 |
| Q4 | 2026-10-01 | 单用户本地优先，表结构预留 user_id | 优先跑通 PRD §33 的 6 条成功标准，推迟权限体系 | 无 | 用户确认 |
| M1-g | 2026-10-02 | evkg 依赖策略 = **有条件依赖（C1–C5）**；不采用"可直接依赖（整体）"，也不升级为"必须改上游才能用" | 实测依据：当前调用面端到端可用（audit pass、引文逐字可回溯）；但 profile 为进程级全局且双实例互相污染、抽取模型名未持久化、上游渲染器丢 `partial` → 整体不满足直接依赖；三处问题分别以条件约束/绕行/延后触发条件管理 | EV-042…EV-046 | ZCode 判定（待用户确认收口） |
