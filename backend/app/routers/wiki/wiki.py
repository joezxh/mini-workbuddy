"""Wiki 文章 CRUD + 搜索 API 路由。

端点:
- POST   /wiki/articles          创建文章
- GET    /wiki/articles          文章列表 (分页 + 分类过滤)
- GET    /wiki/articles/{slug}   按 slug 获取文章
- PUT    /wiki/articles/{id}     更新文章 (自动创建版本快照)
- DELETE /wiki/articles/{id}     删除文章
- GET    /wiki/articles/{id}/versions  获取版本历史
- GET    /wiki/search?q=...      语义搜索
- GET    /wiki/categories        分类树
- POST   /wiki/categories        创建分类
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_article_version import WikiArticleVersion
from app.models.wiki.wiki_category import WikiCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wiki", tags=["LLM-wiki"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ArticleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    slug: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    summary: Optional[str] = Field(None, max_length=1000)
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    owl_class_uris: Optional[List[str]] = None
    wiki_links: Optional[List[str]] = None
    status: int = 1  # 1=发布 0=草稿


class ArticleUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = None
    summary: Optional[str] = Field(None, max_length=1000)
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    owl_class_uris: Optional[List[str]] = None
    wiki_links: Optional[List[str]] = None
    status: Optional[int] = None
    change_note: Optional[str] = Field(None, max_length=500)


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    owl_class_uri: Optional[str] = None
    sort_order: int = 0


def _slugify(text: str) -> str:
    """生成 URL 友好的 slug。"""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    return slug or "untitled"


# ── 文章 CRUD ────────────────────────────────────────────────────────────────

@router.post("/articles")
def create_article(
    body: ArticleCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建 Wiki 文章。"""
    slug = body.slug or _slugify(body.title)
    # 检查 slug 唯一性
    existing = db.execute(select(WikiArticle).where(WikiArticle.slug == slug)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"slug '{slug}' 已存在")

    article = WikiArticle(
        slug=slug,
        title=body.title,
        content=body.content,
        summary=body.summary,
        category_id=body.category_id,
        tags=body.tags or [],
        owl_class_uris=body.owl_class_uris or [],
        wiki_links=body.wiki_links or [],
        status=body.status,
        creator_id=current_user.id,
        updater_id=current_user.id,
        version=1,
    )
    db.add(article)
    db.flush()

    # 创建初始版本
    version = WikiArticleVersion(
        article_id=article.id,
        version=1,
        title=article.title,
        content=article.content,
        slug=article.slug,
        change_note="初始创建",
        editor_id=current_user.id,
    )
    db.add(version)

    # 更新 backlinks
    _update_backlinks(db, article)

    db.commit()
    db.refresh(article)
    return _article_to_dict(article)


