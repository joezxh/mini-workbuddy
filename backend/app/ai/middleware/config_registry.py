"""ConfigRegistry - 组件配置注册表。

启动时从 DB 加载所有组件配置（Agent/Team/Skill/Tool/Workspace），
提供 name → config 和 id → config 的双向映射。
支持定期刷新，避免配置变更后不生效。

用法::

    registry = ConfigRegistry(db)
    await registry.refresh()
    config = registry.get_by_name("agent", "risk_analyst")
    config = registry.get_by_id("agent", 42)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 默认刷新间隔（秒）
DEFAULT_REFRESH_INTERVAL = 300  # 5 分钟


class ConfigRegistry:
    """组件配置注册表 - 从 DB 加载并提供快速查找。

    支持的配置类型:
    - agent: Agent 配置（ai_agent_config 表）
    - team: Team 配置（ai_team_config 表）
    - skill: Skill 配置（ai_skill_package 表）
    - tool: Tool 配置（ai_tool_registry 表）
    - workspace: Workspace 配置
    """

    def __init__(
        self,
        db: Session,
        refresh_interval: int = DEFAULT_REFRESH_INTERVAL,
    ) -> None:
        """初始化 ConfigRegistry。

        Args:
            db: 数据库 session
            refresh_interval: 自动刷新间隔（秒）
        """
        self.db = db
        self.refresh_interval = refresh_interval
        self._last_refresh: float = 0.0

        # 存储结构: {config_type: {id: config_dict}}
        self._by_id: dict[str, dict[int, dict[str, Any]]] = {}
        # 存储结构: {config_type: {name: config_dict}}
        self._by_name: dict[str, dict[str, dict[str, Any]]] = {}

    async def refresh(self) -> None:
        """从 DB 重新加载所有配置。"""
        self._by_id = {}
        self._by_name = {}

        self._load_agents()
        self._load_skills()
        self._load_tools()

        self._last_refresh = time.time()
        total = sum(len(v) for v in self._by_id.values())
        logger.info("ConfigRegistry refreshed: %d configs loaded", total)

    def _ensure_fresh(self) -> None:
        """如果超过刷新间隔则自动刷新。"""
        if time.time() - self._last_refresh > self.refresh_interval:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 在异步上下文中，跳过同步刷新（下次 await 时刷新）
                    return
            except RuntimeError:
                pass
            asyncio.run(self.refresh())

    def get_by_id(self, config_type: str, config_id: int) -> Optional[dict[str, Any]]:
        """按 ID 获取配置。

        Args:
            config_type: 配置类型 (agent/team/skill/tool/workspace)
            config_id: 配置 ID

        Returns:
            配置 dict 或 None
        """
        return self._by_id.get(config_type, {}).get(config_id)

    def get_by_name(self, config_type: str, name: str) -> Optional[dict[str, Any]]:
        """按名称获取配置。

        Args:
            config_type: 配置类型
            name: 配置名称

        Returns:
            配置 dict 或 None
        """
        return self._by_name.get(config_type, {}).get(name)

    def list_configs(self, config_type: str) -> list[dict[str, Any]]:
        """列出某类型的所有配置。"""
        return list(self._by_id.get(config_type, {}).values())

    def get_snapshot(self, config_type: str, config_id: int) -> Optional[dict[str, Any]]:
        """获取配置快照（用于写入 trace）。"""
        config = self.get_by_id(config_type, config_id)
        if config is None:
            return None
        return {
            "config_type": config_type,
            "config_id": config_id,
            "name": config.get("name", ""),
            "snapshot_time": time.time(),
            "data": config,
        }

    # ─── 内部加载方法 ─────────────────────────────────────────────────

    def _load_agents(self) -> None:
        """加载 Agent 配置。"""
        try:
            from app.models.agent.agent_config import AiAgentConfig

            agents = self.db.query(AiAgentConfig).filter(
                AiAgentConfig.enabled == True  # noqa: E712
            ).all()

            type_id_map: dict[int, dict] = {}
            type_name_map: dict[str, dict] = {}

            for agent in agents:
                config = {
                    "id": agent.id,
                    "name": agent.agent_id,
                    "display_name": getattr(agent, "name", agent.agent_id),
                    "agent_type": getattr(agent, "agent_type", "custom"),
                    "enabled": True,
                }
                type_id_map[agent.id] = config
                type_name_map[agent.agent_id] = config

            self._by_id["agent"] = type_id_map
            self._by_name["agent"] = type_name_map
            logger.debug("Loaded %d agent configs", len(type_id_map))
        except Exception as exc:
            logger.warning("Failed to load agent configs: %s", exc)
            self._by_id.setdefault("agent", {})
            self._by_name.setdefault("agent", {})

    def _load_skills(self) -> None:
        """加载 Skill 配置。"""
        try:
            from app.models.ai.ai_skill_package import AiSkillPackage

            skills = self.db.query(AiSkillPackage).filter(
                AiSkillPackage.enabled == True  # noqa: E712
            ).all()

            type_id_map: dict[int, dict] = {}
            type_name_map: dict[str, dict] = {}

            for skill in skills:
                config = {
                    "id": skill.id,
                    "name": skill.package_id,
                    "display_name": getattr(skill, "name", skill.package_id),
                    "enabled": True,
                }
                type_id_map[skill.id] = config
                type_name_map[skill.package_id] = config

            self._by_id["skill"] = type_id_map
            self._by_name["skill"] = type_name_map
            logger.debug("Loaded %d skill configs", len(type_id_map))
        except Exception as exc:
            logger.warning("Failed to load skill configs: %s", exc)
            self._by_id.setdefault("skill", {})
            self._by_name.setdefault("skill", {})

    def _load_tools(self) -> None:
        """加载 Tool 配置。"""
        try:
            from app.models.tool_registry import AiToolRegistry

            tools = self.db.query(AiToolRegistry).filter(
                AiToolRegistry.enabled == True  # noqa: E712
            ).all()

            type_id_map: dict[int, dict] = {}
            type_name_map: dict[str, dict] = {}

            for tool in tools:
                config = {
                    "id": tool.id,
                    "name": tool.tool_code,
                    "display_name": getattr(tool, "name", tool.tool_code),
                    "tool_type": getattr(tool, "tool_type", "custom"),
                    "enabled": True,
                }
                type_id_map[tool.id] = config
                type_name_map[tool.tool_code] = config

            self._by_id["tool"] = type_id_map
            self._by_name["tool"] = type_name_map
            logger.debug("Loaded %d tool configs", len(type_id_map))
        except Exception as exc:
            logger.warning("Failed to load tool configs: %s", exc)
            self._by_id.setdefault("tool", {})
            self._by_name.setdefault("tool", {})


# ─── 全局单例 ──────────────────────────────────────────────────────────

_registry: ConfigRegistry | None = None


def get_config_registry(db: Session | None = None) -> ConfigRegistry | None:
    """获取全局 ConfigRegistry 单例。

    Args:
        db: 数据库 session（仅首次创建时生效）

    Returns:
        ConfigRegistry 实例，或 None（如果无 db 且未初始化）
    """
    global _registry
    if _registry is None and db is not None:
        _registry = ConfigRegistry(db)
    return _registry
