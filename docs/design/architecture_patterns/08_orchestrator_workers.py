# -*- coding: utf-8 -*-
"""Pattern 8 — Orchestrator-Workers (a leader splits the work dynamically).

``TeamPipeline`` is this pattern, ready-made:

- the **leader** gets one extra tool, ``TeamAssign(member, prompt)``, and
  decides *by itself* what to delegate and to whom,
- every **member** runs in its own context and only its final reply comes
  back as the tool result — the leader never sees the member's tool calls
  or intermediate thinking,
- assignments issued in the same round run **concurrently**, except that
  two assignments to the same member queue up,
- members never talk to each other; the leader aggregates.

This is the key difference from Orchestrator-with-a-plan: the split is
decided at runtime by the model, not fixed in code.

Use it for: deep research, large coding tasks, anything whose subtasks
depend on what the leader discovers on the way.
"""
import asyncio
import os

from agentscope.pipeline import TeamMember, TeamPipeline
from agentscope.message import UserMsg
from agentscope.workspace import LocalWorkspace

from _common import make_agent, render_stream

WORKDIR = os.path.join(os.path.dirname(__file__), "workspace")


async def main() -> None:
    """Let a leader delegate a small research-and-write job."""
    async with LocalWorkspace(workdir=WORKDIR) as workspace:
        file_tools = await workspace.list_tools()

        researcher = make_agent(
            name="Researcher",
            system_prompt=(
                "You're a researcher. Answer with facts and cite where they "
                "came from. Keep it under 200 words."
            ),
            tools=file_tools,
            offloader=workspace,
            max_iters=10,
        )
        coder = make_agent(
            name="Coder",
            system_prompt=(
                "You're a Python programmer. Write runnable code and test it "
                "before you answer."
            ),
            tools=file_tools,
            offloader=workspace,
            max_iters=15,
        )
        writer = make_agent(
            name="Writer",
            system_prompt=(
                "You're a technical writer. Turn the material you are given "
                "into a clear, well-structured document."
            ),
            tools=file_tools,
            offloader=workspace,
            max_iters=10,
        )

        leader = make_agent(
            name="Leader",
            system_prompt=(
                "You're a tech lead. Break the request into 2-4 subtasks and "
                "delegate each with TeamAssign. Give every member EVERYTHING "
                "it needs — it cannot see your conversation. When all results "
                "are in, write the final deliverable yourself."
            ),
            max_iters=15,
        )

        pipe = TeamPipeline(
            leader=leader,
            members=[
                TeamMember(
                    agent=researcher,
                    description="调研事实与概念，返回带来源的要点清单",
                ),
                TeamMember(
                    agent=coder,
                    description="写并运行 Python 代码，返回代码与运行结果",
                ),
                TeamMember(
                    agent=writer,
                    description="把素材整理成结构化的中文文档",
                ),
            ],
        )

        final = await render_stream(
            pipe.reply_stream(
                UserMsg(
                    name="user",
                    content=(
                        "产出一份《AgentScope TeamPipeline 上手指南》："
                        "先用 Researcher 确认 TeamPipeline 的三条关键语义"
                        "（派活方式、成员上下文隔离、并发规则），"
                        "再用 Coder 写一个最小可运行示例，"
                        "最后由 Writer 汇总写成 guide.md 放进 workspace。"
                    ),
                ),
            ),
        )
        print("\n===== LEADER'S FINAL ANSWER =====")
        print(final.get_text_content() if final else "(no reply)")


if __name__ == "__main__":
    asyncio.run(main())
