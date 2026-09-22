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
