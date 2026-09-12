"""Wiki 目录 Pydantic schemas。"""
from typing import Optional, List

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    knowledge_id: Optional[int] = Field(None, description='所属知识库 ID（用户侧可留空）')
    slug: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    owl_class_uri: Optional[str] = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    owl_class_uri: Optional[str] = None
    sort_order: Optional[int] = None
    knowledge_id: Optional[int] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    knowledge_id: Optional[int] = None
    owl_class_uri: Optional[str] = None
    sort_order: int = 0
    article_count: int = 0
    children: List[dict] = []
