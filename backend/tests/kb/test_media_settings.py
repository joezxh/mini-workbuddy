"""MediaSettings 默认值与校验（spec §2.4 成本边界 / §6 provider）。"""
from app.config import settings


def test_media_settings_defaults():
    assert settings.MEDIA_VISION_PROVIDER == "dashscope"
    assert settings.MEDIA_ASR_PROVIDER == "dashscope"
    assert settings.MEDIA_MAX_FILE_MB == 100
    assert settings.MEDIA_MAX_AUDIO_HOURS == 2
    assert settings.MEDIA_MAX_VIDEO_MINUTES == 30
    assert settings.MEDIA_MAX_DXF_MB == 50
    # 默认模型名非空（env 未配置时也有可读默认值）
    assert settings.MEDIA_VISION_MODEL
    assert settings.MEDIA_ASR_MODEL
