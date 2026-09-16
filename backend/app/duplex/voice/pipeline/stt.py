"""STT stage：Paraformer 2pass（流式 ASR，funasr）。

- 依赖就绪：走 funasr 流式识别
- 未就绪：退化为「占位转写」，保证四 stage 编排可跑通与可测

对外接口：
    run(in_queue)  -> 逐个产出已结束语音段的识别结果（含 partial 序列）
    partials(seg)  -> 该段的中间结果序列（partial 粒度可控）
    final(seg)     -> 该段最终结果
"""
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger

from app.config import settings


class ParaformerStream:
    """Paraformer 2pass 流式识别封装。"""

    def __init__(
        self,
        model: str = "",
        partial_interval_chars: int = 8,
        sample_rate: int = 16000,
    ):
        self.model = model or settings.VOICE_LOCAL_STT_MODEL
        self.partial_interval_chars = max(1, partial_interval_chars)
        self.sample_rate = sample_rate
        self._model_obj = None

    def available(self) -> bool:
        try:
            import funasr  # noqa: F401
        except ImportError:
            return False
        return bool(self.model)

    def _load(self):
        if self._model_obj is None:
            from funasr import AutoModel

            self._model_obj = AutoModel(model=self.model)
        return self._model_obj

    def _recognize(self, pcm_chunks: List[bytes]) -> str:
        """对一段完整语音做识别。未就绪时返回占位。"""
        audio = b"".join(pcm_chunks)
        if self.available():
            try:
                m = self._load()
                res = m.generate(input=audio, sample_rate=self.sample_rate)
                if res:
                    return str(res[0].get("text", "") or "")
                return ""
            except Exception as e:  # noqa: BLE001 - 识别失败降级为占位
                logger.warning(f"Paraformer 识别失败: {e}")
        # 退化：无识别能力时给出可辨识的占位转写
        return f"[本地转写占位 {len(audio)}B]"

    async def run(
        self, in_queue: "asyncio.Queue[bytes]",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """消费音频块队列，产出 {'final': str, 'chunks': [...]} 段结果。"""
        import asyncio

        buffer: List[bytes] = []
        while True:
            chunk = await in_queue.get()
            if chunk is None:  # 结束哨兵
                if buffer:
                    yield {"final": self._recognize(buffer), "chunks": buffer}
                    buffer = []
                return
            buffer.append(chunk)

    def partials(self, seg: Dict[str, Any]) -> List[str]:
        """把最终结果切成若干中间结果，模拟流式 partial 粒度。"""
        text = seg.get("final", "") or ""
        step = self.partial_interval_chars
        if not text:
            return []
        return [text[i : i + step] for i in range(0, len(text), step)]

    def final(self, seg: Dict[str, Any]) -> str:
        return seg.get("final", "") or ""
