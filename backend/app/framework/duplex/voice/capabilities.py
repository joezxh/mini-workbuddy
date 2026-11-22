"""Provider 能力描述（差距分析 §3.4 能力协商）。

基础能力字段（supports_* / *_sample_rate）由 M1 网关与 Provider 直接消费，
M2 在此扩展「协商维度」：VAD 模式、原生转录、打断模式等，供 ProtocolAdapter
在客户端与服务端之间做能力协商。
"""
from dataclasses import dataclass


@dataclass
class ProviderCapabilities:
    # --- M1 基础能力（网关/Provider 直接依赖，勿删） ---
    supports_partial_audio: bool = True
    supports_interrupt: bool = True
    supports_duplex: bool = True
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000

    # --- M2 协商维度（差距分析 §3.4 能力协商） ---
    server_vad: bool = True
    semantic_vad: bool = False
    native_transcription: bool = True
    manual_vad_only: bool = False
    barge_in_mode: str = "server"  # server | semantic | manual
