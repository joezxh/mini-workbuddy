"""REST 上游客户端 — httpx 转发（spec docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.2/§3.6）。

转发形状为 2026-11-10 实测约定：ASR multipart(file+language, 无 model)、
TTS JSON(input/voice/response_format:"wav")；5xx/不可达 → UPSTREAM_UNAVAILABLE，
4xx → UPSTREAM_REJECTED。
"""
from typing import Optional

import httpx
from loguru import logger

from app.config import settings


class UpstreamUnavailable(Exception):
    """上游不可达 / 5xx → 502。"""


class UpstreamBadRequest(Exception):
    """上游 4xx → 400（附上游 message）。"""


def _transport() -> Optional[httpx.AsyncBaseTransport]:
    """测试注入点：monkeypatch 为返回 httpx.MockTransport 的工厂；生产返回 None。"""
    return None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.VOICE_DEMO_BASE_URL,
        timeout=httpx.Timeout(
            settings.VOICE_DEMO_CONNECT_TIMEOUT_MS / 1000,
            read=settings.VOICE_DEMO_READ_TIMEOUT_MS / 1000,
        ),
        headers={"Authorization": f"Bearer {settings.VOICE_DEMO_API_KEY}"}
        if settings.VOICE_DEMO_API_KEY
        else {},
        transport=_transport(),
    )


async def probe_pool() -> Optional[dict]:
    """GET /v1/pool；任何失败返回 None（health 降级展示）。"""
    try:
        async with _client() as c:
            r = await c.get("/v1/pool")
        return r.json() if r.status_code == 200 else None
    except httpx.HTTPError as exc:
        logger.warning(f"voice-demo pool 探测失败: {exc}")
        return None


async def transcribe(data: bytes, filename: str, language: str) -> dict:
    """POST /v1/audio/transcriptions（multipart file+language；实测无需 model，可选透传）。"""
    form = {"language": language}
    if settings.VOICE_DEMO_ASR_MODEL:
        form["model"] = settings.VOICE_DEMO_ASR_MODEL
    try:
        async with _client() as c:
            r = await c.post(
                "/v1/audio/transcriptions",
                data=form,
                files={"file": (filename, data, "application/octet-stream")},
            )
    except httpx.HTTPError as exc:
        logger.warning(f"voice-demo ASR 转发失败: {exc}")
        raise UpstreamUnavailable(str(exc)) from exc
    return _unwrap_json(r)


async def synthesize(payload: dict) -> bytes:
    """POST /v1/audio/speech（JSON input/voice/response_format）→ WAV 字节。"""
    try:
        async with _client() as c:
            r = await c.post("/v1/audio/speech", json=payload)
    except httpx.HTTPError as exc:
        logger.warning(f"voice-demo TTS 转发失败: {exc}")
        raise UpstreamUnavailable(str(exc)) from exc
    if r.status_code >= 500:
        raise UpstreamUnavailable(r.text[:300])
    if r.status_code >= 400:
        raise UpstreamBadRequest(r.text[:300])
    return r.content


def _unwrap_json(r: httpx.Response) -> dict:
    if r.status_code >= 500:
        raise UpstreamUnavailable(r.text[:300])
    if r.status_code >= 400:
        raise UpstreamBadRequest(r.text[:300])
    return r.json()
