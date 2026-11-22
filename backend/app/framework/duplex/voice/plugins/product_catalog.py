"""商品知识库助手 Agent。

职责：检索商品详情、规格、价格、库存，基于检索结果给出准确回答。
查询完毕后主动切回电商销售顾问。
"""
from __future__ import annotations

from .base import AgentContext, PluginDecision, VoiceAgentPlugin


class ProductCatalogAgentPlugin(VoiceAgentPlugin):
    """商品知识库助手。"""

    key = "product_catalog"
    display_name = "商品知识库助手"

    @property
    def system_prompt(self) -> str:
        return (
            "你是电商商品知识库助手。当客户咨询商品详情、规格、价格、库存、"
            "参数对比时，优先调用 product_search 工具检索商品库，"
            "并基于检索结果给出准确回答。可主动推荐关联商品提升客单价。"
            "查询完毕后切回电商销售顾问跟进成交。"
        )

    @property
    def tools(self) -> list[dict]:
        return [{
            "type": "function",
            "function": {
                "name": "product_search",
                "description": "检索商品库，返回商品详情、价格、库存、规格",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "商品关键词"},
                        "category": {"type": "string", "description": "商品分类"},
                        "top_k": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
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
            yield_reason="product_info_done",
        )
