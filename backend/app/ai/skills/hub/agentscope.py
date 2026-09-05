"""AgentScope 标准 Skill Hub 适配器（占位实现）。

来源尚未最终确定，此处仅提供接口骨架与 TODO：
- 明确 AgentScope hub 的 registry 地址 / 协议后填充 list_remote / fetch
- fetch 应返回与 import_zip 兼容的 zip 字节流（含 SKILL.json）
"""
from __future__ import annotations

from app.ai.skills.hub.base import SkillHubAdapter, SkillHubEntry
from app.ai.skills.hub.registry import register_adapter


@register_adapter
class AgentScopeHubAdapter(SkillHubAdapter):
    name = "agentscope"

    def __init__(self, registry_url: str = "") -> None:
        self.registry_url = registry_url

    def list_remote(self) -> list[SkillHubEntry]:
        # TODO: 调用 AgentScope registry 接口，映射为 SkillHubEntry
        raise NotImplementedError("AgentScope hub 来源未确定，list_remote 待实现")

    def fetch(self, entry: SkillHubEntry) -> bytes:
        # TODO: 根据 entry.id 拉取 zip 包字节流
        raise NotImplementedError("AgentScope hub 来源未确定，fetch 待实现")
