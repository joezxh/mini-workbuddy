"""嵌入模型工厂（对齐文档 §5.4 / D5）：构造契约。

AgentScope 2.0.8 的 ``*EmbeddingModel.__init__`` 收 ``credential`` 对象，
不收裸 ``api_key``/``base_url``——曾按后者构造导致 TypeError，使摄取/升级/
重灌/分段编辑全部失败，故此处卡口（不联网，只构造不调用）。
"""
from __future__ import annotations

import pytest
from agentscope.embedding import (
    DashScopeEmbeddingModel,
    OpenAIEmbeddingModel,
)

from app.services.kb.rag.embedding_factory import (
    EmbeddingSettings,
    build_embedding_model,
)


def test_build_openai_compatible_model():
    model = build_embedding_model(
        EmbeddingSettings(provider="gpustack", model="qwen3-embedding", dimensions=1024)
    )
    assert isinstance(model, OpenAIEmbeddingModel)


def test_build_dashscope_model():
    model = build_embedding_model(
        EmbeddingSettings(provider="dashscope", model="text-embedding-v4", dimensions=1024)
    )
    assert isinstance(model, DashScopeEmbeddingModel)


def test_dimensions_are_mandatory():
    """维度是契约层必填（D19 强校验前置）。"""
    from app.services.kb.embedding_config import resolve_embedding_config

    cfg = resolve_embedding_config(None)
    with pytest.raises(ValueError, match="维度"):
        build_embedding_model(
            EmbeddingSettings(provider=cfg.provider, model=cfg.model, dimensions=0)
        )
