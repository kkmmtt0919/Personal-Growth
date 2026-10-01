# AI Personal Growth OS

### —— 基于证据图谱的个人知识与能力成长操作系统

**项目工作名称：Growth OS**

**产品定位：**
一个以“个人成长”为核心、以“证据驱动能力建模”为底层机制的 AI Agent 系统。

它不是传统的知识库，也不是普通聊天机器人。

它帮助用户完成：

> **明确目标 → 建立目标能力模型 → 收集个人证据 → 审计当前能力 → 发现能力缺口 → 生成任务 → 完成任务 → 产生新证据 → 更新能力 → 持续成长**

------

# 1. 项目背景

目前大量 AI 知识产品主要解决的是：

> “帮我找到信息。”

典型流程：

```text
用户提问
↓
检索资料
↓
LLM生成回答
```

但个人长期成长真正需要解决的问题并不是“我能不能找到知识”，而是：

> **我现在到底会什么？**
>
> **我距离我的目标还有多远？**
>
> **我的判断依据是什么？**
>
> **我下一步真正应该做什么？**

例如，一个用户告诉系统：

> “我想成为 AI Agent Engineer。”

普通 AI 可以给出：

```text
学习 Python
学习 RAG
学习 Agent
学习 LangChain
学习 Docker
```

但它并不知道：

- 用户已经会什么；
- 用户只是“看过”什么；
- 用户真正做过什么；
- 哪些能力有项目证据；
- 哪些能力只是用户自述；
- 哪些能力仍然缺乏实践；
- 为什么系统认为某项能力不足。

Growth OS 要解决的正是这一层。

------

# 2. 核心产品理念

## 2.1 核心理念

> **不是帮用户收藏知识，而是帮助用户把知识转化成能力，把能力转化成行动。**

产品的最小核心闭环：

```text
Goal
目标
 ↓
Capability
目标需要什么能力
 ↓
Evidence
用户有什么证据
 ↓
Audit
证据是否足够
 ↓
Gap
还缺什么
 ↓
Task
下一步做什么
 ↓
Action
用户真正去做
 ↓
New Evidence
产生新的证据
 ↓
Capability Update
能力发生变化
 ↓
下一轮成长
```

因此，它最终形成的不是“知识库”，而是一套：

> **Goal → Evidence → Capability → Task → Growth**

的个人成长系统。

------

# 3. 产品定位

## 3.1 第一核心用户

第一目标用户：

> **希望成为 AI / Agent 工程师，并且需要持续学习、做项目、建立能力证明的人。**

典型用户：

- AI/计算机相关学生；
- AI 工程师；
- 正在转向 AI 的开发者；
- 有大量技术资料但缺乏系统成长路径的人；
- 有 GitHub 项目但不知道自身能力处于什么阶段的人。

------

## 3.2 第二类用户

产品并不绑定 AI 行业。

只要能够建立：

```text
目标
↓
能力模型
↓
证据
↓
任务
```

理论上可以扩展到：

- 数据分析师；
- 产品经理；
- 软件测试；
- 研究人员；
- 设计师；
- 语言学习；
- 其他职业技能成长。

因此：

> **AI 工程师是第一切入口，个人成长系统是最终产品形态。**

------

# 4. 用户核心问题

Growth OS 针对的不是一个问题，而是一组连续问题：

### 问题一：我到底想去哪里？

用户通常说：

> “我想成为 AI 工程师。”

这个目标太模糊。

系统需要通过多轮对话进一步澄清：

```text
AI工程师
↓
AI应用工程师？
算法工程师？
AI基础设施？
↓
偏 Agent / RAG？
↓
为了就业？
项目能力？
长期研究？
↓
时间周期？
```

最终形成：

> **明确、可执行、可衡量的目标。**

------

### 问题二：这个目标到底需要什么？

用户通常自己并不知道完整能力模型。

因此能力模型不由用户手动填写，而由系统根据目标动态生成。

例如：

```text
目标：
AI Agent Engineer

能力模型：

├── LLM基础
│   ├── Prompt
│   ├── Context
│   └── Tool Calling
│
├── Agent Architecture
│   ├── Agent Loop
│   ├── Planning
│   ├── Memory
│   └── Reflection
│
├── Tool System
│   ├── File System
│   ├── Shell
│   ├── Browser
│   └── API
│
├── Engineering
│   ├── Python
│   ├── Backend
│   ├── Database
│   └── Deployment
│
└── Evaluation
    ├── Test Cases
    ├── Trace
    ├── Benchmark
    └── Evaluation
```

