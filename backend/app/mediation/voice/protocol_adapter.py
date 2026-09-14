"""能力协商适配器（差距分析 §3.4 能力协商）。

客户端在连接时上报其能力（VAD 模式偏好、采样率期望等），本端结合
ProviderCapabilities 与本端约束，协商出最终会话参数，并据此构造
voice.ready 下行帧，使客户端无需关心具体 Provider 差异。
"""
from dataclasses import dataclass
from typing import Dict

from app.duplex.voice.capabilities import ProviderCapabilities


@dataclass
class NegotiatedSession:
    vad_mode: str
    transcription: bool
    partial_audio: bool
    duplex: bool
    input_sample_rate: int
    output_sample_rate: int


class ProtocolAdapter:
    """客户端/服务端能力协商。"""

    @staticmethod
    def negotiate(
        client_caps: Dict, server_caps: ProviderCapabilities
    ) -> NegotiatedSession:
        client_caps = client_caps or {}
        client_vad = client_caps.get("vad_mode", "server")

        if client_vad == "server" and server_caps.server_vad:
            vad_mode = "server"
        elif client_vad == "semantic" and server_caps.semantic_vad:
            vad_mode = "semantic"
        elif server_caps.manual_vad_only:
            vad_mode = "manual"
        else:
            vad_mode = "server" if server_caps.server_vad else "manual"

        return NegotiatedSession(
            vad_mode=vad_mode,
            transcription=server_caps.native_transcription,
            partial_audio=server_caps.supports_partial_audio,
            duplex=server_caps.supports_duplex,
            input_sample_rate=server_caps.input_sample_rate,
            output_sample_rate=server_caps.output_sample_rate,
        )

    @staticmethod
    def build_ready_payload(
        caps: ProviderCapabilities, session_id: str, provider: str
    ) -> Dict:
        negotiated = ProtocolAdapter.negotiate({}, caps)
        return {
            "session_id": session_id,
            "provider": provider,
            "input_sample_rate": caps.input_sample_rate,
            "output_sample_rate": caps.output_sample_rate,
            "server_vad": caps.server_vad,
            "native_transcription": caps.native_transcription,
            "supports_interrupt": caps.supports_interrupt,
            "vad_mode": negotiated.vad_mode,
        }
