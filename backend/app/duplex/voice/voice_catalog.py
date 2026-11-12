"""全双工（实时）语音大模型厂商目录。

数据来源：**数据库**（不再硬编码）。
- 厂商、模型、API Key、默认端点全部来自 ``ai_api_key`` + ``ai_chat_model(type=7)`` 表；
- 仅 ``api_key_url``（Key 申请地址）和 ``docs_url``（官方文档地址）两个纯元数据字段
  保留在本模块的 ``_PROVIDER_META`` 静态映射中（DB 表无对应列）。

供以下场景使用：
- ``voice_config._voice_row_usable`` 校验模型名是否为厂商官方全双工语音模型；
- 前端「语音模型配置」页创建/编辑模型时，按厂商过滤可选模型下拉；
- 前端 VoiceDemo 页 Provider 列表仅展示已配置可用全双工模型的厂商。

严格约束（需求 §7）：本目录只收录各厂商**官方发布的全双工语音大模型**
（speech-to-speech / realtime voice conversation）。新增模型时请在
``ai_chat_model`` 表中插入 ``type=7`` 的记录，并保证 ``ai_api_key`` 有对应密钥。
"""
from typing import Dict, List, Optional, TypedDict

from app.db.database import SessionLocal
from app.models.ai.ai_api_key import AiApiKey, AiChatModel

# 语音/实时模型类型（与 ai_chat_model.type 对齐：1=对话, 5=向量, 7=语音实时）
VOICE_MODEL_TYPE = 7


class VoiceModelCatalogItem(TypedDict):
    """目录中的单个全双工语音模型条目。"""
    code: str          # 模型标识（API 调用时使用，如 qwen3.8-omni-flash-realtime）
    name: str          # 展示名称（如 Qwen3.8-Omni-Flash-Realtime）
    is_default: bool   # 是否为该厂商推荐默认模型


class VoiceProviderCatalogItem(TypedDict):
    """单个厂商的全双工语音模型目录。"""
    key: str                       # 厂商 key（与 ai_api_key.platform 归一化后对齐）
    label: str                     # 展示名称
    default_base_url: str          # 默认实时端点（WebSocket）
    api_key: str                   # API Key（来自 ai_api_key.api_key）
    api_key_url: str               # API Key 申请地址（静态元数据）
    docs_url: str                  # 官方文档地址（静态元数据）
    models: List[VoiceModelCatalogItem]


# ── 纯元数据映射（DB 表无对应列，仅此两项保留静态） ──────────────────────
# 仅维护 api_key_url 与 docs_url，厂商/模型/api_key/端点全部来自 DB。
_PROVIDER_META: Dict[str, Dict[str, str]] = {
    "dashscope": {
        "api_key_url": "https://dashscope.console.aliyun.com/apiKey",
        "docs_url": "https://help.aliyun.com/zh/model-studio/developer-reference/realtime-voice-video-api",
    },
    "openai": {
        "api_key_url": "https://platform.openai.com/api-keys",
        "docs_url": "https://platform.openai.com/docs/guides/realtime",
    },
    "google": {
        "api_key_url": "https://aistudio.google.com/app/apikey",
        "docs_url": "https://ai.google.dev/gemini-api/docs/live-api",
    },
    "volcengine": {
        "api_key_url": "https://console.volcengine.com/iam/keymanage",
        "docs_url": "https://www.volcengine.com/docs/6561/1594356",
    },
    "iflytek": {
        "api_key_url": "https://www.xfyun.cn/services/voiceservice",
        "docs_url": "https://www.xfyun.cn/doc/spark/sparkos_interactive.html",
    },
}


def get_provider_catalog() -> Dict[str, VoiceProviderCatalogItem]:
    """从数据库读取全双工语音厂商目录。

    查询逻辑：
    - 取所有 ``status=1`` 的 ``ai_api_key``；
    - 对每个 key 取其下 ``type=VOICE_MODEL_TYPE(7)`` 且 ``status=1`` 的 ``ai_chat_model``；
    - 按 ``normalize_provider_key`` 归一化平台后聚合为 catalog。

    返回结构含 ``api_key`` 字段，供下游 ``resolve_voice_config`` 直接使用，
    避免再次查库。
    """
    db = SessionLocal()
    try:
        keys = db.query(AiApiKey).filter(AiApiKey.status == 1).all()
        if not keys:
            return {}

        catalog: Dict[str, VoiceProviderCatalogItem] = {}
        for key in keys:
            provider_key = normalize_provider_key(key.platform or "")
            if not provider_key:
                continue

            models = (
                db.query(AiChatModel)
                .filter(
                    AiChatModel.key_id == key.id,
                    AiChatModel.type == VOICE_MODEL_TYPE,
                    AiChatModel.status == 1,
                )
                .order_by(AiChatModel.is_default.desc(), AiChatModel.sort.desc(), AiChatModel.id.asc())
                .all()
            )
            if not models:
                continue

            meta = _PROVIDER_META.get(provider_key, {})
            # 若同一归一化 key 已有条目（多个 key 行同平台），合并模型列表
            existing = catalog.get(provider_key)
            model_items: List[VoiceModelCatalogItem] = (
                list(existing["models"]) if existing else []
            )
            existing_codes = {m["code"] for m in model_items}
            for m in models:
                code = m.model or m.code or ""
                if not code or code in existing_codes:
                    continue
                model_items.append({
                    "code": code,
                    "name": m.name or code,
                    "is_default": bool(m.is_default),
                })
                existing_codes.add(code)

            catalog[provider_key] = {
                "key": provider_key,
                "label": existing["label"] if existing else (key.name or key.platform or provider_key),
                "default_base_url": key.url or "",
                "api_key": key.api_key or "",
                "api_key_url": meta.get("api_key_url", ""),
                "docs_url": meta.get("docs_url", ""),
                "models": model_items,
            }
        return catalog
    finally:
        db.close()


def get_provider_model_codes(provider_key: str) -> List[str]:
    """返回指定厂商的全双工语音模型 code 列表（来自 DB）。"""
    provider = get_provider_catalog().get((provider_key or "").lower())
    if not provider:
        return []
    return [m["code"] for m in provider["models"]]


def is_full_duplex_voice_model(provider_key: str, model_code: str) -> bool:
    """校验 model_code 是否为指定厂商官方发布的全双工语音模型。"""
    return model_code in get_provider_model_codes(provider_key)


def normalize_provider_key(platform: str) -> str:
    """将 ai_api_key.platform 归一化为目录 key（小写，兼容历史大小写）。"""
    p = (platform or "").strip().lower()
    # 历史兼容：DashScope 平台值可能为 "DashScope" / "dashscope" / "通义千问" / "aliyun"
    aliases = {
        "dashscope": "dashscope",
        "通义千问": "dashscope",
        "aliyun": "dashscope",
        "阿里云": "dashscope",
        "openai": "openai",
        "google": "google",
        "gemini": "google",
        "volcengine": "volcengine",
        "bytedance": "volcengine",
        "字节跳动": "volcengine",
        "doubao": "volcengine",
        "豆包": "volcengine",
        "iflytek": "iflytek",
        "讯飞": "iflytek",
        "xfyun": "iflytek",
        "spark": "iflytek",
    }
    return aliases.get(p, p)
