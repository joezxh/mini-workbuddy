"""本体 Agent 工具（Task 9）—— ontology_query / ontology_answer_cq / ontology_suggest。

对应 spec §6 的 P4.2 Tool 约定：
* ``ontology_query``    查类层级 / 属性 / 关系 / 统计 / 一致性报告
* ``ontology_answer_cq`` 用 CQ（能力问题）校验本体覆盖度
* ``ontology_suggest``  基于 P2 元数据生成对象类型 / 属性 / 关系候选（写操作）

租户链路
--------
AgentScope 的 ``ToolBase.call()`` 不携带用户信息；本文件经
``tool_context.get_tool_user()`` 取当前用户，再补查 ``SysUser.tenant_id``
（``ToolUserContext`` 不含租户字段）。取不到租户的调用按 IM-07 语义返回
``tenant_required`` 错误，**绝不落到 NULL 分区共享本体**。

会话
----
与项目其它工具一致，``call()`` 内自建会话（``SessionLocal``）；
``session_factory`` 构造参数仅供测试注入，生产侧不传。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agentscope.message import TextBlock
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)
from agentscope.tool import ToolBase, ToolChunk

logger = logging.getLogger(__name__)

__all__ = [
    "OntologyQueryTool",
    "OntologyAnswerCqTool",
    "OntologySuggestTool",
    "ONTOLOGY_TOOL_KEYS",
    "ONTOLOGY_TOOL_TYPE",
    "build_ontology_tool_definitions",
]

ONTOLOGY_TOOL_TYPE = "custom"

#: 三个本体 Agent 工具的 tool_key（与类名一一对应；定义在文件末尾）。
ONTOLOGY_TOOL_KEYS = ("ontology_query", "ontology_answer_cq", "ontology_suggest")

_TENANT_REQUIRED = "tenant_required"


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk（项目统一模式）。"""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return ToolChunk(content=[TextBlock(type="text", text=text)])


class OntologyToolBase(ToolBase):
    """本体工具公共基类：会话工厂注入 + 租户解析。"""

    is_concurrency_safe: bool = False
    is_read_only: bool = True

    def __init__(self, session_factory: Optional[Any] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # 生产为 None → call 内延迟取 SessionLocal；测试注入受控工厂
        self._session_factory = session_factory

    def _session(self):
        if self._session_factory is not None:
            return self._session_factory()
        from app.db.database import SessionLocal

        return SessionLocal()

    def _resolve_tenant_id(self, db: Any) -> Optional[int]:
        """ToolUserContext.user_id → SysUser.tenant_id（上下文不含租户字段）。"""
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
        """只读工具默认放行；写类子类（ontology_suggest）覆盖为要求确认。"""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Read-only ontology tool.",
        )


