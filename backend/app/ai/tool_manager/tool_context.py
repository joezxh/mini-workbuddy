"""Tool 执行期的用户上下文传递。

AgentScope 的 ``ToolBase.call()`` 签名中不包含用户信息，而 SQLBot 业务 Tool
需要依据当前用户的角色 / 辖区做行级数据权限与列级脱敏。本模块用
``contextvars`` 提供一条与 asyncio 任务天然隔离的旁路通道。

使用方式::

    ctx = build_user_context(db, current_user)
    with bind_tool_user(ctx):
        await tool.call(**inputs)

设计约定（安全红线）：
- ``get_tool_user()`` 取不到上下文时返回 ``None``；
- 调用方**不得**将 ``None`` 视为放行，必须按最严格策略处理。
"""
from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "ToolUserContext",
    "bind_tool_user",
    "get_tool_user",
    "set_tool_user",
    "reset_tool_user",
    "build_user_context",
]


@dataclass(frozen=True)
class ToolUserContext:
    """Tool 执行期可见的精简用户上下文（不可变）。"""

    user_id: int
    username: str = ""
    is_admin: bool = False
    role_codes: tuple[str, ...] = ()
    # 已递归展开的辖区集合；为空且非 admin 表示"无任何数据权限"
    region_codes: tuple[str, ...] = ()
    permissions: frozenset[str] = field(default_factory=frozenset)
    # 是否拥有全局（不受区域限制）数据权限
    is_global_scope: bool = False

    def has_permission(self, code: Optional[str]) -> bool:
        """是否拥有指定权限码。空权限码视为不需要校验。"""
        if not code:
            return True
        if self.is_admin:
            return True
        return code in self.permissions

    def has_any_role(self, roles: Optional[Iterable[str]]) -> bool:
        """是否命中给定角色集合中的任意一个。"""
        if not roles:
            return False
        role_set = {r for r in roles if r}
        if not role_set:
            return False
        return bool(role_set & set(self.role_codes))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "is_admin": self.is_admin,
            "role_codes": list(self.role_codes),
            "region_codes": list(self.region_codes),
            "permissions": sorted(self.permissions),
            "is_global_scope": self.is_global_scope,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolUserContext":
        """从普通 dict 还原（供 ToolExecutor 的 context 参数注入使用）。"""
        return cls(
            user_id=int(data.get("user_id") or 0),
            username=str(data.get("username") or ""),
            is_admin=bool(data.get("is_admin")),
            role_codes=tuple(data.get("role_codes") or ()),
            region_codes=tuple(data.get("region_codes") or ()),
            permissions=frozenset(data.get("permissions") or ()),
            is_global_scope=bool(data.get("is_global_scope")),
        )


_current_tool_user: contextvars.ContextVar[Optional[ToolUserContext]] = (
    contextvars.ContextVar("current_tool_user", default=None)
)


def get_tool_user() -> Optional[ToolUserContext]:
    """读取当前 Tool 执行上下文中的用户；无绑定时返回 None。"""
    return _current_tool_user.get()


def set_tool_user(ctx: Optional[ToolUserContext]) -> contextvars.Token:
    """直接设置上下文，返回 token 供 reset。"""
    return _current_tool_user.set(ctx)


def reset_tool_user(token: contextvars.Token) -> None:
    """还原上下文。"""
    _current_tool_user.reset(token)


@contextmanager
def bind_tool_user(ctx: Optional[ToolUserContext]) -> Iterator[Optional[ToolUserContext]]:
    """上下文管理器：在 with 块内绑定用户上下文，退出后自动还原。"""
    token = _current_tool_user.set(ctx)
    try:
        yield ctx
    finally:
        _current_tool_user.reset(token)


# 视为"全局数据权限"的 region_level 取值
_GLOBAL_REGION_LEVELS = {"global", "all", "nation", "country", "province"}


def _expand_regions(db: Any, root_codes: Sequence[str]) -> tuple[str, ...]:
    """依据 sys_region.full_path 递归展开辖区集合（含自身与全部下级）。"""
    codes = [c for c in root_codes if c]
    if not codes:
        return ()

    try:
        from sqlalchemy import or_

        from app.models.sys.sys_user import SysRegion

        result: set[str] = set(codes)
        rows = (
            db.query(SysRegion.region_code, SysRegion.full_path)
            .filter(SysRegion.region_code.in_(codes))
            .all()
        )
        paths = [r[1] for r in rows if r[1]]
        if paths:
            conditions = [SysRegion.full_path.like(f"{p}%") for p in paths]
            children = (
                db.query(SysRegion.region_code)
                .filter(or_(*conditions))
                .all()
            )
            result.update(c[0] for c in children if c[0])
        # 兜底：full_path 缺失时按 parent_code 逐层展开
        if not paths:
            frontier = list(codes)
            seen = set(codes)
            while frontier:
                children = (
                    db.query(SysRegion.region_code)
                    .filter(SysRegion.parent_code.in_(frontier))
                    .all()
                )
                next_frontier = [c[0] for c in children if c[0] and c[0] not in seen]
                seen.update(next_frontier)
                result.update(next_frontier)
                frontier = next_frontier
        return tuple(sorted(result))
    except Exception as exc:  # noqa: BLE001
        logger.warning("expand regions failed, fallback to raw codes: %s", exc)
        return tuple(sorted(set(codes)))


def build_user_context(db: Any, user: Any) -> Optional[ToolUserContext]:
    """由 ORM ``User`` 构造 :class:`ToolUserContext`。

    聚合用户的角色码、权限码（sys_menu.permission）与递归展开的辖区集合。
    任何一步失败均降级为"最小权限"，绝不因异常而放大权限。
    """
    if user is None:
        return None

    user_id = int(getattr(user, "user_id", 0) or 0)
    username = str(getattr(user, "username", "") or "")
    is_admin = bool(getattr(user, "is_admin", False))

    role_codes: tuple[str, ...] = ()
    permissions: frozenset[str] = frozenset()
    region_codes: tuple[str, ...] = ()
    is_global_scope = is_admin

    if db is None or not user_id:
        return ToolUserContext(
            user_id=user_id,
            username=username,
            is_admin=is_admin,
            is_global_scope=is_global_scope,
        )

    try:
        from app.models.sys.sys_user import SysMenu, SysRole, SysRoleMenu, SysUserRole

        roles = (
            db.query(SysRole)
            .join(SysUserRole, SysUserRole.role_id == SysRole.role_id)
            .filter(SysUserRole.user_id == user_id)
            .filter(SysRole.status == "active")
            .filter(SysRole.is_deleted.is_(False))
            .all()
        )
        role_codes = tuple(r.role_code for r in roles if r.role_code)
        role_ids = [r.role_id for r in roles]

        root_regions = [r.region_code for r in roles if r.region_code]
        for r in roles:
            if (r.region_level or "").lower() in _GLOBAL_REGION_LEVELS and not r.region_code:
                is_global_scope = True
        region_codes = _expand_regions(db, root_regions)

        if role_ids:
            perm_rows = (
                db.query(SysMenu.permission)
                .join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id)
                .filter(SysRoleMenu.role_id.in_(role_ids))
                .filter(SysMenu.is_deleted.is_(False))
                .all()
            )
            permissions = frozenset(p[0] for p in perm_rows if p[0])
    except Exception as exc:  # noqa: BLE001
        logger.warning("build_user_context degraded for user_id=%s: %s", user_id, exc)

    return ToolUserContext(
        user_id=user_id,
        username=username,
        is_admin=is_admin,
        role_codes=role_codes,
        region_codes=region_codes,
        permissions=permissions,
        is_global_scope=is_global_scope,
    )
