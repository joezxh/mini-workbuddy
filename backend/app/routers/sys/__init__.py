from app.middleware.audit_logger import AuditLogRoute
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.deps import get_db, require_admin
from app.models.sys.sys_user import SysUser
from app.services.auth_service import AuthService

router = APIRouter(route_class=AuditLogRoute)


def _tenant_name_map(db: Session) -> dict:
    """一次性加载 租户ID -> 租户名称 映射，避免逐行查询。"""
    from app.models.sys.sys_tenant import SysTenant
    return {t.tenant_id: t.name for t in db.query(SysTenant).all()}


def _effective_tenant_id(admin: "SysUser", requested: Optional[int]) -> Optional[int]:
    """计算实际生效的租户过滤条件。

    - 超级管理员（自身 tenant_id 为 0 或空）可查看全部租户，使用传入的 requested；
    - 普通租户管理员强制只能查看自己所属租户，忽略传入参数。
    """
    admin_tenant = admin.tenant_id or 0
    if admin_tenant != 0:
        return admin_tenant
    return requested


class UserUpdate(BaseModel):
    realName: Optional[str] = None
    real_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class PasswordReset(BaseModel):
    oldPassword: str
    newPassword: str


class UserCreate(BaseModel):
    username: str
    password: str
    realName: str
    phone: Optional[str] = None
    email: Optional[str] = None
    tenantId: Optional[int] = None


class RoleAssignReq(BaseModel):
    roleIds: List[int]


class StatusUpdate(BaseModel):
    status: str


# ===========================================================
# 控制台统计
# ===========================================================

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    """MinWorkBuddy 控制台统计 —— 通用 AI 工作台指标。

    各表软删除字段并不统一，故统一走 ORM 按模型字段统计，避免裸 SQL 与模型脱节
    （旧实现引用了不存在的 tool_definition / skill_registry 表以及不存在的
    is_deleted 列，会直接 500）：
      * agent_config / agent_team / sys_user : is_deleted
      * ai_tool_definition                   : status = 'enabled'
      * ai_skill_package                     : enabled
      * ai_chat_session                      : 无软删除字段（status: active/archived）
      * agent_team_run.total_tokens          : Token 消耗累计
    """
    from app.models.ai.ai_chat import AiChatSession
    from app.models.ai.ai_skill_package import AiSkillPackage
    from app.models.ai.ai_tool_definition import AiToolDefinition
    from app.models.agent.agent_config import AgentConfig
    from app.models.agent.agent_team import AgentTeam
    from app.models.agent.agent_team_run import AgentTeamRun

    def count(column, *criteria) -> int:
        query = db.query(func.count(column))
        for criterion in criteria:
            query = query.filter(criterion)
        return int(query.scalar() or 0)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "sessions_total": count(AiChatSession.session_id),
            "agents_total": count(AgentConfig.id, AgentConfig.is_deleted == False),
            "agent_teams_total": count(AgentTeam.id, AgentTeam.is_deleted == False),
            "tools_total": count(AiToolDefinition.id, AiToolDefinition.status == "enabled"),
            "skills_total": count(AiSkillPackage.id, AiSkillPackage.enabled == True),
            "users_total": count(SysUser.user_id, SysUser.is_deleted == False),
            # 目前仅 agent_team_run 记录了 token 消耗，作为全局用量的近似值
            "token_total": int(
                db.query(func.coalesce(func.sum(AgentTeamRun.total_tokens), 0)).scalar() or 0
            ),
        }
    }


# ===========================================================
# 用户管理
# ===========================================================

