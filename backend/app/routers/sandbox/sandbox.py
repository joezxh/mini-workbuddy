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
