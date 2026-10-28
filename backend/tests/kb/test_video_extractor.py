"""视频提取器测试（fake ffmpeg/VLM/ASR，不依赖真实二进制）。"""
import asyncio
from pathlib import Path

import pytest


@pytest.fixture()
def video_mod(monkeypatch):
    from app.services.kb.media import provider_client as pc
    monkeypatch.setattr(pc, "_from_model_mgmt", lambda *a, **kw: None)
    import app.services.kb.media.video_extractor as mod
    monkeypatch.setattr(mod, "ensure_ffmpeg", lambda: None)
    monkeypatch.setattr(mod, "probe_duration_seconds", lambda p: 35.0)
    return mod


def _fake_run_ffmpeg_factory():
    """伪造 ffmpeg：按输出模板生成 3 个帧文件 + audio.wav。"""

    def _run(args):
        for a in args:
            s = str(a)
            if "frame_%04d.jpg" in s:
                d = Path(s).parent
                for i in (1, 2, 3):
                    (d / f"frame_{i:04d}.jpg").write_bytes(b"frame%d" % i)
            elif s.endswith("audio.wav"):
                Path(s).write_bytes(b"wav-bytes")

    return _run


def test_video_segments_frames_and_transcript(video_mod, monkeypatch):
    mod = video_mod
    monkeypatch.setattr(mod, "_run_ffmpeg", _fake_run_ffmpeg_factory())

    async def _describe(cfg, image_bytes, mime, prompt):
        return f"帧描述[{len(image_bytes)}]"

    async def _transcribe(cfg, data, filename):
        return [{"start": 1.0, "end": 3.0, "text": "讲解"}]

    monkeypatch.setattr(mod, "describe_image", _describe)
    monkeypatch.setattr(mod, "transcribe_audio", _transcribe)

    result = asyncio.run(mod.VideoExtractor(None).extract(b"v", "a.mp4"))
    assert result.kind == "video"
    kinds = [(s.locator.get("frame_index"), s.locator.get("start_ms"))
             for s in result.segments]
    # 3 帧段（frame_index 0/1/2，无 start_ms）+ 1 转写段（无 frame_index，start_ms=1000）
    assert kinds == [(0, None), (1, None), (2, None), (None, 1000)]
    assert result.meta["frame_count"] == 3
    assert result.meta["partial_errors"] == []


def test_video_partial_frame_failure_is_tolerated(video_mod, monkeypatch):
    mod = video_mod
    monkeypatch.setattr(mod, "_run_ffmpeg", _fake_run_ffmpeg_factory())
    calls = {"n": 0}

    async def _describe(cfg, image_bytes, mime, prompt):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("VLM 超时")
        return "ok"

    async def _transcribe(cfg, data, filename):
        return [{"start": 1.0, "end": 3.0, "text": "讲解"}]

    monkeypatch.setattr(mod, "describe_image", _describe)
    monkeypatch.setattr(mod, "transcribe_audio", _transcribe)
    result = asyncio.run(mod.VideoExtractor(None).extract(b"v", "a.mp4"))
    # 帧 2 失败但整体成功：3 段中剩 2 帧段 + 1 转写段
    assert len(result.segments) == 3
    assert len(result.meta["partial_errors"]) == 1
    assert "frame_1" in result.meta["partial_errors"][0]


def test_video_all_empty_raises(video_mod, monkeypatch):
    mod = video_mod
    monkeypatch.setattr(mod, "_run_ffmpeg", _fake_run_ffmpeg_factory())

    async def _describe(cfg, *a, **kw):
        return ""

    async def _transcribe(cfg, data, filename):
        return []

    monkeypatch.setattr(mod, "describe_image", _describe)
    monkeypatch.setattr(mod, "transcribe_audio", _transcribe)
    with pytest.raises(ValueError):
        asyncio.run(mod.VideoExtractor(None).extract(b"v", "a.mp4"))


def test_video_over_limit_raises(video_mod, monkeypatch):
    mod = video_mod
    monkeypatch.setattr(mod, "probe_duration_seconds", lambda p: 40 * 60)
    with pytest.raises(ValueError):
        asyncio.run(mod.VideoExtractor(None).extract(b"v", "a.mp4"))
