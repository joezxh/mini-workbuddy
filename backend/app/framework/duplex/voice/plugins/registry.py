"""运行时插件注册表。

支持动态注册/注销/热切换，编排器通过此注册表查找和管理 Agent 插件。
"""
from __future__ import annotations

import asyncio
from typing import Optional

from .base import VoiceAgentPlugin


class PluginRegistry:
    """运行时插件注册表。

    线程安全（asyncio.Lock），支持动态注册和注销。
    Agent 插件在 websocket_gateway 创建 session 时注册，
    也可在运行时动态增删实现热插拔。
    """

    def __init__(self) -> None:
        self._plugins: dict[str, VoiceAgentPlugin] = {}
        self._lock = asyncio.Lock()

    async def register(self, plugin: VoiceAgentPlugin) -> None:
        """注册一个 Agent 插件。若 key 已存在则覆盖。"""
        async with self._lock:
            self._plugins[plugin.key] = plugin

    async def unregister(self, key: str) -> None:
        """注销一个 Agent 插件。key 不存在时静默忽略。"""
        async with self._lock:
            self._plugins.pop(key, None)

    def get(self, key: str) -> Optional[VoiceAgentPlugin]:
        """按 key 获取 Agent 插件。不存在返回 None。"""
        return self._plugins.get(key)

    def list_keys(self) -> list[str]:
        """列出所有已注册 Agent 的 key。"""
        return list(self._plugins.keys())

    def __contains__(self, key: str) -> bool:
        return key in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)
