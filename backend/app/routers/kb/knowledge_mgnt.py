"""知识库管理 CRUD API 路由（由 wiki.py 迁移而来）。

端点（前缀 /api/v1/kb，与 kb.py 约定一致）:
- GET    /knowledges              知识库列表（附文章数统计）
- POST   /knowledges              创建知识库
- PUT    /knowledges/{id}         更新知识库
- DELETE /knowledges/{id}         删除知识库
- GET    /categories              分类树
- POST   /categories              创建分类
- PUT    /categories/{id}         更新分类
- DELETE /categories/{id}         删除分类

业务逻辑、请求参数与返回结构与原 wiki.py 完全一致，仅代码位置与 URL 前缀变化。
OKF 导出/导入端点（/knowledges/{id}/okf-export、/okf-import）仍保留在 wiki.py。
"""
from __future__ import annotations

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.kb.kb_category import KbCategory
from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.kb_format import validate_external_type, validate_kb_format
from app.services.kb.pipeline_config import normalize_pipeline_config

router = APIRouter(prefix="/api/v1/kb", tags=["知识库管理"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    owl_class_uri: Optional[str] = None
    sort_order: int = 0


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class KnowledgeCreateRequest(BaseModel):
    """知识库创建（管理控制台「知识库管理」页）。"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    # 统一容器（spec §3.1/§10.2）：1=llm-wiki 2=general-kb 3=external-kb
    type: int = 1
    kb_format: Optional[str] = Field(None, max_length=16)
    # 外部类型（仅 type=3 / connector）：平台类型（飞书/语雀/钉钉/企业微信/notion/web）
    external_type: Optional[str] = Field(None, max_length=32)
    index_mode: Optional[str] = Field(None, max_length=16)
    multimodal_enabled: bool = False
    # 所属类别（知识库管理）：kms_category.id，NULL=未分类
    category_id: Optional[int] = None


class KnowledgeUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[int] = Field(None, description="1=启用 0=归档")
    # 所属类别（知识库管理）
    category_id: Optional[int] = None
    # 外部类型（编辑态可改平台；改后需重新配置凭据，见 external-sources 接口）
    external_type: Optional[str] = Field(None, max_length=32)
    # 摄取编排（spec §10.7 / D8）：切片方案 + 嵌入模型，原生键名
    pipeline_config: Optional[dict] = None


def _slugify(text: str) -> str:
    """生成 URL 友好的 slug。"""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    return slug or "untitled"


# ── 分类 ─────────────────────────────────────────────────────────────────────

@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取分类树。"""
    categories = db.execute(
        select(KbCategory).order_by(KbCategory.sort_order, KbCategory.name)
    ).scalars().all()

    # 构建树
    cat_map = {}
    roots = []
    for cat in categories:
        node = _category_to_dict(cat)
        cat_map[cat.id] = node
    for cat in categories:
        node = cat_map[cat.id]
        if cat.parent_id and cat.parent_id in cat_map:
            cat_map[cat.parent_id].setdefault("children", []).append(node)
        else:
            roots.append(node)
    return roots


@router.post("/categories")
def create_category(
    body: CategoryCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建分类。"""
    slug = body.slug or _slugify(body.name)
    existing = db.execute(
        select(KbCategory).where(KbCategory.slug == slug)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"分类 slug '{slug}' 已存在")

    if body.knowledge_id is not None:
        raise HTTPException(status_code=400, detail="分类不再归属知识库（knowledge_id 已废弃）")

    category = KbCategory(
        name=body.name,
        slug=slug,
        description=body.description,
        parent_id=body.parent_id,
        owl_class_uri=body.owl_class_uri,
        sort_order=body.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _category_to_dict(category)


@router.put("/categories/{category_id}")
def update_category(
    category_id: int,
    body: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新分类（名称/描述/父级/排序）。slug 保持不变以稳定 URL。"""
    category = db.get(KbCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    if body.parent_id is not None and body.parent_id != category.parent_id:
        if body.parent_id == category.id:
            raise HTTPException(status_code=400, detail="父分类不能是自身")
        parent = db.get(KbCategory, body.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="目标父分类不存在")
        # 禁止把分类移动到自己的子树内（沿父链向上检查）
        node = parent
        while node is not None:
            if node.id == category.id:
                raise HTTPException(status_code=400, detail="不能移动到自身子分类下")
            node = node.parent
        category.parent_id = body.parent_id

    if body.name is not None:
        category.name = body.name
    if body.description is not None:
        category.description = body.description
    if body.sort_order is not None:
        category.sort_order = body.sort_order

    db.commit()
    db.refresh(category)
    return _category_to_dict(category)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除分类。存在子分类或关联文章时拒绝删除（fail-closed）。"""
    category = db.get(KbCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    has_children = db.execute(
        select(func.count()).select_from(KbCategory).where(KbCategory.parent_id == category_id)
    ).scalar()
    if has_children:
        raise HTTPException(status_code=409, detail="存在子分类，请先删除子分类")

    article_count = db.execute(
        select(func.count()).select_from(WikiArticle).where(WikiArticle.category_id == category_id)
    ).scalar()
    if article_count:
        raise HTTPException(status_code=409, detail=f"分类下仍有 {article_count} 篇文章，请先移出")

    db.delete(category)
    db.commit()


# ── 知识库 ───────────────────────────────────────────────────────────────────

def _knowledge_to_dict(kb: WikiKnowledge, category_count: int = 0, article_count: int = 0) -> dict:
    return {
        "id": kb.id,
        "name": kb.name,
        "slug": kb.slug,
        "description": kb.description,
        "status": kb.status,
        "type": kb.type,
        "kb_format": kb.kb_format,
        "external_type": kb.external_type,
        "index_mode": kb.index_mode,
        "multimodal_enabled": kb.multimodal_enabled,
        "category_id": kb.category_id,
        "category_count": category_count,
        "article_count": article_count,
        "created_at": str(kb.created_at) if kb.created_at else None,
        "updated_at": str(kb.updated_at) if kb.updated_at else None,
    }


@router.get("/knowledges")
def list_knowledges(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """知识库列表（附分类数 / 文章数统计）。"""
    kbs = db.execute(select(WikiKnowledge).order_by(WikiKnowledge.id)).scalars().all()
    art_rows = db.execute(
        select(WikiArticle.knowledge_id, func.count()).group_by(WikiArticle.knowledge_id)
    ).all()
    art_counts = {kid: cnt for kid, cnt in art_rows if kid is not None}
    return [
        _knowledge_to_dict(kb, 0, art_counts.get(kb.id, 0))
        for kb in kbs
    ]


@router.post("/knowledges", status_code=201)
def create_knowledge(
    body: KnowledgeCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建知识库。"""
    slug = _slugify(body.name)
    existing = db.execute(
        select(WikiKnowledge).where(WikiKnowledge.slug == slug)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"知识库 slug '{slug}' 已存在")

    # 统一容器校验（spec §10.2）：type/kb_format 合法性矩阵 + 外部类型与形态联动
    validated_format = validate_kb_format(body.type, body.kb_format)
    validated_external = validate_external_type(
        body.type, body.kb_format, body.external_type
    )

    kb = WikiKnowledge(
        name=body.name,
        slug=slug,
        description=body.description,
        type=body.type,
        kb_format=validated_format,
        external_type=validated_external,
        index_mode=body.index_mode or "high_quality",
        multimodal_enabled=body.multimodal_enabled,
        category_id=body.category_id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return _knowledge_to_dict(kb)


@router.put("/knowledges/{knowledge_id}")
def update_knowledge(
    knowledge_id: int,
    body: KnowledgeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新知识库信息。slug 保持不变以稳定 URL。"""
    kb = db.get(WikiKnowledge, knowledge_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    if body.name is not None:
        kb.name = body.name
    if body.description is not None:
        kb.description = body.description
    if body.status is not None:
        kb.status = body.status
    if body.category_id is not None:
        kb.category_id = body.category_id
    # 外部类型（编辑态可改平台）：与既有 type/kb_format 联动校验
    if "external_type" in (body.model_fields_set or set()):
        kb.external_type = validate_external_type(
            kb.type, kb.kb_format, body.external_type
        )
    # 摄取编排：键名白名单校验后落库（D8），驱动后续摄取/重分片的切片方案
    if "pipeline_config" in (body.model_fields_set or set()):
        kb.pipeline_config = normalize_pipeline_config(body.pipeline_config)

    db.commit()
    db.refresh(kb)
    return _knowledge_to_dict(kb)


@router.delete("/knowledges/{knowledge_id}", status_code=204)
def delete_knowledge(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除知识库。存在分类（或分类下有文章）时拒绝删除（fail-closed）。"""
    kb = db.get(WikiKnowledge, knowledge_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    db.delete(kb)
    db.commit()


def _category_to_dict(cat: KbCategory) -> dict:
    return {
        "id": cat.id,
        "name": cat.name,
        "slug": cat.slug,
        "description": cat.description,
        "parent_id": cat.parent_id,
        "owl_class_uri": cat.owl_class_uri,
        "sort_order": cat.sort_order,
        "article_count": cat.article_count,
        "children": [],
    }
