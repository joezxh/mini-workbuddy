"""Session 双轨桥接层。

对外接受 AsyncSession，内部垫片支持同步/异步两种调用风格：
- bridge.sync(fn)       在线程池执行同步 fn，返回 awaitable
- await bridge.execute() 直接 await（推荐）
- await bridge.maybe(v) 自动判断是否需 await

用法：
    bridge = AsyncSessionBridge(db)

    # 同步风格（传入完整的同步调用链）
    result = await bridge.sync(lambda: db.query(Model).filter(...).all())

    # 异步风格
    result = await bridge.execute(select(Model))

    # 自动垫片
    await bridge.maybe(db.commit())
"""
import asyncio
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, Coroutine, Optional, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession


_TLS = threading.local()
_executor: Optional[ThreadPoolExecutor] = None

_T = TypeVar("_T")


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="sync_db_")
    return _executor


class AsyncSessionBridge:
    """
    双轨 Session：对外接受 AsyncSession，内部垫片支持同步/异步两种调用风格。

    设计原则：
    - 路由层（EngineOrchestrator / EngineRouter）使用 async 风格：bridge.execute(select(...))
    - 业务层（Engine 子类）可继续用同步风格：await bridge.sync(lambda: db.query(...).all())
    - bridge.maybe(value) 统一兼容：自动判断是否需 await
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @property
    def db(self) -> AsyncSession:
        """暴露原始 AsyncSession（传递 AsyncSession 给内部 service 时使用）"""
        return self._db

    async def sync(self, fn: Callable[[], _T]) -> _T:
        """
        在线程池中执行同步 fn，避免 MissingGreenlet 错误。

        Example:
            result = await bridge.sync(lambda: db.query(SysUser).filter(SysUser.id == 1).first())
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_get_executor(), fn)

    async def execute(self, statement, **kwargs: Any) -> Any:
        """异步风格 ORM 查询。直接 await。"""
        return await self._db.execute(statement, **kwargs)

    async def commit(self) -> None:
        await self._db.commit()

    async def rollback(self) -> None:
        await self._db.rollback()

    async def refresh(self, instance: Any, **kwargs: Any) -> None:
        await self._db.refresh(instance, **kwargs)

    def add(self, instance: Any) -> None:
        self._db.add(instance)

    async def maybe(self, value: Any) -> Any:
        """
        通用垫片：自动判断 value 是否为 awaitable，是则 await，否则返回原值。
        用于 EngineOrchestrator._record_invocation 等需要同时兼容同步/异步调用的场景。
        """
        if inspect.isawaitable(value):
            return await value
        return value

    async def close(self) -> None:
        await self._db.close()
