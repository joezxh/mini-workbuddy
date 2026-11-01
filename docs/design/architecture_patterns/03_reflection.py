# -*- coding: utf-8 -*-
"""Pattern 3 — Reflection (draft, judge yourself, revise).

The same agent drafts, then grades its own draft through a structured
output (``structured_schema=Review``), then revises — all inside one
context, which is what makes it *reflection* rather than a two-agent
pipeline (see ``07_evaluator_optimizer.py`` for the two-agent variant).

The loop stops when the self-review passes or the round budget runs out.

Use it for: writing code, editing prose — anything where one more pass
noticeably improves the output.
"""
import asyncio

from pydantic import BaseModel, Field

from agentscope.message import UserMsg
from agentscope.types import ReplyFinishedReason

from _common import make_agent, render_stream

MAX_ROUNDS = 3


class Review(BaseModel):
    """What the agent says about its own draft."""

    passed: bool = Field(
        description="Whether the draft is good enough to hand over.",
    )
    score: int = Field(
        description="A score from 1 to 10 for the current draft.",
    )
    issues: list[str] = Field(
        description=(
            "Concrete, actionable problems to fix. Empty when it passes."
        ),
    )


async def main() -> None:
    """Draft a release note, then reflect and revise until it passes."""
    agent = make_agent(
        name="Writer",
        system_prompt=(
            "You're a technical writer. You write, then you review your own "
            "work honestly: say what is wrong, don't flatter yourself."
        ),
        max_iters=10,
    )

    task = UserMsg(
        name="user",
        content=(
            "为 AgentScope 2.0 的 TeamPipeline 写一段 80 字以内的发布说明，"
            "面向开发者，突出「leader 通过工具派活、成员结果只回给 leader」。"
        ),
    )

    print("===== ROUND 0: DRAFT =====")
    draft = await render_stream(agent.reply_stream(task))

    for round_ in range(1, MAX_ROUNDS + 1):
        print(f"\n===== ROUND {round_}: SELF-REVIEW =====")
        review_msg = await agent.reply(
            UserMsg(
                name="user",
                content=(
                    "Review the draft you just wrote. Be strict and specific."
                ),
            ),
            structured_schema=Review,
        )
        if review_msg.finished_reason != ReplyFinishedReason.COMPLETED or (
            review_msg.structured_output is None
        ):
            print("No valid review, stop here.")
            break

        review = Review(**review_msg.structured_output)
        print(f"passed={review.passed} score={review.score}")
        for issue in review.issues:
            print(f"  - {issue}")

        if review.passed or not review.issues:
            break

        print(f"\n===== ROUND {round_}: REVISION =====")
        draft = await render_stream(
            agent.reply_stream(
                UserMsg(
                    name="user",
                    content=(
                        "Revise your draft to fix these issues, and nothing "
                        "else:\n"
                        + "\n".join(f"- {_}" for _ in review.issues)
                    ),
                ),
            ),
        )

    print("\n===== FINAL DRAFT =====")
    print(draft.get_text_content() if draft else "(no reply)")


if __name__ == "__main__":
    asyncio.run(main())
