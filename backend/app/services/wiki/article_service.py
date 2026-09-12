"""WikiArticle 业务逻辑层（用户侧 + 管理后台共用）。

承接原 ``wiki.py`` 的内联逻辑，保持对外响应形状不变：
- 列表 / 详情均含 ``content`` 字段（与重构前 ``_article_to_dict`` 一致）
- 创建 / 更新自动写入 ``kms_article_version`` 快照
- 更新 ``wiki_links`` 后刷新对方 ``backlinks``（G5 只加不清的已知行为保留）
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_article_version import WikiArticleVersion
from app.repositories.wiki.article_repo import WikiArticleRepository


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "untitled"


def _serialize(a: WikiArticle, include_content: bool = False) -> dict:
    d = {
        "id": a.id,
        "slug": a.slug,
        "title": a.title,
        "summary": a.summary,
        "category_id": a.category_id,
        "tags": a.tags or [],
        "owl_class_uris": a.owl_class_uris or [],
        "wiki_links": a.wiki_links or [],
        "backlinks": a.backlinks or [],
        "status": a.status,
        "is_featured": a.is_featured,
        "view_count": a.view_count,
        "version": a.version,
        "creator_id": a.creator_id,
        "updater_id": a.updater_id,
        "created_at": str(a.created_at) if a.created_at else None,
        "updated_at": str(a.updated_at) if a.updated_at else None,
    }
    if include_content:
        d["content"] = a.content
    return d


def _serialize_version(v: WikiArticleVersion) -> dict:
    return {
        "id": v.id,
        "article_id": v.article_id,
        "version": v.version,
        "title": v.title,
        "slug": v.slug,
        "change_note": v.change_note,
        "editor_id": v.editor_id,
        "created_at": str(v.created_at) if v.created_at else None,
    }


class WikiArticleService:
    """文章 CRUD / 版本 / 搜索。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = WikiArticleRepository(db)

    def create(self, data: dict, user) -> dict:
        slug = data.get("slug") or _slugify(data["title"])
        if self.repo.get_by_slug(slug):
            raise HTTPException(status_code=409, detail=f"slug '{slug}' 已存在")
        article = WikiArticle(
            slug=slug,
            title=data["title"],
            content=data.get("content"),
            summary=data.get("summary"),
            category_id=data.get("category_id"),
            tags=data.get("tags") or [],
            owl_class_uris=data.get("owl_class_uris") or [],
            wiki_links=data.get("wiki_links") or [],
            status=data.get("status", 1),
            creator_id=user.id,
            updater_id=user.id,
            version=1,
        )
        self.db.add(article)
        self.db.flush()
        self._create_version(article, "初始创建", user.id, operation_type="create")
        self._update_backlinks(article)
        self._enqueue_index(article.id)
        self.db.commit()
        self.db.refresh(article)
        return _serialize(article, include_content=True)

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        category_id: Optional[int] = None,
        status: Optional[int] = None,
        tag: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> dict:
        # 注：原 list_articles 接受 tag 但未实际使用，此处保留相同契约（tag 透传不生效）。
        total, items = self.repo.list_filtered(
            page=page,
            page_size=page_size,
            category_id=category_id,
            status=status,
            keyword=keyword,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize(a, include_content=True) for a in items],
        }

    def get_by_slug(self, slug: str, incr_view: bool = True) -> dict:
        article = self.repo.get_by_slug(slug)
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        if incr_view:
            article.view_count = (article.view_count or 0) + 1
            self.db.commit()
            self.db.refresh(article)
        return _serialize(article, include_content=True)

    def get(self, article_id: int) -> dict:
        obj = self.repo.get_by_id(article_id)
        if not obj:
            raise HTTPException(status_code=404, detail="文章不存在")
        return _serialize(obj, include_content=True)

    def update(self, article_id: int, data: dict, change_note: Optional[str], user) -> dict:
        article = self.repo.get_by_id(article_id)
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        old_links = set(article.wiki_links or [])
        for key, value in data.items():
            if value is not None:
                setattr(article, key, value)
        article.updater_id = user.id
        article.version = (article.version or 1) + 1
        self.db.flush()
        self._create_version(article, change_note, user.id, operation_type="edit")
        self._update_backlinks(article, old_links)
        self._enqueue_index(article.id)
        self.db.commit()
        self.db.refresh(article)
        return _serialize(article, include_content=True)

    def delete(self, article_id: int) -> None:
        article = self.repo.get_by_id(article_id)
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        self.db.delete(article)
        self.db.commit()

    def list_versions(self, article_id: int) -> List[dict]:
        versions = self.db.execute(
            select(WikiArticleVersion)
            .where(WikiArticleVersion.article_id == article_id)
            .order_by(WikiArticleVersion.version.desc())
        ).scalars().all()
        return [_serialize_version(v) for v in versions]

    def search(self, q: str, top_k: int = 10, owl_class: Optional[str] = None) -> dict:
        # 降级：SQL LIKE（向量检索见 Stage 2 / G1）。owl_class 透传暂不参与过滤，保持原契约。
        pattern = f"%{q}%"
        stmt = (
            select(WikiArticle)
            .where(WikiArticle.status >= 0)
            .where(WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern))
            .order_by(WikiArticle.updated_at.desc())
            .limit(top_k)
        )
        articles = self.db.execute(stmt).scalars().all()
        return {
            "query": q,
            "total": len(articles),
            "items": [_serialize(a, include_content=True) for a in articles],
        }

    # ── 内部工具 ──────────────────────────────────────────────────────────────
    def _create_version(self, article: WikiArticle, change_note: Optional[str], editor_id, operation_type: str = "edit") -> None:
        version = WikiArticleVersion(
            article_id=article.id,
            version=article.version,
            title=article.title,
            content=article.content,
            slug=article.slug,
            change_note=change_note,
            editor_id=editor_id,
            operation_type=operation_type,
        )
        self.db.add(version)

    def _update_backlinks(self, article: WikiArticle, old_links: Optional[list] = None) -> None:
        """增量重算反向链接，消除 G5『只加不清』。

        - 移除已取消链接的目标文章中指向本文的 slug
        - 补充新链接目标文章中的反向链接
        仅触碰发生变化的文章，避免全表扫描。
        """
        new_links = set(article.wiki_links or [])
        removed = (set(old_links or []) - new_links)
        # 仅在链接发生变化时才需处理
        if not removed and not (new_links - set(old_links or [])):
            return
        for slug in removed:
            target = self.repo.get_by_slug(slug)
            if target and target.id != article.id and target.backlinks:
                target.backlinks = [s for s in target.backlinks if s != article.slug]
        for slug in new_links:
            target = self.repo.get_by_slug(slug)
            if target and target.id != article.id:
                backlinks = target.backlinks or []
                if article.slug not in backlinks:
                    backlinks.append(article.slug)
                    target.backlinks = backlinks

    def _enqueue_index(self, article_id: int) -> None:
        """异步触发 RAG 索引（不阻塞主写链路）。失败仅记日志，不影响写请求。"""
        try:
            from app.services.wiki.rag_ingestor import WikiRAGIngestor
            import threading

            threading.Thread(
                target=WikiRAGIngestor().index_article,
                args=(article_id,),
                daemon=True,
            ).start()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[WikiArticleService] 触发 RAG 索引失败(已降级): {e}")
