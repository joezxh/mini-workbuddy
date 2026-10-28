"""提取器抽象与图片提取器测试（fake VLM，不发真实请求）。"""
import asyncio

import pytest

from app.services.kb.media import base as media_base


def test_detect_media_kind():
    cases = {
        "a.png": "image", "b.JPG": "image", "c.jpeg": "image",
        "d.mp3": "audio", "e.wav": "audio", "f.m4a": "audio",
        "g.mp4": "video", "h.mov": "video",
        "i.dxf": "drawing",
        "j.pdf": None, "k": None, "l.docx": None,
    }
    for name, kind in cases.items():
        assert media_base.detect_media_kind(name) == kind, name


def test_registry_dispatch(monkeypatch):
    from app.services.kb.media import provider_client as pc
    monkeypatch.setattr(pc, "_from_model_mgmt", lambda *a, **kw: None)
    import app.services.kb.media.image_extractor  # noqa: F401 触发注册
    ext = media_base.get_extractor("image", None)
    assert type(ext).__name__ == "ImageExtractor"
    with pytest.raises(ValueError):
        media_base.get_extractor("nonexistent", None)


def test_image_extractor_produces_single_segment(monkeypatch):
    import app.services.kb.media.image_extractor as mod
    from app.services.kb.media.provider_client import MediaProviderConfig

    captured = {}

    def _fake_resolve(db, override=None):
        captured["override"] = override
        return MediaProviderConfig("gpustack", "http://x/v1", "k", "vlm-1")

    async def _fake_describe(cfg, image_bytes, mime, prompt):
        captured["mime"] = mime
        captured["bytes_len"] = len(image_bytes)
        return "  一张测试图，含文字：OK  "

    monkeypatch.setattr(mod, "resolve_vision_config", _fake_resolve)
    monkeypatch.setattr(mod, "describe_image", _fake_describe)

    ext = mod.ImageExtractor(None)
    result = asyncio.run(ext.extract(b"12345", "test.png"))
    assert result.kind == "image"
    assert len(result.segments) == 1
    seg = result.segments[0]
    assert seg.text == "一张测试图，含文字：OK"  # strip 生效
    assert seg.locator == {}
    assert result.meta["vision_model"] == "vlm-1"
    assert captured["mime"] == "image/png"
    assert captured["bytes_len"] == 5


def test_image_extractor_empty_description_raises(monkeypatch):
    import app.services.kb.media.image_extractor as mod
    from app.services.kb.media.provider_client import MediaProviderConfig

    monkeypatch.setattr(
        mod, "resolve_vision_config",
        lambda db, override=None: MediaProviderConfig("t", "u", "", "m"))

    async def _empty(cfg, *args, **kwargs):
        return "   "

    monkeypatch.setattr(mod, "describe_image", _empty)
    ext = mod.ImageExtractor(None)
    with pytest.raises(ValueError):
        asyncio.run(ext.extract(b"img", "x.jpg"))  # jpg → image/jpeg mime
