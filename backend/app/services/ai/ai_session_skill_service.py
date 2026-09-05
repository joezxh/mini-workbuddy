"""会话管理服务 - 用于管理技能执行历史和查看会话记录"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.agent.agent_execution import AgentExecution
from app.models.ai.ai_chat import AiChatSession, AiChatMessage


class AiSessionSkillService:
    """会话管理服务"""

    @staticmethod
    def get_sessions_by_skill(db: Session, skill_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取特定技能的所有会话（分页）
        
        Args:
            db: 数据库会话
            skill_id: 技能 ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            {
                "total": 总条数，
                "page": 当前页码，
                "page_size": 每页数量，
                "sessions": [{session_id, session_title, user_id, created_at, ...}]
            }
        """
        # 通过 AgentExecution 找出绑定到该技能（skill 执行模式）的会话 ID
        sub = (
            db.query(AgentExecution.session_id)
            .filter(
                AgentExecution.execution_mode == "skill",
                AgentExecution.target_id == str(skill_id),
            )
            .distinct()
            .subquery()
        )

        matched = db.query(sub.c.session_id).all()
        session_ids = [row[0] for row in matched]

        if not session_ids:
            return {"total": 0, "page": page, "page_size": page_size, "sessions": []}

        # 查询会话详情
        sessions = db.query(AiChatSession).filter(
            AiChatSession.session_id.in_(session_ids)
        ).order_by(desc(AiChatSession.updated_at)).all()

        # 计算分页
        total = len(sessions)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_sessions = sessions[start_idx:end_idx]

        # 返回结构化数据
        result_sessions = []
        for session in paginated_sessions:
            result_sessions.append({
                "session_id": session.session_id,
                "session_title": session.session_title or f"技能执行 {skill_id}",
                "user_id": session.user_id,
                "session_type": session.session_type,
                "message_count": session.message_count or 0,
                "agent_mode": session.agent_mode,
                "updated_at": session.updated_at.isoformat() if hasattr(session, 'updated_at') else None,
                "created_at": session.created_at.isoformat() if hasattr(session, 'created_at') else None,
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "sessions": result_sessions
        }

    @staticmethod
    def get_messages_by_session(db: Session, session_id: int, limit: int = 50, before_message_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取指定会话的所有消息记录
        
        Args:
            db: 数据库会话
            session_id: 会话 ID
            limit: 每次加载的消息数量
            before_message_id: 分页参数，指定在此消息之前
            
        Returns:
            消息列表，按 message_id 升序 [{message_id, role, content, ...}]
        """
        query = db.query(AiChatMessage).filter(
            AiChatMessage.session_id == session_id
        ).order_by(AiChatMessage.message_id.asc())
        
        if before_message_id:
            query = query.filter(AiChatMessage.message_id > before_message_id)
        
        messages = query.limit(limit).all()
        
        return [{
            "message_id": m.message_id,
            "role": m.role,
            "content": m.content,
            "message_type": m.message_type,
            "tool_calls": m.tool_calls,
            "tool_results": m.tool_results,
            "extra_data": m.extra_data,
            "agent_id": m.agent_id,
            "execution_id": m.execution_id,
            "created_at": m.created_at.isoformat(),
        } for m in messages]

    @staticmethod
    def get_session_detail(db: Session, session_id: int) -> Optional[Dict[str, Any]]:
        """获取会话详细信息
        
        Args:
            db: 数据库会话
            session_id: 会话 ID
            
        Returns:
            会话详情或 None
        """
        session = db.query(AiChatSession).filter(
            AiChatSession.session_id == session_id
        ).first()
        
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "session_title": session.session_title,
            "session_type": session.session_type,
            "message_count": session.message_count or 0,
            "is_pinned": session.is_pinned,
            "status": session.status,
            "agent_mode": session.agent_mode,
            "context_data": session.context_data,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }