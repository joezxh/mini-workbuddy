"""语音模型配置管理端点。

挂载后路径：
    /api/v1/admin/duplex/config/voice-models

数据来源：ai_api_key（API 密钥） + ai_chat_model（模型，type=7 语音实时）。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.framework.duplex import (
    list_voice_models,
    resolve_voice_config,
    create_voice_model,
    update_voice_model,
    set_default_voice_model,
    list_voice_provider_catalog,
)

router = APIRouter(prefix="/duplex", tags=["语音配置"])


# ── 语音模型配置（来自 ai_api_key / ai_chat_model）──────────


class VoiceModelIn(BaseModel):
    id: Optional[int] = None
    key_id: int
    name: str
    model: str
    platform: Optional[str] = None
    sort: int = 0
    status: int = 1
    is_default: bool = False


class VoiceModelSetDefaultIn(BaseModel):
    model_id: int


@router.get("/config/voice-models")
def get_voice_models() -> List[Dict[str, Any]]:
    """列出所有启用的语音模型（前端下拉 / 配置页使用）。"""
    return list_voice_models()


@router.get("/config/voice-models/provider-catalog")
def get_voice_provider_catalog() -> Dict[str, Any]:
    """返回全双工语音厂商目录（含各厂商官方模型清单）。

    供前端「语音模型配置」页按厂商过滤模型下拉，以及 VoiceDemo 页
    Provider 列表仅展示有可用全双工模型的厂商。
    """
    return list_voice_provider_catalog()


@router.get("/config/voice-models/default")
def get_voice_model_default() -> Dict[str, Any]:
    """返回当前默认语音模型解析结果（不含 api_key 明文）。"""
    cfg = resolve_voice_config()
    return {
        "configured": cfg.get("configured", False),
        "reason": cfg.get("reason"),
        "model_id": cfg.get("model_id"),
        "model": cfg.get("model"),
        "key_name": cfg.get("key_name"),
        "platform": cfg.get("platform"),
        "is_default": cfg.get("is_default"),
    }


@router.post("/config/voice-models")
def upsert_voice_model(payload: VoiceModelIn) -> Dict[str, Any]:
    """创建或更新语音模型（按 id 区分；type 固定为语音实时类型）。"""
    data = payload.model_dump(exclude_none=True)
    model_id = data.get("id")
    if model_id:
        data.pop("id", None)
        return update_voice_model(data)
    data.pop("id", None)
    return create_voice_model(data)


@router.post("/config/voice-models/set-default")
def set_default_voice_model_endpoint(payload: VoiceModelSetDefaultIn) -> Dict[str, Any]:
    """将指定语音模型设为默认。"""
    try:
        return set_default_voice_model(payload.model_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
