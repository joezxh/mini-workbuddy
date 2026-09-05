"""
Skill 规则 Schema
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class AiSkillRuleConditions(BaseModel):
    """规则条件模型"""
    event_types: Optional[List[str]] = Field(None, description="事件类型列表")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    context_match: Optional[Dict[str, Any]] = Field(None, description="上下文匹配条件")
    time_range: Optional[Dict[str, str]] = Field(None, description="时间范围", examples=[{"start": "09:00", "end": "18:00"}])


class AiSkillRuleBase(BaseModel):
    """Skill 规则基础模型"""
    name: str = Field(..., max_length=200, description="规则名称")
    conditions: Optional[Dict[str, Any]] = Field(None, description="触发条件")
    package_id: str = Field(..., max_length=64, description="Skill包ID")
    agent_name: Optional[str] = Field(None, max_length=200, description="关联专家名称（为空表示全局规则）")
    priority: int = Field(100, description="优先级，数字越小越先执行")
    is_active: bool = Field(True, description="是否启用")


class AiSkillRuleCreate(AiSkillRuleBase):
    """创建 Skill 规则"""
    pass


class AiSkillRuleUpdate(BaseModel):
    """更新 Skill 规则"""
    name: Optional[str] = Field(None, max_length=200, description="规则名称")
    conditions: Optional[Dict[str, Any]] = Field(None, description="触发条件")
    package_id: Optional[str] = Field(None, max_length=64, description="Skill包ID")
    agent_name: Optional[str] = Field(None, max_length=200, description="关联专家名称")
    priority: Optional[int] = Field(None, description="优先级")
    is_active: Optional[bool] = Field(None, description="是否启用")


class AiSkillRuleResponse(AiSkillRuleBase):
    """Skill 规则响应"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiSkillRuleListResponse(BaseModel):
    """Skill 规则列表响应"""
    total: int
    items: List[AiSkillRuleResponse]


class AiSkillRuleMatchRequest(BaseModel):
    """规则匹配请求"""
    context: Dict[str, Any] = Field(..., description="上下文数据")
    event_type: Optional[str] = Field(None, description="事件类型")
    content: Optional[str] = Field(None, description="文本内容")


class AiSkillRuleMatchResponse(BaseModel):
    """规则匹配响应"""
    matched: bool
    rules: List[AiSkillRuleResponse] = Field(default_factory=list, description="匹配的规则列表")
