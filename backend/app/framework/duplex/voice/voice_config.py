"""语音服务配置解析：从数据库 ai_api_key / ai_chat_model 读取语音模型配置。

设计要点：
- 语音/实时模型在 ai_chat_model 中以 type=VOICE_MODEL_TYPE 标记（与对话/向量类型区分）。
- 网关连接前调用 resolve_voice_config() 取得 api_key + model，避免硬编码/环境变量缺失导致连接失败。
- 前端「语音模型配置」页通过 list_voice_models() / set_default_voice_model() 管理可选模型与默认模型。
- 全双工语音模型的有效性校验统一依赖 voice_catalog.get_provider_catalog()
  （从 DB 读取），确保仅各厂商官方发布的全双工语音大模型可被标记为 usable。
"""
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.ai.ai_api_key import AiApiKey, AiChatModel
from app.framework.duplex.voice.voice_catalog import (
    get_provider_catalog,
    is_full_duplex_voice_model,
    normalize_provider_key,
)

# 语音/实时模型类型（与 ai_chat_model.type 对齐：1=对话, 5=向量, 7=语音实时）
# 注意：7 取自前端「模型类别」数据字典(model_type)中“语音模型”的取值，必须保持一致。
VOICE_MODEL_TYPE = 7


def _voice_row_platform(model: AiChatModel, key: Optional[AiApiKey]) -> str:
    """返回模型行归一化后的厂商 key（供目录匹配使用）。"""
    raw = key.platform if key else (model.platform or "")
    return normalize_provider_key(raw)


def _voice_row_base_url(
    model: AiChatModel, key: Optional[AiApiKey], catalog: Dict
) -> Optional[str]:
    """优先取密钥自定义 url，其次取目录默认端点。"""
    if key and key.url:
        return key.url
    provider = catalog.get(_voice_row_platform(model, key))
    return provider["default_base_url"] if provider else None


def _voice_row_usable(
    model: AiChatModel, key: Optional[AiApiKey], catalog: Dict
) -> bool:
    """模型行是否可用于建立实时连接。

    校验规则（严格对齐全双工语音模型目录）：
    1. 厂商必须在目录内（normalize_provider_key 命中）；
    2. 模型名必须为该厂商官方发布的全双工语音大模型（is_full_duplex_voice_model）；
    3. API Key 非空。
    """
    provider_key = _voice_row_platform(model, key)
    if provider_key not in catalog:
        return False
    api_key = key.api_key if key else None
    return is_full_duplex_voice_model(provider_key, model.model) and bool(api_key)


def _platform_matches(want: Optional[str], row_platform: str) -> bool:
    """provider key 与模型行平台匹配：None→全部；指定→归一化后精确匹配。"""
    if want is None:
        return True
    return normalize_provider_key(want) == row_platform


def _row_dict(model: AiChatModel, key: Optional[AiApiKey], catalog: Dict) -> Dict:
    provider_key = _voice_row_platform(model, key)
    provider = catalog.get(provider_key)
    base_url = _voice_row_base_url(model, key, catalog)
    return {
        "id": model.id,
        "name": model.name,
        "model": model.model,
        "platform": provider["label"] if provider else (key.platform if key else model.platform or ""),
        "provider_key": provider_key,
        "key_id": model.key_id,
        "key_name": key.name if key else None,
        "is_default": bool(model.is_default),
        "status": model.status,
        "sort": model.sort,
        "base_url": base_url,
        "api_key": key.api_key if key else "",
        "usable": _voice_row_usable(model, key, catalog),
    }


def list_voice_provider_catalog() -> Dict:
    """返回全双工语音厂商目录（含各厂商官方模型清单）。

    供前端「语音模型配置」页创建/编辑模型时按厂商过滤模型下拉，
    以及 VoiceDemo 页 Provider 列表展示。
    """
    return get_provider_catalog()


def resolve_voice_config(
    provider_key: Optional[str] = None,
    model_id: Optional[int] = None,
) -> Dict:
    """解析语音连接所需的配置（api_key + model + 端点）。

    优先级：
    1. model_id 给定 → 使用该模型（须启用且可用；不可用时报 invalid_model/empty_key）；
    2. 否则按 provider 平台取可用模型中的默认（s2s 平台取 platform='s2s' 的行，
       其余取 DashScope 等云端平台的行）；
    3. 仍无 → 回退到第一条可用模型。

    可用性规则（见 _voice_row_usable）：
    - DashScope：模型名必须在官方实时模型目录内 且 api_key 非空；
    - s2s（本地 Docker）：无需 Key，端点取密钥 url（缺省 ws://127.0.0.1:8765/v1/realtime）。

    返回结构恒为 dict，含 ``configured`` 标志：
    - ``configured=True``：含 api_key / model / base_url 等连接字段；
    - ``configured=False``：``reason`` 为 ``"no_model"`` / ``"empty_key"``
      / ``"invalid_model"``（DashScope 模型名不在官方目录内）。
    """
    db: Session = SessionLocal()
    try:
        catalog = get_provider_catalog()
        rows = (
            db.query(AiChatModel)
            .outerjoin(AiApiKey, AiChatModel.key_id == AiApiKey.id)
            .filter(AiChatModel.type == VOICE_MODEL_TYPE, AiChatModel.status == 1)
            .order_by(
                AiChatModel.is_default.desc(), AiChatModel.sort.desc(), AiChatModel.id.asc()
            )
            .all()
        )
        if model_id is not None:
            row = next((r for r in rows if r.id == model_id), None)
            if row is None:
                return {"configured": False, "reason": "no_model"}
            key = row.api_key_obj
            # 平台校验：指定 provider 时所选模型行必须同平台
            # （防止 provider=openai 误用 DashScope 模型行 / 反之）
            if provider_key and not _platform_matches(
                provider_key, _voice_row_platform(row, key)
            ):
                return {"configured": False, "reason": "invalid_model",
                        "model_id": row.id, "model": row.model}
            if not _voice_row_usable(row, key, catalog):
                api_key = key.api_key if key else None
                if api_key:
                    return {
                        "configured": False,
                        "reason": "invalid_model",
                        "model_id": row.id,
                        "model": row.model,
                    }
                return {
                    "configured": False,
                    "reason": "empty_key",
                    "model_id": row.id,
                    "model": row.model,
                    "key_name": key.name if key else None,
                }
            return _row_dict(row, key, catalog) | {"configured": True}

        candidates = [
            r for r in rows
            if _platform_matches(provider_key,
                                 _voice_row_platform(r, r.api_key_obj))
            and _voice_row_usable(r, r.api_key_obj, catalog)
        ]
        if not candidates:
            return {"configured": False, "reason": "no_model"}
        return _row_dict(candidates[0], candidates[0].api_key_obj, catalog) | {"configured": True}
    finally:
        db.close()


