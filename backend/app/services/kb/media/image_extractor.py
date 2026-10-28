"""图片提取器：VLM 描述 + OCR（单段，locator={}）。"""
from __future__ import annotations

from typing import Optional

from app.services.kb.media.base import (
    MediaExtraction,
    MediaSegment,
    default_vision_prompt,
)
from app.services.kb.media.provider_client import (
    MediaProviderConfig,
    describe_image,
    resolve_vision_config,
)


class ImageExtractor:
    """图片 → 单段描述文本（现有 kb_segment chunk_type=image 同语义）。"""

    def __init__(self, db, override: Optional[dict] = None):
        self.cfg: MediaProviderConfig = resolve_vision_config(db, override)

    async def extract(self, data: bytes, filename: str) -> MediaExtraction:
        mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        text = await describe_image(self.cfg, data, mime, default_vision_prompt())
        if not text.strip():
            raise ValueError(f"图片 {filename} 未产出任何描述文本（VLM 返回为空）")
        return MediaExtraction(
            kind="image",
            segments=[MediaSegment(text=text.strip(), locator={})],
            meta={"vision_model": self.cfg.model},
        )


def register() -> None:
    from app.services.kb.media.base import register_extractor

    register_extractor("image", ImageExtractor)


register()
