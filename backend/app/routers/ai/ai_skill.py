"""AI 技能路由"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.middleware.audit_logger import AuditLogRoute
from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.services.ai.ai_skill_admin_service import AiSkillAdminService
from app.services.ai.ai_session_skill_service import AiSessionSkillService


router = APIRouter(route_class=AuditLogRoute)


# ── Schemas ──────────────────────────────────────────────────────────────────


class SkillPackageInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    scripts: List[Dict[str, Any]] = []


class SkillListResponse(BaseModel):
    packages: List[Dict[str, Any]]
    total: int


# ── 管理端点 ────────────────────────────────────────────────────────────────


class CreatePackageRequest(BaseModel):
    package_id: str
    name: str
    category: str = "other"
    description: Optional[str] = None
    icon: str = "tool"
    version: str = "1.0.0"


class UpdatePackageRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    version: Optional[str] = None
    enabled: Optional[bool] = None


class CreateScriptRequest(BaseModel):
    script_id: str
    name: str
    command: str
    description: Optional[str] = None
    params: Optional[List[Dict]] = None
    sort_order: int = 0


class UpdateScriptRequest(BaseModel):
    name: Optional[str] = None
    command: Optional[str] = None
    description: Optional[str] = None
    params: Optional[List[Dict]] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class SaveSkillMarkdownRequest(BaseModel):
    content: str


@router.get("", response_model=SkillListResponse)
def list_skills(
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取所有技能包列表（支持按 category/enabled 过滤）"""
    svc = AiSkillAdminService()
    packages = svc.list_packages(db, category=category, enabled=enabled)
    return {"packages": packages, "total": len(packages)}


