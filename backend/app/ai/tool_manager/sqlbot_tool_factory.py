"""SqlBotTemplateTool 工厂。

由 ``tool_key`` 定位 ``tool_definition`` 记录，解析 ``config_value`` 并构造
可执行的 :class:`SqlBotTemplateTool` 实例。优先命中 ``ToolManager.definitions``
内存缓存，避免每次调用查库。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.ai.tool_manager.sqlbot_template_tool import SqlBotTemplateTool
from app.ai.tool_manager.sqlbot_tool_config import validate_config
from app.ai.tool_manager.tool_context import ToolUserContext

logger = logging.getLogger(__name__)

__all__ = [
    "SQLBOT_TEMPLATE_CLASS_PATH",
    "is_sqlbot_template_tool",
    "build_tool",
    "from_tool_key",
    "load_definition",
    "build_all_from_db",
]

SQLBOT_TEMPLATE_CLASS_PATH = (
    "app.ai.tool_manager.sqlbot_template_tool.SqlBotTemplateTool"
)


def is_sqlbot_template_tool(definition: Any) -> bool:
    """判断某个 AiToolDefinition 是否为配置化 SQLBot 工具。"""
    if definition is None:
        return False
    class_name = getattr(definition, "class_name", None) or ""
    return class_name.strip() == SQLBOT_TEMPLATE_CLASS_PATH


def load_definition(tool_key: str, db: Any = None) -> Optional[Any]:
    """按 tool_key 读取工具定义：先查内存缓存，未命中再查库。"""
    if not tool_key:
        return None

    try:
        from app.ai.tool_manager.manager import get_tool_manager

        cached = get_tool_manager().get_definition(tool_key)
        if cached is not None:
            return cached
    except Exception as exc:  # noqa: BLE001
        logger.debug("读取 ToolManager 缓存失败: %s", exc)

    if db is None:
        return None

    try:
        from app.models.ai.ai_tool_definition import AiToolDefinition

        return (
            db.query(AiToolDefinition)
            .filter(AiToolDefinition.tool_key == tool_key)
            .first()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("查询工具定义失败 tool_key=%s: %s", tool_key, exc)
        return None


def build_tool(
    definition: Any,
    context: Optional[ToolUserContext] = None,
) -> Optional[SqlBotTemplateTool]:
    """由工具定义构造 Tool 实例。配置非法时返回 None。"""
    if definition is None:
        return None

    raw = getattr(definition, "config_value", None)
    cfg, errors, warnings = validate_config(raw if isinstance(raw, dict) else {})
    if cfg is None:
        logger.warning(
            "SQLBot 工具配置非法 tool_key=%s: %s",
            getattr(definition, "tool_key", "?"),
            errors,
        )
        return None
    if warnings:
        logger.info(
            "SQLBot 工具配置告警 tool_key=%s: %s",
            getattr(definition, "tool_key", "?"),
            warnings,
        )

    return SqlBotTemplateTool(
        config=cfg,
        context=context,
        tool_key=getattr(definition, "tool_key", None),
        display_name=getattr(definition, "display_name", None),
        description=getattr(definition, "description", None),
    )


def from_tool_key(
    tool_key: str,
    db: Any = None,
    context: Optional[ToolUserContext] = None,
) -> Optional[SqlBotTemplateTool]:
    """按 tool_key 构造 Tool 实例。"""
    definition = load_definition(tool_key, db)
    if definition is None:
        logger.warning("未找到工具定义: %s", tool_key)
        return None
    if getattr(definition, "status", "enabled") != "enabled":
        logger.warning("工具已禁用: %s", tool_key)
        return None
    return build_tool(definition, context)


def build_from_config(
    config: Dict[str, Any],
    tool_key: str = "sqlbot_preview",
    context: Optional[ToolUserContext] = None,
) -> tuple[Optional[SqlBotTemplateTool], List[str], List[str]]:
    """由原始配置字典直接构造实例（供配置校验与试跑接口使用）。

    :return: ``(tool, errors, warnings)``
    """
    cfg, errors, warnings = validate_config(config)
    if cfg is None:
        return None, errors, warnings
    tool = SqlBotTemplateTool(config=cfg, context=context, tool_key=tool_key)
    return tool, errors, warnings


def build_all_from_db(
    db: Any, context: Optional[ToolUserContext] = None
) -> Dict[str, SqlBotTemplateTool]:
    """批量构造全部启用的配置化 SQLBot 工具（供 Agent 装配 / 启动预热）。"""
    result: Dict[str, SqlBotTemplateTool] = {}
    try:
        from app.models.ai.ai_tool_definition import AiToolDefinition

        rows = (
            db.query(AiToolDefinition)
            .filter(AiToolDefinition.class_name == SQLBOT_TEMPLATE_CLASS_PATH)
            .filter(AiToolDefinition.status == "enabled")
            .all()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("批量加载 SQLBot 工具失败: %s", exc)
        return result

    for row in rows:
        tool = build_tool(row, context)
        if tool is not None:
            result[row.tool_key] = tool
    logger.info("已构造 %d 个配置化 SQLBot 业务工具", len(result))
    return result
