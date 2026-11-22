"""市场推广助手 Agent。

职责：为客户介绍当前促销活动、优惠券、满减规则、会员等级权益、
积分兑换等营销信息，提升转化率和复购率。介绍完毕后切回电商销售顾问。
"""
from __future__ import annotations

from .base import AgentContext, PluginDecision, VoiceAgentPlugin


class MarketingAgentPlugin(VoiceAgentPlugin):
    """市场推广助手。"""

    key = "marketing"
    display_name = "市场推广助手"

    @property
    def system_prompt(self) -> str:
        return (
            "你是市场推广专家。为客户介绍当前促销活动、优惠券、满减规则、"
            "会员等级权益、积分兑换等营销信息，提升转化率和复购率。"
            "查询时调用 promotion_query 工具获取实时活动数据。"
            "可主动推荐更优惠的组合方案。介绍完毕后切回电商销售顾问。"
        )

    @property
    def tools(self) -> list[dict]:
        return [{
            "type": "function",
            "function": {
                "name": "promotion_query",
                "description": "查询当前促销活动、优惠券、会员权益",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "activity_type": {
                            "type": "string",
                            "enum": ["coupon", "discount", "member", "all"],
                        },
                    },
                },
            },
        }]

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
            yield_reason="promotion_info_done",
        )
