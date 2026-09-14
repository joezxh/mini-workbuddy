"""本地 Docker S2S Provider（qwen-audio-s2s，OpenAI Realtime GA 协议）。

对齐 qwen-audio-agent 的 speech-to-speech Provider（server/src/voice/providers/s2s.mjs
+ ga-protocol.mjs）：用户自管的本地 speech-to-speech 端点，上游服务掌握全部
模型 / STT / TTS / 音色选择，本 Provider 只描述其 GA 方言的线缆契约。

GA（2025+）方言与 OpenAI beta 方言的差异（ confined to this provider）：
- response 载荷用 output_modalities 而非 modalities；
- 文本增量事件为 response.output_text.*（归一化为 response.text.* 语义）；
- session.update 的 session 载荷需要 type: 'realtime' 判别字段。

端点：默认 ws://127.0.0.1:8765/v1/realtime（可用 ai_api_key.url 覆盖），
可选 Bearer Token（ai_api_key.api_key 非空时下发）。
"""
import base64
import json
from typing import Any, AsyncGenerator, Dict, Optional

import websockets
from loguru import logger

from app.duplex.voice.capabilities import ProviderCapabilities
from app.duplex.voice.providers.base import ProviderEvent, RealtimeProvider

INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
DEFAULT_S2S_REALTIME_URL = "ws://127.0.0.1:8765/v1/realtime"


class S2SProvider(RealtimeProvider):
    """本地 Docker qwen-audio-s2s（GA Realtime 协议）。"""

    key = "s2s"
    input_sample_rate = INPUT_SAMPLE_RATE
    output_sample_rate = OUTPUT_SAMPLE_RATE

    def __init__(self):
        self._ws: Optional[Any] = None
        self._url = DEFAULT_S2S_REALTIME_URL
        self._token: Optional[str] = None
        self._model = "default"

    def get_capabilities(self) -> ProviderCapabilities:
        # 服务端 VAD 主导（GA audio.input.turn_detection=server_vad）；
        # 单响应槽：server-VAD 轮次与 response.create 竞争时会被拒绝而非排队。
        return ProviderCapabilities(
            supports_partial_audio=True,
            supports_interrupt=True,
            supports_duplex=True,
            input_sample_rate=self.input_sample_rate,
            output_sample_rate=self.output_sample_rate,
            server_vad=True,
            native_transcription=True,
        )

    async def connect(self, session_config: Dict[str, Any]) -> None:
        self._url = (
            session_config.get("base_url")
            or DEFAULT_S2S_REALTIME_URL
        ).strip()
        self._token = (session_config.get("api_key") or "").strip() or None
        self._model = session_config.get("model") or "default"

        headers = []
        if self._token:
            headers.append(("Authorization", f"Bearer {self._token}"))
        try:
            self._ws = await websockets.connect(self._url, additional_headers=headers)
        except Exception as exc:  # noqa: BLE001 - 统一转成可读错误
            raise RuntimeError(
                f"连接本地 S2S 服务失败（{self._url}）：{exc}。"
                f"请确认本地 Docker 的 {self._model} 服务已启动"
            ) from exc
        await self.configure_session(**session_config)
        logger.info(f"S2SProvider: 已连接 {self._url} (model={self._model})")

    async def send_text(self, text: str) -> None:
        """注入用户文本消息并触发回复（GA：response 用 output_modalities）。"""
        if not self._ws:
            raise RuntimeError("未连接，请先调用 connect()")
        await self._ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        }))
        await self._ws.send(json.dumps({
            "type": "response.create",
            "response": {"output_modalities": ["audio"]},
        }))

    async def send_audio(self, pcm_data: bytes) -> None:
        if not self._ws:
            raise RuntimeError("未连接，请先调用 connect()")
        audio_b64 = (
            base64.b64encode(pcm_data).decode("ascii")
            if isinstance(pcm_data, bytes)
            else pcm_data
        )
        await self._ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }))

    async def configure_session(self, **kwargs) -> None:
        """GA 方言的 session.update（session 载荷带 type='realtime' 判别字段）。"""
        if not self._ws:
            return
        session: Dict[str, Any] = {
            "type": "realtime",
            "instructions": kwargs.get("instructions", ""),
        }
        tools = kwargs.get("tools")
        if tools:
            # GA 工具为扁平对象（非 beta 的 {type, function} 形状）
            session["tools"] = [
                {
                    "type": "function",
                    "name": t.get("function", {}).get("name", ""),
                    "description": t.get("function", {}).get("description", ""),
                    "parameters": t.get("function", {}).get("parameters", {}),
                }
                if "function" in t
                else t
                for t in tools
            ]
        session["output_modalities"] = ["audio"]
        session["audio"] = {
            "input": {
                # 省略输入格式时按服务端原生 16kHz PCM 管线处理（显式声明
                # 16kHz 反而会使整个 session.update 无效，见 GA schema 注释）
                "turn_detection": {"type": "server_vad", "interrupt_response": True},
            },
            "output": {
                "format": {"type": "audio/pcm", "rate": OUTPUT_SAMPLE_RATE},
            },
        }
        await self._ws.send(json.dumps({"type": "session.update", "session": session}))

    async def events(self) -> AsyncGenerator[ProviderEvent, None]:
        if not self._ws:
            return
        async for raw_msg in self._ws:
            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                logger.warning(f"S2SProvider: 无法解析消息: {str(raw_msg)[:100]}")
                continue
            event = self._parse_event(data)
            if event:
                yield event

    def _parse_event(self, data: Dict[str, Any]) -> Optional[ProviderEvent]:
        """GA 方言事件 → 网关 ProviderEvent。"""
        event_type = data.get("type", "")

        if event_type == "response.audio.delta":
            delta = data.get("delta", "")
            audio = b""
            if isinstance(delta, str) and delta:
                try:
                    audio = base64.b64decode(delta)
                except Exception:  # noqa: BLE001 - 坏帧丢弃不中断会话
                    audio = b""
            return ProviderEvent("audio_delta", {"audio": audio})
        if event_type == "response.audio_transcript.delta":
            return ProviderEvent("tts_transcript", {"text": data.get("delta", "")})
        # GA 方言：文本增量走 response.output_text.*（等价口播文字）
        if event_type == "response.output_text.delta":
            return ProviderEvent("tts_transcript", {"text": data.get("delta", "")})
        if event_type == "conversation.item.input_audio_transcription.completed":
            return ProviderEvent("transcript", {"text": data.get("transcript", "")})
        if event_type == "response.function_call_arguments.done":
            args = data.get("arguments", "{}")
            try:
                parsed = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                parsed = {}
            return ProviderEvent("tool_call", {
                "name": data.get("name", ""),
                "arguments": parsed,
            })
        if event_type == "response.done":
            return ProviderEvent("response_done", {})
        if event_type == "input_audio_buffer.speech_started":
            return ProviderEvent("speech_started", {})
        if event_type == "input_audio_buffer.speech_stopped":
            return ProviderEvent("speech_stopped", {})
        if event_type == "error":
            logger.warning(f"S2SProvider: 服务端错误事件: {data}")
            return None

        return None

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
            logger.info("S2SProvider: 已断开")


# 自注册到 ProviderRegistry
from app.duplex.voice.providers.registry import ProviderRegistry  # noqa: E402
ProviderRegistry.register(S2SProvider)
