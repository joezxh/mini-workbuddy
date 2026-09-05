"""UserNotification schema（Pydantic v2）"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class SysUserNotificationOut(BaseModel):
    id: int
    userId: int
    type: str
    title: str
    content: Optional[str] = None
    refId: Optional[int] = None
    refType: Optional[str] = None
    isRead: bool
    expireAt: Optional[str] = None
    createdAt: Optional[str] = None


class SysUserNotificationListResp(BaseModel):
    total: int
    unread: int
    items: list[SysUserNotificationOut]


class SysUserNotificationMarkReadReq(BaseModel):
    ids: list[int] = Field(default_factory=list, description="空列表=标记全部已读")
