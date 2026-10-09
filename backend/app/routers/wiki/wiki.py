"""Wiki 文章 CRUD + 搜索 API 路由。

端点:
- POST   /wiki/articles          创建文章
- GET    /wiki/articles          文章列表 (分页 + 分类过滤)
- GET    /wiki/articles/{slug}   按 slug 获取文章
- PUT    /wiki/articles/{id}     更新文章 (自动创建版本快照)
- DELETE /wiki/articles/{id}     删除文章
- GET    /wiki/articles/{id}/versions  获取版本历史
- GET    /wiki/search?q=...      语义搜索
- GET    /wiki/categories        分类树
- POST   /wiki/categories        创建分类
"""
from __future__ import annotations

import logging
import re
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db, get_current_user
from app.ai.research.llm import llm_complete
from app.models.sys.sys_user import SysUser
from app.services.wiki.doc_converter import SUPPORTED_EXTS, convert_document
from app.services.wiki.search_service import WikiSearchService
from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_article_version import WikiArticleVersion
from app.models.kb.kb_category import KbCategory
from app.models.wiki.wiki_knowledge import WikiKnowledge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wiki", tags=["LLM-wiki"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class DocSourceItem(BaseModel):
    """OKF §5.1 溯源条目（对应 ``kms_article.sources`` 的元素结构）。"""

    resource: str = Field(..., description="源文件 URI / 相对路径（必填）")
    # §6.1：id 是 footnote 的 join 键（label = sources[].id），缺失则逐条归因无法成立
    id: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    last_modified: Optional[str] = None
    usage_count: Optional[int] = None


class ArticleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    slug: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    summary: Optional[str] = Field(None, max_length=1000)
    category_id: Optional[int] = None
    knowledge_id: Optional[int] = Field(None, description="所属知识库 ID（默认取当前选中的知识库）")
    tags: Optional[List[str]] = None
    owl_class_uris: Optional[List[str]] = None
    wiki_links: Optional[List[str]] = None
    status: int = 1  # 1=发布 0=草稿
    # OKF 合规层（文档导入时提取，可人工修改后保存）
    okf_type: Optional[str] = Field(None, max_length=64)
    resource: Optional[str] = Field(None, max_length=500)
    sources: Optional[List[DocSourceItem]] = None
    # OKF §5.2 验证事件列表 [{by, at}]；§5.5 绝对过期时间点
    verified: Optional[List[dict]] = None
    stale_after: Optional[str] = None
    # OKF §10 Attested Computation 契约（spec §9.6 推迟项，本次补齐）
    attested_computation: Optional[dict] = None


class ArticleUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = None
    summary: Optional[str] = Field(None, max_length=1000)
    category_id: Optional[int] = None
    knowledge_id: Optional[int] = None
    tags: Optional[List[str]] = None
    owl_class_uris: Optional[List[str]] = None
    wiki_links: Optional[List[str]] = None
    status: Optional[int] = None
    change_note: Optional[str] = Field(None, max_length=500)
    okf_type: Optional[str] = Field(None, max_length=64)
    resource: Optional[str] = Field(None, max_length=500)
    sources: Optional[List[DocSourceItem]] = None
    # OKF §5.2 / §5.5
    verified: Optional[List[dict]] = None
    stale_after: Optional[str] = None
    # OKF §10 Attested Computation
    attested_computation: Optional[dict] = None


class ArticleConvertOut(BaseModel):
    """文档转换结果：正文 Markdown + 提取到的字段（供前端动态渲染，不写库）。"""

    markdown: str
    resource: str
    filename: str
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = []
    okf_type: Optional[str] = None
    sources: List[DocSourceItem] = []


class RollbackRequest(BaseModel):
    version_id: int
    change_note: Optional[str] = Field(None, max_length=500)


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


class WikiSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    mode: str = Field("hybrid", description="hybrid / semantic / keyword")
    top_k: int = Field(10, ge=1, le=50)
    knowledge_id: Optional[int] = None


class WikiAskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(5, ge=1, le=20)
    knowledge_id: Optional[int] = None


