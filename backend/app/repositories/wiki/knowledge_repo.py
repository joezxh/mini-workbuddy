"""WikiKnowledge 数据访问层。"""
from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wiki.wiki_knowledge import WikiKnowledge


class WikiKnowledgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: dict) -> WikiKnowledge:
        obj = WikiKnowledge(**data)
        self.db.add(obj)
        self.db.flush()
        return obj

    def get_by_id(self, knowledge_id: int) -> Optional[WikiKnowledge]:
        return self.db.get(WikiKnowledge, knowledge_id)

    def get_by_slug(self, slug: str) -> Optional[WikiKnowledge]:
        return self.db.execute(
            select(WikiKnowledge).where(WikiKnowledge.slug == slug)
        ).scalar_one_or_none()

    def list_all(
        self, page: int = 1, page_size: int = 20, status: Optional[int] = None
    ) -> Tuple[int, list]:
        stmt = select(WikiKnowledge)
        count_stmt = select(func.count()).select_from(WikiKnowledge)
        if status is not None:
            stmt = stmt.where(WikiKnowledge.status == status)
            count_stmt = count_stmt.where(WikiKnowledge.status == status)
        total = self.db.execute(count_stmt).scalar() or 0
        items = self.db.execute(
            stmt.order_by(WikiKnowledge.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()
        return total, items

    def update(self, obj: WikiKnowledge, data: dict) -> WikiKnowledge:
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: WikiKnowledge) -> None:
        self.db.delete(obj)
