"""网关 v2 集成测试（回环 Provider，无需外部服务）。"""
import asyncio
import json

from fastapi.testclient import TestClient

from app.main import app
from app.duplex.voice.providers.registry import register_provider
from app.duplex.voice.providers.base import RealtimeProvider, ProviderEvent


class LoopbackProvider(RealtimeProvider):
    key = "loopback"

    def __init__(self):
        self._q = None

    async def connect(self, session_config):
        self._q = asyncio.Queue()

    async def send_audio(self, pcm_data):
        await self._q.put(pcm_data)

    async def configure_session(self, **kwargs):
        pass

    async def send_text(self, text):
        if self._q is not None:
            await self._q.put(text.encode())

    async def events(self):
        while True:
            data = await self._q.get()
            yield ProviderEvent(type="audio_delta", data={"audio": data})

    async def close(self):
        pass


def test_text_turn_loopback():
    register_provider("loopback", LoopbackProvider)
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws?case_number=MED-1&participant_id=party_a&provider=loopback"
    ) as ws:
        ws.send_text(json.dumps({"type": "input.message", "text": "你好"}))
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "voice.ready"
        assert frame["data"]["provider"] == "loopback"
