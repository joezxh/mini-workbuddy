"""语音连接请求/响应 Schema。"""
from typing import List, Optional
from pydantic import BaseModel


class VoicePart(BaseModel):
    type: str = "text"
    text: str


class VoiceConnectConfig(BaseModel):
    protocol_version: int = 2
    session_id: Optional[str] = None
    case_number: str
    participant_id: str
    mode: str = "single"            # single|multi
    agent_id: Optional[str] = None
    engine_code: Optional[str] = None
    system_prompt: Optional[str] = None
    greeting: Optional[str] = None
    role_name: Optional[str] = None
    voice_identity: Optional[str] = None
    language: Optional[str] = "zh-CN"
    mcp_servers: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    enable_plan: bool = True
    max_react_iters: int = 5
    text_only: bool = False
    voice_enabled: bool = True
    output_enabled: bool = True
    output_mode: str = "voice"      # voice|text


class VoiceReadyPayload(BaseModel):
    session_id: str
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    provider: str
    provider_label: str
