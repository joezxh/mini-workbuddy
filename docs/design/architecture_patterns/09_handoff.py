# -*- coding: utf-8 -*-
"""Pattern 9 — Handoff (hand the conversation to a specialist).

AgentScope has no built-in handoff primitive, and it does not need one:
a handoff is *an external tool plus a small driver loop*.

- ``transfer_to`` is declared with ``is_external_tool = True``, so the
  framework never executes it. The agent parks and emits a
  ``RequireExternalExecutionEvent`` instead — that is the signal to switch.
- The driver reads the chosen expert and the summary the agent wrote,
  closes the parked reply with a ``UserInterruptEvent`` (clean, and it
  costs no model call), and starts the next expert with the summary as its
  first message.

The state that crosses the handoff is deliberately small: **the summary,
not the transcript**. The expert starts a fresh, cheap context.

Compare with ``08_orchestrator_workers.py``: there the leader keeps
control and the members are stateless sub-calls; here control is *given
away* — the previous agent is out of the loop for good.

Use it for: support escalation, "this is out of my area, let me get you
to the right person".
"""
import asyncio
import json
from typing import Any

from agentscope.console import ConsoleRenderer
from agentscope.event import RequireExternalExecutionEvent, UserInterruptEvent
from agentscope.message import Msg, UserMsg
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)
from agentscope.tool import ToolBase

from _common import make_agent

MAX_HOPS = 4


class TransferTo(ToolBase):
    """Hand the conversation over to another expert."""

    name: str = "transfer_to"
    is_external_tool: bool = True
    is_concurrency_safe: bool = False
    is_read_only: bool = False
    input_schema: dict[str, Any] = {}

    def __init__(self, experts: dict[str, Any]) -> None:
        """Describe the experts to the model, in the tool itself.

        Args:
            experts (`dict[str, Any]`):
                The agents that can be handed over to, by name.
        """
        super().__init__()
        self.description = (
            "Hand the conversation over to a specialist. Use it as soon as "
            "the request is outside your area — do not try to answer it "
            "yourself. The specialists are:\n"
            + "\n".join(f"- {name}" for name in experts)
        )
        self.input_schema = {
            "type": "object",
            "properties": {
                "expert": {
                    "type": "string",
                    "enum": list(experts),
                    "description": "The specialist to hand over to.",
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "What the user wants and everything you learned so "
                        "far. The specialist sees ONLY this, so make it "
                        "self-contained."
                    ),
                },
            },
            "required": ["expert", "summary"],
        }

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """A handoff is always allowed."""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Handing over to another expert is always allowed.",
        )


def make_experts() -> dict[str, Any]:
    """Build the specialists and give each the handoff tool."""
    experts = {
        "Triage": make_agent(
            name="Triage",
            system_prompt=(
                "You're the front desk. If the request is about a bug or an "
                "integration problem, hand it over with transfer_to instead "
                "of answering. Only answer yourself for simple greetings."
            ),
            max_iters=6,
        ),
        "TechSupport": make_agent(
            name="TechSupport",
            system_prompt=(
                "You're a technical support engineer. Solve the problem "
                "concretely. If it turns out to be a billing question, hand "
                "it over with transfer_to."
            ),
            max_iters=6,
        ),
        "Billing": make_agent(
            name="Billing",
            system_prompt=(
                "You're a billing specialist. Answer about refunds, invoices "
                "and prices only."
            ),
            max_iters=6,
        ),
    }
    return experts


async def register(experts: dict[str, Any]) -> None:
    """Give every expert its own instance of the handoff tool."""
    for agent in experts.values():
        await agent.toolkit.add_tool(TransferTo(experts))


async def run_handoff(
    experts: dict[str, Any],
    entry: str,
    user_msg: Msg,
    max_hops: int = MAX_HOPS,
) -> str:
    """Drive the conversation until nobody hands it over any more.

    Args:
        experts (`dict[str, Any]`):
            The specialists, by name.
        entry (`str`):
            The name of the agent that receives the user first.
        user_msg (`Msg`):
            The user's request.
        max_hops (`int`, optional):
            The cap on handovers, so a loop cannot run forever.

    Returns:
        `str`:
            The answer of whichever agent ended the conversation.
    """
    renderer = ConsoleRenderer(verbosity="default")
    current = experts[entry]
    inputs: Msg = user_msg

    for hop in range(max_hops):
        print(f"\n===== HOP {hop}: {current.name} =====")
        renderer.reset()
        handover = None

        async for event in current.reply_stream(inputs):
            if isinstance(event, Msg):
                continue
            if isinstance(event, RequireExternalExecutionEvent):
                handover = next(
                    (
                        _
                        for _ in event.tool_calls
                        if _.name == TransferTo.name
                    ),
                    None,
                )
                if handover is not None:
                    # The agent parked on the handoff; stop consuming
                    break
            renderer.render(event)

        if handover is None:
            return renderer.last_msg.get_text_content() if renderer.last_msg else ""

        try:
            parsed = json.loads(handover.input or "{}")
        except json.JSONDecodeError:
            parsed = {}
        target = parsed.get("expert")
        summary = parsed.get("summary", "")
        print(f"\n>>> {current.name} --hands over to--> {target}")
        print(f"    summary: {summary}")

        if target not in experts:
            return f"Unknown expert {target!r}"

        # Close the parked reply cleanly: it costs no model call
        async for _ in current.reply_stream(
            UserInterruptEvent(reply_id=current.state.reply_id),
        ):
            pass

        # The specialist starts fresh; the summary is its only context
        sender = current.name
        current = experts[target]
        inputs = UserMsg(
            name="handoff",
            content=(
                f"<handover from=\"{sender}\">\n{summary}\n"
                "</handover>\n"
                "Answer the user's request now."
            ),
        )

    return "Handoff budget exhausted."


async def main() -> None:
    """Hand a technical request from the front desk to an engineer."""
    experts = make_experts()
    await register(experts)

    answer = await run_handoff(
        experts=experts,
        entry="Triage",
        user_msg=UserMsg(
            name="user",
            content=(
                "我们的 TeamPipeline 里，leader 派活给成员之后一直卡住不动，"
                "日志里也没有报错，这是什么原因？"
            ),
        ),
    )
    print("\n===== ANSWER TO THE USER =====")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())
