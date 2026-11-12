"""SourceRegistry —— 管理所有 Source 实例 + HealthBoard + 轮询调度。"""
from __future__ import annotations
import asyncio
from typing import Any

from loguru import logger

from .base import SourceKind, SourceTrigger, HealthStatus
from .github import GitHubSource
from .feishu import FeishuSource


class SourceRegistry:
    """SourceKind 注册表 + 轮询调度。"""

    def __init__(self):
        self._sources: dict[str, Any] = {}
        self._poll_tasks: dict[str, asyncio.Task] = {}
        self._engine: Any | None = None  # 可选 engine 引用，用于触发 receive_trigger

    def register(self, name: str, source: Any) -> None:
        self._sources[name] = source
        logger.info(f"SourceRegistry.register · {name} · kind={getattr(source, 'kind', '?')}")

    def unregister(self, name: str) -> None:
        self._sources.pop(name, None)
        task = self._poll_tasks.pop(name, None)
        if task:
            task.cancel()

    def get(self, name: str) -> Any | None:
        return self._sources.get(name)

    def all(self) -> dict[str, Any]:
        return dict(self._sources)

    def health_board(self) -> list[dict]:
        """SourceRegistry.health_board() —— 返回每个 Source 健康状态。"""
        return [s.health() for s in self._sources.values()]

    async def start_all_polling(self, workspace_id: int, engine: Any | None = None) -> None:
        """为每个 enabled Source 启动独立 poll loop。

        Args:
            workspace_id: 当前 workspace 标识
            engine: 可选 engine 实例，用于将 trigger 转交 engine.receive_trigger()
        """
        self._engine = engine
        for name, source in self._sources.items():
            if not source.is_enabled():
                continue
            if name in self._poll_tasks:
                continue
            self._poll_tasks[name] = asyncio.create_task(
                self._poll_loop(name, source, workspace_id, engine=engine)
            )

    async def stop_all_polling(self) -> None:
        for name, task in list(self._poll_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._poll_tasks[name]
        self._engine = None

    async def _poll_loop(self, name: str, source: Any, workspace_id: int,
                          engine: Any | None = None) -> None:
        cursor: str | None = None
        interval = getattr(source, "poll_seconds", 60)
        try:
            while True:
                triggers, cursor = await source.poll_once(workspace_id, cursor)
                if triggers:
                    logger.info(f"SourceRegistry · {name} · {len(triggers)} triggers → engine")
                    if engine is not None:
                        for t in triggers:
                            try:
                                # SourceTrigger dataclass → dict
                                engine.receive_trigger(t.__dict__)
                            except Exception as e:
                                logger.error(f"engine.receive_trigger failed: {e}")
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info(f"SourceRegistry · {name} · polling stopped")
