# -*- coding: utf-8 -*-
"""Pattern 10 — Hierarchical (a director, and under it several teams).

``TeamPipeline`` is deliberately flat: its members must be ``Agent``
instances, so a team cannot be a member of another team. The hierarchy
lives in a thin orchestration layer instead — about 60 lines here:

- the **director** gets one external tool, ``assign_team(team, task)``,
- each **sub-team** is a normal ``TeamPipeline`` with its own leader and
  workers, so each layer delegates in its own vocabulary,
- the director keeps control: sub-team results come back as tool results
  and it writes the final answer itself.

Why not just one big team? Because a leader with 12 members has to reason
over 12 descriptions on every turn. Two layers let each leader choose
between 2-4 options, and each layer's context stays small.

Use it for: complex projects where the work splits by domain first and by
task second.
"""
import asyncio
import json
import os
from typing import Any, AsyncGenerator

from agentscope.console import ConsoleRenderer
from agentscope.event import (
    ExternalExecutionResultEvent,
    RequireExternalExecutionEvent,
)
from agentscope.message import (
    Msg,
    ToolResultBlock,
    ToolResultState,
    UserMsg,
)
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)
from agentscope.pipeline import TeamMember, TeamPipeline
from agentscope.tool import ToolBase
from agentscope.workspace import LocalWorkspace

from _common import make_agent

WORKDIR = os.path.join(os.path.dirname(__file__), "workspace")
MAX_ROUNDS = 3


