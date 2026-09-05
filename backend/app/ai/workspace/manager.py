"""WorkspaceAdapter - SDK LocalWorkspace 的业务适配层。

设计原则:
1. 封装 AgentScope 2.0.4 LocalWorkspace，提供业务友好的 API
2. 支持 Skill 生命周期管理（add/remove/list）
3. 支持 MCP 客户端管理（add/remove/list）
4. 提供 Toolkit 构建入口，供 Agent 使用
5. 延迟初始化 + 幂等 initialize
"""
from __future__ import annotations

import logging
import os
from typing import Any

from agentscope.workspace import LocalWorkspace
from agentscope.skill import Skill

from app.config import settings

logger = logging.getLogger(__name__)


def _resolve_workspace_base() -> str:
    """解析 workspace 根目录，委托给 settings.resolved_workspace_base_dir。"""
    return settings.resolved_workspace_base_dir


# 默认 workspace 根目录（从配置解析）
DEFAULT_WORKSPACE_DIR = os.path.join(_resolve_workspace_base(), "default")

# 默认 skills 源目录（始终相对于 backend/，不随部署模式变化）
_BACKEND_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DEFAULT_SKILLS_SOURCE_DIR = os.path.join(_BACKEND_ROOT, "data", "skills")


class WorkspaceAdapter:
    """SDK LocalWorkspace 的业务适配层。

    用法::

        adapter = WorkspaceAdapter(workdir="data/workspace/default")
        await adapter.initialize()
        skills = await adapter.list_skills()
        toolkit = adapter.get_toolkit()
    """

    def __init__(
        self,
        workdir: str | None = None,
        skill_paths: list[str] | None = None,
        workspace_id: str | None = None,
        auto_discover_skills: bool = False,
    ) -> None:
        """初始化 WorkspaceAdapter。

        Args:
            workdir: workspace 根目录，默认 backend/data/workspace/default
            skill_paths: 初始化时自动导入的 skill 目录列表
            workspace_id: 已有 workspace ID（续接场景）
            auto_discover_skills: 是否自动发现 DEFAULT_SKILLS_SOURCE_DIR 下的所有 skill
        """
        self._workdir = workdir or DEFAULT_WORKSPACE_DIR
        self._skill_paths = skill_paths or []
        self._workspace_id = workspace_id
        self._ws: LocalWorkspace | None = None
        self._initialized = False

        # 自动发现 skills 源目录下的所有合法 skill
        if auto_discover_skills and not self._skill_paths:
            self._skill_paths = self._discover_skill_dirs(DEFAULT_SKILLS_SOURCE_DIR)

    @property
    def workspace(self) -> LocalWorkspace:
        """获取底层 LocalWorkspace 实例。"""
        if self._ws is None:
            self._ws = LocalWorkspace(
                workdir=self._workdir,
                workspace_id=self._workspace_id,
                skill_paths=self._skill_paths,
            )
        return self._ws

    @property
    def workdir(self) -> str:
        """workspace 根目录绝对路径。"""
        return os.path.abspath(self._workdir)

    @property
    def is_initialized(self) -> bool:
        """是否已完成初始化。"""
        return self._initialized

    async def initialize(self) -> None:
        """初始化 workspace（幂等）。

        - 创建目录结构
        - 恢复/种子 MCP 配置
        - 导入 skill_paths 中的技能
        """
        if self._initialized:
            return
        await self.workspace.initialize()
        self._initialized = True
        logger.info("WorkspaceAdapter initialized: %s", self.workdir)

    # ─── Skill 管理 ─────────────────────────────────────────────────

    async def add_skill(self, skill_path: str) -> None:
        """添加 Skill（从外部目录复制到 workspace）。

        Args:
            skill_path: 包含 SKILL.md 的 skill 目录路径

        Raises:
            ValueError: skill 无效（缺少 SKILL.md 或 frontmatter）
        """
        await self._ensure_initialized()
        await self.workspace.add_skill(skill_path)
        logger.info("Skill added from: %s", skill_path)

    async def remove_skill(self, name: str) -> None:
        """按 agent-facing name 移除 Skill。

        Args:
            name: Skill 名称（SKILL.md frontmatter 中的 name）
        """
        await self._ensure_initialized()
        await self.workspace.remove_skill(name)
        logger.info("Skill removed: %s", name)

    async def list_skills(self) -> list[dict[str, Any]]:
        """列出所有已加载 Skill 的元数据。

        Returns:
            [{"name": ..., "description": ..., "dir": ..., "updated_at": ...}, ...]
        """
        await self._ensure_initialized()
        skills: list[Skill] = await self.workspace.list_skills()
        return [
            {
                "name": sk.name,
                "description": sk.description,
                "dir": sk.dir,
                "updated_at": sk.updated_at,
            }
            for sk in skills
        ]

    async def get_skill(self, name: str) -> dict[str, Any] | None:
        """按名称获取单个 Skill 详情。

        Args:
            name: Skill 名称

        Returns:
            Skill 元数据 dict 或 None
        """
        await self._ensure_initialized()
        skills: list[Skill] = await self.workspace.list_skills()
        for sk in skills:
            if sk.name == name:
                return {
                    "name": sk.name,
                    "description": sk.description,
                    "dir": sk.dir,
                    "markdown": sk.markdown,
                    "updated_at": sk.updated_at,
                }
        return None

    # ─── MCP 管理 ───────────────────────────────────────────────────

    async def add_mcp(self, mcp_config: dict[str, Any]) -> None:
        """添加 MCP 客户端。

        Args:
            mcp_config: AiMcpClient 配置 dict（需符合 AiMcpClient schema）
        """
        from agentscope.mcp import AiMcpClient

        await self._ensure_initialized()
        client = AiMcpClient.model_validate(mcp_config)
        await self.workspace.add_mcp(client)
        logger.info("MCP added: %s", mcp_config.get("name", "unknown"))

    async def remove_mcp(self, name: str) -> None:
        """按名称移除 MCP 客户端。"""
        await self._ensure_initialized()
        await self.workspace.remove_mcp(name)
        logger.info("MCP removed: %s", name)

    async def list_mcps(self) -> list[dict[str, Any]]:
        """列出所有 MCP 客户端配置。"""
        await self._ensure_initialized()
        mcps = await self.workspace.list_mcps()
        return [m.model_dump() if hasattr(m, "model_dump") else m for m in mcps]

    # ─── Toolkit 构建 ───────────────────────────────────────────────

    def get_toolkit(self):
        """构建 Toolkit，包含 workspace skills 目录作为 loader。

        Returns:
            agentscope.tool.Toolkit 实例
        """
        from agentscope.tool import Toolkit

        skills_dir = os.path.join(self.workdir, "skills")
        return Toolkit(skills_or_loaders=[skills_dir])

    async def list_tools(self) -> list:
        """获取 workspace 内置工具列表（Bash, Edit, Glob, Grep, Read, Write）。"""
        await self._ensure_initialized()
        return await self.workspace.list_tools()

    # ─── 生命周期 ───────────────────────────────────────────────────

    async def close(self) -> None:
        """关闭 workspace（释放 MCP 连接等资源）。"""
        if self._ws is not None and self._initialized:
            await self._ws.close()
            self._initialized = False
            logger.info("WorkspaceAdapter closed: %s", self.workdir)

    async def reset(self) -> None:
        """重置 workspace 到空状态（危险操作，会删除 skills/sessions/data）。"""
        await self._ensure_initialized()
        await self.workspace.reset()
        logger.warning("WorkspaceAdapter reset: %s", self.workdir)

    # ─── 内部方法 ───────────────────────────────────────────────────

    async def _ensure_initialized(self) -> None:
        """确保 workspace 已初始化。"""
        if not self._initialized:
            await self.initialize()

    @staticmethod
    def _discover_skill_dirs(source_dir: str) -> list[str]:
        """扫描源目录下所有包含 SKILL.md 的子目录。

        Args:
            source_dir: skills 源目录路径

        Returns:
            合法 skill 目录的绝对路径列表
        """
        if not os.path.isdir(source_dir):
            logger.warning("Skills source dir not found: %s", source_dir)
            return []

        dirs: list[str] = []
        for entry in sorted(os.listdir(source_dir)):
            skill_path = os.path.join(source_dir, entry)
            skill_md = os.path.join(skill_path, "SKILL.md")
            if os.path.isdir(skill_path) and os.path.isfile(skill_md):
                dirs.append(skill_path)
        logger.info("Discovered %d skills from %s", len(dirs), source_dir)
        return dirs


