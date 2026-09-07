"""技能仓库（Skill Hub）API。

兼容 Git 仓库与 SkillHub 云市场等多来源：
- GET    /repos                                 仓库列表（含官方 SkillHub 云市场）
- POST   /repos                                新增仓库
- PUT    /repos/{id}                           修改仓库
- DELETE /repos/{id}                          删除仓库
- POST   /repos/{id}/refresh                  刷新仓库（云市场为刷新分类缓存）
- GET    /repos/{id}/categories               分类列表
- GET    /repos/{id}/skills                   技能列表（检索 / 分类 / 分页）
- POST   /repos/{id}/skills/{skill_id}/install  一键安装
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.middleware.audit_logger import AuditLogRoute
from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.ai.ai_skill_hub_repo import AiSkillHubRepo
from app.services.ai.ai_skill_hub_service import AiSkillHubService

router = APIRouter(route_class=AuditLogRoute, tags=["技能仓库"])


class RepoCreate(BaseModel):
    name: str
    url: str
    branch: str = "main"


class RepoUpdate(BaseModel):
    name: str
    url: str
    branch: str = "main"


def _repo_to_dict(repo: AiSkillHubRepo) -> dict:
    return {
        "id": repo.id,
        "name": repo.name,
        "url": repo.url,
        "branch": repo.branch,
        "is_official": repo.is_official,
        "sort_order": repo.sort_order,
        "source_type": getattr(repo, "source_type", "git"),
        "created_at": repo.created_at.isoformat() if repo.created_at else None,
        "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
    }


@router.get("/repos")
def list_repos(db=Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """仓库列表（含官方 SkillHub 云市场）。"""
    return [_repo_to_dict(r) for r in AiSkillHubService(db).list_repos()]


@router.post("/repos")
def create_repo(
    payload: RepoCreate,
    db=Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiSkillHubService(db)
    try:
        repo = svc.create_repo(payload.name, payload.url, payload.branch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _repo_to_dict(repo)


@router.put("/repos/{repo_id}")
def update_repo(
    repo_id: int,
    payload: RepoUpdate,
    db=Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiSkillHubService(db)
    try:
        repo = svc.update_repo(repo_id, payload.name, payload.url, payload.branch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _repo_to_dict(repo)


@router.delete("/repos/{repo_id}")
def delete_repo(
    repo_id: int,
    db=Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiSkillHubService(db)
    try:
        svc.delete_repo(repo_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/repos/{repo_id}/refresh")
def refresh_repo(
    repo_id: int,
    db=Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiSkillHubService(db)
    try:
        svc.refresh_repo(repo_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/repos/{repo_id}/categories")
def list_categories(
    repo_id: int,
    db=Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiSkillHubService(db)
    try:
        return svc.list_categories(repo_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/repos/{repo_id}/skills")
def list_skills(
    repo_id: int,
    category: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiSkillHubService(db)
    try:
        return svc.list_skills(repo_id, category=category, q=q, page=page, page_size=page_size)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/repos/{repo_id}/skills/{skill_id}/install")
def install_skill(
    repo_id: int,
    skill_id: str,
    db=Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiSkillHubService(db)
    try:
        return svc.install_skill(repo_id, skill_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
