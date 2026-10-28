"""媒体提取器抽象（spec §4.1）：统一输出 分段文本 + 定位器。

locator 约定：音频/视频 {"start_ms": int, "end_ms": int}；视频帧描述附带
{"frame_index": int}；DXF {"layer": str}；图片 {}。经 Chunk.metadata 落
kms_segment.metadata_（零 DDL，spec 简化说明）。

注册表用「懒加载模块导入」：各提取器模块 import 时自注册，避免导入顺序问题。
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Optional, Protocol

# kind → 提取器模块名（app.services.kb.media.<module>）
_KIND_MODULES: dict[str, str] = {
    "image": "image_extractor",
    "audio": "audio_extractor",
    "video": "video_extractor",
    "drawing": "dxf_extractor",
}
_KIND_TO_EXTRACTOR: dict[str, type] = {}

# 扩展名 → 媒体大类（大小写不敏感，detect 时统一 lower）
EXT_KIND_MAP: dict[str, str] = {
    "png": "image", "jpg": "image", "jpeg": "image",
    "gif": "image", "bmp": "image", "webp": "image",
    "mp3": "audio", "wav": "audio", "m4a": "audio",
    "mp4": "video", "mov": "video",
    "dxf": "drawing",
}


@dataclass
class MediaSegment:
    """一个媒体分段：可检索文本 + 定位器（时间轴/帧号/图层）。"""

    text: str
    locator: dict = field(default_factory=dict)


@dataclass
class MediaExtraction:
    """一次提取的完整产出。"""

    kind: str
    segments: list[MediaSegment]
    meta: dict = field(default_factory=dict)


class MediaExtractor(Protocol):
    """媒体提取器接口：bytes+filename → 分段列表。"""

    def __init__(self, db, override: Optional[dict] = None) -> None: ...

    async def extract(self, data: bytes, filename: str) -> MediaExtraction: ...


def detect_media_kind(filename: str) -> Optional[str]:
    """按扩展名判定媒体大类；非媒体返回 None（走既有文档管线）。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXT_KIND_MAP.get(ext)


def register_extractor(kind: str, cls: type) -> None:
    """提取器模块 import 时自注册（同 kind 后注册覆盖先注册）。"""
    _KIND_TO_EXTRACTOR[kind] = cls


def get_extractor(kind: str, db, override: Optional[dict] = None) -> MediaExtractor:
    """按 kind 构造提取器；懒加载对应模块，未知 kind 显式失败。"""
    module = _KIND_MODULES.get(kind)
    if module is None:
        raise ValueError(f"不支持的媒体类型: {kind!r}")
    importlib.import_module(f"app.services.kb.media.{module}")  # 触发自注册
    cls = _KIND_TO_EXTRACTOR.get(kind)
    if cls is None:
        raise ValueError(f"媒体提取器未注册: {kind!r}")
    return cls(db, override)


def default_vision_prompt() -> str:
    """图片描述默认提示词：描述内容 + 逐条 OCR 原文。"""
    return ("请用中文详细描述这张图片的内容；若图中有文字（OCR），逐条原样列出。"
            "不要输出与图片无关的内容。")
