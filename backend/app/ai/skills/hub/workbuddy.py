"""workbuddy 平台 Skill Hub 适配器（占位实现）。

来源尚未最终确定，此处仅提供接口骨架与 TODO：
- 明确 workbuddy hub 的 API 地址 / 鉴权方式后填充 list_remote / fetch
- fetch 应返回与 import_zip 兼容的 zip 字节流（含 SKILL.json）
"""
from __future__ import annotations

from app.ai.skills.hub.base import SkillHubAdapter, SkillHubEntry
from app.ai.skills.hub.registry import register_adapter


@register_adapter
class WorkbuddyHubAdapter(SkillHubAdapter):
    name = "workbuddy"

    def __init__(self, base_url: str = "", token: str = "") -> None:
        self.base_url = base_url
        self.token = token

    def list_remote(self) -> list[SkillHubEntry]:
        # TODO: 调用 workbuddy hub 列表接口，映射为 SkillHubEntry
        raise NotImplementedError("workbuddy hub 来源未确定，list_remote 待实现")

    def fetch(self, entry: SkillHubEntry) -> bytes:
        # TODO: 根据 entry.id 拉取 zip 包字节流
        raise NotImplementedError("workbuddy hub 来源未确定，fetch 待实现")
