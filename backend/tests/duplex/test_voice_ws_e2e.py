"""T23: 语音网关端到端回归测试（回环 Provider，无需外部服务/联网）。

覆盖：连接 → voice.ready（能力协商） → input.message → transcript/audio 下行。
"""
import asyncio
import json

from fastapi.testclient import TestClient

from app.main import app
from app.duplex.voice.providers.base import ProviderEvent, RealtimeProvider
from app.duplex.voice.providers.registry import register_provider


class EchoProvider(RealtimeProvider):
    """回环 Provider：收到文本 → 产出 transcript + audio_delta。"""

    key = "e2e-echo"

    def __init__(self):
        self._q = None

    async def connect(self, session_config):
        self._q = asyncio.Queue()

    async def send_audio(self, pcm_data):
        await self._q.put(ProviderEvent("audio_delta", {"audio": pcm_data}))

    async def configure_session(self, **kwargs):
        pass

    async def send_text(self, text):
        await self._q.put(ProviderEvent("transcript", {"id": "t1", "text": text}))
        await self._q.put(ProviderEvent("audio_delta", {"audio": b"\x01\x02"}))

    async def events(self):
        while True:
            yield await self._q.get()

    async def close(self):
        pass


def test_ws_text_turn_returns_transcript():
    """连接 → 发送文本 → 收到 transcript 下行帧。"""
    register_provider("e2e-echo", EchoProvider)
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws"
        "?case_number=MED-TEST&participant_id=party_a&provider=e2e-echo"
    ) as ws:
        # 1) 连接即下发 voice.ready（含 M2 能力协商结果）
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "voice.ready"
        assert ready["data"]["provider"] == "e2e-echo"
        assert "input_sample_rate" in ready["data"]
        assert "vad_mode" in ready["data"]

        # 2) 发送文本轮次
        ws.send_text(json.dumps({"type": "input.message", "text": "你好"}))

        # 3) 下行：transcript(JSON) + audio(二进制)
        received = []
        for _ in range(2):
            msg = ws.receive()
            if msg.get("text") is not None:
                received.append(json.loads(msg["text"]))
            else:
                received.append({"type": "__binary__"})

        types = [f["type"] for f in received]
        assert "transcript.delta" in types
        assert "__binary__" in types  # 音频以二进制帧下发


def test_ws_transcript_carries_generation():
    """下行 transcript 帧带 M2 代际标记，供客户端丢弃过期帧。"""
    register_provider("e2e-echo", EchoProvider)
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws"
        "?case_number=MED-TEST2&participant_id=party_a&provider=e2e-echo"
    ) as ws:
        assert json.loads(ws.receive_text())["type"] == "voice.ready"

        ws.send_text(json.dumps({"type": "input.message", "text": "第二轮"}))

        # input.message 推进代际至 1，transcript 应带上该代际
        for _ in range(2):
            msg = ws.receive()
            if msg.get("text") is not None:
                frame = json.loads(msg["text"])
                if frame["type"] == "transcript.delta":
                    assert frame.get("generation", 0) >= 1
                    assert frame["data"]["text"] == "第二轮"
                    return
        raise AssertionError("未收到带代际标记的 transcript 帧")


def test_ws_connect_without_case_number():
    """缺失 case_number 不应导致 422 握手失败（回退为 session_id）。"""
    register_provider("e2e-echo", EchoProvider)
    client = TestClient(app)
    # 故意不传 case_number：修复前会因缺少必需参数返回 422，握手失败
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws"
        "?session_id=MED-NOCASE&participant_id=party_a&provider=e2e-echo"
    ) as ws:
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "voice.ready"


def test_ws_ready_reports_negotiated_vad_mode():
    """客户端请求 server VAD 且服务端支持 → 协商结果为 server。"""
    register_provider("e2e-echo", EchoProvider)
    client = TestClient(app)
    caps = json.dumps({"vad_mode": "server"})
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws"
        f"?case_number=MED-TEST3&participant_id=party_a&provider=e2e-echo&client_caps={caps}"
    ) as ws:
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "voice.ready"
        assert ready["data"]["vad_mode"] == "server"
        assert ready["data"]["server_vad"] is True
