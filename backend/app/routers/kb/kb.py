"""KB 认证路由（spec §10.5，Phase 2）：文档 / 检索 / 能力发现。

与子应用 ``/agentscope/knowledge_bases`` 的关系：子应用保留给 AgentScope RAG
Service 内核间调用；前端与业务一律走本路由（主应用认证 + 租户隔离）。
检索走 ``KbRetrievalService``（向量+关键词 RRF 混合），并支持 AgentScope
``metadata_filter`` 语义的键值过滤（作用于 ``kb_segment.metadata_``）。
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.job_runner import run_in_background
from app.deps import get_current_user, get_db
from app.db.database import SessionLocal
from app.models.connectors.external_doc_map import KbExternalDocMap
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
from app.services.kb.upload_store import drop_upload, load_upload, save_upload

router = APIRouter(prefix="/api/v1/kb", tags=["通用知识库"])

logger = logging.getLogger(__name__)


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
        # 文档↔集合关联走 collection_id（单一事实来源）；collection 名仅作展示/兼容，
        # 向量库命名空间由前端用 collection_id 反查 name 后传入。
        "collection_id": doc.collection_id,
        "collection": doc.collection,
        "created_at": str(doc.created_at) if doc.created_at else None,
    }


def _doc_collection_name(db: Session, doc: KbDocument) -> Optional[str]:
    """由文档的 collection_id 反查集合名（向量库命名空间）；缺失时回退 doc.collection。

    文档↔集合关联以 collection_id 为单一事实来源，name 仅作存储标签。
    """
    if doc.collection_id:
        from app.services.kb.collection_service import get_collection_name_by_id

        try:
            return get_collection_name_by_id(db, doc.collection_id)
        except ValueError:
            pass
    return doc.collection


def _resolve_collection_name(db: Session, collection_id: int) -> str:
    """路由层单点：由 collection_id 反查集合名（向量库命名空间）。

    文档↔集合关联以 id 为唯一事实来源，调用方不再直接传集合名；此处反查后
    下游逻辑仍按 name 操作（与历史等价）。集合不存在转 404。
    """
    from app.services.kb.collection_service import get_collection_name_by_id

    try:
        return get_collection_name_by_id(db, collection_id)
    except ValueError:
        raise HTTPException(
            status_code=404, detail=f"集合不存在: collection_id={collection_id}"
        )


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

    # 媒体文件上传门禁（spec §2.4）：未启用多模态 / 超限 → 422
    from app.models.wiki.wiki_knowledge import WikiKnowledge
    from app.services.kb.media.validation import validate_media_upload

    content = file.file.read()
    knowledge = db.get(WikiKnowledge, kid)
    try:
        validate_media_upload(knowledge, file.filename or "", len(content))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
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
    # 落盘原始文件：供「重试」重新执行 解析→清洗→切块→向量化（spec §10.5）
    # 注意：uuid_code 是 Python 侧 default，必须先 flush 才会生成
    db.add(doc)
    db.flush()
    doc.meta = {
        "file_path": save_upload(tenant_id, doc.uuid_code, doc.name, content),
        "chunker_type": chunker_type,
    }
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

    PGVectorStore(db, tenant_id).delete_document(_doc_collection_name(db, doc), doc.uuid_code)
    drop_upload((doc.meta or {}).get("file_path"))
    # 外部导入文档：连带清掉映射。若只靠外键 SET NULL 留孤儿映射，
    # 重新导入会因 content_hash 命中而误判「未变更」并跳过，文档再也拉不回来。
    db.query(KbExternalDocMap).filter(
        KbExternalDocMap.tenant_id == tenant_id,
        KbExternalDocMap.document_id == doc.id,
    ).delete(synchronize_session=False)
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


def _retrieve_collection(
    db: Session, tenant_id: int, collection: str, body: RetrieveBody
) -> dict:
    """单集合检索：economy 走关键词链路，high_quality 走向量链路。"""
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


@router.post("/collections/{collection_id}/retrieve")
def retrieve(
    collection_id: int,
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
    collection = _resolve_collection_name(db, collection_id)
    return _retrieve_collection(db, _tenant_id(current_user), collection, body)


@router.post("/knowledges/{kid}/retrieve")
def retrieve_knowledge(
    kid: int,
    body: RetrieveBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """知识库检索：跨该知识库**全部集合**检索并合并取 Top-K。

    表格知识库可有多个集合（每文件归属其一），单集合检索会漏掉自动新建集合
    里的条目，故「全部文件」视角的检索测试走知识库维度。
    """
    tenant_id = _tenant_id(current_user)
    _require_knowledge(db, kid)
    from app.services.kb.segment_service import knowledge_collection_names

    merged: list[dict] = []
    modes: set[str] = set()
    for name in knowledge_collection_names(db, tenant_id, kid):
        try:
            res = _retrieve_collection(db, tenant_id, name, body)
        except Exception:  # 单个集合无索引/未就绪不影响其它集合
            continue
        if res.get("index_mode"):
            modes.add(res["index_mode"])
        merged.extend(res.get("results") or [])

    merged.sort(key=lambda h: h.get("score") or 0, reverse=True)
    return {
        "results": merged[: body.top_k],
        "index_mode": modes.pop() if len(modes) == 1 else (next(iter(modes), "")),
    }


class IndexModeBody(BaseModel):
    mode: str  # high_quality | economy


@router.post("/collections/{collection_id}/index-mode")
def set_index_mode(
    collection_id: int,
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
    collection = _resolve_collection_name(db, collection_id)
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
        count = reembed_document_segments(
            db, tenant_id, _doc_collection_name(db, doc), doc.uuid_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"document_id": uuid_code, "reembedded": count}


@router.post("/documents/{uuid_code}/retry")
def retry_document(
    uuid_code: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """重试：用留存的原始文件重新执行 解析 → 清洗 → 切块 → 向量化。

    与 ``/reprocess`` 的区别：后者只重嵌**已有**切片（不重新分段）；
    本端点先清理该文档旧切片，再按原 chunker 配置重跑整条管线，
    适用于摄入失败、或调整切块策略后想重新分段的场景。

    历史文档（上传早于落盘改造）没有 ``meta.file_path``，此时返回 400
    并提示改用 ``/reprocess``。
    """
    from app.services.kb.pgvector_store import PGVectorStore

    tenant_id = _tenant_id(current_user)
    doc = _get_document(db, tenant_id, uuid_code)
    meta = dict(doc.meta or {})
    file_path = meta.get("file_path")

    if not file_path:
        raise HTTPException(
            status_code=400,
            detail="该文档未留存原始文件（上传早于落盘改造），无法重新分段；"
                   "如仅需重新向量化，请改用「重新向量化」",
        )
    try:
        payload = load_upload(file_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail=f"原始文件已丢失：{file_path}；如仅需重新向量化，请改用「重新向量化」",
        )
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"原始文件读取失败: {exc}")

    # 表格导入：用原文件重导同一文档行（不新建 kms_document），分支处理
    if meta.get("source") == "table-import":
        return _retry_table_document(db, tenant_id, doc, meta, payload)

    # 清理旧切片，避免重跑后同文档出现重复分段
    PGVectorStore(db, tenant_id).delete_document(_doc_collection_name(db, doc), doc.uuid_code)

    doc.status = "processing"
    doc.error_detail = None
    doc.segment_count = 0
    doc.meta = {**meta, "retry_count": int(meta.get("retry_count") or 0) + 1}
    db.commit()
    db.refresh(doc)

    chunker_type = meta.get("chunker_type") or "approx_token"

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

    run_in_background(_run, name=f"kb-retry-{doc.uuid_code}")
    return _serialize(doc)


def _retry_table_document(db, tenant_id: int, doc, meta: dict, payload: bytes):
    """表格导入文档的重试：删旧切片 → 用原文件重导同一文档行（document_id 不变）。

    与文档管线重试不同，表格导入不经过 parser/chunker，直接复用 ``import_table_file``
    （``create_document=False`` 避免新增 ``kms_document`` 行，``uuid_code`` 保持不变），
    列定义沿用已存的 ``kms_collection.schema_config``（``embed_field`` 不传即沿用）。
    """
    from app.services.kb.pgvector_store import PGVectorStore
    from app.services.kb.rag.content_service import import_table_file

    # 清理旧切片，避免重导后同文档出现重复分段（uq_kms_segment 唯一约束）
    coll_name = _doc_collection_name(db, doc)
    PGVectorStore(db, tenant_id).delete_document(coll_name, doc.uuid_code)
    doc.status = "processing"
    doc.error_detail = None
    doc.segment_count = 0
    doc.meta = {**meta, "retry_count": int(meta.get("retry_count") or 0) + 1}
    db.commit()
    db.refresh(doc)

    def _run():
        from app.db.database import SessionLocal

        s = SessionLocal()
        try:
            res = import_table_file(
                s, tenant_id, coll_name, payload, doc.name,
                knowledge_id=doc.knowledge_id,
                session_factory=SessionLocal,
                document_id=doc.uuid_code,
                create_document=False,
            )
            refreshed = s.get(KbDocument, doc.id)
            if refreshed is not None:
                refreshed.status = "completed"
                refreshed.error_detail = None
                refreshed.segment_count = res["ingested"]
                s.commit()
        except Exception as exc:  # noqa: BLE001 - 重导失败落库可观测
            s.rollback()
            refreshed = s.get(KbDocument, doc.id)
            if refreshed is not None:
                refreshed.status = "failed"
                refreshed.error_detail = str(exc)[:2000]
                s.commit()
        finally:
            s.close()

    run_in_background(_run, name=f"kb-table-retry-{doc.uuid_code}")
    return _serialize(doc)


@router.get("/documents/{uuid_code}/flow")
def document_flow(
    uuid_code: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """文档处理流程：各步产出摘要 + 失败步骤 + 错误信息（文档列表「流程」视图）。

    ``steps`` 来自管线落库的 ``meta.pipeline_steps``（parse/clean/chunk/vectorize
    各步的解析器、切块器与产出数量）；失败时 ``failed_step`` 指出失败在哪一步，
    ``error_detail`` 给出原始错误文本。
    """
    tenant_id = _tenant_id(current_user)
    doc = _get_document(db, tenant_id, uuid_code)
    meta = doc.meta or {}
    return {
        "document_id": doc.uuid_code,
        "name": doc.name,
        "status": doc.status,
        "segment_count": doc.segment_count,
        "steps": meta.get("pipeline_steps") or [],
        "failed_step": meta.get("failed_step"),
        "error_detail": doc.error_detail,
        "retry_count": int(meta.get("retry_count") or 0),
    }


@router.post("/knowledges/{kid}/rechunk")
def rechunk_knowledge(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """按知识库**当前**切片方案，对全部留存原文件的文档重新分段并向量化。

    切片方案来自 ``WikiKnowledge.pipeline_config.chunker``（新建/编辑知识库时选择）；
    管线本来就优先采用该配置，故本端点只需清理旧切片后重跑整条链路即可生效。
    上传早于落盘改造的文档（无 ``meta.file_path``）会被跳过并返回在 ``skipped``。
    """
    from app.services.kb.pgvector_store import PGVectorStore

    tenant_id = _tenant_id(current_user)
    _require_knowledge(db, kid)
    docs = db.execute(
        select(KbDocument).where(
            KbDocument.tenant_id == tenant_id,
            KbDocument.knowledge_id == kid,
        ).order_by(KbDocument.id)
    ).scalars().all()

    queued: list[tuple[int, str, str]] = []  # (doc_id, collection, file_path)
    skipped: list[str] = []
    for doc in docs:
        path = (doc.meta or {}).get("file_path")
        if path and Path(path).exists():
            queued.append((doc.id, _doc_collection_name(db, doc), path))
        else:
            skipped.append(doc.uuid_code)

    for doc_id, _collection, _path in queued:
        doc = db.get(KbDocument, doc_id)
        if doc is None:
            continue
        PGVectorStore(db, tenant_id).delete_document(doc.collection, doc.uuid_code)
        doc.status = "pending"
        doc.error_detail = None
        doc.segment_count = 0
    db.commit()

    def _run():
        from app.db.database import SessionLocal

        s = SessionLocal()
        try:
            for doc_id, _collection, path in queued:
                try:
                    payload = load_upload(path)
                except OSError:
                    continue
                doc = s.get(KbDocument, doc_id)
                if doc is None:
                    continue
                try:
                    run_document_ingest(s, tenant_id, doc.id, payload, doc.name)
                except Exception as exc:  # noqa: BLE001 - 单文档失败不中断整批
                    logger.error(f"[KB 重新分段] 文档 {doc.id} 失败: {exc}")
        finally:
            s.close()

    if queued:
        run_in_background(_run, name=f"kb-rechunk-{kid}")
    return {"queued": len(queued), "skipped": skipped}


@router.post("/collections/{collection_id}/table-records", status_code=201)
def create_table_record(
    collection_id: int,
    body: TableRowBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """新增表格行（spec §10.5 行级新增）：content 为被嵌入列，其余列进 metadata。"""
    from app.services.kb.segment_service import create_segment, serialize_segment

    collection = _resolve_collection_name(db, collection_id)
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


@router.get("/collections/{collection_id}/settings")
def get_collection_settings(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """设置面板当前值（spec §10.5）：检索设置 + 索引模式。"""
    from app.services.kb.collection_settings import get_retrieval_settings

    collection = _resolve_collection_name(db, collection_id)
    return {
        "retrieval_settings": get_retrieval_settings(db, collection),
        "index_mode": _index_mode_for_collection(db, collection),
    }


@router.put("/collections/{collection_id}/settings")
def update_collection_settings(
    collection_id: int,
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
    collection = _resolve_collection_name(db, collection_id)
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
    q: Optional[str] = Query(None, description="对被嵌入内容做包含匹配（表格条目区的查）"),
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
                     chunk_type=chunk_type, q=q, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/collections/{collection_id}/segments")
def list_collection_segments_api(
    collection_id: int,
    document_id: Optional[str] = Query(None, description="收窄到某个文件；不传=该集合全部条目"),
    chunk_type: Optional[str] = Query(None, description="按形态过滤: text|qa|table_row|image|parent|child"),
    q: Optional[str] = Query(None, description="对被嵌入内容做包含匹配"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """集合内条目列表：表格知识库「表格条目」tab（单文件过滤用）。"""
    from app.services.kb.segment_service import list_collection_segments

    collection = _resolve_collection_name(db, collection_id)
    return list_collection_segments(
        db, _tenant_id(current_user), collection,
        document_id=document_id, chunk_type=chunk_type, q=q,
        page=page, page_size=page_size,
    )


@router.get("/knowledges/{kid}/segments")
def list_knowledge_segments_api(
    kid: int,
    document_id: Optional[str] = Query(None, description="收窄到某个文件；不传=该知识库全部条目"),
    chunk_type: Optional[str] = Query(None, description="按形态过滤: text|qa|table_row|image|parent|child"),
    q: Optional[str] = Query(None, description="对被嵌入内容做包含匹配"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """知识库条目列表（跨该知识库全部集合）：表格知识库「表格条目 → 全部文件」用。

    表格知识库支持一个知识库多个集合（每文件归属其一），按单集合过滤会漏掉
    自动新建集合里的条目，故「全部文件」视图走知识库维度聚合。
    """
    from app.services.kb.segment_service import list_knowledge_segments

    _require_knowledge(db, kid)
    return list_knowledge_segments(
        db, _tenant_id(current_user), kid,
        document_id=document_id, chunk_type=chunk_type, q=q,
        page=page, page_size=page_size,
    )


@router.post("/collections/{collection_id}/qa-records/import", status_code=201)
async def import_qa_records(
    collection_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """Q&A 批量导入（spec §10.5）：CSV/xlsx，列名 question/answer/tags。"""
    from app.services.kb.rag.content_service import ingest_qa_records, parse_table_bytes

    collection = _resolve_collection_name(db, collection_id)
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


@router.get("/collections/{collection_id}/qa-records/export")
def export_qa_records(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """Q&A 导出 CSV（spec §10.5），UTF-8 BOM 兼容 Excel。"""
    import csv as _csv
    import io

    from fastapi.responses import StreamingResponse

    from app.services.kb.rag.content_service import list_qa_records

    collection = _resolve_collection_name(db, collection_id)
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
    """已注册切片方案与各自参数 Schema（D6）：含展示名，供前端下拉。"""
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


@router.post("/collections/{collection_id}/qa-records", status_code=201)
def create_qa_records(
    collection_id: int,
    body: QaRecordsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """Q&A 直构 Chunk（D15）：仅问题被嵌入，答案随 metadata 返回。"""
    from app.services.kb.rag.content_service import ingest_qa_records

    collection = _resolve_collection_name(db, collection_id)
    count = ingest_qa_records(
        db, _tenant_id(current_user), collection, body.records,
        session_factory=SessionLocal,
    )
    return {"ingested": count}


@router.get("/collections/{collection_id}/qa-records")
def get_qa_records(
    collection_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    from app.services.kb.rag.content_service import list_qa_records

    collection = _resolve_collection_name(db, collection_id)
    return list_qa_records(db, _tenant_id(current_user), collection, limit)


# ── 知识库级 Q&A（问答 / 文档型知识库不依赖 kms_collection，按 kb_{kid} 标签作用域）──
def _kb_default_collection(kid: int) -> str:
    return f"kb_{kid}"


@router.get("/knowledges/{kid}/qa-records")
def list_knowledge_qa_records(
    kid: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """知识库级 Q&A 列表：问答 / 文档型知识库无需 kms_collection 行，按 kb_{kid} 标签作用域。"""
    _require_knowledge(db, kid)
    from app.services.kb.rag.content_service import list_qa_records

    return list_qa_records(db, _tenant_id(current_user), _kb_default_collection(kid), limit)


@router.post("/knowledges/{kid}/qa-records", status_code=201)
def create_knowledge_qa_records(
    kid: int,
    body: QaRecordsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """知识库级 Q&A 直构 Chunk（D15）：仅问题被嵌入，答案随 metadata 返回。"""
    _require_knowledge(db, kid)
    from app.services.kb.rag.content_service import ingest_qa_records

    count = ingest_qa_records(
        db, _tenant_id(current_user), _kb_default_collection(kid), body.records,
        session_factory=SessionLocal,
    )
    return {"ingested": count}


@router.post("/knowledges/{kid}/qa-records/import", status_code=201)
async def import_knowledge_qa_records(
    kid: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """知识库级 Q&A 批量导入（spec §10.5）：CSV/xlsx，列名 question/answer/tags。"""
    _require_knowledge(db, kid)
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

    count = ingest_qa_records(db, _tenant_id(current_user), _kb_default_collection(kid), records)
    return {"imported": count}


@router.get("/knowledges/{kid}/qa-records/export")
def export_knowledge_qa_records(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """知识库级 Q&A 导出 CSV（spec §10.5），UTF-8 BOM 兼容 Excel。"""
    import csv as _csv
    import io

    from fastapi.responses import StreamingResponse

    from app.services.kb.rag.content_service import list_qa_records

    _require_knowledge(db, kid)
    collection = _kb_default_collection(kid)
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


def _parse_embed_fields(raw: str) -> list[str]:
    """Form 里的「向量化字段组合」（逗号分隔）→ 字段名列表。"""
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


@router.post("/collections/{collection_id}/table-records/import", status_code=201)
def import_table_records(
    collection_id: int,
    file: UploadFile = File(...),
    embed_field: str = Form("", description="兼容旧参数：单个被嵌入列"),
    embed_fields: str = Form("", description="向量化字段组合（逗号分隔，1~N 个）；缺省取字段定义里的被嵌入字段"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """表格文件导入（D15）：按列定义校验 → 一行一段（向量化字段组合拼成 CSV 行）。

    切分：每行一段，``content`` 即被嵌入内容 —— 由集合配置的**向量化字段组合**
    （1~N 个字段）按逗号拼成 CSV 行；其余字段进 ``metadata`` 供过滤。

    列定义（``kms_collection.schema_config``）语义：
    * 尚未定义 → 按文件表头**自动定义**并落库（**默认全部字段**为向量化字段）；
    * 已有定义 → 缺列/多列/取值类型不符一律 422 且**不导入任何数据**。
    """
    from app.services.kb.collection_service import get_collection_by_id
    from app.services.kb.rag.content_service import import_table_file
    from app.services.kb.table_schema import TableSchemaMismatch

    coll = get_collection_by_id(db, collection_id)
    if coll is None:
        raise HTTPException(status_code=404, detail=f"集合不存在: collection_id={collection_id}")
    collection = coll.name
    kid = coll.knowledge_id
    data = file.file.read()
    try:
        return import_table_file(
            db, _tenant_id(current_user), collection, data,
            file.filename or "table.csv",
            knowledge_id=kid,
            embed_field=embed_field or None,
            embed_fields=_parse_embed_fields(embed_fields) or None,
            session_factory=SessionLocal,
        )
    except TableSchemaMismatch as exc:
        raise HTTPException(status_code=422, detail=exc.as_detail())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/knowledges/{kid}/table-records/import", status_code=201)
def import_table_records_to_knowledge(
    kid: int,
    file: UploadFile = File(...),
    collection_id: int = Form(0, description="所属集合 ID；0/不传 = 不指定，后端按文件自动新建集合"),
    embed_fields: str = Form("", description="向量化字段组合（逗号分隔，1~N 个）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """表格文件导入（**可不指定集合**）：未指定时按文件格式自动新建该知识库下的集合。

    表格知识库支持一个知识库配置多个集合。上传时：
    * 指定了 ``collection_id`` → 按该集合的字段定义校验文件列名与类型；
    * 未指定 → 后端自动新建集合（``kb_{kid}_{slug}``），并按文件表头生成字段定义
      （**默认所有字段组合为向量化内容**）。

    两种情况下文档都必有所属集合（``kms_document.collection_id``）。
    """
    from app.services.kb.rag.content_service import import_table_file
    from app.services.kb.table_schema import TableSchemaMismatch

    data = file.file.read()
    try:
        return import_table_file(
            db, _tenant_id(current_user), "", data,
            file.filename or "table.csv",
            knowledge_id=kid,
            embed_fields=_parse_embed_fields(embed_fields) or None,
            session_factory=SessionLocal,
            collection_id=collection_id or None,
            auto_create_collection=not collection_id,
        )
    except TableSchemaMismatch as exc:
        raise HTTPException(status_code=422, detail=exc.as_detail())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/knowledges/{kid}/collections")
def list_knowledge_collections(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """列出某知识库下的全部集合（表格知识库上传时选择「所属集合」用）。"""
    from app.services.kb.collection_service import list_knowledge_collections
    from app.services.kb.table_schema import embedding_fields, get_schema_fields

    colls = list_knowledge_collections(db, _tenant_id(current_user), kid)
    items = []
    for coll in colls:
        fields = get_schema_fields(db, coll.name)
        items.append({
            "id": coll.id,
            "name": coll.name,
            "dimensions": coll.dimensions,
            "field_count": len(fields),
            "embed_fields": embedding_fields(fields),
            "schema_config": fields,
        })
    return {"items": items}


class CollectionCreateBody(BaseModel):
    slug: Optional[str] = None
    schema_config: Optional[list] = None
    dimensions: Optional[int] = None


class CollectionUpdateBody(BaseModel):
    slug: Optional[str] = None
    schema_config: Optional[list] = None
    dimensions: Optional[int] = None


@router.post("/knowledges/{kid}/collections", status_code=201)
def create_knowledge_collection_api(
    kid: int,
    body: CollectionCreateBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """在知识库下新建集合（可选 slug 与字段定义）；slug 缺省自动命名。"""
    from app.services.kb.collection_service import create_knowledge_collection

    tenant_id = _tenant_id(current_user)
    _require_knowledge(db, kid)
    try:
        coll = create_knowledge_collection(
            db, tenant_id, kid,
            slug=body.slug, schema_config=body.schema_config,
            dimensions=body.dimensions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return {
        "id": coll.id, "name": coll.name, "dimensions": coll.dimensions,
        "knowledge_id": coll.knowledge_id, "schema_config": coll.schema_config,
    }


@router.put("/knowledges/{kid}/collections/{collection_id}")
def update_knowledge_collection_api(
    kid: int,
    collection_id: int,
    body: CollectionUpdateBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """编辑集合：重命名（slug）与/或更新字段定义（schema_config）/ 维度。

    重命名级联同步 kms_document / kms_segment 的 name 标签（向量数据不动）；
    字段定义经 ``set_schema_fields`` 校验（至少 1 个向量化字段）。
    """
    from app.services.kb.collection_service import (
        get_collection_by_id,
        rename_collection,
    )
    from app.services.kb.table_schema import set_schema_fields

    coll = get_collection_by_id(db, collection_id)
    if coll is None or coll.knowledge_id != kid:
        raise HTTPException(status_code=404, detail=f"集合不存在: collection_id={collection_id}")
    if body.slug is not None and body.slug != "":
        try:
            rename_collection(db, collection_id, body.slug)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    if body.schema_config is not None:
        try:
            set_schema_fields(db, coll.name, body.schema_config)
        except Exception as exc:  # noqa: BLE001 - TableSchemaMismatch 等
            raise HTTPException(status_code=422, detail=str(exc))
    if body.dimensions is not None:
        coll.dimensions = body.dimensions
    db.commit()
    refreshed = get_collection_by_id(db, collection_id)
    return {
        "id": refreshed.id, "name": refreshed.name,
        "dimensions": refreshed.dimensions,
        "knowledge_id": refreshed.knowledge_id,
        "schema_config": refreshed.schema_config,
    }


@router.delete("/knowledges/{kid}/collections/{collection_id}")
def delete_knowledge_collection_api(
    kid: int,
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """删除集合（级联删其下全部文档与切片；不可恢复，前端二次确认）。"""
    from app.services.kb.collection_service import (
        delete_collection_cascade,
        get_collection_by_id,
    )

    coll = get_collection_by_id(db, collection_id)
    if coll is None or coll.knowledge_id != kid:
        raise HTTPException(status_code=404, detail=f"集合不存在: collection_id={collection_id}")
    try:
        delete_collection_cascade(db, _tenant_id(current_user), collection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return {"deleted": collection_id}


@router.post("/collections/{collection_id}/table-records/preview")
def preview_table_records(
    collection_id: int,
    file: UploadFile = File(...),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """导入前预览：解析前 N 行并按列定义校验（**不落库、不嵌入**）。

    与导入同一套校验口径：列不匹配同样 422，保证「预览能过 = 导入能过」。
    """
    from app.services.kb.rag.content_service import parse_table
    from app.services.kb.table_schema import TableSchemaMismatch, resolve_import_schema

    data = file.file.read()
    try:
        columns, rows = parse_table(data, file.filename or "t.csv", limit=limit)
        if not columns:
            raise ValueError("表格文件没有可用表头（首行需为列名）")
        collection = _resolve_collection_name(db, collection_id)
        schema = resolve_import_schema(
            db, collection, columns, rows,
            tenant_id=_tenant_id(current_user), persist=False,
        )
    except TableSchemaMismatch as exc:
        raise HTTPException(status_code=422, detail=exc.as_detail())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "columns": columns,
        "rows": schema["rows"][:limit],
        "embed_fields": schema["embed_fields"],
        "embed_field": schema["embed_field"],
        "schema": schema["fields"],
    }


# ── 表格列定义（kms_collection.schema_config）────────────────────────────

@router.get("/collections/{collection_id}/schema")
def get_collection_schema(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """表格列定义；未定义时 ``fields`` 为空（下次导入文件会自动按表头生成）。

    ``embed_fields`` 是向量化字段组合（1~N 个，决定每段 CSV 行的列序与向量化内容）。
    """
    from app.services.kb.table_schema import embedding_fields, get_schema_fields

    collection = _resolve_collection_name(db, collection_id)
    fields = get_schema_fields(db, collection)
    embed = embedding_fields(fields)
    return {
        "fields": fields,
        "columns": [f["name"] for f in fields],
        "embed_fields": embed,
        "embed_field": embed[0] if embed else None,
    }


class TableSchemaBody(BaseModel):
    fields: list[dict] = Field(default_factory=list, description="[{name,type,enabled,embedding,filterable}]")


@router.put("/collections/{collection_id}/schema")
def update_collection_schema(
    collection_id: int,
    body: TableSchemaBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """手工维护表格列定义；**至少**一个向量化字段（可多个，与 Dify 字段定义对齐）。"""
    from app.services.kb.table_schema import (
        TableSchemaMismatch,
        embedding_fields,
        set_schema_fields,
    )

    collection = _resolve_collection_name(db, collection_id)
    try:
        fields = set_schema_fields(db, collection, body.fields)
    except TableSchemaMismatch as exc:
        raise HTTPException(status_code=422, detail=exc.as_detail())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    embed = embedding_fields(fields)
    return {
        "fields": fields,
        "columns": [f["name"] for f in fields],
        "embed_fields": embed,
        "embed_field": embed[0] if embed else None,
    }


@router.post("/collections/{collection_id}/assets", status_code=201)
def upload_asset(
    collection_id: int,
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

    collection = _resolve_collection_name(db, collection_id)
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


@router.get("/collections/{collection_id}/assets")
def list_assets_endpoint(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    from app.services.kb.rag.content_service import list_assets

    collection = _resolve_collection_name(db, collection_id)
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
