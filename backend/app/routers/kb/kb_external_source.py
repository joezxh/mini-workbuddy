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
from app.models.kb.kb_document import KbDocument
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.external_import_service import (
    ImportSummary,
    fetch_document,
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
    # 传入 knowledge_id 且 credentials 为空时，由服务端按 (tenant, knowledge_id, source_type)
    # 回退读取已保存（加密）凭据，使导入向导无需前端持有明文凭据即可浏览目录
    knowledge_id: Optional[int] = None


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


class CredentialsSaveBody(BaseModel):
    """新建/编辑知识库时固化平台凭据（spec 知识库管理：平台+凭据在 KB 创建时完成）。"""
    knowledge_id: int
    source_type: str
    credentials: Dict[str, Any]


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
    """浏览目录/文档（懒加载，只取当前层级）。

    凭据回退：``credentials`` 为空且提供 ``knowledge_id`` 时，由服务端按
    (tenant, knowledge_id, source_type) 读取已保存（加密）凭据（spec 知识库管理：
    导入时跳过「配置凭据」一步）。"""
    tenant_id = _tenant_id(current_user)
    _require_type(body.source_type)
    credentials = body.credentials or {}
    if not credentials and body.knowledge_id:
        credentials = load_credentials(
            db, tenant_id, body.knowledge_id, body.source_type
        ) or {}
    try:
        refs = await list_nodes(body.source_type, credentials, body.parent_id)
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


@router.get("/documents/{document_uuid}/content")
async def external_document_content(
    document_uuid: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """查看已导入外部文档的全文（按需回源拉取，不落库）。

    外部导入只保留切片，原文不落盘；全文按需从平台重新拉取，既不占本地
    存储，也能看到平台侧最新内容。凭据仍取已保存（加密）记录，前端不持明文。
    """
    tenant_id = _tenant_id(current_user)
    doc = (
        db.query(KbDocument)
        .filter(
            KbDocument.tenant_id == tenant_id,
            KbDocument.uuid_code == document_uuid,
        )
        .one_or_none()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    external = (doc.meta or {}).get("external") or {}
    source_type = external.get("source_type")
    external_doc_id = external.get("external_doc_id")
    if not source_type or not external_doc_id:
        raise HTTPException(
            status_code=422, detail="该文档不是外部导入文档，无外部全文可读取"
        )
    _require_type(source_type)

    credentials = load_credentials(db, tenant_id, doc.knowledge_id, source_type) or {}
    if not credentials:
        raise HTTPException(
            status_code=422, detail="缺少该平台的访问凭据，无法读取原文"
        )
    try:
        result = await fetch_document(source_type, credentials, external_doc_id)
    except DocSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "document_uuid": document_uuid,
        "title": result.title or doc.name,
        "markdown": result.markdown,
        "external_updated_at": result.updated_at,
        "source_type": source_type,
    }


@router.post("/credentials")
def save_kb_credentials(
    body: CredentialsSaveBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_UPLOAD)),
):
    """把平台凭据（Fernet 加密）固化到指定外部知识库（type=3 / connector）。

    供「新建/编辑知识库」向导在创建容器后立即调用；凭据只入不出，列表接口不回传明文。
    """
    tenant_id = _tenant_id(current_user)
    kb = db.get(WikiKnowledge, body.knowledge_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.type != 3 or kb.kb_format != "connector":
        raise HTTPException(
            status_code=422, detail="仅 type=3 / connector 形态的外部知识库可保存平台凭据"
        )
    if kb.external_type != body.source_type:
        raise HTTPException(
            status_code=422,
            detail=f"凭据平台({body.source_type})与知识库外部类型({kb.external_type})不一致",
        )
    save_credentials(
        db, tenant_id, body.knowledge_id, body.source_type, body.credentials
    )
    db.commit()
    return {"ok": True}


@router.get("/knowledges/{kid}/external-config")
def external_config(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_VIEW)),
):
    """返回该外部知识库的平台类型与是否已配置凭据，供导入向导判定是否跳过凭据步。"""
    tenant_id = _tenant_id(current_user)
    kb = db.get(WikiKnowledge, kid)
    if kb is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    has_credentials = False
    if kb.external_type:
        has_credentials = load_credentials(db, tenant_id, kid, kb.external_type) is not None
    return {"external_type": kb.external_type, "has_credentials": has_credentials}
