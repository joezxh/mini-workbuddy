"""孪生应用编排端点 T1～T7（spec §6.1）。

完整前缀写在 router 自身（与 `app.routers.kb.kg:26` 同律），因此 `router_registry`
的 `RouterSpec` 不再叠加 prefix。路径参数一律标 `int`，因此 `/cards/{card_id}`
与 `/cards/from-template` 不会互相遮蔽（字面路径优先由 Starlette 的注册顺序决定，
因此把字面最具体的端点放在参数量端点之前）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.tool_manager.tool_context import build_user_context
from app.core.api_error import ApiError, TWIN_TENANT_REQUIRED
from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser
from app.services.twin.twin_data_service import TwinDataService
from app.services.twin.twin_publish_service import TwinPublishService
from app.services.twin.twin_service import TEMPLATES, TwinService

router = APIRouter(prefix="/api/v1/twins", tags=["孪生应用"])

# 只读页与工作台共用同一个模块，但**不同前缀**：工作台走 /api/v1/twins/*（要写权限），
# 只读页走 /api/v1/twin-p/*（只要发布授权）。分成两个 APIRouter 才可能在
# router_registry 里各自挂载，也才挡住「把只读端点误挂到写权限链上」的错。
publish_router = APIRouter(prefix="/api/v1/twin-p", tags=["孪生应用·只读页"])


def _require_tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise ApiError(TWIN_TENANT_REQUIRED, "登录用户缺少租户上下文", 400)
    return int(tenant_id)


def _svc(db: Session, current_user: SysUser) -> TwinService:
    """角色码走 `build_user_context()`（失败降级为最小权限），不自己拼 SQL 查 sys_role。"""
    ctx = build_user_context(db, current_user)
    return TwinService(db, _require_tenant_id(current_user),
                       int(getattr(current_user, "user_id", 0) or 0),
                       tuple(ctx.role_codes) if ctx else ())


def _data_svc(db: Session, current_user: SysUser) -> TwinDataService:
    """取数上下文走 `build_user_context()`：**同一个 ctx 同时驱动脱敏豁免与缓存键**，
    两处各取一次角色就会不一致（R3 的事故面）。

    `session_factory` 从当前请求 session 的 bind 派生：生产上就是应用引擎（等价
    `SessionLocal`），测试里自然落到带 `search_path` 监听器的测试引擎——无需为测试另开配置。
    """
    ctx = build_user_context(db, current_user)
    bind = db.get_bind()
    return TwinDataService(db, _require_tenant_id(current_user),
                           int(getattr(current_user, "user_id", 0) or 0), ctx,
                           session_factory=lambda: Session(bind, expire_on_commit=False))


def _pub_svc(db: Session, current_user: SysUser) -> TwinPublishService:
    """`session_factory` 与 `_data_svc()` 同一做法：只读页取数也要在工作线程里开新 Session，
    不能复用当前请求 Session（SQLAlchemy Session 不是线程安全的）。"""
    ctx = build_user_context(db, current_user)
    bind = db.get_bind()
    return TwinPublishService(db, _require_tenant_id(current_user),
                              int(getattr(current_user, "user_id", 0) or 0), ctx,
                              session_factory=lambda: Session(bind, expire_on_commit=False))


class CardCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    icon: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = None
    ontology_id: int
    ontology_version: int = Field(..., ge=1, description="只能钉已发布版本")
    scene_key: Optional[str] = Field(None, max_length=64)


class CardPatchBody(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    icon: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = None
    scene_key: Optional[str] = Field(None, max_length=64)
    runtime_state: Optional[str] = Field(None, description="draft|live|paused")
    ontology_id: Optional[int] = None
    ontology_version: Optional[int] = Field(None, ge=1)


class TemplateBody(BaseModel):
    template_key: str = Field(..., description=f"内置模板：{sorted(TEMPLATES)}")
    name: str = Field(..., min_length=1, max_length=200)
    ontology_id: Optional[int] = None


class PageCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    refresh_json: Optional[Dict[str, Any]] = None


class PagePatchBody(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    refresh_json: Optional[Dict[str, Any]] = None


class ReorderBody(BaseModel):
    page_ids: List[int] = Field(..., min_length=1)


class WidgetCreateBody(BaseModel):
    widget_key: str = Field(..., min_length=1, max_length=32)
    title: Optional[str] = Field(None, max_length=200)
    query_id: Optional[int] = None
    param_values_json: Dict[str, Any] = Field(default_factory=dict)
    display_json: Dict[str, Any] = Field(default_factory=dict)
    grid_json: Dict[str, Any] = Field(default_factory=dict)
    refresh_json: Optional[Dict[str, Any]] = None


class WidgetPatchBody(BaseModel):
    widget_key: Optional[str] = Field(None, max_length=32)
    title: Optional[str] = Field(None, max_length=200)
    query_id: Optional[int] = None          # 显式 null = 解绑（因此端点用 exclude_unset）
    param_values_json: Optional[Dict[str, Any]] = None
    display_json: Optional[Dict[str, Any]] = None
    grid_json: Optional[Dict[str, Any]] = None
    refresh_json: Optional[Dict[str, Any]] = None


class LayoutItem(BaseModel):
    widget_id: int
    grid_json: Dict[str, Any]


class LayoutBody(BaseModel):
    items: List[LayoutItem] = Field(..., min_length=1, max_length=64)


class DataBody(BaseModel):
    """整页取数的**可选**页面级参数（spec §2.2 `{params}`）：只对本查询声明过的同名参数生效。"""

    params: Dict[str, Any] = Field(default_factory=dict)


class PublishBody(BaseModel):
    """发布参数（spec §3.5）：`access=org` 同租户可见，`role` 仅指定角色可见（public 留 P1）。"""

    access: str = Field("org", description="org|role")
    role_codes: Optional[List[str]] = Field(None, max_length=32)


# ---------------------------------------------------------------- T1–T3 卡片


@router.get("/cards")
def list_cards(db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)) -> dict:
    """三组分派：我的 / 共享给我的 / 受限（原型左标 `_myCards` 与 🔒 徽标）。"""
    return _svc(db, current_user).list_cards()


@router.post("/cards/from-template", status_code=201)
def create_from_template(body: TemplateBody, db: Session = Depends(get_db),
                         current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).create_from_template(
        body.template_key, body.name, body.ontology_id)


@router.post("/cards", status_code=201)
def create_card(body: CardCreateBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).create_card(body.model_dump())


@router.get("/cards/{card_id}")
def get_card(card_id: int, db: Session = Depends(get_db),
             current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).get_card(card_id)


@router.patch("/cards/{card_id}")
def update_card(card_id: int, body: CardPatchBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).update_card(card_id, body.model_dump(exclude_unset=True))


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> Response:
    _svc(db, current_user).delete_card(card_id)
    return Response(status_code=204)


# ------------------------------------------------------------------- T4 页面


@router.get("/cards/{card_id}/pages")
def list_pages(card_id: int, db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)) -> list:
    return _svc(db, current_user).list_pages(card_id)


@router.post("/cards/{card_id}/pages", status_code=201)
def create_page(card_id: int, body: PageCreateBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).create_page(card_id, body.name, body.refresh_json)


@router.post("/cards/{card_id}/pages/reorder")
def reorder_pages(card_id: int, body: ReorderBody, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)) -> list:
    return _svc(db, current_user).reorder_pages(card_id, body.page_ids)


@router.patch("/pages/{page_id}")
def update_page(page_id: int, body: PagePatchBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).update_page(page_id, body.model_dump(exclude_unset=True))


@router.delete("/pages/{page_id}", status_code=204)
def delete_page(page_id: int, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> Response:
    _svc(db, current_user).delete_page(page_id)
    return Response(status_code=204)


# -------------------------------------------------------------- T5–T7 组件


@router.get("/pages/{page_id}/widgets")
def list_widgets(page_id: int, db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)) -> list:
    return _svc(db, current_user).list_widgets(page_id)


@router.post("/pages/{page_id}/widgets", status_code=201)
def add_widget(page_id: int, body: WidgetCreateBody, db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).add_widget(page_id, body.model_dump(exclude_unset=True))


@router.post("/pages/{page_id}/widgets/layout")
def save_layout(page_id: int, body: LayoutBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> list:
    """拖拽、自动布局与 AI 应用共用本口（确定性批量写，可整体回滚）。"""
    return _svc(db, current_user).save_layout(
        page_id, [it.model_dump() for it in body.items])


@router.patch("/widgets/{widget_id}")
def update_widget(widget_id: int, body: WidgetPatchBody, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).update_widget(widget_id, body.model_dump(exclude_unset=True))


@router.delete("/widgets/{widget_id}", status_code=204)
def delete_widget(widget_id: int, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)) -> Response:
    _svc(db, current_user).delete_widget(widget_id)
    return Response(status_code=204)


# ------------------------------------------------------------ T8–T9 取数


@router.post("/pages/{page_id}/data")
def load_page_data(page_id: int, body: Optional[DataBody] = None,
                   db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)) -> dict:
    """T8：整页刷新只发 1 个请求（W8）。空体合法（组件用已存实值）；
    单组件失败只影响该组件的 state，**端点本身永远回 200**。"""
    return _data_svc(db, current_user).load_page(page_id, body.params if body else None)


@router.get("/widgets/{widget_id}/data")
def load_widget_data(widget_id: int, db: Session = Depends(get_db),
                     current_user: SysUser = Depends(get_current_user)) -> dict:
    """T9：单组件刷新与错误重试（原型 error 态的 ↻），只用已存 `param_values_json`。"""
    return _data_svc(db, current_user).load_widget(widget_id)


# ------------------------------------------------------------ T10 发布 / 停用


@router.post("/pages/{page_id}/publish")
def publish_page(page_id: int, body: Optional[PublishBody] = None,
                 db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)) -> dict:
    """T10 发布。**恒回 200 而不是 201**：同一页面的重复发布是同一资源的版本推进
    （slug 不变、version+1），回 201 会诱导前端把它当新资源再插一条。"""
    b = body or PublishBody()
    return _pub_svc(db, current_user).publish(page_id, access=b.access, role_codes=b.role_codes)


@router.delete("/publish/{publish_id}", status_code=204)
def unpublish_page(publish_id: int, db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)) -> Response:
    """T10 停用：改 `status='disabled'`，留行保审计与版本史，slug 不回收。"""
    _pub_svc(db, current_user).unpublish(publish_id)
    return Response(status_code=204)


# ---------------------------------------------------------- T11 只读页（发布前缀）


@publish_router.get("/{slug}")
def read_published_page(slug: str, db: Session = Depends(get_db),
                        current_user: SysUser = Depends(get_current_user)) -> dict:
    """T11 元数据：结构来自发布快照，发布后的编辑动作不影响已发布页面。

    仍然要 `get_current_user`：P0 只发**登录态**只读页（§7.1 7a），分享票据与公开链接属 P1
    （T17，新攻击面必须与水印/限流同批）。"""
    return _pub_svc(db, current_user).get_by_slug(slug)


@publish_router.post("/{slug}/data")
def read_published_data(slug: str, body: Optional[DataBody] = None,
                        db: Session = Depends(get_db),
                        current_user: SysUser = Depends(get_current_user)) -> dict:
    """T11 取数：数据恒实时。复用 Task 7 的 `DataBody`，**不另建同名 Body**。"""
    return _pub_svc(db, current_user).run_by_slug(slug, body.params if body else None)
