"""SuperAgent Executor 包 — WorkerSession + LocalWorkspace + Transient Retry + WorkerReport + BackgroundJobs。"""
from .report import (
    WorkerReport, ReportKind,
    ASSIGNMENT_TRANSITIONS, TICKET_TRANSITIONS,
    next_assignment_status, can_transition,
)
from .transient import (
    TransientRetryPolicy, is_transient_error, retry_with_backoff,
    TRANSIENT_ERRNOS, TRANSIENT_HTTP, RetryConfig,
)
from .session import WorkerSession, LocalWorkspace
from .background import (
    JobRegistry, BackgroundJob, COLLECT_WAIT_S, collect_children,
)

__all__ = [
    "WorkerReport", "ReportKind",
    "ASSIGNMENT_TRANSITIONS", "TICKET_TRANSITIONS",
    "next_assignment_status", "can_transition",
    "TransientRetryPolicy", "is_transient_error", "retry_with_backoff",
    "TRANSIENT_ERRNOS", "TRANSIENT_HTTP", "RetryConfig",
    "WorkerSession", "LocalWorkspace",
    "JobRegistry", "BackgroundJob", "COLLECT_WAIT_S", "collect_children",
]
