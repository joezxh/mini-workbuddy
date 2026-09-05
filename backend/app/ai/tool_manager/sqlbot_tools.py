"""SqlBotQuery 工具 —— 将 SQLBot NL2SQL 封装为 Agent 可调用 ToolBase。

解锁 41/78 技能的 "SQLBot 数据查询" 依赖。
内部复用 app.middleware.sqlbot_client 单例，阻塞式返回聚合结果。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from agentscope.message import TextBlock
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)
from agentscope.tool import ToolBase, ToolChunk

logger = logging.getLogger(__name__)


class SqlBotQuery(ToolBase):
    """通过自然语言查询业务数据库（NL2SQL），返回结构化数据。

    适用于 "各维度聚合统计与排名"、"处置时长、成功率统计" 等数据查询场景。
    内部调用 SQLBot 私有化服务，自动完成 NL→SQL→执行→返回 全流程。
    """

    name: str = "sqlbot_query"
    description: str = (
        "通过自然语言提问查询业务数据库（NL2SQL），返回数据行列表。"
        "适用于聚合统计、排名、趋势等结构化数据查询。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "自然语言查询问题，如'各区域纠纷数量统计'",
            },
            "datasource_id": {
                "type": "integer",
                "description": "数据源 ID，不传则使用默认数据源",
            },
            "top_k": {
                "type": "integer",
                "description": "返回行数上限，默认 100",
                "default": 100,
            },
        },
        "required": ["question"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = True

    def __init__(self) -> None:
        super().__init__()
        # 延迟导入避免循环依赖
        from app.middleware.sqlbot_client import sqlbot_client
        self._client = sqlbot_client

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext
    ) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Read-only NL2SQL query via SQLBot.",
        )

    async def call(
        self,
        question: str,
        datasource_id: int | None = None,
        top_k: int = 100,
    ) -> ToolChunk:
        try:
            records: list[dict[str, Any]] = await self._client.query(
                question=question,
                datasource_id=datasource_id,
            )
            # 截断到 top_k
            if len(records) > top_k:
                records = records[:top_k]
            payload = {
                "question": question,
                "records": records,
                "total": len(records),
                "truncated": len(records) == top_k,
            }
            return ToolChunk(
                content=[TextBlock(type="text", text=json.dumps(payload, ensure_ascii=False, default=str))]
            )
        except Exception as exc:
            logger.warning("sqlbot_query failed: %s", exc)
            error_payload = {"error": str(exc), "question": question}
            return ToolChunk(
                content=[TextBlock(type="text", text=json.dumps(error_payload, ensure_ascii=False))]
            )
