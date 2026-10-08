"""pipeline_config 规范化（spec §10.7 / D8）。

键名对齐 AgentScope 原生参数名：``parser`` / ``chunker`` / ``embedding`` /
``index`` / ``rag``。原生链路要求 ``chunker.params`` / ``rag`` 段能**无转换**地
传入 ``ChunkerBase.Parameters`` / ``RAGMiddleware.Parameters``，故本模块只做
白名单校验 + 清理，不做任何键名改写。
"""
from __future__ import annotations

from typing import Any, Optional

# 仅允许的原生顶级键（对齐文档 §6.1）
_NATIVE_TOP_KEYS = ("parser", "chunker", "embedding", "index", "rag")


def normalize_pipeline_config(raw: Optional[dict]) -> Optional[dict]:
    """校验并清理 pipeline_config；非法键名直接失败（D8）。

    返回清理后的 dict（去掉值为 None 的段），空配置返回 None。
    """
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise ValueError("pipeline_config 必须是 JSON 对象")
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in _NATIVE_TOP_KEYS:
            raise ValueError(
                f"pipeline_config 含未知键 {key!r}；"
                f"仅允许原生键 {list(_NATIVE_TOP_KEYS)}"
            )
        if value is not None:
            cleaned[key] = value
    return cleaned or None


def resolve_knowledge_pipeline_config(db, collection: str) -> Optional[dict]:
    """按 collection 名（``kb_{knowledge_id}``）取知识库编排配置并规范化。

    真实摄取链路据此驱动 parse/clean/chunk（spec §10.7）；无容器或无配置返回 None。
    """
    if not (collection and collection.startswith("kb_")):
        return None
    try:
        kid = int(collection[3:])
    except ValueError:
        return None
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    kn = db.get(WikiKnowledge, kid)
    if kn is None or not kn.pipeline_config:
        return None
    return normalize_pipeline_config(kn.pipeline_config)


def pipeline_config_schema() -> dict:
    """前端创建向导 / dry-run 直接消费的原生参数 Schema（D8 / §6.1）。"""
    from app.services.kb.pipeline_runner import cleaner_names, parser_names
    from app.services.kb.rag.chunker_factory import chunker_schemas
    from app.services.kb.rag.rag_middleware import rag_parameters_schema

    return {
        "keys": list(_NATIVE_TOP_KEYS),
        "parser": parser_names(),
        "clean": cleaner_names(),
        "chunker": chunker_schemas(),
        "rag": rag_parameters_schema(),
    }
