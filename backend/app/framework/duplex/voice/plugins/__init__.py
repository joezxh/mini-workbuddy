"""可插拔语音 Agent 插件包。"""

from .base import (
    AgentContext,
    PluginDecision,
    VoiceAgentPlugin,
)
from .registry import PluginRegistry
from .ecommerce_sales import EcommerceSalesAgentPlugin
from .product_catalog import ProductCatalogAgentPlugin
from .cross_border import CrossBorderAgentPlugin
from .marketing import MarketingAgentPlugin
from .dispute_resolution import DisputeResolutionAgentPlugin

# 所有内置 Agent 插件的注册表，供 websocket_gateway 批量注册
BUILTIN_PLUGINS = [
    EcommerceSalesAgentPlugin,
    ProductCatalogAgentPlugin,
    CrossBorderAgentPlugin,
    MarketingAgentPlugin,
    DisputeResolutionAgentPlugin,
]

__all__ = [
    "AgentContext",
    "PluginDecision",
    "VoiceAgentPlugin",
    "PluginRegistry",
    "EcommerceSalesAgentPlugin",
    "ProductCatalogAgentPlugin",
    "CrossBorderAgentPlugin",
    "MarketingAgentPlugin",
    "DisputeResolutionAgentPlugin",
    "BUILTIN_PLUGINS",
]
