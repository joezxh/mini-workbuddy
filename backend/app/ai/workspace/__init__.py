"""Workspace Module - 基于 AgentScope 2.0.4 LocalWorkspace 的统一工作空间管理。"""
from app.ai.workspace.manager import WorkspaceAdapter, get_workspace_adapter  # noqa

__all__ = ["WorkspaceAdapter", "get_workspace_adapter"]
