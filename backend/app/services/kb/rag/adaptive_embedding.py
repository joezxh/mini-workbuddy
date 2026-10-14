"""自适应 OpenAI 兼容嵌入模型。

部分 OpenAI 兼容服务（例如本地 GPUStack 上的 ``qwen3-vl-embedding-2b``）在请求
携带 ``dimensions`` 时会直接返回 400::

    Model "..." does not support matryoshka representation,
    changing output dimensions will lead to poor results.

而另一类服务（OpenAI 的 ``text-embedding-3-*``）恰恰**需要** ``dimensions``
才能输出指定维度。二者无法从配置区分，故此处子类化 AgentScope 的
``OpenAIEmbeddingModel``：首次命中该类 400 即关闭 ``pass_dimensions`` 并用同一批
输入重试，决策在同一模型实例内只做一次，后续批次直接走降级路径。
"""
from __future__ import annotations

from typing import Any

import openai

from agentscope.embedding import OpenAIEmbeddingModel

_DIMENSION_HINTS = ("matryoshka", "dimension")


def _to_embed_text(item: Any) -> str:
    """把单条 embedding 输入强制降级为字符串。

    OpenAI 兼容的纯文本嵌入端点只接受 ``str`` 或 ``str`` 数组，但多模态文档
    （含图的 PDF/PPTX/docx）的 ``DataBlock`` 图片段会由 chunker 原样透传到此；
    基类仅把 ``TextBlock`` 解包成 ``.text``，``DataBlock`` 仍是对象，直接塞进
    ``input`` 会被服务端拒绝（``'input' field must be a string or an array of
    strings``）。这里把非字符串块降级为可读占位文本，保证切片与向量数量对齐、
    摄取不中断。
    """
    if isinstance(item, str):
        return item or " "
    # TextBlock（基类通常已解包，这里兜底）
    text = getattr(item, "text", None)
    if isinstance(text, str) and text:
        return text
    # DataBlock 等二进制块：用名称/媒体类型占位，避免空串被部分服务端拒绝
    name = getattr(item, "name", None)
    source = getattr(item, "source", None)
    media = getattr(source, "media_type", None) if source is not None else None
    label = name or media or getattr(item, "type", None) or "media"
    return f"[{label}]"


class AdaptiveOpenAIEmbeddingModel(OpenAIEmbeddingModel):
    """对 ``dimensions`` 参数自适应降级的 OpenAI 兼容嵌入模型。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # 同一实例只探测一次：False 表示已确认服务端不接受 dimensions
        self._dimensions_supported = True

    @staticmethod
    def _is_dimension_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(hint in text for hint in _DIMENSION_HINTS)

    async def _call_api(self, inputs: list[str], **kwargs: Any):
        # 纯文本端点仅接受字符串：统一降级非字符串块（DataBlock 图片等）
        inputs = [_to_embed_text(x) for x in inputs]
        if self._dimensions_supported:
            try:
                return await super()._call_api(inputs, **kwargs)
            except openai.BadRequestError as exc:
                if not self._is_dimension_error(exc):
                    raise
                # 服务端不接受 dimensions：关闭该参数后重试同一批
                self._dimensions_supported = False
                self.pass_dimensions = False
        return await super()._call_api(inputs, **kwargs)
