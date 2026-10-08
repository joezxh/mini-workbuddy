"""economy 独立关键词检索服务（spec §10.2 / D11 / 验收标准 AC7）。

``index_mode=economy`` 的知识库**不消耗任何 embedding**：摄取时 ``PgVectorStore``
写 NULL 向量（D11）；检索也不走 ``KnowledgeBase`` / ``RAGMiddleware``（后者会强制
对 query 做嵌入），而是本模块独立执行 pg_trgm（gin_trgm GIN 索引）加速的中文子串
召回——与 ``app/services/kb/pgvector_store.PGVectorStore.hybrid_search`` 的关键词路
一致（本环境 pg_trgm.similarity 对 CJK 文本恒为 0，故用 trigram-GIN 加速的 LIKE
子串召回）。从而 economy 库检索实现真正的零 embedding 消耗。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB

from app.models.kb.kb_segment import KbSegment


def _escape_like(query: str) -> str:
    """转义 LIKE 通配符（% _ \\），保留 ESCAPE '\\' 语义。"""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def economy_search(
    db,
    tenant_id: int,
    collection: str,
    query: str,
    top_k: int = 5,
    metadata_filter: Optional[dict] = None,
    score_threshold: Optional[float] = None,
) -> list[dict]:
    """纯关键词检索，零 embedding（D11）。

    返回与 retrieve 端点一致的形状：``{score, document_id, chunk_index, content, metadata}``。
    ``score`` 越靠前命中（strpos 越小）越高，归一化为 ``1/(1+pos)``。
    """
    if not query or not query.strip():
        return []
    like_pattern = f"%{_escape_like(query)}%"
    pos = func.strpos(KbSegment.content, query)

    stmt = (
        select(
            KbSegment.document_id,
            KbSegment.chunk_index,
            KbSegment.content,
            KbSegment.metadata_.label("metadata"),
            pos.label("pos"),
        )
        .where(
            KbSegment.tenant_id == tenant_id,
            KbSegment.collection == collection,
            KbSegment.content.isnot(None),
            KbSegment.content.like(like_pattern, escape="\\"),
        )
    )
    if metadata_filter:
        stmt = stmt.where(
            KbSegment.metadata_.op("@>")(
                cast(literal(json.dumps(metadata_filter, ensure_ascii=False)), JSONB)
            )
        )
    stmt = stmt.order_by(pos.asc(), func.length(KbSegment.content).asc()).limit(top_k)

    rows = db.execute(stmt).all()
    results: list[dict] = []
    for r in rows:
        p = int(r.pos) if r.pos else 1
        score = round(1.0 / (1 + p), 4)  # 越靠前命中分越高
        results.append({
            "score": score,
            "document_id": r.document_id,
            "chunk_index": r.chunk_index,
            "content": r.content,
            "metadata": r.metadata,
        })
    if score_threshold is not None:
        results = [x for x in results if x["score"] >= score_threshold]
    return results
