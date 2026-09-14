"""VAD stage：Silero VAD（onnxruntime 推理）。

- 依赖与模型就绪：走 onnxruntime 推理真实概率
- 未就绪：退化为基于能量的简易 VAD（保证管线可跑通，精度不及 Silero）

状态机带「最小静音时长」迟滞，避免短暂停顿被误判为说话结束。
"""
from typing import Optional

from loguru import logger

from app.config import settings


class SileroVAD:
    """Silero VAD 封装。"""

    def __init__(
        self,
        threshold: Optional[float] = None,
        sample_rate: int = 16000,
        min_silence_ms: int = 300,
        model_path: str = "",
    ):
        self.threshold = threshold if threshold is not None else settings.VOICE_VAD_THRESHOLD
        self.sample_rate = sample_rate
        self.min_silence_ms = min_silence_ms
        self.model_path = model_path or settings.VOICE_LOCAL_VAD_MODEL
        self._session = None
        self._speaking = False
        self._silence_ms = 0.0

    # ── 可用性 ──────────────────────────────────────────
    def available(self) -> bool:
        """onnxruntime 与模型文件均就绪才算可用。"""
        import os

        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return False
        return bool(self.model_path) and os.path.exists(self.model_path)

    # ── 推理 ────────────────────────────────────────────
    def _load(self):
        if self._session is None:
            import onnxruntime

            self._session = onnxruntime.InferenceSession(self.model_path)
        return self._session

    def _infer(self, pcm: bytes) -> float:
        """返回 0..1 语音概率。测试可覆盖此方法注入概率。"""
        if self.available():
            try:
                sess = self._load()
                import numpy as np

                x = np.frombuffer(pcm, dtype=np.int16).astype("float32") / 32768.0
                x = x.reshape(1, -1)
                out = sess.run(None, {"input": x})
                return float(out[0].reshape(-1)[0])
            except Exception as e:  # noqa: BLE001 - 推理失败退化为能量法
                logger.warning(f"SileroVAD 推理失败，退化为能量 VAD: {e}")
        return self._energy(pcm)

    @staticmethod
    def _energy(pcm: bytes) -> float:
        """能量法兜底：归一化 RMS。"""
        if not pcm:
            return 0.0
        import array

        arr = array.array("h")
        try:
            arr.frombytes(pcm[: len(pcm) // 2 * 2])
        except (ValueError, TypeError):
            return 0.0
        if not arr:
            return 0.0
        rms = (sum((v / 32768.0) ** 2 for v in arr) / len(arr)) ** 0.5
        return min(1.0, rms * 6.0)  # 经验放大系数

    # ── 状态机 ──────────────────────────────────────────
    def feed(self, pcm: bytes) -> Optional[str]:
        """喂入一个音频块，返回 None / 'speech_started' / 'speech_stopped'。"""
        prob = self._infer(pcm)
        dur_ms = (len(pcm) / 2) / self.sample_rate * 1000

        if prob >= self.threshold:
            self._silence_ms = 0.0
            if not self._speaking:
                self._speaking = True
                return "speech_started"
            return None

        if self._speaking:
            self._silence_ms += dur_ms
            if self._silence_ms >= self.min_silence_ms:
                self._speaking = False
                self._silence_ms = 0.0
                return "speech_stopped"
        return None

    @property
    def speaking(self) -> bool:
        return self._speaking

    def reset(self) -> None:
        self._speaking = False
        self._silence_ms = 0.0
