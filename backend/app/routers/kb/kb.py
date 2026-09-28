"""KB 认证路由（spec §10.5，Phase 2）：文档 / 检索 / 能力发现。

与子应用 ``/agentscope/knowledge_bases`` 的关系：子应用保留给 AgentScope RAG
Service 内核间调用；前端与业务一律走本路由（主应用认证 + 租户隔离）。
检索走 ``KbRetrievalService``（向量+关键词 RRF 混合），并支持 AgentScope
``metadata_filter`` 语义的键值过滤（作用于 ``kb_segment.metadata_``）。
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.job_runner import run_in_background
from app.deps import get_current_user, get_db
from app.db.database import SessionLocal
from app.models.kb.kb_document import KbDocument
from app.models.sys.sys_user import SysUser
from app.services.kb.document_pipeline import run_document_ingest
from app.services.kb.kb_permissions import (
    KB_ADMIN,
    KB_DELETE,
    KB_UPLOAD,
    require_kb_permission,
)
from app.services.kb.parser_selector import supported_media_types
from app.services.kb.rag.chunker_factory import CHUNKER_REGISTRY, chunker_schemas

router = APIRouter(prefix="/api/v1/kb", tags=["通用知识库"])


def _tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant_required")
    return tenant_id


def _require_knowledge(db: Session, kid: int) -> None:
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    if db.get(WikiKnowledge, kid) is None:
        raise HTTPException(status_code=404, detail="知识库不存在")


def _get_document(db: Session, tenant_id: int, uuid_code: str) -> KbDocument:
    doc = db.execute(
        select(KbDocument).where(
            KbDocument.tenant_id == tenant_id,
            KbDocument.uuid_code == uuid_code,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


def _serialize(doc: KbDocument) -> dict:
    return {
        "document_id": doc.uuid_code,
        "name": doc.name,
        "status": doc.status,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "segment_count": doc.segment_count,
        "error_detail": doc.error_detail,
        "created_at": str(doc.created_at) if doc.created_at else None,
    }


@router.post("/knowledges/{kid}/documents", status_code=201)
def upload_document(
    kid: int,
    file: UploadFile = File(...),
    collection: str = Query("", description="落库集合名；缺省 kb_{kid}"),
    chunker_type: str = Query("approx_token"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """上传文档：落 kb_document(pending)，后台执行 AgentScope 摄取管线。

    权限：``kb:upload``（管理员直通；Phase 3 T3）。
    """
    tenant_id = _tenant_id(current_user)
    _require_knowledge(db, kid)

    content = file.file.read()
    doc = KbDocument(
        tenant_id=tenant_id,
        knowledge_id=kid,
        collection=collection or f"kb_{kid}",
        name=file.filename or "unnamed",
        source_type="upload",
        file_type=(file.filename or "").rsplit(".", 1)[-1] or None,
        file_size=len(content),
        creator_id=getattr(current_user, "user_id", None),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    payload = content  # 闭包持有文件字节；后台线程内自管 Session

    def _run():
        from app.db.database import SessionLocal

        s = SessionLocal()
        try:
            run_document_ingest(
                s, tenant_id, doc.id, payload, doc.name,
                chunker_type=chunker_type,
            )
        finally:
            s.close()

    run_in_background(_run, name=f"kb-ingest-{doc.uuid_code}")
    return _serialize(doc)


@router.get("/knowledges/{kid}/documents")
def list_documents(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    tenant_id = _tenant_id(current_user)
    rows = db.execute(
        select(KbDocument).where(
            KbDocument.tenant_id == tenant_id, KbDocument.knowledge_id == kid
        ).order_by(KbDocument.id.desc())
    ).scalars().all()
    return [_serialize(d) for d in rows]


@router.delete("/documents/{uuid_code}")
def delete_document(
    uuid_code: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_DELETE)),
):
    tenant_id = _tenant_id(current_user)
    doc = _get_document(db, tenant_id, uuid_code)
    from app.services.kb.pgvector_store import PGVectorStore

    PGVectorStore(db, tenant_id).delete_document(doc.collection, doc.uuid_code)
    db.delete(doc)
    db.commit()
    return {"deleted": uuid_code}


@router.get("/documents/status")
def documents_status(
    ids: str = Query(..., description="逗号分隔 uuid"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """状态轮询（前端 3s 间隔消费）。"""
    tenant_id = _tenant_id(current_user)
    wanted = [x for x in ids.split(",") if x]
    rows = db.execute(
        select(KbDocument).where(
            KbDocument.tenant_id == tenant_id, KbDocument.uuid_code.in_(wanted)
        )
    ).scalars().all()
    return {
        d.uuid_code: {"status": d.status, "segment_count": d.segment_count,
                      "error_detail": d.error_detail}
        for d in rows
    }


class RetrieveBody(BaseModel):
    query: str
    top_k: int = 5
    hybrid: bool = True
    score_threshold: Optional[float] = None
    metadata_filters: Optional[dict] = None


@router.post("/collections/{collection}/retrieve")
def retrieve(
    collection: str,
    body: RetrieveBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """统一检索（对齐文档 §8.2 / D3/D10）：底层只调 KnowledgeBase.search。

    * 原生 ``search(queries, top_k, score_threshold)`` 无 metadata_filters 参数，
      故临时筛选在构造期以 ``metadata_filter`` 固化；
    * ``score`` 越大越相关（D12）；父子段落由 ``metadata.parent_content`` 携带（D13）。
    """
    tenant_id = _tenant_id(current_user)
    from app.db.database import SessionLocal
    from app.services.kb.rag.knowledge_factory import knowledge_base

    async def _search():
        async with knowledge_base(
            SessionLocal,
            collection_name=collection,
            tenant_id=tenant_id,
            name=collection,
            metadata_filter=body.metadata_filters,
        ) as kb:
            return await kb.search(
                queries=[body.query], top_k=body.top_k,
                score_threshold=body.score_threshold,
            )

    hits = asyncio.run(_search())
    return {
        "results": [
            {
                "score": h.score,
                "document_id": h.document_id,
                "chunk_index": h.chunk.chunk_index,
                "content": h.chunk.content.text if hasattr(h.chunk.content, "text") else None,
                "metadata": getattr(h.chunk, "metadata", None),
            }
            for h in hits
        ]
    }


@router.get("/supported_content_types")
def supported_content_types():
    """AgentScope Parser 能力发现（supported_media_types 唯一事实源）。"""
    return supported_media_types()


@router.get("/chunkers")
def chunkers():
    """已注册切片器（approx_token / qa / parent_child）与参数 Schema（D6）。"""
    return chunker_schemas()


# ── kb_ref 登记（D1：HTTP 面自子应用迁入主应用，租户取自登录用户）────────────

class KbRefCreate(BaseModel):
    name: str
    description: Optional[str] = None


@router.post("/kb-refs", status_code=201)
def create_kb_ref(
    body: KbRefCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    from app.services.kb.kb_ref_service import KbRefService

    svc = KbRefService(db, _tenant_id(current_user))
    ref = svc.create_kb_ref(
        body.name, body.description,
        getattr(current_user, "user_id", None),
    )
    db.commit()
    return {"kb_id": ref.kb_id, "name": ref.name, "as_user_id": ref.as_user_id}


@router.get("/kb-refs")
def list_kb_refs(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    from app.services.kb.kb_ref_service import KbRefService

    svc = KbRefService(db, _tenant_id(current_user))
    return [
        {"kb_id": r.kb_id, "name": r.name, "as_user_id": r.as_user_id}
        for r in svc.list_kb_refs()
    ]


@router.get("/kb-refs/{kb_id}")
def get_kb_ref(
    kb_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    from app.services.kb.kb_ref_service import KbRefService

    ref = KbRefService(db, _tenant_id(current_user)).get_kb_ref(kb_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="kb 不存在")
    return {"kb_id": ref.kb_id, "name": ref.name, "as_user_id": ref.as_user_id}


@router.delete("/kb-refs/{kb_id}")
def delete_kb_ref(
    kb_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    from app.services.kb.kb_ref_service import KbRefService

    svc = KbRefService(db, _tenant_id(current_user))
    if not svc.delete_kb_ref(kb_id):
        raise HTTPException(status_code=404, detail="kb 不存在")
    db.commit()
    return {"deleted": kb_id}


# ── Phase 3：Q&A / 表格行 / 多模态资产（对齐文档 §8，D15/D9）────────────────

class QaRecordsBody(BaseModel):
    records: list[dict]  # [{question, answer, tags?}]


@router.post("/collections/{collection}/qa-records", status_code=201)
def create_qa_records(
    collection: str,
    body: QaRecordsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """Q&A 直构 Chunk（D15）：仅问题被嵌入，答案随 metadata 返回。"""
    from app.services.kb.rag.content_service import ingest_qa_records

    count = ingest_qa_records(
        db, _tenant_id(current_user), collection, body.records,
        session_factory=SessionLocal,
    )
    return {"ingested": count}


@router.get("/collections/{collection}/qa-records")
def get_qa_records(
    collection: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    from app.services.kb.rag.content_service import list_qa_records

    return list_qa_records(db, _tenant_id(current_user), collection, limit)


@router.post("/collections/{collection}/table-records/import", status_code=201)
def import_table_records(
    collection: str,
    file: UploadFile = File(...),
    embed_field: str = Form(..., description="作为 embedding 的列（单选）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """表格导入（D15）：embed_field 列被嵌入，其余列作可过滤元数据。"""
    from app.services.kb.rag.content_service import ingest_table_rows, parse_table_bytes

    data = file.file.read()
    rows = parse_table_bytes(data, file.filename or "table.csv")
    count = ingest_table_rows(
        db, _tenant_id(current_user), collection, rows, embed_field,
        session_factory=SessionLocal,
    )
    return {"ingested": count, "rows": len(rows)}


@router.post("/collections/{collection}/table-records/preview")
def preview_table_records(
    collection: str,
    file: UploadFile = File(...),
    limit: int = Query(20, ge=1, le=200),
    current_user: SysUser = Depends(get_current_user),
):
    """导入前预览：解析前 N 行，校验字段识别（不落库、不嵌入）。"""
    from app.services.kb.rag.content_service import parse_table_bytes

    data = file.file.read()
    try:
        rows = parse_table_bytes(data, file.filename or "t.csv", limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"columns": sorted({k for r in rows for k in r}), "rows": rows}


@router.post("/collections/{collection}/assets", status_code=201)
def upload_asset(
    collection: str,
    file: UploadFile = File(...),
    caption: str = Form("", description="图片描述/OCR 文本（被嵌入，供文搜图）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """图片资产（D9：仅文搜图——caption 入库被嵌入，图搜图原生不支持）。"""
    import mimetypes

    from app.config import settings
    from app.services.kb.rag.content_service import save_image_asset

    data = file.file.read()
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "image/png"
    try:
        asset = save_image_asset(
            db, _tenant_id(current_user), collection, data,
            file.filename or "image.png", mime, caption,
            storage_dir=settings.UPLOAD_DIR / "kb_assets",
            session_factory=SessionLocal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": asset.id, "file_path": asset.file_path, "size": asset.size}


@router.get("/collections/{collection}/assets")
def list_assets_endpoint(
    collection: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    from app.services.kb.rag.content_service import list_assets

    return list_assets(db, _tenant_id(current_user), collection)


# ── 摄取管线 dry-run（spec §10.7：单步调试，不落库）────────────────────────

@router.post("/pipelines/dry-run")
def pipeline_dry_run(
    file: UploadFile = File(...),
    chunker_type: str = Form("approx_token"),
    chunker_params: str = Form('{}', description='JSON，如 {"chunk_size":256}'),
    current_user: SysUser = Depends(get_current_user),
):
    """样例文件走完整解析→切块链路并返回各步中间产物；**不落库、不嵌入**。"""
    import json as _json

    from app.services.kb.parser_selector import guess_media_type, select_parser
    from app.services.kb.rag.chunker_factory import build_chunker

    data = file.file.read()
    filename = file.filename or "sample.md"
    try:
        params = _json.loads(chunker_params) if chunker_params else {}
    except _json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"chunker_params 非 JSON: {exc}")

    try:
        parser = select_parser(guess_media_type(filename))
        sections = asyncio.run(parser.parse(
            file=data if data else filename, filename=filename,
        ))
        chunker = build_chunker(chunker_type, params)
        chunks = asyncio.run(chunker.chunk(sections))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "sections": [
            {"source": s.source,
             "preview": (s.content.text or "")[:200]
             if hasattr(s.content, "text") else "[DataBlock]"}
            for s in sections
        ],
        "chunks": [
            {"chunk_index": c.chunk_index, "total_chunks": c.total_chunks,
             "preview": (c.content.text or "")[:200]
             if hasattr(c.content, "text") else "[DataBlock]",
             "metadata": c.metadata}
            for c in chunks
        ],
    }
