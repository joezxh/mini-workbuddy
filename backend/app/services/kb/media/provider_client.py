"""媒体 provider 客户端（OpenAI 兼容）：VLM 图片描述 + ASR 转写。

配置解析镜像 embedding_config：模型管理默认（type=6 vision / type=7 asr，
is_default + status=1 + 关联密钥可用）优先，collection 级覆盖
（kb_collection.retrieval_settings.vision_model / asr_model，spec §6）次之，
未配置回落 env（MediaSettings）。
重试 2 次指数退避，超时 120s（spec §8）。
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings

_TIMEOUT = 120.0
_RETRIES = 2
_VISION_MODEL_TYPE = 6
_ASR_MODEL_TYPE = 7


@dataclass
class MediaProviderConfig:
    """单个媒体模型的调用配置（provider 仅作溯源标识）。"""

    provider: str
    base_url: str
    api_key: str
    model: str


def _from_model_mgmt(
    db: Session, model_type: int, label: str
) -> Optional[MediaProviderConfig]:
    """模型管理默认模型（type=N + is_default + status=1）→ 配置；不完整返回 None。"""
    from app.models.ai.ai_api_key import AiApiKey, AiChatModel

    row = db.execute(
        select(AiChatModel).where(
            AiChatModel.type == model_type,
            AiChatModel.is_default.is_(True),
            AiChatModel.status == 1,
        ).order_by(AiChatModel.sort.desc(), AiChatModel.id.asc())
    ).scalars().first()
    if row is None:
        return None
    key = db.get(AiApiKey, row.key_id)
    if key is None or key.status != 1 or not (key.url or "").strip():
        logger.warning(
            f"[Media] 模型管理默认{label} {row.code or row.id} 密钥/地址不可用，回落 env"
        )
        return None
    return MediaProviderConfig(
        provider=f"model_mgmt:{row.code or row.id}",
        base_url=(key.url or "").strip().rstrip("/") + "/v1",
        api_key=key.api_key or "",
        model=row.model,
    )


def _from_env(kind: str) -> MediaProviderConfig:
    if kind == "vision":
        return MediaProviderConfig(
            settings.MEDIA_VISION_PROVIDER, settings.MEDIA_VISION_BASE_URL.rstrip("/"),
            settings.MEDIA_VISION_API_KEY, settings.MEDIA_VISION_MODEL,
        )
    return MediaProviderConfig(
        settings.MEDIA_ASR_PROVIDER, settings.MEDIA_ASR_BASE_URL.rstrip("/"),
        settings.MEDIA_ASR_API_KEY, settings.MEDIA_ASR_MODEL,
    )


def _apply_override(
    cfg: MediaProviderConfig, override: Optional[dict], key: str
) -> MediaProviderConfig:
    """collection 级覆盖（spec §6）：retrieval_settings 里的 model 替换 cfg.model。"""
    model = (override or {}).get(key)
    if model and str(model).strip():
        return MediaProviderConfig(
            cfg.provider, cfg.base_url, cfg.api_key, str(model).strip()
        )
    return cfg


def resolve_vision_config(
    db: Session, override: Optional[dict] = None
) -> MediaProviderConfig:
    """视觉模型解析：模型管理默认 → collection 覆盖 → env。"""
    cfg = _from_model_mgmt(db, _VISION_MODEL_TYPE, "视觉模型") or _from_env("vision")
    return _apply_override(cfg, override, "vision_model")


def resolve_asr_config(
    db: Session, override: Optional[dict] = None
) -> MediaProviderConfig:
    """语音模型解析：模型管理默认 → collection 覆盖 → env。"""
    cfg = _from_model_mgmt(db, _ASR_MODEL_TYPE, "语音模型") or _from_env("asr")
    return _apply_override(cfg, override, "asr_model")


async def _post_with_retry(
    url: str, *, json=None, data=None, files=None, headers: dict
) -> httpx.Response:
    """POST + 重试 2 次指数退避；非 2xx 显式抛错（不静默降级）。"""
    last: Exception = RuntimeError("未执行")
    for attempt in range(_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    url, json=json, data=data, files=files, headers=headers
                )
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            return resp
        except Exception as exc:  # noqa: BLE001 - 统一退避重试
            last = exc
            if attempt < _RETRIES:
                await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"媒体 provider 调用失败（已重试 {_RETRIES} 次）: {last}")


async def describe_image(
    cfg: MediaProviderConfig, image_bytes: bytes, mime: str, prompt: str
) -> str:
    """VLM 描述图片（OpenAI 兼容 chat/completions，图片 base64 data URI）。"""
    b64 = base64.b64encode(image_bytes).decode()
    resp = await _post_with_retry(
        f"{cfg.base_url}/chat/completions",
        json={
            "model": cfg.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
        },
        headers={"Authorization": f"Bearer {cfg.api_key or 'not-required'}"},
    )
    choice = (resp.json().get("choices") or [{}])[0]
    return (choice.get("message") or {}).get("content") or ""


async def transcribe_audio(
    cfg: MediaProviderConfig, audio_bytes: bytes, filename: str
) -> list[dict]:
    """ASR 转写（OpenAI 兼容 /audio/transcriptions，verbose_json 取时间轴分段）。

    返回 [{"start": 秒, "end": 秒, "text": 文本}]；服务端不支持 verbose_json
    segments 时降级为单段（start=end=0），不做词级对齐假设。
    """
    resp = await _post_with_retry(
        f"{cfg.base_url}/audio/transcriptions",
        data={"model": cfg.model, "response_format": "verbose_json"},
        files={"file": (filename, audio_bytes)},
        headers={"Authorization": f"Bearer {cfg.api_key or 'not-required'}"},
    )
    body = resp.json()
    segs = body.get("segments") or []
    if segs:
        return [
            {"start": float(s.get("start") or 0), "end": float(s.get("end") or 0),
             "text": (s.get("text") or "").strip()}
            for s in segs if (s.get("text") or "").strip()
        ]
    text = (body.get("text") or "").strip()
    return [{"start": 0.0, "end": 0.0, "text": text}] if text else []
