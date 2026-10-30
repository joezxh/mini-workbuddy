"""图谱知识库路由（prefix /api/v1/kb/knowledges/{kid}/graph）。

Spec: docs/superpowers/specs/2026-10-30-kg-knowledge-base-design.md 5.3

职责边界：
* 本层只做协议转换 + 鉴权，业务规则全部在 KgService（单一实现来源）。
* 鉴权统一经 require_kb_permission：读 kb:view、写 kb:admin；
  前端隐藏按钮只是 UX 层，不是授权边界。
* 租户来自登录态，缺失即 400——图谱实例是租户私有数据。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_triple import KgTriple
from app.models.sys.sys_user import SysUser
from app.services.kb.kb_permissions import KB_ADMIN, KB_VIEW, require_kb_permission
from app.services.kb.kg.kg_service import KgService

router = APIRouter(prefix="/api/v1/kb/knowledges", tags=["图谱知识库"])


def _tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant_required")
    return tenant_id


def _svc(db: Session, current_user: SysUser, kid: int) -> KgService:
    return KgService(db, tenant_id=_tenant_id(current_user), knowledge_id=kid)


def _entity_out(e: KgEntity, mention_count: Optional[int] = None) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "entity_key": e.entity_key,
        "type_code": e.type_code,
        "aliases": e.aliases or [],
        "properties": e.properties or {},
        "status": e.status,
        "mention_count": mention_count if mention_count is not None
        else len(e.source_segment_ids or []),
        "source_segment_ids": e.source_segment_ids or [],
        "source_document_ids": e.source_document_ids or [],
        "has_vector": e.embedding is not None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _relation_out(t: KgTriple, names: Optional[Dict[int, str]] = None) -> dict:
    names = names or {}
    return {
        "id": t.id,
        "relation_code": t.relation_code,
        "predicate": t.predicate,
        "from_entity_id": t.from_entity_id,
        "from_entity_name": names.get(t.from_entity_id),
        "to_entity_id": t.to_entity_id,
        "to_entity_name": names.get(t.to_entity_id),
        "weight": t.weight,
        "status": t.status,
        "properties": t.properties or {},
        "evidence": t.evidence,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _entity_names(svc: KgService, triples: List[KgTriple]) -> Dict[int, str]:
    """批量取关系两端实体名（避免逐条查询）。"""
    ids = {t.from_entity_id for t in triples} | {t.to_entity_id for t in triples}
    if not ids:
        return {}
    entities = svc.list_entities(limit=100000)
    return {e.id: e.name for e in entities if e.id in ids}


# ── 请求体 ────────────────────────────────────────────────────────────────

class EntityCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    entity_key: Optional[str] = Field(None, max_length=512)
    type_code: Optional[str] = Field(None, max_length=64)
    aliases: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)
    source_segment_ids: List[int] = Field(default_factory=list)
    source_document_ids: List[str] = Field(default_factory=list)


class EntityUpdateBody(BaseModel):
    name: Optional[str] = Field(None, max_length=500)
    type_code: Optional[str] = Field(None, max_length=64)
    aliases: Optional[List[str]] = None
    properties: Optional[Dict[str, Any]] = None


class RelationCreateBody(BaseModel):
    from_entity_id: int
    to_entity_id: int
    relation_code: Optional[str] = Field(None, max_length=64)
    predicate: Optional[str] = Field(None, max_length=200)
    weight: float = 0.0
    properties: Dict[str, Any] = Field(default_factory=dict)
    evidence: Optional[Dict[str, Any]] = None


class ReviewBody(BaseModel):
    verdict: str = Field(..., description="accepted | rejected")


# ── 实体端点 ─────────────────────────────────────────────────────────────

@router.get("/{kid}/graph/entities")
def list_entities(
    kid: int,
    type_code: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """实体列表（按类型 / 状态 / 关键词过滤，分页）。"""
    svc = _svc(db, current_user, kid)
    items = svc.list_entities(
        type_code=type_code, status=status, keyword=keyword,
        limit=limit, offset=offset,
    )
    total = svc.count_entities(type_code=type_code, status=status, keyword=keyword)
    return {
        "items": [_entity_out(e) for e in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/{kid}/graph/entities", status_code=201)
def create_entity(
    kid: int,
    body: EntityCreateBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """新建实体（entity_key 重复时合并返回既有实体）。"""
    svc = _svc(db, current_user, kid)
    entity = svc.create_entity(
        name=body.name,
        entity_key=body.entity_key,
        type_code=body.type_code,
        aliases=body.aliases or None,
        properties=body.properties or None,
        source_segment_ids=body.source_segment_ids or None,
        source_document_ids=body.source_document_ids or None,
    )
    return _entity_out(entity)


@router.get("/{kid}/graph/entities/{entity_id}")
def get_entity(
    kid: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """实体详情 + 邻接关系（检视面板用）。"""
    svc = _svc(db, current_user, kid)
    entity = svc.get_entity(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="实体不存在")
    adjacent = svc.entity_adjacent_triples(entity_id)
    out = _entity_out(entity)
    out["adjacent_relations"] = [
        _relation_out(t, _entity_names(svc, adjacent)) for t in adjacent
    ]
    return out


@router.put("/{kid}/graph/entities/{entity_id}")
def update_entity(
    kid: int,
    entity_id: int,
    body: EntityUpdateBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """编辑实体（名称 / 类型 / 别名 / 属性）。"""
    svc = _svc(db, current_user, kid)
    entity = svc.update_entity(entity_id, **body.model_dump(exclude_unset=True))
    return _entity_out(entity)


@router.delete("/{kid}/graph/entities/{entity_id}")
def delete_entity(
    kid: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """删除实体（关联关系级联清理）。"""
    svc = _svc(db, current_user, kid)
    svc.delete_entity(entity_id)
    return {"ok": True, "id": entity_id}


@router.patch("/{kid}/graph/entities/{entity_id}/accept")
def accept_entity(
    kid: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """实体评审：suggested -> active。"""
    svc = _svc(db, current_user, kid)
    return _entity_out(svc.accept_entity(entity_id))


# ── 关系端点 ─────────────────────────────────────────────────────────────

@router.get("/{kid}/graph/relations")
def list_relations(
    kid: int,
    relation_code: Optional[str] = None,
    status: Optional[str] = None,
    from_entity_id: Optional[int] = None,
    to_entity_id: Optional[int] = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """关系列表（含两端实体名，供表格直接展示）。"""
    svc = _svc(db, current_user, kid)
    items = svc.list_triples(
        relation_code=relation_code, status=status,
        from_entity_id=from_entity_id, to_entity_id=to_entity_id,
        limit=limit, offset=offset,
    )
    total = svc.count_triples(
        relation_code=relation_code, status=status,
        from_entity_id=from_entity_id, to_entity_id=to_entity_id,
    )
    names = _entity_names(svc, items)
    return {
        "items": [_relation_out(t, names) for t in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/{kid}/graph/relations", status_code=201)
def create_relation(
    kid: int,
    body: RelationCreateBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """新建关系（两端实体必须属于当前知识库）。"""
    svc = _svc(db, current_user, kid)
    triple = svc.create_triple(
        from_entity_id=body.from_entity_id,
        to_entity_id=body.to_entity_id,
        relation_code=body.relation_code,
        predicate=body.predicate,
        weight=body.weight,
        properties=body.properties or None,
        evidence=body.evidence,
    )
    return _relation_out(triple, _entity_names(svc, [triple]))


@router.get("/{kid}/graph/relations/{relation_id}")
def get_relation(
    kid: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """关系详情。"""
    svc = _svc(db, current_user, kid)
    triple = svc.get_triple(relation_id)
    if triple is None:
        raise HTTPException(status_code=404, detail="关系不存在")
    return _relation_out(triple, _entity_names(svc, [triple]))


@router.delete("/{kid}/graph/relations/{relation_id}")
def delete_relation(
    kid: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """删除关系。"""
    svc = _svc(db, current_user, kid)
    svc.delete_triple(relation_id)
    return {"ok": True, "id": relation_id}


@router.patch("/{kid}/graph/relations/{relation_id}/review")
def review_relation(
    kid: int,
    relation_id: int,
    body: ReviewBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """关系评审：suggested -> accepted | rejected。"""
    svc = _svc(db, current_user, kid)
    triple = svc.review_triple(relation_id, body.verdict)
    return _relation_out(triple, _entity_names(svc, [triple]))


# ── 概览统计 ─────────────────────────────────────────────────────────────

@router.get("/{kid}/graph/stats")
def graph_stats(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """概览统计：实体 / 关系计数与类型分布（概览 Tab 数据源）。"""
    svc = _svc(db, current_user, kid)
    return svc.stats()


# ── 失败切片清单（spec §5.6，对齐 Yuxi failed-chunks）──────────────────

@router.get("/{kid}/graph/failed-segments")
def failed_segments(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """抽取失败/未就绪的切片清单（含失败原因，供「溯源」Tab 重试）。"""
    from sqlalchemy import select

    from app.models.kb.kb_segment import KbSegment

    tenant_id = _tenant_id(current_user)
    stmt = select(KbSegment).where(
        KbSegment.collection == f"kb_{kid}",
        KbSegment.graph_structure_indexed.is_not(None),
    )
    rows = db.execute(stmt.limit(500)).scalars().all()
    return {
        "items": [
            {
                "segment_id": s.id,
                "document_id": s.document_id,
                "chunk_index": s.chunk_index,
                "structure_indexed": s.graph_structure_indexed,
                "vector_indexed": s.graph_indexed,
                "details": s.graph_extraction_details,
            }
            for s in rows
            if s.graph_structure_indexed is False or s.graph_indexed is False
        ],
        "total": len(rows),
        "tenant_id": tenant_id,
    }


# ── 单文档重抽（前端「文档」Tab 的「重新抽取图谱」）────────────────────

class DocRebuildBody(BaseModel):
    document_uuid: str = Field(..., description="文档 uuid_code")


@router.post("/{kid}/graph/documents/rebuild")
def rebuild_document_graph(
    kid: int,
    body: DocRebuildBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """仅对指定文档重抽图谱：先撤销其贡献，再重建（后台执行）。"""
    from app.services.kb.kg.kg_build_service import submit_build

    tenant_id = _tenant_id(current_user)
    out = submit_build(
        tenant_id=tenant_id, knowledge_id=kid, action="rebuild",
        document_uuid=body.document_uuid,
    )
    if not out.get("accepted"):
        raise HTTPException(status_code=409, detail=out.get("reason", "任务冲突"))
    return out


# ── KB 级图谱配置（存 pipeline_config["graph"]，不新增列）────────────────

class GraphConfigPatch(BaseModel):
    extractor_type: Optional[str] = None
    model_spec: Optional[Dict[str, Any]] = None
    schema_source: Optional[str] = None
    catalog_id: Optional[int] = None
    schema: Optional[str] = None
    concurrency_count: Optional[int] = None
    timeout_seconds: Optional[int] = None
    use_graph_retrieval: Optional[bool] = None
    graph_entity_top_k: Optional[int] = None
    graph_triple_top_k: Optional[int] = None
    graph_max_nodes: Optional[int] = None
    graph_top_k: Optional[int] = None
    graph_weight: Optional[float] = None
    ppr_damping: Optional[float] = None


@router.get("/{kid}/graph/config")
def get_config(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """读取图谱配置（缺省补齐 + 越界钳制后的生效值）。"""
    from app.services.kb.kg.kg_config import get_graph_config

    return get_graph_config(db, kid)


@router.put("/{kid}/graph/config")
def save_config(
    kid: int,
    body: GraphConfigPatch,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """保存图谱配置（只更新提交的键，其余保持既有值）。"""
    from app.services.kb.kg.kg_config import save_graph_config

    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return save_graph_config(db, kid, patch)


# ── 构建管理（独立前缀，避免与查询端点混在一起）──────────────────────────

build_router = APIRouter(prefix="/api/v1/kb/knowledges", tags=["图谱构建"])


class BuildBody(BaseModel):
    action: str = Field("build", description="build|clear_document|rebuild|reconcile")
    document_uuid: Optional[str] = None


@build_router.post("/{kid}/graph-build/submit")
def submit_graph_build(
    kid: int,
    body: BuildBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """提交图谱构建任务（后台执行，立即返回）。

    同一知识库已有任务在执行时返回 409（单库互斥，spec §5.5）。
    """
    from app.services.kb.kg.kg_build_service import submit_build

    tenant_id = _tenant_id(current_user)
    if body.action not in ("build", "clear_document", "rebuild", "reconcile"):
        raise HTTPException(status_code=422, detail=f"未知构建动作: {body.action!r}")
    out = submit_build(
        tenant_id=tenant_id, knowledge_id=kid, action=body.action,
        document_uuid=body.document_uuid,
    )
    if not out.get("accepted"):
        raise HTTPException(status_code=409, detail=out.get("reason", "任务冲突"))
    return out


@build_router.get("/{kid}/graph-build/status")
def graph_build_status(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """构建状态与两阶段进度（前端轮询端点）。"""
    from sqlalchemy import func, select

    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service, kg_neo4j_store

    tenant_id = _tenant_id(current_user)
    total = db.execute(
        select(func.count(KbSegment.id)).where(
            KbSegment.collection == f"kb_{kid}",
            KbSegment.tenant_id == tenant_id,
        )
    ).scalar_one()
    structure_done = db.execute(
        select(func.count(KbSegment.id)).where(
            KbSegment.collection == f"kb_{kid}",
            KbSegment.tenant_id == tenant_id,
            KbSegment.graph_structure_indexed.is_(True),
        )
    ).scalar_one()
    vector_done = db.execute(
        select(func.count(KbSegment.id)).where(
            KbSegment.collection == f"kb_{kid}",
            KbSegment.tenant_id == tenant_id,
            KbSegment.graph_indexed.is_(True),
        )
    ).scalar_one()
    failed = db.execute(
        select(func.count(KbSegment.id)).where(
            KbSegment.collection == f"kb_{kid}",
            KbSegment.tenant_id == tenant_id,
            KbSegment.graph_structure_indexed.is_(False),
        )
    ).scalar_one()

    neo4j_ok = kg_neo4j_store.is_available()
    running = kg_build_service.is_locked(kid)

    if running:
        state = "running"
    elif failed:
        state = "partial_failed"
    elif total and structure_done == total and vector_done == total:
        state = "ready"
    elif total:
        state = "pending"
    else:
        state = "not_built"

    return {
        "state": state,
        "running": running,
        "neo4j_available": neo4j_ok,
        "segments": total,
        "structure_done": structure_done,
        "vector_done": vector_done,
        "failed": failed,
    }
