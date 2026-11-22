"""跨境贸易助手 Agent。

职责：为客户提供跨境物流方案、关税计算、清关流程、海外仓选择、
国际支付方式等专业咨询。咨询完毕后切回电商销售顾问。
"""
from __future__ import annotations

from .base import AgentContext, PluginDecision, VoiceAgentPlugin


class CrossBorderAgentPlugin(VoiceAgentPlugin):
    """跨境贸易助手。"""

    key = "cross_border"
    display_name = "跨境贸易助手"

    @property
    def system_prompt(self) -> str:
        return (
            "你是跨境贸易专家。为客户提供跨境物流方案、关税计算、清关流程、"
            "海外仓选择、国际支付方式等专业咨询。"
            "查询时调用 logistics_query 和 tariff_calc 工具获取实时数据。"
            "咨询完毕后切回电商销售顾问。"
        )

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "logistics_query",
                    "description": "查询跨境物流方案、运费、时效",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "destination": {"type": "string"},
                            "weight": {"type": "number"},
                            "product_category": {"type": "string"},
                        },
                        "required": ["destination", "weight"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tariff_calc",
                    "description": "计算目的国关税和税费",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "country": {"type": "string"},
                            "hs_code": {"type": "string"},
                            "declared_value": {"type": "number"},
                        },
                        "required": ["country", "hs_code"],
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
            yield_reason="cross_border_info_done",
        )