def list_voice_models() -> List[Dict]:
    """返回所有启用的语音模型（前端下拉 / 配置页使用）。

    不再按可用性过滤：即使模型不可用（DashScope 模型名无效或密钥为空），
    也返回并携带 ``usable=False``，便于前端展示并提示用户去「语音模型配置」修复。
    """
    db: Session = SessionLocal()
    try:
        catalog = get_provider_catalog()
        rows = (
            db.query(AiChatModel)
            .outerjoin(AiApiKey, AiChatModel.key_id == AiApiKey.id)
            .filter(AiChatModel.type == VOICE_MODEL_TYPE, AiChatModel.status == 1)
            .order_by(
                AiChatModel.is_default.desc(), AiChatModel.sort.desc(), AiChatModel.id.asc()
            )
            .all()
        )
        return [
            _row_dict(m, m.api_key_obj, catalog)
            for m in rows
        ]
    finally:
        db.close()


def create_voice_model(data: Dict) -> Dict:
    """创建语音模型（type 固定为 VOICE_MODEL_TYPE）。"""
    db: Session = SessionLocal()
    try:
        cm = AiChatModel(
            code=data.get("code"),
            key_id=data["key_id"],
            name=data["name"],
            model=data["model"],
            platform=data.get("platform"),
            sort=data.get("sort", 0),
            status=data.get("status", 1),
            type=VOICE_MODEL_TYPE,
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
            is_default=bool(data.get("is_default", False)),
        )
        if cm.is_default:
            # 语音模型默认应全局唯一：清除同类型下其它所有默认（跨 key）
            db.query(AiChatModel).filter(
                AiChatModel.type == VOICE_MODEL_TYPE,
                AiChatModel.is_default.is_(True),
            ).update({AiChatModel.is_default: False})
        db.add(cm)
        db.commit()
        db.refresh(cm)
        return {"id": cm.id, "model": cm.model, "is_default": cm.is_default}
    finally:
        db.close()


def update_voice_model(data: Dict) -> Dict:
    """更新语音模型（按 id）。"""
    db: Session = SessionLocal()
    try:
        cm = db.query(AiChatModel).filter(AiChatModel.id == data["id"]).first()
        if not cm or cm.type != VOICE_MODEL_TYPE:
            raise ValueError("语音模型不存在")
        cm.name = data.get("name", cm.name)
        cm.model = data.get("model", cm.model)
        cm.platform = data.get("platform", cm.platform)
        cm.key_id = data.get("key_id", cm.key_id)
        cm.sort = data.get("sort", cm.sort)
        cm.status = data.get("status", cm.status)
        if "is_default" in data:
            cm.is_default = bool(data["is_default"])
            if cm.is_default:
                # 语音模型默认应全局唯一：清除同类型下其它所有默认（跨 key）
                db.query(AiChatModel).filter(
                    AiChatModel.type == VOICE_MODEL_TYPE,
                    AiChatModel.id != cm.id,
                    AiChatModel.is_default.is_(True),
                ).update({AiChatModel.is_default: False})
        db.commit()
        db.refresh(cm)
        return {"id": cm.id, "model": cm.model, "is_default": cm.is_default}
    finally:
        db.close()


def set_default_voice_model(model_id: int) -> Dict:
    """将指定语音模型设为默认（清除同类型其它默认，保证全局唯一）。"""
    db: Session = SessionLocal()
    try:
        cm = db.query(AiChatModel).filter(AiChatModel.id == model_id).first()
        if not cm or cm.type != VOICE_MODEL_TYPE:
            raise ValueError("语音模型不存在")
        db.query(AiChatModel).filter(
            AiChatModel.type == VOICE_MODEL_TYPE,
            AiChatModel.id != cm.id,
            AiChatModel.is_default.is_(True),
        ).update({AiChatModel.is_default: False})
        cm.is_default = True
        cm.status = 1
        db.commit()
        db.refresh(cm)
        return {"id": cm.id, "model": cm.model, "is_default": True}
    finally:
        db.close()
