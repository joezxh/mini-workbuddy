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
    KB_VIEW,
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


def _index_mode_for_collection(db: Session, collection: str) -> str:
    """由 collection 名推导知识库索引模式（spec §10.2）。

    collection 命名约定为 ``kb_{knowledge_id}``，反查 ``WikiKnowledge.index_mode``；
    缺省 high_quality。economy 库检索必须绕开向量链路（D11）。
    """
    from app.services.kb.index_mode import resolve_index_mode

    return resolve_index_mode(db, collection)


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
    * ``score`` 越大越相关（D12）；父子段落由 ``metadata.parent_content`` 携带（D13）；
    * ``index_mode=economy`` 时绕开向量链路，走独立关键词检索（D11 / AC7）。
    """
    tenant_id = _tenant_id(current_user)

    # economy 库：独立关键词检索，零 embedding（D11 / AC7）
    if _index_mode_for_collection(db, collection) == "economy":
        from app.services.kb.rag.economy_search import economy_search

        hits = economy_search(
            db, tenant_id, collection, body.query,
            top_k=body.top_k, metadata_filter=body.metadata_filters,
            score_threshold=body.score_threshold,
        )
        return {"results": hits, "index_mode": "economy"}

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
        ],
        "index_mode": "high_quality",
    }


class IndexModeBody(BaseModel):
    mode: str  # high_quality | economy


@router.post("/collections/{collection}/index-mode")
def set_index_mode(
    collection: str,
    body: IndexModeBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """索引模式升降级（spec §10.2 / 验收 7）。

    economy → high_quality 触发后台回填任务（按文档粒度，失败文档保留 economy
    可检索）；high_quality → economy 仅置标志并保留向量，再次升级无需重嵌。
    """
    from app.services.kb.index_mode import (
        ECONOMY,
        HIGH_QUALITY,
        downgrade_to_economy,
        resolve_knowledge_id,
        resolve_index_mode,
        upgrade_to_high_quality,
    )

    if body.mode not in (HIGH_QUALITY, ECONOMY):
        raise HTTPException(status_code=422, detail=f"mode 仅支持 {HIGH_QUALITY}|{ECONOMY}")
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    tenant_id = _tenant_id(current_user)
    kid = resolve_knowledge_id(collection)
    if kid is None:
        raise HTTPException(status_code=400, detail=f"无法从 collection 解析知识库: {collection}")
    if db.get(WikiKnowledge, kid) is None:
        raise HTTPException(status_code=404, detail="知识库不存在")

    current = resolve_index_mode(db, collection)
    if current == body.mode:
        return {"changed": False, "index_mode": current}

    if body.mode == ECONOMY:
        return downgrade_to_economy(db, kid)

    def _run():
        from app.db.database import SessionLocal

        s = SessionLocal()
        try:
            upgrade_to_high_quality(s, tenant_id, kid, collection)
        finally:
            s.close()

    run_in_background(_run, name=f"kb-upgrade-{collection}")
    # 回填期间保持 economy，库仍可经关键词分支检索；完成后自动切 high_quality
    return {"changed": True, "index_mode": ECONOMY, "pending": True}


class CollectionSettingsBody(BaseModel):
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    rerank_provider: Optional[str] = None
    rerank_model: Optional[str] = None
    top_k: Optional[int] = None
    score_threshold: Optional[float] = None
    index_mode: Optional[str] = None


class SegmentUpdateBody(BaseModel):
    content: Optional[str] = None
    keywords: Optional[list] = None
    metadata: Optional[dict] = None


class KeywordsBody(BaseModel):
    keywords: list


class TableRowBody(BaseModel):
    document_id: str
    content: str
    metadata: Optional[dict] = None


class TableSyncBody(BaseModel):
    """db_table 定时同步配置（spec §10.8）；``enabled=false`` 表示停用并移除配置。"""
    enabled: bool = True
    interval_min: int = 60
    source_id: Optional[int] = None
    sql: Optional[str] = None
    embed_field: Optional[str] = None


@router.put("/documents/{uuid_code}/sync")
def configure_table_sync(
    uuid_code: str,
    body: TableSyncBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """配置 db_table 定时同步；启用后由调度器按 interval_min 周期拉取覆盖。"""
    from app.services.kb.table_sync_service import set_sync_config

    tenant_id = _tenant_id(current_user)
    cfg = None
    if body.enabled:
        missing = [k for k in ("source_id", "sql", "embed_field")
                   if getattr(body, k) in (None, "")]
        if missing:
            raise HTTPException(status_code=422, detail=f"启用同步需提供: {missing}")
        cfg = {
            "enabled": True,
            "interval_min": max(1, body.interval_min),
            "source_id": body.source_id,
            "sql": body.sql,
            "embed_field": body.embed_field,
        }
    try:
        doc = set_sync_config(db, tenant_id, uuid_code, cfg)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"document_id": uuid_code, "sync": (doc.meta or {}).get("sync")}


@router.post("/documents/{uuid_code}/sync/run")
def run_table_sync(
    uuid_code: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """立即执行一次同步（与定时作业共用同一实现）。"""
    from app.services.kb.table_sync_service import run_sync_now

    try:
        return run_sync_now(db, _tenant_id(current_user), uuid_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/documents/{uuid_code}/reprocess")
def reprocess_document(
    uuid_code: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """重处理文档：重新嵌入其已有切片（spec §10.5）。

    ``kb_document`` 不留存原始文件字节，故**不会**重新解析；适用场景是换嵌入
    模型后单文档重嵌，或修复失败的嵌入。文本与切片结构保持原样。
    """
    from app.services.kb.segment_service import reembed_document_segments

    tenant_id = _tenant_id(current_user)
    doc = _get_document(db, tenant_id, uuid_code)
    try:
        count = reembed_document_segments(db, tenant_id, doc.collection, doc.uuid_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"document_id": uuid_code, "reembedded": count}


@router.post("/collections/{collection}/table-records", status_code=201)
def create_table_record(
    collection: str,
    body: TableRowBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """新增表格行（spec §10.5 行级新增）：content 为被嵌入列，其余列进 metadata。"""
    from app.services.kb.segment_service import create_segment, serialize_segment

    seg = create_segment(
        db, _tenant_id(current_user), collection, body.document_id, body.content,
        {**(body.metadata or {}), "chunk_type": "table_row"},
    )
    return serialize_segment(seg)


@router.get("/segments/{segment_id}")
def get_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """分段详情（spec §10.5）。"""
    from app.services.kb.segment_service import get_segment as _get, serialize_segment

    seg = _get(db, _tenant_id(current_user), segment_id)
    if seg is None:
        raise HTTPException(status_code=404, detail="分段不存在")
    return serialize_segment(seg)


@router.put("/segments/{segment_id}")
def update_segment(
    segment_id: int,
    body: SegmentUpdateBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """编辑分段（spec §10.5）；改文本后按索引模式重嵌，避免索引与内容不一致。"""
    from app.services.kb.segment_service import serialize_segment
    from app.services.kb.segment_service import update_segment as _update

    try:
        seg = _update(
            db, _tenant_id(current_user), segment_id,
            content=body.content, keywords=body.keywords, metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return serialize_segment(seg)


@router.delete("/segments/{segment_id}")
def delete_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_DELETE)),
):
    """删除分段（spec §10.5）；子块由外键 CASCADE 连带。"""
    from app.services.kb.segment_service import delete_segment as _delete

    try:
        _delete(db, _tenant_id(current_user), segment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"deleted": segment_id}


@router.patch("/segments/{segment_id}/keywords")
def patch_segment_keywords(
    segment_id: int,
    body: KeywordsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """只改关键词（spec §10.5）：不触发重嵌。"""
    from app.services.kb.segment_service import serialize_segment, update_keywords

    try:
        seg = update_keywords(db, _tenant_id(current_user), segment_id, body.keywords)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return serialize_segment(seg)


@router.get("/segments/{segment_id}/citations")
def segment_citations(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """查看引用来源（spec §10.5）：来源文档 + 父块链 + 子块。"""
    from app.services.kb.segment_service import get_citations

    try:
        return get_citations(db, _tenant_id(current_user), segment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/collections/{collection}/settings")
def get_collection_settings(
    collection: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """设置面板当前值（spec §10.5）：检索设置 + 索引模式。"""
    from app.services.kb.collection_settings import get_retrieval_settings

    return {
        "retrieval_settings": get_retrieval_settings(db, collection),
        "index_mode": _index_mode_for_collection(db, collection),
    }


@router.put("/collections/{collection}/settings")
def update_collection_settings(
    collection: str,
    body: CollectionSettingsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """设置面板写入（spec §10.5）：检索参数即时落库，重灌走后台任务。

    换嵌入模型 → ``reembed``（覆盖全部向量）；索引模式升档 → ``upgrade_index``
    （回填 NULL 后翻标志）。同一请求产生多个作业时按序在单个后台任务内执行。
    """
    from app.services.kb.collection_settings import apply_collection_settings
    from app.services.kb.index_mode import (
        reembed_collection,
        resolve_knowledge_id,
        upgrade_to_high_quality,
    )

    tenant_id = _tenant_id(current_user)
    kid = resolve_knowledge_id(collection)
    if kid is None:
        raise HTTPException(status_code=400, detail=f"无法从 collection 解析知识库: {collection}")

    try:
        applied = apply_collection_settings(db, collection, body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    jobs = applied["jobs"]
    if jobs:
        def _run():
            from app.db.database import SessionLocal

            s = SessionLocal()
            try:
                for job in jobs:  # 有序：先重嵌，再回填 NULL 并翻标志
                    if job == "reembed":
                        reembed_collection(s, tenant_id, kid, collection)
                    elif job == "upgrade_index":
                        upgrade_to_high_quality(s, tenant_id, kid, collection)
            finally:
                s.close()

        run_in_background(_run, name=f"kb-settings-{collection}")

    return {**applied, "pending": bool(jobs)}


@router.get("/documents/{uuid_code}/segments")
def list_document_segments(
    uuid_code: str,
    chunk_type: Optional[str] = Query(None, description="按形态过滤: text|qa|table_row|image|parent|child"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """文档的分段列表（spec §10.5 分段详情 / 表格条目 / Q&A 列表共用）。"""
    from app.services.kb.segment_service import list_document_segments as _list

    try:
        return _list(db, _tenant_id(current_user), uuid_code,
                     chunk_type=chunk_type, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/collections/{collection}/qa-records/import", status_code=201)
async def import_qa_records(
    collection: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """Q&A 批量导入（spec §10.5）：CSV/xlsx，列名 question/answer/tags。"""
    from app.services.kb.rag.content_service import ingest_qa_records, parse_table_bytes

    data = await file.read()
    filename = file.filename or "qa.csv"
    try:
        rows = parse_table_bytes(data, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    records = [
        {"question": str(r.get("question", "")).strip(),
         "answer": str(r.get("answer", "")).strip(),
         "tags": [t.strip() for t in str(r.get("tags") or "").split(";") if t.strip()]}
        for r in rows if r.get("question")
    ]
    if not records:
        raise HTTPException(status_code=422, detail="未解析到任何 question 列数据")

    count = ingest_qa_records(db, _tenant_id(current_user), collection, records)
    return {"imported": count}


@router.get("/collections/{collection}/qa-records/export")
def export_qa_records(
    collection: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """Q&A 导出 CSV（spec §10.5），UTF-8 BOM 兼容 Excel。"""
    import csv as _csv
    import io

    from fastapi.responses import StreamingResponse

    from app.services.kb.rag.content_service import list_qa_records

    rows = list_qa_records(db, _tenant_id(current_user), collection, limit=100000)
    buf = io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(["question", "answer", "tags"])
    for r in rows:
        writer.writerow([r["question"] or "", r["answer"] or "", ";".join(r["tags"])])
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(("\ufeff" + buf.getvalue()).encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="qa-{collection}.csv"'},
    )


@router.get("/supported_content_types")
def supported_content_types():
    """AgentScope Parser 能力发现（supported_media_types 唯一事实源）。"""
    return supported_media_types()


@router.get("/chunkers")
def chunkers():
    """已注册切片器（approx_token / qa / parent_child）与参数 Schema（D6）。"""
    return chunker_schemas()


@router.get("/pipelines/schema")
def pipeline_schema():
    """摄取编排 Schema（spec §10.7 / D8）：原生键名 + chunker/rag 参数 Schema。"""
    from app.services.kb.pipeline_config import pipeline_config_schema

    return pipeline_config_schema()


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
    pipeline_config: str = Form(None, description='完整原生编排 JSON（D8）；优先于 chunker_* 扁平参数'),
    current_user: SysUser = Depends(get_current_user),
):
    """样例文件走完整解析→清洗→切块链路并返回各步中间产物；**不落库、不嵌入**。

    支持两种入参：扁平 ``chunker_type``/``chunker_params``（兼容旧向导），
    或完整 ``pipeline_config``（D8 原生键名，``parser``/``clean``/``chunker``
    段零转换驱动）。与真实摄取共用 ``pipeline_runner``，预览即落库结果。
    """
    import json as _json

    from app.services.kb.pipeline_runner import run_pipeline_from_config

    data = file.file.read()
    filename = file.filename or "sample.md"

    # D8：pipeline_config 优先（parser/clean/chunker 段全部生效）
    pc: dict | None = None
    if pipeline_config:
        try:
            from app.services.kb.pipeline_config import normalize_pipeline_config

            pc = normalize_pipeline_config(_json.loads(pipeline_config)) or {}
        except (_json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"pipeline_config 非法: {exc}")

    try:
        params = _json.loads(chunker_params) if chunker_params else {}
    except _json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"chunker_params 非 JSON: {exc}")

    try:
        result = run_pipeline_from_config(
            data, filename,
            pipeline_config=pc,
            chunker_type=chunker_type,
            chunker_params=params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return result.to_preview()
