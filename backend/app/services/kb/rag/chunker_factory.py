"""切块器工厂（对齐文档 §5.3 / D6/D7）：键必须是原生 chunker_type。

自定义子类须遵守 ChunkerBase 四条约定：不跨 Section、DataBlock 透传、
chunk_index 连续、total_chunks 一致。
"""
from __future__ import annotations

from agentscope.rag import ApproxTokenChunker, ChunkerBase
from agentscope.rag import Chunk, Section
from agentscope.message import DataBlock, TextBlock

from app.services.kb.parent_child_chunker import ParentChildChunker
from app.services.kb.qa_chunker import QaChunker

CHUNKER_REGISTRY: dict[str, type[ChunkerBase]] = {
    ApproxTokenChunker.chunker_type: ApproxTokenChunker,
    QaChunker.chunker_type: QaChunker,
    ParentChildChunker.chunker_type: ParentChildChunker,
}


def build_chunker(chunker_type: str, params: dict | None = None) -> ChunkerBase:
    cls = CHUNKER_REGISTRY.get(chunker_type)
    if cls is None:
        raise ValueError(f"未知 chunker_type: {chunker_type!r}，可选 {sorted(CHUNKER_REGISTRY)}")
    return cls(parameters=cls.Parameters(**(params or {})))


def chunker_schemas() -> list[dict]:
    """前端创建向导直接消费的 JSON Schema（D6）。"""
    return [
        {"chunker_type": t, "parameters_schema": cls.Parameters.model_json_schema()}
        for t, cls in CHUNKER_REGISTRY.items()
    ]


def build_qa_chunks(pairs: list[dict], source: str = "qa-import") -> list[Chunk]:
    """Q&A 形态不经 parser/chunker（D15），直接构造 Chunk。"""
    chunks: list[Chunk] = []
    for i, pair in enumerate(pairs):
        chunks.append(Chunk(
            content=TextBlock(text=pair.get("question", "")),
            source=source,
            chunk_index=i,
            total_chunks=len(pairs),
            metadata={
                "chunk_type": "qa",
                "answer": pair.get("answer"),
                "tags": pair.get("tags") or [],
                "enabled": True,
            },
        ))
    return chunks


def build_table_row_chunks(rows: list[dict], embed_field: str, source: str = "table-import") -> list[Chunk]:
    """表格行形态：embed_field 列作为被嵌入内容，其余列进 metadata（D15）。"""
    chunks: list[Chunk] = []
    for i, row in enumerate(rows):
        content = str(row.get(embed_field, ""))
        meta = {k: v for k, v in row.items() if k != embed_field}
        meta["chunk_type"] = "table_row"
        chunks.append(Chunk(
            content=TextBlock(text=content),
            source=source,
            chunk_index=i,
            total_chunks=len(rows),
            metadata=meta,
        ))
    return chunks