class AssignTeam(ToolBase):
    """Assign a piece of work to one of the sub-teams."""

    name: str = "assign_team"
    is_external_tool: bool = True
    is_concurrency_safe: bool = True
    is_read_only: bool = False
    input_schema: dict[str, Any] = {}

    def __init__(self, teams: dict[str, TeamPipeline]) -> None:
        """Describe the sub-teams to the director.

        Args:
            teams (`dict[str, TeamPipeline]`):
                The sub-teams, by name.
        """
        super().__init__()
        self.description = (
            "Assign a piece of work to one of the teams below and get its "
            "result back. The teams are:\n"
            + "\n".join(f"- {name}" for name in teams)
        )
        self.input_schema = {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "enum": list(teams),
                    "description": "The team to assign to.",
                },
                "task": {
                    "type": "string",
                    "description": (
                        "The complete brief for the team's leader. It cannot "
                        "see your conversation, so include everything."
                    ),
                },
            },
            "required": ["team", "task"],
        }

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Assigning work to a team is always allowed."""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Assigning work to a team is always allowed.",
        )


class HierarchicalTeam:
    """A director on top of several sub-teams."""

    def __init__(
        self,
        director: Any,
        teams: dict[str, TeamPipeline],
        max_rounds: int = MAX_ROUNDS,
    ) -> None:
        """Initialize the hierarchy.

        Args:
            director (`Agent`):
                The top-level agent that splits the request across teams.
            teams (`dict[str, TeamPipeline]`):
                The sub-teams, by the name the director uses.
            max_rounds (`int`, optional):
                The cap on delegation rounds.
        """
        self.director = director
        self.teams = teams
        self.max_rounds = max_rounds
        self._tool = AssignTeam(teams)
        self._registered = False

    async def reply_stream(
        self,
        inputs: Msg | list[Msg] | None = None,
    ) -> AsyncGenerator[Any, None]:
        """Run the director, executing its assignments on the sub-teams.

        Args:
            inputs (`Msg | list[Msg] | None`):
                What to start from.

        Yields:
            `AgentEvent`:
                The events of the director and of every sub-team it runs.
        """
        if not self._registered:
            await self.director.toolkit.add_tool(self._tool)
            self._registered = True

        renderer = ConsoleRenderer(verbosity="default")
        for _round in range(self.max_rounds):
            assignments: list[Any] = []
            async for event in self.director.reply_stream(inputs):
                if (
                    isinstance(event, RequireExternalExecutionEvent)
                    and all(_.name == self._tool.name for _ in event.tool_calls)
                ):
                    # Executed here, not by the caller
                    assignments.extend(event.tool_calls)
                    continue
                if isinstance(event, Msg):
                    continue
                renderer.render(event)
                yield event

            if not assignments:
                return

            results = await self._run_assignments(assignments)
            inputs = ExternalExecutionResultEvent(
                reply_id=self.director.state.reply_id,
                execution_results=results,
            )

    async def _run_assignments(
        self,
        tool_calls: list[Any],
    ) -> list[ToolResultBlock]:
        """Run every assignment concurrently, one sub-team per call."""

        async def run_one(tool_call: Any) -> ToolResultBlock:
            """Run one sub-team and turn its final reply into a result."""
            try:
                parsed = json.loads(tool_call.input or "{}")
            except json.JSONDecodeError:
                parsed = {}
            team = self.teams.get(parsed.get("team", ""))
            if team is None:
                return ToolResultBlock(
                    id=tool_call.id,
                    name=self._tool.name,
                    output=f"Unknown team {parsed.get('team')!r}.",
                    state=ToolResultState.ERROR,
                )
            print(f"\n>>> director --assigns to--> {parsed['team']}")
            # Each sub-team streams into its own renderer: several teams
            # running at once would otherwise interleave
            sub_renderer = ConsoleRenderer(verbosity="quiet")
            async for event in team.reply_stream(
                UserMsg(name="director", content=parsed.get("task", "")),
            ):
                if isinstance(event, Msg):
                    continue
                sub_renderer.render(event)
            text = (
                sub_renderer.last_msg.get_text_content()
                if sub_renderer.last_msg
                else "The team finished without a reply."
            )
            return ToolResultBlock(
                id=tool_call.id,
                name=self._tool.name,
                output=text,
                state=ToolResultState.SUCCESS,
            )

        return list(await asyncio.gather(*[run_one(_) for _ in tool_calls]))


async def main() -> None:
    """Two teams under one director, each with its own workers."""
    async with LocalWorkspace(workdir=WORKDIR) as workspace:
        tools = await workspace.list_tools()

        # ---- Layer 2: two teams, each with a leader and two workers ----
        research_team = TeamPipeline(
            leader=make_agent(
                name="ResearchLead",
                system_prompt=(
                    "You lead the research team. Delegate to your two "
                    "members, then merge their findings into one brief."
                ),
                max_iters=10,
            ),
            members=[
                TeamMember(
                    agent=make_agent(
                        name="DocReader",
                        system_prompt="Read the code/docs and report facts.",
                        tools=tools,
                        offloader=workspace,
                        max_iters=10,
                    ),
                    description="读代码与文档，报告事实",
                ),
                TeamMember(
                    agent=make_agent(
                        name="Summarizer",
                        system_prompt="Condense material into a short brief.",
                        max_iters=8,
                    ),
                    description="把素材压缩成简短要点",
                ),
            ],
        )

        engineering_team = TeamPipeline(
            leader=make_agent(
                name="EngLead",
                system_prompt=(
                    "You lead the engineering team. Delegate to your two "
                    "members, then report the code and how to run it."
                ),
                max_iters=10,
            ),
            members=[
                TeamMember(
                    agent=make_agent(
                        name="Coder",
                        system_prompt="Write runnable Python code.",
                        tools=tools,
                        offloader=workspace,
                        max_iters=15,
                    ),
                    description="写可运行的 Python 代码",
                ),
                TeamMember(
                    agent=make_agent(
                        name="Tester",
                        system_prompt="Run the code and report the output.",
                        tools=tools,
                        offloader=workspace,
                        max_iters=15,
                    ),
                    description="运行代码并报告结果",
                ),
            ],
        )

        # ---- Layer 1: the director ----
        director = make_agent(
            name="Director",
            system_prompt=(
                "You're the director of two teams: research and engineering. "
                "Split the request across them with assign_team, giving each "
                "team's leader a complete brief. When the results are back, "
                "write the final deliverable yourself."
            ),
            max_iters=10,
        )

        hierarchy = HierarchicalTeam(
            director=director,
            teams={
                "research": research_team,
                "engineering": engineering_team,
            },
        )

        async for _ in hierarchy.reply_stream(
            UserMsg(
                name="user",
                content=(
                    "交付一份《AgentScope TeamPipeline 实战指南》："
                    "research 团队负责核实 TeamPipeline 的三条关键语义"
                    "（派活方式、成员上下文隔离、并发与排队规则），"
                    "engineering 团队负责写一个最小可运行示例并跑通，"
                    "最后由你汇总成一份中文指南。"
                ),
            ),
        ):
            pass


if __name__ == "__main__":
    asyncio.run(main())
