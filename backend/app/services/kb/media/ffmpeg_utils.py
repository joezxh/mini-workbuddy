"""ffmpeg/ffprobe 工具：存在性探测 + 时长探测（音视频共用）。"""
from __future__ import annotations

import json
import shutil
import subprocess


def ensure_ffmpeg() -> None:
    """ffmpeg 缺失显式报错（音视频摄取硬依赖，spec §5）。"""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("缺少 ffmpeg，请安装后重试（音视频摄取依赖）")


def probe_duration_seconds(path: str) -> float:
    """ffprobe 取媒体时长（秒）；解析失败/文件损坏显式抛错。"""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])
