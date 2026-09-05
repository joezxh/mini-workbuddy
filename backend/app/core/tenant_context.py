"""租户上下文管理 — 基于 contextvars，天然支持 asyncio。

对标 Java 项目的 TenantContextHolder，管理请求级别的租户 ID 和忽略标记。
"""
from contextvars import ContextVar

_current_tenant_id: ContextVar[int | None] = ContextVar("tenant_id", default=None)
_ignore_tenant: ContextVar[bool] = ContextVar("ignore_tenant", default=False)


def set_tenant_id(tenant_id: int | None) -> None:
    """设置当前请求的租户 ID。"""
    _current_tenant_id.set(tenant_id)


def get_tenant_id() -> int | None:
    """获取当前租户 ID，未设置时返回 None。"""
    return _current_tenant_id.get()


def get_required_tenant_id() -> int:
    """获取当前租户 ID，未设置时抛出 ValueError。"""
    tid = get_tenant_id()
    if tid is None:
        raise ValueError("TenantContext 中不存在租户ID，请检查认证流程")
    return tid


def set_ignore(ignore: bool) -> None:
    """设置是否忽略租户过滤。"""
    _ignore_tenant.set(ignore)


def is_ignore() -> bool:
    """当前是否忽略租户过滤。"""
    return _ignore_tenant.get()


def clear() -> None:
    """清理所有租户上下文（请求结束时调用）。"""
    _current_tenant_id.set(None)
    _ignore_tenant.set(False)
