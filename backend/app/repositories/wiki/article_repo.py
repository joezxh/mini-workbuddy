"""WikiArticle 数据访问层（管理后台）。"""
from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_category import WikiCategory


class WikiArticleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, article_id: int) -> Optional[WikiArticle]:
        return self.db.get(WikiArticle, article_id)

    def get_by_slug(self, slug: str) -> Optional[WikiArticle]:
        return self.db.execute(
            select(WikiArticle).where(WikiArticle.slug == slug)
        ).scalar_one_or_none()

    def list_filtered(
        self,
        page: int = 1,
        page_size: int = 20,
        knowledge_id: Optional[int] = None,
        category_id: Optional[int] = None,
        status: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[int, List[WikiArticle]]:
        stmt = select(WikiArticle)
        count_stmt = select(func.count()).select_from(WikiArticle)

        if category_id is not None:
            stmt = stmt.where(WikiArticle.category_id == category_id)
            count_stmt = count_stmt.where(WikiArticle.category_id == category_id)
        if knowledge_id is not None:
            join = WikiCategory.id == WikiArticle.category_id
            stmt = stmt.join(WikiCategory, join).where(WikiCategory.knowledge_id == knowledge_id)
            count_stmt = count_stmt.join(WikiCategory, join).where(
                WikiCategory.knowledge_id == knowledge_id
            )
        if status is not None:
            stmt = stmt.where(WikiArticle.status == status)
            count_stmt = count_stmt.where(WikiArticle.status == status)
        else:
            stmt = stmt.where(WikiArticle.status >= 0)
            count_stmt = count_stmt.where(WikiArticle.status >= 0)
        if keyword:
            pattern = f"%{keyword}%"
            cond = WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern)
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        total = self.db.execute(count_stmt).scalar() or 0
        items = self.db.execute(
            stmt.order_by(WikiArticle.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()
        return total, items
