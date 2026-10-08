"""后台任务执行器 —— 长耗时 / 可降级任务的统一入口。

用途
----
取代各处直接 `threading.Thread(...).start()` 的裸线程写法：

* 请求链路只负责提交，不等待结果（写接口不被阻塞）；
* 每个任务自带异常兜底与日志，绝不把异常抛回主链路；
* 与 FastAPI `BackgroundTasks` 解耦：任务不绑定请求生命周期，请求返回后仍可继续跑。

约束
----
任务函数**必须自己创建并关闭 Session**（如 `SessionLocal()`），不得复用请求的
Session —— 请求提交后该 Session 即被关闭，复用会产生不可预期的行为。
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# 运行中的后台任务句柄（name → Thread），便于测试与运维观测
_TASKS: Dict[str, threading.Thread] = {}


def run_in_background(
    fn: Callable[..., Any],
    *args: Any,
    name: Optional[str] = None,
    **kwargs: Any,
) -> threading.Thread:
    """在守护线程中执行 fn，失败仅记日志。

    :param fn: 任务函数（需自行管理 Session 生命周期）
    :param name: 任务名，缺省取 fn.__name__
    :return: 已启动的 Thread 句柄（仅用于观测/测试，不要 join 阻塞请求）
    """
    task_name = name or getattr(fn, "__name__", "job")

    def _runner() -> None:
        try:
            fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - 后台任务失败不得影响主链路
            logger.warning(f"[job_runner] 后台任务失败 task={task_name}: {exc}")

    thread = threading.Thread(target=_runner, name=f"job-{task_name}", daemon=True)
    thread.start()
    _TASKS[task_name] = thread
    return thread


def pending_tasks() -> Dict[str, bool]:
    """返回已登记任务的存活状态（测试断言用）。"""
    return {name: t.is_alive() for name, t in _TASKS.items()}
