# -*- coding: utf-8 -*-
"""Shared scaffolding for the architecture pattern examples.

Ten mainstream agent architectures, each in its own script, all sharing
the model/agent/rendering factories below so that the examples stay
short and the differences between the patterns stay visible.

Environment variables
---------------------
``DASHSCOPE_API_KEY``
    Used by the default DashScope model.
``OPENAI_BASE_URL`` / ``OPENAI_API_KEY``
    Optional. When ``OPENAI_BASE_URL`` is set, ``make_model`` builds an
    OpenAI-compatible chat model instead, which is how you point the
    examples at a self-hosted gateway.
"""
import os
from typing import Any, AsyncGenerator, Sequence

from agentscope.agent import Agent, ReActConfig
from agentscope.console import ConsoleRenderer
from agentscope.credential import DashScopeCredential, OpenAICredential
from agentscope.message import Msg
from agentscope.model import (
    ChatModelBase,
    DashScopeChatModel,
    OpenAIChatModel,
)
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import ToolBase, Toolkit
from agentscope.workspace import Offloader

DEFAULT_MODEL = "qwen3.8-max"
"""The default DashScope model used by every example."""


def make_model(model: str | None = None) -> ChatModelBase:
    """Build the chat model shared by the examples.

    DashScope by default. Set ``OPENAI_BASE_URL`` to switch the whole
    directory over to an OpenAI-compatible endpoint, e.g.

    .. code-block:: python

        # One line to switch to an OpenAI-compatible endpoint
        model = OpenAIChatModel(
            credential=OpenAICredential(
                api_key=os.environ["OPENAI_API_KEY"],
                base_url="http://127.0.0.1:8000/v1",
            ),
            model="qwen3-32b",
        )

    Args:
        model (`str | None`, optional):
            The model name. Defaults to :data:`DEFAULT_MODEL`.

    Returns:
        `ChatModelBase`:
            The chat model to hand to the agents.
    """
    model = model or DEFAULT_MODEL
    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        return OpenAIChatModel(
            credential=OpenAICredential(
                api_key=os.environ.get("OPENAI_API_KEY", "EMPTY"),
                base_url=base_url,
            ),
            model=model,
        )
    return DashScopeChatModel(
        credential=DashScopeCredential(
            api_key=os.environ["DASHSCOPE_API_KEY"],
        ),
        model=model,
    )


def make_agent(
    name: str,
    system_prompt: str,
    tools: Sequence[ToolBase] | None = None,
    *,
    model: ChatModelBase | None = None,
    max_iters: int = 20,
    offloader: Offloader | None = None,
    middlewares: Sequence[Any] | None = None,
) -> Agent:
    """Build an agent that runs without interactive confirmations.

    Every example runs head-less, so the permission context is put in
    ``BYPASS`` mode: tool calls are executed instead of parking on a
    confirmation request.

    Args:
        name (`str`):
            The agent name, which is also how other agents refer to it.
        system_prompt (`str`):
            What the agent is for.
        tools (`Sequence[ToolBase] | None`, optional):
            The tools registered in the agent's toolkit.
        model (`ChatModelBase | None`, optional):
            The chat model. Built by :func:`make_model` when omitted.
        max_iters (`int`, optional):
            The cap on reasoning-acting iterations in one reply.
        offloader (`Offloader | None`, optional):
            Where to offload compressed context and long tool results,
            e.g. the shared `LocalWorkspace`.
        middlewares (`Sequence[Any] | None`, optional):
            The middlewares applied to the agent, e.g. a
            `ModelRouterMiddleware`. They must be given at construction,
            since the agent binds its hooks once.

    Returns:
        `Agent`:
            The agent, ready to reply.
    """
    return Agent(
        name=name,
        system_prompt=system_prompt,
        model=model or make_model(),
        toolkit=Toolkit(tools=list(tools or [])),
        offloader=offloader,
        middlewares=list(middlewares or []),
        state=AgentState(
            permission_context=PermissionContext(
                mode=PermissionMode.BYPASS,
            ),
        ),
        react_config=ReActConfig(max_iters=max_iters),
    )


async def render_stream(
    stream: AsyncGenerator[Any, None],
    verbosity: str = "default",
) -> Msg | None:
    """Render every event of a reply stream and return the final message.

    Works for a single ``Agent`` as well as for the pipelines
    (``TeamPipeline`` / ``GoalPipeline`` / ``SOPEngine``), because they
    all stream the same events.

    Args:
        stream (`AsyncGenerator`):
            The stream to consume, e.g. ``agent.reply_stream(msg)``.
        verbosity (`str`, optional):
            ``"quiet"``, ``"default"`` or ``"debug"``.

    Returns:
        `Msg | None`:
            The last message accumulated by the renderer, if any.
    """
    renderer = ConsoleRenderer(verbosity=verbosity)
    async for event in stream:
        if isinstance(event, Msg):
            # The final message carries no event to render
            continue
        renderer.render(event)
    return renderer.last_msg


def get_text(msg: Msg | None) -> str:
    """Collect the text of a message, tolerating a missing one.

    Args:
        msg (`Msg | None`):
            The message to read.

    Returns:
        `str`:
            The concatenated text blocks, or `""`.
    """
    if msg is None:
        return ""
    return msg.get_text_content()
