"""图谱知识库路由（prefix /api/v1/kb/knowledges/{kid}/graph）。

Spec: docs/superpowers/specs/2026-10-30-kg-knowledge-base-design.md 5.3

职责边界：
* 本层只做协议转换 + 鉴权，业务规则全部在 KgService（单一实现来源）。
* 鉴权统一经 require_kb_permission：读 kb:view、写 kb:admin；
  前端隐藏按钮只是 UX 层，不是授权边界。
* 租户来自登录态，缺失即 400——图谱实例是租户私有数据。
"""
from __future__ import annotations

import json

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
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


def _relation_out(
    t: KgTriple,
    names: Optional[Dict[int, str]] = None,
    mention_count: int = 0,
) -> dict:
    # 抽取器：手动录入与图谱抽取的区分（evidence 存在即视为抽取产物）
    extractor = (t.properties or {}).get("extractor") or ("llm" if t.evidence else "manual")
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
        "review_verdict": t.review_verdict,
        "review_note": t.review_note,
        "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
        "properties": t.properties or {},
        "evidence": t.evidence,
        "mention_count": mention_count,
        "extractor": extractor,
        # 溯源文档（uuid_code 列表）：供前端按文档过滤关系（只读展示）
        "source_document_ids": t.source_document_ids or [],
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _triple_mention_counts(db: Session, triples: List[KgTriple]) -> Dict[int, int]:
    """批量统计关系提及数（避免逐条 count 查询）。"""
    from sqlalchemy import func, select

    from app.models.kb.kg_triple_mention import KgTripleMention

    ids = [t.id for t in triples if t.id is not None]
    if not ids:
        return {}
    rows = db.execute(
        select(KgTripleMention.kg_triple_id, func.count(KgTripleMention.id))
        .where(KgTripleMention.kg_triple_id.in_(ids))
        .group_by(KgTripleMention.kg_triple_id)
    ).all()
    return {int(rid): int(cnt) for rid, cnt in rows}