class OntologyQueryTool(OntologyToolBase):
    """查询本体：类层级 / 类清单 / 属性 / 关系 / 统计 / 一致性报告（只读）。"""

    name: str = "ontology_query"
    description: str = (
        "查询企业本体的结构化信息：类层级树（hierarchy）、OWL 类清单（classes）、"
        "对象类型属性（properties）、关系类型（link_types）、统计（stats）与"
        "一致性报告（consistency：悬空父类/循环继承/URI 冲突）。只读。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["hierarchy", "classes", "properties", "link_types", "stats", "consistency"],
                "description": "查询类型",
            },
            "object_type_code": {
                "type": "string",
                "description": "对象类型编码（action=properties 时必填）",
            },
        },
        "required": ["action"],
    }

    async def call(
        self,
        action: str,
        object_type_code: Optional[str] = None,
    ) -> ToolChunk:
        from app.ai.knowledge.owl_engine import WikiOwlEngine
        from app.services.ontology.modeling_service import ModelingService
        from app.services.ontology.ontology_repository import OntologyRepository

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})
            svc = ModelingService(db, tenant_id)
            engine = WikiOwlEngine.from_store(OntologyRepository(db, tenant_id))

            if action == "hierarchy":
                payload = [n.to_dict() for n in engine.get_hierarchy()]
            elif action == "classes":
                payload = [c.to_dict() for c in engine.list_classes()]
            elif action == "properties":
                if not object_type_code:
                    return _text_chunk({"error": "action=properties 需要 object_type_code"})
                payload = [
                    {
                        "code": p.code,
                        "name": p.name,
                        "data_type": p.data_type,
                        "required": p.required,
                        "status": p.status,
                        "confidence": p.confidence,
                    }
                    for p in svc.list_properties(object_type_code)
                ]
            elif action == "link_types":
                payload = [
                    {
                        "code": lt.code,
                        "name": lt.name,
                        "source_type": lt.source_type_id,
                        "target_type": lt.target_type_id,
                        "cardinality": lt.cardinality,
                        "status": lt.status,
                    }
                    for lt in svc.list_link_types()
                ]
            elif action == "stats":
                payload = {**engine.stats(), "cq_coverage": svc.cq_coverage()}
            elif action == "consistency":
                payload = {
                    "issues": [vars(i) for i in svc.check_consistency().issues],
                }
            else:
                return _text_chunk({"error": f"未知 action: {action}"})
            return _text_chunk(payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ontology_query failed")
            return _text_chunk({"error": f"本体查询失败: {exc}"})
        finally:
            db.close()


class OntologyAnswerCqTool(OntologyToolBase):
    """用能力问题（CQ）校验本体覆盖度（只读）。"""

    name: str = "ontology_answer_cq"
    description: str = (
        "列出本体的能力问题（CQ）及其覆盖状态，返回覆盖率与未覆盖的问题清单，"
        "用于评估本体是否足以回答目标业务问题。只读。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "按关键词过滤 CQ（可选，模糊匹配）",
            },
            "include_archived": {
                "type": "boolean",
                "description": "是否包含已归档的 CQ，默认 false",
            },
        },
    }

    async def call(
        self,
        question: Optional[str] = None,
        include_archived: bool = False,
    ) -> ToolChunk:
        from app.services.ontology.modeling_service import ModelingService

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})
            svc = ModelingService(db, tenant_id)

            cqs = svc.list_cqs(status=None if include_archived else "active")
            if question:
                kw = question.strip().lower()
                cqs = [c for c in cqs if kw in (c.question or "").lower()]

            covered = [c for c in cqs if c.linked_object_types]
            return _text_chunk({
                "cq_coverage": svc.cq_coverage(),
                "total": len(cqs),
                "covered": len(covered),
                "uncovered": [c.question for c in cqs if not c.linked_object_types],
                "items": [
                    {
                        "question": c.question,
                        "status": c.status,
                        "covered": bool(c.linked_object_types),
                        "linked_object_types": list(c.linked_object_types or []),
                    }
                    for c in cqs
                ],
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("ontology_answer_cq failed")
            return _text_chunk({"error": f"CQ 查询失败: {exc}"})
        finally:
            db.close()


class OntologySuggestTool(OntologyToolBase):
    """基于 P2 元数据生成本体候选（写操作：落 suggested/accepted 候选）。"""

    name: str = "ontology_suggest"
    description: str = (
        "把 P2 元数据（物理表/列/高重叠列对）转换为本体候选：对象类型、属性、"
        "关系类型，进入评审队列（conf≥0.85 自动接受，0.65~0.85 进入人工评审）。"
        "幂等：重复提交同一批元数据不会产生重复候选。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "tables": {
                "type": "array",
                "description": "P2 元数据表列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string"},
                        "database": {"type": "string"},
                        "table_name": {"type": "string"},
                        "comment": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["source_id", "database", "table_name"],
                },
            },
            "columns": {
                "type": "array",
                "description": "P2 元数据列列表（含 rule_engine 置信度）",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string"},
                        "database": {"type": "string"},
                        "table_name": {"type": "string"},
                        "column_name": {"type": "string"},
                        "data_type": {"type": "string"},
                        "comment": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["source_id", "database", "table_name", "column_name"],
                },
            },
            "column_pairs": {
                "type": "array",
                "description": "高重叠列对（relation_inference 产出）",
                "items": {
                    "type": "object",
                    "properties": {
                        "left_table": {"type": "string"},
                        "left_column": {"type": "string"},
                        "right_table": {"type": "string"},
                        "right_column": {"type": "string"},
                        "overlap_ratio": {"type": "number"},
                    },
                    "required": ["left_table", "left_column", "right_table", "right_column", "overlap_ratio"],
                },
            },
        },
    }
    is_read_only: bool = False

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext,
    ) -> PermissionDecision:
        """写操作：默认要求用户确认（与项目内写类工具的策略一致）。"""
        return PermissionDecision(
            behavior=PermissionBehavior.ASK,
            message="ontology_suggest 会写入本体候选，需要用户确认。",
        )

    async def call(
        self,
        tables: Optional[List[Dict[str, Any]]] = None,
        columns: Optional[List[Dict[str, Any]]] = None,
        column_pairs: Optional[List[Dict[str, Any]]] = None,
    ) -> ToolChunk:
        from app.services.ontology.modeling_service import (
            ColumnPairOverlap,
            MetaColumnRef,
            MetaTableRef,
            ModelingService,
        )

        def _build(cls: type, items: Optional[List[Dict[str, Any]]]) -> List[Any]:
            """宽松构造：忽略未知字段，避免 Agent 多传字段导致失败。"""
            known = {"source_id", "database", "table_name", "comment", "confidence",
                     "column_name", "data_type", "left_table", "left_column",
                     "right_table", "right_column", "overlap_ratio"}
            out = []
            for item in items or []:
                filtered = {k: v for k, v in item.items() if k in known}
                out.append(cls(**filtered))
            return out

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})
            svc = ModelingService(db, tenant_id)
            report = svc.generate_candidates(
                tables=_build(MetaTableRef, tables),
                columns=_build(MetaColumnRef, columns),
                column_pairs=_build(ColumnPairOverlap, column_pairs),
            )
            db.commit()
            return _text_chunk({
                "created": report.created,
                "skipped": report.skipped,
            })
        except ValueError as exc:
            db.rollback()
            return _text_chunk({"error": f"候选生成失败（输入校验）: {exc}"})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("ontology_suggest failed")
            return _text_chunk({"error": f"候选生成失败: {exc}"})
        finally:
            db.close()


