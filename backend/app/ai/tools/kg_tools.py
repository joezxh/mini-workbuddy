"""知识图谱 Agent 工具（kg_query）。

暴露给 Agent（AgentScope ToolBase 协议），供 Agent 对图谱知识库做多跳问答。

设计要点
--------
* 单工具多子命令：entity_search / neighbors / paths / stats，
  避免为每个子命令各建一个工具（工具列表膨胀）。子命令由 action 参数区分。
* 不依赖 ontology 模块任何符号：ontology 正随 semantica 迁移被删，
  本工具只依赖 app.services.kb.kg.*。
* 租户 fail-closed：call() 内自建会话，经 get_tool_user() 解析 tenant_id；
  取不到租户的调用返回 tenant_required，绝不落到 NULL 分区。
* 只读：不写任何数据，权限默认放行。

消费的服务：KgService（实体/关系/子图/路径/统计）。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from agentscope.message import TextBlock
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)
from agentscope.tool import ToolBase, ToolChunk

logger = logging.getLogger(__name__)

__all__ = [
    "KgQueryTool",
    "KG_TOOL_KEYS",
    "KG_TOOL_TYPE",
    "build_kg_tool_definitions",
]

KG_TOOL_TYPE = "custom"
KG_TOOL_KEYS = ("kg_query",)

_TENANT_REQUIRED = "tenant_required"

_ACTIONS = ("entity_search", "neighbors", "paths", "stats")


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk（项目统一模式）。"""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return ToolChunk(content=[TextBlock(type="text", text=text)])


class KgQueryTool(ToolBase):
    """知识图谱查询（实体检索 / 邻接 / 路径 / 统计）。"""

    is_concurrency_safe: bool = True
    is_read_only: bool = True

    name: str = "kg_query"
    description: str = (
        "查询知识图谱知识库：按关键词语义检索实体（entity_search）、查看实体邻接关系"
        "（neighbors，1~3 跳）、查询两实体之间的路径（paths）、查看图谱统计（stats）。"
        "只读，不修改数据。结果按当前登录用户所属租户隔离。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(_ACTIONS),
                       "description": "子命令"},
            "knowledge_id": {"type": "integer",
                             "description": "图谱知识库 ID（type=4）"},
            "keyword": {"type": "string",
                        "description": "entity_search 的关键词"},
            "entity_id": {"type": "integer",
                          "description": "neighbors 的目标实体 ID"},
            "from_entity_id": {"type": "integer",
                               "description": "paths 的起点实体 ID"},
            "to_entity_id": {"type": "integer",
                             "description": "paths 的终点实体 ID"},
            "depth": {"type": "integer",
                      "description": "neighbors 的跳数（1~3），默认 1"},
            "limit": {"type": "integer",
                      "description": "返回条数上限，默认 20"},
        },
        "required": ["action", "knowledge_id"],
    }

    def __init__(
        self,
        session_factory: Optional[Any] = None,
        tenant_resolver: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._session_factory = session_factory
        # 租户解析的可注入点：默认经 SysUser 查（生产）；测试可注入固定租户，
        # 避免依赖系统表（系统表不在业务库的测试 schema 内）。
        self._tenant_resolver = tenant_resolver

    def _session(self):
        if self._session_factory is not None:
            return self._session_factory()
        from app.db.database import SessionLocal

        return SessionLocal()

    def _resolve_tenant_id(self, db) -> Optional[int]:
        """ToolUserContext.user_id -> SysUser.tenant_id（上下文不含租户字段）。"""
        if self._tenant_resolver is not None:
            return self._tenant_resolver(db)

        from app.ai.tool_manager.tool_context import get_tool_user
        from app.models.sys.sys_user import SysUser

        ctx = get_tool_user()
        if ctx is None or not ctx.user_id:
            return None
        row = db.query(SysUser.tenant_id).filter(SysUser.user_id == ctx.user_id).first()
        return row[0] if row else None


    async def check_permissions(
        self, tool_input: dict, context: PermissionContext,
    ) -> PermissionDecision:
        """只读工具默认放行。"""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Read-only knowledge graph tool.",
        )

    async def call(
        self,
        action: str,
        knowledge_id: int,
        keyword: Optional[str] = None,
        entity_id: Optional[int] = None,
        from_entity_id: Optional[int] = None,
        to_entity_id: Optional[int] = None,
        depth: int = 1,
        limit: int = 20,
    ) -> ToolChunk:
        from app.services.kb.kg.kg_service import KgService

        if action not in _ACTIONS:
            return _text_chunk({"error": f"未知子命令: {action!r}",
                                "allowed": list(_ACTIONS)})

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})

            svc = KgService(db, tenant_id=tenant_id, knowledge_id=knowledge_id)

            if action == "stats":
                return _text_chunk(svc.stats())

            if action == "entity_search":
                if not keyword:
                    return _text_chunk({"error": "entity_search 需要 keyword"})
                entities = svc.list_entities(keyword=keyword, limit=limit)
                return _text_chunk(
                    {
                        "items": [
                            {
                                "id": e.id, "name": e.name,
                                "type": e.type_code or "", "status": e.status,
                            }
                            for e in entities
                        ],
                        "total": len(entities),
                    }
                )

            if action == "neighbors":
                if entity_id is None:
                    return _text_chunk({"error": "neighbors 需要 entity_id"})
                return _text_chunk(svc.neighbors(entity_id, depth=depth, limit=limit))

            # paths
            if from_entity_id is None or to_entity_id is None:
                return _text_chunk(
                    {"error": "paths 需要 from_entity_id 与 to_entity_id"}
                )
            paths = svc.paths(from_entity_id, to_entity_id, max_depth=2, limit=limit)
            return _text_chunk({"paths": paths})
        except Exception as exc:  # noqa: BLE001 - 工具异常转结构化错误，不抛出
            db.rollback()
            logger.warning("[kg_query] 执行失败: %s", exc)
            return _text_chunk({"error": f"{type(exc).__name__}: {exc}"})
        finally:
            db.close()


def build_kg_tool_definitions() -> list:
    """构造 kg_query 的 AiToolDefinition 内置定义（供启动 seed + 工具库）。"""
    from app.models.ai.ai_tool_definition import AiToolDefinition

    return [
        AiToolDefinition(
            tool_key="kg_query",
            display_name="知识图谱查询",
            category="知识管理",
            tool_type=KG_TOOL_TYPE,
            class_name="app.ai.tools.kg_tools.KgQueryTool",
            method_name="call",
            description=KgQueryTool.description,
            config_schema=None,
            config_value=None,
            input_schema=KgQueryTool.input_schema,
            output_schema=None,
            status="enabled",
            is_system=True,
            sort=1250,
        )
    ]