@router.get("/users")
def get_users(
        tenant_id: Optional[int] = None,
        skip: int = 0, limit: int = 20,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    effective = _effective_tenant_id(admin, tenant_id)
    query = db.query(SysUser).filter(SysUser.is_deleted == False)
    if effective is not None:
        query = query.filter(SysUser.tenant_id == effective)
    total = query.count()
    users = query.offset(skip).limit(limit).all()

    tenant_map = _tenant_name_map(db)
    data = []
    for u in users:
        data.append({
            "userId": u.user_id,
            "username": u.username,
            "realName": u.real_name,
            "phone": u.phone,
            "email": u.email,
            "status": u.status,
            "tenantId": u.tenant_id,
            "tenantName": tenant_map.get(u.tenant_id) if u.tenant_id is not None else None,
            "createdAt": u.created_at.isoformat() if u.created_at else None
        })
    return {"code": 0, "message": "success", "data": data, "total": total}


# ===========================================================
# 菜单管理
# ===========================================================

class MenuCreate(BaseModel):
    name: str
    permission: Optional[str] = None  # 权限标识
    path: Optional[str] = None  # 路由地址
    type: int = 2  # 1=目录, 2=菜单, 3=按钮
    sort: int = 0
    parent_id: Optional[int] = 0
    icon: Optional[str] = None
    component: Optional[str] = None
    component_name: Optional[str] = None
    status: int = 0  # 0=开启 1=关闭
    visible: int = 1  # 1=显示 0=隐藏
    keep_alive: int = 0  # 1=缓存 0=不缓存
    always_show: int = 0  # 1=总是 0=不是
    i18n_key: Optional[str] = None  # 多语言翻译 key


class MenuUpdate(BaseModel):
    name: Optional[str] = None
    permission: Optional[str] = None
    path: Optional[str] = None
    type: Optional[int] = None
    sort: Optional[int] = None
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    component: Optional[str] = None
    component_name: Optional[str] = None
    status: Optional[int] = None
    visible: Optional[int] = None
    keep_alive: Optional[int] = None
    always_show: Optional[int] = None
    i18n_key: Optional[str] = None  # 多语言翻译 key


def _menu_to_dict(m) -> dict:
    """将 Menu ORM 对象转为字典"""
    return {
        "id": m.id,
        "name": m.name,
        "permission": m.permission,
        "path": m.path,
        "type": m.type,
        "sort": m.sort,
        "parentId": m.parent_id,
        "icon": m.icon,
        "component": m.component,
        "componentName": m.component_name,
        "status": m.status,
        "visible": m.visible,
        "keepAlive": m.keep_alive,
        "alwaysShow": m.always_show,
        "i18nKey": m.i18n_key,
    }


def _build_menu_tree(menus: List, parent_id=None) -> List:
    """递归构建菜单树"""
    tree = []
    for menu in menus:
        pid = menu.get('parentId')
        # 兼容 parent_id 为 None 或 0 的顶级菜单
        is_match = (pid == parent_id) or (parent_id is None and (pid is None or pid == 0)) or (
                    parent_id == 0 and (pid is None or pid == 0))
        if is_match:
            children = _build_menu_tree(menus, menu['id'])
            item = dict(menu)
            if children:
                item['children'] = children
            tree.append(item)
    return tree


@router.get("/menus")
def get_menus(
        name: Optional[str] = None,
        status: Optional[int] = None,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)
):
    """获取菜单列表（树形结构，支持过滤）"""
    from app.models.sys.sys_user import SysMenu
    query = db.query(SysMenu).filter(SysMenu.is_deleted == False)
    if name:
        query = query.filter(SysMenu.name.ilike(f"%{name}%"))
    if status is not None:
        query = query.filter(SysMenu.status == status)
    menus = query.order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()

    data = [_menu_to_dict(m) for m in menus]
    # 构建树形结构
    tree = _build_menu_tree(data)
    return {"code": 0, "message": "success", "data": tree}


@router.get("/menus/flat")
def get_menus_flat(
        name: Optional[str] = None,
        status: Optional[int] = None,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)
):
    """获取菜单列表（扁平结构，用于下拉选择等）"""
    from app.models.sys.sys_user import SysMenu
    query = db.query(SysMenu).filter(SysMenu.is_deleted == False)
    if name:
        query = query.filter(SysMenu.name.ilike(f"%{name}%"))
    if status is not None:
        query = query.filter(SysMenu.status == status)
    menus = query.order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()

    data = [_menu_to_dict(m) for m in menus]
    return {"code": 0, "message": "success", "data": data}


