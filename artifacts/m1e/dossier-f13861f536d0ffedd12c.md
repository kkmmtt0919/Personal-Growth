# 能力证据档案：用户 —[实现过]-> RAG 检索服务（基于 Spring Boot 与 ChromaDB 的测试用例生成平台…

## 生成信息
- **生成时间**：2026-10-02T03:02:33+00:00
- **数据库**：`D:\projects\Personal Growth\data\growth.db`
- **生成脚本**：`artifacts/m1e/run_dossier.py`
- **数据范围**：库中共 3 个来源、109 条段落、2 条主张、6 条证据行；**本档案只覆盖其中 1 条主张**
- **分数呈现**：保留 3 位小数，便于直接与数据库逐字段对照
- **复核模型**：deepseek-flash
- **抽取所用模型**：**未记录在案**。抽取阶段没有把模型名写入数据库，因此此处无法给出历史事实 —— 当前配置值不作为该次抽取的记录。

## 一、主张与最终状态
- **主张 ID**：`clm_f13861f536d0ffedd12c`
- **陈述**：原文（README）描述的项目 MYtest 中实现了 RAG 检索服务、AI 调用服务、测试用例生成等模块，且展示了优化前后量化指标；但未明确用户本人在项目中的具体角色与贡献，能力主张仅基于项目描述本身。
- **三元组**：用户 —[实现过]-> RAG 检索服务（基于 Spring Boot 与 ChromaDB 的测试用例生成平台 MYtest）
- **最终状态**：**`disputed`**
- **综合置信度**：0.170
  - 来源可靠性 0.820｜抽取质量 0.350｜互证 0.000｜矛盾惩罚 0.000
  - 分级状态：`assessed`
  - 依据：原文仅展示 MYtest 项目的 README 目录结构与量化指标，能够证明该项目包含 RagService.java、ChromaDB 数据及 RAG 相关模块，但没有直接说明用户本人在其中承担开发、实现或独立贡献的角色。README 属于项目自述/二手描述，代码目录与指标表也不等同于用户个人实现能力的直接证据，因此不足以直接支持“用户实现过 RAG 检索服务”这一主张。
- **复核处置**：`disputed_by_adversarial`

## 二、证据链（按环节顺序）
### 1. 原始来源
- `src_d81f3f5932e5a9e7` **README**｜evkg 类型 `primary`｜来源：file:///D:/projects/mytset-rag/README.md

### 2. 段落与逐字摘录
- `p_1b8447226daad0ff`（第 47 段，来源类型 `primary`，基线 0.820）
  > ``` MYtest/ ├── .idea/ # IDE 配置文件（建议忽略提交） ├── .gitignore # Git 忽略文件配置 ├── pom.xml # Maven 项目依赖配置 ├── README.md # 项目说明文档 │ ├── chroma_data/ # ChromaDB 向量数据库存储 │ └── chroma.sqlite3 # 向量数据文件 │ ├── scripts/ # Python 脚本目录 │ ├── retrieval_service.py # 向量检索服务（Fresh/Flask 封装） │ └── vectorize_cases.py # 测试用例向量化脚本 │ ├── src/ # Spring Boot 后端主代码 │ └── main/ │ ├── java/com/hw/ │ │ ├── controller/ # API 控制器层 │ │ │ ├── InterfaceDocController.java │ │ │ ├── TestCaseController.java │ │ │ ├── McpController.java │ │ │ └── TestController.java │ │ ├── service/ # 业务逻辑层 │ │ │ ├── impl/ # 服务实现类 │ │ │ ├── IInterfaceDocService.java │ │ │ ├── ITestCaseService.java │ │ │ ├── AiService.java # AI 调用服务 │ │ │ ├── RagService.java # RAG 检索服务 │ │ │ ├── TestGenerationService.java # 测试用例生成服务 │ │ │ └── VectorRetrievalService.java # 向量检索服务 │ │ ├── mapper/ # MyBatis 数据访问层 │ │ ├── entity/ # 数据库实体类 │ │ ├── dto/ # 数据传输对象 │ │ ├── mcp/ # MCP 协议相关实现 │ │ └── Application.java # Spring Boot 启动类 │ └── resources/ │ ├── mapper/ # MyBatis XML 映射文件 │ ├── prompts/ # AI 提示词模板 │ │ └── test_case_generation.txt │ ├── static/ # 静态资源（如 index.html） │ └── application.yml # Spring Boot 配置文件 │ ├── test/ # 单元测试目录 ├── target/ # Maven 编译输出目录（建议忽略提交） └── venv/ # Python 虚拟环境（建议忽略提交） ├── Lib/ └── pyvenv.cfg ```
