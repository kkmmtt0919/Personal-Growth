# 项目功能

> 功能范围与当前状态的唯一清单。API、数据模型和函数级设计放在 `docs/ARCHITECTURE.md` 并从此处引用。

## 状态定义

- 候选：尚未批准进入范围
- 已规划：已确认但未开始
- 进行中：正在实现
- 已阻塞：等待外部条件
- 已完成：完成条件满足且有证据
- 已取消：退出范围并保留原因

## 功能清单

| 功能 ID | 功能 | 来源引用 | 优先级 | 状态 | 验收状态 | 依赖 | 完成条件 | 设计引用 | 证据 ID |
|---|---|---|---|---|---|---|---|---|---|
| F-001 | 目标澄清与确认（Goal Agent、澄清状态机、目标存储） | PRD §16 §17 | P0 | 已完成 | 通过 | Q1 Q2 | ≤6 轮产出 confirmed goal 且含方向/目的/周期/可衡量结果 | ARCHITECTURE §5.3；ROADMAP M2 | EV-052 EV-056 EV-057 |
| F-002 | 能力模型动态生成（目标 → 能力树 + 外部参考） | PRD §25 | P0 | 已完成 | 通过 | F-001 | 生成 ≥3 领域 ≥12 能力点，且可人工调整不被覆盖 | ARCHITECTURE §5.3；ROADMAP M2 | EV-053 EV-056 |
| F-003 | 文档摄入与检索（PDF/Markdown/TXT/代码/ZIP） | PRD §22 §23 | P0 | 进行中 | 部分（后端 Gate 通过；PDF 产品上传入口未建） | M1 | 上传 PDF 与 MD 均产出 passages 且可检索 | ARCHITECTURE §7；ROADMAP M3 | EV-059 EV-061 EV-065 |
| F-004 | GitHub 集成（OAuth、选仓库、项目分析） | PRD §7.3 | P0 | 进行中 | 部分（公共仓库已通过；OAuth/私有仓库未做，M3 决策 6） | M1 | 授权后自动产出技术栈清单与 ≥3 条 capability claim；token 不落明文 | ARCHITECTURE §3.4；ROADMAP M3 | EV-062 EV-065 |
| F-005 | 证据图谱（Claim / Evidence / Source / Provenance / Attack / Confidence） | PRD §5 §6 §7 §8 | P0 | 已完成 | 通过 | M1 | evkg 全流水线可用；audit_store=pass；damage_selftest=caught | ARCHITECTURE §3 §7；ROADMAP M1 | EV-008 EV-037…EV-041（QG2 双向测量口径） |
| F-006 | 五星能力审计与缺口识别 | PRD §9 §10 | P0 | 已规划 | 待检查 | F-002 F-005 | 通过 G3 的 A/B 对照实验；每级可追溯；能解释"为什么三星" | ARCHITECTURE §3；ACCEPTANCE G3；ROADMAP M4 | 无 |
| F-007 | 任务生成与完成闭环 | PRD §11 §12 | P0 | 已规划 | 待检查 | F-006 | 通过 G4、G5；任务含可交付物/时长/验收方式；星级变化可归因 | ARCHITECTURE §2；ACCEPTANCE G4 G5；ROADMAP M5 | 无 |
| F-008 | Memory 三层（Profile / State / Growth History） | PRD §13 | P0 | 已规划 | 待检查 | F-006 | 三层互不覆盖；能展示能力星级时间线 | ROADMAP M6 | 无 |
| F-009 | 主动 Agent（每日分析、4 类事件、提醒可关闭） | PRD §14 §15 | P0 | 已规划 | 待检查 | F-007 F-008 | 无变化不通知；冷却期生效；用户可关闭 | ARCHITECTURE §5.4；ROADMAP M7 | 无 |
| F-010 | Agent 运行时与轨迹（Runtime / ToolRegistry / ContextAssembler / Tracer） | PRD §29 §30 | P0 | 进行中 | 部分（最小运行时与轨迹已通过；编排与更多工具随 M4/M5） | M1 | 轨迹落 `g_agent_runs` 可回放；工具调用可审计 | ARCHITECTURE §5；ROADMAP M1 | EV-051 EV-056 |
| F-011 | UI · Growth Dashboard | PRD §19 | P0 | 已规划 | 待检查 | F-006 | 首页只回答目标/状态/缺口/下一步 | ROADMAP M8 | 无 |
| F-012 | UI · Knowledge / Evidence Space | PRD §20 | P0 | 已规划 | 待检查 | F-005 | 可回答"为什么我只有三星"，含支持证据/不足/攻击结果 | ROADMAP M8 | 无 |
| F-013 | UI · AI Mentor | PRD §21 | P0 | 已规划 | 待检查 | F-006 F-008 | 回答时同时访问 Goal+Memory+Capability+Evidence+History | ROADMAP M8 | 无 |
| F-014 | 项目验收证据链（用 evkg 承载验收证据，与用户库隔离） | DECISIONS D8 | P1 | 已规划 | 待检查 | F-005 | 每道验收门有可审计 dossier；acceptance.db 与用户库物理隔离 | ACCEPTANCE §2 | 无 |
| F-015 | LLM 网关配置与 Agent 模型分层 | DECISIONS D3 | P0 | 已完成 | 通过 | M1 | evkg 流水线与 Agent 可用不同模型；verifier 可独立配置 | ARCHITECTURE §5.2 | EV-029 EV-051 |

## 功能变更历史

| 日期 | 功能 ID | 变化摘要 | 原因与影响 | 证据 ID | 确认来源 |
|---|---|---|---|---|---|
| 2026-10-01 | F-001…F-013 | 初次登记：PRD §31 的 P0 清单拆为 13 项功能并绑定里程碑 | PRD → 可实施步骤的映射 | 无 | 待用户确认 |
| 2026-10-01 | F-014 F-015 | 新增两项架构性功能 | F-014 落实验收证据链自举；F-015 落实模型分层与独立复核 | 无 | 待用户确认 |
| 2026-10-02 | F-001 F-002 F-005 F-015 | 状态推进为"已完成"（M1/M2 已收口） | 账本同步：功能清单此前未随 M1/M2 更新，按已收口门的证据修正 | F-001 EV-052/056/057；F-002 EV-053/056；F-005 EV-008/037…041；F-015 EV-029/051 | ZCode 修正（依据已收口证据） |
| 2026-10-02 | F-003 F-004 F-010 | 状态推进为"进行中"并写明未完成边界 | M3 收口后的如实状态：后端通道已过 Gate；产品上传入口（PDF V1 入口）、OAuth/私有仓库、通用编排分别未做 | F-003 EV-059/061/065；F-004 EV-062/065；F-010 EV-051/056 | ZCode 修正（依据已收口证据） |
