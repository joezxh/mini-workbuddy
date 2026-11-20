# -*- coding: utf-8 -*-
"""范例01 Supervisor-Worker —— 跨境新品上架统筹（agentscope 2.0.12 原生 TeamPipeline）。

模式语义：Leader 始终掌权，运行时决定拆什么派给谁并汇总；成员独立上下文互不通信，
同轮指派并发；leader 只看到成员的最终回复（TeamAssign 工具结果）。

运行：python 01_supervisor_worker.py --mock   （离线）
      python 01_supervisor_worker.py          （需 OPENAI_BASE_URL/OPENAI_API_KEY 或 DASHSCOPE_API_KEY）
"""
from __future__ import annotations

import json

from agentscope.event import (
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultEndEvent,
)
from agentscope.message import Msg, TextBlock
from agentscope.pipeline import TeamMember, TeamPipeline
from agentscope.tool import FunctionTool

from _common import (
    Trace,
    make_agent,
    make_model,
    mock_compliance_check,
    mock_cost_table,
    mock_fx_rate,
    mock_market_scan,
    run_cli,
)

SAMPLE_INPUT = "评估『便携咖啡机』上架日本亚马逊，给出 GO/NO-GO 与售价"

LEADER_PROMPT = """你是跨境电商上架总监（listing_director），负责新品上架的 GO/NO-GO 决策。
通过 TeamAssign 工具把子任务派给最合适的成员（一次调用派一个成员，任务描述要自包含）：
- product_picker：选品分析（市场热度/竞争度）
- listing_writer：多语种 Listing 文案
- compliance_checker：目标市场合规检查
- pricing_analyst：成本与定价测算
收集全部成员结论后，输出最终决策：必须包含 GO 或 NO-GO，并给出建议售价与理由。"""

MEMBER_SPECS = [
    ("product_picker", "选品专家：用市场扫描数据评估品类热度与竞争度，返回选品结论。",
     "你是选品专家，用 mock_market_scan 工具评估品类，返回简短选品结论。", [mock_market_scan]),
    ("listing_writer", "Listing 文案专家：撰写目标市场语言的标题与卖点。",
     "你是多语种 Listing 文案专家，针对目标市场撰写标题与 3 条卖点。", []),
    ("compliance_checker", "合规专家：检查目标市场准入认证要求。",
     "你是合规专家，用 mock_compliance_check 工具检查产品准入，返回合规结论。", [mock_compliance_check]),
    ("pricing_analyst", "定价专家：核算成本并结合汇率给出建议售价。",
     "你是定价专家，用 mock_cost_table 与 mock_fx_rate 工具核算成本，给出建议售价。",
     [mock_cost_table, mock_fx_rate]),
]


def _mock_leader_script() -> list:
    """leader 首轮对 4 成员各发一个 TeamAssign，次轮输出含 GO 的汇总。"""
    assigns = [
        {"name": "TeamAssign", "input": {"member": name, "prompt": f"针对『便携咖啡机』上架日本亚马逊完成你的职责：{desc}"}}
        for name, desc, _, _ in MEMBER_SPECS
    ]
    return [
        {"tool_calls": assigns},
        "GO：便携咖啡机上架日本亚马逊。建议售价 4980 日元；市场热度高、合规已通过、定价毛利达标。",
    ]


def _mock_member_script(name: str) -> list:
    return {
        "product_picker": ["选品结论：便携咖啡机品类热度 82、竞争中位，值得进入。"],
        "listing_writer": ["标题：ポータブルコーヒーメーカー；卖点：軽量・USB充電・静音。"],
        "compliance_checker": ["合规结论：PSE 认证与 METI 备案均已通过。"],
        "pricing_analyst": ["定价结论：成本 57 元，按 USD/JPY=155 折算，建议售价 4980 日元。"],
    }[name]


async def run_demo(mock: bool) -> dict:
    trace = Trace()
    leader = make_agent(
        "listing_director", LEADER_PROMPT, max_iters=12,
        model=make_model(_mock_leader_script() if mock else None, name="listing_director"),
    )
    members = [
        TeamMember(
            agent=make_agent(
                name, prompt,
                tools=[FunctionTool(fn) for fn in tools],
                model=make_model(_mock_member_script(name) if mock else None, name=name),
            ),
            description=desc,
        )
        for name, desc, prompt, tools in MEMBER_SPECS
    ]
    pipe = TeamPipeline(leader=leader, members=members)

    # 监听 pipe 事件流记录派活/完成（TeamAssign 的 tool_call_id 贯穿调用与结果）
    from agentscope.console import ConsoleRenderer
    renderer = ConsoleRenderer()
    calls: dict = {}
    dispatch_by_call: dict = {}
    task = Msg(name="user", role="user", content=[TextBlock(type="text", text=SAMPLE_INPUT)])
    async for evt in pipe.reply_stream(task):
        if isinstance(evt, ToolCallStartEvent):
            calls[evt.tool_call_id] = {"name": evt.tool_call_name, "buf": ""}
        elif isinstance(evt, ToolCallDeltaEvent):
            calls[evt.tool_call_id]["buf"] += evt.delta
        elif isinstance(evt, ToolCallEndEvent):
            info = calls.pop(evt.tool_call_id, None)
            if info and info["name"] == "TeamAssign":
                member = json.loads(info["buf"]).get("member", "?")
                dispatch_by_call[evt.tool_call_id] = member
                trace.record("dispatch", member=member)
        elif isinstance(evt, ToolResultEndEvent):
            member = dispatch_by_call.pop(evt.tool_call_id, None)
            if member:
                trace.record("member_done", member=member)
        renderer.render(evt)

    final_msg = renderer.last_msg
    final = final_msg.get_text_content() if final_msg else ""
    trace.record("final", text=final)
    return {"final": final, "trace": trace}


if __name__ == "__main__":
    run_cli(run_demo)