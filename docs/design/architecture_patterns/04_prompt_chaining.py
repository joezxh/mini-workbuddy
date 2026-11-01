# -*- coding: utf-8 -*-
"""Pattern 4 — Prompt Chaining (fixed steps, each picking up the last).

``SOP`` / ``SOPStep`` / ``SOPEngine`` is the built-in chaining primitive:

- steps run **in order**,
- each step only receives a ``<handover from="previous step">`` block — it
  cannot see the earlier steps' tools, files or conversations, which keeps
  every step's context small and its contract explicit,
- a step can carry a ``verifier``; without one the step is accepted as-is,
  which is the plain "relay" behaviour.

Use it for: drafting → translating → proof-reading — any process whose
steps are fixed and known in advance.
"""
import asyncio

from agentscope.message import UserMsg
from agentscope.sop import SOP, SOPEngine, SOPStep

from _common import make_agent, render_stream


async def main() -> None:
    """Chain three agents: write → translate → proof-read (verified)."""
    writer = make_agent(
        name="Writer",
        system_prompt=(
            "You're a Chinese product marketer. Write a short, punchy "
            "Chinese product intro."
        ),
        max_iters=5,
    )
    translator = make_agent(
        name="Translator",
        system_prompt=(
            "You're a translator. Translate the handed-over Chinese text "
            "into natural English without adding anything."
        ),
        max_iters=5,
    )
    proofreader = make_agent(
        name="Proofreader",
        system_prompt=(
            "You're a proof-reader. Polish the English text handed to you: "
            "fix grammar and rhythm, keep the meaning."
        ),
        max_iters=5,
    )
    critic = make_agent(
        name="Critic",
        system_prompt=(
            "You're a strict editor. Judge whether the English copy is "
            "fluent, faithful to the source and free of grammar errors."
        ),
        max_iters=5,
    )

    sop = SOP(
        name="product-copy",
        description="Chinese draft → English translation → proof-read",
        steps=[
            SOPStep(
                subject="写中文初稿",
                description="Write a 60-word Chinese product intro.",
                executor=writer,
                # verifier=None → pure relay, accepted as-is
            ),
            SOPStep(
                subject="译成英文",
                description="Translate the Chinese draft into English.",
                executor=translator,
            ),
            SOPStep(
                subject="英文审校",
                description="Proof-read the English copy.",
                executor=proofreader,
                verifier=critic,
                max_attempts=2,
            ),
        ],
    )

    engine = SOPEngine(sop)
    await render_stream(
        engine.reply_stream(
            UserMsg(
                name="user",
                content=(
                    "为「AgentScope 2.0 的 TeamPipeline」写一段产品简介，"
                    "强调 leader 通过工具派活、成员并发执行、结果只回给 leader。"
                ),
            ),
        ),
    )

    print("\n===== STEP STATES =====")
    for step, record in zip(sop.steps, engine.state.steps):
        print(f"- {step.subject}: {record.phase.value}")

    print("\n===== FINAL HANDOVER =====")
    submission = engine.state.steps[-1].submission or []
    print(
        "\n".join(
            _.text for _ in submission if getattr(_, "text", None)
        )
        or "(nothing handed over)",
    )


if __name__ == "__main__":
    asyncio.run(main())
