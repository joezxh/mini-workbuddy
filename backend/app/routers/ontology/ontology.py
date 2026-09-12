"""本体治理 REST 端点（P4，prefix /api/v1/ontology）。

安全约定（与 DataOps / 连接器一致）：
- 所有端点要求登录且用户有租户（400 tenant_required）；
- 子表（对象类型/属性/关系/CQ/版本）不直存 tenant_id，一律先按租户解析出本体，
  再以其 ontology_id 过滤子表（杜绝拿裸 ontology_id 跨租户直查，见 model.py 安全说明）；
- TTL 导入/导出/类增删走 `WikiOwlEngine`（rdflib 内核），`ttl_content` 为唯一真相源，
  类与标注索引由其派生重建。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.ontology.model import (
    OntologyCq,
    OntologyLinkType,
    OntologyObjectType,
    OntologyVersion,
)
from app.models.ontology.ontology import Ontology, OntologyClass
from app.models.sys.sys_user import SysUser

router = APIRouter(prefix="/api/v1/ontology", tags=["本体治理"])

TENANT_REQUIRED_DETAIL = "tenant_required"
DEFAULT_NS = "http://minworkbuddy.example/ontology/"


def _require_tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail=TENANT_REQUIRED_DETAIL)
    return tenant_id


def _owned_ontology(db: Session, tenant_id: int, ontology_id: int) -> Ontology:
    ont = db.get(Ontology, ontology_id)
    if ont is None or ont.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="ontology_not_found")
    return ont


def _slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", s.strip()) or "x"


def _engine_for(db: Session, tenant_id: int, ont: Ontology):
    """按本体的 code 构造持久化仓储 + OWL 引擎（懒导入避免启动期重依赖）。"""
    from app.services.ontology.ontology_repository import OntologyRepository
    from app.ai.knowledge.owl_engine import WikiOwlEngine

    repo = OntologyRepository(db, tenant_id, code=ont.code)
    return WikiOwlEngine.from_store(repo)


def _ns_for(ont: Ontology) -> str:
    ns = ont.namespace_uri or DEFAULT_NS
    return ns if ns.endswith(("#", "/")) else ns + "#"


# ── 请求体 ────────────────────────────────────────────────────────────────
class OntologyCreate(BaseModel):
    code: str = Field(..., description="本体编码（租户内唯一）")
    name: Optional[str] = None
    namespace: Optional[str] = None
    version: int = 1
    description: Optional[str] = None


class OntologyUpdate(BaseModel):
    name: Optional[str] = None
    namespace: Optional[str] = None
    version: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ClassCreate(BaseModel):
    name: str = Field(..., description="类标签/名称")
    comment: Optional[str] = None
    parent_uris: List[str] = Field(default_factory=list)


class ClassUpdate(BaseModel):
    comment: Optional[str] = None
    parent_uris: List[str] = Field(default_factory=list)


class ObjectTypeCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None


class ReviewDecision(BaseModel):
    decision: str = Field(..., description="accepted | rejected")


class VersionCreate(BaseModel):
    change_note: Optional[str] = None


# ── 序列化 ────────────────────────────────────────────────────────────────
def _serialize_ontology(ont: Ontology) -> Dict[str, Any]:
    return {
        "id": ont.id,
        "code": ont.code,
        "name": ont.name,
        "namespace": ont.namespace_uri,
        "version": ont.version,
        "status": ont.status,
        "source": ont.source,
        "description": ont.description,
        "ttl_content": ont.ttl_content,
        "created_at": ont.created_at.isoformat() if ont.created_at else None,
        "updated_at": ont.updated_at.isoformat() if ont.updated_at else None,
    }


# ── 本体 CRUD ─────────────────────────────────────────────────────────────
@router.get("")
def list_ontologies(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    rows = db.execute(select(Ontology).where(Ontology.tenant_id == tenant_id)).scalars().all()
    return [_serialize_ontology(r) for r in rows]


@router.post("", status_code=201)
def create_ontology(
    body: OntologyCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    ont = Ontology(
        tenant_id=tenant_id,
        code=body.code,
        name=body.name or body.code,
        namespace_uri=body.namespace,
        version=body.version,
        description=body.description,
        status="draft",
        source="manual",
        creator_id=current_user.user_id,
    )
    db.add(ont)
    db.commit()
    db.refresh(ont)
    return _serialize_ontology(ont)


@router.get("/{ontology_id}")
def get_ontology(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    return _serialize_ontology(_owned_ontology(db, tenant_id, ontology_id))


@router.put("/{ontology_id}")
def update_ontology(
    ontology_id: int,
    body: OntologyUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    ont = _owned_ontology(db, tenant_id, ontology_id)
    if body.name is not None:
        ont.name = body.name
    if body.namespace is not None:
        ont.namespace_uri = body.namespace
    if body.version is not None:
        ont.version = body.version
    if body.description is not None:
        ont.description = body.description
    if body.status is not None:
        ont.status = body.status
    ont.updater_id = current_user.user_id
    db.commit()
    db.refresh(ont)
    return _serialize_ontology(ont)


@router.delete("/{ontology_id}")
def delete_ontology(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    ont = _owned_ontology(db, tenant_id, ontology_id)
    db.delete(ont)
    db.commit()
    return {"deleted": ontology_id}


# ── TTL 导入 / 导出 ────────────────────────────────────────────────────────
@router.post("/{ontology_id}/import")
def import_ttl(
    ontology_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    ont = _owned_ontology(db, tenant_id, ontology_id)
    content = (file.file.read() or b"").decode("utf-8", errors="replace")
    try:
        engine = _engine_for(db, tenant_id, ont)
        added = engine.import_ttl(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"added": added}


@router.get("/{ontology_id}/export")
def export_ttl(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    from fastapi.responses import Response

    tenant_id = _require_tenant_id(current_user)
    ont = _owned_ontology(db, tenant_id, ontology_id)
    engine = _engine_for(db, tenant_id, ont)
    ttl = engine.export_ttl()
    return Response(
        content=ttl,
        media_type="text/turtle",
        headers={"Content-Disposition": f'attachment; filename="{ont.code}.ttl"'},
    )


# ── 类层级 ────────────────────────────────────────────────────────────────
@router.get("/{ontology_id}/classes")
def list_classes(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    rows = db.execute(
        select(OntologyClass).where(
            OntologyClass.tenant_id == tenant_id,
            OntologyClass.ontology_id == ontology_id,
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "uri": r.uri,
            "label": r.label,
            "name": r.label,
            "comment": r.comment,
            "parent_id": (r.parent_uris or [None])[0] if r.parent_uris else None,
            "parent_uris": list(r.parent_uris or []),
            "status": r.status,
        }
        for r in rows
    ]


@router.post("/{ontology_id}/classes", status_code=201)
def create_class(
    ontology_id: int,
    body: ClassCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    ont = _owned_ontology(db, tenant_id, ontology_id)
    uri = f"{_ns_for(ont)}{_slug(body.name)}"
    engine = _engine_for(db, tenant_id, ont)
    engine.register_class(uri, label=body.name, comment=body.comment or "", parent_uris=body.parent_uris)
    row = db.execute(
        select(OntologyClass).where(
            OntologyClass.tenant_id == tenant_id,
            OntologyClass.ontology_id == ontology_id,
            OntologyClass.uri == uri,
        )
    ).scalar_one_or_none()
    return {
        "id": row.id, "uri": row.uri, "label": row.label, "name": row.label,
        "comment": row.comment, "parent_uris": list(row.parent_uris or []), "status": row.status,
    }


@router.put("/{ontology_id}/classes/{class_id}")
def update_class(
    ontology_id: int,
    class_id: int,
    body: ClassUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    row = db.get(OntologyClass, class_id)
    if row is None or row.tenant_id != tenant_id or row.ontology_id != ontology_id:
        raise HTTPException(status_code=404, detail="class_not_found")
    engine = _engine_for(db, tenant_id, _owned_ontology(db, tenant_id, ontology_id))
    engine.register_class(row.uri, comment=body.comment or "", parent_uris=body.parent_uris)
    db.refresh(row)
    return {
        "id": row.id, "uri": row.uri, "label": row.label, "name": row.label,
        "comment": row.comment, "parent_uris": list(row.parent_uris or []), "status": row.status,
    }


@router.delete("/{ontology_id}/classes/{class_id}")
def delete_class(
    ontology_id: int,
    class_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    row = db.get(OntologyClass, class_id)
    if row is None or row.tenant_id != tenant_id or row.ontology_id != ontology_id:
        raise HTTPException(status_code=404, detail="class_not_found")
    engine = _engine_for(db, tenant_id, _owned_ontology(db, tenant_id, ontology_id))
    engine.unregister(row.uri)
    return {"deleted": class_id}


# ── 对象类型 / 关系 / CQ ──────────────────────────────────────────────────
@router.get("/{ontology_id}/object-types")
def list_object_types(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    rows = db.execute(
        select(OntologyObjectType).where(OntologyObjectType.ontology_id == ontology_id)
    ).scalars().all()
    return [
        {
            "id": r.id, "code": r.code, "name": r.name, "description": r.description,
            "parent_id": r.parent_id, "status": r.status, "source": r.source,
            "confidence": r.confidence, "evidence_json": r.evidence_json,
        }
        for r in rows
    ]


@router.post("/{ontology_id}/object-types", status_code=201)
def create_object_type(
    ontology_id: int,
    body: ObjectTypeCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    obj = OntologyObjectType(
        ontology_id=ontology_id,
        code=body.code or _slug(body.name),
        name=body.name,
        description=body.description,
        parent_id=body.parent_id,
        status="suggested",
        source="human",
        creator_id=current_user.user_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return {
        "id": obj.id, "code": obj.code, "name": obj.name, "description": obj.description,
        "parent_id": obj.parent_id, "status": obj.status, "source": obj.source,
    }


@router.get("/{ontology_id}/relations")
def list_relations(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    type_names = {
        r.id: r.name
        for r in db.execute(
            select(OntologyObjectType).where(OntologyObjectType.ontology_id == ontology_id)
        ).scalars().all()
    }
    rows = db.execute(
        select(OntologyLinkType).where(OntologyLinkType.ontology_id == ontology_id)
    ).scalars().all()
    out = []
    for r in rows:
        overlap = None
        if r.evidence_json and isinstance(r.evidence_json, dict):
            overlap = r.evidence_json.get("overlap_ratio")
        out.append({
            "id": r.id, "code": r.code, "name": r.name,
            "source_type": type_names.get(r.source_type_id, str(r.source_type_id)),
            "target_type": type_names.get(r.target_type_id, str(r.target_type_id)),
            "cardinality": r.cardinality, "status": r.status,
            "confidence": r.confidence, "overlap_ratio": overlap,
        })
    return out


@router.get("/{ontology_id}/cqs")
def list_cqs(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    rows = db.execute(
        select(OntologyCq).where(OntologyCq.ontology_id == ontology_id)
    ).scalars().all()
    return [
        {
            "id": r.id, "question": r.question,
            "object_type": (r.linked_object_types or [None])[0] if r.linked_object_types else None,
            "linked_object_types": list(r.linked_object_types or []),
            "status": r.status,
        }
        for r in rows
    ]


# ── 评审与版本 ────────────────────────────────────────────────────────────
@router.get("/{ontology_id}/review")
def list_review_items(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    items: List[Dict[str, Any]] = []

    def _collect(model, kind: str, name_field: str):
        for r in db.execute(
            select(model).where(model.ontology_id == ontology_id, model.status == "suggested")
        ).scalars().all():
            items.append({
                "id": r.id, "kind": kind, "name": getattr(r, name_field),
                "confidence": r.confidence, "evidence_json": r.evidence_json,
                "status": r.status,
            })

    _collect(OntologyObjectType, "object_type", "name")
    _collect(OntologyLinkType, "link_type", "name")
    return items


@router.post("/{ontology_id}/review/{item_id}")
def review_item(
    ontology_id: int,
    item_id: int,
    body: ReviewDecision,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    if body.decision not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="invalid_decision")
    # 候选可能落在对象类型 / 关系类型任一张表，按 id 定位（同租户本体下 id 空间独立）
    for model in (OntologyObjectType, OntologyLinkType):
        row = db.get(model, item_id)
        if row is not None and getattr(row, "ontology_id", None) == ontology_id:
            row.status = body.decision
            row.updater_id = current_user.user_id
            db.commit()
            return {"id": item_id, "status": body.decision}
    raise HTTPException(status_code=404, detail="review_item_not_found")


@router.get("/{ontology_id}/versions")
def list_versions(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    rows = db.execute(
        select(OntologyVersion).where(OntologyVersion.ontology_id == ontology_id)
    ).scalars().all()
    return [
        {
            "id": r.id, "label": r.version, "snapshot": r.snapshot_json,
            "change_note": r.change_note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/{ontology_id}/versions", status_code=201)
def create_version(
    ontology_id: int,
    body: VersionCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    _owned_ontology(db, tenant_id, ontology_id)
    snapshot = {
        "object_types": [
            {"code": r.code, "name": r.name, "status": r.status}
            for r in db.execute(
                select(OntologyObjectType).where(OntologyObjectType.ontology_id == ontology_id)
            ).scalars().all()
        ],
        "link_types": [
            {"code": r.code, "name": r.name, "cardinality": r.cardinality}
            for r in db.execute(
                select(OntologyLinkType).where(OntologyLinkType.ontology_id == ontology_id)
            ).scalars().all()
        ],
        "cqs": [
            {"question": r.question, "linked": list(r.linked_object_types or [])}
            for r in db.execute(
                select(OntologyCq).where(OntologyCq.ontology_id == ontology_id)
            ).scalars().all()
        ],
    }
    version = OntologyVersion(
        ontology_id=ontology_id,
        version=datetime.utcnow().strftime("v%Y%m%d-%H%M%S"),
        snapshot_json=snapshot,
        change_note=body.change_note,
        author_user_id=current_user.user_id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return {"id": version.id, "label": version.version, "snapshot": version.snapshot_json}
