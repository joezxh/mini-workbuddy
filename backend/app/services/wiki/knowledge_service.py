"""WikiKnowledge 业务逻辑层。"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wiki.wiki_article import WikiArticle
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
        .where(WikiArticle.knowledge_id == knowledge_id)
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
        "type": k.type,
        "kb_format": k.kb_format,
        "index_mode": k.index_mode,
        "multimodal_enabled": k.multimodal_enabled,
        "pipeline_config": k.pipeline_config,
        "category_id": k.category_id,
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

        # 统一容器校验（spec §10.2）：type/kb_format 合法性矩阵
        from app.services.kb.kb_format import validate_kb_format

        kb_type = data.get("type", 1)
        data["type"] = kb_type
        data["kb_format"] = validate_kb_format(kb_type, data.get("kb_format"))

        # 索引模式（spec §10.2）：仅两档，未传/非法回落 high_quality
        mode = (data.get("index_mode") or "high_quality").lower()
        data["index_mode"] = mode if mode in ("high_quality", "economy") else "high_quality"
        # 多模态仅 type=2/document 有意义（§10.1 ④）
        data["multimodal_enabled"] = bool(data.get("multimodal_enabled")) and kb_type == 2

        # pipeline_config 规范化（D8：键名对齐原生）
        from app.services.kb.pipeline_config import normalize_pipeline_config

        data["pipeline_config"] = normalize_pipeline_config(
            payload.pipeline_config if hasattr(payload, "pipeline_config") else None
        )

        obj = self.repo.create(data)

        # type=2 联动建 collection（AgentScope 约定 kb_<uuid> 逻辑名，绑定统一容器）
        if kb_type == 2:
            from uuid import uuid4

            from app.config import settings
            from app.models.kb.kb_collection import KbCollection

            self.db.add(KbCollection(
                name=f"kb_{uuid4().hex}",
                dimensions=settings.GPUSTACK_EMBEDDING_DIMENSION,
                knowledge_id=obj.id,
            ))
            self.db.flush()

        self.db.commit()
        self.db.refresh(obj)
        return _to_out(self.db, obj)

    def list(self, page: int = 1, page_size: int = 20, status: Optional[int] = None) -> dict:
        """知识库列表缓存（Phase 3 T2）：写操作后由 create/update/delete 失效。"""
        from app.services.kb.kb_cache import cache_key, cached

        @cached(key_builder=lambda: cache_key("knowledges", page, page_size, status))
        def _query() -> dict:
            total, items = self.repo.list_all(page, page_size, status)
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [_to_out(self.db, k) for k in items],
            }

        return _query()

    def get(self, knowledge_id: int) -> dict:
        obj = self._require(knowledge_id)
        return _to_out(self.db, obj)

    def update(self, knowledge_id: int, payload: KnowledgeUpdate) -> dict:
        obj = self._require(knowledge_id)
        payload_dict = payload.dict(exclude_none=True)
        # 创建后不可切换（spec §10.2）
        from app.services.kb.kb_format import assert_format_unchanged

        assert_format_unchanged(obj.kb_format, payload_dict.get("kb_format"))
        # pipeline_config 规范化（D8）
        if "pipeline_config" in payload_dict:
            from app.services.kb.pipeline_config import normalize_pipeline_config

            payload_dict["pipeline_config"] = normalize_pipeline_config(
                payload_dict.get("pipeline_config")
            )
        self.repo.update(obj, payload_dict)
        self.db.commit()
        self.db.refresh(obj)
        from app.services.kb.kb_cache import cache_key, invalidate

        invalidate(cache_key("knowledges"))
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
        from app.services.kb.kb_cache import cache_key, invalidate

        invalidate(cache_key("knowledges"))  # 列表缓存失效
        invalidate(cache_key("tree"))        # 目录树缓存失效

    def _require(self, knowledge_id: int) -> WikiKnowledge:
        obj = self.repo.get_by_id(knowledge_id)
        if not obj:
            raise HTTPException(status_code=404, detail="知识库不存在")
        return obj
