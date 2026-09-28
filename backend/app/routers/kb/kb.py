"""KB 认证路由（spec §10.5，Phase 2）：文档 / 检索 / 能力发现。

与子应用 ``/agentscope/knowledge_bases`` 的关系：子应用保留给 AgentScope RAG
Service 内核间调用；前端与业务一律走本路由（主应用认证 + 租户隔离）。
检索走 ``KbRetrievalService``（向量+关键词 RRF 混合），并支持 AgentScope
``metadata_filter`` 语义的键值过滤（作用于 ``kb_segment.metadata_``）。
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.job_runner import run_in_background
from app.deps import get_current_user, get_db
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
