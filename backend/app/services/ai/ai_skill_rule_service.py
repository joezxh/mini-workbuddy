"""Skill 规则引擎服务"""
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ai.ai_skill_rule import AiSkillRule


class AiSkillRuleService:
    """Skill 规则管理 + 规则引擎"""

    def list_rules(
        self,
        db: Session,
        is_active: Optional[bool] = None,
        package_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> List[AiSkillRule]:
        """获取规则列表"""
        q = select(AiSkillRule)
        if is_active is not None:
            q = q.where(AiSkillRule.is_active == is_active)
        if package_id:
            q = q.where(AiSkillRule.package_id == package_id)
        if agent_name:
            q = q.where(AiSkillRule.agent_name == agent_name)
        return list(db.scalars(q.order_by(AiSkillRule.priority, AiSkillRule.id)).all())

    def get_by_id(self, db: Session, rule_id: int) -> Optional[AiSkillRule]:
        """根据 ID 获取规则"""
        return db.scalars(
            select(AiSkillRule).where(AiSkillRule.id == rule_id)
        ).first()

    def create(
        self,
        db: Session,
        name: str,
        package_id: str,
        conditions: Optional[Dict[str, Any]] = None,
        priority: int = 100,
        is_active: bool = True,
        agent_name: Optional[str] = None,
    ) -> AiSkillRule:
        """创建规则"""
        rule = AiSkillRule(
            name=name,
            package_id=package_id,
            conditions=conditions,
            agent_name=agent_name,
            priority=priority,
            is_active=is_active,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule

    def update(
        self,
        db: Session,
        rule_id: int,
        **fields,
    ) -> Optional[AiSkillRule]:
        """更新规则"""
        rule = self.get_by_id(db, rule_id)
        if not rule:
            return None
        for k, v in fields.items():
            if v is not None and hasattr(rule, k):
                setattr(rule, k, v)
        db.commit()
        db.refresh(rule)
        return rule

    def delete(self, db: Session, rule_id: int) -> bool:
        """删除规则"""
        rule = self.get_by_id(db, rule_id)
        if not rule:
            return False
        db.delete(rule)
        db.commit()
        return True

    def match_rules(
        self,
        db: Session,
        context: Dict[str, Any],
        event_type: Optional[str] = None,
        content: Optional[str] = None,
    ) -> List[AiSkillRule]:
        """规则匹配：根据上下文/事件类型/内容匹配规则"""
        q = select(AiSkillRule).where(AiSkillRule.is_active == True)
        rules = db.scalars(q.order_by(AiSkillRule.priority)).all()

        matched = []
        for rule in rules:
            if self._match_conditions(rule, context, event_type, content):
                matched.append(rule)
        return matched

    def _match_conditions(
        self,
        rule: AiSkillRule,
        context: Dict[str, Any],
        event_type: Optional[str],
        content: Optional[str],
    ) -> bool:
        """判断规则条件是否匹配"""
        if not rule.conditions:
            return True

        conditions = rule.conditions

        if "event_types" in conditions and event_type:
            if event_type not in conditions["event_types"]:
                return False

        if "keywords" in conditions and content:
            keywords = conditions["keywords"]
            if not any(kw in content for kw in keywords):
                return False

        if "context_match" in conditions:
            ctx_match = conditions["context_match"]
            for key, expected in ctx_match.items():
                actual = context.get(key)
                if actual is None:
                    return False
                if isinstance(expected, list):
                    if actual not in expected:
                        return False
                elif actual != expected:
                    return False

        if "time_range" in conditions:
            from datetime import datetime
            now = datetime.now()
            time_range = conditions["time_range"]
            start = time_range.get("start", "00:00")
            end = time_range.get("end", "23:59")
            current_time = now.strftime("%H:%M")
            if not (start <= current_time <= end):
                return False

        return True

    def to_dict(self, rule: AiSkillRule) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": rule.id,
            "name": rule.name,
            "conditions": rule.conditions,
            "package_id": rule.package_id,
            "agent_name": rule.agent_name,
            "priority": rule.priority,
            "is_active": rule.is_active,
            "created_at": str(rule.created_at) if rule.created_at else None,
            "updated_at": str(rule.updated_at) if rule.updated_at else None,
        }
