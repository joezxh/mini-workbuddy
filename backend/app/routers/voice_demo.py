"""语音能力 Demo 网关 — spec docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.2。

router 不声明 prefix，由 router_registry 叠加 /api/v1/voice-demo。
REST：/health、/asr/transcribe、/tts/synthesize（JWT 头鉴权）；
WS：/ws?token=<JWT>（query 鉴权，对齐 duplex/voice 网关先例，真正校验 JWT）。
Mock 默认开启（VOICE_DEMO_MOCK=true），事件/响应形状与真实 s2s 逐一同构。
"""
import asyncio
import json
import time

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from loguru import logger

from app.config import settings
from app.deps import get_current_user
from app.services.voice_demo import gateway, mock
from app.services.voice_demo import realtime_bridge as bridge

router = APIRouter(tags=["语音演示"])


@router.get("/health")
async def health(_user=Depends(get_current_user)):
    """探测上游服务（GET /v1/pool）+ 返回生效配置摘要；Mock 模式 pool 为 None。"""
    pool = None
    if not settings.VOICE_DEMO_MOCK:
        pool = await gateway.probe_pool()
    return {
        "mock": settings.VOICE_DEMO_MOCK,
        "base_url": settings.VOICE_DEMO_BASE_URL,
        "realtime_ws_url": settings.VOICE_DEMO_REALTIME_WS_URL,
        "pool": pool,
        "ok": True,
    }


@router.post("/asr/transcribe")
async def asr_transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    _user=Depends(get_current_user),
):
    """multipart 转发 ASR（实测形状）→ {text, language, cost_ms}。"""
    data = await file.read()
    if len(data) > settings.VOICE_DEMO_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="音频文件过大（>25MB）")
    t0 = time.perf_counter()
    if settings.VOICE_DEMO_MOCK:
        result = mock.mock_asr_text(language)
    else:
        try:
            result = await gateway.transcribe(data, file.filename or "audio.wav", language)
        except gateway.UpstreamUnavailable as exc:
            raise HTTPException(
                status_code=502, detail={"code": "UPSTREAM_UNAVAILABLE", "message": str(exc)}
            )
        except gateway.UpstreamBadRequest as exc:
            raise HTTPException(
                status_code=400, detail={"code": "UPSTREAM_REJECTED", "message": str(exc)}
            )
    return {**result, "cost_ms": int((time.perf_counter() - t0) * 1000)}


@router.post("/tts/synthesize")
async def tts_synthesize(payload: dict, _user=Depends(get_current_user)):
    """JSON 转发 TTS（input/voice/response_format；实测仅 wav、无 speed）→ WAV。"""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text 不能为空")
    body = {
        "input": text,
        "voice": payload.get("voice") or settings.VOICE_DEMO_TTS_VOICE,
        "response_format": "wav",  # 实测仅支持 wav
    }
    if settings.VOICE_DEMO_MOCK:
        content = mock.mock_tts_wav_bytes()
    else:
        try:
            content = await gateway.synthesize(body)
        except gateway.UpstreamUnavailable as exc:
            raise HTTPException(
                status_code=502, detail={"code": "UPSTREAM_UNAVAILABLE", "message": str(exc)}
            )
        except gateway.UpstreamBadRequest as exc:
            raise HTTPException(
                status_code=400, detail={"code": "UPSTREAM_REJECTED", "message": str(exc)}
            )
    return Response(
        content=content,
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="tts.wav"'},
    )


@router.websocket("/ws")
async def voice_demo_ws(websocket: WebSocket):
    """WS 桥接入口：query JWT 鉴权 → 并发闸 → Mock 会话或真实泵（spec §3.3）。"""
    user_id = bridge._jwt_user_id(websocket.query_params.get("token", ""))
    if user_id is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    if settings.VOICE_DEMO_MOCK:
        await bridge.run_mock_session(websocket)
        return
    # 并发闸：0.1s 内抢不到 → UPSTREAM_BUSY（对齐 s2s pool size 1）
    acquired = False
    try:
        acquired = await asyncio.wait_for(
            bridge.BRIDGE_SEMAPHORE.acquire(), timeout=0.1
        )
    except asyncio.TimeoutError:
        pass
    if not acquired:
        await websocket.send_text(json.dumps({"type": "error", "code": "UPSTREAM_BUSY"}))
        await websocket.close(code=1013)
        return
    try:
        await bridge.run_bridge(websocket)
    except WebSocketDisconnect:
        pass
    finally:
        bridge.BRIDGE_SEMAPHORE.release()


# 总开关守卫（spec §3.5）：VOICE_DEMO_ENABLED=false 时以空 router 替换端点 router，
# registry 挂载后模块对外无路由（等价「路由不注册」，且无需改静态清单）。
if not settings.VOICE_DEMO_ENABLED:
    router = APIRouter(tags=["语音演示"])
    logger.warning("VOICE_DEMO_ENABLED=false，语音能力 Demo 路由未注册（对外 404）")
