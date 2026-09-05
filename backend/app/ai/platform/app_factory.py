"""Platform App Factory - 基于 AgentScope 2.0.4 create_app 的平台入口。

职责:
1. 组装 SDK 基础设施（RedisStorage / RedisMessageBus / LocalWorkspaceManager）
2. 注册业务 SubAgentTemplate（5 种专家模板）
3. 注入自定义中间件（GraphitiMiddleware / ConfigTraceMiddleware）
4. 返回 SDK App 实例供 FastAPI 挂载

用法::

    from app.ai.platform import create_platform_app
    app_instance = create_platform_app()  # 使用 settings 默认配置
"""
from __future__ import annotations

import logging
from typing import Any

from agentscope.app import create_app
from agentscope.app.storage import RedisStorage
from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.middleware import MiddlewareBase

logger = logging.getLogger(__name__)


def _build_storage(settings: Any) -> RedisStorage:
    """构建 Redis 存储后端。"""
    return RedisStorage(
        host=getattr(settings, "REDIS_HOST", "localhost"),
        port=getattr(settings, "REDIS_PORT", 6379),
        db=getattr(settings, "REDIS_DB", 0),
        password=getattr(settings, "REDIS_PASSWORD", None) or None,
    )


def _build_message_bus(settings: Any) -> RedisMessageBus:
    """构建 Redis 消息总线。"""
    return RedisMessageBus(
        host=getattr(settings, "REDIS_HOST", "localhost"),
        port=getattr(settings, "REDIS_PORT", 6379),
        db=getattr(settings, "REDIS_DB", 0),
        password=getattr(settings, "REDIS_PASSWORD", None) or None,
    )


def _build_workspace_manager(settings: Any) -> LocalWorkspaceManager:
    """构建本地 Workspace 管理器。

    注意：此为 SDK 级别的 workspace manager，用于平台 App 初始化。
    业务层的多工作空间管理通过 WorkspaceFactory + WorkspaceAdapter 实现。
    """
    import os

    basedir = getattr(settings, "WORKSPACE_BASE_DIR", None)
    if not basedir:
        # 默认: backend/data/workspace
        backend_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        basedir = os.path.join(backend_root, "data", "workspace")

    # 技能源目录
    skills_dir = getattr(settings, "SKILLS_SOURCE_DIR", None)
    skill_paths = []
    if skills_dir and os.path.isdir(skills_dir):
        for entry in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, entry)
            if os.path.isdir(skill_path) and os.path.isfile(
                os.path.join(skill_path, "SKILL.md")
            ):
                skill_paths.append(skill_path)

    return LocalWorkspaceManager(
        basedir=basedir,
        skill_paths=skill_paths or None,
    )


def _build_middlewares(settings: Any) -> list[MiddlewareBase]:
    """构建自定义中间件列表。"""
    middlewares: list[MiddlewareBase] = []

    # Graphiti 图谱记忆中间件（按需启用）
    if getattr(settings, "NEO4J_ENABLED", False):
        try:
            from app.ai.middleware.graphiti_memory import GraphitiMiddleware

            middlewares.append(
                GraphitiMiddleware(
                    neo4j_uri=getattr(settings, "NEO4J_URI", "bolt://localhost:7687"),
                    neo4j_user=getattr(settings, "NEO4J_USER", "neo4j"),
                    neo4j_password=getattr(settings, "NEO4J_PASSWORD", ""),
                    group_id=getattr(settings, "GRAPHITI_GROUP_ID", "miniworkbuddy"),
                    enabled=True,
                )
            )
            logger.info("GraphitiMiddleware enabled")
        except Exception as exc:
            logger.warning("GraphitiMiddleware init failed: %s", exc)

    return middlewares


def create_platform_app(settings: Any | None = None) -> Any:
    """创建 AgentScope 平台 App 实例。

    Args:
        settings: 应用配置对象（默认从 app.config.settings 读取）

    Returns:
        SDK App 实例（可挂载到 FastAPI）
    """
    if settings is None:
        from app.config import settings as app_settings

        settings = app_settings

    # 1. 基础设施
    storage = _build_storage(settings)
    message_bus = _build_message_bus(settings)
    workspace_manager = _build_workspace_manager(settings)

    # 2. 业务模板
    from app.ai.agents.templates import ALL_TEMPLATES

    # 3. 自定义中间件
    middlewares = _build_middlewares(settings)

    # 4. 创建 App
    app = create_app(
        storage=storage,
        message_bus=message_bus,
        workspace_manager=workspace_manager,
        custom_subagent_templates=ALL_TEMPLATES,
        extra_middlewares=middlewares or None,
        title=getattr(settings, "APP_NAME", "MiniWorkBuddy"),
        version=getattr(settings, "APP_VERSION", "1.0.0"),
    )

    logger.info(
        "Platform app created: %s v%s (templates=%d, middlewares=%d)",
        getattr(settings, "APP_NAME", "App"),
        getattr(settings, "APP_VERSION", "1.0.0"),
        len(ALL_TEMPLATES),
        len(middlewares),
    )

    return app
