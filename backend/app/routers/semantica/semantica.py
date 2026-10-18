"""Semantica 语义层 REST 端点（prefix /api/v1/semantic）。

安全约定（对标旧本体治理路由）：
- 所有端点要求登录且用户有租户（400 tenant_required）；
- 一切 semantica 读写经 ``TenantScope`` 解析命名空间，杜绝跨租户直查；
- semantica 或其存储后端（PG / Neo4j）不可用时返回 503（fail-closed），
  不静默降级。
"""
from __future__ import annotations

import tempfile
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.services.semantica import (
    SemanticaClient,
    SemanticaPipelineService,
    SemanticaUnavailable,
    SemanticExporter,
    SemanticRetriever,
    TenantScope,
)

router = APIRouter(prefix="/api/v1/semantic", tags=["语义/Semantica"])

_TENANT_REQUIRED = "tenant_required"


def _require_tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail=_TENANT_REQUIRED)
    return tenant_id


def _scope(tenant_id: int, ontology_code: str = "default") -> TenantScope:
    return TenantScope(tenant_id=tenant_id, ontology_code=ontology_code)


# ── 请求体 ────────────────────────────────────────────────────────────────
class ExtractRequest(BaseModel):
    text: str
    ontology_code: str = "default"
    options: Dict[str, Any] = Field(default_factory=dict)


class BuildRequest(BaseModel):
    text: str
    ontology_code: str = "default"
    steps: Optional[List[str]] = None


class SearchRequest(BaseModel):
    query_vector: List[float]
    ontology_code: str = "default"
    top_k: int = 10
    concept_uris: Optional[List[str]] = None
    kind: str = "entity"


class ExportRequest(BaseModel):
    data: Dict[str, Any]
    ontology_code: str = "default"
    fmt: str = "turtle"


# ── 端点 ──────────────────────────────────────────────────────────────────
@router.get("/health")
def health() -> Dict[str, Any]:
    """能力探测：semantica 是否可用、Neo4j 开关、向量/嵌入维度一致性。"""
    return {
        "available": SemanticaClient.is_available(),
        "neo4j_enabled": settings.NEO4J_ENABLED,
        "vector_dim": settings.SEMANTICA_VECTOR_DIM,
        "embedding_dim": settings.GPUSTACK_EMBEDDING_DIMENSION,
    }


@router.post("/extract/entities")
def extract_entities(
    req: ExtractRequest, current_user: SysUser = Depends(get_current_user)
):
    tid = _require_tenant_id(current_user)
    try:
        client = SemanticaClient(scope=_scope(tid, req.ontology_code))
        return {"entities": client.extract_entities(req.text, **req.options)}
    except SemanticaUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"semantica 不可用: {exc}")


@router.post("/extract/relations")
def extract_relations(
    req: ExtractRequest, current_user: SysUser = Depends(get_current_user)
):
    tid = _require_tenant_id(current_user)
    try:
        client = SemanticaClient(scope=_scope(tid, req.ontology_code))
        entities = client.extract_entities(req.text, **req.options)
        return {"relations": client.extract_relations(req.text, entities, **req.options)}
    except SemanticaUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"semantica 不可用: {exc}")


@router.post("/build")
def build(req: BuildRequest, current_user: SysUser = Depends(get_current_user)):
    """分步编排语义管道（抽取→冲突→去重→建图→向量）。重负载建议分批调用。"""
    tid = _require_tenant_id(current_user)
    try:
        svc = SemanticaPipelineService(db=None, scope=_scope(tid, req.ontology_code))
        report = svc.run(req.text, steps=req.steps)
        return {
            "ok": report.ok,
            "summary": report.summary,
            "timings": report.timings,
            "steps": report.steps,
        }
    except SemanticaUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"semantica 不可用: {exc}")
    except Exception as exc:  # noqa: BLE001 - 管道错误透传给调用方
        raise HTTPException(status_code=500, detail=f"语义管道失败: {exc}")


@router.post("/search")
def search(req: SearchRequest, current_user: SysUser = Depends(get_current_user)):
    tid = _require_tenant_id(current_user)
    try:
        retriever = SemanticRetriever(scope=_scope(tid, req.ontology_code))
        return {
            "results": retriever.search_by_vector(
                req.query_vector,
                top_k=req.top_k,
                concept_uris=req.concept_uris,
                kind=req.kind,
            )
        }
    except SemanticaUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"semantica 不可用: {exc}")


@router.post("/export")
def export(req: ExportRequest, current_user: SysUser = Depends(get_current_user)):
    tid = _require_tenant_id(current_user)
    try:
        tmp = tempfile.gettempdir()
        path = f"{tmp}/semantica_export_{uuid.uuid4().hex}.{req.fmt}"
        exporter = SemanticExporter(scope=_scope(tid, req.ontology_code))
        out = exporter.export(req.data, path, fmt=req.fmt)
        return {"path": out}
    except SemanticaUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"semantica 不可用: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
