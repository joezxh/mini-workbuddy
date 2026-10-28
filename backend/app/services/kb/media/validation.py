"""媒体上传校验（spec §2.4 成本边界）：多模态开关 + 大小上限。

音频/视频的时长校验在提取器内（extract 时 ffprobe），上传侧只做
字节数校验与开关门禁；非媒体文件不在此校验（走既有文档管线）。
"""
from __future__ import annotations

from app.config import settings
from app.services.kb.media.base import detect_media_kind


def validate_media_upload(knowledge, filename: str, size: int) -> None:
    """媒体文件上传门禁；违规抛 ValueError（调用方转 422）。

    knowledge：WikiKnowledge ORM 实例（读 multimodal_enabled）。
    """
    kind = detect_media_kind(filename)
    if kind is None:
        return
    if not getattr(knowledge, "multimodal_enabled", False):
        raise ValueError("该知识库未启用多模态，无法上传媒体文件")
    if size > settings.MEDIA_MAX_FILE_MB * 1024 * 1024:
        raise ValueError(
            f"文件大小 {size / 1024 / 1024:.0f}MB 超过上限 {settings.MEDIA_MAX_FILE_MB}MB")
    if kind == "drawing" and size > settings.MEDIA_MAX_DXF_MB * 1024 * 1024:
        raise ValueError(
            f"DXF 大小 {size / 1024 / 1024:.0f}MB 超过上限 {settings.MEDIA_MAX_DXF_MB}MB")
