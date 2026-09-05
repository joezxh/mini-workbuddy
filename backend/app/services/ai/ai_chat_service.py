"""AI助理会话与消息服务层"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.ai.ai_chat import AiChatSession, AiChatMessage


class AiChatService:
    """AI会话与消息增删查改服务"""

    def __init__(self, db: Session):
        self.db = db

    # ── 会话 ────────────────────────────────────────────────────────────────

    def create_session(
        self,
        user_id: int,
        session_title: Optional[str] = None,
        session_type: str = 'general',
    ) -> AiChatSession:
        """创建新会话

        Args:
            user_id: 用户 ID
            session_title: 会话标题
            session_type: 会话类型（general/thinking/deep_research/skill/agent/team）
        """
        session = AiChatSession(
            user_id=user_id,
            session_title=session_title or '新会话',
            session_type=session_type,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: int) -> Optional[AiChatSession]:
        """按ID获取会话"""
        return self.db.query(AiChatSession).filter(
            AiChatSession.session_id == session_id
        ).first()

    def get_user_sessions(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[int, List[AiChatSession]]:
        """获取用户的会话列表（置顶优先，按更新时间倒序）"""
        query = self.db.query(AiChatSession).filter(
            AiChatSession.user_id == user_id
        )
        if status:
            query = query.filter(AiChatSession.status == status)
        total = query.count()
        items = (
            query
            .order_by(
                desc(AiChatSession.is_pinned),
                desc(AiChatSession.updated_at),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return total, items

    def get_all_sessions(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Tuple[int, List[AiChatSession]]:
        """管理端：获取所有会话（支持按用户/状态过滤）"""
        query = self.db.query(AiChatSession)
        if user_id:
            query = query.filter(AiChatSession.user_id == user_id)
        if status:
            query = query.filter(AiChatSession.status == status)
        total = query.count()
        items = (
            query
            .order_by(desc(AiChatSession.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return total, items

    def update_session_title(self, session_id: int, title: str) -> Optional[AiChatSession]:
        """更新会话标题"""
        session = self.get_session(session_id)
        if not session:
            return None
        session.session_title = title
        self.db.commit()
        self.db.refresh(session)
        return session

    def pin_session(self, session_id: int, is_pinned: bool) -> Optional[AiChatSession]:
        """置顶 / 取消置顶会话"""
        session = self.get_session(session_id)
        if not session:
            return None
        session.is_pinned = is_pinned
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: int) -> bool:
        """删除会话（级联删除消息）"""
        session = self.get_session(session_id)
        if not session:
            return False
        # 先删除所有消息
        self.db.query(AiChatMessage).filter(
            AiChatMessage.session_id == session_id
        ).delete(synchronize_session=False)
        self.db.delete(session)
        self.db.commit()
        return True

    def batch_delete_sessions(self, session_ids: List[int]) -> int:
        """批量删除会话，返回实际删除数量"""
        if not session_ids:
            return 0
        # 先删除关联消息
        self.db.query(AiChatMessage).filter(
            AiChatMessage.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        deleted = self.db.query(AiChatSession).filter(
            AiChatSession.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        self.db.commit()
        return deleted

    # ── 消息 ────────────────────────────────────────────────────────────────

    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        message_type: str = 'text',
        extra_data: Optional[dict] = None,
        file_id: Optional[int] = None,
    ) -> AiChatMessage:
        """添加消息并更新会话计数
        file_id: 关联到 infra_file.id（用于消息附件）
        """
        msg = AiChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            extra_data=extra_data,
            file_id=file_id,
        )
        self.db.add(msg)
        # 更新会话消息计数和更新时间
        self.db.query(AiChatSession).filter(
            AiChatSession.session_id == session_id
        ).update(
            {AiChatSession.message_count: AiChatSession.message_count + 1},
            synchronize_session=False,
        )
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_session_messages(
        self,
        session_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[int, List[AiChatMessage]]:
        """获取会话消息列表（按时间升序，附带文件信息）"""
        from sqlalchemy.orm import joinedload
        query = self.db.query(AiChatMessage).options(
            joinedload(AiChatMessage.file)
        ).filter(
            AiChatMessage.session_id == session_id
        )
        total = query.count()
        items = (
            query
            .order_by(AiChatMessage.created_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return total, items

    def batch_delete_messages(self, message_ids: List[int]) -> int:
        """批量删除消息，返回实际删除数量"""
        if not message_ids:
            return 0
        deleted = self.db.query(AiChatMessage).filter(
            AiChatMessage.message_id.in_(message_ids)
        ).delete(synchronize_session=False)
        self.db.commit()
        return deleted

    def delete_session_messages(self, session_id: int) -> int:
        """清空会话的所有消息，返回删除数量"""
        deleted = self.db.query(AiChatMessage).filter(
            AiChatMessage.session_id == session_id
        ).delete(synchronize_session=False)
        # 重置消息计数
        self.db.query(AiChatSession).filter(
            AiChatSession.session_id == session_id
        ).update({AiChatSession.message_count: 0}, synchronize_session=False)
        self.db.commit()
        return deleted

    def auto_title_session(
        self,
        session_id: int,
        first_user_message: str,
        max_length: int = 30,
    ) -> None:
        """根据第一条用户消息自动生成会话标题"""
        session = self.get_session(session_id)
        if not session or session.session_title != '新会话':
            return
        title = first_user_message[:max_length].strip()
        if len(first_user_message) > max_length:
            title += '...'
        session.session_title = title
        self.db.commit()

