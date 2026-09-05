"""云端调度异步任务表（用户提交的 Agent/Team/Skill 后台任务）

与运维定时任务 ScheduledTask 语义隔离：本表为「用户提交即异步执行、一次性、归属会话」。
状态机：queued → running → completed / failed / cancelled
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, SmallInteger, Float,
    DateTime, ForeignKey, Index,
)
from sqlalchemy.sql import func, text
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AgentAsyncTask(Base, TenantMixin):
    __tablename__ = 'agent_async_task'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='任务ID')
    task_no = Column(String(64), unique=True, index=True, comment='任务编号(可读)')
    session_id = Column(String(64), nullable=True, index=True, comment='归属会话ID')
    user_id = Column(Integer, nullable=False, index=True, comment='提交用户ID')

    task_name = Column(String(255), nullable=False, comment='任务名称')
    target_mode = Column(String(32), nullable=False, comment='执行模式: agent/team/skill')
    payload = Column(Text, nullable=True, comment='执行参数(JSON: message/agent_id/team_id/skill 等)')

    status = Column(String(16), nullable=False, default='queued',
                    comment='queued/running/completed/failed/cancelled')
    priority = Column(SmallInteger, nullable=False, default=5, comment='优先级0-9(越大越优先)')
    progress = Column(Float, nullable=False, default=0.0, comment='进度百分比0-100')

    timeout_seconds = Column(Integer, nullable=False, default=1800, comment='超时秒数')
    max_retries = Column(SmallInteger, nullable=False, default=2, comment='最大重试次数')
    retry_count = Column(SmallInteger, nullable=False, default=0, comment='已重试次数')

    execution_id = Column(String(100), nullable=True, index=True,
                          comment='网关执行ID(启动即写入, 支持运行中实时回放执行事件)')
    result_data = Column(Text, nullable=True, comment='执行结果(JSON)')
    error_message = Column(Text, nullable=True, comment='错误信息')
    log_ref = Column(String(128), nullable=True, comment='执行日志引用(TaskExecutionLog id等)')
    cancel_requested = Column(Boolean, nullable=False, server_default=text("false"), comment='用户请求取消标记，执行中任务轮询该标记主动中断')

    submitted_at = Column(DateTime, server_default=func.now(), comment='提交时间')
    started_at = Column(DateTime, nullable=True, comment='开始执行时间')
    finished_at = Column(DateTime, nullable=True, comment='结束时间')

    created_at = Column(DateTime, server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment='更新时间')

    __table_args__ = (
        Index('ix_async_task_status_user', 'status', 'user_id'),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "taskNo": self.task_no,
            "sessionId": self.session_id,
            "userId": self.user_id,
            "taskName": self.task_name,
            "targetMode": self.target_mode,
            "payload": self.payload,
            "status": self.status,
            "priority": self.priority,
            "progress": self.progress,
            "timeoutSeconds": self.timeout_seconds,
            "maxRetries": self.max_retries,
            "retryCount": self.retry_count,
            "executionId": self.execution_id,
            "resultData": self.result_data,
            "errorMessage": self.error_message,
            "cancelRequested": self.cancel_requested,
            "submittedAt": self.submitted_at.isoformat() if self.submitted_at else None,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
        }
