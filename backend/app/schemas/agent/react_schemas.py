"""ReAct HITL 请求/响应模型。"""
from pydantic import BaseModel
from typing import Optional


class ReactRespondRequest(BaseModel):
    """响应 HITL 确认请求。"""
    step_id: Optional[str] = None
    answer: str = ""
    action: str = "confirm"  # confirm / skip / cancel


class ReactStatusResponse(BaseModel):
    """ReAct 运行状态响应。"""
    run_id: str
    plan: Optional[dict] = None
    cancelled: bool = False
    interaction_mode: str = "auto"
