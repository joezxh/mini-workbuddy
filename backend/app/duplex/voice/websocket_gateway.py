"""调解语音 WebSocket 网关 v2（差距分析 §3 实现）。

协议 v2：
- 客户端上行：PCM 帧 / JSON 控制帧（input.message / input.mute / output.mode / interrupt / ping）
- 服务端下行：voice.ready / audio / transcript / turn / error / pong

M2 增强：
- 轮次代际仲裁（turn_state.TurnState）：音频/文本帧携带 generation，过期帧丢弃
- 能力协商（protocol_adapter.ProtocolAdapter）：voice.ready 由协商结果构造
- 事件重放缓冲（replay_buffer）：断线重连回放遗漏的状态帧
- AgentScope RealtimeAgent 内核（providers/agentscope.py，dashscope|openai）
"""
import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from loguru import logger

from app.config import settings
from app.duplex.voice.constants import (
    VoiceState, EventType, ProviderKey, ErrorCode,
)
from app.duplex.voice.providers.registry import get_provider, register_provider
from app.duplex.voice.providers.base import RealtimeProvider, ProviderEvent
from app.duplex.voice.turn_state import TurnState
from app.duplex.voice.metrics import voice_provider_errors, voice_ws_connections
from app.duplex.voice.protocol_adapter import ProtocolAdapter
from app.duplex.voice.replay_buffer import (
    ReplayBuffer,
    SESSION_REPLAY_BUFFERS,
)
from app.duplex.voice.voice_session_service import (
    create_voice_session, update_voice_session_status,
)
from app.duplex.voice.voice_config import resolve_voice_config
from app.duplex.voice.voice_turn_service import (
    append_turn, mark_interrupted, bump_generation, record_latency,
)

# AgentScope 内核 Provider 通过 providers.registry._register_defaults 注册（import 即生效）


router = APIRouter(prefix="/duplex/voice", tags=["调解语音"])


@dataclass
class VoiceSession:
    """语音会话状态（保留以兼容存量 e2e 测试）。"""
    session_id: str = ""
    case_number: str = ""
    party_id: str = ""
    is_active: bool = True

    def close(self):
        self.is_active = False


async def _authenticate(websocket: WebSocket) -> tuple:
    """鉴权（MVP：dev 态跳过 JWT；接入 risk_control 鉴权在 M2）。

    TODO(zxh): 接入 app.deps 鉴权。
    """
    return (
        websocket.query_params.get("session_id", str(uuid.uuid4())),
        websocket.query_params.get("participant_id", "party_a"),
        websocket.query_params.get("agent_id"),
    )


def _parse_client_caps(websocket: WebSocket) -> Dict[str, Any]:
    raw = websocket.query_params.get("client_caps")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


async def _replay_buffered(websocket: WebSocket, session_id: str) -> None:
    """重连：先回放该会话缓冲的状态帧。"""
    buf = SESSION_REPLAY_BUFFERS.get(session_id)
    if not buf:
        return
    for frame in buf.drain():
        await websocket.send_text(json.dumps(frame, ensure_ascii=False))


def _buffer_outbound(session_id: str, frame: Dict[str, Any]) -> None:
    """缓冲可序列化的下行状态帧（供重连回放）。"""
    if isinstance(frame.get("data"), bytes):
        return
    buf = SESSION_REPLAY_BUFFERS.setdefault(session_id, ReplayBuffer())
    buf.push(frame)


async def _normalize_outbound(event: ProviderEvent) -> Optional[Dict[str, Any]]:
    """Provider 事件 → 客户端协议帧（差距分析 §3.4.2）。"""
    etype = event.type
    if etype == "audio_delta":
        audio = event.data.get("audio", b"")
        return {"type": EventType.AUDIO_DELTA.value, "data": audio}
    if etype == "transcript":
        # 用户语音转写（ASR）：标记为 user 角色
        return {"type": EventType.TRANSCRIPT_DELTA.value,
                "data": {"text": event.data.get("text", ""), "role": "user"}}
    if etype == "tts_transcript":
        # 模型口播文字（TTS 转写）：标记为 assistant 角色
        return {"type": EventType.TRANSCRIPT_DELTA.value,
                "data": {"text": event.data.get("text", ""), "role": "assistant"}}
    # M4 本地管线事件
    if etype == "transcript_delta":
        return {"type": EventType.TRANSCRIPT_DELTA.value, "data": event.data}
    if etype == "transcript_final":
        return {"type": EventType.TRANSCRIPT_FINAL.value, "data": event.data}
    if etype == "speech_started":
        return {"type": EventType.TURN_STARTED.value, "data": event.data}
    if etype == "speech_stopped":
        return {"type": EventType.VOICE_STATE.value,
                "data": {"state": VoiceState.LISTENING.value}}
    if etype == "response_started":
        return {"type": EventType.RESPONSE_STARTED.value, "data": event.data}
    if etype == "playback_cancelled":
        return {"type": EventType.PLAYBACK_CANCELLED.value, "data": event.data}
    # 其余透传
    return {"type": etype, "data": event.data}