- `p_e9ca93d22aa5a18e`（第 45 段，来源类型 `primary`，基线 0.820）
  > | 指标 | 优化前 | 优化后 | 提升 | |------|--------|--------|------| | 检索召回率（Hit@5） | 65% | 92% | +27% | | 生成用例场景覆盖率 | 70% | 95% | +25% | | AI 执行成功率 | - | 82% | - | | 首次可执行率 | - | 91% | - | | 人工介入时间 | 100% | 40% | -60% | | 单接口用例生成 P99 响应时间 | 8s | 2.5s | -68% |

### 3. 抽取结果（模型产出，非事实）
- `p_1b8447226daad0ff`：polarity=`supports`，抽取置信 0.350
  - 抽取说明：候选主张的原文绑定，尚未完成审查
- `p_e9ca93d22aa5a18e`：polarity=`supports`，抽取置信 0.350
  - 抽取说明：候选主张的原文绑定，尚未完成审查

### 4. 独立复核意见（另一模型产出，非事实）
- `p_1b8447226daad0ff`：**polarity=`partial`**，复核置信 0.170
  - 复核意见：原文仅展示 MYtest 项目的 README 目录结构与量化指标，能够证明该项目包含 RagService.java、ChromaDB 数据及 RAG 相关模块，但没有直接说明用户本人在其中承担开发、实现或独立贡献的角色。README 属于项目自述/二手描述，代码目录与指标表也不等同于用户个人实现能力的直接证据，因此不足以直接支持“用户实现过 RAG 检索服务”这一主张。
- `p_e9ca93d22aa5a18e`：**polarity=`partial`**，复核置信 0.170
  - 复核意见：原文仅展示 MYtest 项目的 README 目录结构与量化指标，能够证明该项目包含 RagService.java、ChromaDB 数据及 RAG 相关模块，但没有直接说明用户本人在其中承担开发、实现或独立贡献的角色。README 属于项目自述/二手描述，代码目录与指标表也不等同于用户个人实现能力的直接证据，因此不足以直接支持“用户实现过 RAG 检索服务”这一主张。

### 5. 对抗攻击与裁决（复核模型裁决）
- **质疑角度**：仅基于 README 自述，无独立验证（用户角色不明）
  - 质疑：MYtest 项目的量化指标（Hit@5 92% 等）全部来自项目 README 自述，且未说明用户在项目中的角色——这是个人独立完成、团队协作还是照抄教程/开源项目？是否存在证明用户本人写了 RAG 检索服务的代码提交记录或可运行产物？
  - **裁决：`broken`**
  - 裁决理由：给定证据仅包含项目 README 的目录结构和自述量化指标，能够证明 MYtest 项目包含 RagService.java 等文件，但无法证明用户本人实现过 RAG 检索服务。主张将项目存在等同于用户个人实现，加入了原文没有的信息（用户角色与贡献）。攻击质疑成立，且无任何直接证据（如提交记录、署名、可运行产物）支持用户独立完成或参与开发。因此，该主张在现有证据下无法成立。
  - 时间：2026-10-02 02:54:17
