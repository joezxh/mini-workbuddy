"""知识库权限点（Phase 3 T3）：RBAC 权限标识与鉴权依赖。

权限模型沿用系统既有链路：
    sys_user_role(user_id → role_id) → sys_role_menu(role_id → menu_id)
    → sys_menu.permission（权限标识）

设计约定：
* **管理员直通**（``is_admin``）——与 ``app.deps.require_admin`` 一致的既有语义；
* 非管理员按角色菜单权限校验，**查不到权限即拒绝**（fail-closed）；
* 权限只在**后端依赖**处闭合；前端隐藏/禁用、prompt、schema 省略都不是授权边界。
"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysMenu, SysRoleMenu, SysUserRole

# ── 权限标识（与 sys_menu.permission 对齐，需在菜单初始化 SQL 中登记）──────
KB_VIEW = "kb:view"          # 读取知识库/文档/检索
KB_UPLOAD = "kb:upload"      # 上传文档、触发摄取
KB_DELETE = "kb:delete"      # 删除文档/知识库
KB_ADMIN = "kb:admin"        # 知识库管理（创建/配置/外部集成）
WIKI_WRITE = "wiki:write"    # llm-wiki 文章写

ALL_PERMISSIONS = (KB_VIEW, KB_UPLOAD, KB_DELETE, KB_ADMIN, WIKI_WRITE)


def user_permissions(db: Session, user_id: int) -> set[str]:
    """按用户角色 → 菜单，收集其全部权限标识。"""
    rows = db.execute(
        select(SysMenu.permission)
        .join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id)
        .join(SysUserRole, SysUserRole.role_id == SysRoleMenu.role_id)
        .where(SysUserRole.user_id == user_id)
    ).scalars().all()
    return {p for p in rows if p}


def require_kb_permission(code: str):
    """生成鉴权依赖：管理员直通，否则需具备指定权限点。"""

    def _dependency(
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user),
    ):
        if getattr(current_user, "is_admin", False):
            return current_user
        perms = user_permissions(db, getattr(current_user, "user_id", None))
        if code not in perms and KB_ADMIN not in perms:
            raise HTTPException(status_code=403, detail=f"缺少权限: {code}")
        return current_user

    return _dependency
