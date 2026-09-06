"""模型工厂扩展 —— DB 模型配置 → AgentScope 2.x ChatModelBase。

被以下模块依赖（延迟导入，避免与 db/模型层产生循环依赖）：

- ``app.ai.research.llm``：研究编排的 LLM 调用
- ``app.ai.skills.execution``：技能执行 Agent
- ``app.ai.team.orchestrator``：多 Agent 团队编排
- ``app.ai.agent_factory``：会话 Agent 构造

约定：
- ``resolve_model_config`` 返回**空 dict 表示不可用**（不存在/禁用/缺密钥），
  由调用方降级到 ENV 兜底配置，与 research.llm 的既有契约一致；
- ``build_model`` 只负责把配置映射为 agentscope 2.x 的模型实例，不抛业务异常之外的错误。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "resolve_model_config",
    "build_model",
    "build_default_model_config",
    "build_config_from_rows",
    "normalize_provider",
]

# 平台/提供商别名 → agentscope 模型族。
# 智谱/讯飞/百度/其他 等平台对外提供 OpenAI 兼容接口，统一走 OpenAIChatModel + base_url。
_PROVIDER_ALIASES: Dict[str, str] = {
    "openai": "openai",
    "gpt": "openai",
    "deepseek": "deepseek",
    "moonshot": "moonshot",
    "kimi": "moonshot",
    "xai": "xai",
    "grok": "xai",
    "dashscope": "dashscope",
    "qwen": "dashscope",
    "通义千问": "dashscope",
    "阿里": "dashscope",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "gemini": "gemini",
    "google": "gemini",
    "ollama": "ollama",
    "智谱": "openai",
    "glm": "openai",
    "zhipu": "openai",
    "讯飞": "openai",
    "spark": "openai",
    "百度": "openai",
    "文心": "openai",
    "ernie": "openai",
    "其他": "openai",
    "custom": "openai",
}


def normalize_provider(raw: Optional[str]) -> str:
    """把平台名归一化为 agentscope 模型族标识（未识别则按 OpenAI 兼容处理）。"""
    if not raw:
        return "openai"
    key = str(raw).strip().lower()
    if key in _PROVIDER_ALIASES:
        return _PROVIDER_ALIASES[key]
    # 中文平台名不做 lower 失效处理，再查一次原值
    return _PROVIDER_ALIASES.get(str(raw).strip(), "openai")


def build_config_from_rows(model: Any, api_key: Any) -> Dict[str, Any]:
    """由 AiChatModel + AiApiKey 两行记录组装模型配置 dict。

    抽出来供 ``resolve_model_config``（按 id 查）与
    ``registry_bridge.build_model_from_db``（按 code 查）共用，避免两处字段映射分叉。
    """
    return {
        "provider": model.platform or api_key.platform,
        "model": model.model,
        "base_url": api_key.url or "",
        "api_key": api_key.api_key,
        "temperature": model.temperature,
        "max_tokens": model.max_tokens,
        "top_p": model.top_p,
        "top_k": model.top_k,
        "seed": model.seed,
    }


def resolve_model_config(model_id: Optional[int]) -> Dict[str, Any]:
    """读取 DB 中的模型配置。

    Args:
        model_id: ``ai_chat_model.id``。

    Returns:
        配置 dict（provider/model/base_url/api_key/temperature/max_tokens/top_p），
        **空 dict 表示该模型不可用**，调用方应降级到 ENV 兜底。
    """
    if not model_id:
        return {}

    from app.db.database import SessionLocal
    from app.models.ai.ai_api_key import AiApiKey, AiChatModel

    db = SessionLocal()
    try:
        model = (
            db.query(AiChatModel)
            .filter(AiChatModel.id == model_id, AiChatModel.status == 1)
            .first()
        )
        if not model:
            logger.warning("模型 %s 不存在或已禁用", model_id)
            return {}

        api_key = (
            db.query(AiApiKey)
            .filter(AiApiKey.id == model.key_id, AiApiKey.status == 1)
            .first()
        )
        if not api_key:
            logger.warning("模型 %s 关联的密钥不可用", model_id)
            return {}

        return build_config_from_rows(model, api_key)
    except Exception as e:  # noqa: BLE001 配置读取失败应降级，不应中断调用方
        logger.warning("读取模型配置失败: %s", e)
        return {}
    finally:
        db.close()


def build_default_model_config() -> Dict[str, Any]:
    """ENV 兜底模型配置（DB 无可用模型时使用）。"""
    return {
        "provider": "openai",
        "model": os.environ.get("DEFAULT_MODEL", "gpt-4o-mini"),
        "base_url": os.environ.get("OPENAI_BASE_URL", ""),
        "api_key": os.environ.get("OPENAI_API_KEY", ""),
        "temperature": 0.3,
    }


def build_model(cfg: Dict[str, Any]):
    """把配置 dict 构建为 AgentScope 2.x 的 ChatModelBase 实例。

    agentscope 2.x 的模型构造函数签名为 ``(credential, model, parameters=...)``，
    凭据是 pydantic 模型（而非裸 api_key 字符串）。
    """
    from agentscope.credential import (
        AnthropicCredential,
        DashScopeCredential,
        DeepSeekCredential,
        GeminiCredential,
        MoonshotCredential,
        OllamaCredential,
        OpenAICredential,
        XAICredential,
    )
    from agentscope.model import (
        AnthropicChatModel,
        DashScopeChatModel,
        DeepSeekChatModel,
        GeminiChatModel,
        MoonshotChatModel,
        OllamaChatModel,
        OpenAIChatModel,
        XAIChatModel,
    )

    provider = normalize_provider(cfg.get("provider"))
    model_name = cfg.get("model") or ""
    base_url = (cfg.get("base_url") or "").strip()
    api_key = cfg.get("api_key") or ""

    table = {
        "openai": (OpenAIChatModel, OpenAICredential),
        "deepseek": (DeepSeekChatModel, DeepSeekCredential),
        "moonshot": (MoonshotChatModel, MoonshotCredential),
        "xai": (XAIChatModel, XAICredential),
        "dashscope": (DashScopeChatModel, DashScopeCredential),
        "anthropic": (AnthropicChatModel, AnthropicCredential),
        "gemini": (GeminiChatModel, GeminiCredential),
        "ollama": (OllamaChatModel, OllamaCredential),
    }
    model_cls, cred_cls = table.get(provider, (OpenAIChatModel, OpenAICredential))

    cred_kwargs: Dict[str, Any] = {"api_key": api_key}
    fields = getattr(cred_cls, "model_fields", {}) or {}
    if base_url and "base_url" in fields:
        cred_kwargs["base_url"] = base_url
    credential = cred_cls(**cred_kwargs)

    kwargs: Dict[str, Any] = {}
    if provider == "ollama":
        # Ollama 的凭据可为空，model 名与本地服务地址通过 model/base_url 表达
        kwargs["model"] = model_name
    else:
        kwargs["model"] = model_name
    parameters = _build_parameters(model_cls, cfg)
    if parameters is not None:
        kwargs["parameters"] = parameters

    logger.info(
        "构建模型 provider=%s model=%s base_url=%s api_key_set=%s",
        provider, model_name, base_url, bool(api_key),
    )
    return model_cls(credential=credential, **kwargs)


def _build_parameters(model_cls: Any, cfg: Dict[str, Any]) -> Any:
    """按模型类自身的 Parameters schema 构造参数，失败则回退默认参数。"""
    params_cls = getattr(model_cls, "Parameters", None)
    if params_cls is None:
        return None

    candidates = ("temperature", "max_tokens", "top_p", "top_k", "seed")
    kwargs = {k: cfg[k] for k in candidates if cfg.get(k) is not None}
    if not kwargs:
        return None
    try:
        return params_cls(**kwargs)
    except Exception as e:  # noqa: BLE001 参数不兼容不应阻断模型构建
        logger.warning("构建模型参数失败，改用默认参数: %s", e)
        return None
