"""T24: 本地管线各 stage 单测（VAD 阈值 / STT partial 粒度 / TTS 首包）。

无需真实模型：VAD 通过覆盖 `_infer` 注入概率；STT/TTS 走降级路径。
"""
import asyncio
import struct

import pytest

from app.duplex.voice.pipeline.stt import ParaformerStream
from app.duplex.voice.pipeline.tts import CosyVoice2
from app.duplex.voice.pipeline.vad import SileroVAD


class StubVAD(SileroVAD):
    """注入固定概率序列，便于测试状态机。"""

    def __init__(self, probs, **kwargs):
        super().__init__(**kwargs)
        self._probs = list(probs)
        self.calls = 0

    def _infer(self, pcm):
        self.calls += 1
        return self._probs.pop(0) if self._probs else 0.0


def _chunk(ms=30, value=0, sample_rate=16000):
    n = int(sample_rate * ms / 1000)
    return struct.pack(f"<{n}h", *([value] * n))


# ── VAD ─────────────────────────────────────────────────


def test_vad_below_threshold_no_event():
    vad = StubVAD([0.1, 0.2], threshold=0.55)
    assert vad.feed(_chunk()) is None
    assert vad.feed(_chunk()) is None
    assert vad.speaking is False


def test_vad_above_threshold_starts_speech():
    vad = StubVAD([0.9], threshold=0.55)
    assert vad.feed(_chunk()) == "speech_started"
    assert vad.speaking is True


def test_vad_hysteresis_requires_min_silence():
    """说话中短时间静音不应立刻判定结束（迟滞）。"""
    vad = StubVAD([0.9, 0.0, 0.0], threshold=0.55, min_silence_ms=300)
    assert vad.feed(_chunk(ms=30)) == "speech_started"
    # 30ms < 300ms → 仍视为说话中
    assert vad.feed(_chunk(ms=30)) is None
    assert vad.feed(_chunk(ms=30)) is None
    assert vad.speaking is True


def test_vad_stops_after_min_silence():
    vad = StubVAD([0.9] + [0.0] * 12, threshold=0.55, min_silence_ms=300)
    assert vad.feed(_chunk(ms=30)) == "speech_started"
    result = None
    for _ in range(12):
        r = vad.feed(_chunk(ms=30))
        if r:
            result = r
            break
    assert result == "speech_stopped"
    assert vad.speaking is False


def test_vad_reset():
    vad = StubVAD([0.9], threshold=0.55)
    vad.feed(_chunk())
    vad.reset()
    assert vad.speaking is False


def test_vad_energy_fallback_on_silence():
    """能量法兜底：全零音频概率应远低于阈值。"""
    vad = SileroVAD(threshold=0.55)
    assert vad._infer(_chunk(value=0)) < 0.55


def test_vad_energy_fallback_on_loud():
    """能量法兜底：响亮音频概率应高于阈值。"""
    vad = SileroVAD(threshold=0.55)
    assert vad._infer(_chunk(value=20000)) >= 0.55


# ── STT ─────────────────────────────────────────────────


def test_stt_partials_respect_interval():
    stt = ParaformerStream(partial_interval_chars=4)
    seg = {"final": "abcdefghij", "chunks": []}
    parts = stt.partials(seg)
    assert parts == ["abcd", "efgh", "ij"]
    assert stt.final(seg) == "abcdefghij"


def test_stt_partials_empty_text():
    stt = ParaformerStream()
    assert stt.partials({"final": ""}) == []
    assert stt.final({}) == ""


def test_stt_run_emits_segment_on_sentinel():
    async def run():
        q = asyncio.Queue()
        stt = ParaformerStream()
        await q.put(b"aaaa")
        await q.put(None)  # 段结束哨兵
        segs = []
        async for seg in stt.run(q):
            segs.append(seg)
            break  # run() 消费到哨兵后结束
        return segs

    segs = asyncio.run(run())
    assert len(segs) == 1
    assert "final" in segs[0]


# ── TTS ─────────────────────────────────────────────────


def test_tts_stream_yields_per_sentence():
    tts = CosyVoice2()
    chunks = list(tts.stream("你好。请问有什么纠纷？"))
    assert len(chunks) == 2  # 按句号/问号切分


def test_tts_first_packet_non_empty():
    tts = CosyVoice2()
    first = next(iter(tts.stream("你好。")))
    assert isinstance(first, bytes)
    assert len(first) > 0


def test_tts_silence_scales_with_text_length():
    """无模型时输出静音；文本越长音频越长。"""
    tts = CosyVoice2()
    short = next(iter(tts.stream("短。")))
    long = next(iter(tts.stream("这是一句比较长的话" * 5 + "。")))
    assert len(long) > len(short)
