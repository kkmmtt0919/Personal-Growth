# 项目总览

> 当前项目方向与边界的紧凑视图。详细设计在 `.project-to-act/docs/`，此处只记短摘要与引用。

## 基本信息

- 项目名称：Growth OS（AI Personal Growth OS）
- 项目 ID：growth-os
- 项目负责人：用户（产品决策）／ZCode（实施）
- 风险等级：中（含一项高不确定性技术依赖：evkg 作为模块可用性，见 R1/R2）
- 当前阶段：M0 地基与治理（已完成，待用户确认后进入 M1）
- 当前状态：规划已定稿，等待 4 项选型确认
- 最后更新：2026-10-01

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

- 技术栈：Python 3.12（uv 托管）· FastAPI · SQLite(WAL) · React + Vite + TS —— 详见 `docs/DECISIONS.md` Q1–Q4（待确认）
- 证据底座：复用 evkg（`D:\projects\evkg`，独立仓库，非 fork），只允许经 `backend/evidence/adapter.py` 单一入口 import
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

- 下一里程碑：**M1 证据底座打通（技术 spike，最高优先级）**
- 当前工作重点：等待 Q1–Q4 选型确认；确认后从 M1-a 开始
- 主要阻塞：Q1（evkg 集成方式）、Q2（LLM 模型选型）、Q3（前端技术栈）、Q4（是否需要多用户）

## 路线变更记录

| 决定 ID | 日期 | 决定摘要 | 原因与影响 | 证据 ID | 确认来源 |
|---|---|---|---|---|---|
| D1–D8 | 2026-10-01 | 拟定 8 项架构决策，见 `docs/DECISIONS.md` | 架构规划产物；D1/D5/D6 影响证据层实现方式 | 无 | 待用户确认 |
| Q1–Q4 | 2026-10-01 | 提出 4 项待决策，阻塞 M1 开工 | 均为影响全局的选型，不宜由实施方单方决定 | 无 | 待用户决策 |
