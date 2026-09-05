"""WorkspaceFactory - 根据 DB 配置创建 agentscope Workspace 实例。"""
import logging
import os
from typing import Any

from app.config import settings
from app.models.ai.ai_workspace import AiWorkspace

logger = logging.getLogger(__name__)


def _resolve_workspace_base() -> str:
    """解析 workspace 根目录，委托给 settings.resolved_workspace_base_dir。"""
    return settings.resolved_workspace_base_dir


class WorkspaceFactory:
    """根据 DB 中的 workspace 配置创建对应的 agentscope Workspace 实例。"""

    @staticmethod
    async def create(workspace_record: AiWorkspace) -> Any:
        """根据 workspace_type 和 config 创建 workspace 后端实例。

        Args:
            workspace_record: DB 中的 Workspace 记录

        Returns:
            agentscope WorkspaceBase 子类实例
        """
        ws_type = workspace_record.workspace_type
        config = workspace_record.config or {}
        ws_id = workspace_record.workspace_id

        if ws_type == "local":
            from agentscope.workspace import LocalWorkspace

            workdir = config.get("workdir") or os.path.join(_resolve_workspace_base(), ws_id)
            return LocalWorkspace(
                workdir=workdir,
                workspace_id=ws_id,
            )
        elif ws_type == "docker":
            from agentscope.workspace import DockerWorkspace

            return DockerWorkspace(
                base_image=config.get("base_image", "python:3.11-slim"),
                workdir=config.get("workdir") or os.path.join(_resolve_workspace_base(), ws_id),
                node_version=config.get("node_version", "20"),
                workspace_id=ws_id,
            )
        elif ws_type == "opensandbox":
            from agentscope.workspace import OpenSandboxWorkspace

            return OpenSandboxWorkspace(
                image=config.get("image", "python:3.11-slim"),
                api_key=config.get("api_key", ""),
                domain=config.get("domain", ""),
                protocol=config.get("protocol", "http"),
                workspace_id=ws_id,
            )
        else:
            raise ValueError(f"Unsupported workspace type: {ws_type}")

    @staticmethod
    async def create_and_initialize(workspace_record: AiWorkspace) -> Any:
        """创建并初始化 workspace 实例。"""
        ws = await WorkspaceFactory.create(workspace_record)
        await ws.initialize()
        logger.info(
            "Workspace initialized: %s (%s)",
            workspace_record.name,
            workspace_record.workspace_id,
        )
        return ws
