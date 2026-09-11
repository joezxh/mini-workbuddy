"""DataOps Agent 工具（P2 Task 14）—— 把元数据/查询/写审批/标准绑定/关系推断
暴露给 Agent（AgentScope ToolBase 协议）。

消费的服务（按 tenant_id 隔离）：
* ``MetaScanService``            —— 元数据扫描
* ``ReadonlyQueryService``       —— 只读 SQL 执行
* ``DataWriteRequestService``    —— 写操作申请单
* ``StandardBindingService``     —— 字段↔标准绑定
* ``RelationInferenceService``   —— 三方投票关系推断

租户链路
--------
与 ``ontology_tools`` 一致：``call()`` 内自建会话，经 ``get_tool_user()`` 解析
``tenant_id``；取不到租户的调用返回 ``tenant_required`` 错误，**绝不落到 NULL 分区**。
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
    "DataopsScanTool",
    "DataopsQueryTool",
    "DataopsWriteRequestTool",
    "DataopsBindTool",
    "DataopsInferRelationsTool",
    "DATAOPS_TOOL_KEYS",
    "DATAOPS_TOOL_TYPE",
    "build_dataops_tool_definitions",
]

DATAOPS_TOOL_TYPE = "custom"
DATAOPS_TOOL_KEYS = (
    "dataops_scan",
    "dataops_query",
    "dataops_write_request",
    "dataops_bind",
    "dataops_infer_relations",
)

_TENANT_REQUIRED = "tenant_required"


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk（项目统一模式）。"""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return ToolChunk(content=[TextBlock(type="text", text=text)])


class DataopsToolBase(ToolBase):
    """DataOps 工具公共基类：会话工厂注入 + 租户解析。"""

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
        """只读工具默认放行；写类子类覆盖为要求确认。"""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Read-only DataOps tool.",
        )


class DataopsScanTool(DataopsToolBase):
    """触发数据源元数据扫描（建连取表/列/画像，幂等覆盖）。"""

    name: str = "dataops_scan"
    description: str = (
        "对指定数据源执行元数据扫描：连接数据库 → 读取表/列/类型/注释 → 可选列画像，"
        "幂等写入元数据目录（重扫覆盖）。返回扫描任务状态与统计。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "source_id": {"type": "integer", "description": "数据源 ID"},
            "database": {"type": "string", "description": "目标库/schema"},
            "with_profile": {"type": "boolean", "description": "是否采集列画像，默认 false"},
        },
        "required": ["source_id", "database"],
    }
    is_read_only: bool = False
    is_concurrency_safe: bool = False

    async def check_permissions(self, tool_input: dict, context: PermissionContext) -> PermissionDecision:
        return PermissionDecision(behavior=PermissionBehavior.ASK, message="元数据扫描会写入元数据目录，需要确认。")

    async def call(self, source_id: int, database: str, with_profile: bool = False) -> ToolChunk:
        from app.services.dataops.scan_service import MetaScanService

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})
            job = MetaScanService(db, tenant_id).start_scan(
                source_id, database, with_profile=with_profile,
                creator_id=None,
            )
            db.commit()
            return _text_chunk({
                "job_id": job.id, "status": job.status,
                "tables": job.tables_json, "stats": job.stats_json,
                "error_detail": job.error_detail,
            })
        except KeyError:
            db.rollback()
            return _text_chunk({"error": f"数据源不存在: {source_id}"})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("dataops_scan failed")
            return _text_chunk({"error": f"扫描失败: {exc}"})
        finally:
            db.close()


