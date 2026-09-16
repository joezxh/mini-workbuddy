"""工具调用处理器（差距分析 §3.3 会话级工具调用）。

将 Provider 透传的 function_call 事件，路由给当前 Agent 的工具实现，
并以统一结构返回结果；失败的工具调用可整体 replay（如断线重连后）。
"""
import asyncio
from typing import Any, Dict, List, Optional

from app.duplex.voice.agent_adapter import AgentAdapter


class ToolCallHandler:
    """执行并回放会话级工具调用。"""

    def __init__(self, agent: Optional[AgentAdapter] = None):
        self._agent = agent

    async def handle(
        self,
        tool_name: str,
        args: Dict[str, Any],
        agent: Optional[AgentAdapter] = None,
    ) -> Dict[str, Any]:
        target = agent or self._agent
        if target is None:
            return {
                "name": tool_name,
                "arguments": args,
                "result": None,
                "ok": False,
                "error": "no agent bound",
            }
        try:
            result = await target.call_tool(tool_name, args)
            return {
                "name": tool_name,
                "arguments": args,
                "result": result,
                "ok": True,
            }
        except Exception as e:  # noqa: BLE001 - 工具调用失败需被结构化捕获
            return {
                "name": tool_name,
                "arguments": args,
                "result": None,
                "ok": False,
                "error": str(e),
            }

    def replay(
        self,
        failed: List[Dict[str, Any]],
        agent: Optional[AgentAdapter] = None,
    ) -> List[Dict[str, Any]]:
        """重放一批失败的工具调用（参数中需含 name / arguments）。

        同步接口：逐项在独立事件循环中执行 handle，便于无后端环境下批量重试。
        """
        results: List[Dict[str, Any]] = []
        for item in failed or []:
            name = item.get("name", "")
            args = item.get("arguments", {})
            results.append(asyncio.run(self.handle(name, args, agent)))
        return results
