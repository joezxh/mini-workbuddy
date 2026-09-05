"""Skill 规则管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.schemas.ai.ai_skill_rule import (
    AiSkillRuleCreate,
    AiSkillRuleUpdate,
    AiSkillRuleResponse,
    AiSkillRuleListResponse,
    AiSkillRuleMatchRequest,
    AiSkillRuleMatchResponse as MatchRuleResponseSchema,
)
from app.services.ai.ai_skill_rule_service import AiSkillRuleService


router = APIRouter(prefix="/api/v1/skill-rules", tags=["SkillRule"])


@router.get("", response_model=AiSkillRuleListResponse)
def list_rules(
    is_active: Optional[bool] = Query(None, description="是否启用"),
    package_id: Optional[str] = Query(None, description="技能包ID"),
    agent_name: Optional[str] = Query(None, description="关联专家名称"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取规则列表"""
    svc = AiSkillRuleService()
    rules = svc.list_rules(db, is_active, package_id, agent_name)
    return {"total": len(rules), "items": [AiSkillRuleResponse.model_validate(r) for r in rules]}


@router.get("/{rule_id}", response_model=AiSkillRuleResponse)
def get_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取单个规则"""
    svc = AiSkillRuleService()
    rule = svc.get_by_id(db, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.post("", response_model=AiSkillRuleResponse, status_code=201)
def create_rule(
    req: AiSkillRuleCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建规则"""
    svc = AiSkillRuleService()
    rule = svc.create(
        db,
        name=req.name,
        package_id=req.package_id,
        conditions=req.conditions,
        priority=req.priority,
        is_active=req.is_active,
        agent_name=req.agent_name,
    )
    return rule


@router.put("/{rule_id}", response_model=AiSkillRuleResponse)
def update_rule(
    rule_id: int,
    req: AiSkillRuleUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新规则"""
    svc = AiSkillRuleService()
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    rule = svc.update(db, rule_id, **fields)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除规则"""
    svc = AiSkillRuleService()
    ok = svc.delete(db, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"deleted": True}


@router.post("/match", response_model=MatchRuleResponseSchema)
def match_rules(
    req: AiSkillRuleMatchRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """规则匹配：返回匹配的所有规则（按优先级排序）"""
    svc = AiSkillRuleService()
    rules = svc.match_rules(
        db,
        context=req.context,
        event_type=req.event_type,
        content=req.content,
    )
    return {
        "matched": len(rules) > 0,
        "rules": [AiSkillRuleResponse.model_validate(r) for r in rules],
    }
