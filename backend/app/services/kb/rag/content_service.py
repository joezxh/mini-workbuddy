"""QA / 表格行 / 多模态资产的内容服务（对齐文档 §8 / D15 / D9）。

共同形态：**不经 parser/chunker**，直接构造 ``Chunk`` 调
``KnowledgeBase.insert_document``（嵌入在 KB 内部完成）。
``kb_factory`` 可注入（测试替换真实嵌入模型）；生产路径传 ``session_factory``。

D9 边界：AgentScope 2.0.8 ``supports_multimodal`` 恒 False → 仅支持**文搜图**
（图片以 caption/OCR 文本入库 + 资产文件落盘），图搜图不支持。
"""
from __future__ import annotations

import asyncio
import csv
import io
import uuid
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.kb.kb_document import KbDocument, new_document_uuid
from app.models.kb.kb_segment import KbSegment
from app.models.kb.kb_segment_asset import KbSegmentAsset
from app.services.kb.rag.chunker_factory import build_qa_chunks, build_table_row_chunks

ASSET_MAX_BYTES = 2 * 1024 * 1024   # 单图 ≤ 2MB（对齐 Dify）
ASSET_MAX_PER_SEGMENT = 10          # 单 chunk ≤ 10 张


def _insert_via_kb(
    session_factory: Optional[Callable],
    *,
    db: Session,
    collection: str,
    tenant_id: int,
    document_id: str,
    chunks,
    kb_factory: Optional[Callable] = None,
    document_metadata: Optional[dict] = None,
) -> None:
    """经 KnowledgeBase.insert_document 落库（嵌入内部完成）。

    economy 模式写 NULL 向量（D11）；检索走独立关键词服务（AC7）。
    """

    async def _run() -> None:
        from app.services.kb.index_mode import resolve_index_mode

        index_mode = resolve_index_mode(db, collection)
        if kb_factory is not None:
            async with kb_factory(index_mode=index_mode) as kb:
                await kb.ensure_collection()
                await kb.insert_document(chunks, document_id=document_id,
                                         document_metadata=document_metadata)
            return
        from app.db.database import SessionLocal
        from app.services.kb.rag.knowledge_factory import knowledge_base

        async with knowledge_base(
            SessionLocal, collection_name=collection, tenant_id=tenant_id,
            name=collection, index_mode=index_mode,
        ) as kb:
            await kb.ensure_collection()
            await kb.insert_document(chunks, document_id=document_id,
                                     document_metadata=document_metadata)

    asyncio.run(_run())


