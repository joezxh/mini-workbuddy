"""推演沙盘沙箱域 REST 端点（S1–S21，spec §4.2）。

前缀 ``/api/v1/dataops`` 由父 router 提供，本模块用相对路径 ``/ontologies/sandbox/...``，
经 ``dataops.router.include_router(sandbox_router)`` 单点挂载。错误契约（R3）：领域错误
由服务抛 :class:`ApiError`，本模块不手写 try/except。路由风格抄 ``routers/ontology/ontology.py``。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser
from app.services.sandbox.sandbox_element_service import SandboxElementService
from app.services.sandbox.sandbox_scene_service import SandboxSceneService

router = APIRouter(tags=["推演沙盘 沙箱域"])


def _tenant(current_user: SysUser) -> int:
    from app.core.api_error import ApiError
    tid = getattr(current_user, "tenant_id", None)
    if tid is None:
        raise ApiError("TENANT_REQUIRED", "缺少租户上下文", http_status=403)
    return tid


# --------------------------------------------------------------------- 请求体

class SceneCreate(BaseModel):
    ontology_id: int
    name: str = Field(..., min_length=1, max_length=200)
    clone_scope: dict = Field(default_factory=dict)
    tick_max: int = Field(default=12, ge=1, le=1000)
    exec_mode: str = Field(default="auto")


class ScenePatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    exec_mode: Optional[str] = None


class ElementUpsert(BaseModel):
    kind: str
    code: str = Field(..., min_length=1, max_length=64)
    label: Optional[str] = Field(default=None, max_length=200)
    from_ref: Optional[str] = None
    to_ref: Optional[str] = None
    condition_expr_json: Optional[dict] = None
    effect_expr_json: Optional[dict] = None
    activation_tick: Optional[int] = None
    confidence: Optional[float] = None


class ElementReview(BaseModel):
    decision: str = Field(..., pattern="^(accept|reject)$")


# --------------------------------------------------------------------- S1–S5

@router.post("/ontologies/sandbox/scenes", status_code=201)
def create_scene(body: SceneCreate, db: Session = Depends(get_db),
                 user: SysUser = Depends(get_current_user)):
    svc = SandboxSceneService(db, _tenant(user))
    return svc.create_scene(ontology_id=body.ontology_id, name=body.name,
                            clone_scope=body.clone_scope, tick_max=body.tick_max,
                            exec_mode=body.exec_mode, creator_id=getattr(user, "user_id", None))


@router.get("/ontologies/sandbox/scenes")
def list_scenes(ontology_id: Optional[int] = Query(default=None),
                status: Optional[str] = Query(default=None),
                db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    return SandboxSceneService(db, _tenant(user)).list_scenes(ontology_id=ontology_id, status=status)


@router.get("/ontologies/sandbox/scenes/{scene_id}")
def get_scene(scene_id: int, db: Session = Depends(get_db),
              user: SysUser = Depends(get_current_user)):
    return SandboxSceneService(db, _tenant(user)).get_scene(scene_id)


@router.delete("/ontologies/sandbox/scenes/{scene_id}", status_code=204)
def delete_scene(scene_id: int, db: Session = Depends(get_db),
                 user: SysUser = Depends(get_current_user)):
    SandboxSceneService(db, _tenant(user)).delete_scene(scene_id)
    return Response(status_code=204)


@router.patch("/ontologies/sandbox/scenes/{scene_id}")
def patch_scene(scene_id: int, body: ScenePatch, db: Session = Depends(get_db),
                user: SysUser = Depends(get_current_user)):
    return SandboxSceneService(db, _tenant(user)).patch_scene(
        scene_id, name=body.name, exec_mode=body.exec_mode)


# --------------------------------------------------------------------- S13–S15

@router.get("/ontologies/sandbox/scenes/{scene_id}/elements")
def list_elements(scene_id: int, kind: Optional[str] = Query(default=None),
                  status: Optional[str] = Query(default=None),
                  db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    return SandboxElementService(db, _tenant(user)).list_elements(
        scene_id, kind=kind, status=status)


@router.post("/ontologies/sandbox/scenes/{scene_id}/elements", status_code=201)
def create_element(scene_id: int, body: ElementUpsert, db: Session = Depends(get_db),
                   user: SysUser = Depends(get_current_user)):
    return SandboxElementService(db, _tenant(user)).upsert_element(
        scene_id, body.model_dump(), origin="human", creator_id=getattr(user, "user_id", None))


@router.post("/ontologies/sandbox/scenes/{scene_id}/elements/llm-draft")
def draft_elements(scene_id: int, model_id: Optional[int] = Query(default=None),
                   db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    return SandboxElementService(db, _tenant(user)).draft_llm(scene_id, model_id=model_id)


@router.put("/ontologies/sandbox/elements/{element_id}")
def update_element(element_id: int, body: ElementUpsert, db: Session = Depends(get_db),
                   user: SysUser = Depends(get_current_user)):
    return SandboxElementService(db, _tenant(user)).update_element(
        element_id, body.model_dump(exclude_unset=True))


@router.delete("/ontologies/sandbox/elements/{element_id}", status_code=204)
def delete_element(element_id: int, db: Session = Depends(get_db),
                   user: SysUser = Depends(get_current_user)):
    SandboxElementService(db, _tenant(user)).delete_element(element_id)
    return Response(status_code=204)


@router.post("/ontologies/sandbox/elements/{element_id}/review")
def review_element(element_id: int, body: ElementReview, db: Session = Depends(get_db),
                   user: SysUser = Depends(get_current_user)):
    return SandboxElementService(db, _tenant(user)).review_element(element_id, body.decision)