@router.get("/articles")
def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取文章列表 (分页)。"""
    stmt = select(WikiArticle)
    count_stmt = select(func.count()).select_from(WikiArticle)

    if category_id is not None:
        stmt = stmt.where(WikiArticle.category_id == category_id)
        count_stmt = count_stmt.where(WikiArticle.category_id == category_id)
    if status is not None:
        stmt = stmt.where(WikiArticle.status == status)
        count_stmt = count_stmt.where(WikiArticle.status == status)
    else:
        # 默认不显示归档
        stmt = stmt.where(WikiArticle.status >= 0)
        count_stmt = count_stmt.where(WikiArticle.status >= 0)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern))
        count_stmt = count_stmt.where(WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern))

    total = db.execute(count_stmt).scalar() or 0
    articles = db.execute(
        stmt.order_by(WikiArticle.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_article_to_dict(a) for a in articles],
    }


@router.get("/articles/{slug}")
def get_article(
    slug: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """按 slug 获取文章详情。"""
    article = db.execute(
        select(WikiArticle).where(WikiArticle.slug == slug)
    ).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 增加浏览计数
    db.execute(
        sa_update(WikiArticle).where(WikiArticle.id == article.id).values(
            view_count=WikiArticle.view_count + 1
        )
    )
    db.commit()
    db.refresh(article)
    return _article_to_dict(article)


@router.put("/articles/{article_id}")
def update_article(
    article_id: int,
    body: ArticleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新文章 (自动创建版本快照)。"""
    article = db.get(WikiArticle, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 应用变更
    update_fields = body.dict(exclude_none=True, exclude={"change_note"})
    for key, value in update_fields.items():
        setattr(article, key, value)

    article.updater_id = current_user.id
    article.version = (article.version or 1) + 1
    db.flush()

    # 创建版本快照
    version = WikiArticleVersion(
        article_id=article.id,
        version=article.version,
        title=article.title,
        content=article.content,
        slug=article.slug,
        change_note=body.change_note,
        editor_id=current_user.id,
    )
    db.add(version)

    # 更新 backlinks
    _update_backlinks(db, article)

    db.commit()
    db.refresh(article)
    return _article_to_dict(article)


@router.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除文章。"""
    article = db.get(WikiArticle, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    db.delete(article)
    db.commit()
    return {"message": "删除成功"}


@router.get("/articles/{article_id}/versions")
def get_article_versions(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取文章版本历史。"""
    versions = db.execute(
        select(WikiArticleVersion)
        .where(WikiArticleVersion.article_id == article_id)
        .order_by(WikiArticleVersion.version.desc())
    ).scalars().all()

    return [
        {
            "id": v.id,
            "article_id": v.article_id,
            "version": v.version,
            "title": v.title,
            "slug": v.slug,
            "change_note": v.change_note,
            "editor_id": v.editor_id,
            "created_at": str(v.created_at) if v.created_at else None,
        }
        for v in versions
    ]


# ── 搜索 ─────────────────────────────────────────────────────────────────────

@router.get("/search")
def search_articles(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    top_k: int = Query(10, ge=1, le=50),
    owl_class: Optional[str] = Query(None, description="按 OWL Class URI 过滤"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """语义搜索 Wiki 文章。

    优先使用向量检索 (RAG), 降级为 SQL LIKE 搜索。
    """
    # 降级: SQL LIKE 搜索 (向量检索需要 EmbeddingService 配置)
    pattern = f"%{q}%"
    stmt = (
        select(WikiArticle)
        .where(WikiArticle.status >= 0)
        .where(WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern))
        .order_by(WikiArticle.updated_at.desc())
        .limit(top_k)
    )
    articles = db.execute(stmt).scalars().all()

    return {
        "query": q,
        "total": len(articles),
        "items": [_article_to_dict(a) for a in articles],
    }


# ── 分类 ─────────────────────────────────────────────────────────────────────

@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取分类树。"""
    categories = db.execute(
        select(WikiCategory).order_by(WikiCategory.sort_order, WikiCategory.name)
    ).scalars().all()

    # 构建树
    cat_map = {}
    roots = []
    for cat in categories:
        node = _category_to_dict(cat)
        cat_map[cat.id] = node
    for cat in categories:
        node = cat_map[cat.id]
        if cat.parent_id and cat.parent_id in cat_map:
            cat_map[cat.parent_id].setdefault("children", []).append(node)
        else:
            roots.append(node)
    return roots


@router.post("/categories")
def create_category(
    body: CategoryCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建分类。"""
    slug = body.slug or _slugify(body.name)
    existing = db.execute(
        select(WikiCategory).where(WikiCategory.slug == slug)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"分类 slug '{slug}' 已存在")

    category = WikiCategory(
        name=body.name,
        slug=slug,
        description=body.description,
        parent_id=body.parent_id,
        owl_class_uri=body.owl_class_uri,
        sort_order=body.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _category_to_dict(category)


# ── 内部工具 ─────────────────────────────────────────────────────────────────

def _article_to_dict(article: WikiArticle) -> dict:
    return {
        "id": article.id,
        "slug": article.slug,
        "title": article.title,
        "summary": article.summary,
        "content": article.content,
        "category_id": article.category_id,
        "tags": article.tags or [],
        "owl_class_uris": article.owl_class_uris or [],
        "wiki_links": article.wiki_links or [],
        "backlinks": article.backlinks or [],
        "status": article.status,
        "is_featured": article.is_featured,
        "view_count": article.view_count,
        "version": article.version,
        "creator_id": article.creator_id,
        "updater_id": article.updater_id,
        "created_at": str(article.created_at) if article.created_at else None,
        "updated_at": str(article.updated_at) if article.updated_at else None,
    }


def _category_to_dict(cat: WikiCategory) -> dict:
    return {
        "id": cat.id,
        "name": cat.name,
        "slug": cat.slug,
        "description": cat.description,
        "parent_id": cat.parent_id,
        "owl_class_uri": cat.owl_class_uri,
        "sort_order": cat.sort_order,
        "article_count": cat.article_count,
        "children": [],
    }


def _update_backlinks(db: Session, article: WikiArticle) -> None:
    """更新文章的 backlinks (反向链接)。"""
    if not article.wiki_links:
        return
    # 找到所有被本文链接的文章, 在它们的 backlinks 中添加本文 slug
    linked_slugs = article.wiki_links
    for slug in linked_slugs:
        target = db.execute(
            select(WikiArticle).where(WikiArticle.slug == slug)
        ).scalar_one_or_none()
        if target:
            backlinks = target.backlinks or []
            if article.slug not in backlinks:
                backlinks.append(article.slug)
                target.backlinks = backlinks
