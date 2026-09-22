# Task 1 Brief: BrowserTransport（AgentScope 传输桥）

计划: `docs/superpowers/plans/2026-09-20-agentscope-voice-s2s.md`（AgentScope 内核替换语音 Provider）
规格: `docs/superpowers/specs/2026-09-20-agentscope-voice-s2s-design.md`

> **重要约定**：任务中出现的所有 agentscope API 签名均已对照本地安装包（`backend/.venv/Lib/site-packages/agentscope`，版本 2.0.8）实测验证，**以本简报与计划头部「已验证 API 事实」为准，勿查官方文档或 GitHub main 分支**（它们超前于发布版）。

---

**Files:**
- Create: `backend/app/duplex/voice/providers/agentscope_transport.py`
- Test: `backend/tests/duplex/voice/test_agentscope_transport.py`

- [ ] **Step 1: 写失败测试**

```python
"""BrowserTransport 单测：上行桥接、下行水位记账、打断清零、重采样。"""
import asyncio
import pytest

from app.duplex.voice.providers.agentscope_transport import BrowserTransport


def _make_transport(in_rate=16000, out_rate=24000):
    uplink: asyncio.Queue = asyncio.Queue()
    events: asyncio.Queue = asyncio.Queue()
    t = BrowserTransport(input_sample_rate=in_rate, output_sample_rate=out_rate,
                         uplink=uplink, downlink_events=events)
    return t, uplink, events


@pytest.mark.asyncio
async def test_submit_audio_yields_audio_frame():
    t, uplink, _ = _make_transport()
    await t.start()
    t.submit_audio(b"\x01\x00" * 160)
    frame = await asyncio.wait_for(uplink.get(), timeout=1)
    assert type(frame).__name__ == "AudioFrame"
    assert frame.pcm == b"\x01\x00" * 160


@pytest.mark.asyncio
async def test_send_audio_updates_playout_watermark_and_emits():
    t, _, events = _make_transport()
    await t.start()
    await t.send_audio(b"\x00\x00" * 24000, item_id="item_1")  # 1s @24k
    pos = t.playout()
    assert pos.item_id == "item_1"
    assert pos.played_ms == 1000
    ev = events.get_nowait()
    assert ev.type == "audio_delta"
    assert ev.data["audio"] == b"\x00\x00" * 24000


@pytest.mark.asyncio
async def test_clear_audio_reports_and_resets():
    t, _, events = _make_transport()
    await t.start()
    await t.send_audio(b"\x00\x00" * 12000, item_id="item_1")  # 500ms
    pos = await t.clear_audio()
    assert pos.item_id == "item_1"
    assert pos.played_ms == 500
    assert t.playout().played_ms == 0
    types = [events.get_nowait().type for _ in range(events.qsize())]
    assert "playback_cancelled" in types


@pytest.mark.asyncio
async def test_resample_16k_to_24k():
    t, uplink, _ = _make_transport(in_rate=24000, out_rate=24000)
    await t.start()
    t.submit_resampled(b"\x00\x00" * 16000, source_rate=16000)
    frame = await asyncio.wait_for(uplink.get(), timeout=1)
    assert len(frame.pcm) == 48000  # 24000 样本 × 2B


@pytest.mark.asyncio
async def test_new_item_resets_watermark():
    t, _, _ = _make_transport()
    await t.start()
    await t.send_audio(b"\x00\x00" * 24000, item_id="a")
    await t.send_audio(b"\x00\x00" * 4800, item_id="b")  # 200ms
    assert t.playout().item_id == "b"
    assert t.playout().played_ms == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_agentscope_transport.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 实现 agentscope_transport.py**

```python
"""浏览器侧 TransportBase 桥接（协议 v2 网关 ⇄ AgentScope RealtimeAgent，spec §2.2）。

- 上行：网关 PCM/控制帧 → AudioFrame/ControlFrame（限深 100 块，满丢最旧）
- 下行：agent 音频 → 事件队列（audio_delta）+ 发送水位记账（服务端模拟 PlayoutPosition）
- clear_audio：返回水位并清零（barge-in truncate 事实来源），并产出 playback_cancelled
- 采样率契约：transport.input_sample_rate 必须等于模型上行率；
  浏览器 16k 与模型 24k 不一致时经 submit_resampled 线性插值重采样。
"""
import asyncio
import time
from typing import AsyncIterator

