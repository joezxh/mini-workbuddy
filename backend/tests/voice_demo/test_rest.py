"""voice-demo REST 转发测试 — spec §3.2/§3.6（转发形状为 2026-11-10 实测约定）。"""
import io
import wave

import httpx

from app.config import settings
from tests.voice_demo.test_health import make_client  # 复用（带 auth override）
from app.services.voice_demo import gateway


def mock_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)  # 0.1s 静音
    return buf.getvalue()


def test_asr_mock():
    r = make_client().post(
        "/api/v1/voice-demo/asr/transcribe",
        files={"file": ("a.wav", mock_wav_bytes(), "audio/wav")},
        data={"language": "auto"},
    )
    assert r.status_code == 200
    body = r.json()
    assert {"text", "language", "cost_ms"} <= set(body)


def test_tts_mock_wav():
    r = make_client().post(
        "/api/v1/voice-demo/tts/synthesize",
        json={"text": "你好", "voice": "Aiden", "response_format": "wav"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    w = wave.open(io.BytesIO(r.content), "rb")
    assert w.getnframes() > 0


def test_asr_forward(monkeypatch):
    """httpx MockTransport 验证转发形状（multipart file+language，无 model）。"""
    monkeypatch.setattr(settings, "VOICE_DEMO_MOCK", False)  # 走真实转发分支
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.content
        return httpx.Response(200, json={"text": "今天天气怎么样？", "language": "Chinese"})

    # 注入点：_transport 为返回 transport 实例的工厂函数（生产返回 None）
    monkeypatch.setattr(gateway, "_transport", lambda: httpx.MockTransport(handler))
    r = make_client().post(
        "/api/v1/voice-demo/asr/transcribe",
        files={"file": ("a.wav", mock_wav_bytes(), "audio/wav")},
        data={"language": "auto"},
    )
    assert r.json()["text"] == "今天天气怎么样？"
    assert captured["path"] == "/v1/audio/transcriptions"
    assert b"model" not in captured["body"]  # 默认不传 model（实测约定）


def test_upstream_5xx_maps_502(monkeypatch):
    monkeypatch.setattr(settings, "VOICE_DEMO_MOCK", False)  # 走真实转发分支
    monkeypatch.setattr(
        gateway, "_transport",
        lambda: httpx.MockTransport(lambda req: httpx.Response(500, text="boom")),
    )
    r = make_client().post(
        "/api/v1/voice-demo/tts/synthesize",
        json={"text": "x", "voice": "Aiden", "response_format": "wav"},
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "UPSTREAM_UNAVAILABLE"
