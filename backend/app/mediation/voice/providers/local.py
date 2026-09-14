"""Local Provider（本地私有化管线，M4 真实对接）。

四 stage 编排：
    Silero VAD  →  Paraformer 2pass  →  AgentAdapter  →  CosyVoice2

- 各 stage 惰性加载重型依赖（onnxruntime / funasr / cosyvoice），
  缺依赖时按 stage 优雅降级（能量 VAD / 占位转写 / 静音 wav），
  使编排本身可跑通、可测试。
- 总开关 `VOICE_LOCAL_ENABLED`：关闭时 `is_configured()=False`，
  `connect()` 直接抛出，交由上层（registry/网关）降级到云端 Provider。
- supervisor：单个 stage 崩溃自动重启，不影响整体会话。
"""
import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger

from app.config import settings
from app.duplex.voice.agent_adapter import AgentRegistry
from app.duplex.voice.capabilities import ProviderCapabilities
from app.duplex.voice.providers.base import ProviderEvent, RealtimeProvider


class LocalProvider(RealtimeProvider):
    """本地管线 Provider（Silero + Paraformer + Agent + CosyVoice2）。"""

    key = "local"
    input_sample_rate = 16000
    output_sample_rate = 24000

    def __init__(self):
        self._in: asyncio.Queue = asyncio.Queue()        # 上行音频块
        self._out: asyncio.Queue = asyncio.Queue()       # 下行 ProviderEvent
        self._speech_q: asyncio.Queue = asyncio.Queue()  # VAD 判定为语音的块 → STT
        self._text_q: asyncio.Queue = asyncio.Queue()    # 待 Agent 处理的文本
        self._tts_q: asyncio.Queue = asyncio.Queue()     # 待合成文本 → TTS
        self._tasks: List[asyncio.Task] = []
        self._cfg: Dict[str, Any] = {}
        self._adapter = None

    # ── 能力 / 配置探测 ──────────────────────────────────
    def get_capabilities(self) -> ProviderCapabilities:
        # 本地管线为客户端 VAD 主导：端点由本端判定，打断走 client 模式
        return ProviderCapabilities(
            supports_partial_audio=True,
            supports_interrupt=True,
            supports_duplex=True,
            input_sample_rate=self.input_sample_rate,
            output_sample_rate=self.output_sample_rate,
            server_vad=False,
            semantic_vad=False,
            native_transcription=False,
            manual_vad_only=True,
            barge_in_mode="client",
        )

    def is_configured(self) -> bool:
        """本地管线总开关（关闭时上层应降级到云端 Provider）。"""
        return bool(settings.VOICE_LOCAL_ENABLED)

    # ── 生命周期 ─────────────────────────────────────────
    async def connect(self, session_config: Dict[str, Any]) -> None:
        if not self.is_configured():
            raise RuntimeError("本地管线未启用：请设置 VOICE_LOCAL_ENABLED=1")
        self._cfg = session_config or {}
        self._adapter = AgentRegistry.default()
        self._tasks = [
            self._spawn(self._vad_loop),
            self._spawn(self._stt_loop),
            self._spawn(self._agent_loop),
            self._spawn(self._tts_loop),
        ]
        logger.info("LocalProvider: 四 stage 编排已启动")

    def _spawn(self, factory) -> asyncio.Task:
        """supervisor：单 stage 异常后自动重启。"""

        async def runner() -> None:
            while True:
                try:
                    await factory()
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001 - stage 崩溃需重启而非扩散
                    logger.error(f"LocalProvider stage 异常，重启中: {e}")
                    await asyncio.sleep(0.1)

        return asyncio.create_task(runner())

    # ── Stage 1: VAD ─────────────────────────────────────
    async def _vad_loop(self) -> None:
        from app.duplex.voice.pipeline.vad import SileroVAD

        vad = SileroVAD(threshold=self._cfg.get("vad_threshold"))
        while True:
            chunk = await self._in.get()
            event = vad.feed(chunk)
            if event == "speech_started":
                await self._out.put(ProviderEvent("speech_started", {}))
            elif event == "speech_stopped":
                await self._speech_q.put(None)  # 段结束哨兵
                await self._out.put(ProviderEvent("speech_stopped", {}))
            elif vad.speaking:
                await self._speech_q.put(chunk)

    # ── Stage 2: STT ─────────────────────────────────────
    async def _stt_loop(self) -> None:
        from app.duplex.voice.pipeline.stt import ParaformerStream

        stt = ParaformerStream()
        while True:
            # run() 消费至哨兵后产出一段结果，随后结束；外层循环处理下一段
            async for seg in stt.run(self._speech_q):
                for partial in stt.partials(seg):
                    await self._out.put(
                        ProviderEvent("transcript_delta", {"text": partial, "role": "user"})
                    )
                await self._out.put(
                    ProviderEvent("transcript_final", {"text": stt.final(seg), "role": "user"})
                )
                await self._text_q.put(stt.final(seg))

    # ── Stage 3: Agent ───────────────────────────────────
    async def _agent_loop(self) -> None:
        while True:
            text = await self._text_q.get()
            if not text:
                continue
            await self._out.put(ProviderEvent("response_started", {}))
            if self._adapter is not None:
                try:
                    result = await self._adapter.run_voice_turn(text=text)
                    reply = (result or {}).get("text", "")
                except Exception as e:  # noqa: BLE001 - Agent 失败时本地兜底
                    logger.warning(f"LocalProvider Agent 调用失败: {e}")
                    reply = f"[本地兜底] {text}"
            else:
                reply = f"[本地兜底] {text}"
            await self._tts_q.put(reply)

    # ── Stage 4: TTS ─────────────────────────────────────
    async def _tts_loop(self) -> None:
        from app.duplex.voice.pipeline.tts import CosyVoice2

        tts = CosyVoice2()
        while True:
            text = await self._tts_q.get()
            for wav in tts.stream(text):
                await self._out.put(ProviderEvent("audio_delta", {"audio": wav}))

    # ── I/O ──────────────────────────────────────────────
    async def send_audio(self, pcm_data: bytes) -> None:
        await self._in.put(pcm_data)

    async def send_text(self, text: str) -> None:
        await self._text_q.put(text)

    async def configure_session(self, **kwargs) -> None:
        self._cfg.update(kwargs)

    async def events(self) -> AsyncGenerator[ProviderEvent, None]:
        while True:
            yield await self._out.get()

    async def close(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks = []


# 自注册到 ProviderRegistry
from app.duplex.voice.providers.registry import ProviderRegistry
ProviderRegistry.register(LocalProvider)
