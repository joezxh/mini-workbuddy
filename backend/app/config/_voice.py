"""语音 RTC 配置"""
from pydantic import BaseModel


class VoiceSettings(BaseModel):
    """语音 RTC 配置字段"""
    VOICE_DEFAULT_PROVIDER: str = "dashscope"
    VOICE_INPUT_SAMPLE_RATE: int = 16000
    VOICE_OUTPUT_SAMPLE_RATE: int = 24000
    VOICE_RESPONSE_START_TIMEOUT_MS: int = 3000
    VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS: int = 15000
    VOICE_RECONNECT_MAX: int = 5
    VOICE_LOCAL_PIPELINE_URL: str = "ws://127.0.0.1:8765"
    VOICE_VAD_THRESHOLD: float = 0.55
    VOICE_LOCAL_ENABLED: bool = False
    VOICE_LOCAL_VAD_MODEL: str = ""      # silero_vad.onnx 路径
    VOICE_LOCAL_STT_MODEL: str = ""      # Paraformer 模型名/路径
    VOICE_LOCAL_TTS_MODEL: str = ""      # CosyVoice2 模型路径
    VOICE_LOCAL_TTS_SPEED: float = 0.95