from agentscope.realtime import (
    AudioFrame, ControlFrame, ControlFrameType, PlayoutPosition, TransportBase,
)

from app.duplex.voice.providers.base import ProviderEvent

_UPLINK_MAX = 100


class BrowserTransport(TransportBase):
    """桥接浏览器 WebSocket 与 RealtimeAgent 的 TransportBase 实现。"""

    def __init__(self, input_sample_rate: int, output_sample_rate: int,
                 uplink: asyncio.Queue, downlink_events: asyncio.Queue) -> None:
        self.input_sample_rate = input_sample_rate
        self.output_sample_rate = output_sample_rate
        self._uplink = uplink
        self._events = downlink_events
        self._running = False
        self._item_id = ""
        self._played_samples = 0
        self._first_played_at: float | None = None

    async def start(self) -> None:
        self._running = True

    async def close(self) -> None:
        self._running = False

    async def incoming(self) -> AsyncIterator[AudioFrame | ControlFrame]:
        while True:
            frame = await self._uplink.get()
            if frame is None:  # 关闭哨兵
                return
            yield frame

    # ---- 上行入口（由 Provider 调用）----

    def submit_audio(self, pcm: bytes) -> None:
        self._put_uplink(AudioFrame(pcm=pcm))

    def submit_resampled(self, pcm: bytes, source_rate: int) -> None:
        if source_rate != self.input_sample_rate:
            pcm = _resample_pcm16(pcm, source_rate, self.input_sample_rate)
        self._put_uplink(AudioFrame(pcm=pcm))

    def submit_text(self, text: str) -> None:
        self._put_uplink(ControlFrame(type=ControlFrameType.TEXT, data={"text": text}))

    def submit_confirm(self, data: dict) -> None:
        self._put_uplink(ControlFrame(type=ControlFrameType.USER_CONFIRM, data=data))

    def submit_interrupt(self) -> None:
        self._put_uplink(ControlFrame(type=ControlFrameType.INTERRUPT, data={}))

    def _put_uplink(self, frame) -> None:
        if not self._running:
            return
        if self._uplink.qsize() >= _UPLINK_MAX:
            try:
                self._uplink.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._uplink.put_nowait(frame)

    def close_uplink(self) -> None:
        self._uplink.put_nowait(None)

    # ---- 下行（agent 调用）----

    async def send_audio(self, pcm: bytes, item_id: str) -> None:
        if item_id != self._item_id:
            self._item_id = item_id
            self._played_samples = 0
            self._first_played_at = time.monotonic()
        self._played_samples += len(pcm) // 2
        await self._events.put(
            ProviderEvent(type="audio_delta", data={"audio": pcm}))

    async def clear_audio(self) -> PlayoutPosition:
        pos = self.playout()
        self._played_samples = 0
        self._first_played_at = None
        await self._events.put(ProviderEvent(
            type="playback_cancelled",
            data={"item_id": pos.item_id, "played_ms": pos.played_ms,
                  "reason": "barge_in"}))
        return pos

    def playout(self) -> PlayoutPosition:
        return PlayoutPosition(
            item_id=self._item_id,
            played_ms=self._played_samples * 1000 // self.output_sample_rate,
            first_played_at=self._first_played_at,
        )


def _resample_pcm16(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """PCM16 单声道线性插值重采样（16k→24k 上行适配）。"""
    if from_rate == to_rate or not pcm:
        return pcm
    import array
    samples = array.array("h")
    samples.frombytes(pcm)
    if len(samples) < 2:
        return pcm
    ratio = from_rate / to_rate
    out_len = int(len(samples) / ratio)
    out = array.array("h", bytes(2 * out_len))
    for i in range(out_len):
        src = i * ratio
        i0 = int(src)
        i1 = min(i0 + 1, len(samples) - 1)
        frac = src - i0
        out[i] = int(samples[i0] * (1 - frac) + samples[i1] * frac)
    return out.tobytes()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_agentscope_transport.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/duplex/voice/providers/agentscope_transport.py backend/tests/duplex/voice/
git commit -m "feat(voice): BrowserTransport 桥接协议v2网关与 AgentScope TransportBase"
```
