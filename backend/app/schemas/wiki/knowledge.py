"""Wiki 知识库 Pydantic schemas。"""
from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=100)
    cover_url: Optional[str] = Field(None, max_length=500)
    owner_id: Optional[int] = None
    status: int = 1
    # 统一容器（spec §3.1/§10.2）：1=llm-wiki 2=general-kb 3=external-kb
    type: int = 1
    kb_format: Optional[str] = Field(None, max_length=16)


class KnowledgeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=100)
    cover_url: Optional[str] = Field(None, max_length=500)
    owner_id: Optional[int] = None
    status: Optional[int] = None
    kb_format: Optional[str] = Field(None, max_length=16)


class KnowledgeOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    cover_url: Optional[str] = None
    owner_id: Optional[int] = None
    status: int
    article_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