async def _handle_control_frame(
    frame: Dict[str, Any],
    realtime_provider: RealtimeProvider,
    turn: TurnState,
    voice_session_id: str,
    websocket: Optional[WebSocket] = None,
) -> None:
    """处理客户端控制帧（协议 v2 + tool.confirm 增量）。

    input.message 受响应不活动超时保护：超时则下发 error(inactivity) 并复位聆听态。
    """
    ftype = frame.get("type")
    if ftype == "input.message":
        text = frame.get("text", "")
        turn.turn_id = str(uuid.uuid4())
        turn.on_speech_started()  # 代际 +1，进入 LISTENING
        append_turn(voice_session_id, turn.turn_id, "user", "text", transcript=text)
        timeout_s = settings.VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS / 1000
        try:
            await asyncio.wait_for(realtime_provider.send_text(text), timeout=timeout_s)
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning("语音响应超时（inactivity），复位为聆听态")
            turn.reset_listening()
            if websocket is not None:
                await websocket.send_text(json.dumps({
                    "type": EventType.ERROR.value,
                    "code": ErrorCode.INACTIVITY.value,
                    "message": "响应超时",
                }, ensure_ascii=False))
    elif ftype == "tool.confirm":
        data = frame.get("data", {})
        confirm = getattr(realtime_provider, "resolve_confirm", None)
        if confirm is not None:
            await confirm(data.get("confirm_id", ""), bool(data.get("approved")))
    elif ftype == "input.mute":
        # 透传静音状态（存量 Provider 不支持则忽略）
        pass
    elif ftype == "output.mode":
        pass
    elif ftype == "interrupt":
        _apply_interrupt(turn, voice_session_id)
        interrupt = getattr(realtime_provider, "interrupt", None)
        if interrupt is not None:
            await interrupt()
    elif ftype == "ping":
        # 修复：pong 回客户端，而非发给上游 Provider
        if websocket is not None:
            await websocket.send_text(json.dumps({"type": EventType.PONG.value}))


def _apply_interrupt(turn: TurnState, voice_session_id: str) -> None:
    """打断统一入口：代际 +1 + 轮次标记（客户端 interrupt 与 VAD barge-in 共用）。"""
    if turn.turn_id:
        turn.on_interrupt()
        turn.generation += 1
        mark_interrupted(turn.turn_id)
        bump_generation(turn.turn_id)


@router.get("/metrics")
async def voice_metrics():
    """Prometheus 指标导出（语音层，差距分析 §12）。"""
    from fastapi import Response

    from app.duplex.voice.metrics import render_metrics

    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")


