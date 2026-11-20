# -*- coding: utf-8 -*-
"""范例08 联邦式 —— 跨组织供应链协同（白名单网关边界）。

模式语义：各组织 Agent 数据主权独立，只交换最小必要结果，跨边界走受控网关。
brand_coordinator 以 Supervisor 式派活给 3 域 Agent（TeamPipeline 原生）；
各域 Agent 只挂本域白名单网关工具（erp: 产能/交期；logistics: 报价/时效；
ads: 预算消耗），越界字段请求直接拒绝。框架管通信、工程管边界——
真实 MCP/A2A 变体为进阶可选，本期全 mock。

运行：python 08_federated_supplychain.py --mock
"""
from __future__ import annotations

from agentscope.console import ConsoleRenderer
from agentscope.message import Msg, TextBlock
from agentscope.pipeline import TeamMember, TeamPipeline
from agentscope.tool import FunctionTool

from _common import (
    Trace,
    ads_gateway,
    erp_gateway,
    logistics_gateway,
    make_agent,
    make_model,
    run_cli,
)

SAMPLE_INPUT = "圣诞季：确认工厂产能、锁物流舱位、联动广告预算"


async def run_demo(mock: bool, probe_boundary: bool = False) -> dict:
    trace = Trace()

    def wrapped_gateway(domain: str, fn):
        """网关薄包装：留痕 gateway_call / gateway_denied（边界由网关白名单强制）。"""
        def gateway(fields: list[str]) -> dict:
            """经白名单网关查询本域对外字段（越界字段将被拒绝）。

            Args:
                fields (list[str]): 请求字段列表，仅限本域白名单。
            """
            trace.record("gateway_call", domain=domain, fields=list(fields))
            res = fn(fields)
            if "error" in res:
                trace.record("gateway_denied", domain=domain, denied=res["denied"])
            return res
        gateway.__name__ = gateway.__qualname__ = f"{domain}_gateway"  # 工具名与域对齐
        return gateway

    if mock:
        erp_script = [
            {"tool_calls": [{"name": "erp_gateway", "input": {"fields": ["capacity", "lead_time"]}}]},
            "工厂域结论：月产能 5000 台，交期 14 天，可支撑圣诞备货。",
        ]
        logistics_script = [
            {"tool_calls": [{"name": "logistics_gateway", "input": {"fields": ["quote", "transit_time"]}}]},
            "物流域结论：报价 $3.2/kg，时效 9 天，建议 D-20 锁舱。",
        ]
        if probe_boundary:
            # 越界探测：向物流域索取工厂成本价 → 网关拒绝 → 改用白名单字段重试
            logistics_script = [
                {"tool_calls": [{"name": "logistics_gateway",
                                 "input": {"fields": ["quote", "transit_time", "cost_price"]}}]},
                {"tool_calls": [{"name": "logistics_gateway",
                                 "input": {"fields": ["quote", "transit_time"]}}]},
                "物流域结论：报价 $3.2/kg，时效 9 天（成本价越界被拒，仅交换白名单字段）。",
            ]
        ads_script = [
            {"tool_calls": [{"name": "ads_gateway", "input": {"fields": ["budget_spent"]}}]},
            "广告域结论：预算已消耗 $1200，剩余预算可向圣诞大促倾斜。",
        ]
        coordinator_script = [
            {"tool_calls": [
                {"name": "TeamAssign", "input": {"member": "factory_erp_agent",
                                                 "prompt": "经 erp_gateway 查询产能与交期，返回工厂域最小必要结论。"}},
                {"name": "TeamAssign", "input": {"member": "logistics_agent",
                                                 "prompt": "经 logistics_gateway 查询报价与时效，返回物流域最小必要结论。"}},
                {"name": "TeamAssign", "input": {"member": "ads_platform_agent",
                                                 "prompt": "经 ads_gateway 查询预算消耗，返回广告域最小必要结论。"}},
            ]},
            "大促联动方案：工厂月产能 5000 台/交期 14 天可支撑圣诞备货；物流 $3.2/kg、时效 9 天，"
            "D-20 锁舱；广告已耗 $1200，剩余预算向大促倾斜。三域仅交换白名单字段，数据主权各自保留。",
        ]
    else:
        erp_script = logistics_script = ads_script = coordinator_script = None

    domain_specs = [
        ("factory_erp_agent", "工厂 ERP 域代理：只暴露产能/交期，拒绝越界字段。",
         "你是工厂 ERP 域代理，数据主权独立，只用 erp_gateway 暴露产能与交期，结论只含白名单字段。",
         erp_gateway, erp_script),
        ("logistics_agent", "物流域代理：只暴露报价/时效，拒绝越界字段。",
         "你是物流域代理，数据主权独立，只用 logistics_gateway 暴露报价与时效，结论只含白名单字段。",
         logistics_gateway, logistics_script),
        ("ads_platform_agent", "广告平台域代理：只暴露预算消耗，拒绝越界字段。",
         "你是广告平台域代理，数据主权独立，只用 ads_gateway 暴露预算消耗，结论只含白名单字段。",
         ads_gateway, ads_script),
    ]
    members = [
        TeamMember(
            agent=make_agent(name, prompt,
                             tools=[FunctionTool(wrapped_gateway(domain, fn))],
                             max_iters=6, model=make_model(script, name=name)),
            description=desc,
        )
        for (name, desc, prompt, fn, script), domain in zip(
            domain_specs, ["erp", "logistics", "ads"])
    ]
    coordinator = make_agent(
        "brand_coordinator",
        "你是品牌方供应链协调者，用 TeamAssign 派活给三个域代理，只接收白名单字段结论，"
        "不得索取域内私有数据（如成本价）；收齐后输出大促联动方案。",
        max_iters=10, model=make_model(coordinator_script, name="brand_coordinator"),
    )
    pipe = TeamPipeline(leader=coordinator, members=members)

    renderer = ConsoleRenderer()
    task = Msg(name="user", role="user", content=[TextBlock(type="text", text=SAMPLE_INPUT)])
    async for evt in pipe.reply_stream(task):
        if not isinstance(evt, Msg):
            renderer.render(evt)
    final = renderer.last_msg.get_text_content() if renderer.last_msg else ""
    trace.record("final", text=final)
    return {"final": final, "trace": trace}


if __name__ == "__main__":
    run_cli(run_demo)