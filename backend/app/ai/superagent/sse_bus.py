"""SSEBus —— SSE 事件总线 + EffectQueue 持久化推送。

契约冻结（根据 experience 2160148 教训）：
  ① SSE 输出格式：每个事件 `event: <name>\ndata: <json>\n\n`（标准 \n\n 分隔）
  ② data 字段统一 json.dumps（双引号，确保前端 JSON.parse 可用）
  ③ 无 sse-starlette 依赖 —— 用原生 StreamingResponse 直接 yield
"""
from __future__ import annotations
import asyncio, json, time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class SSEEvent:
    """一个 SSE 事件 —— 前端 Feed/Ideas/Goals 消费。"""
    event: str   # effect_assess / effect_launch / ticket_created / ticket_completed / ...
    data: dict   # 任意 JSON 数据

    def encode(self) -> str:
        """编码为 SSE wire format —— 双引号 JSON + \n\n 分隔。"""
        return f"event: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


class SSEBus:
    """SSE 事件总线 —— 单例模式，支持多订阅者。"""

    _instance: "SSEBus | None" = None

    def __init__(self):
        self._subscribers: list[asyncio.Queue[SSEEvent]] = []
        self._events: list[SSEEvent] = []  # 历史缓存（最多 200 条）
        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "SSEBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def publish(self, event: str, data: dict | None = None) -> None:
        """发布事件 —— 广播到所有订阅者 + 写入历史缓存。"""
        evt = SSEEvent(event=event, data=data or {})
        async with self._lock:
            self._events.append(evt)
            if len(self._events) > 200:
                self._events = self._events[-200:]
        for q in self._subscribers:
            try:
                q.put_nowait(evt)
            except asyncio.QueueFull:
                pass
        logger.debug(f"SSEBus.publish · {event}")

    def subscribe(self, maxsize: int = 500) -> asyncio.Queue[SSEEvent]:
        """订阅 —— 返回一个 asyncio.Queue，需手动 unsubscribe。"""
        q: asyncio.Queue[SSEEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[SSEEvent]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def replay_history(self, limit: int = 50) -> list[SSEEvent]:
        """重放历史 —— 新订阅者先收到最近 N 条。"""
        return self._events[-limit:]


# 便捷发布函数（全局单例）
async def sse_publish(event: str, data: dict | None = None) -> None:
    await SSEBus.instance().publish(event, data)
