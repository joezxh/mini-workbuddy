"""站内通知服务

- notify_user: 落库 SysUserNotification（可选外发，复用 NotificationSender）
- list_notifications: 分页 + 未读数
- mark_read: 单条/批量/全部
- clean_expired: 过期自动清理（由定时任务或请求时触发）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func
from app.db.database import SessionLocal
from app.models.sys.sys_user_notification import SysUserNotification

logger = logging.getLogger(__name__)


def notify_user(
    user_id: int,
    ntype: str,
    title: str,
    content: Optional[str] = None,
    ref_id: Optional[int] = None,
    ref_type: Optional[str] = None,
    expire_days: Optional[int] = 30,
    external: bool = False,
) -> SysUserNotification:
    """创建一条站内通知（可选外发邮件/钉钉）。"""
    db = SessionLocal()
    try:
        expire_at = None
        if expire_days:
            expire_at = datetime.now() + timedelta(days=expire_days)
        note = SysUserNotification(
            user_id=user_id, ntype=ntype, title=title, content=content,
            ref_id=ref_id, ref_type=ref_type, is_read=False, expire_at=expire_at,
        )
        db.add(note)
        db.commit()
        db.refresh(note)

        if external:
            try:
                from app.ai.tool_manager.notification_tools import NotificationSender
                NotificationSender.send_email(to=user_id, subject=title, body=content or "")
            except Exception as e:
                logger.warning(f"通知外发失败(忽略): {e}")
        return note
    finally:
        db.close()


def list_notifications(
    user_id: int,
    page: int = 1,
    size: int = 20,
    only_unread: bool = False,
) -> tuple[int, int, List[SysUserNotification]]:
    """返回 (total, unread, items)。自动跳过已过期。"""
    db = SessionLocal()
    try:
        _purge_expired_in_session(db)
        base = db.query(SysUserNotification).filter(SysUserNotification.user_id == user_id)
        if only_unread:
            base = base.filter(SysUserNotification.is_read.is_(False))
        total = base.count()
        unread = (
            db.query(func.count(SysUserNotification.id))
            .filter(SysUserNotification.user_id == user_id, SysUserNotification.is_read.is_(False))
            .scalar() or 0
        )
        items = (
            base.order_by(SysUserNotification.id.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return total, unread, items
    finally:
        db.close()


def mark_read(user_id: int, ids: Optional[List[int]] = None) -> int:
    """标记已读。ids 为空则标记该用户全部。返回影响行数。"""
    db = SessionLocal()
    try:
        q = db.query(SysUserNotification).filter(
            SysUserNotification.user_id == user_id, SysUserNotification.is_read.is_(False)
        )
        if ids:
            q = q.filter(SysUserNotification.id.in_(ids))
        cnt = q.update({"is_read": True}, synchronize_session=False)
        db.commit()
        return cnt
    finally:
        db.close()


def unread_count(user_id: int) -> int:
    db = SessionLocal()
    try:
        _purge_expired_in_session(db)
        return (
            db.query(func.count(SysUserNotification.id))
            .filter(SysUserNotification.user_id == user_id, SysUserNotification.is_read.is_(False))
            .scalar() or 0
        )
    finally:
        db.close()


def _purge_expired_in_session(db) -> int:
    """清理已过期的通知。"""
    now = datetime.now()
    cnt = (
        db.query(SysUserNotification)
        .filter(
            SysUserNotification.expire_at.isnot(None),
            SysUserNotification.expire_at < now,
        )
        .delete(synchronize_session=False)
    )
    if cnt:
        db.commit()
    return cnt


def clean_expired() -> int:
    """定时任务入口：清理过期通知。"""
    db = SessionLocal()
    try:
        return _purge_expired_in_session(db)
    finally:
        db.close()
