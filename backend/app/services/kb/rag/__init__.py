"""原生 RAG 装配层（AgentScope 2.0.8）：无自研编排，只做装配。

模块职责（对齐文档 §4）：
    pg_vector_store   唯一自定义扩展（VectorStoreBase 子类）
    embedding_factory 原生 EmbeddingModel 构造
    chunker_factory   原生 chunker_type 注册表 + Q&A/表格行直构 Chunk
    knowledge_factory KnowledgeBase 句柄装配（含 store 生命周期）
    rag_middleware    RAGMiddleware 装配 + 工具收集
    parser_factory    原生 *Parser 按媒体类型选择

导入是**惰性**的（PEP 562 ``__getattr__``）
--------------------------------------------------
以前这里在包导入期就把 embedding_factory 拉起来，而它 → adaptive_embedding →
``import openai`` → aiohttp 是一条 **约 2 s** 的重链；`kb.py` 只要引用
``rag.chunker_factory`` 就会连带触发整条链，让进程冷启动与每次 ``--reload``
（Windows 下走 multiprocessing spawn，全量重 import）都白付这笔钱。

改成按需转发后，``from app.services.kb.rag import build_embedding_model``
一类的既有写法**照旧可用**（首次访问时才真正 import 子模块）；仓内所有引用都
写成 ``from app.services.kb.rag.<子模块> import ...``，不依赖旧的 eager 副作用。
"""
from __future__ import annotations

import importlib
from typing import Any

# 对外名 → (目标模块, 属性)。模块可用相对名（以 ``.`` 开头，相对本包解析）。
_EXPORTS: dict[str, tuple[str, str]] = {
    # 解析器选择器不在本包内，走绝对名
    "select_parser": ("app.services.kb.parser_selector", "select_parser"),
    "supported_media_types": (
        "app.services.kb.parser_selector", "supported_media_types"
    ),
    "CHUNKER_REGISTRY": (".chunker_factory", "CHUNKER_REGISTRY"),
    "build_chunker": (".chunker_factory", "build_chunker"),
    "build_qa_chunks": (".chunker_factory", "build_qa_chunks"),
    "build_table_row_chunks": (".chunker_factory", "build_table_row_chunks"),
    "chunker_schemas": (".chunker_factory", "chunker_schemas"),
    "EmbeddingSettings": (".embedding_factory", "EmbeddingSettings"),
    "build_embedding_model": (".embedding_factory", "build_embedding_model"),
    "knowledge_base": (".knowledge_factory", "knowledge_base"),
    "PgVectorStore": (".pg_vector_store", "PgVectorStore"),
    "build_rag_middleware": (".rag_middleware", "build_rag_middleware"),
    "collect_rag_tools": (".rag_middleware", "collect_rag_tools"),
    "rag_parameters_schema": (".rag_middleware", "rag_parameters_schema"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:  # noqa: ANN401 - 转发任意子模块属性
    """按需导入子模块并取出被转发的名字（首次访问后才进 ``sys.modules``）。"""
    target = _EXPORTS.get(name)
    if target is None:
        # 兼容 ``from app.services.kb.rag import chunker_factory`` 这类**子模块**访问：
        # 常规导入机制本身能处理，这里兜住显式 getattr（如 ``rag.content_service``）。
        try:
            return importlib.import_module(f".{name}", __package__)
        except ImportError:
            raise AttributeError(
                f"module {__name__!r} has no attribute {name!r}"
            ) from None
    module_name, attr = target
    return getattr(importlib.import_module(module_name, __package__), attr)


def __dir__() -> list[str]:
    """让 ``dir(rag)``/补全仍能看到转发名（不必先触发 import）。"""
    return __all__
