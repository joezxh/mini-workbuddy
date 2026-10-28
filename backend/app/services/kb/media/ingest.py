"""媒体摄取编排：extract → 构造 Chunk → _insert_via_kb（嵌入内部完成）。

复用 content_service 的「不经 parser/chunker 直接入库」通道（D15）：
Chunk.metadata["chunk_type"] 由 pg_vector_store 投影到 kms_segment.chunk_type（D14），
media_locator/media_kind 留在 kms_segment.metadata_ JSONB（零 DDL）。
失败语义与 document_pipeline.run_document_ingest 一致：
状态机 pending→processing→completed/failed + meta.failed_step（extract/embed）。
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.kb.kb_document import KbDocument
from app.services.kb.pipeline_runner import PipelineStepError


def _fail(db: Session, doc_id: int, step: str, exc: Exception) -> None:
    doc = db.get(KbDocument, doc_id)
    if doc is not None:
        doc.status = "failed"
        doc.error_detail = f"[{step}] {type(exc).__name__}: {exc}"
        doc.meta = {**(doc.meta or {}), "failed_step": step}
        db.commit()
    logger.error(f"[KB 媒体] 文档 {doc_id} 在 {step} 步失败: {exc}")


def run_media_ingest(
    db: Session,
    tenant_id: int,
    doc_id: int,
    file_bytes: bytes,
    filename: str,
    session_factory: Optional[Callable] = None,
    kb_factory: Optional[Callable] = None,
) -> int:
    """同步执行媒体摄取；返回切片数。失败落 failed 后原样抛出。"""
    from agentscope.message import TextBlock
    from agentscope.rag import Chunk

    from app.models.kb.kb_collection import KbCollection
    from app.services.kb.media.base import detect_media_kind, get_extractor
    from app.services.kb.rag.content_service import _insert_via_kb

    doc = db.get(KbDocument, doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: {doc_id}")
    kind = detect_media_kind(filename)
    if kind is None:
        raise ValueError(f"非媒体文件: {filename}")
    doc.status = "processing"
    doc.error_detail = None
    db.commit()

    try:
        # provider 覆盖（spec §6）：知识库 pipeline_config.media → collection retrieval_settings
        override: dict = {}
        from app.models.wiki.wiki_knowledge import WikiKnowledge

        kb = db.get(WikiKnowledge, doc.knowledge_id)
        if kb is not None:
            override.update((kb.pipeline_config or {}).get("media") or {})
        col = db.query(KbCollection).filter(
            KbCollection.name == doc.collection).first()
        if col is not None:
            override.update(col.retrieval_settings or {})
        extractor = get_extractor(kind, db, override)

        async def _extract():
            return await extractor.extract(file_bytes, filename)

        try:
            extraction = asyncio.run(_extract())
        except Exception as exc:  # noqa: BLE001 - 标注 extract 步名后统一落库
            db.rollback()
            raise PipelineStepError("extract", exc) from exc

        chunks = [
            Chunk(
                content=TextBlock(text=seg.text),
                source=filename,
                chunk_index=i,
                total_chunks=len(extraction.segments),
                metadata={
                    "chunk_type": extraction.kind,
                    "media_kind": extraction.kind,
                    "media_locator": seg.locator,
                    "media_meta": extraction.meta,
                },
            )
            for i, seg in enumerate(extraction.segments)
        ]
        document_id = doc.uuid_code
        try:
            _insert_via_kb(
                session_factory, db=db, collection=doc.collection,
                tenant_id=tenant_id, document_id=document_id, chunks=chunks,
                kb_factory=kb_factory,
                document_metadata={"source": f"media:{kind}",
                                   "filename": filename},
            )
        except Exception as exc:  # noqa: BLE001 - 标注 embed 步名后统一落库
            db.rollback()
            raise PipelineStepError("embed", exc) from exc

        doc.status = "completed"
        doc.segment_count = len(chunks)
        doc.meta = {
            **(doc.meta or {}),
            "media": {"kind": kind, **extraction.meta},
            "failed_step": None,
        }
        db.commit()
        logger.info(f"[KB 媒体] {filename} 摄取完成：{len(chunks)} 段（{kind}）")
        return len(chunks)
    except PipelineStepError as exc:
        # spec §5：失败步骤名可观测（extract / embed）
        db.rollback()
        _fail(db, doc_id, exc.step, exc)
        raise
    except Exception as exc:  # noqa: BLE001 - 其余异常统一落 pipeline 步
        db.rollback()
        _fail(db, doc_id, "pipeline", exc)
        raise
