"""文档摄取管线（spec §10.3）：AgentScope Parser → Chunker → KbIngestService。

状态机：pending → processing → completed | failed；失败写入
``kb_document.error_detail``（含步骤名），整档可重试（重灌即幂等 upsert）。

同步执行体供 ``job_runner.run_in_background`` 调用（调用方负责开/关 Session，
本函数内部按步骤 commit 状态）。``embed_fn`` 可注入（测试替换 / 换 embedding 后端）。
"""
from __future__ import annotations

import asyncio
from typing import Callable, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.kb.kb_document import KbDocument
from app.services.kb.ingest_service import EmbedFn, KbIngestService, build_embed_fn
from app.services.kb.parser_selector import select_parser
from app.services.kb.pgvector_store import PGVectorStore, SegmentInput

# 扩展名 → IANA 媒体类型（仅供 Parser 选择；能力面仍以 parser.supported_media_types 为准）
_EXT_MEDIA = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp",
}


def guess_media_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _EXT_MEDIA:
        return _EXT_MEDIA[ext]
    return "text/markdown" if ext in ("md", "markdown") else "text/plain"


def _fail(db: Session, doc_id: int, step: str, exc: Exception) -> None:
    doc = db.get(KbDocument, doc_id)
    if doc is not None:
        doc.status = "failed"
        doc.error_detail = f"[{step}] {type(exc).__name__}: {exc}"
        db.commit()
    logger.error(f"[KB 管线] 文档 {doc_id} 在 {step} 步失败: {exc}")


def run_document_ingest(
    db: Session,
    tenant_id: int,
    doc_id: int,
    file_bytes: Optional[bytes],
    filename: str,
    chunker_type: str = "approx_token",
    chunker_params: Optional[dict] = None,
    embedding_code: Optional[str] = None,
    embed_fn: Optional[EmbedFn] = None,
) -> int:
    """同步执行整条管线；返回写入切片数。失败落 failed 状态后原样抛出。"""
    from app.services.kb.kb_app import CHUNKER_REGISTRY

    doc = db.get(KbDocument, doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: {doc_id}")
    doc.status = "processing"
    doc.error_detail = None
    db.commit()

    try:
        # 1) 解析（AgentScope Parser；TextParser 兼容 bytes/str）
        parser = select_parser(guess_media_type(filename))
        sections = asyncio.run(parser.parse(
            file=file_bytes if file_bytes is not None else filename,
            filename=filename,
        ))

        # 2) 切块（注册表内选择；参数经 Parameters 模型校验）
        chunker_cls = CHUNKER_REGISTRY.get(chunker_type)
        if chunker_cls is None:
            raise ValueError(f"未知 chunker_type: {chunker_type!r}")
        params_model = chunker_cls.Parameters(**(chunker_params or {}))
        chunker = chunker_cls(parameters=params_model)
        chunks = asyncio.run(chunker.chunk(sections))

        # 3)+4) 向量化 + 幂等落库（复用既有服务）
        if embed_fn is None:
            embed_fn = build_embed_fn(embedding_code)
        store = PGVectorStore(db, tenant_id)
        service = KbIngestService(store, embed_fn)
        segments: List[SegmentInput] = []
        for c in chunks:
            content = c.content.text if hasattr(c.content, "text") else None
            if not content:
                continue  # DataBlock（多模态）切片 Phase 2 暂不落库，multimodal 形态处理
            segments.append(SegmentInput(
                chunk_index=c.chunk_index,
                content=content,
                metadata=dict(c.metadata or {}),
            ))
        count = service.ingest_document(doc.collection, doc.uuid_code, segments)

        # 5) 收尾
        doc.status = "completed"
        doc.segment_count = count
        db.commit()
        return count
    except Exception as exc:  # noqa: BLE001 - 管线失败必须落库可观测后原样抛出
        db.rollback()
        _fail(db, doc_id, "pipeline", exc)
        raise
