"""分段详情服务（spec §10.5：Dify 分段详情页）。

单段读写 / 关键词 / 查看引用来源。切片即向量记录（``PgVectorStore`` 直接落
``kb_segment``），故删除行即删除向量，无第二处存储需同步。

约定：
* ``keywords`` 按 D14 以 ``metadata`` 为写入源，再冗余投影到列（供 SQL 过滤）；
* 改文本后**按需重嵌**——high_quality 库必须重嵌，否则索引与内容不一致；
  economy 库与父块（``chunk_type='parent'``，设计上无向量）不嵌。
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from sqlalchemy import func, select

from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment
from app.services.kb.index_mode import _embed_texts, resolve_index_mode

# D14：metadata → 冗余列的投影
_PROJECTIONS = ("chunk_type", "answer", "keywords")
_NON_EMBEDDED_CHUNK_TYPES = ("parent",)


def get_segment(db, tenant_id: int, segment_id: int) -> Optional[KbSegment]:
    return db.execute(
        select(KbSegment).where(
            KbSegment.id == segment_id, KbSegment.tenant_id == tenant_id
        )
    ).scalar_one_or_none()


def _require_segment(db, tenant_id: int, segment_id: int) -> KbSegment:
    seg = get_segment(db, tenant_id, segment_id)
    if seg is None:
        raise ValueError(f"分段不存在: {segment_id}")
    return seg


def _embed_one(text: str, embed_fn: Optional[Callable]) -> list[float]:
    if embed_fn is not None:
        return embed_fn([text])[0]
    from app.services.kb.rag.embedding_factory import build_embedding_model

    model = build_embedding_model(None)

    async def _run() -> list[float]:
        resp = await model([text])
        return list(resp.embeddings)[0]

    return asyncio.run(_run())


def _should_embed(db, seg: KbSegment) -> bool:
    """economy 库与父块不嵌（D11 / §10.2）。"""
    if seg.chunk_type in _NON_EMBEDDED_CHUNK_TYPES:
        return False
    return resolve_index_mode(db, seg.collection) != "economy"


def update_segment(
    db,
    tenant_id: int,
    segment_id: int,
    *,
    content: Optional[str] = None,
    keywords: Optional[list] = None,
    metadata: Optional[dict] = None,
    embed_fn: Optional[Callable] = None,
) -> KbSegment:
    """更新分段内容/关键词/元数据；改文本后按索引模式决定是否重嵌。"""
    seg = _require_segment(db, tenant_id, segment_id)

    if keywords is not None:
        # D14：写入源是 metadata，列只是投影
        seg.metadata_ = {**(seg.metadata_ or {}), "keywords": keywords}
        seg.keywords = keywords
    if metadata:
        seg.metadata_ = {**(seg.metadata_ or {}), **metadata}
        for key in _PROJECTIONS:
            if key in metadata:
                setattr(seg, key, metadata[key])
    if content is not None:
        seg.content = content
        if _should_embed(db, seg):
            seg.embedding = _embed_one(content, embed_fn)

    db.commit()
    return seg


def list_document_segments(
    db,
    tenant_id: int,
    document_id: str,
    *,
    chunk_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """文档内分段列表（spec §10.5），分页 + 按形态过滤。

    分段详情抽屉 / 表格条目列表 / Q&A 列表共用此入口。
    """
    stmt = select(KbSegment).where(
        KbSegment.document_id == document_id,
        KbSegment.tenant_id == tenant_id,
    )
    if chunk_type:
        stmt = stmt.where(KbSegment.chunk_type == chunk_type)

    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    rows = db.execute(
        stmt.order_by(KbSegment.chunk_index)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_segment(s) for s in rows],
    }


def update_keywords(
    db, tenant_id: int, segment_id: int, keywords: list
) -> KbSegment:
    """独立端点：仅改关键词（不重嵌——关键词不参与向量）。"""
    return update_segment(db, tenant_id, segment_id, keywords=keywords)


def reembed_document_segments(db, tenant_id: int, collection: str,
                              document_id: str) -> int:
    """重嵌某文档的全部切片（spec §10.5 reprocess）。

    只覆盖向量，不动文本/结构；父块与 economy 库跳过（D11 / §10.2）。
    """
    rows = db.execute(
        select(KbSegment).where(
            KbSegment.collection == collection,
            KbSegment.tenant_id == tenant_id,
            KbSegment.document_id == document_id,
            KbSegment.chunk_type.notin_(_NON_EMBEDDED_CHUNK_TYPES),
        )
    ).scalars().all()
    if not rows:
        raise ValueError(f"文档 {document_id} 没有可重嵌的切片")
    if resolve_index_mode(db, collection) == "economy":
        raise ValueError("economy 库不做嵌入（D11）；请先升级为 high_quality")

    vectors = _embed_texts([r.content or "" for r in rows], None)
    if len(vectors) != len(rows):
        raise ValueError(f"嵌入数量不匹配: {len(vectors)} vs 切片 {len(rows)}")
    for row, vec in zip(rows, vectors):
        row.embedding = vec
    db.commit()
    return len(rows)


def create_segment(
    db,
    tenant_id: int,
    collection: str,
    document_id: str,
    content: str,
    metadata: Optional[dict] = None,
    embed_fn: Optional[Callable] = None,
) -> KbSegment:
    """新增分段（表格行 / 手工条目）；chunk_index 取该文档 max+1。"""
    meta = dict(metadata or {})
    next_index = db.execute(
        select(func.coalesce(func.max(KbSegment.chunk_index), -1)).where(
            KbSegment.collection == collection,
            KbSegment.document_id == document_id,
            KbSegment.tenant_id == tenant_id,
        )
    ).scalar_one() + 1

    seg = KbSegment(
        tenant_id=tenant_id, collection=collection, document_id=document_id,
        chunk_index=next_index, content=content, metadata_=meta,
    )
    for key in _PROJECTIONS:
        if key in meta:
            setattr(seg, key, meta[key])
    db.add(seg)
    db.flush()
    if _should_embed(db, seg):
        seg.embedding = _embed_one(content, embed_fn)
    db.commit()
    return seg


def delete_segment(db, tenant_id: int, segment_id: int) -> None:
    """删除分段（父块的字块由 DB 外键 ON DELETE CASCADE 连带）。"""
    seg = _require_segment(db, tenant_id, segment_id)
    db.delete(seg)
    db.commit()


def get_citations(db, tenant_id: int, segment_id: int) -> dict:
    """引用来源：所属文档 + 上游父块链 + 下游子块（spec §10.5）。"""
    seg = _require_segment(db, tenant_id, segment_id)

    doc = db.execute(
        select(KbDocument).where(
            KbDocument.uuid_code == seg.document_id,
            KbDocument.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()

    parent = None
    if seg.parent_id:
        parent = db.get(KbSegment, seg.parent_id)
        if parent is not None and parent.tenant_id != tenant_id:
            parent = None  # 跨租户防御

    children = db.execute(
        select(KbSegment).where(
            KbSegment.parent_id == segment_id,
            KbSegment.tenant_id == tenant_id,
        ).order_by(KbSegment.chunk_index)
    ).scalars().all()

    siblings = db.execute(
        select(KbSegment.id).where(
            KbSegment.collection == seg.collection,
            KbSegment.document_id == seg.document_id,
            KbSegment.tenant_id == tenant_id,
        )
    ).scalars().all()

    return {
        "segment": serialize_segment(seg),
        "document": {
            "document_id": doc.uuid_code,
            "name": doc.name,
            "source_type": doc.source_type,
            "status": doc.status,
        } if doc else None,
        "parent": serialize_segment(parent) if parent else None,
        "children": [serialize_segment(c) for c in children],
        "sibling_count": len(siblings),
    }


def serialize_segment(seg: KbSegment) -> dict:
    return {
        "id": seg.id,
        "collection": seg.collection,
        "document_id": seg.document_id,
        "chunk_index": seg.chunk_index,
        "chunk_type": seg.chunk_type,
        "content": seg.content,
        "answer": seg.answer,
        "keywords": seg.keywords,
        "metadata": seg.metadata_,
        "parent_id": seg.parent_id,
        "has_embedding": seg.embedding is not None,
    }