class DataopsQueryTool(DataopsToolBase):
    """对数据源执行只读 SQL（经 SqlGuard 强制只读 + 行数截断）。"""

    name: str = "dataops_query"
    description: str = (
        "对指定数据源执行**只读** SQL 查询（仅允许单条 SELECT/CTE/UNION/EXPLAIN 查询，"
        "自动限行并标记截断）。只读，不修改数据。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "source_id": {"type": "integer", "description": "数据源 ID"},
            "sql": {"type": "string", "description": "只读查询 SQL"},
            "limit": {"type": "integer", "description": "返回行数上限（1~5000），默认 100"},
        },
        "required": ["source_id", "sql"],
    }
    is_read_only: bool = True
    is_concurrency_safe: bool = True

    async def call(self, source_id: int, sql: str, limit: int = 100) -> ToolChunk:
        from app.services.dataops.query_service import ReadonlyQueryService

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})
            result = ReadonlyQueryService(db, tenant_id).run(source_id, sql, limit)
            return _text_chunk(result)
        except ValueError as exc:
            db.rollback()
            return _text_chunk({"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("dataops_query failed")
            return _text_chunk({"error": f"查询失败: {exc}"})
        finally:
            db.close()


class DataopsWriteRequestTool(DataopsToolBase):
    """提交数据写操作申请单（需审批 + 一次性令牌执行）。"""

    name: str = "dataops_write_request"
    description: str = (
        "提交数据写操作（INSERT/UPDATE/DELETE/DDL）申请单。申请经 SqlGuard 校验必须为写语句，"
        "进入审批流；批准后由执行端凭一次性令牌执行。仅创建申请，不直接执行。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "source_id": {"type": "integer", "description": "数据源 ID"},
            "sql": {"type": "string", "description": "写操作 SQL"},
            "database": {"type": "string", "description": "目标库（可选）"},
        },
        "required": ["source_id", "sql"],
    }
    is_read_only: bool = False
    is_concurrency_safe: bool = False

    async def check_permissions(self, tool_input: dict, context: PermissionContext) -> PermissionDecision:
        return PermissionDecision(behavior=PermissionBehavior.ASK, message="写操作申请会进入审批流，需要确认。")

    async def call(self, source_id: int, sql: str, database: Optional[str] = None) -> ToolChunk:
        from app.services.dataops.write_request_service import DataWriteRequestService

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})
            req = DataWriteRequestService(db, tenant_id).create_request(
                source_id, sql, database,
            )
            db.commit()
            return _text_chunk({
                "request_id": req.id, "status": req.status,
                "statement_type": req.statement_type,
            })
        except KeyError:
            db.rollback()
            return _text_chunk({"error": f"数据源不存在: {source_id}"})
        except ValueError as exc:
            db.rollback()
            return _text_chunk({"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("dataops_write_request failed")
            return _text_chunk({"error": f"申请失败: {exc}"})
        finally:
            db.close()


class DataopsBindTool(DataopsToolBase):
    """把数据源字段与标准项绑定（规则标注 + 标准匹配，进入评审队列）。"""

    name: str = "dataops_bind"
    description: str = (
        "对数据源做字段↔标准绑定：先用规则引擎给每列标注语义类型/PII 等级，"
        "再匹配内置标准项，落入评审队列（conf≥0.85 自动接受，0.65~0.85 进入人工评审）。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "source_id": {"type": "integer", "description": "数据源 ID"},
            "database": {"type": "string", "description": "限定库（可选，默认全部）"},
        },
        "required": ["source_id"],
    }
    is_read_only: bool = False
    is_concurrency_safe: bool = False

    async def check_permissions(self, tool_input: dict, context: PermissionContext) -> PermissionDecision:
        return PermissionDecision(behavior=PermissionBehavior.ASK, message="标准绑定会写入标注结果，需要确认。")

    async def call(self, source_id: int, database: Optional[str] = None) -> ToolChunk:
        from app.services.dataops.standard_binding_service import StandardBindingService

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})
            rep = StandardBindingService(db, tenant_id).bind_source(source_id, database)
            db.commit()
            return _text_chunk({
                "tables": rep.tables, "columns": rep.columns,
                "annotated": rep.annotated, "bound": rep.bound,
                "updated": rep.updated, "skipped_human": rep.skipped_human,
            })
        except KeyError:
            db.rollback()
            return _text_chunk({"error": f"数据源不存在: {source_id}"})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("dataops_bind failed")
            return _text_chunk({"error": f"绑定失败: {exc}"})
        finally:
            db.close()


class DataopsInferRelationsTool(DataopsToolBase):
    """推断数据源表间关系（三方投票：键命名法 / 同名属性法 / 采样重叠率法）。"""

    name: str = "dataops_infer_relations"
    description: str = (
        "用三方投票推断表间关系：主键/外键命名法、同名属性法、采样重叠率法，"
        "取各票最大置信度；conf≥0.65 入库进入评审。ware_overlap 需要实时连接（默认关闭）。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "source_id": {"type": "integer", "description": "数据源 ID"},
            "database": {"type": "string", "description": "限定库（可选）"},
            "with_overlap": {"type": "boolean", "description": "是否启用采样重叠率投票（需实时连接），默认 false"},
        },
        "required": ["source_id"],
    }
    is_read_only: bool = False
    is_concurrency_safe: bool = False

    async def check_permissions(self, tool_input: dict, context: PermissionContext) -> PermissionDecision:
        return PermissionDecision(behavior=PermissionBehavior.ASK, message="关系推断会写入候选关系，需要确认。")

    async def call(
        self, source_id: int, database: Optional[str] = None, with_overlap: bool = False,
    ) -> ToolChunk:
        from app.services.dataops.relation_inference_service import RelationInferenceService

        db = self._session()
        try:
            tenant_id = self._resolve_tenant_id(db)
            if tenant_id is None:
                return _text_chunk({"error": _TENANT_REQUIRED})
            rep = RelationInferenceService(db, tenant_id).infer(
                source_id, database, with_overlap=with_overlap,
            )
            db.commit()
            return _text_chunk({
                "scanned_pairs": rep.scanned_pairs,
                "relations": rep.relations,
                "details": rep.details,
            })
        except KeyError:
            db.rollback()
            return _text_chunk({"error": f"数据源不存在: {source_id}"})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("dataops_infer_relations failed")
            return _text_chunk({"error": f"关系推断失败: {exc}"})
        finally:
            db.close()


def build_dataops_tool_definitions() -> list:
    """构造五个 DataOps Agent 工具的 ``AiToolDefinition`` 内置定义（供启动 seed + 工具库）。"""
    from app.models.ai.ai_tool_definition import AiToolDefinition

    display_names = {
        "dataops_scan": "元数据扫描",
        "dataops_query": "只读查询",
        "dataops_write_request": "写操作申请",
        "dataops_bind": "标准绑定",
        "dataops_infer_relations": "关系推断",
    }
    classes = {
        "dataops_scan": DataopsScanTool,
        "dataops_query": DataopsQueryTool,
        "dataops_write_request": DataopsWriteRequestTool,
        "dataops_bind": DataopsBindTool,
        "dataops_infer_relations": DataopsInferRelationsTool,
    }
    defs: list = []
    for key, cls in classes.items():
        defs.append(
            AiToolDefinition(
                tool_key=key,
                display_name=display_names[key],
                category="数据治理",
                tool_type=DATAOPS_TOOL_TYPE,
                class_name=f"app.ai.tools.dataops_tools.{cls.__name__}",
                method_name="call",
                description=cls.description,
                config_schema=None,
                config_value=None,
                input_schema=cls.input_schema,
                output_schema=None,
                status="enabled",
                is_system=True,
                sort=1200,
            )
        )
    return defs
