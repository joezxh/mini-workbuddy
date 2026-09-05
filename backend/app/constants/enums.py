"""跨模块复用的状态枚举。

替代此前散落在 service / router 中的裸字符串。
"""
from enum import Enum


class TaskStatus(str, Enum):
    """调度任务状态。"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStatus(str, Enum):
    """AI 处理 / 工作流执行状态。"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
