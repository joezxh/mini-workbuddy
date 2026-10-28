"""视频提取器：抽帧(1帧/10s)→VLM 逐帧描述 + 音轨 ASR（spec §5）。

帧级 VLM 失败记入 meta.partial_errors 继续（spec 部分成功语义）；
帧文件与临时音轨在 TemporaryDirectory 内，处理完即删（spec §8）。
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services.kb.media.audio_extractor import AudioExtractor
from app.services.kb.media.base import (
    MediaExtraction,
    MediaSegment,
    default_vision_prompt,
)
from app.services.kb.media.ffmpeg_utils import ensure_ffmpeg, probe_duration_seconds
from app.services.kb.media.provider_client import (
    describe_image,
    resolve_vision_config,
    transcribe_audio,
)

FRAME_INTERVAL_SEC = 10


def _run_ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                   capture_output=True, timeout=600, check=True)


class VideoExtractor:
    """视频 → 帧描述段（frame_index）+ 音轨转写段（时间轴）。"""

    def __init__(self, db, override: Optional[dict] = None):
        self.vision_cfg = resolve_vision_config(db, override)
        self._audio = AudioExtractor(db, override)

    async def extract(self, data: bytes, filename: str) -> MediaExtraction:
        ensure_ffmpeg()
        segments: list[MediaSegment] = []
        partial: list[str] = []
        frame_files: list[Path] = []
        with tempfile.TemporaryDirectory(prefix="kb_video_") as tmp:
            src = Path(tmp) / filename
            src.write_bytes(data)
            max_seconds = settings.MEDIA_MAX_VIDEO_MINUTES * 60
            duration = probe_duration_seconds(str(src))
            if duration > max_seconds:
                raise ValueError(
                    f"视频时长 {duration / 60:.0f}min 超过上限 "
                    f"{settings.MEDIA_MAX_VIDEO_MINUTES}min"
                )
            # 抽帧（JPEG）+ 提音轨（16k 单声道 wav，临时文件用后即删）
            _run_ffmpeg(["-i", str(src), "-vf", f"fps=1/{FRAME_INTERVAL_SEC}",
                         "-q:v", "5", str(Path(tmp) / "frame_%04d.jpg")])
            audio_wav = Path(tmp) / "audio.wav"
            _run_ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
                         str(audio_wav)])
            frame_files = sorted(Path(tmp).glob("frame_*.jpg"))
            # 帧描述：串行调用天然限速（spec §10 provider 限流风险）；单帧失败继续
            for idx, fp in enumerate(frame_files):
                try:
                    text = await describe_image(
                        self.vision_cfg, fp.read_bytes(), "image/jpeg",
                        default_vision_prompt())
                    if text.strip():
                        segments.append(MediaSegment(
                            text=text.strip(), locator={"frame_index": idx}))
                except Exception as exc:  # noqa: BLE001 - 帧级失败继续
                    partial.append(f"frame_{idx}: {exc}")
            # 音轨转写段
            if audio_wav.exists():
                for s in await transcribe_audio(
                        self._audio.cfg, audio_wav.read_bytes(), "audio.wav"):
                    if s["text"].strip():
                        segments.append(MediaSegment(
                            text=s["text"],
                            locator={"start_ms": int(s["start"] * 1000),
                                     "end_ms": int(s["end"] * 1000)}))
            if not segments:
                raise ValueError(
                    f"视频 {filename} 未产出任何分段（帧描述与音轨转写均为空）")
        return MediaExtraction(kind="video", segments=segments, meta={
            "vision_model": self.vision_cfg.model,
            "asr_model": self._audio.cfg.model,
            "duration": duration, "frame_count": len(frame_files),
            "partial_errors": partial,
        })

    def thumbnail_bytes(self, data: bytes) -> bytes:
        """首帧 JPEG（供 asset 预览）；失败由调用方决定是否降级。"""
        proc = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-frames:v", "1",
             "-q:v", "5", "-f", "image2pipe", "-"],
            input=data, capture_output=True, timeout=120, check=True)
        return proc.stdout


def register() -> None:
    from app.services.kb.media.base import register_extractor

    register_extractor("video", VideoExtractor)


register()
