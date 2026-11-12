"""BackgroundJobs —— 子进程 / 子任务注册与统一回收（Task 8.2）。

对齐 dsh-superagent backgroundJobs.ts —— waitForChildren / drainChildren 语义：
Executor 停止或回合结束时，统一收集 / 终止所有注册的后台子任务。
COLLECT_WAIT_S = 1800s 为硬性等待上限，超时返回 False 并强制 kill_all。
"""
from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# 子任务回收硬性上限（30 分钟）
COLLECT_WAIT_S = 1800

# terminate → kill 的默认宽限期（秒）
KILL_WAIT_S = 10


@dataclass
class BackgroundJob:
    """注册表条目 —— asyncio subprocess / asyncio Task / 鸭子类型兼容对象。"""
    name: str
    proc: Any
    started_at: float = field(default_factory=time.monotonic)

    @property
    def done(self) -> bool:
        p = self.proc
        if isinstance(p, asyncio.Task):
            return p.done()
        return getattr(p, "returncode", None) is not None


class JobRegistry:
    """后台子任务注册表 —— register / list / kill_all。"""

    def __init__(self) -> None:
        self._jobs: dict[int, BackgroundJob] = {}
        self._seq = 0

    def register(self, proc: Any, name: str = "job") -> BackgroundJob:
        """记录一个 asyncio subprocess / task。"""
        self._seq += 1
        job = BackgroundJob(name=name, proc=proc)
        self._jobs[self._seq] = job
        logger.debug(f"[JobRegistry] register #{self._seq} {name} · done={job.done}")
        return job

    def list(self) -> list[BackgroundJob]:
        """当前 job 快照。"""
        return list(self._jobs.values())

    def __len__(self) -> int:
        return len(self._jobs)

    async def kill_all(self, wait_s: float = KILL_WAIT_S) -> None:
        """统一终止所有子任务 —— terminate → wait(wait_s) → kill。"""
        for job in self.list():
            await self._kill_one(job, wait_s)
        self._jobs.clear()
        logger.info("[JobRegistry] kill_all 完成")

    @staticmethod
    async def _kill_one(job: BackgroundJob, wait_s: float) -> None:
        p = job.proc
        try:
            if isinstance(p, asyncio.Task):
                if not p.done():
                    p.cancel()
                    done, _ = await asyncio.wait({p}, timeout=wait_s)
                    if not done:
                        logger.warning(f"[JobRegistry] {job.name} cancel 未及时完成")
                return
            # asyncio.subprocess.Process（或鸭子类型兼容对象）
            if getattr(p, "returncode", None) is not None:
                return  # 已退出
            if hasattr(p, "terminate"):
                p.terminate()
            try:
                await asyncio.wait_for(p.wait(), timeout=wait_s)
            except asyncio.TimeoutError:
                if hasattr(p, "kill"):
                    logger.warning(f"[JobRegistry] {job.name} terminate 超时 → kill")
                    p.kill()
                await p.wait()
        except ProcessLookupError:
            pass  # 进程已不存在
        except Exception as exc:
            logger.warning(f"[JobRegistry] kill {job.name} 失败: {type(exc).__name__}: {exc}")


async def collect_children(registry: JobRegistry,
                           timeout_s: float = COLLECT_WAIT_S,
                           kill_wait_s: float = KILL_WAIT_S) -> bool:
    """等待所有注册子任务完成 —— 超时返回 False 并 kill_all（drainChildren 语义）。"""
    waiters: list[asyncio.Future] = []
    for job in registry.list():
        p = job.proc
        if isinstance(p, asyncio.Task):
            if not p.done():
                waiters.append(p)
        elif getattr(p, "returncode", None) is None and hasattr(p, "wait"):
            waiters.append(asyncio.ensure_future(p.wait()))

    if not waiters:
        return True

    done, pending = await asyncio.wait(waiters, timeout=timeout_s)
    for f in done:
        if f.done() and not f.cancelled():
            f.exception()  # 标记异常已消费，避免 "never retrieved" 警告

    if pending:
        names = [job.name for job in registry.list()]
        logger.warning(
            f"[JobRegistry] collect_children 超时（{timeout_s}s）→ kill_all · jobs={names}"
        )
        await registry.kill_all(wait_s=kill_wait_s)
        return False
    return True
