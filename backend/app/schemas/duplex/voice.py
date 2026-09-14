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


# ── M3 配置化：三张配置表的写入 Schema ──────────────────────


class AgentConfigIn(BaseModel):
    agent_id: str
    name: str
    type: str = "agentscope"
    model: str = "qwen-plus"
    system_prompt: str = ""
    tool_bindings: List = []
    mcp_bindings: List = []
    max_react_iters: int = 5
    enable_plan: bool = True


class VoiceRoleConfigIn(BaseModel):
    role_id: str
    role_name: str
    greeting: str = ""
    voice_identity: str = ""
    language: str = "zh-CN"
    agent_id: Optional[str] = None
    case_type: Optional[str] = None


class ToolPolicyIn(BaseModel):
    tool_name: str
    enabled: bool = True
    timeout_ms: int = 8000
    max_calls_per_turn: int = 2
    max_result_bytes: int = 32768
