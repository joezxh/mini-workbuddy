"""销售纠纷解决助手 Agent（AI 自动投诉处理）。

职责：当客户发起投诉时，AI 自动处理：
1. 共情安抚客户情绪
2. 调用 dispute_classify 判断纠纷类型
3. 根据纠纷类型给出解决方案
4. 调用 compensation_apply 自动申请补偿
5. 超出 AI 权限时升级人工客服
处理完毕后切回电商销售顾问。
"""
from __future__ import annotations

from .base import AgentContext, PluginDecision, VoiceAgentPlugin


class DisputeResolutionAgentPlugin(VoiceAgentPlugin):
    """销售纠纷解决助手。"""

    key = "dispute_resolution"
    display_name = "销售纠纷解决助手"

    @property
    def system_prompt(self) -> str:
        return (
            "你是销售纠纷解决专家。当客户发起投诉时，AI 自动处理："
            "1) 先共情安抚客户情绪；"
            "2) 调用 dispute_classify 工具判断纠纷类型"
            "（商品质量/物流延误/服务态度/退款纠纷/虚假宣传/其他）；"
            "3) 根据纠纷类型给出解决方案（退款/换货/补偿/优惠券/升级人工）；"
            "4) 调用 compensation_apply 工具自动申请补偿；"
            "5) 若纠纷超出 AI 处理权限（如大额赔偿、法律诉讼），"
            "主动升级到人工客服并生成工单。"
            "处理完毕后切回电商销售顾问。"
        )

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "dispute_classify",
                    "description": "AI 自动分类纠纷类型并给出建议处理方案",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "complaint_text": {"type": "string",
                                                "description": "客户投诉内容"},
                            "order_id": {"type": "string", "description": "订单号"},
                        },
                        "required": ["complaint_text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "refund_query",
                    "description": "查询订单退款政策与可退金额",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compensation_apply",
                    "description": "自动申请客户补偿（优惠券/积分/现金）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string"},
                            "compensation_type": {
                                "type": "string",
                                "enum": ["coupon", "points", "cash", "refund"],
                            },
                            "amount": {"type": "number"},
                            "reason": {"type": "string"},
                        },
                        "required": ["order_id", "compensation_type", "amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_human",
                    "description": "升级到人工客服并生成工单",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string"},
                            "dispute_type": {"type": "string"},
                            "summary": {"type": "string"},
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "urgent"],
                            },
                        },
                        "required": ["order_id", "dispute_type", "summary"],
                    },
                },
            },
        ]

    async def on_activate(self, ctx: AgentContext) -> None:
        pass

    async def on_deactivate(self, ctx: AgentContext) -> None:
        pass

    async def on_user_turn_start(self, ctx: AgentContext,
                                  partial_transcript: str) -> PluginDecision:
        return PluginDecision()

    async def on_user_turn_end(self, ctx: AgentContext,
                                final_transcript: str) -> PluginDecision:
        return PluginDecision()

    async def on_assistant_turn_end(self, ctx: AgentContext,
                                     assistant_text: str) -> PluginDecision:
        return PluginDecision(
            should_yield=True,
            next_agent_hint="ecommerce_sales",
            yield_reason="dispute_resolved",
        )
