"""AI 模块 ORM 模型聚合导入。

显式导入确保 Base.metadata 拾取全部表(含 2026_09_27 跨模式上下文新增表),
供 alembic autogenerate 与 create_all 使用。
"""
from app.models.ai.ai_chat import AiChatSession, AiChatMessage
from app.models.ai.ai_chat_context_storage import AIChatContextStorage
from app.models.ai.ai_session_finalize_log import AISessionFinalizeLog

__all__ = [
    "AiChatSession",
    "AiChatMessage",
    "AIChatContextStorage",
    "AISessionFinalizeLog",
]
