"""duplex 框架层（自 app/duplex 迁移）。

对外再导出 voice 子包的公共符号，保持迁移前
``from app.duplex import X`` 的调用方写法不变（现为 ``from app.framework.duplex import X``）。
"""
from app.framework.duplex.voice.mcp_session_resolver import McpSessionResolver
from app.framework.duplex.voice.protocol_adapter import NegotiatedSession, ProtocolAdapter
from app.framework.duplex.voice.turn_state import TurnState
from app.framework.duplex.voice.voice_config import (
    _platform_matches,
    create_voice_model,
    list_voice_models,
    list_voice_provider_catalog,
    resolve_voice_config,
    set_default_voice_model,
    update_voice_model,
)
from app.framework.duplex.voice.websocket_gateway import (
    _handle_control_frame,
    router,
)

__all__ = [
    "McpSessionResolver",
    "NegotiatedSession",
    "ProtocolAdapter",
    "TurnState",
    "_handle_control_frame",
    "_platform_matches",
    "create_voice_model",
    "list_voice_models",
    "list_voice_provider_catalog",
    "resolve_voice_config",
    "router",
    "set_default_voice_model",
    "update_voice_model",
]