def _entity_names(svc: KgService, triples: List[KgTriple]) -> Dict[int, str]:
    """批量取关系两端实体名（只查涉及的 id，两列精确查询）。

    性能：旧实现 ``list_entities(limit=100000)`` 整表加载全部实体
    （含 embedding 向量列），实体详情/关系列表每次请求都白载全库向量。
    """
    ids = {t.from_entity_id for t in triples} | {t.to_entity_id for t in triples}
    if not ids:
        return {}
    return svc.list_entity_names(list(ids))


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
    mentions = _triple_mention_counts(db, items)
    return {
        "items": [
            _relation_out(t, names, mentions.get(int(t.id), 0)) for t in items
        ],
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
    """关系详情（含两端实体名 / 提及数 / 抽取器，供检视面板）。"""
    svc = _svc(db, current_user, kid)
    triple = svc.get_triple(relation_id)
    if triple is None:
        raise HTTPException(status_code=404, detail="关系不存在")
    mentions = _triple_mention_counts(db, [triple])
    return _relation_out(
        triple, _entity_names(svc, [triple]), mentions.get(int(triple.id), 0)
    )


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


class RelationUpdateBody(BaseModel):
    relation_code: Optional[str] = None
    predicate: Optional[str] = None
    weight: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None


@router.patch("/{kid}/graph/relations/{relation_id}")
def update_relation(
    kid: int,
    relation_id: int,
    body: RelationUpdateBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """编辑关系（类型/谓词/权重/证据/边属性；端点实体不可变）。"""
    svc = _svc(db, current_user, kid)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    triple = svc.update_triple(relation_id, **fields)
    return _relation_out(triple, _entity_names(svc, [triple]))


# ── 批量操作（原型「批量接受/批量改类型/批量删除」的后端支撑）──────────────

def _batch_apply(apply, ids: List[int]) -> dict:
    """逐条容错执行：单条失败不毁整批，返回逐条明细供前端提示。"""
    results = []
    for raw_id in ids:
        try:
            iid = int(raw_id)
        except (TypeError, ValueError):
            results.append({"id": raw_id, "ok": False, "error": "非法 ID"})
            continue
        try:
            apply(iid)
            results.append({"id": iid, "ok": True})
        except HTTPException as exc:
            results.append({"id": iid, "ok": False, "error": exc.detail})
        except Exception as exc:  # noqa: BLE001
            results.append({"id": iid, "ok": False, "error": str(exc)})
    ok_count = sum(1 for r in results if r["ok"])
    return {
        "results": results,
        "ok_count": ok_count,
        "failed_count": len(results) - ok_count,
    }


class BatchIdsBody(BaseModel):
    ids: List[int]
    verdict: Optional[str] = None  # batch-review 用: accepted|rejected
    type_code: Optional[str] = None  # batch-set-type 用


@router.post("/{kid}/graph/entities/batch-review")
def batch_review_entities(
    kid: int,
    body: BatchIdsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """批量接受实体（suggested → active；逐条容错）。"""
    svc = _svc(db, current_user, kid)
    return _batch_apply(svc.accept_entity, body.ids)


@router.post("/{kid}/graph/entities/batch-set-type")
def batch_set_entity_type(
    kid: int,
    body: BatchIdsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """批量修改实体类型。"""
    svc = _svc(db, current_user, kid)
    type_code = (body.type_code or "").strip() or None
    return _batch_apply(
        lambda iid: svc.update_entity(iid, type_code=type_code), body.ids
    )


@router.post("/{kid}/graph/entities/batch-delete")
def batch_delete_entities(
    kid: int,
    body: BatchIdsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """批量删除实体（级联清理其关系；逐条容错）。"""
    svc = _svc(db, current_user, kid)
    return _batch_apply(svc.delete_entity, body.ids)


@router.post("/{kid}/graph/relations/batch-review")
def batch_review_relations(
    kid: int,
    body: BatchIdsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """批量评审关系（suggested → accepted|rejected；逐条容错）。"""
    svc = _svc(db, current_user, kid)
    if body.verdict not in ("accepted", "rejected"):
        raise HTTPException(status_code=422, detail="verdict 应为 accepted/rejected")
    return _batch_apply(
        lambda iid: svc.review_triple(iid, body.verdict), body.ids
    )


@router.post("/{kid}/graph/relations/batch-delete")
def batch_delete_relations(
    kid: int,
    body: BatchIdsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """批量删除关系（逐条容错）。"""
    svc = _svc(db, current_user, kid)
    return _batch_apply(svc.delete_triple, body.ids)


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


class ReviewBatchBody(BaseModel):
    relation_ids: Optional[List[int]] = None   # 指定条目；空 = 按 status 取
    status: str = "suggested"                  # suggested|accepted|rejected|all
    limit: Optional[int] = None                # 默认 review_batch_size


@router.post("/{kid}/graph/relations/review-batch")
def review_relations_batch(
    kid: int,
    body: ReviewBatchBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """手动触发关系 LLM 二次复核（证据复核 pass）。

    构建完成后会自动跑一轮；本端点用于补跑/重跑（如换了更好的模型后）。
    ``status=all`` 覆盖全部状态（含 accepted——换模型后全量重评）。
    """
    from app.services.kb.kg import kg_config, kg_relation_reviewer
    from app.services.kb.kg.kg_llm_extractor import build_llm_extractor

    cfg = kg_config.get_graph_config(db, kid)
    llm, note = build_llm_extractor(db, cfg)
    if llm is None:
        raise HTTPException(
            status_code=409,
            detail=f"复核通道不可用（模型管理无可用对话模型）: {note}",
        )
    status = body.status if body.status in ("suggested", "accepted", "rejected") else None
    summary = kg_relation_reviewer.run_review(
        db,
        tenant_id=current_user.tenant_id,
        knowledge_id=kid,
        complete=llm.complete,
        relation_ids=body.relation_ids or None,
        status=status,  # None = 全部状态（body.status="all"）
        limit=int(body.limit or cfg.get("review_batch_size") or 200),
        concurrency=int(cfg.get("review_concurrency") or 4),
    )
    return summary


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
    """抽取失败/未就绪的切片清单（含失败原因，供「溯源」Tab 重试）。

    每条平级给出 ``stage`` / ``error_code`` / ``error``：前端按码取 i18n 文案，
    ``error`` 是技术原文（只作悬浮详情），不必钻 `details` 里的旧形状。
    阶段以两个标志位为准（结构是根因，优先报结构），`details` 内的两组键只作存证。
    """
    from sqlalchemy import select

    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_failure

    def _failure(s) -> dict:
        details = s.graph_extraction_details or {}
        if s.graph_structure_indexed is False:
            stage, keys = kg_failure.STAGE_STRUCTURE, ("error", "error_code")
        else:
            stage, keys = kg_failure.STAGE_VECTOR, ("vector_error", "vector_error_code")
        error = details.get(keys[0]) or ""
        code = details.get(keys[1]) or (
            kg_failure.classify_message(error, stage=stage) if error
            else kg_failure.UNKNOWN
        )
        return {"stage": stage, "error_code": code, "error": error}

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
                **_failure(s),
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
    """仅对指定文档重抽图谱：先撤销其贡献，再重建（后台执行）。

    图谱是从**切片**抽的：文档摄取失败时 ``kms_segment`` 为空，后台任务会
    扫到 0 个切片并"成功"结束（entities=0），前端却拿到 200 被误导——
    故此处对「无切片」直接 409，把「先重试解析」显式交回用户。
    解析**进行中**也 409：此时可能已有部分切片，直接放行会与摄取完成后
    自动提交的图谱构建撞锁（后台静默吞掉，前端不知道图谱没自动建）。
    """
    from sqlalchemy import select

    from app.models.kb.kb_document import KbDocument
    from app.services.kb.kg.kg_build_service import KgBuildService, submit_build

    tenant_id = _tenant_id(current_user)
    doc = db.execute(
        select(KbDocument).where(
            KbDocument.uuid_code == body.document_uuid,
            KbDocument.knowledge_id == kid,
            KbDocument.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if doc is not None and doc.status == "processing":
        raise HTTPException(
            status_code=409,
            detail="文档仍在解析中，请等解析完成后再抽取图谱",
        )
    if KgBuildService(db, tenant_id, kid).count_segments(body.document_uuid) == 0:
        reason = (doc.error_detail if doc is not None else None) or "文档尚无切片"
        raise HTTPException(
            status_code=409,
            detail=f"该文档没有可抽取的切片（{reason}）；"
                   "请先在「文档」面板重试解析，解析成功后再抽取图谱",
        )

    out = submit_build(
        tenant_id=tenant_id, knowledge_id=kid, action="rebuild",
        document_uuid=body.document_uuid,
    )
    if not out.get("accepted"):
        raise HTTPException(status_code=409, detail=out.get("reason", "任务冲突"))
    return out


# ── KB 级图谱配置（存 pipeline_config["graph"]，不新增列）────────────────

class GraphConfigPatch(BaseModel):
    # 「schema」与 BaseModel.schema() 方法重名（Pydantic v2 UserWarning），
    # 字段改名 schema_text + 别名兼容：入参仍收 "schema"（前端契约不变），
    # model_dump(by_alias=True) 仍产出 "schema" 键（kg_config 存储键不变）。
    model_config = ConfigDict(populate_by_name=True)

    extractor_type: Optional[str] = None
    model_spec: Optional[Dict[str, Any]] = None
    schema_source: Optional[str] = None
    catalog_id: Optional[int] = None
    schema_text: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("schema", "schema_text"),
        serialization_alias="schema",
    )
    concurrency_count: Optional[int] = None
    timeout_seconds: Optional[int] = None
    max_output_tokens: Optional[int] = None
    max_text_chars: Optional[int] = None
    max_entities: Optional[int] = None
    max_relations: Optional[int] = None
    max_continuation_rounds: Optional[int] = None
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


@router.get("/{kid}/graph/prompt-preview")
def prompt_preview(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """按当前配置拼装的**最终生效抽取提示词**（「输出当前抽取所用的提示词」）。

    正文用占位符：真实提示词 = 本返回值把占位符换成切片正文（截到
    ``max_text_chars``）。构建服务实际调用的是同一份 ``build_prompt``，
    不存在「预览与生效不一致」的第二口径。
    """
    from app.services.kb.kg.kg_extractor import build_schema_hint
    from app.services.kb.kg.kg_llm_extractor import build_prompt
    from app.services.kb.kg.kg_config import get_graph_config

    cfg = get_graph_config(db, kid)
    hint = build_schema_hint(
        db,
        schema_source=cfg.get("schema_source", "free_text"),
        catalog_id=cfg.get("catalog_id"),
        free_text=cfg.get("schema", "") or "",
        tenant_id=current_user.tenant_id,
    )
    max_text = int(cfg.get("max_text_chars") or 0)
    placeholder = f"（此处为切片正文占位：真实构建时替换为切片原文，最多 {max_text} 字）"
    prompt = build_prompt(
        placeholder,
        schema_hint=hint,
        max_entities=int(cfg.get("max_entities") or 0),
        max_relations=int(cfg.get("max_relations") or 0),
        max_text_chars=max_text,
    )
    return {
        "prompt": prompt,
        "schema_source": cfg.get("schema_source"),
        "config": {
            "max_output_tokens": cfg.get("max_output_tokens"),
            "max_text_chars": max_text,
            "max_entities": cfg.get("max_entities"),
            "max_relations": cfg.get("max_relations"),
            "max_continuation_rounds": cfg.get("max_continuation_rounds"),
            "concurrency_count": cfg.get("concurrency_count"),
            "timeout_seconds": cfg.get("timeout_seconds"),
        },
    }


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

    # by_alias=True：schema_text 字段以别名 "schema" 落键（kg_config 存储键契约）
    patch = {k: v for k, v in body.model_dump(by_alias=True).items() if v is not None}
    return save_graph_config(db, kid, patch)


# ── 图查询：子图 / 路径 / 邻接 / 类型分布（spec §6.3）────────────────────

@router.get("/{kid}/graph/documents/{uuid_code}")
def graph_document(
    kid: int,
    uuid_code: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """单文档实体与关系（文档弹窗专用，无条数截断）。

    * ``entities``：source_document_ids 含本文档的实体 **∪** 本文档关系的端点
      实体（端点实体可能在其他文档中首次创建——没有它图谱连线会被丢弃）；
    * ``relations``：source_document_ids 含本文档的关系。

    与文档列表页的 graph.entities/relations 计数（jsonb 聚合）口径一致。
    非 PG 后端（单测 SQLite）退化为全量加载后 Python 过滤。
    """
    from sqlalchemy import select, text

    from app.models.kb.kb_document import KbDocument

    svc = _svc(db, current_user, kid)
    doc_stmt = select(KbDocument).where(
        KbDocument.uuid_code == uuid_code,
        KbDocument.knowledge_id == svc.knowledge_id,
    )
    if svc.tenant_id is not None:
        doc_stmt = doc_stmt.where(KbDocument.tenant_id == svc.tenant_id)
    if db.execute(doc_stmt).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    needle = json.dumps([uuid_code])
    ent_stmt = select(KgEntity).where(KgEntity.knowledge_id == svc.knowledge_id)
    rel_stmt = select(KgTriple).where(KgTriple.knowledge_id == svc.knowledge_id)
    if svc.tenant_id is not None:
        ent_stmt = ent_stmt.where(KgEntity.tenant_id == svc.tenant_id)
        rel_stmt = rel_stmt.where(KgTriple.tenant_id == svc.tenant_id)

    if db.get_bind().dialect.name == "postgresql":
        ents = list(db.execute(
            ent_stmt.where(text("source_document_ids @> CAST(:doc_needle AS jsonb)")),
            {"doc_needle": needle},
        ).scalars())
        rels = list(db.execute(
            rel_stmt.where(text("source_document_ids @> CAST(:doc_needle2 AS jsonb)")),
            {"doc_needle2": needle},
        ).scalars())
    else:  # SQLite 等：退化为加载后 Python 过滤（测试规模内无碍）
        ents = [e for e in db.execute(ent_stmt).scalars()
                if uuid_code in (e.source_document_ids or [])]
        rels = [t for t in db.execute(rel_stmt).scalars()
                if uuid_code in (t.source_document_ids or [])]

    # 关系端点实体补桩（跨文档共享实体）：图谱连线两端必须有节点
    ent_ids = {e.id for e in ents}
    endpoint_ids = {t.from_entity_id for t in rels} | {t.to_entity_id for t in rels}
    missing = endpoint_ids - ent_ids
    if missing:
        stub_stmt = select(KgEntity).where(
            KgEntity.knowledge_id == svc.knowledge_id,
            KgEntity.id.in_(list(missing)),
        )
        if svc.tenant_id is not None:
            stub_stmt = stub_stmt.where(KgEntity.tenant_id == svc.tenant_id)
        ents.extend(db.execute(stub_stmt).scalars().all())

    names = _entity_names(svc, rels)
    ents.sort(key=lambda e: e.id)
    rels.sort(key=lambda t: t.id)
    return {
        "document_id": uuid_code,
        "entities": [_entity_out(e) for e in ents],
        "relations": [_relation_out(t, names) for t in rels],
    }


@router.get("/{kid}/graph/subgraph")
def graph_subgraph(
    kid: int,
    entity_ids: str = Query(..., description="逗号分隔的实体 ID"),
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """以实体为种子取子图；返回 {nodes, edges}（结构与标准中心 graph() 对齐）。"""
    ids = [int(x) for x in entity_ids.split(",") if x.strip().isdigit()]
    return _svc(db, current_user, kid).subgraph(ids, depth=depth, limit=limit)


@router.get("/{kid}/graph/full")
def graph_full(
    kid: int,
    limit: int = Query(200, ge=1, le=2000),
    type_code: Optional[str] = Query(None, description="只保留该类型的实体"),
    relation_code: Optional[str] = Query(None, description="只保留该关系类型的边"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """全库图（无种子）：节点按度数截断到 limit，返回 {nodes, edges}。"""
    return _svc(db, current_user, kid).full_graph(
        limit=limit, type_code=type_code, relation_code=relation_code,
    )


@router.get("/{kid}/graph/subgraph/seed")
def graph_seed_subgraph(
    kid: int,
    seed_ids: str = Query(..., description="逗号分隔的种子实体 ID"),
    depth: int = Query(2, ge=1, le=3),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """种子子图（多跳起点；与 /subgraph 同结构，供图视图「以此为种子扩展」用）。"""
    ids = [int(x) for x in seed_ids.split(",") if x.strip().isdigit()]
    return _svc(db, current_user, kid).subgraph(ids, depth=depth, limit=limit)


@router.get("/{kid}/graph/entities/{entity_id}/neighbors")
def graph_neighbors(
    kid: int,
    entity_id: int,
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """单实体邻接子图（检视面板「相邻关系」）。"""
    return _svc(db, current_user, kid).neighbors(entity_id, depth=depth, limit=limit)


@router.get("/{kid}/graph/entities/{entity_id}/mentions")
def graph_entity_mentions(
    kid: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """实体溯源：它被哪些切片提及（含切片正文与抽取依据）。"""
    svc = _svc(db, current_user, kid)
    if svc.get_entity(entity_id) is None:
        raise HTTPException(status_code=404, detail="实体不存在")
    return {"items": svc.entity_mentions(entity_id)}


@router.get("/{kid}/graph/relations/{relation_id}/mentions")
def graph_relation_mentions(
    kid: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """关系溯源：它被哪些切片提及（与实体提及同契约）。"""
    svc = _svc(db, current_user, kid)
    if svc.get_triple(relation_id) is None:
        raise HTTPException(status_code=404, detail="关系不存在")
    return {"items": svc.triple_mentions(relation_id)}


class PathsBody(BaseModel):
    from_entity_id: int = Field(..., description="起点实体 ID")
    to_entity_id: int = Field(..., description="终点实体 ID")
    max_depth: int = Field(2, ge=1, le=3)
    limit: int = Field(20, ge=1, le=100)


@router.post("/{kid}/graph/paths")
def graph_paths(
    kid: int,
    body: PathsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """两实体间路径查询（≤3 跳）。"""
    return {
        "paths": _svc(db, current_user, kid).paths(
            body.from_entity_id, body.to_entity_id,
            max_depth=body.max_depth, limit=body.limit,
        )
    }


@router.get("/{kid}/graph/labels")
def graph_labels(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """实体类型分布（对齐 Yuxi /graph/labels）。"""
    return {"items": _svc(db, current_user, kid).labels()}


# ── CDM 双向校验（spec §6.5，沿用 meta_relation_check 词表）──────────────

@router.get("/{kid}/graph/cdm-check")
def graph_cdm_check(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """图谱实例层 <-> CDM 模式层校验：hit / missing / conflict 三态。"""
    from app.services.kb.kg.kg_cdm_check import run_cdm_check

    return run_cdm_check(db, kid, _tenant_id(current_user))


# ── 图谱导出（spec §6.3 生态对接）────────────────────────────────────────

@router.get("/{kid}/graph/export")
def graph_export(
    kid: int,
    fmt: str = Query("json", description="json|csv|graphml"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """导出图谱实例（JSON 三元组 / CSV 边列表 / GraphML），供外部消费。"""
    svc = _svc(db, current_user, kid)
    entities = svc.list_entities(limit=10000)
    triples = svc.list_triples(limit=10000)
    names = {e.id: e.name for e in entities}

    if fmt == "csv":
        lines = ["source,source_type,relation_type,target,target_type,weight,status"]
        for t in triples:
            lines.append(
                "{},{},{},{},{},{},{}".format(
                    names.get(t.from_entity_id, ""),
                    _type_of_id(svc, t.from_entity_id),
                    t.relation_code or "",
                    names.get(t.to_entity_id, ""),
                    _type_of_id(svc, t.to_entity_id),
                    t.weight if t.weight is not None else "",
                    t.status,
                )
            )
        return {"format": "csv", "content": "\n".join(lines)}

    if fmt == "graphml":
        from xml.sax.saxutils import escape

        types = {
            e.id: (e.type_code or "") for e in entities
        }
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"'
            ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<key id="d0" for="node" attr.name="label" attr.type="string"/>'
            '<key id="d1" for="node" attr.name="type" attr.type="string"/>'
            '<key id="d2" for="node" attr.name="status" attr.type="string"/>'
            '<key id="d3" for="edge" attr.name="relation" attr.type="string"/>'
            '<key id="d4" for="edge" attr.name="weight" attr.type="double"/>',
            '<graph edgedefault="directed">',
        ]
        for e in entities:
            lines.append(
                f'<node id="n{e.id}">'
                f'<data key="d0">{escape(e.name)}</data>'
                f'<data key="d1">{escape(types.get(e.id, ""))}</data>'
                f'<data key="d2">{escape(e.status)}</data>'
                "</node>"
            )
        for t in triples:
            weight = "" if t.weight is None else f"{t.weight:.4f}"
            lines.append(
                f'<edge source="n{t.from_entity_id}" target="n{t.to_entity_id}">'
                f'<data key="d3">{escape(t.relation_code or "")}</data>'
                f'<data key="d4">{weight}</data>'
                "</edge>"
            )
        lines.append("</graph></graphml>")
        return {"format": "graphml", "content": "\n".join(lines)}

    return {
        "format": "json",
        "entities": [
            {
                "id": e.id, "name": e.name, "type": e.type_code or "",
                "aliases": e.aliases or [], "properties": e.properties or {},
                "status": e.status,
            }
            for e in entities
        ],
        "relations": [
            {
                "id": t.id,
                "source": t.from_entity_id, "target": t.to_entity_id,
                "relation_type": t.relation_code or "", "predicate": t.predicate,
                "weight": t.weight, "status": t.status,
            }
            for t in triples
        ],
    }


def _type_of_id(svc, entity_id: Optional[int]) -> str:
    e = svc.get_entity(entity_id) if entity_id is not None else None
    return (e.type_code or "") if e is not None else ""


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
    from app.services.kb.kg.kg_config import get_build_meta

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

    # 最近一次构建的运行元信息（时间/耗时/失败环节），供概览「上次构建」展示
    meta = get_build_meta(db, kid)
    failed_step = ""
    if int(meta.get("structure_failed") or 0) > 0:
        failed_step = "structure"
    elif int(meta.get("vector_failed") or 0) > 0:
        failed_step = "vector"

    return {
        "state": state,
        "running": running,
        "neo4j_available": neo4j_ok,
        "segments": total,
        "structure_done": structure_done,
        "vector_done": vector_done,
        "failed": failed,
        "last_build_at": meta.get("finished_at"),
        "last_build_action": meta.get("action"),
        "last_build_duration": meta.get("duration_seconds"),
        "last_failed_step": failed_step,
        "last_failed_count": int(meta.get("structure_failed") or 0)
        + int(meta.get("vector_failed") or 0),
    }
