"""SQLAlchemy do_orm_execute 事件拦截器，自动注入租户过滤条件。

对标 Java 的 TenantDatabaseInterceptor，使用 SQLAlchemy 2.0 的
``with_loader_criteria`` 在查询编译阶段自动追加 WHERE tenant_id = ? 条件。
"""
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

from app.core.tenant_context import get_tenant_id, is_ignore
from app.models.tenant_mixin import TenantMixin

# 不需要租户过滤的表名集合（全局表）
TENANT_IGNORE_TABLES = {
    "sys_tenant", "sys_tenant_package", "sys_menu", "sys_region",
    "sys_role_menu",
}


def setup_tenant_interceptor(session_factory) -> None:
    """在 Session 工厂上注册 do_orm_execute 事件，自动注入租户过滤。

    调用方式::

        from app.db.database import SessionLocal
        setup_tenant_interceptor(SessionLocal)
    """

    @event.listens_for(session_factory, "do_orm_execute")
    def _add_tenant_filter(execute_state):
        # 忽略模式：超管操作、登录接口等跳过租户过滤
        if is_ignore():
            return
        # 未设置租户ID：不注入过滤条件
        tenant_id = get_tenant_id()
        if tenant_id is None:
            return

        # 使用 with_loader_criteria 在编译阶段自动追加 WHERE 条件
        # 以 TenantMixin 为基类，所有继承它的模型都会被过滤
        # 使用 callable 形式，SQLAlchemy 会将具体模型类传入
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.tenant_id == tenant_id,
                include_aliases=True,
            )
        )
