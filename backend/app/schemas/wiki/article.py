"""Wiki 文章 Pydantic schemas（管理后台用）。"""
from typing import Optional, List

from pydantic import BaseModel


class ArticleOut(BaseModel):
    id: int
    slug: str
    title: str
    summary: Optional[str] = None
    category_id: Optional[int] = None
    tags: List[str] = []
    owl_class_uris: List[str] = []
    wiki_links: List[str] = []
    backlinks: List[str] = []
    status: int
    is_featured: bool = False
    view_count: int = 0
    version: int
    creator_id: Optional[int] = None
    updater_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
