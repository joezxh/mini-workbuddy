"""语音能力 Demo 配置（VOICE_DEMO_*）— 独立于 duplex 语音线 VoiceSettings。

直连真实服务：同主机 s2s（127.0.0.1:8765，2026-11-10 实测 REST+WS 全功能）。
详见 docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.5。
"""
from pydantic import BaseModel


class VoiceDemoSettings(BaseModel):
    """语音 Demo 配置段（清单式追加，不改既有 _voice.py）。"""

    VOICE_DEMO_ENABLED: bool = True
    """模块总开关；False 时路由不注册。"""

    VOICE_DEMO_BASE_URL: str = "http://127.0.0.1:8765"
    """REST 上游（探测 /v1/pool + ASR/TTS 转发；2026-11-10 实测可用）。"""

    VOICE_DEMO_REALTIME_WS_URL: str = "ws://127.0.0.1:8765/v1/realtime"
    """对话上游，独立于 BASE_URL（2026-11-10 实测可用）。"""

    VOICE_DEMO_API_KEY: str = "not-needed"
    """上游鉴权占位（137 类部署无鉴权）。"""

    VOICE_DEMO_ASR_MODEL: str = ""
    """可选透传 multipart 的 model 参数；空 = 不传（实测上游无需此字段）。"""

    VOICE_DEMO_TTS_VOICE: str = "Aiden"
    """TTS 默认音色（9 音色清单由前端内置）。"""

    VOICE_DEMO_TTS_LANGUAGE: str = "auto"
    """ASR 默认语言。"""

    VOICE_DEMO_INSTRUCTIONS: str = (
        "你是 MinWorkBuddy 的工作台助手，回答简洁口语化，帮助用户查询待办、日程与信息。"
    )
    """WS connect 时注入 session.update 的 instructions（人设）。"""

    VOICE_DEMO_CONNECT_TIMEOUT_MS: int = 5000
    VOICE_DEMO_READ_TIMEOUT_MS: int = 30000
    """httpx 连接/读超时。"""

    VOICE_DEMO_WS_IDLE_TIMEOUT_S: int = 300
    """桥接空闲超时（无任何帧双向关闭）。"""

    VOICE_DEMO_MAX_CONCURRENCY: int = 1
    """桥接并发闸（对齐 s2s pool size 1）。"""

    VOICE_DEMO_UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024
    """转写上传体积上限。"""
