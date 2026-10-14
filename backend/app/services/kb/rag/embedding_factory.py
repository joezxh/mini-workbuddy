"""嵌入模型工厂（对齐文档 §5.4 / D5）：统一用 AgentScope 原生 EmbeddingModel。

provider → 原生类映射：
    dashscope        → DashScopeEmbeddingModel（原生协议）
    gpustack / nvidia → OpenAIEmbeddingModel（OpenAI 兼容协议）

dimensions 契约层必填，并与 kb_collection.dimensions 强校验（D19）。
"""
from __future__ import annotations

from dataclasses import dataclass

from agentscope.credential import DashScopeCredential, OpenAICredential
from agentscope.embedding import DashScopeEmbeddingModel, EmbeddingModelBase

from app.services.kb.rag.adaptive_embedding import AdaptiveOpenAIEmbeddingModel
from app.services.kb.embedding_config import (
    normalize_openai_base_url,
    resolve_embedding_config_with_fallback,
)


@dataclass(frozen=True)
class EmbeddingSettings:
    provider: str
    model: str
    dimensions: int


def build_embedding_model(
    cfg: EmbeddingSettings | None = None, *, provider: str | None = None
) -> EmbeddingModelBase:
    """按 provider 构造原生嵌入模型；不支持的 provider 显式失败。

    provider 取值优先显式入参，其次 ``cfg.provider``（设置面板落库值），
    最后才是全局默认——否则选了 dashscope 也仍走默认 provider。
    """
    # 未显式指定 provider 时：模型管理默认向量化模型优先，环境变量配置兜底
    resolved = resolve_embedding_config_with_fallback(
        provider or (cfg.provider if cfg else None)
    )
    model_name = cfg.model if cfg else resolved.model
    dimensions = cfg.dimensions if cfg else resolved.dimension
    if not dimensions:
        raise ValueError("嵌入维度未配置（dimensions 为契约层必填）")

    # AgentScope 2.0.8 的 EmbeddingModel 收 ``credential`` 对象而非裸 api_key/base_url
    if resolved.protocol == "dashscope":
        return DashScopeEmbeddingModel(
            credential=DashScopeCredential(api_key=resolved.api_key),
            model=model_name,
            dimensions=dimensions,
        )
    # openai 兼容协议（gpustack / nvidia / 模型管理）；base_url 属 credential
    # 统一规范化 /v1；本地无鉴权服务用占位 key（OpenAI SDK 拒绝空 api_key）
    # 用自适应子类：服务端不接受 dimensions 参数时自动降级重试
    return AdaptiveOpenAIEmbeddingModel(
        credential=OpenAICredential(
            api_key=resolved.api_key or "not-required",
            base_url=normalize_openai_base_url(resolved.base_url),
        ),
        model=model_name,
        dimensions=dimensions,
    )
