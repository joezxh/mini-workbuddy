"""Workspace 工作空间管理路由。"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.schemas.ai.ai_workspace import (
    AiWorkspaceCreate, AiWorkspaceUpdate, AiWorkspaceResp, AiWorkspaceSimpleResp,
    AiWorkspaceLinkMcpReq, AiWorkspaceLinkSkillReq,
)
from app.services.ai.ai_workspace_service import AiWorkspaceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/workspaces", tags=["工作空间管理"])


@router.get("", response_model=list[AiWorkspaceResp])
def list_workspaces(
    scope: Optional[str] = Query(None, description="筛选: public/private"),
    keyword: Optional[str] = Query(None, description="名称搜索"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出当前用户可见的工作空间。"""
    svc = AiWorkspaceService(db)
    return svc.list_workspaces(user_id=current_user.user_id, scope=scope, keyword=keyword)


@router.get("/simple", response_model=list[AiWorkspaceSimpleResp])
def list_workspaces_simple(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """工作空间简易列表（用于下拉选择）。"""
    svc = AiWorkspaceService(db)
    return svc.list_workspaces(user_id=current_user.user_id)


@router.post("", response_model=AiWorkspaceResp)
def create_workspace(
    data: AiWorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建工作空间。"""
    svc = AiWorkspaceService(db)
    return svc.create_workspace(data, user_id=current_user.user_id, username=current_user.username)


@router.get("/{workspace_id}", response_model=AiWorkspaceResp)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取工作空间详情。"""
    svc = AiWorkspaceService(db)
    ws = svc.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return ws


@router.put("/{workspace_id}", response_model=AiWorkspaceResp)
def update_workspace(
    workspace_id: int,
    data: AiWorkspaceUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新工作空间。"""
    svc = AiWorkspaceService(db)
    try:
        ws = svc.update_workspace(workspace_id, data)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not ws:
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return ws


@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """软删除工作空间。"""
    svc = AiWorkspaceService(db)
    try:
        if not svc.delete_workspace(workspace_id):
            raise HTTPException(status_code=404, detail="工作空间不存在")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"message": "删除成功"}


@router.post("/{workspace_id}/activate")
def activate_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """设为当前用户的默认工作空间。"""
    svc = AiWorkspaceService(db)
    if not svc.activate_workspace(workspace_id, current_user.user_id):
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return {"message": "已设为默认"}


# ── 资源关联 ──


@router.get("/{workspace_id}/mcps")
def list_workspace_mcps(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出工作空间生效的 MCP 服务 ID（公共空间返回全部启用 MCP）。"""
    svc = AiWorkspaceService(db)
    ws = svc.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return {"mcp_ids": svc.resolve_effective_mcp_ids(workspace_id)}


@router.post("/{workspace_id}/mcps")
def link_mcp(
    workspace_id: int,
    data: AiWorkspaceLinkMcpReq,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """关联 MCP 服务到工作空间。"""
    svc = AiWorkspaceService(db)
    if not svc.link_mcp(workspace_id, data.mcp_id):
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return {"message": "关联成功"}


@router.delete("/{workspace_id}/mcps/{mcp_id}")
def unlink_mcp(
    workspace_id: int,
    mcp_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """取消关联 MCP 服务。"""
    svc = AiWorkspaceService(db)
    if not svc.unlink_mcp(workspace_id, mcp_id):
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return {"message": "取消关联成功"}


@router.get("/{workspace_id}/skills")
def list_workspace_skills(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出工作空间生效的技能 ID（公共空间返回全部启用技能）。"""
    svc = AiWorkspaceService(db)
    ws = svc.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return {"skill_ids": svc.resolve_effective_skill_ids(workspace_id)}


@router.post("/{workspace_id}/skills")
def link_skill(
    workspace_id: int,
    data: AiWorkspaceLinkSkillReq,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """关联技能到工作空间。"""
    svc = AiWorkspaceService(db)
    if not svc.link_skill(workspace_id, data.skill_id):
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return {"message": "关联成功"}


@router.delete("/{workspace_id}/skills/{skill_id}")
def unlink_skill(
    workspace_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """取消关联技能。"""
    svc = AiWorkspaceService(db)
    if not svc.unlink_skill(workspace_id, skill_id):
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return {"message": "取消关联成功"}