需要强调：

> 这不是一个永久固定的技能树。

它是一个**动态能力模型**，可以随着目标、领域资料和用户证据变化而调整。

------

### 问题三：用户真的会吗？

这是产品最核心的难题。

用户说：

> “我懂 RAG。”

并不能直接认为：

```text
RAG = 已掌握
```

因为“懂”至少有：

```text
看过
↓
理解
↓
能解释
↓
能实践
↓
能独立完成
↓
能优化
```

不同层级。

因此产品不能把“用户自述”作为主要能力证明。

必须建立：

> **Evidence-driven Capability Assessment**

即：

**证据驱动的能力评估。**

------

# 5. Evidence Graph：产品的核心信任层

项目中的 `evkg` 可以直接作为这一层的基础设施。

它并不是普通的知识图谱，而是：

> **围绕 Claim、Evidence、Provenance 和 Attack 建立的可审计证据系统。**

核心流程：

```text
Input
↓
Claim Extraction
↓
Evidence Binding
↓
Graph Construction
↓
Attack
↓
Audit
↓
Dossier
↓
Retrieval
```

------

# 6. Claim：整个系统的语义中心

系统不是简单地记录：

```text
用户学习过 RAG
```

而是形成一个可被验证的 Claim：

```text
Claim：

用户具备 RAG 工程基础能力
```

这个 Claim 必须关联真实证据。

例如：

```text
Claim
│
├── Evidence A
│   └── 用户笔记
│
├── Evidence B
│   └── GitHub代码
│
├── Evidence C
│   └── 用户完成的任务
│
└── Evidence D
    └── AI测试结果
```

每条证据都必须能够追溯到真实来源。

------

# 7. Evidence：能力判断的依据

MVP 允许三类主要证据来源。

## 7.1 聊天

用于判断：

- 目标；
- 用户偏好；
- 理解程度；
- 思考过程；
- 短期状态。

例如：

用户解释：

> “为什么 RAG 需要 rerank？”

系统可以把回答作为能力证据。

但：

> 聊天属于较弱的能力证据。

------

## 7.2 文件

支持用户主动上传自己的：

- PDF；
- Markdown；
- Word；
- PPT；
- 图片；
- 代码；
- 项目压缩包等。

不同格式由不同解析器处理，然后进入统一知识表示层。

```text
PDF
PPT
Markdown
Code
Image
        ↓
Format-specific Parser
        ↓
Unified Knowledge Representation
        ↓
Claim / Evidence / Entity / Relation
```

MVP 不要求一次支持所有格式。

第一阶段优先：

```text
PDF
Markdown
TXT
代码
ZIP项目
```

------

## 7.3 GitHub

MVP 唯一的自动同步入口：

> GitHub OAuth + 用户主动选择 Repository。

不要求用户提供 GitHub 密码，也不默认使用 SSH Key。

权限设计遵循：

> **最小权限原则。**

系统只读取用户明确授权的项目数据。

GitHub 的价值在于：

> **代码和项目是能力证明强度最高的证据之一。**

例如系统发现：

```text
用户项目
AI Testing Assistant

技术：
FastAPI
RAG
ChromaDB
MCP
```

可以形成项目级能力证据：

```text
RAG → 实践证据
Backend → 实践证据
MCP → 实践证据
```

------

# 8. Attack：AI主动攻击自己的判断

这是 Growth OS 与普通 RAG / Knowledge Base 的关键区别。

系统生成一个 Claim：

> “用户具备 Agent Memory 能力。”

它不能立即相信自己。

需要进一步攻击：

```text
这个结论有什么证据？

证据是否只是用户自述？

是否只有理论笔记？

有没有代码？

代码是不是调用现成 API？

有没有独立设计？

是否存在反向证据？

有没有相互矛盾的资料？
```

形成：

```text
Claim
↓
Evidence
↓
Attack
↓
Counter Evidence
↓
Confidence
```

最终才决定：

```text
Agent Memory
⭐⭐⭐☆☆
```

------

# 9. 能力星级模型

用户界面不展示精确数字。

只显示：

```text
⭐⭐☆☆☆
⭐⭐⭐☆☆
⭐⭐⭐⭐☆
```

