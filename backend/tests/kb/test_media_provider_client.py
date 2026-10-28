"""媒体 provider 客户端测试（fake httpx，不发真实请求）。"""
import asyncio
import base64
import json

from app.services.kb.media import provider_client as pc


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _FakeClient:
    calls: list = []
    next_payload: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        _FakeClient.calls.append({"url": url, **kwargs})
        return _FakeResp(_FakeClient.next_payload)


def _patch_httpx(monkeypatch):
    _FakeClient.calls = []
    _FakeClient.next_payload = {}
    monkeypatch.setattr(pc.httpx, "AsyncClient", _FakeClient)


def test_describe_image_builds_data_uri(monkeypatch):
    _patch_httpx(monkeypatch)
    _FakeClient.next_payload = {"choices": [{"message": {"content": "一张图"}}]}
    cfg = pc.MediaProviderConfig("gpustack", "http://x/v1", "key", "m")
    out = asyncio.run(pc.describe_image(cfg, b"img", "image/png", "描述"))
    assert out == "一张图"
    call = _FakeClient.calls[0]
    assert call["url"] == "http://x/v1/chat/completions"
    body = call["json"]
    assert body["model"] == "m"
    parts = body["messages"][0]["content"]
    assert parts[0]["text"] == "描述"
    expect_b64 = base64.b64encode(b"img").decode()
    assert parts[1]["image_url"]["url"] == f"data:image/png;base64,{expect_b64}"
    assert call["headers"]["Authorization"] == "Bearer key"


def test_transcribe_audio_verbose_segments(monkeypatch):
    _patch_httpx(monkeypatch)
    _FakeClient.next_payload = {"segments": [
        {"start": 0.0, "end": 2.5, "text": "你好"},
        {"start": 2.5, "end": 4.0, "text": "再见"},
    ]}
    cfg = pc.MediaProviderConfig("gpustack", "http://x/v1", "key", "m")
    segs = asyncio.run(pc.transcribe_audio(cfg, b"audio", "a.wav"))
    assert segs == [
        {"start": 0.0, "end": 2.5, "text": "你好"},
        {"start": 2.5, "end": 4.0, "text": "再见"},
    ]
    call = _FakeClient.calls[0]
    assert call["url"] == "http://x/v1/audio/transcriptions"
    assert call["data"]["response_format"] == "verbose_json"
    assert call["files"]["file"][0] == "a.wav"


def test_transcribe_audio_fallback_single_segment(monkeypatch):
    _patch_httpx(monkeypatch)
    _FakeClient.next_payload = {"text": "整段转写"}
    cfg = pc.MediaProviderConfig("gpustack", "http://x/v1", "", "m")
    segs = asyncio.run(pc.transcribe_audio(cfg, b"audio", "a.wav"))
    assert segs == [{"start": 0.0, "end": 0.0, "text": "整段转写"}]


def test_resolve_vision_config_env_fallback_and_override(monkeypatch):
    monkeypatch.setattr(pc, "_from_model_mgmt", lambda *a, **kw: None)
    cfg = pc.resolve_vision_config(None)
    assert cfg.model  # env 默认非空
    # collection 级覆盖（spec §6）：vision_model 替换 model，其余不动
    overridden = pc.resolve_vision_config(None, {"vision_model": " My-VLM "})
    assert overridden.model == "My-VLM"
    assert overridden.base_url == cfg.base_url
    assert pc.resolve_asr_config(None, {"asr_model": "ASR-X"}).model == "ASR-X"


def test_resolve_vision_config_from_model_mgmt(monkeypatch):
    class _Row:
        code = "vlm-default"
        key_id = 1
        model = "Qwen3-VL"

    class _Key:
        status = 1
        url = "http://host:80 "
        api_key = "k"

    class _Scalars:
        def first(self):
            return _Row()

    class _Result:
        def scalars(self):
            return _Scalars()

    class _FakeDB:
        def execute(self, *_a, **_kw):
            return _Result()

        def get(self, _model, pk):
            return _Key() if pk == 1 else None

    cfg = pc.resolve_vision_config(_FakeDB())
    assert cfg.provider == "model_mgmt:vlm-default"
    assert cfg.model == "Qwen3-VL"
    # url 去空格并补 /v1
    assert cfg.base_url == "http://host:80/v1"


def test_resolve_falls_back_when_mgmt_key_disabled(monkeypatch):
    class _Row:
        code = "vlm-default"
        key_id = 9
        model = "Qwen3-VL"

    class _Scalars:
        def first(self):
            return _Row()

    class _Result:
        def scalars(self):
            return _Scalars()

    class _FakeDB:
        def execute(self, *_a, **_kw):
            return _Result()

        def get(self, _model, pk):
            return None  # 密钥缺失 → 回落 env

    cfg = pc.resolve_vision_config(_FakeDB())
    assert not cfg.provider.startswith("model_mgmt:")
