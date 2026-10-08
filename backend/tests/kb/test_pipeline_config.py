"""D8 pipeline_config 规范化（键名对齐 AgentScope 原生参数名）。

验收标准 7：pipeline_config 的 chunker/rag 段能**无转换**地传入
ChunkerBase.Parameters / RAGMiddleware.Parameters。
"""
from __future__ import annotations

import pytest

from app.services.kb.pipeline_config import (
    normalize_pipeline_config,
    pipeline_config_schema,
)


def test_normalize_accepts_native_keys_and_strips_none():
    raw = {
        "parser": {"type": "markdown"},
        "chunker": {"type": "approx_token", "params": {"chunk_size": 64}},
        "embedding": {"provider": "dashscope"},
        "index": {"index_mode": "high_quality"},
        "rag": {"mode": "agentic", "top_k": 4},
        "unknown_extra": 1,
    }
    with pytest.raises(ValueError, match="未知键"):
        normalize_pipeline_config(raw)

    cleaned = normalize_pipeline_config({k: v for k, v in raw.items() if k != "unknown_extra"})
    assert set(cleaned) == {"parser", "chunker", "embedding", "index", "rag"}
    assert cleaned["chunker"]["params"]["chunk_size"] == 64


def test_normalize_empty_returns_none():
    assert normalize_pipeline_config(None) is None
    assert normalize_pipeline_config({}) is None
    assert normalize_pipeline_config({"chunker": None}) is None


def test_normalized_config_drives_chunker_without_transform():
    """D8：原生 chunker 段零转换驱动 build_chunker。"""
    from app.services.kb.rag.chunker_factory import build_chunker

    pc = normalize_pipeline_config({
        "chunker": {"type": "approx_token", "params": {"chunk_size": 32, "overlap": 4}},
    })
    chunker = build_chunker(pc["chunker"]["type"], pc["chunker"]["params"])
    assert chunker.chunker_type == "approx_token"


def test_pipeline_config_schema_exposes_native_keys():
    schema = pipeline_config_schema()
    assert set(schema["keys"]) == {"parser", "chunker", "embedding", "index", "rag"}
    assert schema["chunker"] and schema["rag"]