因为“67%能力”容易制造伪精确。

内部系统仍可以保存连续数值用于计算。

------

## 9.1 五级能力模型

建议 MVP 使用：

### ⭐☆☆☆☆ 接触

知道概念、看过资料。

### ⭐⭐☆☆☆ 理解

能够解释主要概念。

### ⭐⭐⭐☆☆ 实践

能够按照已有方法实现。

### ⭐⭐⭐⭐☆ 独立

能够独立完成完整任务。

### ⭐⭐⭐⭐⭐ 深度

能够优化、诊断、设计并解释取舍。

------

# 10. 能力评估的证据优先级

能力判断不是平均计算。

可以采用：

```text
能力评估
=
知识证据
+
行为证据
+
实践证据
+
任务证据
-
反向证据
```

例如：

用户说：

> “我会 Agent Memory。”

但系统发现：

```text
聊天证据：有
论文笔记：有
代码证据：无
项目证据：无
任务证据：无
```

那么：

```text
可能：

理解能力 ⭐⭐⭐☆☆
实践能力 ⭐☆☆☆☆
```

而不是直接：

```text
Agent Memory ⭐⭐⭐⭐☆
```

------

# 11. 任务驱动成长

产品最终的“成长单位”不是知识点，而是：

> **任务。**

例如：

```text
能力缺口：

Agent Evaluation
        ↓
生成任务：

设计10个Agent测试Case
        ↓
用户完成
        ↓
产生新证据
        ↓
Evidence Audit
        ↓
能力更新
```

因此：

> **任务是连接“能力模型”和“现实行动”的桥梁。**

------

# 12. 任务必须能够产生证据

例如：

系统不应该只给：

> “去学习 Agent Evaluation。”

而应该生成：

```text
任务：

设计一个10条样本的Agent Evaluation Set

目标：
证明你理解基础Evaluation方法

预计：
60分钟

提交：
代码 / Markdown / GitHub commit
```

任务完成后：

```text
任务结果
↓
证据
↓
Audit
↓
能力升级
```

因此系统不是学习提醒器，而是：

> **能力形成系统。**

------

# 13. Memory 体系

Memory 不采用“一个万能 Memory”。

而采用三个层次。

------

## 13.1 Long-term Profile

长期信息：

```text
用户目标
职业方向
长期偏好
学习风格
长期能力状态
```

例如：

```text
偏好：
喜欢代码实践
倾向先理解架构再看源码
```

------

## 13.2 Short-term State

当前状态：

```text
当前正在学习：
Agent Runtime

当前任务：
Memory模块

已理解：
Agent Loop

未理解：
Session管理
```

变化频繁。

------

## 13.3 Growth History

成长时间线：

```text
2026.07
RAG ⭐⭐☆☆☆

2026.08
RAG ⭐⭐⭐☆☆

2026.09
RAG ⭐⭐⭐⭐☆
```

形成：

> **成长曲线。**

三者完全不冲突：

```text
User
│
├── Long-term Profile
├── Current State
└── Growth History
```

------

# 14. AI 导师

产品不是“分析工具”，而是：

> **AI导师。**

它的特点是：

### 用户主动问

例如：

> 我距离 Coding Agent 还有什么差距？

系统基于：

```text
目标
+
能力模型
+
Evidence Graph
+
Memory
```

回答。

------

### AI 主动分析

每天后台执行一次：

```text
Scheduler
↓
读取最近状态
↓
分析新增证据
↓
检查能力变化
↓
判断是否存在重要事件
↓
生成建议
```

注意：

> 每天分析 ≠ 每天骚扰用户。

只有发现有意义的变化时才提醒。

------

# 15. 主动 Agent 的触发机制

第一版建议只做几类高价值事件。

### 事件一：能力出现新证据

例如：

```text
用户完成一个Memory项目
```

→ 更新能力。

------

### 事件二：发现长期停滞

例如：

```text
连续两周：

理论学习增加
实践任务 = 0
```

→ 给出行动建议。

------

### 事件三：发现能力缺口

例如：

```text
用户有5个Agent项目

但没有Evaluation证据
```

→ 生成任务。

------

### 事件四：目标发生变化

例如：

用户说：

> “我准备开始找Agent岗位。”

→ 重新生成目标能力模型。

------

# 16. 目标澄清 Agent

用户不会填写复杂表单。

而是直接聊天。

