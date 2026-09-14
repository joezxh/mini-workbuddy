from app.config import settings

def test_voice_config_present():
    assert settings.VOICE_DEFAULT_PROVIDER in ("dashscope", "local")
