# -*- coding: utf-8 -*-
"""Pattern 1 — ReAct (reasoning-acting).

The agent thinks, calls a tool, looks at what came back, and thinks
again — until it can answer. In AgentScope this loop is **built into
``Agent``**: you only supply the model, the system prompt and the tools.
There is no loop to write.

Use it for: search Q&A, general assistants — anything where the number
of steps is not known up front.
"""
import asyncio

from agentscope.message import UserMsg
from agentscope.tool import FunctionTool

from _common import make_agent, render_stream


async def get_weather(city: str) -> str:
    """Get the current weather of a city.

    Args:
        city (`str`):
            The city name, e.g. "杭州".
    """
    table = {"杭州": "晴，28°C", "北京": "多云，22°C", "上海": "小雨，25°C"}
    return table.get(city, f"{city}：晴，26°C")


async def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression.

    Args:
        expression (`str`):
            The expression to evaluate, e.g. "(12 + 8) * 3".
    """
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as exc:  # noqa: BLE001
        return f"Invalid expression: {exc}"


async def main() -> None:
    """Run a ReAct agent on a question that needs both tools."""
    agent = make_agent(
        name="Friday",
        system_prompt=(
            "You're a helpful assistant named Friday. Answer with the tools "
            "you have; never guess a value you could look up."
        ),
        tools=[
            FunctionTool(get_weather),
            FunctionTool(calculator),
        ],
        max_iters=10,
    )

    final = await render_stream(
        agent.reply_stream(
            UserMsg(
                name="user",
                content=(
                    "杭州和北京今天谁更热？温差是多少摄氏度？"
                    "顺便算一下 (12 + 8) * 3。"
                ),
            ),
        ),
    )
    print("\n===== FINAL ANSWER =====")
    print(final.get_text_content() if final else "(no reply)")


if __name__ == "__main__":
    asyncio.run(main())
