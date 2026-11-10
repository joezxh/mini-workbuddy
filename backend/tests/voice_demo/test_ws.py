"""WS 桥接测试 — spec §3.3（query JWT 鉴权 + Mock 会话）。"""
import pytest
from jose import jwt as jose_jwt

from app.config import settings
from tests.voice_demo.test_health import make_client


def _token(user_id: int = 1) -> str:
    return jose_jwt.encode({"sub": str(user_id)}, settings.SECRET_KEY,
                           algorithm=settings.ALGORITHM)


def test_ws_bad_token_closed_1008():
    with pytest.raises(Exception):  # TestClient 对 accept 前 close 抛 WebSocketDisconnect
        with make_client().websocket_connect("/api/v1/voice-demo/ws?token=bad") as ws:
            ws.receive_json()


def test_ws_mock_session_round():
    with make_client().websocket_connect(f"/api/v1/voice-demo/ws?token={_token()}") as ws:
        created = ws.receive_json()
        assert created["type"] == "session.created"
        # 两片音频触发 Mock 轮次（累计 >= 19200 字节）
        for _ in range(2):
            ws.send_json({"type": "input_audio_buffer.append", "audio": "A" * 9600})
        ws.send_json({"type": "input_audio_buffer.commit"})
        types = []
        for _ in range(30):
            evt = ws.receive_json()
            types.append(evt["type"])
            if evt["type"] == "response.done":
                break
        assert "input_audio_buffer.speech_started" in types
        assert "response.audio.delta" in types
        assert types[-1] == "response.done"
        # 取消：Mock 立即回 done(cancelled)
        ws.send_json({"type": "response.cancel"})
        last = ws.receive_json()
        assert last["type"] == "response.done"
        assert last["response"]["status"] == "cancelled"
