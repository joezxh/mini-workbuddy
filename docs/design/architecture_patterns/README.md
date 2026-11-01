# 10 种主流 Agent 架构 × AgentScope

用 AgentScope 2.0 实现 10 种主流 Agent 架构的可运行示例。每个脚本一个架构，非交互跑通一个演示任务，并在终端渲染完整事件流。

配套总文档见 [`docs/agent-architecture-patterns-zh.md`](../../docs/agent-architecture-patterns-zh.md)（含每种架构的 Mermaid pipeline 图与选型对照表）。

## 运行前准备

```bash
# 仓库根目录安装（Python >= 3.11）
uv pip install -e .

# DashScope 密钥（默认路径）
export DASHSCOPE_API_KEY=sk-xxxxxxxx
```

切换到 OpenAI 兼容端点（自建网关 / vLLM / GPUStack 等）：

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8000/v1
export OPENAI_API_KEY=EMPTY
```

`_common.make_model()` 检测到 `OPENAI_BASE_URL` 后会自动改用 `OpenAIChatModel`，10 个脚本无需改动。

## 脚本清单

| # | 脚本 | 架构 | 核心构件 |
| --- | --- | --- | --- |
| 01 | `01_react.py` | ReAct 边想边做 | `Agent` + `Toolkit`（内置推理-行动循环） |
| 02 | `02_plan_and_execute.py` | Plan-and-Execute 先谋后动 | `TaskCreate/TaskUpdate/TaskList/TaskGet` + 运行时计划注入 |
| 03 | `03_reflection.py` | Reflection 自我反思 | `reply(structured_schema=...)` 自评 + 同 agent 修订循环 |
| 04 | `04_prompt_chaining.py` | Prompt Chaining 流水线 | `SOP` + `SOPStep` + `SOPEngine` |
| 05 | `05_routing.py` | Routing 智能分流 | 结构化输出分派 + `ModelRouterMiddleware` |
| 06 | `06_parallelization.py` | Parallelization 并行分身 | `asyncio.gather` 扇出 + 多次采样投票 |
| 07 | `07_evaluator_optimizer.py` | Evaluator-Optimizer 生成+评审 | `GoalPipeline` |
| 08 | `08_orchestrator_workers.py` | Orchestrator-Workers 主管派活 | `TeamPipeline` + `TeamMember` |
| 09 | `09_handoff.py` | Handoff 专家交接 | 自定义外部工具 `transfer_to` + 驱动循环 |
| 10 | `10_hierarchical.py` | Hierarchical 层级团队 | 顶层 director 派活给多个子 `TeamPipeline` |

## 逐个运行

```bash
python examples/architecture_patterns/01_react.py
python examples/architecture_patterns/02_plan_and_execute.py
python examples/architecture_patterns/03_reflection.py
python examples/architecture_patterns/04_prompt_chaining.py
python examples/architecture_patterns/05_routing.py
python examples/architecture_patterns/06_parallelization.py
python examples/architecture_patterns/07_evaluator_optimizer.py
python examples/architecture_patterns/08_orchestrator_workers.py
python examples/architecture_patterns/09_handoff.py
python examples/architecture_patterns/10_hierarchical.py
```

## 共享脚手架 `_common.py`

| 函数 | 作用 |
| --- | --- |
| `make_model(model=None)` | 建聊天模型；默认 DashScope `qwen3.8-max`，`OPENAI_BASE_URL` 存在时切 OpenAI 兼容端点 |
| `make_agent(name, system_prompt, tools, ...)` | 建 agent；权限设 `PermissionMode.BYPASS` 以便脚本免交互跑通 |
| `render_stream(stream, verbosity="default")` | 用 `ConsoleRenderer` 渲染事件流，返回最终消息 |
| `get_text(msg)` | 取消息纯文本，便于打印结果 |

## 说明

- 所有脚本均为 `async def main()` + `asyncio.run(main())`，直接 `python` 执行，不需要额外服务。
- 涉及文件读写的模式（02/07/08/10）会共享一个 `LocalWorkspace`，工作目录位于脚本同级 `workspace/`。
- 脚本中的迭代上限（`max_iters`、`max_rounds`、`max_hops`）都刻意调小，便于快速跑完；生产使用请按需放大。