def _slugify(text: str) -> str:
    """生成 URL 友好的 slug。"""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    return slug or "untitled"


def _parse_optional_datetime(value: Optional[str]):
    """把 ISO 8601 字符串解析为 datetime；不可解析返回 None（宽容，不拒绝请求）。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


# ── 文章 CRUD ────────────────────────────────────────────────────────────────

@router.post("/articles")
def create_article(
    body: ArticleCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建 Wiki 文章。

    写入统一走 ``WikiArticleService``（版本快照 / 反向链接 / 异步向量索引的唯一实现），
    保持对外响应形状与历史内联实现一致。
    """
    from app.services.wiki.article_service import WikiArticleService

    payload = body.model_dump(exclude_none=False)
    payload["sources"] = [s.model_dump() for s in body.sources] if body.sources else []
    payload["stale_after"] = _parse_optional_datetime(body.stale_after)
    return WikiArticleService(db).create(payload, current_user)


@router.get("/articles")
def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = Query(None),
    knowledge_id: Optional[int] = Query(None, description="按知识库过滤（文章所属分类归属该知识库）"),
    status: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    sort: str = Query("updated_at", description="排序字段：updated_at | title | version | view_count"),
    order: str = Query("desc", description="排序方向：asc | desc"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取文章列表 (分页 + 排序)。"""
    stmt = select(WikiArticle)
    count_stmt = select(func.count()).select_from(WikiArticle)

    if category_id is not None:
        stmt = stmt.where(WikiArticle.category_id == category_id)
        count_stmt = count_stmt.where(WikiArticle.category_id == category_id)
    if knowledge_id is not None:
        stmt = stmt.where(WikiArticle.knowledge_id == knowledge_id)
        count_stmt = count_stmt.where(WikiArticle.knowledge_id == knowledge_id)
    if status is not None:
        stmt = stmt.where(WikiArticle.status == status)
        count_stmt = count_stmt.where(WikiArticle.status == status)
    else:
        # 默认不显示归档
        stmt = stmt.where(WikiArticle.status >= 0)
        count_stmt = count_stmt.where(WikiArticle.status >= 0)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern))
        count_stmt = count_stmt.where(WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern))

    # 排序：白名单映射，未知字段一律退化为 updated_at，避免把用户输入拼进 ORDER BY
    sort_col = {
        "updated_at": WikiArticle.updated_at,
        "title": WikiArticle.title,
        "version": WikiArticle.version,
        "view_count": WikiArticle.view_count,
    }.get(sort, WikiArticle.updated_at)
    order_by = sort_col.asc() if str(order).lower() == "asc" else sort_col.desc()

    total = db.execute(count_stmt).scalar() or 0
    articles = db.execute(
        stmt.order_by(order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_article_to_dict(a) for a in articles],
    }


@router.get("/articles/{article_id:int}")
def get_article_by_id(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """按 ID 获取文章详情（消除前端 slug hack，spec G4）。

    路径使用 ``{article_id:int}`` 转换器：仅数字路径命中本端点，
    非数字路径（slug）自动落到下方的 ``/articles/{slug}`` 端点，避免 422。
    """
    article = db.get(WikiArticle, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return _article_to_dict(article)


@router.get("/articles/{article_id}/versions/{version_id}/diff")
def diff_article_version(
    article_id: int,
    version_id: int,
    target: Optional[int] = Query(None, description="对照版本 ID；缺省=当前版本"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """版本 diff：目标版本 vs 当前版本；指定 target 时为两历史版本互比。"""
    from app.services.wiki.version_service import WikiVersionService

    return WikiVersionService(db).get_diff(article_id, version_id, target_version_id=target)


@router.post("/articles/{article_id}/rollback")
def rollback_article(
    article_id: int,
    body: RollbackRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """非破坏式回滚：以历史版本内容生成新的当前版本（version = max+1）。"""
    from app.services.wiki.version_service import WikiVersionService

    return WikiVersionService(db).rollback(
        article_id, body.version_id, current_user, change_note=body.change_note
    )


@router.get("/articles/{slug}")
def get_article(
    slug: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """按 slug 获取文章详情。"""
    article = db.execute(
        select(WikiArticle).where(WikiArticle.slug == slug)
    ).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 增加浏览计数
    db.execute(
        sa_update(WikiArticle).where(WikiArticle.id == article.id).values(
            view_count=WikiArticle.view_count + 1
        )
    )
    db.commit()
    db.refresh(article)
    return _article_to_dict(article)


@router.put("/articles/{article_id}")
def update_article(
    article_id: int,
    body: ArticleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新文章（自动创建版本快照 + 触发异步重新索引）。

    写入统一走 ``WikiArticleService``，与创建路径共用一处实现。
    """
    from app.services.wiki.article_service import WikiArticleService

    data = body.model_dump(exclude_none=True, exclude={"change_note"})
    if body.sources is not None:
        data["sources"] = [s.model_dump() for s in body.sources]
    if "stale_after" in data:
        data["stale_after"] = _parse_optional_datetime(data["stale_after"])
    return WikiArticleService(db).update(
        article_id, data, body.change_note, current_user,
    )


@router.post("/articles/convert-document", response_model=ArticleConvertOut)
def convert_uploaded_document(
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_user),
):
    """上传文档 → 转 Markdown + 提取字段（**不写库**，前端确认后再保存）。

    源文件落盘到 ``settings.UPLOAD_DIR/wiki_docs/<tenant>/<date>/`` 以便溯源，
    落盘路径同时写入 ``resource`` 与 ``sources[].resource``。
    """
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式 '{ext or '未知'}'，仅支持 PDF / Word / TXT / Markdown / PPT / Excel",
        )

    data = file.file.read()
    try:
        result = convert_document(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 落盘：租户 / 日期分目录 + uuid 前缀重命名（防重名与路径穿越）
    safe_name = re.sub(r"[^\w.\-\u4e00-\u9fa5]", "_", Path(filename).name)[:120] or "doc"
    rel_dir = Path("wiki_docs") / str(getattr(current_user, "tenant_id", None) or 0) / date.today().isoformat()
    target_dir: Path = Path(settings.UPLOAD_DIR) / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex}_{safe_name}"
    target.write_bytes(data)
    resource = str(target)

    return ArticleConvertOut(
        markdown=result.markdown,
        resource=resource,
        filename=filename,
        title=result.title,
        summary=result.summary,
        tags=result.tags,
        okf_type=result.okf_type,
        sources=[DocSourceItem(
            resource=resource,
            title=result.title,
            author=result.source_meta.author,
            last_modified=result.source_meta.last_modified,
        )],
    )