@router.get("/menus/simple")
def get_menus_simple(db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    """获取简化菜单列表（仅 id/name/parentId，用于上级菜单选择）"""
    from app.models.sys.sys_user import SysMenu
    menus = db.query(SysMenu).filter(
        SysMenu.is_deleted == False,
        SysMenu.status == 0,
        SysMenu.type.in_([1, 2])
    ).order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()

    data = [{"id": m.id, "parentId": m.parent_id, "name": m.name} for m in menus]
    return {"code": 0, "message": "success", "data": data}


@router.get("/menus/{menu_id}")
def get_menu_detail(menu_id: int, db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    """获取单个菜单详情"""
    from app.models.sys.sys_user import SysMenu
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id, SysMenu.is_deleted == False).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")
    return {"code": 0, "message": "success", "data": _menu_to_dict(menu)}


@router.post("/menus")
def create_menu(menu_in: MenuCreate, db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    """创建菜单"""
    from app.models.sys.sys_user import SysMenu
    if menu_in.permission:
        exist = db.query(SysMenu).filter(SysMenu.permission == menu_in.permission, SysMenu.is_deleted == False).first()
        if exist:
            raise HTTPException(status_code=400, detail="权限标识已存在")

    new_menu = SysMenu(
        name=menu_in.name,
        permission=menu_in.permission,
        path=menu_in.path,
        type=menu_in.type,
        sort=menu_in.sort,
        parent_id=menu_in.parent_id if menu_in.parent_id else 0,
        icon=menu_in.icon,
        component=menu_in.component,
        component_name=menu_in.component_name,
        status=menu_in.status,
        visible=menu_in.visible,
        keep_alive=menu_in.keep_alive,
        always_show=menu_in.always_show,
        i18n_key=menu_in.i18n_key,
    )
    db.add(new_menu)
    db.commit()
    db.refresh(new_menu)
    return {"code": 0, "message": "创建成功", "data": {"id": new_menu.id}}


@router.put("/menus/{menu_id}")
def update_menu(
        menu_id: int, menu_in: MenuUpdate,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)
):
    """更新菜单"""
    from app.models.sys.sys_user import SysMenu
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id, SysMenu.is_deleted == False).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")

    if menu_in.name is not None:
        menu.name = menu_in.name
    if menu_in.path is not None:
        menu.path = menu_in.path
    if menu_in.type is not None:
        menu.type = menu_in.type
    if menu_in.sort is not None:
        menu.sort = menu_in.sort
    if menu_in.parent_id is not None:
        menu.parent_id = menu_in.parent_id
    if menu_in.icon is not None:
        menu.icon = menu_in.icon
    if menu_in.component is not None:
        menu.component = menu_in.component
    if menu_in.component_name is not None:
        menu.component_name = menu_in.component_name
    if menu_in.status is not None:
        menu.status = menu_in.status
    if menu_in.visible is not None:
        menu.visible = menu_in.visible
    if menu_in.keep_alive is not None:
        menu.keep_alive = menu_in.keep_alive
    if menu_in.always_show is not None:
        menu.always_show = menu_in.always_show
    if menu_in.i18n_key is not None:
        menu.i18n_key = menu_in.i18n_key

    db.commit()
    return {"code": 0, "message": "更新成功"}


@router.delete("/menus/{menu_id}")
def delete_menu(
        menu_id: int,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)
):
    """删除菜单（软删除，同时删除子菜单）"""
    from app.models.sys.sys_user import SysMenu
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id, SysMenu.is_deleted == False).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")

    # 递归软删除所有子菜单
    def soft_delete_children(pid):
        children = db.query(SysMenu).filter(SysMenu.parent_id == pid, SysMenu.is_deleted == False).all()
        for child in children:
            child.is_deleted = True
            soft_delete_children(child.id)

    soft_delete_children(menu_id)
    menu.is_deleted = True
    db.commit()
    return {"code": 0, "message": "删除成功"}


