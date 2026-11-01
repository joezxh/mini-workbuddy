# -*- coding: utf-8 -*-
"""Pattern 2 — Plan-and-Execute (plan first, then work the plan).

Two things do the work here:

- the built-in task tools ``TaskCreate`` / ``TaskUpdate`` / ``TaskList`` /
  ``TaskGet``, which hold the plan in the agent's own state, and
- runtime state injection (``InjectionConfig.inject_runtime_state``, on by
  default), which puts the current task list back into the context on every
  iteration, so the agent cannot forget what it promised to do.

The plan is therefore not a prompt you write: the agent writes it, keeps it
up to date, and is continuously reminded of it.

Use it for: multi-step long tasks where the steps are mostly known once the
task is understood.
"""
import asyncio
import os

from agentscope.message import UserMsg
from agentscope.tool import TaskCreate, TaskGet, TaskList, TaskUpdate
from agentscope.workspace import LocalWorkspace

from _common import make_agent, render_stream

WORKDIR = os.path.join(os.path.dirname(__file__), "workspace")


async def main() -> None:
    """Let an agent plan a three-file deliverable and execute the plan."""
    async with LocalWorkspace(workdir=WORKDIR) as workspace:
        agent = make_agent(
            name="Planner",
            system_prompt=(
                "You're a project manager who also writes the files.\n"
                "Before doing anything, break the request into tasks with "
                "TaskCreate. Then work one task at a time: mark it "
                "in_progress with TaskUpdate, finish it, mark it completed, "
                "and move to the next. Call TaskList whenever you need to "
                "re-read the plan."
            ),
            tools=[
                *await workspace.list_tools(),
                TaskCreate(),
                TaskUpdate(),
                TaskList(),
                TaskGet(),
            ],
            offloader=workspace,
            max_iters=30,
        )

        final = await render_stream(
            agent.reply_stream(
                UserMsg(
                    name="user",
                    content=(
                        "在 workspace 目录下交付一份《AgentScope 上手清单》，"
                        "包含三个文件：outline.md（大纲）、draft.md（正文草稿）、"
                        "checklist.md（上线前检查项）。先列计划再逐个完成。"
                    ),
                ),
            ),
        )
        print("\n===== FINAL REPORT =====")
        print(final.get_text_content() if final else "(no reply)")
        print("\n===== PLANNED TASKS =====")
        for task in agent.state.tasks_context.tasks:
            print(f"- [{task.state}] {task.id} {task.subject}")


if __name__ == "__main__":
    asyncio.run(main())
