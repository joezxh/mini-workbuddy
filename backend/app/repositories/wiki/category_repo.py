"""KbCategory 数据访问层。"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.kb.kb_category import KbCategory


class KbCategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: dict) -> KbCategory:
        obj = KbCategory(**data)
        self.db.add(obj)
        self.db.flush()
        return obj

    def get_by_id(self, category_id: int) -> Optional[KbCategory]:
        return self.db.get(KbCategory, category_id)

    def get_by_slug(self, slug: str) -> Optional[KbCategory]:
        return self.db.execute(
            select(KbCategory).where(KbCategory.slug == slug)
        ).scalar_one_or_none()

    def list_all(self) -> List[KbCategory]:
        return self.db.execute(
            select(KbCategory).order_by(KbCategory.sort_order, KbCategory.name)
        ).scalars().all()

    def count_articles(self, category_id: int) -> int:
        from app.models.wiki.wiki_article import WikiArticle

        return self.db.execute(
            select(func.count())
            .select_from(WikiArticle)
            .where(WikiArticle.category_id == category_id)
        ).scalar() or 0

    def update(self, obj: KbCategory, data: dict) -> KbCategory:
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: KbCategory) -> None:
        self.db.delete(obj)
