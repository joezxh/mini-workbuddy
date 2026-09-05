"""DatabaseTools - 数据库工具集

提供 Agent 可调用的数据库操作工具。
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text


class DatabaseTools:
    """数据库工具集"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """执行查询"""
        try:
            result = self.db.execute(text(sql), params or {})
            rows = result.fetchmany(limit)
            columns = result.keys()
            
            return {
                "columns": list(columns),
                "rows": [dict(zip(columns, row)) for row in rows],
                "count": len(rows),
            }
        except Exception as e:
            return {"error": str(e), "rows": [], "count": 0}
    
    async def search_events(
        self,
        keywords: Optional[str] = None,
        region: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """搜索风险事件"""
        from app.models.risk_event import RiskEvent
        
        query = self.db.query(RiskEvent).filter(RiskEvent.is_deleted == False)
        
        if keywords:
            query = query.filter(RiskEvent.event_title.like(f"%{keywords}%"))
        if region:
            query = query.filter(RiskEvent.region_code == region)
        if risk_level:
            query = query.filter(RiskEvent.risk_level == risk_level)
        
        events = query.order_by(RiskEvent.created_at.desc()).limit(limit).all()
        
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "title": e.event_title,
                    "type": e.event_type,
                    "risk_level": e.risk_level,
                    "region": e.region_name,
                    "date": e.event_date.isoformat() if e.event_date else None,
                }
                for e in events
            ],
            "count": len(events),
        }
    
    async def get_event_detail(self, event_id: int) -> Dict[str, Any]:
        """获取事件详情"""
        from app.models.risk_event import RiskEvent
        
        event = self.db.query(RiskEvent).filter(
            RiskEvent.event_id == event_id,
            RiskEvent.is_deleted == False
        ).first()
        
        if not event:
            return {"error": "Event not found"}
        
        return {
            "event_id": event.event_id,
            "title": event.event_title,
            "content": event.event_content,
            "type": event.event_type,
            "risk_level": event.risk_level,
            "risk_score": float(event.risk_score or 0),
            "region": event.region_name,
            "date": event.event_date.isoformat() if event.event_date else None,
            "disposal_status": event.disposal_status,
            "ai_summary": event.ai_summary,
            "tags": event.tags,
        }
    
    async def get_persons_by_event(self, event_id: int) -> Dict[str, Any]:
        """获取事件关联人员"""
        from app.models.risk_event import RiskEvent
        from app.models.risk_person import RiskPerson
        from app.models.disposal import DisposalRecord
        
        person_ids = self.db.query(DisposalRecord.person_id).filter(
            DisposalRecord.event_id == event_id
        ).distinct().limit(50).all()
        
        if not person_ids:
            return {"persons": [], "count": 0}
        
        persons = self.db.query(RiskPerson).filter(
            RiskPerson.person_id.in_([p[0] for p in person_ids])
        ).all()
        
        return {
            "persons": [
                {
                    "person_id": p.person_id,
                    "name": p.real_name,
                    "type": p.person_type,
                    "risk_level": p.risk_level,
                    "region": p.current_region_name,
                }
                for p in persons
            ],
            "count": len(persons),
        }
