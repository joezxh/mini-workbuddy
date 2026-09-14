"""调解语音配置管理端点（M3 配置化，差距分析 §9）。

挂载后路径：
    /api/v1/admin/duplex/config/voice-roles
    /api/v1/admin/duplex/config/agents
    /api/v1/admin/duplex/config/tool-policy

均为 UPSERT 语义（按唯一键 role_id / agent_id / tool_name 更新或新建）。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.database import SessionLocal
from app.duplex.voice.voice_config import (
    list_voice_models,
    resolve_voice_config,
    create_voice_model,
    update_voice_model,
    set_default_voice_model,
)
from app.models.duplex.duplex_voice_config import (
    AiAgentConfig,
    DuplexVoiceConfig,
    ToolPolicy,
)
from app.schemas.duplex.voice import (
    AgentConfigIn,
    ToolPolicyIn,
    VoiceRoleConfigIn,
)

router = APIRouter(prefix="/duplex", tags=["语音配置"])


def _upsert(db, model, key_field: str, key_value: str, payload: Dict[str, Any]):
    """按唯一键 UPSERT。"""
    obj = db.query(model).filter_by(**{key_field: key_value}).first()
    if not obj:
        obj = model(**{key_field: key_value})
    for k, v in payload.items():
        if k == key_field:
            continue
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── 角色语音配置 ──────────────────────────────────────────


@router.post("/config/voice-roles")
def upsert_voice_role(cfg: VoiceRoleConfigIn) -> Dict[str, Any]:
    with SessionLocal() as db:
        obj = _upsert(db, DuplexVoiceConfig, "role_id", cfg.role_id,
                      cfg.model_dump())
        return {"role_id": obj.role_id, "role_name": obj.role_name}


@router.get("/config/voice-roles")
def list_voice_roles() -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.query(DuplexVoiceConfig).all()
        return [
            {
                "role_id": r.role_id,
                "role_name": r.role_name,
                "greeting": r.greeting,
                "voice_identity": r.voice_identity,
                "language": r.language,
                "agent_id": r.agent_id,
                "case_type": r.case_type,
            }
            for r in rows
        ]


@router.get("/config/voice-roles/{role_id}")
def get_voice_role(role_id: str) -> Dict[str, Any]:
    with SessionLocal() as db:
        r = db.query(DuplexVoiceConfig).filter_by(role_id=role_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="role not found")
        return {
            "role_id": r.role_id,
            "role_name": r.role_name,
            "greeting": r.greeting,
            "voice_identity": r.voice_identity,
            "language": r.language,
            "agent_id": r.agent_id,
            "case_type": r.case_type,
        }


# ── Agent 配置 ────────────────────────────────────────────


@router.post("/config/agents")
def upsert_agent(cfg: AgentConfigIn) -> Dict[str, Any]:
    with SessionLocal() as db:
        obj = _upsert(db, AiAgentConfig, "agent_id", cfg.agent_id, cfg.model_dump())
        return {"agent_id": obj.agent_id, "name": obj.name}


@router.get("/config/agents")
def list_agents() -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.query(AiAgentConfig).all()
        return [
            {
                "agent_id": r.agent_id,
                "name": r.name,
                "type": r.type,
                "model": r.model,
                "max_react_iters": r.max_react_iters,
                "enable_plan": r.enable_plan,
            }
            for r in rows
        ]


# ── 工具调用策略 ──────────────────────────────────────────


@router.post("/config/tool-policy")
def upsert_tool_policy(cfg: ToolPolicyIn) -> Dict[str, Any]:
    with SessionLocal() as db:
        obj = _upsert(db, ToolPolicy, "tool_name", cfg.tool_name, cfg.model_dump())
        return {"tool_name": obj.tool_name, "enabled": obj.enabled}


@router.get("/config/tool-policy")
def list_tool_policies() -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.query(ToolPolicy).all()
        return [
            {
                "tool_name": r.tool_name,
                "enabled": r.enabled,
                "timeout_ms": r.timeout_ms,
                "max_calls_per_turn": r.max_calls_per_turn,
                "max_result_bytes": r.max_result_bytes,
            }
            for r in rows
        ]


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
