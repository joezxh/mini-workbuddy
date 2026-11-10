"""语音能力 Demo 网关 — spec docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.2。

router 不声明 prefix，由 router_registry 叠加 /api/v1/voice-demo。
REST：/health、/asr/transcribe、/tts/synthesize（JWT 头鉴权）；
WS：/ws?token=<JWT>（query 鉴权，对齐 duplex/voice 网关先例，真正校验 JWT）。
Mock 默认开启（VOICE_DEMO_MOCK=true），事件/响应形状与真实 s2s 逐一同构。
"""
from fastapi import APIRouter, Depends
from loguru import logger

from app.config import settings
from app.deps import get_current_user

router = APIRouter(tags=["语音演示"])


@router.get("/health")
async def health(_user=Depends(get_current_user)):
    """探测上游服务（GET /v1/pool）+ 返回生效配置摘要；Mock 模式 pool 为 None。"""
    pool = None
    if not settings.VOICE_DEMO_MOCK:
        # 延迟导入：gateway 在 Task 3 落地完整转发；Mock 模式无需加载
        from app.services.voice_demo import gateway

        pool = await gateway.probe_pool()
    return {
        "mock": settings.VOICE_DEMO_MOCK,
        "base_url": settings.VOICE_DEMO_BASE_URL,
        "realtime_ws_url": settings.VOICE_DEMO_REALTIME_WS_URL,
        "pool": pool,
        "ok": True,
    }


# 总开关守卫（spec §3.5）：VOICE_DEMO_ENABLED=false 时以空 router 替换端点 router，
# registry 挂载后模块对外无路由（等价「路由不注册」，且无需改静态清单）。
if not settings.VOICE_DEMO_ENABLED:
    router = APIRouter(tags=["语音演示"])
    logger.warning("VOICE_DEMO_ENABLED=false，语音能力 Demo 路由未注册（对外 404）")
