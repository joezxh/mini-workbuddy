"""调解语音配置表（M3 配置化，差距分析 §9）。

三张表：
- duplex_voice_config：角色语音配置（greeting / voiceIdentity / 绑定 Agent）
- ai_agent_config：语音绑定的 Agent 配置
- tool_policy：工具调用策略（开关 / 超时 / 每轮上限 / 结果体积上限）
"""
from sqlalchemy import (
    JSON, BigInteger, Boolean, Column, Integer, String, TIMESTAMP, Text, func,
)

from app.db.database import Base


class DuplexVoiceConfig(Base):
    __tablename__ = "duplex_voice_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_id = Column(String(64), unique=True, nullable=False, index=True,
                     comment="角色标识（如 mediator / party_a）")
    role_name = Column(String(128), comment="角色展示名")
    greeting = Column(Text, comment="开场白")
    voice_identity = Column(String(64), comment="音色标识")
    language = Column(String(16), server_default="zh-CN")
    agent_id = Column(String(64), comment="绑定的 Agent")
    case_type = Column(String(64), comment="适用案件类型（空表示通用）")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class AiAgentConfig(Base):
    __tablename__ = "ai_agent_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128))
    type = Column(String(32), server_default="agentscope",
                  comment="agentscope|dify|direct")
    model = Column(String(64), server_default="qwen-plus")
    system_prompt = Column(Text)
    tool_bindings = Column(JSON, comment="绑定的工具名列表")
    mcp_bindings = Column(JSON, comment="绑定的 MCP 服务列表")
    max_react_iters = Column(Integer, server_default="5")
    enable_plan = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class ToolPolicy(Base):
    __tablename__ = "tool_policy"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tool_name = Column(String(128), unique=True, nullable=False, index=True)
    enabled = Column(Boolean, server_default="true")
    timeout_ms = Column(Integer, server_default="8000")
    max_calls_per_turn = Column(Integer, server_default="2")
    max_result_bytes = Column(Integer, server_default="32768")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
