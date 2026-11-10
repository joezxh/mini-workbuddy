"""Mock 生成器 — 无真实服务时的完整链路（spec docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.4）。

事件形状与真实 s2s 逐一同构，前端联调不感知 Mock 与真实差异。
"""
import asyncio
import io
import math
import struct
import wave
from typing import AsyncIterator, Awaitable, Callable, Dict, List

SAMPLE_RATE = 24000


def mock_asr_text(language: str = "auto") -> Dict:
    """样例转写文本（language 回显调用方传值）。"""
    return {"text": "你好，请帮我查看今天下午三点的会议安排。", "language": language or "zh"}


def mock_tts_wav_bytes(duration_s: float = 1.5) -> bytes:
    """440/660Hz 交替正弦提示音，带 20ms 起音 + 50ms 收尾包络（24kHz mono 16bit WAV）。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        n = int(SAMPLE_RATE * duration_s)
        for i in range(n):
            t = i / SAMPLE_RATE
            freq = 440.0 if (t % 0.5) < 0.25 else 660.0
            env = min(1.0, t / 0.02, max(0.0, (duration_s - t) / 0.05))
            v = int(0.35 * 32767 * env * math.sin(2 * math.pi * freq * t))
            w.writeframesraw(struct.pack("<h", v))
    return buf.getvalue()


class MockRealtimeScript:
    """扮演 s2s /v1/realtime 服务端：消费客户端事件，回放一轮对话脚本。

    触发规则：append 累计 >= 19200 字节（≈0.6s@16k/16bit）或收到
    input_audio_buffer.commit（有累计音频时兜底）/ response.create 时开始一轮；
    response.cancel → 立即 response.done(status=cancelled)。
    """

    REPLIES: List[str] = [
        "今天下午三点有一个项目评审会，地点在三楼会议室。",
        "你今天完成了 8 项待办中的 5 项，还剩 3 项。",
        "好的，我记下了，稍后会提醒你。",
    ]
    _TRIGGER_BYTES = 19200
    _DELTA_CHUNKS = 8  # 每轮 audio.delta 片数

    def __init__(self) -> None:
        self._accumulated = 0
        self._turn = 0

    async def run(
        self,
        send: Callable[[Dict], Awaitable],
        client_events: AsyncIterator[Dict],
    ) -> None:
        await send({"type": "session.created",
                    "session": {"id": "mock-session", "voice": "Aiden"}})
        cancelled = False
        async for evt in client_events:
            etype = evt.get("type", "")
            if etype == "input_audio_buffer.append":
                self._accumulated += len(evt.get("audio", ""))
            elif etype == "response.cancel":
                await send({"type": "response.done",
                            "response": {"status": "cancelled"}})
                cancelled = True
                continue
            if etype in ("input_audio_buffer.append", "input_audio_buffer.commit", "response.create"):
                triggered = self._accumulated >= self._TRIGGER_BYTES or (
                    etype != "input_audio_buffer.append" and self._accumulated > 0
                )
                if triggered:
                    self._accumulated = 0
                    await self._one_turn(send, cancelled)
                    cancelled = False

    async def _one_turn(self, send: Callable[[Dict], Awaitable], cancelled: bool) -> None:
        text = self.REPLIES[self._turn % len(self.REPLIES)]
        self._turn += 1
        await send({"type": "input_audio_buffer.speech_started"})
        await asyncio.sleep(0.05)
        await send({"type": "input_audio_buffer.speech_stopped"})
        await send({"type": "conversation.item.input_audio_transcription.completed",
                    "transcript": "现在几点了？顺便看看我的日程。"})
        if cancelled:
            await send({"type": "response.done", "response": {"status": "cancelled"}})
            return
        await send({"type": "response.created",
                    "response": {"id": f"mock-resp-{self._turn}"}})
        await send({"type": "response.audio_transcription.delta", "delta": text})
        chunk = "AAAA"  # base64(静音 PCM16)
        for _ in range(self._DELTA_CHUNKS):
            await send({"type": "response.audio.delta", "delta": chunk})
            await asyncio.sleep(0.02)
        await send({"type": "response.audio.done"})
        await send({"type": "response.done", "response": {"status": "completed"}})
