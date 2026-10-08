"""知识库索引模式解析与升降级（spec §10.2 / §11 / 验收 7）。

collection 命名约定为 ``kb_{knowledge_id}``；据此反查 ``WikiKnowledge.index_mode``。
economy 模式摄取写 NULL 向量、检索走独立关键词服务（D11 / AC7）。

**升级（economy → high_quality）** 触发全量 embedding 回填：按 ``kb_document``
粒度推进，成功文档记进度、失败文档保留 economy 分支可检索并记错误，全部成功
才切换 ``index_mode``（避免半升级状态让已回填文档走不到向量分支）。
**降级（high_quality → economy）** 仅置标志、保留向量，故再次升级无需重嵌。
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from loguru import logger
from sqlalchemy import select

# 父块（父子分段）设计上 embedding 恒为 NULL：只存完整上下文，不参与检索（spec §10.2）
_NON_EMBEDDED_CHUNK_TYPES = ("parent",)

HIGH_QUALITY = "high_quality"
ECONOMY = "economy"


def resolve_knowledge_id(collection: str) -> Optional[int]:
    """``kb_{knowledge_id}`` → knowledge_id；非约定命名返回 None。"""
    if collection and collection.startswith("kb_"):
        try:
            return int(collection[3:])
        except ValueError:
            return None
    return None


def resolve_index_mode(db, collection: str) -> str:
    """返回 collection 所属知识库的索引模式；缺省 high_quality。"""
    kid = resolve_knowledge_id(collection)
    if kid is None:
        return HIGH_QUALITY
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    kn = db.get(WikiKnowledge, kid)
    if kn and kn.index_mode:
        return kn.index_mode
    return HIGH_QUALITY


def _embed_texts(texts: list[str], embed_fn: Optional[Callable]) -> list[list[float]]:
    """按批嵌入；``embed_fn`` 为测试注入点（同步：texts → 向量列表）。"""
    if embed_fn is not None:
        return embed_fn(texts)
    from app.services.kb.rag.embedding_factory import build_embedding_model

    model = build_embedding_model(None)

    async def _run(batch: list[str]):
        resp = await model(batch)
        return list(resp.embeddings)

    out: list[list[float]] = []
    for i in range(0, len(texts), 64):  # 限批，避免单文档过大撑爆请求体
        out.extend(asyncio.run(_run(texts[i:i + 64])))
    return out


def _set_doc_progress(db, uuid_code: str, payload: dict) -> None:
    from app.models.kb.kb_document import KbDocument

    doc = db.execute(
        select(KbDocument).where(KbDocument.uuid_code == uuid_code)
    ).scalar_one_or_none()
    if doc is None:
        return
    meta = dict(doc.meta or {})
    meta["index_upgrade"] = payload
    doc.meta = meta
    db.commit()


def _fill_documents(
    db,
    tenant_id: int,
    collection: str,
    embed_fn: Optional[Callable],
    *,
    only_null: bool,
    progress_key: str,
) -> tuple[int, int, list[dict]]:
    """按文档粒度批量嵌入，返回 ``(filled, doc_count, failed)``。

    ``only_null=True`` 只回填 NULL 向量（升级）；``False`` 覆盖全部（换嵌入模型重灌）。
    单文档失败不中断整批：回滚该文档并记录 ``kb_document.meta[progress_key]``。
    """
    from app.models.kb.kb_collection import KbCollection
    from app.models.kb.kb_document import KbDocument
    from app.models.kb.kb_segment import KbSegment

    coll = db.execute(
        select(KbCollection).where(KbCollection.name == collection)
    ).scalar_one_or_none()
    dimensions = coll.dimensions if coll else None

    docs = db.execute(
        select(KbDocument).where(
            KbDocument.collection == collection,
            KbDocument.tenant_id == tenant_id,
        ).order_by(KbDocument.id)
    ).scalars().all()

    filled = 0
    failed: list[dict] = []
    for doc in docs:
        try:
            stmt = select(KbSegment).where(
                KbSegment.collection == collection,
                KbSegment.tenant_id == tenant_id,
                KbSegment.document_id == doc.uuid_code,
                KbSegment.chunk_type.notin_(_NON_EMBEDDED_CHUNK_TYPES),
            )
            if only_null:
                stmt = stmt.where(KbSegment.embedding.is_(None))
            rows = db.execute(stmt.order_by(KbSegment.chunk_index)).scalars().all()
            if not rows:
                _set_doc_progress(db, doc.uuid_code, {progress_key: {"status": "skipped"}})
                continue

            vectors = _embed_texts([r.content or "" for r in rows], embed_fn)
            if len(vectors) != len(rows):
                raise ValueError(f"嵌入数量不匹配: {len(vectors)} vs 切片 {len(rows)}")
            for row, vec in zip(rows, vectors):
                if dimensions and len(vec) != dimensions:
                    raise ValueError(
                        f"嵌入维度 {len(vec)} 与 collection {dimensions} 不一致（D19）"
                    )
                row.embedding = vec
            db.commit()
            filled += len(rows)
            _set_doc_progress(db, doc.uuid_code,
                              {progress_key: {"status": "done", "filled": len(rows)}})
        except Exception as exc:  # noqa: BLE001 - 单文档失败不中断整批
            db.rollback()
            logger.error(f"[KB 重嵌] 文档 {doc.uuid_code} 失败: {exc}")
            failed.append({"document_id": doc.uuid_code, "error": str(exc)})
            _set_doc_progress(db, doc.uuid_code,
                              {progress_key: {"status": "failed", "error": str(exc)}})
    return filled, len(docs), failed


def upgrade_to_high_quality(
    db,
    tenant_id: int,
    knowledge_id: int,
    collection: str,
    embed_fn: Optional[Callable] = None,
) -> dict:
    """回填 NULL 向量并升级到 high_quality；返回升级报告。

    报告含 ``failed`` 列表（文档粒度），非空时**不切换** index_mode ——
    失败文档仍可经 economy 关键词分支检索，修复后可重试。
    """
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    kn = db.get(WikiKnowledge, knowledge_id)
    if kn is None:
        raise ValueError(f"知识库不存在: {knowledge_id}")
    if kn.index_mode == HIGH_QUALITY:
        return {"changed": False, "index_mode": HIGH_QUALITY,
                "filled": 0, "docs": 0, "failed": []}

    filled, doc_count, failed = _fill_documents(
        db, tenant_id, collection, embed_fn,
        only_null=True, progress_key="index_upgrade",
    )
    if failed:
        return {"changed": False, "index_mode": ECONOMY,
                "filled": filled, "docs": doc_count, "failed": failed}

    kn.index_mode = HIGH_QUALITY
    db.commit()
    _ensure_vector_indexes(db)
    return {"changed": True, "index_mode": HIGH_QUALITY,
            "filled": filled, "docs": doc_count, "failed": []}


def reembed_collection(
    db,
    tenant_id: int,
    knowledge_id: int,
    collection: str,
    embed_fn: Optional[Callable] = None,
) -> dict:
    """换嵌入模型后重灌：覆盖全部切片向量（父块除外），不改动 index_mode。"""
    filled, doc_count, failed = _fill_documents(
        db, tenant_id, collection, embed_fn,
        only_null=False, progress_key="reembed",
    )
    return {"filled": filled, "docs": doc_count, "failed": failed}


def downgrade_to_economy(db, knowledge_id: int) -> dict:
    """降级仅置标志并保留向量（再次升级无需重嵌）；需前端二次确认。"""
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    kn = db.get(WikiKnowledge, knowledge_id)
    if kn is None:
        raise ValueError(f"知识库不存在: {knowledge_id}")
    if kn.index_mode == ECONOMY:
        return {"changed": False, "index_mode": ECONOMY}
    kn.index_mode = ECONOMY
    db.commit()
    return {"changed": True, "index_mode": ECONOMY}


def _ensure_vector_indexes(db) -> None:
    """升级完成后补建 HNSW / trigram 索引（幂等，失败仅告警）。"""
    from app.db.startup_migrations import create_performance_indexes

    try:
        create_performance_indexes(db.get_bind())
    except Exception as exc:  # noqa: BLE001 - 索引非正确性依赖
        logger.warning(f"[KB 索引升级] 性能索引补建跳过: {exc}")
