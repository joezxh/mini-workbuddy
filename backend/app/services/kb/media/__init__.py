"""媒体提取包（spec §4.1）：提取器抽象 + provider 客户端 + 摄取编排。"""
from app.services.kb.media.provider_client import (
    MediaProviderConfig,
    describe_image,
    resolve_asr_config,
    resolve_vision_config,
    transcribe_audio,
)

__all__ = [
    "MediaProviderConfig",
    "describe_image",
    "transcribe_audio",
    "resolve_vision_config",
    "resolve_asr_config",
]
