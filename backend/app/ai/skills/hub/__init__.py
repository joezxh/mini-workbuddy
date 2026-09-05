"""第三方 Skill Hub 可插拔适配层。

不同来源（workbuddy 平台、AgentScope 标准、未来未知 hub）通过实现
SkillHubAdapter 抽象接口接入，统一由 import_zip 消费其返回的 zip 字节流。
"""

from app.ai.skills.hub.base import SkillHubAdapter, SkillHubEntry
from app.ai.skills.hub.registry import get_adapter, register_adapter
from app.ai.skills.hub.workbuddy import WorkbuddyHubAdapter
from app.ai.skills.hub.agentscope import AgentScopeHubAdapter

__all__ = [
    "SkillHubAdapter",
    "SkillHubEntry",
    "get_adapter",
    "register_adapter",
    "WorkbuddyHubAdapter",
    "AgentScopeHubAdapter",
]
