"""KbCategory 业务逻辑层（目录归属知识库）。"""
from __future__ import annotations

import re
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.kb.kb_category import KbCategory
from app.repositories.wiki.category_repo import KbCategoryRepository
from app.schemas.wiki.category import CategoryCreate, CategoryUpdate


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "untitled"


def _to_out(c: KbCategory) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
        "parent_id": c.parent_id,
        "knowledge_id": c.knowledge_id,
        "owl_class_uri": c.owl_class_uri,
        "sort_order": c.sort_order or 0,
        "article_count": c.article_count or 0,
        "children": [],
    }


class KbCategoryService:
    """目录管理：创建 / 树形查询（可过滤知识库）/ 更新 / 移动 / 删除。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = KbCategoryRepository(db)

    def create(self, payload: CategoryCreate, user) -> dict:
        slug = payload.slug or _slugify(payload.name)
        if self.repo.get_by_slug(slug):
            raise HTTPException(status_code=409, detail=f"分类 slug '{slug}' 已存在")
        data = payload.dict(exclude_none=True)
        data["slug"] = slug
        obj = self.repo.create(data)
        self.db.commit()
        self.db.refresh(obj)
        from app.services.kb.kb_cache import cache_key, invalidate

        invalidate(cache_key("tree"))  # 树结构变更 → 失效全部树缓存
        return _to_out(obj)

    def tree(self, knowledge_id: Optional[int] = None) -> List[dict]:
        """目录树：读多写少，走缓存（Phase 3 T2）；写操作在下方各方法内失效。"""
        from app.services.kb.kb_cache import cache_key, cached

        @cached(key_builder=lambda: cache_key("tree", knowledge_id))
        def _build() -> List[dict]:
            return self._build_tree(knowledge_id)

        return _build()

    def _build_tree(self, knowledge_id: Optional[int] = None) -> List[dict]:
        categories = (
            self.repo.list_by_knowledge(knowledge_id)
            if knowledge_id is not None
            else self.repo.list_all()
        )
        node_map: dict = {}
        roots: list = []
        for c in categories:
            node_map[c.id] = _to_out(c)
        for c in categories:
            node = node_map[c.id]
            if c.parent_id and c.parent_id in node_map:
                node_map[c.parent_id].setdefault("children", []).append(node)
            else:
                roots.append(node)
        return roots

    def get(self, category_id: int) -> dict:
        obj = self._require(category_id)
        return _to_out(obj)

    def update(self, category_id: int, payload: CategoryUpdate) -> dict:
        obj = self._require(category_id)
        self.repo.update(obj, payload.dict(exclude_none=True))
        self.db.commit()
        self.db.refresh(obj)
        from app.services.kb.kb_cache import cache_key, invalidate

        invalidate(cache_key("tree"))
        return _to_out(obj)

    def move(self, category_id: int, parent_id: Optional[int]) -> dict:
        obj = self._require(category_id)
        if parent_id is not None:
            parent = self.repo.get_by_id(parent_id)
            if not parent:
                raise HTTPException(status_code=404, detail="父目录不存在")
        obj.parent_id = parent_id
        self.db.commit()
        self.db.refresh(obj)
        from app.services.kb.kb_cache import cache_key, invalidate

        invalidate(cache_key("tree"))
        return _to_out(obj)

    def delete(self, category_id: int) -> None:
        obj = self._require(category_id)
        self.repo.delete(obj)
        self.db.commit()
        from app.services.kb.kb_cache import cache_key, invalidate

        invalidate(cache_key("tree"))

    def _require(self, category_id: int) -> KbCategory:
        obj = self.repo.get_by_id(category_id)
        if not obj:
            raise HTTPException(status_code=404, detail="目录不存在")
        return obj