# ─── 模块级工厂 ────────────────────────────────────────────────────────

_default_adapter: WorkspaceAdapter | None = None
_adapter_registry: dict[str, WorkspaceAdapter] = {}


def get_workspace_adapter(
    workdir: str | None = None,
    auto_discover: bool = True,
) -> WorkspaceAdapter:
    """获取全局 WorkspaceAdapter 单例（向后兼容）。

    Args:
        workdir: 自定义 workspace 目录（仅首次生效）
        auto_discover: 是否自动发现 data/skills/ 下的技能

    Returns:
        WorkspaceAdapter 实例
    """
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = WorkspaceAdapter(
            workdir=workdir,
            auto_discover_skills=auto_discover,
        )
    return _default_adapter


async def get_workspace_adapter_by_id(workspace_id: int) -> WorkspaceAdapter | None:
    """根据 DB workspace ID 获取或创建 WorkspaceAdapter 实例。

    使用内存缓存避免重复创建。从 DB 加载配置后通过 WorkspaceFactory 创建底层实例。

    Args:
        workspace_id: workspace 表主键 ID

    Returns:
        WorkspaceAdapter 实例，如果 workspace 不存在返回 None
    """
    cache_key = str(workspace_id)
    if cache_key in _adapter_registry:
        return _adapter_registry[cache_key]

    from app.db.session import SessionLocal
    from app.models.ai.ai_workspace import AiWorkspace
    from app.ai.workspace.factory import WorkspaceFactory

    db = SessionLocal()
    try:
        ws_record = db.query(AiWorkspace).filter(
            AiWorkspace.id == workspace_id,
            AiWorkspace.is_deleted == False,
        ).first()
        if not ws_record:
            return None

        # 根据 DB 配置创建底层 workspace 实例
        ws_instance = await WorkspaceFactory.create(ws_record)

        # 包装为 WorkspaceAdapter
        adapter = WorkspaceAdapter(
            workdir=getattr(ws_instance, 'workdir', None),
            workspace_id=ws_record.workspace_id,
        )
        # 替换底层实例为工厂创建的（支持 Docker/OpenSandbox）
        adapter._ws = ws_instance
        await adapter.initialize()

        _adapter_registry[cache_key] = adapter
        logger.info("WorkspaceAdapter created from DB: id=%d, type=%s", workspace_id, ws_record.workspace_type)
        return adapter
    finally:
        db.close()


def remove_workspace_adapter(workspace_id: int) -> None:
    """从缓存中移除 WorkspaceAdapter（workspace 被删除/禁用时调用）。"""
    cache_key = str(workspace_id)
    adapter = _adapter_registry.pop(cache_key, None)
    if adapter:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(adapter.close())
            else:
                loop.run_until_complete(adapter.close())
        except Exception:
            pass
        logger.info("WorkspaceAdapter removed from cache: id=%d", workspace_id)
