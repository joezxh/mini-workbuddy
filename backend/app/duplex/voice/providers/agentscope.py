"""AgentScope 2.0.8 RealtimeAgent 内核 Provider（spec §2）。

两个注册子类：
- DashScopeAgentProvider(key="dashscope")：Qwen-Omni / Qwen-Audio-3.0 实时模型
- OpenAIAgentProvider(key="openai")：gpt-realtime-*（注册位，2.0.8 暂不可用）

事件映射（spec §3.1）：
ReplyStart(user)→speech_started；ReplyStart(assistant)→response_started；
TextBlockDelta→transcript|tts_transcript；DataBlockDelta→audio_delta；
ReplyEnd(user)→speech_stopped；ReplyEnd(assistant)→playback.ended；
ToolCallStart→tool_call；ToolResultEnd→tool_result；
RequireUserConfirm→tool.confirm_required。
"""
import asyncio
import json
from typing import Any, AsyncGenerator, Dict, Optional

from loguru import logger

from app.duplex.voice.providers.base import RealtimeProvider, ProviderEvent
from app.duplex.voice.providers.agentscope_transport import BrowserTransport


def build_realtime_model(provider_key: str, model_name: str, api_key: str,
                         base_url: Optional[str] = None,
                         voice: str = "default"):
    """模型工厂（spec §2.3）：按模型名前缀选择 AgentScope 模型类。

    注意：agentscope 2.0.8 发布版不含 OpenAIRealtimeModel（官方文档与
    GitHub main 超前于发布版）。gpt-realtime 分支做惰性导入，框架升级后
    零代码自动启用；当前版本下抛出明确的 NotImplementedError。
    """
    from agentscope.credential import DashScopeCredential

    if model_name.startswith("qwen-audio-3.0-realtime"):
        from agentscope.realtime import DashScopeAudioRealtimeModel
        return DashScopeAudioRealtimeModel(
            model=model_name, credential=DashScopeCredential(api_key=api_key))
    if model_name.startswith(("qwen3.5-omni", "qwen3-omni", "qwen-omni")):
        from agentscope.realtime import DashScopeRealtimeModel
        return DashScopeRealtimeModel(
            model=model_name, credential=DashScopeCredential(api_key=api_key),
            parameters=DashScopeRealtimeModel.Parameters(voice=voice))
    if model_name.startswith("gpt-realtime"):
        from agentscope.credential import OpenAICredential
        try:
            from agentscope.realtime import OpenAIRealtimeModel
        except ImportError as e:
            raise NotImplementedError(
                f"当前 agentscope 版本不含 OpenAIRealtimeModel（gpt-realtime "
                f"模型需升级 agentscope > 2.0.8 后使用）: {e}") from e
        return OpenAIRealtimeModel(
            model=model_name, credential=OpenAICredential(api_key=api_key))
    raise ValueError(f"未知实时模型: {model_name}（provider={provider_key}）")


def _safe_json(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"_raw": raw}


