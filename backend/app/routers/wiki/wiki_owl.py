"""Wiki OWL 本体管理 API 路由。

端点:
- POST /wiki/owl/classes       注册 OWL Class
- GET  /wiki/owl/classes       列出所有 OWL Class
- GET  /wiki/owl/hierarchy     获取类层级树
- POST /wiki/owl/import-ttl    导入 TTL 本体文件
- GET  /wiki/owl/export-ttl    导出 TTL
- GET  /wiki/owl/stats         本体统计
- GET  /wiki/owl/articles/{class_uri}  按 OWL 类查询文章
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.wiki.wiki_article import WikiArticle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wiki/owl", tags=["Wiki OWL 本体"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class OwlClassCreateRequest(BaseModel):
    uri: str = Field(..., description="OWL Class URI")
    label: str = Field("", description="中文标签")
    comment: str = Field("", description="描述")
    parent_uris: List[str] = Field(default_factory=list, description="父类 URI 列表")


# ── 全局 OWL 引擎单例 ────────────────────────────────────────────────────────

_owl_engine = None


def get_owl_engine():
    """获取全局 WikiOwlEngine 单例。"""
    global _owl_engine
    if _owl_engine is None:
        from app.ai.knowledge.owl_engine import WikiOwlEngine
        _owl_engine = WikiOwlEngine()
    return _owl_engine


# ── OWL Class CRUD ───────────────────────────────────────────────────────────

@router.post("/classes")
def create_class(
    body: OwlClassCreateRequest,
    current_user: SysUser = Depends(get_current_user),
):
    """注册一个 OWL Class。"""
    engine = get_owl_engine()
    owl_class = engine.register_class(
        uri=body.uri,
        label=body.label,
        comment=body.comment,
        parent_uris=body.parent_uris,
    )
    return owl_class.to_dict()


@router.get("/classes")
def list_classes(
    current_user: SysUser = Depends(get_current_user),
):
    """列出所有已注册 OWL Class。"""
    engine = get_owl_engine()
    return [c.to_dict() for c in engine.list_classes()]


@router.get("/hierarchy")
def get_hierarchy(
    current_user: SysUser = Depends(get_current_user),
):
    """获取 OWL 类层级树。"""
    engine = get_owl_engine()
    return [node.to_dict() for node in engine.get_hierarchy()]


# ── TTL 导入/导出 ─────────────────────────────────────────────────────────────

@router.post("/import-ttl")
async def import_ttl(
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_user),
):
    """导入 TTL 本体文件。"""
    content = await file.read()
    try:
        ttl_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="TTL 文件必须为 UTF-8 编码")

    engine = get_owl_engine()
    try:
        added = engine.import_ttl(ttl_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"message": f"导入成功, 新增 {added} 条三元组", "added": added}


@router.get("/export-ttl")
def export_ttl(
    current_user: SysUser = Depends(get_current_user),
):
    """导出本体为 TTL 格式。"""
    engine = get_owl_engine()
    ttl = engine.export_ttl()
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=ttl,
        media_type="text/turtle",
        headers={"Content-Disposition": "attachment; filename=wiki-ontology.ttl"},
    )


# ── 统计 ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    current_user: SysUser = Depends(get_current_user),
):
    """获取本体统计信息。"""
    engine = get_owl_engine()
    return engine.stats()


# ── 按 OWL 类查询文章 ────────────────────────────────────────────────────────

@router.get("/articles/{class_uri:path}")
def get_articles_by_class(
    class_uri: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取属于指定 OWL 类的所有文章。"""
    # 使用 JSONB 包含查询
    articles = db.execute(
        select(WikiArticle)
        .where(WikiArticle.status >= 0)
        .where(WikiArticle.owl_class_uris.contains([class_uri]))
        .order_by(WikiArticle.updated_at.desc())
    ).scalars().all()

    return {
        "class_uri": class_uri,
        "total": len(articles),
        "items": [
            {
                "id": a.id,
                "slug": a.slug,
                "title": a.title,
                "summary": a.summary,
                "version": a.version,
                "updated_at": str(a.updated_at) if a.updated_at else None,
            }
            for a in articles
        ],
    }
