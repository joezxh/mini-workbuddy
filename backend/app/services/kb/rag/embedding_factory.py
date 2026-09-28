"""嵌入模型工厂（对齐文档 §5.4 / D5）：统一用 AgentScope 原生 EmbeddingModel。

provider → 原生类映射：
    dashscope        → DashScopeEmbeddingModel（原生协议）
    gpustack / nvidia → OpenAIEmbeddingModel（OpenAI 兼容协议）

dimensions 契约层必填，并与 kb_collection.dimensions 强校验（D19）。
"""
from __future__ import annotations

from dataclasses import dataclass

from agentscope.embedding import (
    DashScopeEmbeddingModel,
    EmbeddingModelBase,
    OpenAIEmbeddingModel,
)

from app.services.kb.embedding_config import resolve_embedding_config


@dataclass(frozen=True)
class EmbeddingSettings:
    provider: str
    model: str
    dimensions: int


def build_embedding_model(
    cfg: EmbeddingSettings | None = None, *, provider: str | None = None
) -> EmbeddingModelBase:
    """按 provider 构造原生嵌入模型；不支持的 provider 显式失败。"""
    resolved = resolve_embedding_config(provider)
    model_name = cfg.model if cfg else resolved.model
    dimensions = cfg.dimensions if cfg else resolved.dimension
    if not dimensions:
        raise ValueError("嵌入维度未配置（dimensions 为契约层必填）")

    if resolved.protocol == "dashscope":
        return DashScopeEmbeddingModel(
            api_key=resolved.api_key,
            model=model_name,
            dimensions=dimensions,
        )
    # openai 兼容协议（gpustack / nvidia）
    return OpenAIEmbeddingModel(
        api_key=resolved.api_key,
        model=model_name,
        dimensions=dimensions,
        base_url=resolved.base_url,
    )