# ===========================================================
# 角色菜单关联管理
# ===========================================================

class RoleMenuAssign(BaseModel):
    menuIds: List[int]


@router.get("/roles/{role_id}/menus")
def get_role_menus(
        role_id: int,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)
):
    """获取角色的菜单权限"""
    from app.models.sys.sys_user import SysRole, SysRoleMenu
    role = db.query(SysRole).filter(SysRole.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    rms = db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).all()
    menu_ids = [rm.menu_id for rm in rms]
    return {"code": 0, "message": "success", "data": menu_ids}


@router.put("/roles/{role_id}/menus")
def assign_role_menus(
        role_id: int, body: RoleMenuAssign,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)
):
    """分配角色菜单权限"""
    from app.models.sys.sys_user import SysRole, SysRoleMenu
    role = db.query(SysRole).filter(SysRole.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 删除旧关联
    db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).delete()

    # 添加新关联
    for mid in body.menuIds:
        db.add(SysRoleMenu(role_id=role_id, menu_id=mid))
    db.commit()
    return {"code": 0, "message": "菜单分配成功"}


# ===========================================================
# 用户角色关联管理（扩展：获取用户当前角色列表）
# ===========================================================

@router.get("/users/{user_id}/roles")
def get_user_roles(
        user_id: int,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)
):
    from app.models.sys.sys_user import SysUserRole
    urs = db.query(SysUserRole).filter(SysUserRole.user_id == user_id).all()
    role_ids = [ur.role_id for ur in urs]
    return {"code": 0, "message": "success", "data": role_ids}


@router.post("/users")
def create_user(user_in: UserCreate, db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    exist = db.query(SysUser).filter(SysUser.username == user_in.username).first()
    if exist:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 普通租户管理员创建的用户强制归属自身租户；
    # 超级管理员可显式指定租户，缺省归属平台租户 0。
    admin_tenant = admin.tenant_id or 0
    tenant_id = admin_tenant if admin_tenant != 0 else (user_in.tenantId or 0)

    hashed_password = AuthService.get_password_hash(user_in.password)
    new_user = SysUser(
        username=user_in.username,
        password_hash=hashed_password,
        real_name=user_in.realName,
        phone=user_in.phone,
        email=user_in.email,
        tenant_id=tenant_id,
        status="active"
    )
    db.add(new_user)
    db.commit()
    return {"code": 0, "message": "创建成功"}


@router.put("/users/{user_id}")
def update_user(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db),
                admin: SysUser = Depends(require_admin)):
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # allow both realName and real_name input
    real_n = user_in.realName if user_in.realName else user_in.real_name
    if real_n is not None:
        user.real_name = real_n
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.email is not None:
        user.email = user_in.email

    db.commit()
    return {"code": 0, "message": "更新成功"}


@router.put("/users/{user_id}/role")
def assign_role(user_id: int, role_in: RoleAssignReq, db: Session = Depends(get_db),
                admin: SysUser = Depends(require_admin)):
    from app.models.sys.sys_user import SysUserRole
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # delete old roles
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
    db.commit()

    # insert new roles
    for rid in role_in.roleIds:
        ur = SysUserRole(user_id=user_id, role_id=rid)
        db.add(ur)
    db.commit()
    return {"code": 0, "message": "分配成功"}


@router.put("/users/{user_id}/status")
def update_user_status(user_id: int, status_in: StatusUpdate, db: Session = Depends(get_db),
                       admin: SysUser = Depends(require_admin)):
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.status = status_in.status
    db.commit()
    return {"code": 0, "message": "更新成功"}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, pwd_in: PasswordReset, db: Session = Depends(get_db),
                   admin: SysUser = Depends(require_admin)):
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not AuthService.verify_password(pwd_in.oldPassword, user.password_hash):
        return {"code": 400, "message": "原密码不正确"}

    user.password_hash = AuthService.get_password_hash(pwd_in.newPassword)
    db.commit()
    return {"code": 0, "message": "重置成功"}


