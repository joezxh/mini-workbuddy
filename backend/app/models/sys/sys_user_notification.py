"""站内通知表（轻量级 UserNotification）

支持：未读角标、列表分页、单条/批量标记已读、过期自动清理。
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, SmallInteger, DateTime, Index,
)
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class SysUserNotification(Base, TenantMixin):
    __tablename__ = 'sys_user_notification'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    user_id = Column(Integer, nullable=False, index=True, comment='接收用户ID')
    ntype = Column(String(32), nullable=False, default='system',
                  comment='通知类型: system/async_task/research/scheduled/...')
    title = Column(String(255), nullable=False, comment='通知标题')
    content = Column(Text, nullable=True, comment='通知内容')
    ref_id = Column(Integer, nullable=True, comment='关联业务ID(如任务ID)')
    ref_type = Column(String(32), nullable=True, comment='关联业务类型')
    is_read = Column(Boolean, nullable=False, default=False, comment='已读状态')
    expire_at = Column(DateTime, nullable=True, comment='过期时间(可空=不过期)')
    created_at = Column(DateTime, server_default=func.now(), index=True, comment='创建时间')

    __table_args__ = (
        Index('ix_notif_user_read', 'user_id', 'is_read'),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "userId": self.user_id,
            "type": self.ntype,
            "title": self.title,
            "content": self.content,
            "refId": self.ref_id,
            "refType": self.ref_type,
            "isRead": self.is_read,
            "expireAt": self.expire_at.isoformat() if self.expire_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