@router.websocket("/ws")
async def voice_websocket(
    websocket: WebSocket,
    case_number: str = "",
    participant_id: str = "",
    provider: str = "dashscope",
    model_id: Optional[int] = Query(None, description="语音模型 ID，缺省使用数据库默认语音模型"),
):
    """调解语音 WebSocket 端点（协议 v2）。

    case_number / participant_id 为可选查询参数：缺失时回退取值，
    避免因漏传导致 FastAPI 422 而使 WS 握手失败（表现为前端"连接异常"）。
    """
    await websocket.accept()
    session_id, participant_id, agent_id = await _authenticate(websocket)
    client_caps = _parse_client_caps(websocket)
    # 缺省兜底：用 session_id 作为案件号、默认当事人
    case_number = case_number or session_id or ""
    participant_id = participant_id or "party_a"

    # 能力协商
    provider_cls = get_provider(provider)
    provider_instance = provider_cls()
    capabilities = provider_instance.get_capabilities()
    negotiated = ProtocolAdapter.negotiate(client_caps, capabilities)

    # 持久化会话
    voice_session_id = create_voice_session(
        duplex_session_id=int(session_id) if session_id.isdigit() else 0,
        case_number=case_number,
        participant_id=participant_id,
        provider=provider,
        mode="single",
        agent_id=agent_id,
    )

    turn = TurnState()
    realtime_provider = provider_cls()

    try:
        # 从数据库解析语音模型配置（api_key + model + 端点），缺省使用默认语音模型。
        # 仅云端 Provider（dashscope/s2s）需要；local / loopback / 测试桩跳过解析
        # （避免误报 no_model）。
        if provider in ("dashscope", "openai"):
            voice_cfg = resolve_voice_config(provider, model_id)
            if not voice_cfg.get("configured"):
                if voice_cfg.get("reason") == "empty_key":
                    raise ValueError(
                        f"语音模型「{voice_cfg.get('model')}」(id={voice_cfg.get('model_id')}) "
                        f"已启用，但关联密钥「{voice_cfg.get('key_name')}」的 api_key 为空："
                        f"请在「API Key 管理」中填写真实的 API Key"
                    )
                if voice_cfg.get("reason") == "invalid_model":
                    raise ValueError(
                        f"语音模型「{voice_cfg.get('model')}」(id={voice_cfg.get('model_id')}) "
                        f"不是有效的实时模型名：请在「语音模型配置」中更正"
                        f"（可用模型见官方实时模型目录）"
                    )
                raise ValueError(
                    "未配置语音模型：请在「语音模型配置」中新增并启用一个语音模型（type=7）"
                )
        else:
            voice_cfg = {}

        # 会话级 MCP 工具注入：读取 Agent 绑定的工具/服务清单（失败不阻塞语音链路）
        mcp_tool_schemas: list = []
        if agent_id:
            try:
                from app.db.database import SessionLocal
                from app.models.duplex.duplex_voice_config import AiAgentConfig
                db = SessionLocal()
                try:
                    row = (
                        db.query(AiAgentConfig)
                        .filter(AiAgentConfig.agent_id == agent_id)
                        .first()
                    )
                    tool_bindings = list(row.tool_bindings or []) if row else []
                    mcp_bindings = list(row.mcp_bindings or []) if row else []
                finally:
                    db.close()
                from app.duplex.voice.mcp_session_resolver import McpSessionResolver
                mcp_tool_schemas = await McpSessionResolver(
                    mcp_service_ids=mcp_bindings,
                    tool_bindings=tool_bindings,
                ).resolve_tools()
                if mcp_tool_schemas:
                    logger.info(
                        f"语音会话注入 {len(mcp_tool_schemas)} 个工具"
                        f"（agent={agent_id}）"
                    )
            except Exception as e:  # noqa: BLE001 - MCP 注入失败不阻塞语音
                logger.warning(f"MCP 工具注入失败（忽略）: {e}")

        await realtime_provider.connect(session_config={
            "instructions": f"你是一位专业的 AI 调解员，正在处理案件 {case_number}。",
            "tools": [],
            "voice": "default",
            "api_key": voice_cfg.get("api_key", ""),
            "model": voice_cfg.get("model", "default"),
            "base_url": voice_cfg.get("base_url"),
            "mcp_tools": mcp_tool_schemas,
        })
    except Exception as e:
        logger.error(f"Provider 连接失败: {e}")
        voice_provider_errors.labels(provider=provider).inc()
        await websocket.send_text(json.dumps({
            "type": EventType.ERROR.value,
            "code": ErrorCode.PROVIDER_UNAVAILABLE.value,
            "message": str(e),
        }, ensure_ascii=False))
        await websocket.close(code=4503)
        return

    # 断线重连：先回放遗漏的状态帧
    await _replay_buffered(websocket, session_id)

    await websocket.send_text(json.dumps({
        "type": EventType.VOICE_READY.value,
        "data": ProtocolAdapter.build_ready_payload(capabilities, voice_session_id, provider),
    }, ensure_ascii=False))

    update_voice_session_status(voice_session_id, "connected")
    voice_ws_connections.inc()

    async def client_reader():
        while True:
            try:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message["type"] == "websocket.receive":
                    data = message.get("text") or message.get("bytes")
                    if isinstance(data, bytes):
                        await realtime_provider.send_audio(data)
                    elif data:
                        frame = json.loads(data)
                        await _handle_control_frame(
                            frame, realtime_provider, turn, voice_session_id, websocket
                        )
            except WebSocketDisconnect:
                break

    async def provider_reader():
        async for event in realtime_provider.events():
            if event.type == "playback_cancelled":
                # VAD barge-in：与客户端 interrupt 走同一代际仲裁入口
                _apply_interrupt(turn, voice_session_id)
            frame = await _normalize_outbound(event)
            if not frame:
                continue
            # 代际标记：携带当前 generation，供客户端丢弃过期帧
            if frame["type"] in (
                EventType.AUDIO_DELTA.value,
                EventType.TRANSCRIPT_DELTA.value,
            ):
                frame["generation"] = turn.generation
            if isinstance(frame.get("data"), bytes):
                await websocket.send_bytes(frame["data"])
            else:
                _buffer_outbound(session_id, frame)
                await websocket.send_text(json.dumps(frame, ensure_ascii=False))

    # 任一 reader 退出（客户端断开 / provider 事件流终止）即整体收尾：
    # gather 会在 provider_reader 阻塞于空队列时永远等待，导致 close 永不执行
    # （每个会话泄漏一个上游模型连接），故用 asyncio.wait FIRST_COMPLETED。
    client_task = asyncio.create_task(client_reader())
    provider_task = asyncio.create_task(provider_reader())
    try:
        done, pending = await asyncio.wait(
            {client_task, provider_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.wait(pending)
        for t in done:
            exc = t.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                logger.warning(f"语音 reader 异常退出: {exc}")
    finally:
        update_voice_session_status(voice_session_id, "disconnected")
        voice_ws_connections.dec()
        await realtime_provider.close()
