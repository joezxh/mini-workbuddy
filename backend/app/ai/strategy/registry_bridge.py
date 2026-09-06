"""模型注册桥 —— 按业务标识（model_code）从 DB 构建 ChatModel。

与 :mod:`app.ai.strategy.factory_ext` 的分工：

- ``factory_ext.resolve_model_config(model_id)`` 按**主键 id** 取配置；
- 本模块 ``build_model_from_db(db, model_code)`` 按 **ai_chat_model.code**
  （前端选择的模型编码）取配置，由调用方传入自己的 Session。

主要供技能进化（``app.ai.skills.evolution.optimizer``）等「按业务编码取模型」的场景使用。

约定：找不到 / 不可用 / 构建失败时返回 ``None``，由调用方降级到下一个模型来源，
不在此抛异常吞掉调用方的回退链。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["build_model_from_db"]


def build_model_from_db(db: Any, model_code: Optional[str]) -> Any:
    """按模型编码（ai_chat_model.code）构建 AgentScope ChatModel。

    Args:
        db: SQLAlchemy Session（由调用方管理生命周期）。
        model_code: 模型编码；为空则直接返回 None。

    Returns:
        构建好的 ChatModelBase 实例；不可用时返回 None。
    """
    if not model_code:
        return None

    from app.ai.strategy.factory_ext import build_config_from_rows, build_model
    from app.models.ai.ai_api_key import AiApiKey, AiChatModel

    try:
        model = (
            db.query(AiChatModel)
            .filter(AiChatModel.code == model_code, AiChatModel.status == 1)
            .first()
        )
        if not model:
            logger.warning("模型编码 %s 不存在或已禁用", model_code)
            return None

        api_key = (
            db.query(AiApiKey)
            .filter(AiApiKey.id == model.key_id, AiApiKey.status == 1)
            .first()
        )
        if not api_key:
            logger.warning("模型编码 %s 关联的密钥不可用", model_code)
            return None

        return build_model(build_config_from_rows(model, api_key))
    except Exception as e:  # noqa: BLE001 交由调用方回退到其它模型来源
        logger.warning("按编码 %s 构建模型失败: %s", model_code, e)
        return None
