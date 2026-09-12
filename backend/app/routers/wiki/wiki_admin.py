"""Wiki 管理后台路由（知识库 / 目录 / 文章 管理）。

挂载: prefix="/wiki/admin"（router_registry 叠加 /api/v1 → /api/v1/wiki/admin）。

权限:
- 知识库增删改与启停: 管理员 (require_admin)
- 目录 / 文章管理: 登录用户 (get_current_user)；细粒度「知识库归属」校验为后续增强项
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_admin
from app.models.sys.sys_user import SysUser
from app.schemas.wiki.article import ArticleOut
from app.schemas.wiki.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.wiki.knowledge import KnowledgeCreate, KnowledgeOut, KnowledgeUpdate
from app.services.wiki.article_service import WikiArticleService
from app.services.wiki.category_service import WikiCategoryService
from app.services.wiki.knowledge_service import WikiKnowledgeService
from app.services.wiki.search_service import WikiSearchService

router = APIRouter(prefix="/wiki/admin", tags=["Wiki 管理后台"])


# ── 知识库管理 ──────────────────────────────────────────────────────────────
@router.post("/knowledge", response_model=KnowledgeOut, status_code=201)
def create_knowledge(
    body: KnowledgeCreate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    return WikiKnowledgeService(db).create(body, user)


@router.get("/knowledge")
def list_knowledge(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiKnowledgeService(db).list(page, page_size, status)


@router.get("/knowledge/{knowledge_id}", response_model=KnowledgeOut)
def get_knowledge(
    knowledge_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiKnowledgeService(db).get(knowledge_id)


@router.put("/knowledge/{knowledge_id}", response_model=KnowledgeOut)
def update_knowledge(
    knowledge_id: int,
    body: KnowledgeUpdate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    return WikiKnowledgeService(db).update(knowledge_id, body)


@router.patch("/knowledge/{knowledge_id}/status", response_model=KnowledgeOut)
def set_knowledge_status(
    knowledge_id: int,
    status: int = Query(..., description="1=启用 0=归档"),
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    return WikiKnowledgeService(db).set_status(knowledge_id, status)


@router.delete("/knowledge/{knowledge_id}", status_code=204)
def delete_knowledge(
    knowledge_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    WikiKnowledgeService(db).delete(knowledge_id)
    return None


# ── 目录管理（归属知识库）────────────────────────────────────────────────────
@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    body: CategoryCreate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiCategoryService(db).create(body, user)


@router.get("/categories", response_model=List[CategoryOut])
def list_category_tree(
    knowledge_id: int = Query(..., description="所属知识库 ID"),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiCategoryService(db).tree(knowledge_id)


@router.get("/categories/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiCategoryService(db).get(category_id)


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    body: CategoryUpdate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiCategoryService(db).update(category_id, body)


@router.patch("/categories/{category_id}/move", response_model=CategoryOut)
def move_category(
    category_id: int,
    parent_id: Optional[int] = Query(None, description="新父目录 ID，null=顶级"),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiCategoryService(db).move(category_id, parent_id)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    WikiCategoryService(db).delete(category_id)
    return None


# ── 文章管理（跨库筛选 / 按 ID 详情，G4 / G10）──────────────────────────────
@router.get("/articles")
def list_articles_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    knowledge_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiArticleService(db).list(page, page_size, knowledge_id, category_id, status, keyword)


@router.get("/articles/{article_id}", response_model=ArticleOut)
def get_article_admin(
    article_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiArticleService(db).get(article_id)


# ── 检索审计（RAG 测试 Tab 复用）──────────────────────────────────────────────
@router.get("/search-logs")
def list_search_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mode: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return WikiSearchService(db).history(page=page, page_size=page_size, mode=mode)
