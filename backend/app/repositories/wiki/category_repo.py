"""WikiCategory 数据访问层。"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wiki.wiki_category import WikiCategory


class WikiCategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: dict) -> WikiCategory:
        obj = WikiCategory(**data)
        self.db.add(obj)
        self.db.flush()
        return obj

    def get_by_id(self, category_id: int) -> Optional[WikiCategory]:
        return self.db.get(WikiCategory, category_id)

    def get_by_slug(self, slug: str) -> Optional[WikiCategory]:
        return self.db.execute(
            select(WikiCategory).where(WikiCategory.slug == slug)
        ).scalar_one_or_none()

    def list_by_knowledge(self, knowledge_id: int) -> List[WikiCategory]:
        return self.db.execute(
            select(WikiCategory)
            .where(WikiCategory.knowledge_id == knowledge_id)
            .order_by(WikiCategory.sort_order, WikiCategory.name)
        ).scalars().all()

    def list_all(self) -> List[WikiCategory]:
        return self.db.execute(
            select(WikiCategory).order_by(WikiCategory.sort_order, WikiCategory.name)
        ).scalars().all()

    def count_articles(self, category_id: int) -> int:
        from app.models.wiki.wiki_article import WikiArticle

        return self.db.execute(
            select(func.count())
            .select_from(WikiArticle)
            .where(WikiArticle.category_id == category_id)
        ).scalar() or 0

    def update(self, obj: WikiCategory, data: dict) -> WikiCategory:
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: WikiCategory) -> None:
        self.db.delete(obj)
