"""LiveKit 入会 Token 签发服务。

spec: docs/LIVEKIT_SELF_HOSTED_DEPLOYMENT_GUIDE.md §5（后端集成）

密钥对（LIVEKIT_API_KEY / LIVEKIT_API_SECRET）与 docker/livekit/livekit.yaml
的 keys 一致；token 用 HS256 签 JWT，LiveKit server 侧校验后才允许接入 ws_url。
房间无需预先创建：首个参会者连接时 LiveKit 自动建房（见 room.empty_timeout 回收）。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from loguru import logger

from app.config import settings


class LiveKitNotConfigured(RuntimeError):
    """服务端未配置 LiveKit 密钥（.env 缺失或与 server 不一致时由 router 转 503）。"""


def build_room_token(
    room: str,
    identity: str,
    name: str,
    *,
    can_publish: bool = True,
) -> Dict[str, Any]:
    """签发单个房间的入会 token。

    :param room: 房间名（router 层已做字面校验）
    :param identity: 房间内唯一参与者 ID（同一房间重复会导致旧连接被顶替）
    :param name: 房间内展示名
    :param can_publish: False 时仅可订阅（旁听席），不可推音视频
    :return: {token, ws_url, room, identity, name, ttl_seconds}
    """
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise LiveKitNotConfigured("LIVEKIT_API_KEY / LIVEKIT_API_SECRET 未配置")

    # noinspection PyUnresolvedReferences
    from livekit import api  # 延迟导入：未启用会议功能时不引入 SDK 依赖链

    token = (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_ttl(timedelta(seconds=settings.LIVEKIT_TOKEN_TTL_SECONDS))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=can_publish,
                can_subscribe=True,
                # 入会后自行开关麦克风/摄像头，无需服务端逐次签发
                can_publish_data=True,
                can_update_own_metadata=True,
            )
        )
    )
    logger.debug(f"签发 LiveKit 入会 token: room={room} identity={identity}")
    return {
        "token": token.to_jwt(),
        "ws_url": settings.LIVEKIT_WS_URL,
        "room": room,
        "identity": identity,
        "name": name,
        "ttl_seconds": settings.LIVEKIT_TOKEN_TTL_SECONDS,
    }