例如：

```text
用户：
我想成为AI工程师。

AI：
AI工程师范围比较广。
你更偏向：
应用 / 算法 / 基础设施？

用户：
应用。

AI：
你主要目标是就业、项目能力，还是长期研究？

用户：
找工作。

AI：
目标时间大概多久？

用户：
六个月。

AI：
那么我暂时把你的目标定义为：
“六个月内达到AI应用工程师的项目与求职能力”。

是否以此为当前目标？
```

用户确认之后才建立目标。

因此：

> **模糊目标必须经过澄清，才能进入能力分析。**

------

# 17. 用户第一次使用流程

MVP 的第一条核心用户旅程：

```text
进入网站
↓
AI问候
↓
用户自然语言描述目标
↓
多轮澄清
↓
形成明确目标
↓
生成第一版能力模型
↓
邀请用户提供证据
│
├── 上传资料
├── 连接GitHub
└── 直接继续聊天
↓
Evidence Graph建立
↓
能力初始评估
↓
展示第一版能力画像
↓
给出第一个任务
```

最重要的设计原则：

> **允许“低数据量启动”。**

用户不应该必须上传20篇论文、绑定GitHub、填写一大堆表格之后才能看到结果。

------

# 18. 产品信息架构

MVP 第一版不做大量页面。

建议：

```text
               Growth OS
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
     Dashboard   AI Mentor   Knowledge
        │
        ↓
   Goal / Capability
   Evidence / Task
```

实际 MVP 可以进一步压缩。

------

# 19. 页面一：Growth Dashboard

这是产品首页。

核心问题：

> **“我现在在哪里，下一步去哪里？”**

展示：

```text
我的目标

AI Agent Engineer
```

↓

```text
当前阶段

基础 → 项目能力
```

↓

```text
能力画像

RAG           ⭐⭐⭐⭐☆
Agent Runtime ⭐⭐⭐☆☆
Evaluation    ⭐⭐☆☆☆
Memory        ⭐⭐⭐☆☆
```

↓

```text
系统发现

你已经有较多理论与项目经验，
但 Evaluation 缺少实践证据。
```

↓

```text
下一步

完成：
10条Agent Evaluation测试Case
```

首页不承担所有知识展示。

它只负责回答：

> **目标、状态、缺口、下一步。**

------

# 20. 页面二：Knowledge / Evidence Space

这个页面不是单纯文件管理器。

它负责回答：

> **“你的这些结论，是从哪里来的？”**

可以查看：

```text
Knowledge
│
├── Papers
├── Notes
├── Projects
└── GitHub
```

同时展示：

```text
Evidence Graph

Claim
↓
Evidence
↓
Source
↓
Attack
↓
Confidence
```

用户可以点击：

> 为什么我只有三星？

系统显示：

```text
支持证据：
+ GitHub项目
+ 任务记录
+ 技术笔记

不足：
- 缺少独立实现
- 缺少Evaluation结果

攻击结果：
当前证据不足以支持四星。
```

透明性是这一页的核心。

------

# 21. 页面三：AI Mentor

这是整个产品最自然的交互入口。

用户可以直接：

```text
我现在应该学什么？

我距离Agent工程师还有什么差距？

为什么我的Memory只有三星？

分析我最近一个月的成长。

帮我设计下一个项目。

把我的目标改成AI测试工程师。
```

聊天背后的 Agent 始终访问：

```text
Goal
+
Memory
+
Capability
+
Evidence
+
Growth History
```

因此它不是通用聊天机器人，而是：

> **认识用户的成长型 Agent。**

------

# 22. 输入系统

MVP 输入仅保留三个入口：

```text
① Chat
② Upload
③ GitHub
```

### Chat

自然语言交流。

用于：

- 目标；
- 偏好；
- 解释；
- 反馈；
- 任务完成结果。

### Upload

用于：

- PDF；
- Markdown；
- TXT；
- 代码；
- 项目文件。

### GitHub

用于：

- 项目；
- 技术栈；
- Commit；
- README；
- Code evidence。

------

# 23. 多格式内容处理

原则：

> **不同格式分别解析，统一进入知识表示层。**

```text
                Input
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
      PDF        Code       Image
        ↓          ↓          ↓
      Parser      AST       OCR
        └──────────┼──────────┘
                   ↓
       Unified Knowledge Model
                   ↓
       Claim / Evidence / Entity
                   ↓
          SQLite + FTS + Graph
```

