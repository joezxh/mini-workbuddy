# -*- coding: utf-8 -*-
"""跨语种客服交接（交接式，外部工具 + 自建驱动循环）。

模式语义：请求不在当前专家职责范围时，把会话**交出去**——前专家出局，
新专家只拿到 `<handover>交接摘要</handover>`（看不到前专家的全量对话）。
框架无内置 handoff：transfer_to 声明 is_external_tool=True，Agent 挂起并发
RequireExternalExecutionEvent；驱动循环用 UserInterruptEvent 干净关闭挂起
（不消耗模型调用），再切专家。max_hops=3 硬上限防 A→B→A 死循环。

对应团队：xborder-handoff-support（mode=sequential，交接语义由本实现保证）。
离线运行：python scripts/run_org_pattern.py support_handoff --mock
"""
from __future__ import annotations

import json
from typing import Any, Optional

from agentscope.console import ConsoleRenderer
from agentscope.event import RequireExternalExecutionEvent, UserInterruptEvent
from agentscope.message import Msg, UserMsg
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ToolBase

from app.ai.team.trade.scaffolding import Trace, make_agent, make_model

MAX_HOPS = 3

# 客户原文埋标记串：若泄漏进交接摘要，测试会抓住
CUSTOMER_MSG = (
    "【西语客户完整对话】Hola, mi pedido ORD-2026-1120 lleva 10 días sin "
    "actualización de envío. Primero pregunté por la preventa del lote nuevo, "
    "pero ahora quiero saber dónde está mi paquete o pedir un reembolso. "
    "（历史闲聊与完整订单上下文略，共 3000 字）"
)


class TransferTo(ToolBase):
    """外部工具：框架不执行，只发 RequireExternalExecutionEvent 由驱动循环接管。"""

    name: str = "transfer_to"
    description: str = (
        "把会话交接给另一位专家。只传你写的交接摘要（含订单号等关键要素），"
        "不要复制客户全量对话。"
    )
    is_external_tool: bool = True
    is_concurrency_safe: bool = False
    is_read_only: bool = False

    def __init__(self, experts: list[str]):
        super().__init__()
        self.input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "expert": {"type": "string", "enum": list(experts)},
                "summary": {"type": "string"},
            },
            "required": ["expert", "summary"],
        }

    async def check_permissions(self, tool_input, context):
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Handover is always allowed.",
        )


async def run(mock: bool, model_id: Optional[int] = None) -> dict:
    """运行跨语种客服交接团队，返回 {"final": str, "trace": Trace}。"""
    trace = Trace()

    presale_script = logistics_script = returns_script = None
    if mock:
        # xborder-presale-es：西语售前 → 发现是物流查件诉求，交接（摘要含订单号，不含全量对话）
        presale_script = [{"tool_calls": [{"name": "transfer_to", "input": {
            "expert": "xborder-logistics-en",
            "summary": "西语客户咨询订单 ORD-2026-1120：包裹 10 天无物流更新，"
                       "诉求从新品预售转为查件/退款，需英文物流专员对接承运商。",
        }}]}]
        # xborder-logistics-en：英文物流 → 查件确认丢件，客户要退款，交接给中文退货专员
        logistics_script = [{"tool_calls": [{"name": "transfer_to", "input": {
            "expert": "xborder-returns-zh",
            "summary": "Order ORD-2026-1120 confirmed lost in transit by carrier. "
                       "Customer requests full refund; hand over to Chinese-speaking "
                       "returns specialist to process refund and retention.",
        }}]}]
        # xborder-returns-zh：中文退货专员直接终答
        returns_script = [
            "已为订单 ORD-2026-1120 发起全额退款，预计 3-5 个工作日原路到账；"
            "另附 9 折优惠券挽留客户，退款进度将在 App 内推送。",
        ]

    expert_specs = {
        "xborder-presale-es": ("你是西语售前客服，负责新品咨询；物流/退款诉求请 transfer_to 交接。", presale_script),
        "xborder-logistics-en": ("你是英文物流专员，负责查件与承运商对接；退款诉求请 transfer_to 交接。", logistics_script),
        "xborder-returns-zh": ("你是中文退货退款专员，负责退款流程与客户挽留，直接给出终答。", returns_script),
    }
    experts = {
        name: make_agent(
            name, prompt,
            tools=[TransferTo([n for n in expert_specs if n != name])],
            max_iters=6, model=make_model(script, name=name, model_id=model_id),
        )
        for name, (prompt, script) in expert_specs.items()
    }

    renderer = ConsoleRenderer()
    current = experts["xborder-presale-es"]
    inputs = UserMsg(name="customer", content=CUSTOMER_MSG)
    final = ""
    for _hop in range(MAX_HOPS + 1):
        handover = None
        async for event in current.reply_stream(inputs):
            if isinstance(event, RequireExternalExecutionEvent):
                handover = next(c for c in event.tool_calls if c.name == "transfer_to")
                break  # Agent 已挂起，停止消费
            if isinstance(event, Msg):
                final = event.get_text_content() or ""
            else:
                renderer.render(event)
        if handover is None:
            if not final:
                final = renderer.last_msg.get_text_content() if renderer.last_msg else ""
            break
        parsed = json.loads(handover.input)
        # 干净关闭挂起的回复（不进入推理循环，不消耗模型调用）
        async for _ in current.reply_stream(
            UserInterruptEvent(reply_id=current.state.reply_id),
        ):
            pass
        trace.record("handoff", **{"from": current.name},
                     to=parsed["expert"], summary=parsed["summary"])
        current = experts[parsed["expert"]]  # 控制权真的交出去了
        inputs = UserMsg(name="handoff", content=f'<handover>{parsed["summary"]}</handover>')
        trace.record("expert_first_msg", expert=current.name, content=inputs.get_text_content())
    else:
        raise RuntimeError(f"交接跳数超过硬上限 max_hops={MAX_HOPS}，疑似 A→B→A 死循环")

    trace.record("final", text=final)
    return {"final": final, "trace": trace}


PATTERN = {
    "team_code": "xborder-handoff-support",
    "name": "跨语种客服交接",
    "mode": "sequential",
    "sample_input": "Hola, mi pedido ORD-2026-1120 lleva 10 días sin actualización de envío, quiero un reembolso.",
    "run": run,
}