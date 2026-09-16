"""异步任务调度配置"""
from pydantic import BaseModel


class AsyncTaskSettings(BaseModel):
    """异步任务调度配置字段"""
    ASYNC_TASK_MAX_CONCURRENCY: int = 3
    ASYNC_TASK_BACKOFF_BASE: float = 30.0
    ASYNC_TASK_BACKOFF_CAP: float = 600.0
    ASYNC_TASK_ALERT_FAILURE_RATE: float = 0.3
    ASYNC_TASK_FAILURE_ALERT_ENABLED: bool = False
    ASYNC_TASK_FAILURE_ALERT_WEBHOOK: str = ""
    ASYNC_TASK_SCHEDULER_PRIMARY_ONLY: bool = False
