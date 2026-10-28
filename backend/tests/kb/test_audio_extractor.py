"""音频提取器测试（fake ASR + fake ffprobe，不依赖真实 ffmpeg）。"""
import asyncio

import pytest


@pytest.fixture()
def audio_mod(monkeypatch):
    from app.services.kb.media import provider_client as pc
    monkeypatch.setattr(pc, "_from_model_mgmt", lambda *a, **kw: None)
    import app.services.kb.media.audio_extractor as mod
    # 本机/CI 不保证装 ffmpeg：提取逻辑单测打桩依赖，ffmpeg 探测单独测
    monkeypatch.setattr(mod, "ensure_ffmpeg", lambda: None)
    return mod


def test_audio_segments_mapped_to_ms(audio_mod, monkeypatch):
    mod = audio_mod
    monkeypatch.setattr(mod, "probe_duration_seconds", lambda p: 600.0)

    async def _fake_transcribe(cfg, data, filename):
        assert filename == "a.mp3"
        return [
            {"start": 0.0, "end": 2.5, "text": "你好"},
            {"start": 2.5, "end": 4.0, "text": "再见"},
        ]

    monkeypatch.setattr(mod, "transcribe_audio", _fake_transcribe)
    result = asyncio.run(mod.AudioExtractor(None).extract(b"x", "a.mp3"))
    assert result.kind == "audio"
    assert [s.locator for s in result.segments] == [
        {"start_ms": 0, "end_ms": 2500},
        {"start_ms": 2500, "end_ms": 4000},
    ]
    assert result.meta["asr_model"]


def test_audio_over_limit_raises(audio_mod, monkeypatch):
    mod = audio_mod
    monkeypatch.setattr(mod, "probe_duration_seconds", lambda p: 3 * 3600)
    with pytest.raises(ValueError):
        asyncio.run(mod.AudioExtractor(None).extract(b"x", "a.mp3"))


def test_audio_empty_transcription_raises(audio_mod, monkeypatch):
    mod = audio_mod
    monkeypatch.setattr(mod, "probe_duration_seconds", lambda p: 60.0)

    async def _empty(cfg, data, filename):
        return []

    monkeypatch.setattr(mod, "transcribe_audio", _empty)
    with pytest.raises(ValueError):
        asyncio.run(mod.AudioExtractor(None).extract(b"x", "a.wav"))


def test_ensure_ffmpeg_missing_raises(monkeypatch):
    from app.services.kb.media import ffmpeg_utils
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError):
        ffmpeg_utils.ensure_ffmpeg()
