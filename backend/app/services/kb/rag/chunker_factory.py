"""切块器工厂（对齐文档 §5.3 / D6/D7）：键必须是原生 chunker_type。

自定义子类须遵守 ChunkerBase 四条约定：不跨 Section、DataBlock 透传、
chunk_index 连续、total_chunks 一致。
"""
from __future__ import annotations

import csv
import io
from typing import Optional

from agentscope.rag import ApproxTokenChunker, ChunkerBase
from agentscope.rag import Chunk, Section
from agentscope.message import DataBlock, TextBlock

from app.services.kb.common_chunkers import (
    FixedSizeChunker,
    MarkdownChunker,
    SentenceChunker,
)
from app.services.kb.parent_child_chunker import ParentChildChunker
from app.services.kb.qa_chunker import QaChunker

CHUNKER_REGISTRY: dict[str, type[ChunkerBase]] = {
    ApproxTokenChunker.chunker_type: ApproxTokenChunker,
    MarkdownChunker.chunker_type: MarkdownChunker,
    SentenceChunker.chunker_type: SentenceChunker,
    FixedSizeChunker.chunker_type: FixedSizeChunker,
    QaChunker.chunker_type: QaChunker,
    ParentChildChunker.chunker_type: ParentChildChunker,
}


def build_chunker(chunker_type: str, params: dict | None = None) -> ChunkerBase:
    cls = CHUNKER_REGISTRY.get(chunker_type)
    if cls is None:
        raise ValueError(f"未知 chunker_type: {chunker_type!r}，可选 {sorted(CHUNKER_REGISTRY)}")
    return cls(parameters=cls.Parameters(**(params or {})))


# 切片方案展示名（前端下拉直接用）
CHUNKER_LABELS: dict[str, str] = {
    ApproxTokenChunker.chunker_type: "按 Token 近似切分（通用）",
    MarkdownChunker.chunker_type: "按 Markdown 标题切分",
    SentenceChunker.chunker_type: "按句子切分（可重叠）",
    FixedSizeChunker.chunker_type: "固定长度切分（可重叠）",
    QaChunker.chunker_type: "问答对切分（结构化数据）",
    ParentChildChunker.chunker_type: "父子分段（小问大答）",
}


def chunker_schemas() -> list[dict]:
    """前端创建向导直接消费的 JSON Schema（D6）。"""
    return [
        {
            "chunker_type": t,
            "label": CHUNKER_LABELS.get(t, t),
            "parameters_schema": cls.Parameters.model_json_schema(),
        }
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


def csv_row_line(values: list) -> str:
    """把一行取值拼成 **CSV 行**（RFC4180：逗号间隔，含逗号/引号/换行自动转义）。

    用于表格知识库「每段一行、遵守 CSV 格式、逗号间隔」的切分内容。
    """
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(
        ["" if v is None else v for v in values]
    )
    return buf.getvalue()


def build_table_row_chunks(
    rows: list[dict],
    embed_fields=None,
    source: str = "table-import",
    *,
    embed_field: Optional[str] = None,
) -> list[Chunk]:
    """表格行形态：**一行一段**，内容为向量化字段组合拼成的 CSV 行（D15）。

    ``embed_fields`` 是集合配置的「向量化字段组合」（1~N 个字段名，顺序即 CSV 列序）：
    * ``content`` = 这些字段值拼成的 CSV 行 —— 与向量化文本一致（向量检索依赖它）；
    * ``metadata`` 存该行全部字段（便于按集合字段定义回显记录、按未选中字段过滤）。

    兼容旧调用：``embed_fields`` 传单个字段名（``str``），或用旧关键字
    ``embed_field="列名"``（单字段组合）。
    """
    names: list[str] = []
    if isinstance(embed_fields, str):
        names = [embed_fields] if embed_fields else []
    else:
        names = [str(name) for name in (embed_fields or []) if name]
    if not names and embed_field:
        names = [embed_field]
    chunks: list[Chunk] = []
    for i, row in enumerate(rows):
        content = csv_row_line([row.get(name, "") for name in names])
        meta = dict(row)
        meta["chunk_type"] = "table_row"
        chunks.append(Chunk(
            content=TextBlock(text=content),
            source=source,
            chunk_index=i,
            total_chunks=len(rows),
            metadata=meta,
        ))
    return chunks
