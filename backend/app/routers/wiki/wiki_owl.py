"""Wiki OWL 本体管理 API 路由。

端点:
- POST /wiki/owl/classes       注册 OWL Class
- GET  /wiki/owl/classes       列出所有 OWL Class
- GET  /wiki/owl/hierarchy     获取类层级树
- POST /wiki/owl/import-ttl    导入 TTL 本体文件
- GET  /wiki/owl/export-ttl    导出 TTL
- GET  /wiki/owl/stats         本体统计
- GET  /wiki/owl/articles/{class_uri}  按 OWL 类查询文章

租户隔离
--------
改造前 `get_owl_engine()` 返回**进程级单例**，本体既重启即丢又跨租户共享。
现按当前登录用户的 `tenant_id` 构造引擎，本体持久化到 `ontology*` 三张表。

`tenant_id` 为空的请求**不再落到 NULL 分区共享**，统一返回 `400 tenant_required`
（评审 IM-07，用户授权的行为变更）。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.wiki.wiki_article import WikiArticle

if TYPE_CHECKING:  # 仅类型提示，避免运行时循环导入
    from app.ai.knowledge.owl_engine import WikiOwlEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wiki/owl", tags=["Wiki OWL 本体"])

#: 无租户请求的固定错误码：不返回内部细节（评审 R2-04 / CWE-209）。
TENANT_REQUIRED_DETAIL = "tenant_required"
#: 数据库异常对客户端统一文案：SQLAlchemy 异常原文含完整 SQL 与绑定参数（含 tenant_id），
#: 不能回显（评审 R2-04 / CWE-209）。
WRITE_FAILED_DETAIL = "本体写入失败，请稍后重试"
SERVICE_UNAVAILABLE_DETAIL = "本体服务暂时不可用，请稍后重试"


# ── Schemas ──────────────────────────────────────────────────────────────────

class OwlClassCreateRequest(BaseModel):
    uri: str = Field(..., description="OWL Class URI")
    label: str = Field("", description="中文标签")
    comment: str = Field("", description="描述")
    parent_uris: List[str] = Field(default_factory=list, description="父类 URI 列表")


# ── 按租户构造引擎 ───────────────────────────────────────────────────────────

def get_owl_engine(
    tenant_id: Optional[int],
    db: Session,
    *,
    auto_commit: bool = True,
) -> "WikiOwlEngine":
    """按租户构造 WikiOwlEngine（持久化后端，不再使用全局单例）。

    `tenant_id` 为空时返回 `400 tenant_required`（评审 IM-07，用户授权的行为变更）：
    NULL 分区会让所有无租户用户共享同一份本体，与改造前的「全局单例」缺陷等价。

    :param auto_commit: 仓储是否自行提交。批量写（TTL 导入）传 `False`，
        由路由在一个显式事务里收口，失败整体回滚（评审 IM-05）。
    """
    if tenant_id is None:
        raise HTTPException(status_code=400, detail=TENANT_REQUIRED_DETAIL)

    from app.ai.knowledge.owl_engine import WikiOwlEngine
    from app.services.ontology.ontology_repository import OntologyRepository

    return WikiOwlEngine.from_store(
        OntologyRepository(db, tenant_id, auto_commit=auto_commit)
    )


def _require_tenant_id(current_user: SysUser) -> int:
    """取当前用户租户 ID，为空则拒绝请求（`400 tenant_required`）。

    评审 IM-07 + 用户授权：不再让无租户请求落到 NULL 分区共享本体。
    """
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        logger.warning("拒绝无租户的本体请求：当前用户缺少 tenant_id")
        raise HTTPException(status_code=400, detail=TENANT_REQUIRED_DETAIL)
    return tenant_id


def _write_error_response(
    exc: BaseException, *, client_prefix: str = ""
) -> HTTPException:
    """把写路径异常映射成**不泄漏内部细节**的 HTTP 响应（评审 R2-04 / CWE-209）。

    * 数据库连不上（`OperationalError`）→ 503，服务端问题；
    * 其它 `SQLAlchemyError` → 400 + 固定文案，异常体只进日志（原文含完整 SQL
      与绑定参数，含 `tenant_id`，不能回显）；
    * `ValueError` / 业务校验错误 → 400 + 原文（客户端错误，可安全回显）。

    :param client_prefix: 客户端错误文案前缀（如 `TTL 导入失败`）。
    """
    if isinstance(exc, OperationalError):
        logger.exception("本体服务不可用（数据库错误），已回滚")
        return HTTPException(status_code=503, detail=SERVICE_UNAVAILABLE_DETAIL)
    if isinstance(exc, SQLAlchemyError):
        logger.exception("本体写入失败（数据库错误），已回滚")
        return HTTPException(status_code=400, detail=WRITE_FAILED_DETAIL)
    logger.warning("本体写入失败（客户端错误），已回滚: %s", exc)
    detail = str(exc)
    if client_prefix:
        detail = f"{client_prefix}: {detail}"
    return HTTPException(status_code=400, detail=detail)


# ── OWL Class CRUD ───────────────────────────────────────────────────────────

@router.post("/classes")
def create_class(
    body: OwlClassCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """注册一个 OWL Class。"""
    engine = get_owl_engine(_require_tenant_id(current_user), db)
    try:
        owl_class = engine.register_class(
            uri=body.uri,
            label=body.label,
            comment=body.comment,
            parent_uris=body.parent_uris,
        )
        db.commit()
    except (ValueError, SQLAlchemyError) as exc:
        db.rollback()
        raise _write_error_response(exc)
    return owl_class.to_dict()


@router.get("/classes")
def list_classes(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出当前租户的所有 OWL Class。"""
    engine = get_owl_engine(_require_tenant_id(current_user), db)
    return [c.to_dict() for c in engine.list_classes()]


