"""Agent 适配器：把本平台 Agent 接入实时语音样例回放/工具调用。

- AgentScopeAdapter：接入 app.ai.*（以存量为准，不新建抽象）。
- DirectLLMAdapter：无 app.ai 依赖的直连 LLM 回放（样例/测试/降级）。
- AgentRegistry：运行时按 agent_id 注册/解析适配器。
"""
from typing import Any, Dict, List, Optional, Protocol


class AgentAdapter(Protocol):
    agent_id: str
    engine_code: str

    async def run_voice_turn(
        self,
        audio_b64: Optional[str],
        text: Optional[str],
        history: List[Dict[str, Any]],
        tools: List[str],
    ) -> Dict[str, Any]:
        ...

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        ...


class AgentRegistry:
    """按 agent_id 注册/解析 AgentAdapter。"""

    _registry: Dict[str, AgentAdapter] = {}
    _default_id: Optional[str] = None

    @classmethod
    def register(cls, adapter: AgentAdapter) -> None:
        cls._registry[adapter.agent_id] = adapter

    @classmethod
    def get(cls, agent_id: str) -> AgentAdapter:
        if agent_id not in cls._registry:
            raise KeyError(f"agent not found: {agent_id}")
        return cls._registry[agent_id]

    @classmethod
    def exists(cls, agent_id: str) -> bool:
        return agent_id in cls._registry

    @classmethod
    def set_default(cls, agent_id: str) -> None:
        """指定默认 Agent（未指定时 default() 取首个注册者）。"""
        cls._default_id = agent_id

    @classmethod
    def default(cls) -> Optional[AgentAdapter]:
        """返回默认 AgentAdapter；无注册时返回 None。"""
        if cls._default_id:
            return cls._registry.get(cls._default_id)
        if cls._registry:
            return next(iter(cls._registry.values()))
        return None


class AgentScopeAdapter:
    """接入 app.ai.*（以存量为准，不新建抽象）。"""

    def __init__(
        self,
        agent_id: str,
        engine_code: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_react_iters: int = 5,
    ):
        self.agent_id = agent_id
        self.engine_code = engine_code or "default"
        self.system_prompt = system_prompt
        self.max_react_iters = max_react_iters

    async def run_voice_turn(
        self,
        audio_b64: Optional[str] = None,
        text: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """经统一网关 UnifiedAgentGateway 执行（存量真实入口）。"""
        from app.ai.gateway.gateway import UnifiedAgentGateway
        from app.ai.gateway.models import AgentMode, AgentRequest
        from app.db.database import SessionLocal

        with SessionLocal() as db:
            gateway = UnifiedAgentGateway(db)
            req = AgentRequest(
                mode=AgentMode.AGENT,
                user_input=text or "",
                agent_ids=[self.agent_id],
                context={
                    "history": history or [],
                    "tools": tools or [],
                    "system_prompt": self.system_prompt,
                },
            )
            resp = await gateway.dispatch(req)

        return {
            "text": resp.output or "",
            "audio_b64": None,
            "tool_calls": [],
            "error": resp.error,
        }

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """委托存量 ToolManager 统一调用入口。"""
        from app.ai.tool_manager.manager import ToolManager

        return await ToolManager().call_tool(name, **(args or {}))


class DirectLLMAdapter:
    """无 app.ai 依赖的直连 LLM 回放（用于样例/测试/降级）。"""

    def __init__(self, agent_id: str, engine_code: str = "echo"):
        self.agent_id = agent_id
        self.engine_code = engine_code

    async def run_voice_turn(
        self,
        audio_b64: Optional[str] = None,
        text: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "text": f"[echo] {text or ''}".strip(),
            "audio_b64": None,
            "tool_calls": [],
        }

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"name": name, "result": "ok", "args": args}


class DifyAdapter:
    """接入 app.ai.dify.model_wrapper.DifyModelWrapper（Dify Chatflow，以存量为准）。

    与 AgentScopeAdapter 同构，遵守 AgentAdapter 协议（run_voice_turn / call_tool）。
    Dify Chatflow 本身不暴露原生工具调用，故 call_tool 委托存量 ToolManager。
    """

    def __init__(
        self,
        agent_id: str = "dify",
        flow_code: str = "",
        engine_code: str = "dify",
        stream: bool = False,
    ):
        self.agent_id = agent_id
        self.engine_code = engine_code
        self.flow_code = flow_code
        self.stream = stream
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from app.ai.dify.model_wrapper import DifyModelWrapper

            self._client = DifyModelWrapper(flow_code=self.flow_code, stream=self.stream)
        return self._client

    def _build_messages(self, text: Optional[str], history: Optional[List[Dict[str, Any]]]):
        from agentscope.message import Msg

        # agentscope 2.0：Msg 为 pydantic 模型（关键字传参），
        # 且 content 必须是 list[ContentBlock]，纯字符串会被校验拒绝。
        from agentscope.message import TextBlock

        def _msg(role: str, content: str):
            return Msg(name=role, content=[TextBlock(type="text", text=content)], role=role)

        messages = []
        for item in history or []:
            role = item.get("role", "user")
            messages.append(_msg(role, item.get("content", "")))
        messages.append(_msg("user", text or ""))
        return messages

    async def run_voice_turn(
        self,
        audio_b64: Optional[str] = None,
        text: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        import inspect

        client = self._ensure_client()
        resp = await client(self._build_messages(text, history))

        # 流式模式返回 async generator，需聚合；阻塞模式直接取 content。
        # 用 isasyncgen 显式判定（避免 MagicMock 的 __aiter__ 造成误判）。
        content = ""
        if inspect.isasyncgen(resp):
            async for chunk in resp:
                content += getattr(chunk, "content", "") or ""
        else:
            content = getattr(resp, "content", "") or ""

        return {"text": content, "audio_b64": None, "tool_calls": []}

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        from app.ai.tool_manager.manager import ToolManager

        return await ToolManager().call_tool(name, **(args or {}))


# 默认注册 Dify 适配器（import 即生效，避免调用方手工注册）
AgentRegistry.register(DifyAdapter())
