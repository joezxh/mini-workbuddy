"""SimulationTools - 仿真工具集

提供 Agent 可调用的仿真操作工具。
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


class SimulationTools:
    """仿真工具集"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def list_simulations(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """列出仿真会话"""
        from app.models.simulation import SimulationSession
        
        query = self.db.query(SimulationSession)
        
        if user_id:
            query = query.filter(SimulationSession.created_by == user_id)
        if status:
            query = query.filter(SimulationSession.status == status)
        
        sessions = query.order_by(SimulationSession.created_at.desc()).limit(limit).all()
        
        return {
            "simulations": [
                {
                    "sim_id": s.sim_id,
                    "name": s.name,
                    "type": s.sim_type,
                    "status": s.status,
                    "current_step": s.current_step,
                    "total_steps": s.total_steps,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ],
            "count": len(sessions),
        }
    
    async def get_simulation_status(self, sim_id: int) -> Dict[str, Any]:
        """获取仿真状态"""
        from app.models.simulation import SimulationSession
        
        sim = self.db.query(SimulationSession).filter(
            SimulationSession.sim_id == sim_id
        ).first()
        
        if not sim:
            return {"error": "Simulation not found"}
        
        return {
            "sim_id": sim.sim_id,
            "name": sim.name,
            "status": sim.status,
            "current_step": sim.current_step,
            "total_steps": sim.total_steps,
            "event_id": sim.event_id,
            "metrics": {
                "risk_score": sim.metrics.get("risk_score") if sim.metrics else None,
                "tension": sim.metrics.get("tension") if sim.metrics else None,
                "resolution": sim.metrics.get("resolution") if sim.metrics else None,
            },
        }
    
    async def get_simulation_steps(
        self,
        sim_id: int,
        limit: int = 50
    ) -> Dict[str, Any]:
        """获取仿真步骤快照"""
        from app.models.simulation import SimulationStepState
        
        steps = self.db.query(SimulationStepState).filter(
            SimulationStepState.sim_id == sim_id
        ).order_by(SimulationStepState.step_no.desc()).limit(limit).all()
        
        return {
            "steps": [
                {
                    "step_no": s.step_no,
                    "risk_score": float(s.risk_score or 0),
                    "tension": float(s.tension or 0),
                    "escalation_prob": float(s.escalation_prob or 0),
                    "resolution_progress": float(s.resolution_progress or 0),
                    "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                }
                for s in steps
            ],
            "count": len(steps),
        }
