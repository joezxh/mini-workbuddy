"""WikiKnowledge 业务逻辑层。"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_category import WikiCategory
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.repositories.wiki.knowledge_repo import WikiKnowledgeRepository
from app.schemas.wiki.knowledge import KnowledgeCreate, KnowledgeUpdate


logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "untitled"


def _article_count(db: Session, knowledge_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(WikiArticle)
        .join(WikiCategory, WikiArticle.category_id == WikiCategory.id)
        .where(WikiCategory.knowledge_id == knowledge_id)
    ).scalar() or 0


def _to_out(db: Session, k: WikiKnowledge) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "slug": k.slug,
        "description": k.description,
        "icon": k.icon,
        "cover_url": k.cover_url,
        "owner_id": k.owner_id,
        "status": k.status,
        "article_count": _article_count(db, k.id),
        "created_at": str(k.created_at) if k.created_at else None,
        "updated_at": str(k.updated_at) if k.updated_at else None,
    }


class WikiKnowledgeService:
    """知识库管理：CRUD + 启停。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = WikiKnowledgeRepository(db)

    def create(self, payload: KnowledgeCreate, user) -> dict:
        slug = payload.slug or _slugify(payload.name)
        if self.repo.get_by_slug(slug):
            raise HTTPException(status_code=409, detail=f"slug '{slug}' 已存在")
        data = payload.dict(exclude_none=True)
        data["slug"] = slug
        data.setdefault("owner_id", user.id if user else None)
        obj = self.repo.create(data)
        self.db.commit()
        self.db.refresh(obj)
        return _to_out(self.db, obj)

    def list(self, page: int = 1, page_size: int = 20, status: Optional[int] = None) -> dict:
        total, items = self.repo.list_all(page, page_size, status)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_to_out(self.db, k) for k in items],
        }

    def get(self, knowledge_id: int) -> dict:
        obj = self._require(knowledge_id)
        return _to_out(self.db, obj)

    def update(self, knowledge_id: int, payload: KnowledgeUpdate) -> dict:
        obj = self._require(knowledge_id)
        self.repo.update(obj, payload.dict(exclude_none=True))
        self.db.commit()
        self.db.refresh(obj)
        return _to_out(self.db, obj)

    def set_status(self, knowledge_id: int, status: int) -> dict:
        obj = self._require(knowledge_id)
        obj.status = status
        self.db.commit()
        self.db.refresh(obj)
        return _to_out(self.db, obj)

    def delete(self, knowledge_id: int) -> None:
        obj = self._require(knowledge_id)
        self.repo.delete(obj)
        self.db.commit()

    def _require(self, knowledge_id: int) -> WikiKnowledge:
        obj = self.repo.get_by_id(knowledge_id)
        if not obj:
            raise HTTPException(status_code=404, detail="知识库不存在")
        return obj