@router.get("/hierarchy")
def get_hierarchy(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取当前租户的 OWL 类层级树。"""
    engine = get_owl_engine(_require_tenant_id(current_user), db)
    return [node.to_dict() for node in engine.get_hierarchy()]


# ── TTL 导入/导出 ─────────────────────────────────────────────────────────────

@router.post("/import-ttl")
async def import_ttl(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """导入 TTL 本体文件。"""
    content = await file.read()
    try:
        ttl_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="TTL 文件必须为 UTF-8 编码")

    # auto_commit=False：整个导入在同一个事务里完成，失败整体回滚，
    # 不会留下「导入了一半的本体」（评审 IM-05）。
    engine = get_owl_engine(_require_tenant_id(current_user), db, auto_commit=False)
    try:
        added = engine.import_ttl(ttl_str)
        db.commit()
    except (ValueError, SQLAlchemyError) as exc:
        db.rollback()
        # SQLAlchemy 的 DataError / IntegrityError 不属于 ValueError，
        # 只捕获 ValueError 会让超长 URI 之类的错误直接冒泡成 500。
        raise _write_error_response(exc, client_prefix="TTL 导入失败")

    return {"message": f"导入成功, 新增 {added} 条三元组", "added": added}


@router.get("/export-ttl")
def export_ttl(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """导出当前租户本体为 TTL 格式。"""
    engine = get_owl_engine(_require_tenant_id(current_user), db)
    ttl = engine.export_ttl()
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=ttl,
        media_type="text/turtle",
        headers={"Content-Disposition": "attachment; filename=wiki-ontology.ttl"},
    )


# ── 统计 ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取当前租户的本体统计信息。"""
    engine = get_owl_engine(_require_tenant_id(current_user), db)
    return engine.stats()


# ── 按 OWL 类查询文章 ────────────────────────────────────────────────────────

@router.get("/articles/{class_uri:path}")
def get_articles_by_class(
    class_uri: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取属于指定 OWL 类的所有文章。"""
    tenant_id = _require_tenant_id(current_user)
    # 使用 JSONB 包含查询（`@>`）；租户过滤在端点内**显式**声明，
    # 不依赖全局 do_orm_execute 拦截器（后者在 tenant_id 为空/超管时会跳过过滤）。
    articles = db.execute(
        select(WikiArticle)
        .where(WikiArticle.status >= 0)
        .where(WikiArticle.tenant_id == tenant_id)
        .where(WikiArticle.owl_class_uris.contains([class_uri]))
        .order_by(WikiArticle.updated_at.desc())
    ).scalars().all()

    return {
        "class_uri": class_uri,
        "total": len(articles),
        "items": [
            {
                "id": a.id,
                "slug": a.slug,
                "title": a.title,
                "summary": a.summary,
                "version": a.version,
                "updated_at": str(a.updated_at) if a.updated_at else None,
            }
            for a in articles
        ],
    }