def build_ontology_tool_definitions() -> list:
    """构造三个本体 Agent 工具的 ``AiToolDefinition`` 内置定义（Task 9 收尾）。

    用于启动 seed + 管理后台「工具库」，标记 ``is_system=True``（不可删除）。
    与 ``web_search_tool.build_web_search_definition`` 同模式。
    """
    from app.models.ai.ai_tool_definition import AiToolDefinition

    display_names = {
        "ontology_query": "本体查询",
        "ontology_answer_cq": "本体能力问题校验",
        "ontology_suggest": "本体候选生成",
    }
    classes = {
        "ontology_query": OntologyQueryTool,
        "ontology_answer_cq": OntologyAnswerCqTool,
        "ontology_suggest": OntologySuggestTool,
    }
    defs: list = []
    for key, cls in classes.items():
        defs.append(
            AiToolDefinition(
                tool_key=key,
                display_name=display_names[key],
                category="本体治理",
                tool_type=ONTOLOGY_TOOL_TYPE,
                class_name=f"app.ai.tools.ontology_tools.{cls.__name__}",
                method_name="call",
                description=cls.description,
                config_schema=None,
                config_value=None,
                input_schema=cls.input_schema,
                output_schema=None,
                status="enabled",
                is_system=True,
                sort=1100,
            )
        )
    return defs
