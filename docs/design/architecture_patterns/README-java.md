# 10 种主流 Agent 架构 × AgentScope Java

用 [AgentScope Java 2.0](https://github.com/agentscope-ai/agentscope-java)（源码仓库 `agentscope-java`，本示例默认按其 `2.1.0-SNAPSHOT` 的 API 编写）实现与 Python 版（本目录 `01_react.py` ~ `10_hierarchical.py`，见 [README.md](README.md)）完全对应的 10 种 Agent 设计模式。

每个 Java 范例：模式名称 + 适用场景 + AgentScope Java 核心概念（`ReActAgent`、消息模型、`@Tool` 工具调用、结构化输出、事件流、子智能体）+ 可独立编译运行的完整代码。

## 文件对照表（Java ↔ Python）

| # | Java（本目录） | Python（对照） | 架构 | AgentScope Java 核心构件 |
| --- | --- | --- | --- | --- |
| 01 | `Pattern01ReAct.java` | `01_react.py` | ReAct 边想边做 | `ReActAgent` + `Toolkit` + `@Tool`/`@ToolParam` + `streamEvents` 事件流 |
| 02 | `Pattern02PlanAndExecute.java` | `02_plan_and_execute.py` | Plan-and-Execute 先谋后动 | `Builder#enableTaskList(true)`：内置 `todo_write` 工具 + `TaskReminderMiddleware` 每轮回注计划 |
| 03 | `Pattern03Reflection.java` | `03_reflection.py` | Reflection 自我反思 | 同一 Agent + 结构化输出 `call(msg, Review.class)` 自评后回喂修订 |
| 04 | `Pattern04PromptChaining.java` | `04_prompt_chaining.py` | Prompt Chaining 流水线 | 多个 `ReActAgent` 顺序接力（Java 版无 `SOP`，手工串联） |
| 05 | `Pattern05Routing.java` | `05_routing.py` | Routing 智能分流 | 结构化输出 `Route` 选专家 + 分发表派发（备注 `JevModelRouterMiddleware` 选模型轴） |
| 06 | `Pattern06Parallelization.java` | `06_parallelization.py` | Parallelization 并行分身 | Reactor `Flux.flatMap` 扇出/投票 + `ToolkitConfig.parallel(true)` 并发工具 |
| 07 | `Pattern07EvaluatorOptimizer.java` | `07_evaluator_optimizer.py` | Evaluator-Optimizer 生成+评审 | executor + verifier（结构化 `Verdict`）驱动循环（Java 版无 `GoalPipeline`） |
| 08 | `Pattern08OrchestratorWorkers.java` | `08_orchestrator_workers.py` | Orchestrator-Workers 主管派活 | `SubAgentTool` + `SubAgentProvider`/`SubAgentConfig`：成员即工具，独立上下文 |
| 09 | `Pattern09Handoff.java` | `09_handoff.py` | Handoff 专家交接 | 结构化输出 `HandoffDecision` 交接信号 + 驱动循环切换专家 |
| 10 | `Pattern10Hierarchical.java` | `10_hierarchical.py` | Hierarchical 层级团队 | 嵌套 `SubAgentTool`：director → 子团队 leader → 成员 |

共享脚手架：`PatternSupport.java`（对应 `_common.py`）——模型/Agent 工厂与事件流打印。

## 与 Python 版的能力对照（重要）

| 能力 | AgentScope (Python) | AgentScope Java 2.0 |
| --- | --- | --- |
| 内置 ReAct 循环 | `Agent` | `ReActAgent`（`io.agentscope.core.ReActAgent`） |
| 工具注解 | `FunctionTool` 包装函数 | `@Tool` / `@ToolParam` 注解 POJO 方法 |
| 结构化输出 | `reply(..., structured_schema=Model)` | `call(msg, Schema.class)` → `msg.getStructuredData(Schema.class)` |
| 事件流 | `reply_stream` → `AgentEvent` | `streamEvents(...)` → `Flux<AgentEvent>`（32 种类型化事件） |
| 内置任务/计划 | `TaskCreate/TaskUpdate/...` + 注入 | `enableTaskList(true)`：`todo_write` + `TaskReminderMiddleware` |
| Evaluator-Optimizer | `GoalPipeline`（内置） | 无内置 → 手写驱动循环 |
| 多步骤流程 | `SOP`/`SOPStep`（内置） | 无内置 → 顺序 `call` 串联 |
| 主管派活 | `TeamPipeline`（内置） | `SubAgentTool`（成员即工具）；生产可用 `HarnessAgent.subagent(SubagentDeclaration)` |
| 选模型中间件 | `ModelRouterMiddleware` | `JevModelRouterMiddleware` / `OpenAIDecisionsModelRouterMiddleware`（需额外 Key） |
| 响应式模型 | asyncio | Project Reactor（`Mono`/`Flux`），`.block()` 同步等待 |

## 运行前准备

- JDK 17+
- Maven 3.8+
- 环境变量：`export DASHSCOPE_API_KEY=sk-xxxx`
- 切换 OpenAI 兼容端点：`export OPENAI_API_KEY=...` 与 `export OPENAI_BASE_URL=...`，并把各示例中的模型 ID 改为 `openai:<模型名>`（或在 `PatternSupport.MODEL_ID` 一处修改）

## 编译与运行

方式一：Maven（推荐，`pom-java.xml` 已配置好依赖与 exec 插件）

```bash
cd examples/architecture_patterns

# 编译
mvn -f pom-java.xml compile

# 逐个运行（mainClass 换成对应类名即可）
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern01ReAct
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern02PlanAndExecute
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern03Reflection
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern04PromptChaining
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern05Routing
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern06Parallelization
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern07EvaluatorOptimizer
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern08OrchestratorWorkers
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern09Handoff
mvn -f pom-java.xml exec:java -Dexec.mainClass=io.agentscope.examples.patterns.Pattern10Hierarchical
```

方式二：javac + java（不想用 Maven 时，先把依赖 jar 拷到 `libs/`）

```bash
mvn -f pom-java.xml dependency:copy-dependencies -DoutputDirectory=libs
javac -encoding UTF-8 -cp "libs/*" -d out Pattern*.java
java -cp "out;libs/*" io.agentscope.examples.patterns.Pattern01ReAct      # Windows
java -cp "out:libs/*" io.agentscope.examples.patterns.Pattern01ReAct      # Linux/macOS
```

> 版本说明：`pom-java.xml` 默认使用 Maven Central 的 GA 版本 `2.0.3`；若在
> agentscope-java 源码仓库本地执行过 `mvn install -DskipTests`，可把
> `<agentscope.version>` 改为 `2.1.0-SNAPSHOT` 与源码对照。

## 10 个模式在 Java 版中的实现要点

| # | 实现要点 |
| --- | --- |
| 01 | 循环内置在 `ReActAgent` 里；`@Tool` 注解即工具；`streamEvents` 实时打印文本增量与 `TOOL_CALL_START` |
| 02 | 计划存在 Agent 状态里：`todo_write` 由模型自己维护，`TaskReminderMiddleware` 每轮把清单注回上下文 |
| 03 | 评审与写作同一个 Agent（共享上下文）；`call(msg, Review.class)` + `hasStructuredData()` 判定有效性 |
| 04 | 步骤固定：上一步 `getTextContent()` 作为下一步输入；需异步时换 `Mono.flatMap` |
| 05 | 路由与执行解耦：`Route.expert` 由结构化输出约束取值；模型路由轴见 `JevModelRouterMiddleware` |
| 06 | `Flux.flatMap` 天然并发（每个分支独立 Agent 实例）；`ToolkitConfig.parallel(true)` 控制一轮多工具并发 |
| 07 | verifier 必须有真实判据（本例给它同样的计算器工具先验算再判）；fail 把 `message` 回喂 |
| 08 | `SubAgentProvider` 每次会话创建全新实例（`ReActAgent` 非线程安全）；成员只见完整任务指令，结果只回 leader |
| 09 | 交接信号 = 结构化输出的 `HandoffDecision`；交接的是摘要而非对话；`MAX_HOPS` 防死循环 |
| 10 | 嵌套两层 SubAgentTool；每层 leader 只面对 2-3 个选项；子 Agent 建议视为叶子，不再继续派生 |

## 设计说明

- **为什么 03/04/07/09/10 有手写编排？** Python 版的 `GoalPipeline` / `SOP` /
  `TeamPipeline` 是框架内置编排；Java 版 2.x 把这些留给应用层（提供 `SubAgentTool`、
  Reactor 组合子、`HarnessAgent` 声明式子智能体等更细的积木），因此这些模式的
  Java 范例是"最小驱动循环 + 核心构件"的组合，恰好能看清模式本身的控制流。
- **版本对照**：本目录同时有 Python 与 Java 两套示例，模式编号一一对应，
  场景任务尽量相同，便于逐行对照学习。