# ===========================================================
# 角色管理
# ===========================================================

class RoleCreate(BaseModel):
    roleName: str
    roleCode: str
    description: Optional[str] = None
    tenantId: Optional[int] = None


@router.get("/roles")
def get_roles(
        tenant_id: Optional[int] = None,
        db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    from app.models.sys.sys_user import SysRole
    effective = _effective_tenant_id(admin, tenant_id)
    query = db.query(SysRole).filter(SysRole.is_deleted == False)
    if effective is not None:
        query = query.filter(SysRole.tenant_id == effective)
    roles = query.all()
    tenant_map = _tenant_name_map(db)
    data = [{
        "roleId": r.role_id,
        "roleName": r.role_name,
        "roleCode": r.role_code,
        "description": r.description,
        "status": r.status,
        "tenantId": r.tenant_id,
        "tenantName": tenant_map.get(r.tenant_id) if r.tenant_id is not None else None,
    } for r in roles]
    return {"code": 0, "message": "success", "data": data}


@router.post("/roles")
def create_role(role_in: RoleCreate, db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    from app.models.sys.sys_user import SysRole
    admin_tenant = admin.tenant_id or 0
    tenant_id = admin_tenant if admin_tenant != 0 else (role_in.tenantId or 0)
    new_role = SysRole(role_name=role_in.roleName, role_code=role_in.roleCode,
                       description=role_in.description, tenant_id=tenant_id)
    db.add(new_role)
    db.commit()
    return {"code": 0, "message": "创建成功"}


@router.put("/roles/{role_id}")
def update_role(role_id: int, role_in: RoleCreate, db: Session = Depends(get_db),
                admin: SysUser = Depends(require_admin)):
    from app.models.sys.sys_user import SysRole
    role = db.query(SysRole).filter(SysRole.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    role.role_name = role_in.roleName
    role.role_code = role_in.roleCode
    if role_in.description is not None:
        role.description = role_in.description
    db.commit()
    return {"code": 0, "message": "更新成功"}


# ===========================================================
# 审计日志
# ===========================================================

@router.get("/audit-logs")
def get_audit_logs(
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        db: Session = Depends(get_db),
        admin: SysUser = Depends(require_admin)
):
    from app.models.sys.sys_user import SysAuditLog
    effective = _effective_tenant_id(admin, tenant_id)
    query = db.query(SysAuditLog)

    if effective is not None:
        query = query.filter(SysAuditLog.tenant_id == effective)
    if user_id:
        query = query.filter(SysAuditLog.user_id == user_id)
    if operation_type:
        query = query.filter(SysAuditLog.operation_type == operation_type)

    total = query.count()
    logs = query.order_by(SysAuditLog.created_at.desc()).offset(skip).limit(limit).all()
    tenant_map = _tenant_name_map(db)

    data = []
    for log in logs:
        data.append({
            "logId": log.log_id,
            "userId": log.user_id,
            "username": log.username,
            "operationType": log.operation_type,
            "operationModule": log.operation_module,
            "operationDesc": log.operation_desc,
            "requestUrl": log.request_url,
            "requestIp": log.request_ip,
            "requestParams": log.request_params,  # 脱敏后的请求参数
            "newData": log.new_data,  # 附件详情等扩展数据
            "userAgent": log.user_agent,
            "responseTimeMs": log.response_time_ms,
            "tenantId": log.tenant_id,
            "tenantName": tenant_map.get(log.tenant_id) if log.tenant_id is not None else None,
            "createdAt": log.created_at.isoformat() if log.created_at else None,
            "status": log.response_status,
        })

    return {"code": 0, "message": "success", "data": data, "total": total}


# ===========================================================
# 智能报表管理
# ===========================================================

@router.get("/smart-reports")
def get_all_reports(db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    return {"data": [], "total": 0}


@router.put("/smart-reports/{report_id}/scope")
def update_report_scope(report_id: str, db: Session = Depends(get_db), admin: SysUser = Depends(require_admin)):
    return {"message": "更新成功"}