MVP 不追求“什么都能吃”。

首先确保：

```text
PDF
Markdown
TXT
Code
GitHub
```

链路可靠。

------

# 24. 外部知识

这里不建立“全互联网知识库”。

产品的外部知识主要用于：

> **帮助系统建立目标和能力模型。**

例如：

```text
目标：
AI Agent Engineer

外部参考：
官方文档
技术资料
公开项目
论文
岗位信息
```

然后形成：

```text
Goal
↓
Capability Ontology
```

而不是单纯让用户“搜索资料”。

------

# 25. 能力模型的来源

AI 动态生成能力模型时，需要同时考虑：

```text
用户目标
+
领域知识
+
可信来源
+
已有能力
```

例如：

```text
用户目标：

AI Agent Engineer
```

系统生成：

```text
Capability Model
```

再通过证据不断调整。

因此：

> 能力模型不是一次生成以后永久固定，而是动态可演化对象。

------

# 26. 数据模型

MVP 核心实体：

```text
User
Goal
Capability
Evidence
Claim
Task
Memory
Project
Source
Assessment
Event
```

基本关系：

```text
User
 ↓
Goal
 ↓
Capability
 ↓
Claim
 ↓
Evidence
 ↓
Source
```

以及：

```text
Capability
 ↓
Gap
 ↓
Task
 ↓
Completion
 ↓
New Evidence
```

------

# 27. 核心数据库结构

你现有 `evkg` 的单 SQLite 思路非常适合 MVP。

建议：

```text
SQLite
├── users
├── goals
├── capabilities
├── claims
├── evidence
├── passages
├── sources
├── tasks
├── assessments
├── memories
├── events
└── growth_snapshots
```

搜索：

```text
FTS5
```

结构化查询：

```text
JSON
```

图关系可以在逻辑层维护，不必为了 MVP 强行引入 Neo4j。

------

# 28. 系统总体架构

建议第一版：

```text
                    Frontend
                       │
                       ↓
                  API / Backend
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
     Goal Agent     Knowledge     Growth Agent
          │          Pipeline          │
          │              │             │
          ↓              ↓             ↓
      Capability       EVKG         Scheduler
       Model           Core            │
          │              │             │
          └──────────────┼─────────────┘
                         ↓
                       SQLite
```

------

# 29. Agent 层

不建议一开始做很多 Agent。

MVP 可以只有三个逻辑 Agent。

### 1. Goal Agent

负责：

```text
目标澄清
目标确认
目标更新
```

------

### 2. Assessment Agent

负责：

```text
Evidence分析
Claim生成
Attack
Capability评估
```

这是 EVKG + LLM 的结合。

------

### 3. Growth Agent

负责：

```text
能力缺口
任务生成
每日分析
主动建议
```

后续再考虑 Planner、Executor、Evaluator 等更复杂的多 Agent 架构。

------

# 30. 系统最核心的 Agent Workflow

```text
User Message
      ↓
Context Retrieval
      ↓
Goal / Memory / Evidence
      ↓
LLM Reasoning
      ↓
Tool Calls
      ↓
Evidence / Capability Update
      ↓
Task Decision
      ↓
Response
```

后台主动模式：

```text
Scheduler
 ↓
Event Detection
 ↓
Evidence Analysis
 ↓
Capability Change?
 ↓
Meaningful Event?
 ↓
Growth Agent
 ↓
Notification
```

------

# 31. MVP 必须实现什么

第一版只实现以下能力：

## P0

### Goal

- 自然语言输入目标；
- 多轮澄清；
- 目标确认；
- 目标存储。

### Knowledge

- PDF / Markdown / TXT；
- 代码；
- 基础文本抽取；
- Embedding / Retrieval。

### GitHub

- OAuth；
- 用户选择 Repository；
- 基础项目分析。

### Evidence

- Claim；
- Evidence；
- Source；
- Provenance；
- Attack；
- 基础 Confidence。

### Capability

- 动态生成能力模型；
- 五级星级；
- 能力差距识别。

### Task

- 根据能力缺口生成任务；
- 任务状态；
- 完成记录；
- 完成后重新评估。

### Memory

- Long-term Profile；
- Short-term State；
- Growth History。

### Proactive Agent

- 每日分析；
- 有意义事件提醒；
- 用户可关闭。

