# -*- coding: utf-8 -*-
"""Pattern 7 — Evaluator-Optimizer (one generates, another judges).

``GoalPipeline`` is this pattern, ready-made:

- the **executor** works towards the goal and ends with a structured
  achievement report,
- the **verifier** judges that report against the goal and answers
  ``pass`` / ``fail`` / ``impossible``,
- on ``fail`` the verifier's message is fed back to the executor and it
  tries again, up to ``max_iters`` times.

Unlike ``03_reflection.py`` the two roles are separate agents, so the
verifier never sees the executor's scratchpad — it judges the work, not
the reasoning.

Use it for: translation quality loops, copy improvement, "keep fixing
until the tests pass".
"""
import asyncio
import os

from agentscope.pipeline import GoalPipeline
from agentscope.message import UserMsg
from agentscope.workspace import LocalWorkspace

from _common import make_agent, render_stream

WORKDIR = os.path.join(os.path.dirname(__file__), "workspace")

GOAL = (
    "在 workspace 目录下写一个 Python 文件 fib.py：定义 fib(n) 返回第 n 个"
    "斐波那契数（fib(0)=0, fib(1)=1），并用 assert 覆盖 n=0,1,2,10 四个用例。"
    "文件必须能被 `python fib.py` 直接运行且不报错。"
)


async def main() -> None:
    """Run an executor-verifier loop until the verifier passes."""
    async with LocalWorkspace(workdir=WORKDIR) as workspace:
        tools = await workspace.list_tools()
        executor = make_agent(
            name="Executor",
            system_prompt=(
                "You're a programmer. Write the code, run it to check, and "
                "end your reply with a report of what you produced."
            ),
            tools=tools,
            offloader=workspace,
            max_iters=20,
        )
        verifier = make_agent(
            name="Verifier",
            system_prompt=(
                "You're a strict verifier. Read the actual files before "
                "judging; 'pass' only when the goal is truly met, otherwise "
                "say exactly what is wrong and what to change."
            ),
            tools=tools,
            offloader=workspace,
            max_iters=20,
        )

        pipe = GoalPipeline(
            executor=executor,
            verifier=verifier,
            max_iters=3,
            max_retries=2,
        )

        await render_stream(
            pipe.reply_stream(UserMsg(name="user", content=GOAL)),
        )


if __name__ == "__main__":
    asyncio.run(main())
