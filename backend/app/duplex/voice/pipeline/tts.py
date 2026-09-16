"""TTS stage：CosyVoice2（流式语音合成）。

- 依赖就绪：走 CosyVoice2 流式合成，按句/按块产出 wav
- 未就绪：产出静音 wav 占位（保证编排可跑通与首包可测）
"""
from typing import Iterator, List

from loguru import logger

from app.config import settings


class CosyVoice2:
    """CosyVoice2 流式 TTS 封装。"""

    def __init__(self, model: str = "", speed: float = 0.0, sample_rate: int = 24000):
        self.model = model or settings.VOICE_LOCAL_TTS_MODEL
        self.speed = speed or settings.VOICE_LOCAL_TTS_SPEED
        self.sample_rate = sample_rate
        self._tts = None

    def available(self) -> bool:
        try:
            import cosyvoice  # noqa: F401
        except ImportError:
            return False
        return bool(self.model)

    def _load(self):
        if self._tts is None:
            from cosyvoice.cli.cosyvoice import CosyVoice2 as _Impl

            self._tts = _Impl(self.model)
        return self._tts

    def _split(self, text: str) -> List[str]:
        """按标点切句，便于流式逐句合成（降低首包延迟）。"""
        import re

        parts = re.split(r"(?<=[。！？；.!?;])", text or "")
        return [p for p in parts if p.strip()]

    def stream(self, text: str) -> Iterator[bytes]:
        """流式产出 wav 音频块（bytes）。"""
        for sentence in self._split(text):
            yield self._synth(sentence)

    def _synth(self, sentence: str) -> bytes:
        if self.available():
            try:
                tts = self._load()
                chunks = []
                for out in tts.inference_zero_shot(sentence, "", "", speed=self.speed):
                    chunks.append(out["tts_speech"].numpy().tobytes())
                return b"".join(chunks)
            except Exception as e:  # noqa: BLE001 - 合成失败降级为静音
                logger.warning(f"CosyVoice2 合成失败: {e}")
        return self._silence(sentence)

    def _silence(self, sentence: str) -> bytes:
        """按句长产出等时长静音 wav（16bit PCM），用于无模型时跑通编排。"""
        import struct

        # 经验值：每字约 0.25s
        seconds = max(0.2, len(sentence or "") * 0.25)
        n = int(seconds * self.sample_rate)
        return b"".join(struct.pack("<h", 0) for _ in range(n))