### UI

三个核心页面：

```text
Dashboard
Knowledge / Evidence
AI Mentor
```

------

# 32. MVP 明确不做什么

为了避免第一版失控，暂时不做：

```text
× Notion同步
× 浏览器历史
× 微信 / QQ
× 多平台聊天记录导入
× 大规模知识社区
× 多人协作
× 企业组织管理
× 复杂社交
× 全自动学习课程
× 自动替用户写大量项目
× 复杂多Agent系统
× Neo4j等重型图数据库
× 全互联网实时爬取
```

核心原则：

> **先把“证据 → 能力 → 任务 → 成长”闭环跑通。**

------

# 33. MVP 核心成功标准

项目第一版不是以：

```text
页面数量
知识条目数量
LLM调用次数
```

来评价。

而是看：

### 1. Goal Clarification

用户能否从一句模糊目标，得到一个明确目标？

------

### 2. Evidence Traceability

每个重要能力判断是否都能追溯到真实证据？

------

### 3. Capability Audit

系统是否能够发现：

> “用户说自己会，但目前证据并不足。”

------

### 4. Task Quality

给出的任务是否真正针对能力缺口？

------

### 5. Growth Loop

完成任务之后：

```text
Evidence增加
↓
Capability变化
```

是否能够自动发生？

------

### 6. User Return Value

用户过几天回来之后，能不能得到：

> “你发生了什么变化，以及接下来该做什么。”

------

# 34. 产品的核心差异

普通 AI Chat：

```text
Question
↓
Answer
```

普通 RAG：

```text
Question
↓
Retrieve
↓
Answer
```

普通知识库：

```text
Document
↓
Store
↓
Search
```

Growth OS：

```text
Goal
↓
Capability Model
↓
Evidence
↓
Audit
↓
Capability State
↓
Task
↓
Action
↓
Evidence Update
↓
Growth
```

因此核心差异不是：

> “我也用了 RAG。”

而是：

> **我建立了一个围绕“个人目标—能力—证据—行动”的持续状态系统。**

------

# 35. 最核心的产品循环

整个产品最终可以浓缩成一张图：

```text
                    ┌──────────────┐
                    │     Goal     │
                    │     目标      │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │  Capability  │
                    │   能力模型    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   Evidence   │
                    │     证据      │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │    Attack    │
                    │   证据攻击    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   Assess     │
                    │   能力审计    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │     Gap      │
                    │   能力缺口    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │     Task     │
                    │   成长任务    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │    Action    │
                    │   用户行动    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │ New Evidence │
                    │    新证据     │
                    └──────┬───────┘
                           │
                           └──────────→ 回到 Capability
```

------

# 36. 产品最终形态

长期来看，产品可以从：

> AI个人知识库

演化成：

> AI个人成长操作系统。

它长期维护的是三张图：

```text
1. Goal Graph
   我想去哪里

2. Knowledge Graph
   我知道什么

3. Capability / Evidence Graph
   我到底会什么
```

然后通过一个 Agent 将它们连接起来：

```text
             Goal
              ↓
          Capability
              ↓
            Task
              ↓
           Evidence
              ↓
           Growth
```

这就是产品的真正核心。

------

# 37. 一句话产品定义

对用户：

> **一个认识你的 AI 导师，它会根据你的目标、学习资料和真实项目证据，持续判断你会什么、还缺什么，并告诉你下一步应该做什么。**

对技术：

> **一个以 Evidence Graph 为可信底座，以 Memory 为个人状态层，以 Capability Model 为核心状态，以 Agent 为交互与决策引擎的个人成长系统。**

对项目：

> **Goal → Evidence → Capability → Task → Growth 的闭环 AI Agent。**

------

# 38. MVP 第一阶段的真正目标

不是把所有功能做完。

而是证明一件事：

> **一个 AI Agent 能不能仅通过少量个人资料、GitHub 项目和对话，建立一个有证据依据的个人能力模型，并据此持续生成有意义的成长任务。**

只要这个闭环能够稳定跑通：

```text
目标澄清
+
证据收集
+
能力审计
+
任务生成
+
成长更新
```

这个项目就已经有了一个完整、可演示、可继续扩展的产品内核。

后续的文件格式、自动同步、更多职业模型、多用户、团队知识库、商业化，都只是建立在这个内核之上的扩展，而不是 MVP 必须解决的问题。