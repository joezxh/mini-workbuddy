"""音频编解码：float32↔PCM16、Base64、线性重采样。"""
import base64
import numpy as np


def float32_to_pcm16(samples: np.ndarray) -> np.ndarray:
    """float32[-1,1] → int16 PCM（钳位到 [-1,1]，满量程映射到 [-32768,32767]）。"""
    s = np.clip(samples, -1.0, 1.0)
    return (s * 32768).clip(-32768, 32767).astype(np.int16)


def pcm16_to_base64(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("ascii")


def base64_to_pcm16(b64: str) -> bytes:
    return base64.b64decode(b64)


def linear_resample(pcm: np.ndarray, in_rate: int, out_rate: int) -> np.ndarray:
    """简单最近邻重采样（差距分析 §3.4.3 48k→16k 线性插值占位实现）。"""
    if in_rate == out_rate:
        return pcm
    n_out = int(round(len(pcm) * out_rate / in_rate))
    idx = np.linspace(0, len(pcm) - 1, n_out)
    return pcm[idx.astype(np.int32)].astype(pcm.dtype)


def resample_pcm16(pcm_bytes: bytes, in_rate: int, out_rate: int) -> bytes:
    arr = np.frombuffer(pcm_bytes, dtype=np.int16)
    return linear_resample(arr, in_rate, out_rate).tobytes()
