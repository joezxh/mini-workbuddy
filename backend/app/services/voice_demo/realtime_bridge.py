"""WS 桥接 — 浏览器 ↔ 网关 ↔ s2s /v1/realtime（spec docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.3）。

websockets 双向泵，connect 注入一次 session.update，其余纯透传；并发闸对齐 s2s pool size 1。
"""
import asyncio
import json
from typing import Optional

import websockets
from fastapi import WebSocket
from jose import JWTError, jwt
from loguru import logger

from app.config import settings

BRIDGE_SEMAPHORE = asyncio.Semaphore(settings.VOICE_DEMO_MAX_CONCURRENCY)


def _jwt_user_id(token: str) -> Optional[int]:
    """query token → user_id；失败返回 None（调用方 close 1008）。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub else None
    except (JWTError, ValueError, TypeError):
        return None


def build_session_update() -> dict:
    """connect 注入：人设 + 音色 + server_vad + 可打断（spec §3.3）。"""
    return {
        "type": "session.update",
        "session": {
            "instructions": settings.VOICE_DEMO_INSTRUCTIONS,
            "voice": settings.VOICE_DEMO_TTS_VOICE,
            "turn_detection": {"type": "server_vad", "interrupt_response": True},
        },
    }


async def run_bridge(websocket: WebSocket) -> None:
    """真实模式：websockets 连上游，双向泵 + 空闲超时。"""
    idle = settings.VOICE_DEMO_WS_IDLE_TIMEOUT_S
    async with websockets.connect(
        settings.VOICE_DEMO_REALTIME_WS_URL,
        open_timeout=settings.VOICE_DEMO_CONNECT_TIMEOUT_MS / 1000,
    ) as up:
        await up.send(json.dumps(build_session_update(), ensure_ascii=False))

        async def up2down() -> None:
            while True:
                msg = await asyncio.wait_for(up.recv(), timeout=idle)
                await websocket.send_text(msg if isinstance(msg, str) else msg.decode())

        async def down2up() -> None:
            while True:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=idle)
                await up.send(raw)

        tasks = [asyncio.create_task(up2down()), asyncio.create_task(down2up())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        exc = next(iter(done)).exception()
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            await websocket.send_text(json.dumps({"type": "error", "code": "UPSTREAM_TIMEOUT"}))
        elif exc:
            logger.warning(f"voice-demo 桥接结束: {exc!r}")
            await websocket.send_text(json.dumps(
                {"type": "error", "code": "UPSTREAM_DISCONNECTED", "message": str(exc)[:200]}))
