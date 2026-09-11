"""内置工具 seed：启动时把系统工具写入 ``ai_tool_definition`` 表（幂等）。

与 ``web_search_tool.build_web_search_definition`` / ``ontology_tools
.build_ontology_tool_definitions`` 配套：首次启动插入，之后每次启动若已存在
则跳过（按 ``tool_key`` 去重），不覆盖管理员在后台做的修改。
"""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.ai.ai_tool_definition import AiToolDefinition

logger = logging.getLogger(__name__)


def _all_builtin_definitions() -> List[AiToolDefinition]:
    """汇总所有系统内置工具定义（含 web_search + 三个本体工具 + 五个 DataOps 工具）。"""
    from app.ai.tool_manager.web_search_tool import build_web_search_definition
    from app.ai.tools.dataops_tools import build_dataops_tool_definitions
    from app.ai.tools.ontology_tools import build_ontology_tool_definitions

    defs: List[AiToolDefinition] = []
    try:
        defs.append(build_web_search_definition())
    except Exception as exc:  # noqa: BLE001 - 单个工具构建失败不应阻断启动
        logger.warning("构造 web_search 定义失败，跳过: %s", exc)
    try:
        defs.extend(build_ontology_tool_definitions())
    except Exception as exc:  # noqa: BLE001
        logger.warning("构造本体工具定义失败，跳过: %s", exc)
    try:
        defs.extend(build_dataops_tool_definitions())
    except Exception as exc:  # noqa: BLE001
        logger.warning("构造 DataOps 工具定义失败，跳过: %s", exc)
    return defs


def register_builtin_tools(db: Session) -> int:
    """幂等地把系统内置工具登记进 ``ai_tool_definition``。

    返回本次新插入的数量（已存在的不计入）。
    """
    existing = {
        r.tool_key
        for r in db.query(AiToolDefinition.tool_key).all()
    }
    inserted = 0
    for defn in _all_builtin_definitions():
        if defn.tool_key in existing:
            continue
        db.add(defn)
        existing.add(defn.tool_key)
        inserted += 1
    if inserted:
        db.commit()
        logger.info("已登记 %d 个内置工具", inserted)
    return inserted
