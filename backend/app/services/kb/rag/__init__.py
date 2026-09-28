"""原生 RAG 装配层（AgentScope 2.0.8）：无自研编排，只做装配。

模块职责（对齐文档 §4）：
    pg_vector_store   唯一自定义扩展（VectorStoreBase 子类）
    embedding_factory 原生 EmbeddingModel 构造
    chunker_factory   原生 chunker_type 注册表 + Q&A/表格行直构 Chunk
    knowledge_factory KnowledgeBase 句柄装配（含 store 生命周期）
    rag_middleware    RAGMiddleware 装配 + 工具收集
    parser_factory    原生 *Parser 按媒体类型选择
"""
from app.services.kb.parser_selector import select_parser, supported_media_types  # noqa: F401
from app.services.kb.rag.chunker_factory import (  # noqa: F401
    CHUNKER_REGISTRY,
    build_chunker,
    build_qa_chunks,
    build_table_row_chunks,
    chunker_schemas,
)
from app.services.kb.rag.embedding_factory import (  # noqa: F401
    EmbeddingSettings,
    build_embedding_model,
)
from app.services.kb.rag.knowledge_factory import knowledge_base  # noqa: F401
from app.services.kb.rag.pg_vector_store import PgVectorStore  # noqa: F401
from app.services.kb.rag.rag_middleware import (  # noqa: F401
    build_rag_middleware,
    collect_rag_tools,
    rag_parameters_schema,
)
