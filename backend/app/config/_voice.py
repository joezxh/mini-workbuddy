"""语音 RTC 配置"""
from pydantic import BaseModel


class VoiceSettings(BaseModel):
    """语音 RTC 配置字段

    VOICE_DEFAULT_PROVIDER 值域：dashscope | openai
    （AgentScope RealtimeAgent 内核；openai 需 agentscope > 2.0.8，见 spec §2.3）
    """
    VOICE_DEFAULT_PROVIDER: str = "dashscope"
    VOICE_INPUT_SAMPLE_RATE: int = 16000
    VOICE_OUTPUT_SAMPLE_RATE: int = 24000
    VOICE_RESPONSE_START_TIMEOUT_MS: int = 3000
    VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS: int = 15000
    VOICE_RECONNECT_MAX: int = 5
    VOICE_VAD_THRESHOLD: float = 0.55
