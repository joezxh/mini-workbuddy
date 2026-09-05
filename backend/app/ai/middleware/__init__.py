"""AI Middleware Module - AgentScope 中间件扩展

包含：
- GraphitiMiddleware: Graphiti 图数据长期记忆
- ConfigTraceMiddleware: 配置追踪（Trace ↔ Config 双向关联）
- ConfigRegistry: 组件配置注册表
- SkillMetricsMiddleware: Skill 执行指标采集
- tools: 图查询工具（SearchGraphTool / GetRelationsTool）
"""
from app.ai.middleware.graphiti_memory import GraphitiMiddleware
from app.ai.middleware.config_trace import ConfigTraceMiddleware, extract_config_trace
from app.ai.middleware.config_registry import ConfigRegistry, get_config_registry
from app.ai.middleware.skill_metrics import SkillMetricsMiddleware

__all__ = [
    "GraphitiMiddleware",
    "ConfigTraceMiddleware",
    "extract_config_trace",
    "ConfigRegistry",
    "get_config_registry",
    "SkillMetricsMiddleware",
]
