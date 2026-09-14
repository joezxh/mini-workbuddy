import numpy as np
from app.duplex.voice.audio_codec import (
    float32_to_pcm16, pcm16_to_base64, base64_to_pcm16,
    resample_pcm16, linear_resample,
)

def test_float32_to_pcm16_roundtrip():
    f = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
    pcm = float32_to_pcm16(f)
    assert pcm.dtype == np.int16
    assert int(pcm[-1]) == -32768  # clamp -1.0 → -32768

def test_base64_roundtrip():
    raw = np.array([1, 2, 3, -4], dtype=np.int16).tobytes()
    b64 = pcm16_to_base64(raw)
    assert base64_to_pcm16(b64) == raw

def test_resample_48k_to_16k_length():
    src = np.random.randint(-30000, 30000, size=4800, dtype=np.int16).tobytes()  # 0.1s @48k
    out = resample_pcm16(src, 48000, 16000)
    assert len(out) // 2 == 1600
