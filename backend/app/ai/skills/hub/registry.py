"""Skill Hub 适配器注册表（简单内存注册 + 按 name 获取）。"""
from __future__ import annotations

from typing import Dict, Type

from app.ai.skills.hub.base import SkillHubAdapter

_REGISTRY: Dict[str, Type[SkillHubAdapter]] = {}


def register_adapter(cls: Type[SkillHubAdapter]) -> Type[SkillHubAdapter]:
    """注册一个 adapter 类（装饰器或普通调用均可）。"""
    _REGISTRY[cls.name] = cls
    return cls


def get_adapter(name: str, **kwargs) -> SkillHubAdapter:
    """按 name 实例化对应 adapter；未知来源抛出 KeyError。"""
    if name not in _REGISTRY:
        raise KeyError(f"未注册的 Skill Hub 适配器: {name}")
    return _REGISTRY[name](**kwargs)


def available_adapters() -> list[str]:
    return list(_REGISTRY.keys())
