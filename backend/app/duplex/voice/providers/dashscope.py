"""DashScope Realtime Provider。

通过 WebSocket 连接 DashScope Realtime API，
处理双向音频流 + ASR 转写 + 工具调用。
"""
import base64
import json
import os
from typing import Any, AsyncGenerator, Dict, Optional

import websockets
from loguru import logger

from app.duplex.voice.capabilities import ProviderCapabilities
from app.duplex.voice.providers.base import ProviderEvent, RealtimeProvider


class DashScopeProvider(RealtimeProvider):
    """DashScope Realtime Provider 实现。"""

    key = "dashscope"
    input_sample_rate = 16000
    output_sample_rate = 24000

    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        # 对齐 qwen-audio-agent：api-ws 实时端点 + qwen-audio-3.0-realtime-plus
        self._base_url = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
        self._model = "qwen-audio-3.0-realtime-plus"
        self._api_key: Optional[str] = None

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_partial_audio=True,
            supports_interrupt=True,
            supports_duplex=True,
            input_sample_rate=self.input_sample_rate,
            output_sample_rate=self.output_sample_rate,
        )

    async def connect(self, session_config: Dict[str, Any]) -> None:
        """建立与 DashScope Realtime API 的 WebSocket 连接。

        api_key / model / base_url 优先取自 session_config（由网关从数据库解析注入），
        缺省时回退到环境变量 / 内置默认值，保证向后兼容。
        """
        self._api_key = (session_config.get("api_key") or os.getenv("DASHSCOPE_API_KEY") or "").strip()
        if not self._api_key:
            raise ValueError("DashScopeProvider 需要 api_key（请配置语音模型密钥）")
        self._model = session_config.get("model") or self._model
        # 端点可被「API Key 管理」中的 url 覆盖（支持百炼业务空间专属域名）
        base_url = session_config.get("base_url") or self._base_url

        # 对齐 qwen-audio-agent 已验证可用的写法：
        #   - URL 仅带 model 查询参数（不带 api-key）
        #   - 鉴权在 WebSocket 握手阶段通过 Authorization: Bearer <api_key> 头完成
        #     （DashScope Realtime API 当前只认此头；旧的 ?api-key= 查询参数已失效，会触发 401）
        # 鉴权头必须用 additional_headers（直接写入握手请求头，Python 3.11 即可）：
        #   不能用 extra_headers —— 它会转发到 loop.create_connection(extra_headers=)，
        #   该参数需 Python 3.12+，在 3.11 / Windows 上抛 TypeError，导致头发不出 → 401。
        separator = "&" if "?" in base_url else "?"
        url = f"{base_url}{separator}model={self._model}"
        headers = [("Authorization", f"Bearer {self._api_key}")]
        self._ws = await websockets.connect(url, additional_headers=headers)
        await self.configure_session(**session_config)
        logger.info("DashScopeProvider: 已连接")

    async def send_text(self, text: str) -> None:
        """向 DashScope 发送文本（文本模式 / 打断时）。

        对齐 qwen-audio-agent：通过 conversation.item.create 注入用户文本消息，
        并触发 response.create 让模型回应。
        """
        if not self._ws:
            raise RuntimeError("未连接，请先调用 connect()")
        item_event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        }
        await self._ws.send(json.dumps(item_event))
        await self._ws.send(json.dumps({"type": "response.create"}))

    async def send_audio(self, pcm_data: bytes) -> None:
        """发送 PCM 音频数据。

        DashScope api-ws 的 audio 字段接受 base64 编码的 PCM
        （对齐 qwen-audio-agent 的 pcmBase64）；浏览器直接发原始 PCM 字节到此。
        """
        if not self._ws:
            raise RuntimeError("未连接，请先调用 connect()")
        audio_b64 = base64.b64encode(pcm_data).decode("ascii") if isinstance(pcm_data, bytes) else pcm_data
        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }
        await self._ws.send(json.dumps(event))

    async def configure_session(self, **kwargs) -> None:
        """配置 DashScope 会话参数。

        语音质量修复（方案 A）：补配 turn_detection——此前未配置，走服务端默认 VAD
        （阈值不可控），外放回声易误触发。默认 smart_turn（qwen-audio 家族支持，
        对齐 qwen-audio-agent 模型目录 audio 家族默认值）；session_config 可覆盖，
        传 "off" 时不下发（兼容不支持 smart_turn 的自定义模型）。
        """
        if not self._ws:
            return
        config = {
            "type": "session.update",
            "session": {
                "instructions": kwargs.get("instructions", ""),
                "voice": kwargs.get("voice", "default"),
                # api-ws 实时端点使用 "pcm"（非 "pcm16"），对齐 qwen-audio-agent
                "input_audio_format": "pcm",
                "output_audio_format": "pcm",
            },
        }
        turn_detection = kwargs.get("turn_detection", {"type": "smart_turn"})
        if turn_detection and turn_detection != "off":
            config["session"]["turn_detection"] = turn_detection
        # 输入转写：仅显式提供时下发（避免无效字段导致整个 session.update 被拒）
        transcription = kwargs.get("input_audio_transcription")
        if transcription:
            config["session"]["input_audio_transcription"] = transcription
        tools = kwargs.get("tools")
        if tools:
            config["session"]["tools"] = tools
        await self._ws.send(json.dumps(config))

    async def events(self) -> AsyncGenerator[ProviderEvent, None]:
        """产出 DashScope 事件流。"""
        if not self._ws:
            return
        async for raw_msg in self._ws:
            try:
                data = json.loads(raw_msg)
                event = self._parse_event(data)
                if event:
                    yield event
            except json.JSONDecodeError:
                logger.warning(f"DashScopeProvider: 无法解析消息: {raw_msg[:100]}")

    def _parse_event(self, data: Dict[str, Any]) -> Optional[ProviderEvent]:
        """解析 DashScope 事件。"""
        event_type = data.get("type", "")

        if event_type == "conversation.item.input_audio_transcription.completed":
            return ProviderEvent("transcript", {"text": data.get("transcript", "")})
        elif event_type == "response.audio.delta":
            # DashScope api-ws 的 delta 为 base64 编码的 PCM，解码为原始字节，
            # 由网关以二进制帧下发，前端直接播放（无需再次 base64）。
            delta = data.get("delta", "")
            audio = b""
            if isinstance(delta, str) and delta:
                try:
                    audio = base64.b64decode(delta)
                except Exception:
                    audio = b""
            return ProviderEvent("audio_delta", {"audio": audio})
        elif event_type == "response.audio_transcript.delta":
            return ProviderEvent("tts_transcript", {"text": data.get("delta", "")})
        elif event_type == "response.function_call_arguments.done":
            args = data.get("arguments", "{}")
            try:
                parsed_args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                parsed_args = {}
            return ProviderEvent("tool_call", {
                "name": data.get("name", ""),
                "arguments": parsed_args,
            })
        elif event_type == "response.done":
            return ProviderEvent("response_done", {})
        elif event_type == "input_audio_buffer.speech_started":
            return ProviderEvent("speech_started", {})
        elif event_type == "input_audio_buffer.speech_stopped":
            return ProviderEvent("speech_stopped", {})
        elif event_type == "error":
            # 服务端错误事件（如 session.update 含非法字段被拒）：落日志供排查，
            # 不向网关产出事件（_normalize_outbound 无对应映射，透传会被丢弃）
            logger.warning(f"DashScopeProvider: 服务端错误事件: {data}")
            return None

        return None

    async def close(self) -> None:
        """关闭 WebSocket 连接。"""
        if self._ws:
            await self._ws.close()
            self._ws = None
            logger.info("DashScopeProvider: 已断开")


# 自注册到 ProviderRegistry
from app.duplex.voice.providers.registry import ProviderRegistry
ProviderRegistry.register(DashScopeProvider)
