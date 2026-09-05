"""ConfigTraceMiddleware - 配置追踪中间件。

在 Agent 执行链路中注入配置上下文信息：
- on_reply: 将 agent_config_id / team_config_id 写入 middle_context
- on_acting: 将 tool/skill config_id + snapshot 写入 middle_context
- on_model_call: 记录模型调用关联的配置

TraceService._save_to_db() 读取 middle_context 中的配置信息写入新字段。

用法::

    middleware = ConfigTraceMiddleware(registry=config_registry)
    # 注册到 Agent 的 middlewares 列表
"""
from __future__ import annotations

import logging
import time
from typing import Any, AsyncGenerator, Optional

from agentscope.middleware import MiddlewareBase

logger = logging.getLogger(__name__)

# middle_context 中的 key 前缀
CONFIG_TRACE_PREFIX = "config_trace_"


class ConfigTraceMiddleware(MiddlewareBase):
    """配置追踪中间件 - 在 Agent 执行过程中注入配置上下文。

    写入 middle_context 的数据::

        {
            "config_trace_agent": {"config_id": 1, "name": "risk_analyst", ...},
            "config_trace_team": {"config_id": 2, "name": "risk_team", ...},
            "config_trace_tools": [{"config_id": 3, "name": "search", ...}],
            "config_trace_timestamp": 1722000000.0,
        }
    """

    def __init__(
        self,
        registry: Any = None,
        agent_config_id: int | None = None,
        team_config_id: int | None = None,
        workspace_config_id: int | None = None,
    ) -> None:
        """初始化 ConfigTraceMiddleware。

        Args:
            registry: ConfigRegistry 实例（用于查询配置快照）
            agent_config_id: 当前 Agent 的配置 ID
            team_config_id: 所属 Team 的配置 ID
            workspace_config_id: 所属 Workspace 的配置 ID
        """
        self._registry = registry
        self._agent_config_id = agent_config_id
        self._team_config_id = team_config_id
        self._workspace_config_id = workspace_config_id

    async def on_reply(
        self,
        agent: Any,
        input_kwargs: dict[str, Any],
        next_handler: Any,
    ) -> AsyncGenerator[Any, None]:
        """在 reply 开始时注入配置上下文到 middle_context。"""
        # 注入配置信息到 agent state
        self._inject_config_context(agent)

        # 继续执行
        async for chunk in next_handler(agent, input_kwargs):
            yield chunk

    async def on_acting(
        self,
        agent: Any,
        input_kwargs: dict[str, Any],
        next_handler: Any,
    ) -> AsyncGenerator[Any, None]:
        """在工具执行时记录 tool/skill 配置。"""
        # 提取工具名称
        tool_name = self._extract_tool_name(input_kwargs)

        # 执行工具
        async for chunk in next_handler(agent, input_kwargs):
            yield chunk

        # 执行后记录工具配置
        if tool_name and self._registry:
            self._record_tool_config(agent, tool_name)

    async def on_model_call(
        self,
        agent: Any,
        input_kwargs: dict[str, Any],
        next_handler: Any,
    ) -> AsyncGenerator[Any, None]:
        """模型调用时记录配置关联。"""
        # 确保配置上下文已注入
        self._inject_config_context(agent)

        async for chunk in next_handler(agent, input_kwargs):
            yield chunk

    def get_middleware_key(self) -> str:
        """中间件唯一标识。"""
        return "config_trace"

    # ─── 内部方法 ─────────────────────────────────────────────────────

    def _inject_config_context(self, agent: Any) -> None:
        """将配置信息注入 agent.state.middle_context。"""
        state = getattr(agent, "state", None)
        if state is None:
            return

        middle_context = getattr(state, "middle_context", None)
        if middle_context is None:
            return

        # 避免重复注入
        if f"{CONFIG_TRACE_PREFIX}timestamp" in middle_context:
            return

        # Agent 配置
        if self._agent_config_id and self._registry:
            snapshot = self._registry.get_snapshot("agent", self._agent_config_id)
            if snapshot:
                middle_context[f"{CONFIG_TRACE_PREFIX}agent"] = snapshot

        # Team 配置
        if self._team_config_id and self._registry:
            snapshot = self._registry.get_snapshot("team", self._team_config_id)
            if snapshot:
                middle_context[f"{CONFIG_TRACE_PREFIX}team"] = snapshot

        # Workspace 配置 ID（无快照，仅记录 ID）
        if self._workspace_config_id:
            middle_context[f"{CONFIG_TRACE_PREFIX}workspace_id"] = self._workspace_config_id

        # 时间戳
        middle_context[f"{CONFIG_TRACE_PREFIX}timestamp"] = time.time()

    def _record_tool_config(self, agent: Any, tool_name: str) -> None:
        """记录工具配置到 middle_context。"""
        state = getattr(agent, "state", None)
        if state is None:
            return

        middle_context = getattr(state, "middle_context", None)
        if middle_context is None:
            return

        # 查找工具配置
        tool_config = self._registry.get_by_name("tool", tool_name)
        if tool_config is None:
            # 尝试 skill
            tool_config = self._registry.get_by_name("skill", tool_name)

        if tool_config:
            tools_key = f"{CONFIG_TRACE_PREFIX}tools"
            if tools_key not in middle_context:
                middle_context[tools_key] = []
            middle_context[tools_key].append({
                "config_id": tool_config.get("id"),
                "name": tool_name,
                "timestamp": time.time(),
            })

    @staticmethod
    def _extract_tool_name(input_kwargs: dict[str, Any]) -> str | None:
        """从 input_kwargs 中提取工具名称。"""
        # SDK 工具调用通常在 tool_call 或 name 字段
        tool_call = input_kwargs.get("tool_call")
        if tool_call and hasattr(tool_call, "name"):
            return tool_call.name
        return input_kwargs.get("tool_name") or input_kwargs.get("name")


