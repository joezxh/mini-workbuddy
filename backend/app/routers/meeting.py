"""视频会议 API —— LiveKit 入会 Token 签发。

spec: docs/LIVEKIT_SELF_HOSTED_DEPLOYMENT_GUIDE.md §5

router 自带完整 prefix ``/api/v1/meeting``，路由注册表不再叠加前缀。

- ``POST /api/v1/meeting/tokens``  为当前用户签发指定房间的入会 token

鉴权复用 ``deps.get_current_user``（JWT Bearer）；房间名与参与者身份
来自请求参数，identity 缺省为当前 user_id。非管理员不得代签他人身份，
防止冒名入会。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.services.livekit_service import LiveKitNotConfigured, build_room_token

router = APIRouter(prefix="/api/v1/meeting", tags=["视频会议"])

# 房间名：首尾为字母/数字，中间可含 - 与 _，总长 3-64（业务层收口，挡控制字符与路径式输入）
_ROOM_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{1,62}[A-Za-z0-9]$"
# identity：LiveKit 允许较宽字符集，业务层收紧为可安全入库/落日志的字面
_IDENTITY_PATTERN = r"^[A-Za-z0-9_.:@-]{1,64}$"


class MeetingTokenIn(BaseModel):
    """入会 token 签发入参。"""

    room: str = Field(..., min_length=3, max_length=64, pattern=_ROOM_PATTERN,
                      description="房间名，如 project-review-01")
    identity: Optional[str] = Field(None, max_length=64, pattern=_IDENTITY_PATTERN,
                                    description="房间内参与者唯一 ID；缺省为当前用户 user_id")
    name: Optional[str] = Field(None, min_length=1, max_length=64,
                                description="房间内展示名；缺省为当前用户 real_name")
    can_publish: bool = Field(True, description="False 时为旁听席：只可订阅，不可推音视频")


class MeetingTokenOut(BaseModel):
    """签发结果：前端 livekit-client 以 ws_url + token 直连自建 SFU。"""

    token: str
    ws_url: str
    room: str
    identity: str
    name: str
    ttl_seconds: int


@router.post("/tokens", response_model=MeetingTokenOut)
def create_meeting_token(
    payload: MeetingTokenIn,
    current_user: SysUser = Depends(get_current_user),
):
    """签发入会 token（房间不存在时由 LiveKit 在首个参与者接入时自动创建）。"""
    identity = payload.identity or str(current_user.user_id)
    # 代签他人身份仅限管理员（会议邀请外链等场景）；普通用户只能签自己
    if identity != str(current_user.user_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可代签他人入会身份")

    name = payload.name or current_user.real_name or current_user.username
    try:
        return build_room_token(
            room=payload.room,
            identity=identity,
            name=name,
            can_publish=payload.can_publish,
        )
    except LiveKitNotConfigured as exc:
        # 配置缺失属于服务端问题，与调用方无关
        raise HTTPException(status_code=503, detail=f"视频会议服务未就绪：{exc}")
