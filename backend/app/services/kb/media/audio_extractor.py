"""音频提取器：整文件 ASR，按转写分段映射 MediaSegment（spec §4.1）。"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services.kb.media.base import MediaExtraction, MediaSegment
from app.services.kb.media.ffmpeg_utils import ensure_ffmpeg, probe_duration_seconds
from app.services.kb.media.provider_client import resolve_asr_config, transcribe_audio


class AudioExtractor:
    """音频 → ASR 时间轴分段；空转写整篇失败（spec 部分成功语义）。"""

    def __init__(self, db, override: Optional[dict] = None):
        self.cfg = resolve_asr_config(db, override)

    async def extract(self, data: bytes, filename: str) -> MediaExtraction:
        ensure_ffmpeg()
        with tempfile.TemporaryDirectory(prefix="kb_media_") as tmp:
            path = Path(tmp) / filename
            path.write_bytes(data)
            max_seconds = settings.MEDIA_MAX_AUDIO_HOURS * 3600
            duration = probe_duration_seconds(str(path))
            if duration > max_seconds:
                raise ValueError(
                    f"音频时长 {duration / 3600:.1f}h 超过上限 "
                    f"{settings.MEDIA_MAX_AUDIO_HOURS}h"
                )
        segs = await transcribe_audio(self.cfg, data, filename)
        if not segs:
            raise ValueError(f"音频 {filename} 转写结果为空（ASR 无输出）")
        segments = [
            MediaSegment(
                text=s["text"],
                locator={"start_ms": int(s["start"] * 1000),
                         "end_ms": int(s["end"] * 1000)},
            )
            for s in segs
        ]
        return MediaExtraction(
            kind="audio", segments=segments,
            meta={"asr_model": self.cfg.model, "duration": duration},
        )


def register() -> None:
    from app.services.kb.media.base import register_extractor

    register_extractor("audio", AudioExtractor)


register()
