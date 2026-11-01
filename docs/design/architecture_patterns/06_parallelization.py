# -*- coding: utf-8 -*-
"""Pattern 6 — Parallelization (split, run at once, then combine).

Three flavours, all with plain asyncio:

1. **Fan-out / gather** — several independent agents work on the same
   input at the same time, an aggregator merges what came back.
2. **Voting** — the same question is answered by N independent runs and
   the majority (or the best-scored) answer wins.
3. **Concurrent tool calls** — one agent, several tools: AgentScope
   batches the tool calls a model emits in one turn and runs them
   concurrently when every tool is marked ``is_concurrency_safe=True``
   (the default for ``FunctionTool``).

The one rule that matters: **one ``Agent`` instance is one conversation**
(its state holds the context), so every parallel branch needs its own
instance — never gather over the same instance.

Use it for: batch processing, multi-reviewer judging, ensemble answers.
"""
import asyncio
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

from agentscope.message import UserMsg
from agentscope.tool import FunctionTool

from _common import make_agent, render_stream

REVIEW_TARGET = (
    "AgentScope 的 TeamPipeline 让 leader 通过 TeamAssign 工具给成员派活，"
    "成员在各自上下文里执行，结果只回给 leader。"
)
QUESTION = (
    "一段文本有 3 个段落，每段 120 字，用中文写。总分多少字？"
    "选项：A. 240  B. 360  C. 480"
)


class Vote(BaseModel):
    """One voter's answer."""

    answer: Literal["A", "B", "C"] = Field(description="The chosen option.")
    reason: str = Field(description="One line of reasoning.")


async def get_weather(city: str) -> str:
    """Get the current weather of a city.

    Args:
        city (`str`):
            The city name.
    """
    return {"杭州": "晴，28°C", "北京": "多云，22°C"}.get(city, "晴，26°C")


async def get_population(city: str) -> str:
    """Get the population of a city.

    Args:
        city (`str`):
            The city name.
    """
    return {"杭州": "约 1250 万", "北京": "约 2180 万"}.get(city, "未知")


async def fan_out() -> None:
    """Three reviewers at once, then one aggregator."""
    print("===== 1. FAN-OUT / GATHER =====")
    reviewers = [
        make_agent(
            name=f"Reviewer-{role}",
            system_prompt=(
                f"You're a {role} reviewer. Give at most three bullet "
                "points, no preamble."
            ),
            max_iters=5,
        )
        for role in ("accuracy", "clarity", "conciseness")
    ]
    # No rendering here: three streams at once would interleave unreadably
    results = await asyncio.gather(
        *[
            _.reply(UserMsg(name="user", content=f"Review: {REVIEW_TARGET}"))
            for _ in reviewers
        ],
    )
    for reviewer, msg in zip(reviewers, results):
        print(f"\n--- {reviewer.name} ---\n{msg.get_text_content()}")

    aggregator = make_agent(
        name="Aggregator",
        system_prompt="Merge the given reviews into one short verdict.",
        max_iters=5,
    )
    merged = "\n\n".join(
        f"[{_.name}] {msg.get_text_content()}"
        for _, msg in zip(reviewers, results)
    )
    final = await render_stream(
        aggregator.reply_stream(
            UserMsg(name="user", content=f"Summarize these reviews:\n{merged}"),
        ),
    )
    print("\n--- MERGED ---")
    print(final.get_text_content() if final else "(no reply)")


async def voting(n: int = 3) -> None:
    """Ask the same question n times, take the majority answer."""
    print("\n===== 2. VOTING =====")
    voters = [
        make_agent(
            name=f"Voter-{i}",
            system_prompt="Answer the multiple-choice question.",
            max_iters=5,
        )
        for i in range(1, n + 1)
    ]
    msgs = await asyncio.gather(
        *[
            _.reply(UserMsg(name="user", content=QUESTION),
                    structured_schema=Vote)
            for _ in voters
        ],
    )
    votes = []
    for voter, msg in zip(voters, msgs):
        vote = Vote(**(msg.structured_output or {}))
        votes.append(vote.answer)
        print(f"{voter.name}: {vote.answer} ({vote.reason})")

    winner, count = Counter(votes).most_common(1)[0]
    print(f"\nMajority answer: {winner} ({count}/{len(votes)} votes)")


async def concurrent_tools() -> None:
    """One agent, two concurrency-safe tools in one turn."""
    print("\n===== 3. CONCURRENT TOOL CALLS =====")
    agent = make_agent(
        name="Researcher",
        system_prompt=(
            "Answer with the tools. When you need two facts, call both "
            "tools in the SAME turn instead of one after another."
        ),
        tools=[FunctionTool(get_weather), FunctionTool(get_population)],
        max_iters=8,
    )
    final = await agent.reply(
        UserMsg(
            name="user",
            content="杭州和北京今天的天气与常住人口分别是多少？",
        ),
    )
    print(final.get_text_content())


async def main() -> None:
    """Run all three parallelization flavours."""
    await fan_out()
    await voting()
    await concurrent_tools()


if __name__ == "__main__":
    asyncio.run(main())