- **质疑角度**：代码独立性与二手资料风险
  - 质疑：该项目的 RAG 检索是否只是调用 ChromaDB 与现成大模型 API 的标准教程式组合（如 LangChain/Spring AI 模板），还是包含用户独立设计的检索优化？声称召回率从 65% 提升到 92% 的优化手段是否有对应代码与实验记录佐证，还是仅在 README 中口头给出？
  - **裁决：`broken`**
  - 裁决理由：给定证据仅包含 README 目录结构与一张量化指标表。目录确实显示项目存在 RagService.java、VectorRetrievalService.java、retrieval_service.py、chroma_data 等 RAG 相关文件，但这只能证明 MYtest 项目包含 RAG 检索模块，不能证明用户本人“实现过”该服务，更不能证明其独立设计的检索优化。指标表虽列出 Hit@5 从 65% 提升到 92%，但没有任何实验记录、基准说明、评测脚本、代码 diff、提交作者或设计文档佐证。质疑所指出的“标准教程式组合”风险（如仅拼接 ChromaDB 与现成大模型 API）在现有证据中无法排除。主张本身也承认未明确用户角色与贡献，仅基于项目 README 描述。因此，该主张在只允许使用给定证据的前提下无法成立，质疑成立。
  - 时间：2026-10-02 02:54:17

### 6. 最终状态如何得到
上述各步都是**模型的判断**，不是已被证实的事实。最终状态由这些判断合并而来：
- 抽取阶段把状态置为 `extracted`（此时尚无任何复核）
- 独立复核给出 polarity 与复核置信，并按证据是否充分决定是否转为 `machine_reviewed`
- 对抗裁决为 ['broken', 'broken']；出现 `broken` 时主张被置为 `disputed`
- **当前状态：`disputed`** —— 这是一个可复核的判断，而非定论

## 三、尚未确认的证据（不等于造假）
以下条目是攻击环节指出的**尚未确认**的信息。
**缺失证据不等于造假**：它只说明现有材料不足以支持该主张，既不构成“用户没做过”的判断，也不构成“材料不实”的判断。
要把它们变成结论，需要补充相应证据后重新评估。

**来自 `broken` 裁决**：
- 用户本人在项目中的角色说明（如个人独立/团队协作）
- 证明用户编写了 RAG 检索服务代码的提交记录、代码署名或可运行产物
- 排除照抄教程或开源项目的证据（如原创性说明、开发过程记录）
- 独立于 README 的第三方验证（如代码仓库链接、部署实例）

**来自 `broken` 裁决**：
- 用户本人承担 MYtest 项目中 RAG 检索服务开发/实现的直接证据（如提交记录、作者归属、项目角色说明）
- 声称召回率从 65% 提升到 92% 的检索优化具体设计与代码 diff
- 该指标对应的实验记录：评测数据集、基线配置、评测脚本、复现命令与测量方法
- 排除该项目仅为 ChromaDB、LangChain/Spring AI 模板等标准教程式组合的证据
- RagService.java、VectorRetrievalService.java、retrieval_service.py 之间的具体实现逻辑与用户独立贡献说明

## 四、两类“独立”的取值与含义
本档案涉及两个都叫“独立”但**毫不相关**的概念，不可互换：
  - **复核模型独立**（`independent_verifier`）：做复核/裁决的模型是否与抽取模型不同。
    衡量的是**复核机制**是否可能自我偏袒。
  - **证据来源独立**（`evidence.independent_source`）：该主张的证据是否跨多个不同来源。
    衡量的是**证据互证**程度。若两条证据都出自同一份文件，此项为 False，这是正确结果，不代表复核不独立。

- `independent_verifier = True`（复核模型：deepseek-flash）
- `evidence.independent_source = False`（本主张的证据是否跨多个来源）

## 五、本档案不成立的结论
为避免把模型判断读成事实，明确列出**本档案不能支持**的推论：
- 不能得出“用户具备该能力”的结论 —— 档案只呈现证据是否充分，不代替能力评级。
- 不能由“项目存在”推出“用户个人实现”：本库的归属层尚未建立，`repo_artifact` 等材料只能证明材料本身的内容。
- 不能把本条主张的状态推广为“系统的能力评估整体可靠”的结论。
- 不能把缺失证据读作造假或未做过。

## 附：原始审计轨迹
- 2026-10-02 02:54:17 `claim_saved`
- 2026-10-02 02:54:17 `claim_saved`
- 2026-10-02 02:53:54 `claim_saved`
- 2026-10-02 02:48:01 `claim_saved`

