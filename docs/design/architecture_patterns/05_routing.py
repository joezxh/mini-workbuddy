# -*- coding: utf-8 -*-
"""Pattern 5 — Routing (classify first, then dispatch).

Two independent routing axes, both built in:

1. **Route the work.** A router agent answers with a structured output
   (``Literal[...]``), and the driver hands the request to the matching
   expert agent. This is the客服分流 / 选流程 case.
2. **Route the model.** ``ModelRouterMiddleware`` swaps ``agent.model``
   per reply according to a classifier — same agent, different model for
   easy vs. hard questions. This is the 选模型 case, and it needs no
   driver code at all.

Use it for: support triage, model selection, any fan-out where the branch
is chosen per request.
"""
import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from agentscope.middleware import ChatModelCandidate, ModelRouterMiddleware
from agentscope.message import UserMsg

from _common import make_agent, make_model, render_stream


class Route(BaseModel):
    """Where the request should go."""

    expert: Literal["billing", "tech", "general"] = Field(
        description=(
            "billing: 退款/发票/价格；tech: 报错/接入/配置；"
            "general: 其他"
        ),
    )
    reason: str = Field(description="One line explaining the choice.")


async def main() -> None:
    """Route three requests to experts, then demo model routing."""
    router = make_agent(
        name="Router",
        system_prompt=(
            "You're a support triager. Classify the request into exactly one "
            "expert and explain why in one line."
        ),
        max_iters=5,
    )
    experts = {
        "billing": make_agent(
            name="Billing",
            system_prompt="You're a billing specialist. Be precise about "
            "refunds, invoices and prices.",
            max_iters=5,
        ),
        "tech": make_agent(
            name="Tech",
            system_prompt="You're a technical support engineer. Give the "
            "exact commands or config to fix the problem.",
            max_iters=5,
        ),
        "general": make_agent(
            name="General",
            system_prompt="You're a friendly general support agent.",
            max_iters=5,
        ),
    }

    requests = [
        "我上个月重复扣费了，怎么退款？",
        "TeamPipeline 里成员之间为什么看不到彼此的对话？",
        "你们的服务覆盖哪些地区？",
    ]

    for text in requests:
        print(f"\n===== REQUEST: {text} =====")
        routed = await router.reply(UserMsg(name="user", content=text),
                                    structured_schema=Route)
        route = Route(**routed.structured_output)
        print(f"→ expert={route.expert} ({route.reason})")
        await render_stream(
            experts[route.expert].reply_stream(UserMsg(name="user",
                                                       content=text)),
        )

    # --------------------------------------------------------------
    # Axis 2: route the MODEL with a middleware, no driver code needed
    # --------------------------------------------------------------
    print("\n===== MODEL ROUTING =====")
    # Two different models in production; the same one is used twice here so
    # the example needs no extra credentials.
    strong = make_model()
    fast = make_model()
    agent = make_agent(
        name="Adaptive",
        system_prompt="You're a helpful assistant.",
        max_iters=5,
        model=fast,
        # The middleware swaps agent.model per reply and restores it after
        middlewares=[
            ModelRouterMiddleware(
                classifier_model=strong,
                candidates=[
                    ChatModelCandidate(
                        name="strong",
                        model=strong,
                        description="复杂推理、长文写作、代码生成",
                    ),
                    ChatModelCandidate(
                        name="fast",
                        model=fast,
                        description="简单问答、闲聊、格式转换",
                    ),
                ],
            ),
        ],
    )
    await render_stream(
        agent.reply_stream(
            UserMsg(name="user", content="用一句话解释什么是向量数据库？"),
        ),
    )


if __name__ == "__main__":
    asyncio.run(main())
