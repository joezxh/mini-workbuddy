"""AI 任务定时调度表（深度研究 / Agent / AgentTeam 周期性自动执行）

与运维定时任务 ScheduledTask 语义隔离：本表为「用户配置的 AI 任务调度」。
APScheduler 触发时调用 async_task_service.submit_task 生成一次性
agent_async_task 异步任务，执行结果回到「我的异步任务」列表。
状态机：enabled → paused / deleted（软删）
"""
import json

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Index,
)
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AgentScheduledTask(Base, TenantMixin):
    __tablename__ = 'agent_scheduled_task'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='调度ID')
    task_name = Column(String(200), nullable=False, comment='调度任务名称')
    user_id = Column(Integer, nullable=False, index=True, comment='归属用户ID')
    description = Column(Text, nullable=True, comment='任务描述')

    # ── 执行目标 ──
    target_mode = Column(String(20), nullable=False, comment='执行模式: deep_research/agent/team')
    agent_id = Column(Integer, nullable=True, comment='agent 模式：目标智能体ID')
    team_id = Column(Integer, nullable=True, comment='team 模式：目标专家团ID(空=默认团队)')
    skill_info = Column(Text, nullable=True,
                        comment='skill 模式：技能信息(JSON: package_id/package_name/script_id/script_name/params)')
    prompt = Column(Text, nullable=False, comment='执行输入(深度研究=研究主题, agent/team=指令)')
    session_id = Column(String(64), nullable=True, comment='关联会话ID')
    model_id = Column(Integer, nullable=True, comment='指定模型ID(空=默认文本模型)')

    # ── 调度配置 ──
    schedule_type = Column(String(20), nullable=False, comment='调度类型: cron/interval/once')
    cron_expression = Column(String(100), nullable=True, comment='Cron 表达式(5段: 分 时 日 月 周)')
    interval_seconds = Column(Integer, nullable=True, comment='间隔秒数(interval 类型, 最小60)')
    run_at = Column(DateTime, nullable=True, comment='单次执行时间(once 类型)')
    timezone = Column(String(50), nullable=False, server_default='Asia/Shanghai', comment='时区')

    # ── 状态与统计 ──
    status = Column(String(20), nullable=False, server_default='enabled',
                    comment='enabled/paused/deleted')
    last_run_at = Column(DateTime, nullable=True, comment='最近触发时间')
    next_run_at = Column(DateTime, nullable=True, comment='下次触发时间(调度器回填)')
    last_task_id = Column(Integer, nullable=True, comment='最近生成的异步任务ID')
    run_count = Column(Integer, nullable=False, server_default='0', comment='累计触发次数')
    fail_count = Column(Integer, nullable=False, server_default='0', comment='触发失败次数')

    created_at = Column(DateTime, server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment='更新时间')

    __table_args__ = (
        Index('ix_agent_sched_user_status', 'user_id', 'status'),
    )

    def _parse_skill_info(self) -> dict | None:
        """skill_info JSON 字符串 → dict（非法内容返回 None）。"""
        if not self.skill_info:
            return None
        try:
            v = json.loads(self.skill_info)
            return v if isinstance(v, dict) else None
        except (ValueError, TypeError):
            return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "taskName": self.task_name,
            "userId": self.user_id,
            "description": self.description,
            "targetMode": self.target_mode,
            "agentId": self.agent_id,
            "teamId": self.team_id,
            "skillInfo": self._parse_skill_info(),
            "prompt": self.prompt,
            "sessionId": self.session_id,
            "modelId": self.model_id,
            "scheduleType": self.schedule_type,
            "cronExpression": self.cron_expression,
            "intervalSeconds": self.interval_seconds,
            "runAt": self.run_at.isoformat() if self.run_at else None,
            "timezone": self.timezone,
            "status": self.status,
            "lastRunAt": self.last_run_at.isoformat() if self.last_run_at else None,
            "nextRunAt": self.next_run_at.isoformat() if self.next_run_at else None,
            "lastTaskId": self.last_task_id,
            "runCount": self.run_count,
            "failCount": self.fail_count,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
