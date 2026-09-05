"""ReMe 长期记忆集成 — 按用户隔离记忆空间。

当前使用 GraphitiMiddleware（Neo4j 图数据）作为后端。
未来可切换至 ReMeMiddleware（当 agentscope[reme] 可用时）。

Usage:
    memory = UserMemoryManager.get_memory(user_id="user_123")
    agent = Agent(..., middlewares=[memory])
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class UserMemoryManager:
    """按用户隔离的记忆管理器。

    每个用户拥有独立的记忆空间（group_id），互不干扰。
    底层使用 GraphitiMiddleware（Neo4j 图数据）。
    """

    _instances: Dict[str, Any] = {}
    _graphiti_available: Optional[bool] = None

    @classmethod
    def get_memory(cls, user_id: str, **kwargs) -> Any:
        """获取用户的记忆中间件实例。

        Args:
            user_id: 用户 ID
            **kwargs: 传递给 GraphitiMiddleware 的额外参数

        Returns:
            记忆中间件实例（GraphitiMiddleware 或 None）
        """
        if user_id in cls._instances:
            return cls._instances[user_id]

        # 尝试使用 GraphitiMiddleware
        if cls._graphiti_available is None:
            cls._graphiti_available = cls._check_graphiti()

        if not cls._graphiti_available:
            logger.debug("GraphitiMiddleware 不可用，用户 %s 无长期记忆", user_id)
            return None

        try:
            from app.ai.middleware.graphiti_memory import GraphitiMiddleware

            middleware = GraphitiMiddleware(
                group_id=f"user_{user_id}",
                **kwargs,
            )
            cls._instances[user_id] = middleware
            logger.info("为用户 %s 创建 Graphiti 记忆中间件", user_id)
            return middleware
        except Exception as e:
            logger.warning("为用户 %s 创建记忆中间件失败: %s", user_id, e)
            return None

    @classmethod
    def clear_cache(cls, user_id: Optional[str] = None) -> None:
        """清除缓存的记忆中间件实例。"""
        if user_id:
            cls._instances.pop(user_id, None)
        else:
            cls._instances.clear()

    @staticmethod
    def _check_graphiti() -> bool:
        """检查 GraphitiMiddleware 是否可用。"""
        try:
            from app.ai.middleware.graphiti_memory import GraphitiMiddleware
            return True
        except ImportError:
            return False


# TODO: ReMe 集成（待 agentscope[reme] 可用后启用）
#
# class ReMeMemoryManager:
#     """基于 ReMe 的长期记忆管理。"""
#     _instances: Dict[str, Any] = {}
#
#     @classmethod
#     def get_memory(cls, user_id: str) -> Any:
#         from agentscope.middleware import ReMeMiddleware
#         if user_id not in cls._instances:
#             cls._instances[user_id] = ReMeMiddleware(
#                 workspace_dir=f".reme/users/{user_id}/",
#             )
#         return cls._instances[user_id]