def _track_document(
    db: Session, tenant_id: int, collection: str, name: str,
    source_type: str, count: int,
) -> KbDocument:
    doc = KbDocument(
        tenant_id=tenant_id, knowledge_id=0, collection=collection,
        name=name, source_type=source_type, status="completed", segment_count=count,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ── Q&A（D15）────────────────────────────────────────────────────────────

def ingest_qa_records(
    db: Session, tenant_id: int, collection: str, records: list[dict],
    session_factory: Optional[Callable] = None,
    kb_factory: Optional[Callable] = None,
) -> int:
    """Q&A 直构 Chunk：content=问题（仅问题被嵌入），answer/tags 进 metadata。"""
    if not records:
        return 0
    doc_id = new_document_uuid()
    chunks = build_qa_chunks(records, source="qa-import")
    _insert_via_kb(
        session_factory, db=db, collection=collection, tenant_id=tenant_id,
        document_id=doc_id, chunks=chunks, kb_factory=kb_factory,
        document_metadata={"source": "qa-import"},
    )
    _track_document(db, tenant_id, collection, f"qa-{doc_id[:8]}", "qa_import", len(chunks))
    return len(chunks)


def list_qa_records(db: Session, tenant_id: int, collection: str,
                    limit: int = 100) -> list[dict]:
    """Q&A 条目列表；``segment_id`` 供前端直接改单条（启停/编辑）而不必回表定位。"""
    rows = db.execute(text(
        "SELECT id, document_id, chunk_index, content, metadata"
        " FROM kms_segment WHERE collection = :c AND tenant_id = :t"
        " AND metadata->>'chunk_type' = 'qa' ORDER BY id DESC LIMIT :k"
    ), {"c": collection, "t": tenant_id, "k": limit}).all()
    return [
        {
            "segment_id": r.id,
            "document_id": r.document_id,
            "chunk_index": r.chunk_index,
            "question": r.content,
            "answer": (r.metadata or {}).get("answer"),
            "tags": (r.metadata or {}).get("tags") or [],
            "enabled": (r.metadata or {}).get("enabled", True),
        }
        for r in rows
    ]


# ── 表格行（D15）─────────────────────────────────────────────────────────

def parse_table_bytes(data: bytes, filename: str, limit: int | None = None) -> list[dict]:
    """CSV / xlsx → [{列名: 值}]。"""
    rows: list[dict] = []
    lower = filename.lower()
    if lower.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        for row in reader:
            rows.append({k: v for k, v in row.items() if k})
            if limit and len(rows) >= limit:
                break
        return rows
    if lower.endswith((".xlsx", ".xls")):
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        iterator = ws.iter_rows(values_only=True)
        headers = [str(h) for h in next(iterator, [])]
        for values in iterator:
            if all(v is None for v in values):
                continue
            rows.append({h: v for h, v in zip(headers, values) if h})
            if limit and len(rows) >= limit:
                break
        wb.close()
        return rows
    raise ValueError(f"不支持的表格文件类型: {filename!r}（仅 csv/xlsx/xls）")


def ingest_table_rows(
    db: Session, tenant_id: int, collection: str, rows: list[dict],
    embed_field: str,
    session_factory: Optional[Callable] = None,
    kb_factory: Optional[Callable] = None,
    document_id: Optional[str] = None,
) -> int:
    """表格行直构 Chunk：embed_field 列被嵌入，其余列进 metadata（可过滤）。

    ``document_id`` 供定时同步覆盖同一文档（spec §10.8）；缺省新建文档 ID。
    """
    if not rows:
        return 0
    if embed_field not in rows[0]:
        raise ValueError(f"embedding 字段 {embed_field!r} 不在表头中")
    doc_id = document_id or new_document_uuid()
    chunks = build_table_row_chunks(rows, embed_field=embed_field, source="table-import")
    _insert_via_kb(
        session_factory, db=db, collection=collection, tenant_id=tenant_id,
        document_id=doc_id, chunks=chunks, kb_factory=kb_factory,
        document_metadata={"source": "table-import", "embed_field": embed_field},
    )
    # 定时同步传入已有 document_id 时不新建文档（避免重复文档行）
    if document_id is None:
        _track_document(db, tenant_id, collection, f"table-{doc_id[:8]}",
                        "db_table", len(chunks))
    return len(chunks)


# ── 多模态资产（D9：仅文搜图）────────────────────────────────────────────

def save_image_asset(
    db: Session, tenant_id: int, collection: str,
    data: bytes, filename: str, mime_type: str, caption: str,
    storage_dir: Path,
    session_factory: Optional[Callable] = None,
    kb_factory: Optional[Callable] = None,
) -> KbSegmentAsset:
    """图片落盘 + caption 文本 chunk 入库（文搜图）+ 资产行登记。

    资产行挂在 insert_document 产生的首个 kms_segment 行上（D9：原生 Chunk 无
    segment id，取该文档 chunk_index=0 的行）。
    """
    if len(data) > ASSET_MAX_BYTES:
        raise ValueError(f"图片超过 2MB 上限（{len(data)} 字节）")
    if not mime_type.startswith("image/"):
        raise ValueError(f"仅支持图片类型，收到 {mime_type!r}")

    doc_id = new_document_uuid()
    from agentscope.message import TextBlock
    from agentscope.rag import Chunk

    chunk = Chunk(
        content=TextBlock(text=caption or filename),
        source=filename,
        chunk_index=0, total_chunks=1,
        metadata={"chunk_type": "image", "filename": filename, "mime": mime_type},
    )
    _insert_via_kb(
        session_factory, db=db, collection=collection, tenant_id=tenant_id,
        document_id=doc_id, chunks=[chunk], kb_factory=kb_factory,
        document_metadata={"source": "image", "filename": filename},
    )

    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    asset_name = f"{uuid.uuid4().hex}_{filename}"
    path = storage_dir / asset_name
    path.write_bytes(data)

    segment = db.execute(
        text("SELECT id FROM kms_segment WHERE collection=:c AND document_id=:d"
             " AND chunk_index=0 LIMIT 1"),
        {"c": collection, "d": doc_id},
    ).scalar_one()

    asset = KbSegmentAsset(
        tenant_id=tenant_id, segment_id=segment,
        file_path=str(path), mime_type=mime_type, size=len(data),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def list_assets(db: Session, tenant_id: int, collection: str,
                limit: int = 100) -> list[dict]:
    """按 collection 列出图片资产（经 kms_segment 反查）。"""
    rows = db.execute(text(
        "SELECT a.id, a.file_path, a.mime_type, a.size, a.created_at"
        " FROM kms_segment_asset a"
        " JOIN kms_segment s ON s.id = a.segment_id"
        " WHERE s.collection = :c AND a.tenant_id = :t"
        " ORDER BY a.id DESC LIMIT :k"
    ), {"c": collection, "t": tenant_id, "k": limit}).all()
    return [
        {"id": r.id, "file_path": r.file_path, "mime_type": r.mime_type,
         "size": r.size, "created_at": str(r.created_at) if r.created_at else None}
        for r in rows
    ]
