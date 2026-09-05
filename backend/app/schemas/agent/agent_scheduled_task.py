"""定时任务 Schema"""
import json
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta


def _to_cst_str(dt: Optional[datetime]) -> Optional[str]:
    """将 datetime 转换为北京时间字符串（格式: YYYY-MM-DD HH:MM:SS）"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 无时区信息，直接视为北京时间（服务器本地时间）
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    # 有时区，转换为北京时间
    cst_dt = dt.astimezone(timezone(timedelta(hours=8)))
    return cst_dt.strftime('%Y-%m-%d %H:%M:%S')


class AgentScheduledTaskBase(BaseModel):
    """任务基础模型"""
    task_code: str = Field(..., description="任务编码")
    task_name: str = Field(..., description="任务名称")
    task_type: str = Field(..., description="任务类型：report-报表, event-事件处理, cluster-聚合事件")
    flow_code: Optional[str] = Field(None, description="关联的 Dify 流程编码")
    schedule_type: str = Field(..., description="调度类型：cron-定时, interval-间隔, once-单次")
    cron_expression: Optional[str] = Field(None, description="Cron 表达式")
    interval_seconds: Optional[int] = Field(None, description="间隔秒数")
    task_params: Optional[Dict[str, Any]] = Field(None, description="任务参数")
    description: Optional[str] = Field(None, description="任务描述")
    sort_order: int = Field(0, description="排序")


class AgentScheduledTaskCreate(AgentScheduledTaskBase):
    """创建任务"""
    pass


class AgentScheduledTaskUpdate(BaseModel):
    """更新任务"""
    task_name: Optional[str] = None
    task_type: Optional[str] = None
    flow_code: Optional[str] = None
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    task_params: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None

    @field_validator("task_params", mode="before")
    @classmethod
    def _parse_task_params(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            try:
                parsed = json.loads(s)
            except Exception as e:
                raise ValueError(f"task_params 不是合法JSON字符串: {e}")
            if not isinstance(parsed, dict):
                raise ValueError("task_params JSON必须是对象")
            return parsed
        raise ValueError("task_params 必须是对象或JSON字符串")


class AgentScheduledTaskOut(AgentScheduledTaskBase):
    """任务输出"""
    task_id: int
    status: str
    is_active: bool
    total_runs: int
    success_runs: int
    failed_runs: int
    last_run_time: Optional[datetime]
    last_run_status: Optional[str]
    last_run_message: Optional[str]
    next_run_time: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('last_run_time', 'next_run_time', 'created_at', 'updated_at')
    def serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return _to_cst_str(dt)


class AgentScheduledTaskListResp(BaseModel):
    """任务列表响应"""
    data: List[AgentScheduledTaskOut]
    total: int
    page: int
    pageSize: int


class AgentTaskExecutionLogOut(BaseModel):
    """执行日志输出"""
    log_id: int
    task_id: int
    task_code: str
    task_name: str
    execution_status: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    result_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    trigger_type: str
    triggered_by: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('start_time', 'end_time', 'created_at')
    def serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return _to_cst_str(dt)


class AgentTaskExecutionLogListResp(BaseModel):
    """执行日志列表响应"""
    data: List[AgentTaskExecutionLogOut]
    total: int
    page: int
    pageSize: int


class AgentTaskExecuteRequest(BaseModel):
    """手动执行任务请求"""
    task_params: Optional[Dict[str, Any]] = Field(None, description="任务参数（覆盖默认参数）")


class AgentTaskStatistics(BaseModel):
    """任务统计"""
    total_tasks: int = 0
    enabled_tasks: int = 0
    disabled_tasks: int = 0
    running_tasks: int = 0
    total_executions: int = 0
    success_executions: int = 0
    failed_executions: int = 0
    success_rate: float = 0.0