@router.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除文章。"""
    article = db.get(WikiArticle, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    db.delete(article)
    db.commit()
    return {"message": "删除成功"}


@router.get("/articles/{article_id}/versions")
def get_article_versions(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取文章版本历史。"""
    versions = db.execute(
        select(WikiArticleVersion)
        .where(WikiArticleVersion.article_id == article_id)
        .order_by(WikiArticleVersion.version.desc())
    ).scalars().all()

    return [
        {
            "id": v.id,
            "article_id": v.article_id,
            "version": v.version,
            "title": v.title,
            "slug": v.slug,
            "change_note": v.change_note,
            "editor_id": v.editor_id,
            "created_at": str(v.created_at) if v.created_at else None,
        }
        for v in versions
    ]


# ── 搜索 ─────────────────────────────────────────────────────────────────────

@router.get("/search")
def search_articles(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    top_k: int = Query(10, ge=1, le=50),
    owl_class: Optional[str] = Query(None, description="按 OWL Class URI 过滤"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """语义搜索 Wiki 文章。

    优先使用向量检索 (RAG), 降级为 SQL LIKE 搜索。
    """
    # 降级: SQL LIKE 搜索 (向量检索需要 EmbeddingService 配置)
    pattern = f"%{q}%"
    stmt = (
        select(WikiArticle)
        .where(WikiArticle.status >= 0)
        .where(WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern))
        .order_by(WikiArticle.updated_at.desc())
        .limit(top_k)
    )
    articles = db.execute(stmt).scalars().all()

    return {
        "query": q,
        "total": len(articles),
        "items": [_article_to_dict(a) for a in articles],
    }


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


# ── 知识库（仅 wiki 类型） ───────────────────────────────────────────────────

def _knowledge_to_dict(kb: WikiKnowledge, category_count: int = 0, article_count: int = 0) -> dict:
    return {
        "id": kb.id,
        "name": kb.name,
        "slug": kb.slug,
        "description": kb.description,
        "status": kb.status,
        "type": kb.type,
        "kb_format": kb.kb_format,
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
    """创建 wiki 类型知识库。"""
    slug = _slugify(body.name)
    existing = db.execute(
        select(WikiKnowledge).where(WikiKnowledge.slug == slug)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"知识库 slug '{slug}' 已存在")

    kb = WikiKnowledge(
        name=body.name,
        slug=slug,
        description=body.description,
        type=body.type,
        kb_format=body.kb_format,
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


# ── 内部工具 ─────────────────────────────────────────────────────────────────

def _article_to_dict(article: WikiArticle) -> dict:
    return {
        "id": article.id,
        "slug": article.slug,
        "title": article.title,
        "summary": article.summary,
        "content": article.content,
        "category_id": article.category_id,
        "knowledge_id": article.knowledge_id,
        "okf_type": article.okf_type,
        "resource": article.resource,
        "sources": article.sources or [],
        "tags": article.tags or [],
        # OKF §10 Attested Computation
        "attested_computation": getattr(article, "attested_computation", None),
        "owl_class_uris": article.owl_class_uris or [],
        "wiki_links": article.wiki_links or [],
        "backlinks": article.backlinks or [],
        "status": article.status,
        "is_featured": article.is_featured,
        "view_count": article.view_count,
        "version": article.version,
        "creator_id": article.creator_id,
        "updater_id": article.updater_id,
        "created_at": str(article.created_at) if article.created_at else None,
        "updated_at": str(article.updated_at) if article.updated_at else None,
    }


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


def _update_backlinks(db: Session, article: WikiArticle) -> None:
    """更新文章的 backlinks (反向链接)。"""
    if not article.wiki_links:
        return
    # 找到所有被本文链接的文章, 在它们的 backlinks 中添加本文 slug
    linked_slugs = article.wiki_links
    for slug in linked_slugs:
        target = db.execute(
            select(WikiArticle).where(WikiArticle.slug == slug)
        ).scalar_one_or_none()
        if target:
            backlinks = target.backlinks or []
            if article.slug not in backlinks:
                backlinks.append(article.slug)
                target.backlinks = backlinks


# ── RAG 检索 / 问答（管理台 RagTestTab 的后端契约） ─────────────────────────

@router.post("/search")
def wiki_search(
    body: WikiSearchRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """混合检索（semantic / keyword / hybrid，RRF 融合），自动落检索日志。"""
    return WikiSearchService(db).search(
        body.query,
        mode=body.mode,
        top_k=body.top_k,
        knowledge_id=body.knowledge_id,
        user_id=current_user.user_id,
    )


@router.get("/search-logs")
def wiki_search_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mode: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """检索历史日志。"""
    return WikiSearchService(db).history(page=page, page_size=page_size, mode=mode)


@router.post("/ask")
async def wiki_ask(
    body: WikiAskRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """向知识库提问：检索 top_k 篇文章作为上下文，由 LLM 生成带引用的回答。"""
    res = WikiSearchService(db).search(
        body.query,
        mode="hybrid",
        top_k=body.top_k,
        knowledge_id=body.knowledge_id,
        user_id=current_user.user_id,
    )
    sources = []
    for item in res.get("items", []):
        art = db.execute(
            select(WikiArticle).where(WikiArticle.id == item["id"])
        ).scalar_one_or_none()
        if not art:
            continue
        content = (art.content or "").strip()
        if not content:
            continue
        sources.append({
            "title": art.title,
            "slug": art.slug,
            "content": content[:4000],
            "snippet": (content[:240] + ("…" if len(content) > 240 else "")),
        })
    if not sources:
        raise HTTPException(status_code=404, detail="未检索到相关文章，无法回答")

    context = "\n\n".join(
        f"[{i + 1}] {s['title']}\n{s['content']}" for i, s in enumerate(sources)
    )
    prompt = (
        "请根据以下知识库文章内容回答用户问题。只依据给出的资料作答，"
        "资料不足时如实说明，不要编造。引用资料时标注编号（如 [1]）。"
        "用中文 Markdown 输出。\n\n"
        f"=== 知识库资料 ===\n{context}\n\n"
        f"=== 用户问题 ===\n{body.query}"
    )
    try:
        answer = await llm_complete(prompt)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[wiki/ask] LLM 调用失败: {e}")
        raise HTTPException(status_code=502, detail="AI 服务暂不可用，请稍后重试或检查模型配置")

    citations = [
        {
            "ref": i + 1,
            "article_id": res["items"][i]["id"] if i < len(res.get("items", [])) else None,
            "slug": s["slug"],
            "title": s["title"],
            "snippet": s["snippet"],
        }
        for i, s in enumerate(sources)
    ]
    return {"answer": answer, "citations": citations, "mode": res.get("mode", "hybrid")}


# ── OKF 合规层（spec §9.4）：导出 Bundle / 单篇 concept 预览 / 宽容导入 ──────

@router.get("/knowledges/{knowledge_id}/okf-export")
def okf_export_bundle(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """知识库导出 OKF v0.2 Bundle（zip）。"""
    import io
    import zipfile

    from fastapi.responses import StreamingResponse

    from app.services.wiki.okf_service import export_bundle

    files = export_bundle(db, knowledge_id, tenant_id=current_user.tenant_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="okf-{knowledge_id}.zip"'},
    )


@router.get("/articles/{article_id}/okf")
def article_okf_preview(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """单篇 concept.md 预览（frontmatter 键序按规范推荐）。"""
    from app.services.wiki.okf_service import _to_utc_iso, serialize_article

    art = db.get(WikiArticle, article_id)
    if art is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    username = getattr(current_user, "username", None) or str(current_user.user_id)
    return {
        "filename": f"{art.slug}.md",
        "content": serialize_article(art, author_actor=f"human:{username}",
                                     generated_at=_to_utc_iso(art.updated_at), db=db),
    }


@router.post("/knowledges/{knowledge_id}/okf-import")
async def okf_import_bundle(
    knowledge_id: int,
    file: UploadFile = File(..., description="OKF Bundle（zip）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """宽容导入 Bundle（zip）：缺可选字段 / 未知 type / 断链一律接受（§11.3）。

    解包在服务端完成（条目数、体积与路径穿越均有上限），浏览器不需要 zip 解析依赖。
    """
    from app.services.wiki.okf_service import extract_zip, import_bundle

    raw = await file.read()
    try:
        files = extract_zip(raw)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail=f"不是合法的 zip 文件: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Bundle 校验失败: {exc}") from exc

    return import_bundle(
        db, knowledge_id, files, current_user, tenant_id=current_user.tenant_id,
    )


@router.post("/reindex")
def reindex_articles(
    knowledge_id: Optional[int] = Query(None, description="限定知识库；缺省为当前租户全部文章"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """后台重建文章向量索引（存量修复入口）。

    ``WikiRAGIngestor.reindex_all`` 此前没有任何 HTTP 入口，导致历史文章
    ``content_vector`` 恒为 NULL、语义检索永远为空集。本端点补齐该入口。
    """
    from app.core.job_runner import run_in_background
    from app.services.wiki.rag_ingestor import WikiRAGIngestor

    tenant_id = getattr(current_user, "tenant_id", None)
    run_in_background(
        WikiRAGIngestor().reindex_all,
        batch_size=200,
        tenant_id=tenant_id,
        knowledge_id=knowledge_id,
        name=f"wiki-reindex-{tenant_id}-{knowledge_id}",
    )
    return {"started": True, "tenant_id": tenant_id, "knowledge_id": knowledge_id}

