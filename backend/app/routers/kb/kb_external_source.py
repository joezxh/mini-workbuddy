"""外部知识库文档导入路由（prefix /api/v1/kb/external-sources）。

驱动「外部知识库文档导入向导」：平台元数据 → 凭据测试 → 目录/文档浏览 →
导入（同一端点幂等：已存在则覆盖，不存在则新建）。

凭据只入不出：保存走 Fernet 加密，列表接口不回传明文。
平台域名在各 doc_sources 实现中硬编码，不接受任意 base_url（防 SSRF）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.connectors.doc_sources import (
    DocSourceError,
    list_providers,
    supported_source_types,
)
from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser
from app.services.kb.external_import_service import (
    ImportSummary,
    import_documents,
    list_external_documents,
    list_nodes,
    load_credentials,
    save_credentials,
    test_source,
)
from app.services.kb.kb_permissions import (
    KB_UPLOAD,
    KB_VIEW,
    require_kb_permission,
)

router = APIRouter(prefix="/api/v1/kb/external-sources", tags=["外部知识库文档导入"])
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


def _require_type(source_type: str) -> None:
    if source_type not in supported_source_types():
        raise HTTPException(status_code=400, detail=f"不支持的外部平台：{source_type}")


class CredentialsBody(BaseModel):
    source_type: str
    credentials: Dict[str, Any] = Field(default_factory=dict)


class NodesBody(CredentialsBody):
    parent_id: Optional[str] = None


class DocRef(BaseModel):
    doc_id: str
    title: str = ""


class ImportBody(BaseModel):
    knowledge_id: int
    source_type: str
    doc_refs: List[DocRef]
    # 留空则使用已保存（加密）的凭据，便于「重新选择文档」免重复填写
    credentials: Optional[Dict[str, Any]] = None
    chunker_type: str = "approx_token"
    chunker_params: Optional[Dict[str, Any]] = None
    save_credentials: bool = True


@router.get("/providers")
def providers(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """五个平台元数据 + 各自凭据字段 schema（驱动前端动态表单）。"""
    _tenant_id(current_user)
    return {"items": list_providers()}


@router.post("/test")
async def test_connection(
    body: CredentialsBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """连通性测试；结果 message 可直接回显前端。"""
    _tenant_id(current_user)
    _require_type(body.source_type)
    result = await test_source(body.source_type, body.credentials or {})
    return {"ok": result.ok, "message": result.message, "identity": result.identity}


@router.post("/nodes")
async def browse_nodes(
    body: NodesBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """浏览目录/文档（懒加载，只取当前层级）。"""
    _tenant_id(current_user)
    _require_type(body.source_type)
    try:
        refs = await list_nodes(body.source_type, body.credentials or {}, body.parent_id)
    except DocSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "items": [
            {
                "doc_id": r.doc_id,
                "title": r.title,
                "node_type": r.node_type,
                "parent_id": r.parent_id,
                "updated_at": r.updated_at,
                "url": r.url,
            }
            for r in refs
        ]
    }


@router.post("/import", response_model=ImportSummary)
async def import_external_documents(
    body: ImportBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """导入 / 重新导入：按映射表判定新建、覆盖或跳过。"""
    tenant_id = _tenant_id(current_user)
    _require_knowledge(db, body.knowledge_id)
    _require_type(body.source_type)

    credentials = body.credentials
    if not credentials:
        credentials = load_credentials(db, tenant_id, body.knowledge_id, body.source_type)
    if not credentials:
        raise HTTPException(status_code=400, detail="缺少平台凭据")

    summary = await import_documents(
        db,
        tenant_id,
        body.knowledge_id,
        body.source_type,
        credentials,
        [{"doc_id": r.doc_id, "title": r.title} for r in body.doc_refs],
        chunker_type=body.chunker_type,
        chunker_params=body.chunker_params,
        user_id=getattr(current_user, "user_id", None),
    )

    if body.save_credentials and body.credentials:
        save_credentials(db, tenant_id, body.knowledge_id, body.source_type,
                         body.credentials)
        db.commit()

    logger.info(
        "external import knowledge=%s source=%s total=%s created=%s updated=%s unchanged=%s failed=%s",
        body.knowledge_id, body.source_type, summary.total, summary.created,
        summary.updated, summary.unchanged, summary.failed,
    )
    return summary


@router.get("/knowledges/{kid}/external-documents")
def external_documents(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """该外部知识库已导入的文档列表（含状态，供面板展示与再次导入）。"""
    tenant_id = _tenant_id(current_user)
    _require_knowledge(db, kid)
    return {"items": list_external_documents(db, tenant_id, kid)}