class AgentscopeRealtimeProvider(RealtimeProvider):
    """以 AgentScope RealtimeAgent 为内核的实时语音 Provider。"""

    def __init__(self, key: Optional[str] = None) -> None:
        # 注册表以 provider_cls() 无参实例化做 is_configured 探测，
        # key 缺省回退到类属性（子类以类属性声明各自 key）
        self.key = key or type(self).key or ""
        self._system_prompt = ""
        self._mcp_tool_schemas: list = []
        self._agent = None
        self._transport: Optional[BrowserTransport] = None
        self._queue: Optional[asyncio.Queue] = None
        self._pump_task: Optional[asyncio.Task] = None
        self._user_replies: set = set()
        # confirm_id → (reply_id, ToolCallBlock)
        self._pending_confirms: Dict[str, tuple] = {}
        self._closed = False

    # ---- 组装（测试可覆写）----

    def _agent_factory(self, model, toolkit):
        from agentscope.agent import RealtimeAgent
        return RealtimeAgent(name="mediator", system_prompt=self._system_prompt,
                             model=model, toolkit=toolkit)

    def _toolkit_factory(self):
        from app.duplex.voice.toolkit_builder import build_toolkit
        return build_toolkit(self._mcp_tool_schemas)

    # ---- RealtimeProvider 接口 ----

    async def connect(self, session_config: Dict[str, Any]) -> None:
        self._system_prompt = session_config.get("instructions", "")
        self._mcp_tool_schemas = session_config.get("mcp_tools", [])
        model = build_realtime_model(
            provider_key=self.key,
            model_name=session_config.get("model", ""),
            api_key=session_config.get("api_key", ""),
            base_url=session_config.get("base_url"),
            voice=session_config.get("voice", "default"),
        )
        self._queue = asyncio.Queue()
        self._transport = BrowserTransport(
            input_sample_rate=model.input_sample_rate,
            output_sample_rate=model.output_sample_rate,
            uplink=asyncio.Queue(), downlink_events=self._queue,
        )
        self._agent = self._agent_factory(model, self._toolkit_factory())
        await self._agent.connect()
        await self._transport.start()
        await self._start_pump()

    async def _start_pump(self) -> None:
        if self._pump_task is not None or self._agent is None:
            return
        self._pump_task = asyncio.create_task(
            self._pump(self._agent, self._transport, self._queue))

    async def _pump(self, agent, transport, queue) -> None:
        from agentscope.event import (
            DataBlockDeltaEvent, ReplyEndEvent, ReplyStartEvent,
            RequireUserConfirmEvent, TextBlockDeltaEvent, ToolCallStartEvent,
            ToolResultEndEvent,
        )
        try:
            async for ev in agent.reply_stream(transport):
                match ev:
                    case ReplyStartEvent(role="user"):
                        self._user_replies.add(ev.reply_id)
                        await queue.put(ProviderEvent("speech_started", {}))
                    case ReplyStartEvent():
                        await queue.put(ProviderEvent("response_started", {}))
                    case TextBlockDeltaEvent():
                        is_user = ev.reply_id in self._user_replies
                        await queue.put(ProviderEvent(
                            "transcript" if is_user else "tts_transcript",
                            {"text": ev.delta}))
                    case DataBlockDeltaEvent():
                        # 音频统一走 transport.send_audio 单通道下发（RealtimeAgent
                        # 在同一事件上既调 send_audio 又 emit 本事件；若在此再次
                        # 映射会导致每个音频块重复两份）。此处仅显式忽略。
                        pass
                    case ToolCallStartEvent():
                        await queue.put(ProviderEvent(
                            "tool_call", {"call_id": ev.tool_call_id,
                                          "name": ev.tool_call_name}))
                    case ToolResultEndEvent():
                        await queue.put(ProviderEvent(
                            "tool_result", {"call_id": ev.tool_call_id,
                                            "state": str(ev.state)}))
                    case RequireUserConfirmEvent():
                        for tc in ev.tool_calls:
                            self._pending_confirms[tc.id] = (ev.reply_id, tc)
                            await queue.put(ProviderEvent(
                                "tool.confirm_required",
                                {"confirm_id": tc.id, "tool_name": tc.name,
                                 "arguments": _safe_json(tc.input),
                                 "timeout_ms": 300000}))
                    case ReplyEndEvent() if ev.reply_id in self._user_replies:
                        await queue.put(ProviderEvent("speech_stopped", {}))
                    case ReplyEndEvent():
                        await queue.put(ProviderEvent(
                            "playback.ended",
                            {"reply_id": ev.reply_id,
                             "finished_reason": str(ev.finished_reason)}))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - 泵异常落事件流
            if not self._closed:
                logger.error(f"AgentScope 事件泵异常: {e}")
                await queue.put(ProviderEvent(
                    "error", {"code": "fatal", "message": str(e)}))
        finally:
            # 无论正常/异常/取消结束，都必须唤醒 events() 消费者
            await queue.put(None)

    async def send_audio(self, pcm_data: bytes) -> None:
        if self._transport is None:  # 未连接（含测试直注场景）：无下游可送
            return
        if self._transport.input_sample_rate != 16000:
            self._transport.submit_resampled(pcm_data, source_rate=16000)
        else:
            self._transport.submit_audio(pcm_data)

    async def send_text(self, text: str) -> None:
        if self._agent is not None and not self._agent.model.supports_text_input:
            await self._queue.put(ProviderEvent(
                "error", {"code": "text_unsupported",
                          "message": f"{type(self._agent.model).__name__} 不支持文本输入"}))
            return
        if self._transport is None:
            await self._queue.put(ProviderEvent(
                "error", {"code": "not_connected",
                          "message": "语音会话未连接，无法发送文本"}))
            return
        self._transport.submit_text(text)

    async def interrupt(self) -> None:
        if self._agent is not None:
            await self._agent.interrupt()

    async def resolve_confirm(self, confirm_id: str, approved: bool) -> None:
        entry = self._pending_confirms.pop(confirm_id, None)
        if entry is None:
            return
        reply_id, tool_call = entry
        from agentscope.event import ConfirmResult, UserConfirmResultEvent
        payload = UserConfirmResultEvent(
            reply_id=reply_id,
            confirm_results=[ConfirmResult(confirmed=approved,
                                           tool_call=tool_call)],
        ).model_dump(exclude_none=True)
        self._transport.submit_confirm(payload)

    async def configure_session(self, **kwargs) -> None:
        return None  # 会话在 connect 一次性配置

    async def events(self) -> AsyncGenerator[ProviderEvent, None]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def close(self) -> None:
        self._closed = True
        if self._pump_task is not None:
            self._pump_task.cancel()
            # 等待泵真正退出并回收取消异常，避免悬挂任务与竞态
            try:
                await asyncio.gather(self._pump_task, return_exceptions=True)
            except Exception:  # noqa: BLE001
                pass
            self._pump_task = None
        if self._transport is not None:
            self._transport.close_uplink()
            await self._transport.close()
        if self._agent is not None:
            try:
                await self._agent.close()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"agent close 异常（忽略）: {e}")
        if self._queue is not None:
            await self._queue.put(None)

    def get_capabilities(self):
        from app.duplex.voice.capabilities import ProviderCapabilities
        return ProviderCapabilities(
            input_sample_rate=16000, output_sample_rate=24000,
            server_vad=True, native_transcription=True,
            barge_in_mode="server")

    def is_configured(self) -> bool:
        from app.duplex.voice.voice_config import resolve_voice_config
        try:
            return bool(resolve_voice_config(self.key).get("configured"))
        except Exception:  # noqa: BLE001
            return False


class DashScopeAgentProvider(AgentscopeRealtimeProvider):
    key = "dashscope"


class OpenAIAgentProvider(AgentscopeRealtimeProvider):
    key = "openai"
