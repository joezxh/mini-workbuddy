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
    # 索引模式（spec §10.2）：economy 摄取写 NULL 向量、检索走关键词服务
    index_mode: Optional[str] = Field(None, max_length=16)
    # 多模态（spec §10.2）：type=2/document 下图片独立向量化（仅文搜图，D9）
    multimodal_enabled: bool = False
    # 摄取编排（spec §10.7 / D8）：键名对齐 AgentScope 原生参数名
    pipeline_config: Optional[dict] = None
    # 所属类别（知识库管理）：kms_category.id，NULL=未分类
    category_id: Optional[int] = None


class KnowledgeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=100)
    cover_url: Optional[str] = Field(None, max_length=500)
    owner_id: Optional[int] = None
    status: Optional[int] = None
    kb_format: Optional[str] = Field(None, max_length=16)
    multimodal_enabled: Optional[bool] = None
    pipeline_config: Optional[dict] = None
    # 所属类别（知识库管理）
    category_id: Optional[int] = None


class KnowledgeOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    cover_url: Optional[str] = None
    owner_id: Optional[int] = None
    status: int
    type: int = 1
    kb_format: Optional[str] = None
    index_mode: Optional[str] = None
    multimodal_enabled: bool = False
    category_id: Optional[int] = None
    article_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
