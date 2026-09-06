"""站内通知接口（UserNotification）

- GET  /notifications            列表（分页 + 未读数）
- POST /notifications/read        标记已读（ids 空=全部）
- POST /notifications/clean       清理过期通知
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.sys.sys_user import SysUser
from app.deps import get_current_user_or_api_key
from app.schemas.sys.sys_user_notification import SysUserNotificationOut, SysUserNotificationListResp, SysUserNotificationMarkReadReq
from app.services.sys.sys_notification_service import (
    list_notifications, mark_read, clean_expired, )

router = APIRouter(prefix="/notifications", tags=["站内通知"])


@router.get("")
def get_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    only_unread: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user_or_api_key),
):
    total, unread, items = list_notifications(
        current_user.user_id, page=page, size=size, only_unread=only_unread
    )
    return SysUserNotificationListResp(
        total=total,
        unread=unread,
        items=[SysUserNotificationOut(**n.to_dict()) for n in items],
    )


@router.post("/read")
def mark_read(
    body: SysUserNotificationMarkReadReq,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user_or_api_key),
):
    # 即便未使用 db，保持依赖一致
    cnt = mark_read(current_user.user_id, body.ids or None)
    return {"marked": cnt}


@router.post("/clean")
def clean(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user_or_api_key),
):
    # 任意登录用户均可触发清理（清理仅影响过期数据）
    removed = clean_expired()
    return {"removed": removed}
