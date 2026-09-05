"""租户相关装饰器。"""
import asyncio
from functools import wraps

from app.core.tenant_context import set_ignore


def tenant_ignore(func):
    """标记不需要租户过滤的接口。

    用于登录、注册、公开 API 等不需要租户过滤的场景。
    被装饰的函数执行期间，租户拦截器会跳过过滤条件注入。

    同时支持同步和异步函数::

        @tenant_ignore
        def login_sync(...):
            ...

        @tenant_ignore
        async def login_async(...):
            ...
    """
    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            set_ignore(True)
            try:
                return await func(*args, **kwargs)
            finally:
                set_ignore(False)
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            set_ignore(True)
            try:
                return func(*args, **kwargs)
            finally:
                set_ignore(False)
        return sync_wrapper
