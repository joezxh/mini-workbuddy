"""Semantica Agent 工具：semantic_query / semantic_build / semantic_search。

租户链路与 ``ontology_tools`` 一致：经 ``tool_context.get_tool_user()`` 取当前用户，
再补查 ``SysUser.tenant_id``（``ToolUserContext`` 不含租户字段）。取不到租户的调用
返回 ``tenant_required`` 错误，**绝不落到 NULL 分区共享语义数据**。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolBase, ToolChunk

from app.models.sys.sys_user import SysUser
from app.services.semantica import (
    SemanticaClient,
    SemanticaPipelineService,
    SemanticaUnavailable,
    SemanticRetriever,
    TenantScope,
)

logger = logging.getLogger(__name__)

SEMANTIC_TOOL_TYPE = "custom"
SEMANTIC_TOOL_KEYS = ("semantic_query", "semantic_build", "semantic_search")
_TENANT_REQUIRED = "tenant_required"


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk（项目统一模式）。"""
    text = payload if isinstance(payload, str) else json.dumps(
        payload, ensure_ascii=False, default=str
    )
    return ToolChunk(content=[TextBlock(type="text", text=text)])


class SemanticToolBase(ToolBase):
    """Semantica 工具公共基类：会话工厂注入 + 租户解析。"""

    is_concurrency_safe = False
    is_read_only = True

    def __init__(self, session_factory: Optional[Any] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # 生产为 None → call 内延迟取 SessionLocal；测试注入受控工厂
        self.session_factory = session_factory

    def _tenant_id(self, tool_context: Any) -> int:
        from app.db.session import SessionLocal

        user = tool_context.get_tool_user()
        if user is None or user.get("id") is None:
            raise PermissionError(_TENANT_REQUIRED)
        factory = self.session_factory or SessionLocal
        with factory() as db:
            su = db.get(SysUser, user["id"])
            tid = getattr(su, "tenant_id", None)
        if tid is None:
            raise PermissionError(_TENANT_REQUIRED)
        return tid


class SemanticQueryTool(SemanticToolBase):
    """查询语义实体抽取与图谱构建摘要（只读）。"""

    def call(self, text: str, ontology_code: str = "default") -> ToolChunk:
        try:
            tid = self._tenant_id(self.tool_context)
            client = SemanticaClient(scope=TenantScope(tid, ontology_code))
            entities = client.extract_entities(text)
            triplets = client.extract_triplets(text, entities=entities)
            return _text_chunk(
                {"entity_count": len(entities), "triplet_count": len(triplets)}
            )
        except (SemanticaUnavailable, PermissionError) as exc:
            return _text_chunk({"error": str(exc)})


class SemanticBuildTool(SemanticToolBase):
    """基于文本构建语义图谱（抽取→冲突→去重→建图→向量）。"""

    is_read_only = False

    def call(self, text: str, ontology_code: str = "default") -> ToolChunk:
        try:
            tid = self._tenant_id(self.tool_context)
            svc = SemanticaPipelineService(
                db=None, scope=TenantScope(tid, ontology_code)
            )
            report = svc.run(text)
            return _text_chunk({"ok": report.ok, "summary": report.summary})
        except (SemanticaUnavailable, PermissionError) as exc:
            return _text_chunk({"error": str(exc)})


class SemanticSearchTool(SemanticToolBase):
    """基于查询向量检索语义实体/关系（只读）。"""

    def call(
        self,
        query_vector: List[float],
        top_k: int = 10,
        ontology_code: str = "default",
        concept_uris: Optional[List[str]] = None,
    ) -> ToolChunk:
        try:
            tid = self._tenant_id(self.tool_context)
            retriever = SemanticRetriever(scope=TenantScope(tid, ontology_code))
            results = retriever.search_by_vector(
                query_vector, top_k=top_k, concept_uris=concept_uris
            )
            return _text_chunk({"count": len(results), "results": results[:top_k]})
        except (SemanticaUnavailable, PermissionError) as exc:
            return _text_chunk({"error": str(exc)})


def build_semantic_tool_definitions() -> List["Any"]:
    """构造 3 个 Semantica Agent 工具的持久化定义（供 seed 注册）。"""
    from app.models.ai.ai_tool_definition import AiToolDefinition

    definitions = []
    for key, desc in [
        ("semantic_query", "查询语义实体抽取与图谱构建摘要"),
        ("semantic_build", "基于文本构建语义图谱（抽取/冲突/去重/建图/向量）"),
        ("semantic_search", "基于查询向量检索语义实体/关系"),
    ]:
        definitions.append(
            AiToolDefinition(
                tool_key=key,
                name=key,
                tool_type=SEMANTIC_TOOL_TYPE,
                description=desc,
                is_system=True,
            )
        )
    return definitions
