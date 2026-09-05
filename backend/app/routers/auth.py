from app.middleware.audit_logger import AuditLogRoute
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..schemas.auth import LoginRequest, LoginResponse, UserInfoResponse, UpdateProfileRequest
from ..services.auth_service import AuthService
from app.models.sys.sys_user import SysUser

router = APIRouter(route_class=AuditLogRoute)


def _build_menu_tree(menus: list, parent_id: int = None) -> list:
    """递归构建菜单树"""
    tree = []
    for menu in menus:
        pid = menu.get('parentId')
        # 兼容 parent_id 为 None 或 0 的顶级菜单
        is_match = (pid == parent_id) or (parent_id is None and (pid is None or pid == 0)) or (parent_id == 0 and (pid is None or pid == 0))
        if is_match:
            children = _build_menu_tree(menus, menu['id'])
            item = dict(menu)
            if children:
                item['children'] = children
            tree.append(item)
    return tree


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """用户登录"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.login(
            request.username, request.password, request.tenant_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return result


@router.post("/logout")
def logout(
    current_user: SysUser = Depends(get_current_user)
):
    """用户登出"""
    return {"message": "登出成功"}


@router.get("/tenant-simple-list")
def get_tenant_simple_list(db: Session = Depends(get_db)):
    """登录页租户下拉数据源（公开接口）"""
    from app.models.sys.sys_tenant import SysTenant
    from app.core.tenant_context import set_ignore
    set_ignore(True)
    try:
        tenants = db.query(SysTenant).filter(SysTenant.status == "active").all()
        return {"code": 0, "data": [{"tenantId": t.tenant_id, "name": t.name} for t in tenants]}
    finally:
        set_ignore(False)


@router.get("/me", response_model=UserInfoResponse)
def get_current_user_info(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户信息"""
    # 获取用户角色
    roles = []
    if current_user.user_roles:
        roles = [ur.role.role_code for ur in current_user.user_roles if ur.role]

    # 菜单树与权限集合：与 /me/menus 共用同一份权限过滤逻辑，
    # 不再下发通配符 '*:*'，权限从可访问菜单树中收集得到。
    menu_tree = _get_user_menu_tree(current_user, db)

    def _collect_perms(nodes: list) -> set:
        perms: set = set()
        for n in nodes:
            if n.get('permission'):
                perms.add(n['permission'])
            if n.get('children'):
                perms |= _collect_perms(n['children'])
        return perms

    permissions = sorted(_collect_perms(menu_tree))
    
    return {
        "userId": current_user.user_id,
        "username": current_user.username,
        "realName": current_user.real_name,
        "phone": current_user.phone,
        "email": current_user.email,
        "avatar": current_user.avatar_url,
        "roles": roles,
        "permissions": permissions,
        "menus": menu_tree,
        "regionCode": "",
        "regionName": "",
        "regionLevel": ""
    }


@router.put("/me/profile", response_model=UserInfoResponse)
def update_profile(
    profile_data: UpdateProfileRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新个人信息"""
    # 更新允许修改的字段
    if profile_data.realName is not None:
        current_user.real_name = profile_data.realName
    if profile_data.phone is not None:
        current_user.phone = profile_data.phone
    if profile_data.email is not None:
        current_user.email = profile_data.email
    if profile_data.avatar is not None:
        current_user.avatar_url = profile_data.avatar
    
    # 提交到数据库
    db.commit()
    db.refresh(current_user)
    
    # 获取用户角色
    roles = []
    if current_user.user_roles:
        roles = [ur.role.role_code for ur in current_user.user_roles if ur.role]

    # 菜单树与权限集合：与 /me/menus 共用同一份权限过滤逻辑
    menu_tree = _get_user_menu_tree(current_user, db)

    def _collect_perms(nodes: list) -> set:
        perms: set = set()
        for n in nodes:
            if n.get('permission'):
                perms.add(n['permission'])
            if n.get('children'):
                perms |= _collect_perms(n['children'])
        return perms

    permissions = sorted(_collect_perms(menu_tree))

    return {
        "userId": current_user.user_id,
        "username": current_user.username,
        "realName": current_user.real_name,
        "phone": current_user.phone,
        "email": current_user.email,
        "avatar": current_user.avatar_url,
        "roles": roles,
        "permissions": permissions,
        "menus": menu_tree,
        "regionCode": "",
        "regionName": "",
        "regionLevel": ""
    }


def _get_user_menu_tree(current_user: SysUser, db: Session) -> list:
    """按当前用户（角色）返回可访问的菜单树（已过滤停用/删除，仅目录与菜单类型）。"""
    from app.models.sys.sys_user import SysRoleMenu, SysMenu

    is_super = current_user.is_admin or any(
        ur.role and ur.role.role_code == 'super_admin' for ur in current_user.user_roles
    )

    if is_super:
        menus = db.query(SysMenu).filter(
            SysMenu.is_deleted == False,
            SysMenu.status == 0,
            SysMenu.type.in_([1, 2]),  # 只返回目录和菜单，不返回按钮
        ).order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()
    else:
        role_ids = [ur.role_id for ur in current_user.user_roles]
        if not role_ids:
            return []
        menu_ids = [rm.menu_id for rm in db.query(SysRoleMenu.menu_id).filter(SysRoleMenu.role_id.in_(role_ids)).all()]
        if not menu_ids:
            return []
        menus = db.query(SysMenu).filter(
            SysMenu.id.in_(menu_ids),
            SysMenu.is_deleted == False,
            SysMenu.status == 0,
            SysMenu.type.in_([1, 2]),  # 只返回目录和菜单，不返回按钮
        ).order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()

    menu_list = [{
        "id": m.id,
        "name": m.name,
        "permission": m.permission,
        "permissionCode": m.path,
        "menuKey": m.path.rstrip('/').split('/')[-1] if m.path else None,
        "type": m.type,
        "parentId": m.parent_id,
        "icon": m.icon,
        "component": m.component,
        "sortOrder": m.sort,
        # 国际化翻译 key：前端据此通过 vue-i18n 渲染多语言菜单标题，缺失时回退到 name
        "i18nKey": m.i18n_key,
        "visible": m.visible,
        "keepAlive": m.keep_alive,
        "alwaysShow": m.always_show,
    } for m in menus]

    return _build_menu_tree(menu_list)


@router.get("/me/menus")
def get_user_menus(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的菜单树"""
    return {"code": 0, "data": _get_user_menu_tree(current_user, db)}


@router.get("/regions")
def get_regions(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户可访问的地区树"""
    from ..services.region_service import RegionService
    
    region_service = RegionService(db)
    
    # 如果是超级管理员，返回完整地区树
    if current_user.is_admin:
        tree = region_service.get_region_tree()
        return {"data": tree}
    
    # 目前先返回完整地区树，后续可根据用户角色过滤
    tree = region_service.get_region_tree()
    return {"data": tree}