def extract_config_trace(middle_context: dict[str, Any]) -> dict[str, Any]:
    """从 middle_context 提取配置追踪信息（供 TraceService 使用）。

    Args:
        middle_context: Agent state 的 middle_context

    Returns:
        {
            "agent_config_id": int | None,
            "team_config_id": int | None,
            "workspace_config_id": int | None,
            "component_ids": {"tool": [...], "skill": [...]},
            "spans": [{"config_id": ..., "config_type": ..., "config_snapshot": ...}],
        }
    """
    result: dict[str, Any] = {
        "agent_config_id": None,
        "team_config_id": None,
        "workspace_config_id": None,
        "component_ids": {},
        "spans": [],
    }

    # Agent 配置
    agent_data = middle_context.get(f"{CONFIG_TRACE_PREFIX}agent")
    if agent_data:
        result["agent_config_id"] = agent_data.get("config_id")
        result["spans"].append({
            "config_id": agent_data.get("config_id"),
            "config_type": "agent",
            "config_snapshot": agent_data.get("data"),
        })

    # Team 配置
    team_data = middle_context.get(f"{CONFIG_TRACE_PREFIX}team")
    if team_data:
        result["team_config_id"] = team_data.get("config_id")
        result["spans"].append({
            "config_id": team_data.get("config_id"),
            "config_type": "team",
            "config_snapshot": team_data.get("data"),
        })

    # Workspace 配置
    ws_id = middle_context.get(f"{CONFIG_TRACE_PREFIX}workspace_id")
    if ws_id:
        result["workspace_config_id"] = ws_id

    # 工具/Skill 配置
    tools_data = middle_context.get(f"{CONFIG_TRACE_PREFIX}tools", [])
    tool_ids = []
    for tool in tools_data:
        cid = tool.get("config_id")
        if cid:
            tool_ids.append(cid)
            result["spans"].append({
                "config_id": cid,
                "config_type": "tool",
                "config_snapshot": None,
            })
    if tool_ids:
        result["component_ids"]["tool"] = tool_ids

    return result
