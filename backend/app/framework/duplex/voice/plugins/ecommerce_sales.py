"""电商销售顾问 Agent（默认活跃）。

职责：热情接待客户，了解需求并推荐合适的商品。
根据客户问题主动让权给商品知识库/跨境贸易/市场推广/纠纷解决 Agent。
"""
from __future__ import annotations

from .base import AgentContext, PluginDecision, VoiceAgentPlugin


class EcommerceSalesAgentPlugin(VoiceAgentPlugin):
    """电商销售顾问，默认活跃 Agent。"""

    key = "ecommerce_sales"
    display_name = "电商销售顾问"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名专业的电商销售顾问。热情地接待客户，了解需求并推荐合适的商品。"
            "当客户询问商品详情、规格、价格、库存时，切换到商品知识库助手查询；"
            "当客户咨询跨境配送、关税、海外仓时，切换到跨境贸易助手；"
            "当客户询问优惠活动、优惠券、会员权益时，切换到市场推广助手；"
            "当客户发起投诉、退款、质量问题时，切换到销售纠纷解决助手。"
            "目标是促成交易，提升转化率和客单价。"
        )

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
        return PluginDecision()
