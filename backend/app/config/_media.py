"""多模态媒体处理配置（vision / asr provider，spec §6）。

均走 OpenAI 兼容协议；provider 仅影响默认 base_url/model 取值，
实际以模型管理（type=4 多模态理解 vision / type=8 语音识别 asr）优先、
collection 级覆盖次之、env 兜底
（见 app/services/kb/media/provider_client.py）。
"""
from pydantic import BaseModel


class MediaSettings(BaseModel):
    """媒体摄取配置"""
    MEDIA_VISION_PROVIDER: str = "dashscope"   # gpustack | dashscope
    MEDIA_VISION_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MEDIA_VISION_API_KEY: str = ""
    MEDIA_VISION_MODEL: str = "qwen3.8-flash"

    MEDIA_ASR_PROVIDER: str = "dashscope"      # gpustack | dashscope
    MEDIA_ASR_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MEDIA_ASR_API_KEY: str = ""
    # 语音转写走 chat/completions 的 input_audio，需支持音频输入的模型
    # （qwen3.8-flash 实测不接受音频，故选 omni 系列）
    MEDIA_ASR_MODEL: str = "qwen3.8-omni-flash"

    # 成本边界（spec §2.4），超限拒收
    MEDIA_MAX_FILE_MB: int = 100
    MEDIA_MAX_AUDIO_HOURS: int = 2
    MEDIA_MAX_VIDEO_MINUTES: int = 30
    MEDIA_MAX_DXF_MB: int = 50