@router.get("/{package_id}")
def get_skill_package(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取单个技能包详情（含脚本列表）"""
    svc = AiSkillAdminService()
    pkg = svc.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="技能包不存在")
    return pkg


@router.post("")
def create_skill_package(
    req: CreatePackageRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """新建技能包（自动创建目录）"""
    svc = AiSkillAdminService()
    try:
        pkg = svc.create_package(
            db,
            package_id=req.package_id,
            name=req.name,
            category=req.category,
            description=req.description,
            icon=req.icon,
            version=req.version,
            created_by=current_user.user_id,
        )
        return {"package_id": pkg.package_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{package_id}")
def update_skill_package(
    package_id: str,
    req: UpdatePackageRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新技能包元数据"""
    svc = AiSkillAdminService()
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    pkg = svc.update_package(db, package_id, **fields)
    if not pkg:
        raise HTTPException(status_code=404, detail="技能包不存在")
    return {"ok": True}


@router.delete("/{package_id}")
def delete_skill_package(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除技能包（级联删除脚本记录和文件系统目录）"""
    svc = AiSkillAdminService()
    ok = svc.delete_package(db, package_id)
    if not ok:
        raise HTTPException(status_code=404, detail="技能包不存在")
    return {"deleted": True}


@router.post("/import")
def import_skill_package(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """上传 ZIP 导入技能包"""
    svc = AiSkillAdminService()
    try:
        content = file.file.read()
        result = svc.import_zip(db, content)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{package_id}/export")
def export_skill_package(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """导出技能包为 ZIP"""
    svc = AiSkillAdminService()
    try:
        data = svc.export_zip(db, package_id)
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{package_id}.zip"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── 脚本端点 ────────────────────────────────────────────────────────────────


@router.get("/{package_id}/scripts")
def list_scripts(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出指定包下的脚本"""
    pkg = AiSkillAdminService().get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="技能包不存在")
    return {"scripts": pkg.get("scripts", [])}


@router.post("/{package_id}/scripts")
def create_script(
    package_id: str,
    req: CreateScriptRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """新建脚本（自动创建占位文件）"""
    svc = AiSkillAdminService()
    try:
        script = svc.create_script(
            db,
            package_id=package_id,
            script_id=req.script_id,
            name=req.name,
            command=req.command,
            description=req.description,
            params=req.params,
            sort_order=req.sort_order,
        )
        return {"script_id": script.script_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{package_id}/scripts/{script_id}")
def update_script(
    package_id: str,
    script_id: str,
    req: UpdateScriptRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新脚本"""
    svc = AiSkillAdminService()
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    script = svc.update_script(db, package_id, script_id, **fields)
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return {"ok": True}


@router.delete("/{package_id}/scripts/{script_id}")
def delete_script(
    package_id: str,
    script_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除脚本"""
    svc = AiSkillAdminService()
    ok = svc.delete_script(db, package_id, script_id)
    if not ok:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return {"deleted": True}


# 说明：技能执行已统一走 POST /ai-agent/chat/stream（Gateway SkillHandler，
# SSE 流式 + agent_execution_event 持久化 + /skill-execution/{id}/events 回放），
# 旧版同步 /execute 与 /result/{task_id} 任务轮询端点（V1）已删除。


# ── SKILL.md 文档端点 ──────────────────────────────────────────────────────


@router.get("/{package_id}/skill-md")
def get_skill_markdown(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """读取 SKILL.md 内容（数据库 skill_markdown 优先，fallback 文件系统）"""
    svc = AiSkillAdminService()
    content = svc.get_skill_markdown(db, package_id)
    if content is None:
        raise HTTPException(status_code=404, detail="SKILL.md 文件不存在")
    return {"content": content}


@router.put("/{package_id}/skill-md")
def save_skill_markdown(
    package_id: str,
    req: SaveSkillMarkdownRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """保存 SKILL.md 内容（数据库 skill_markdown + 文件系统同步）

    保存后技能执行将以数据库内容优先（见 SkillExecutionService._load_skill）。
    """
    svc = AiSkillAdminService()
    try:
        pkg = svc.save_skill_markdown(db, package_id, req.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "package": pkg}


# ── 技能执行历史会话 ────────────────────────────────────────────────────────


class GetSessionsRequest(BaseModel):
    """获取技能会话列表请求参数"""
    skill_id: str
    page: int = 1
    page_size: int = 20


class GetMessagesRequest(BaseModel):
    """获取会话消息列表请求参数"""
    session_id: int
    limit: int = 50
    before_message_id: Optional[int] = None


class SessionListResponse(BaseModel):
    """会话列表响应"""
    total: int
    page: int
    page_size: int
    sessions: List[Dict[str, Any]] = []


class MessageResponse(BaseModel):
    """单条消息响应"""
    message_id: int
    role: str
    content: str
    message_type: str = "text"
    tool_calls: Optional[Dict[str, Any]] = None
    tool_results: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict[str, Any]] = None
    agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    created_at: str


class MessagesListResponse(BaseModel):
    """消息列表响应"""
    messages: List[MessageResponse] = []


@router.post("/{package_id}/sessions", response_model=SessionListResponse)
def get_skill_sessions(
    package_id: str,
    request: GetSessionsRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取特定技能的所有会话（分页）"""
    try:
        result = AiSessionSkillService.get_sessions_by_skill(
            db=db,
            skill_id=request.skill_id,
            page=request.page,
            page_size=request.page_size,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


@router.post("/{package_id}/messages", response_model=MessagesListResponse)
def get_session_messages(
    package_id: str,
    request: GetMessagesRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取指定会话的所有消息记录（分页）"""
    try:
        messages = AiSessionSkillService.get_messages_by_session(
            db=db,
            session_id=request.session_id,
            limit=request.limit,
            before_message_id=request.before_message_id,
        )
        return MessagesListResponse(messages=[MessageResponse(**m) for m in messages])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


@router.get("/{package_id}/session/{session_id}", response_model=Dict[str, Any])
def get_session_detail(
    package_id: str,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取会话详细信息"""
    try:
        detail = AiSessionSkillService.get_session_detail(db=db, session_id=session_id)
        if not detail:
            raise HTTPException(status_code=404, detail="会话不存在")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")
