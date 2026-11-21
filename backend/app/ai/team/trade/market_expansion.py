# -*- coding: utf-8 -*-
"""海外市场拓展（层级式，薄编排层 + 子 TeamPipeline）。

模式语义：总监只面对渠道 Leader（assign_team 外部工具），Leader 再派 Worker
（子 TeamPipeline 原生 TeamAssign），每层自己的词汇；总监不得直派 Worker。
子团队结果经 ExternalExecutionResultEvent 回填，总监保留控制权并亲自写交付物。
每层独立上限（总监 6 / Leader 8 / Worker 6）+ 每队 asyncio.wait_for 超时，
单队超时总监收到错误结果仍可继续。

对应团队：xborder-hierarchy-expansion（mode=supervisor，表结构无层级字段，层级由本实现保证）。
离线运行：python scripts/run_org_pattern.py market_expansion --mock
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from agentscope.console import ConsoleRenderer
from agentscope.event import (
    ExternalExecutionResultEvent,
    RequireExternalExecutionEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from agentscope.message import Msg, TextBlock, ToolResultBlock, ToolResultState, UserMsg
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.pipeline import TeamMember, TeamPipeline
from agentscope.tool import ToolBase

from app.ai.team.trade.scaffolding import Trace, make_agent, make_model

SAMPLE_INPUT = "为便携咖啡机制定东南亚与欧洲市场渠道拓展方案"
TEAM_TIMEOUT = 60


class AssignTeam(ToolBase):
    """外部工具：总监把团队级任务派给子团队，框架只发事件由编排层执行。"""

    name: str = "assign_team"
    description: str = "把任务派给一个渠道子团队（只能派团队，不能直派 Worker），任务描述要自包含。"
    is_external_tool: bool = True
    is_concurrency_safe: bool = False
    is_read_only: bool = False

    def __init__(self, teams: list[str]):
        super().__init__()
        self.input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "team": {"type": "string", "enum": list(teams)},
                "task": {"type": "string"},
            },
            "required": ["team", "task"],
        }

    async def check_permissions(self, tool_input, context):
        return PermissionDecision(behavior=PermissionBehavior.ALLOW,
                                  message="Team assignment is always allowed.")


def _build_subteam(leader_name: str, leader_prompt: str, leader_script: Optional[list],
                   workers: list[tuple[str, str, Optional[list]]],
                   model_id: Optional[int] = None) -> TeamPipeline:
    """workers: (name, description, mock_script)；leader max_iters=8 / worker 6。"""
    leader = make_agent(leader_name, leader_prompt, max_iters=8,
                        model=make_model(leader_script, name=leader_name, model_id=model_id))
    members = [
        TeamMember(
            agent=make_agent(name, f"你是 {name}，完成 Leader 指派的任务并返回简短结论。",
                             max_iters=6, model=make_model(script, name=name, model_id=model_id)),
            description=desc,
        )
        for name, desc, script in workers
    ]
    return TeamPipeline(leader=leader, members=members)


async def run(mock: bool, model_id: Optional[int] = None,
              timeout_team: Optional[str] = None) -> dict:
    """运行海外市场拓展团队，返回 {"final": str, "trace": Trace}。

    Args:
        mock: True 走离线 FakeChatModel；False 走真实模型（model_id 或环境变量兜底）。
        model_id: DB 模型配置 id（factory_ext 构建）。
        timeout_team: 失败注入开关——指定子团队名（如 xborder-eu-team）模拟超时。
    """
    trace = Trace()

    if mock:
        sea_leader_script = [
            {"tool_calls": [
                {"name": "TeamAssign", "input": {"member": "xborder-sea-researcher",
                                                 "prompt": "调研东南亚便携咖啡机市场格局与优先国家，返回调研结论。"}},
                {"name": "TeamAssign", "input": {"member": "xborder-sea-writer",
                                                 "prompt": "基于东南亚市场特点产出本地化卖点文案方向。"}},
            ]},
            "东南亚团队结论：优先印尼/泰国，Shopee+TikTok Shop 双渠道，本地化文案已就绪。",
        ]
        eu_leader_script = [
            {"tool_calls": [
                {"name": "TeamAssign", "input": {"member": "xborder-eu-researcher",
                                                 "prompt": "调研欧洲便携咖啡机合规要求与渠道进入策略，返回调研结论。"}},
            ]},
            "欧洲团队结论：CE/GDPR 合规路径明确，优先德法，Amazon 欧洲站+独立站。",
        ]
        sea_workers = [
            ("xborder-sea-researcher", "东南亚市场调研：平台格局/消费偏好/准入要点。",
             ["东南亚调研：Shopee/Lazada/TikTok Shop 三强，印尼泰国优先，价格敏感。"]),
            ("xborder-sea-writer", "东南亚本地化文案：本地语言卖点与渠道话术。",
             ["东南亚文案：泰语/印尼语本地化卖点，主打性价比与货到付款。"]),
        ]
        eu_workers = [
            ("xborder-eu-researcher", "欧洲市场调研：合规要求与渠道进入策略。",
             ["欧洲调研：需 CE 认证与 GDPR 合规，德法优先，Amazon 欧洲站+独立站。"]),
        ]
        director_final = (
            "市场拓展方案：东南亚——Shopee+TikTok Shop 双渠道，印尼/泰国优先，本地化文案就绪；"
            "欧洲——CE/GDPR 合规路径明确，德法优先，Amazon 欧洲站+独立站。两区预算 60/40 分配。"
        )
        if timeout_team:
            director_final = (
                "市场拓展方案：东南亚团队正常交付（Shopee+TikTok Shop 双渠道，印尼/泰国优先）；"
                f"{timeout_team} 执行超时失败，欧洲结论缺失，建议补跑欧洲子团队后再补全方案，"
                "先行启动东南亚。"
            )
        director_script = [
            {"tool_calls": [
                {"name": "assign_team", "input": {"team": "xborder-sea-team",
                                                  "task": "调研东南亚市场格局并产出本地化渠道进入策略（团队级任务，自行拆分）。"}},
                {"name": "assign_team", "input": {"team": "xborder-eu-team",
                                                  "task": "调研欧洲合规要求并产出渠道进入策略（团队级任务，自行拆分）。"}},
            ]},
            director_final,
        ]
    else:
        sea_leader_script = eu_leader_script = director_script = None
        sea_workers = [("xborder-sea-researcher", "东南亚市场调研：平台格局/消费偏好/准入要点。", None),
                       ("xborder-sea-writer", "东南亚本地化文案：本地语言卖点与渠道话术。", None)]
        eu_workers = [("xborder-eu-researcher", "欧洲市场调研：合规要求与渠道进入策略。", None)]

    pipes = {
        "xborder-sea-team": _build_subteam(
            "xborder-sea-leader",
            "你是东南亚渠道负责人，把总监任务拆给 xborder-sea-researcher/xborder-sea-writer 并汇总上报。",
            sea_leader_script, sea_workers, model_id=model_id),
        "xborder-eu-team": _build_subteam(
            "xborder-eu-leader",
            "你是欧洲渠道负责人，把总监任务拆给 xborder-eu-researcher 并汇总上报。",
            eu_leader_script, eu_workers, model_id=model_id),
    }
    director = make_agent(
        "xborder-region-director",
        "你是海外市场拓展总监，只用 assign_team 把团队级任务派给 xborder-sea-team/xborder-eu-team 两个渠道团队，"
        "不得直派 Worker；收齐两队结论后亲自输出市场拓展方案。",
        tools=[AssignTeam(list(pipes))], max_iters=6,
        model=make_model(director_script, name="xborder-region-director", model_id=model_id),
    )

    renderer = ConsoleRenderer()

    async def run_team(team: str, task: str) -> str:
        """跑一个子 TeamPipeline，worker_call trace 只记 leader 层派活。"""
        if team == timeout_team:
            raise asyncio.TimeoutError(f"子团队 {team} 执行超时（失败注入）")
        pipe = pipes[team]
        leader_name = pipe.leader.name
        local_renderer = ConsoleRenderer()  # 每队独立 renderer，避免并发共享 last_msg 竞态
        calls: dict = {}
        async for evt in pipe.reply_stream(UserMsg(name="director", content=task)):
            if isinstance(evt, ToolCallStartEvent):
                calls[evt.tool_call_id] = {"name": evt.tool_call_name, "buf": ""}
            elif isinstance(evt, ToolCallDeltaEvent):
                calls[evt.tool_call_id]["buf"] += evt.delta
            elif isinstance(evt, ToolCallEndEvent):
                info = calls.pop(evt.tool_call_id, None)
                if info and info["name"] == "TeamAssign":
                    worker = json.loads(info["buf"]).get("member", "?")
                    trace.record("worker_call", leader=leader_name, worker=worker)
            if not isinstance(evt, Msg):
                local_renderer.render(evt)
        last = local_renderer.last_msg
        return last.get_text_content() if last else ""

    async def guarded_team(call: dict, call_id: str) -> ToolResultBlock:
        team = call["team"]
        try:
            text = await asyncio.wait_for(run_team(team, call["task"]), TEAM_TIMEOUT)
            trace.record("team_done", team=team)
            return ToolResultBlock(type="tool_result", id=call_id, name="assign_team",
                                   output=[TextBlock(type="text", text=text)],
                                   state=ToolResultState.SUCCESS)
        except Exception as e:  # noqa: BLE001 —— 单队失败回填错误结果，总监继续
            trace.record("team_failed", team=team, error=str(e))
            return ToolResultBlock(type="tool_result", id=call_id, name="assign_team",
                                   output=[TextBlock(type="text", text=f"团队 {team} 执行失败：{e}")],
                                   state=ToolResultState.ERROR)

    # 总监驱动循环：消费至 RequireExternalExecutionEvent → 并发跑子团队 → 结果回填
    inputs: Any = UserMsg(name="user", content=SAMPLE_INPUT)
    final = ""
    for _round in range(6):  # 安全上限（总监 max_iters=6 之内）
        pending = None
        async for evt in director.reply_stream(inputs):
            if isinstance(evt, RequireExternalExecutionEvent):
                pending = evt
                break  # 总监挂起，等待外部执行结果
            if isinstance(evt, Msg):
                final = evt.get_text_content() or ""
            else:
                renderer.render(evt)
        if pending is None:
            break
        assignments = []
        for c in pending.tool_calls:
            if c.name != "assign_team":
                continue
            parsed = json.loads(c.input)
            trace.record("assign_team", team=parsed["team"], task=parsed["task"])
            assignments.append((parsed, c.id))
        results = await asyncio.gather(*[guarded_team(p, cid) for p, cid in assignments])
        inputs = ExternalExecutionResultEvent(
            reply_id=director.state.reply_id, execution_results=results)
    else:
        raise RuntimeError("层级编排超过安全轮次上限，疑似死循环")

    if not final and renderer.last_msg:
        final = renderer.last_msg.get_text_content() or ""
    trace.record("final", text=final)
    return {"final": final, "trace": trace}


PATTERN = {
    "team_code": "xborder-hierarchy-expansion",
    "name": "海外市场拓展",
    "mode": "supervisor",
    "sample_input": SAMPLE_INPUT,
    "run": run,
}