"""SqlBotTemplateTool —— 唯一的通用 SQLBot 业务 Tool 实现。

所有业务线的自定义查询 Tool 共用本类，差异全部由
``tool_definition.config_value`` 中的声明式配置驱动，业务人员**无需写代码**。

七步执行流水线::

    1. 参数校验          template_renderer.validate_inputs
    2. 行级权限裁决      row_scope.resolve_scope
    3. 模板渲染          template_renderer.render_question
    4. 约束组装          template_renderer.build_constraint_text
    5. SQLBot 取数       sqlbot_client.query
    6. 兜底行过滤        row_scope.filter_rows        <- 真实安全边界
    7. 列级脱敏 + 格式化 masking.apply_masking / result_formatter.format_results

异常约定：**不抛异常**，一律返回 ``{"error": ...}`` 结构，
避免单个工具失败中断整个 Agent 会话（与既有 ``SqlBotQuery`` 保持一致）。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from agentscope.message import TextBlock
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)
from agentscope.tool import ToolBase, ToolChunk

from app.ai.tool_manager.masking import apply_masking
from app.ai.tool_manager.result_formatter import format_results
from app.ai.tool_manager.row_scope import filter_rows, resolve_scope
from app.ai.tool_manager.sqlbot_tool_config import SqlBotToolConfig
from app.ai.tool_manager.template_renderer import (
    ParamValidationError,
    build_constraint_text,
    render_question,
    validate_inputs,
)
from app.ai.tool_manager.tool_context import ToolUserContext, get_tool_user

logger = logging.getLogger(__name__)

__all__ = ["SqlBotTemplateTool"]

AUDIT_MODULE = "ai:sqlbot_tool"


def _text_chunk(payload: Dict[str, Any]) -> ToolChunk:
    return ToolChunk(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, default=str),
            )
        ]
    )


class SqlBotTemplateTool(ToolBase):
    """配置驱动的 SQLBot 业务数据查询工具。"""

    # 类级默认值；实例化后由 config 覆盖
    name: str = "sqlbot_template_tool"
    description: str = "配置化 SQLBot 业务数据查询工具"
    input_schema: dict = {"type": "object", "properties": {}}
    is_concurrency_safe: bool = True
    is_read_only: bool = True

    def __init__(
        self,
        config: Any = None,
        context: Any = None,
        tool_key: Optional[str] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        super().__init__()

        self._config: Optional[SqlBotToolConfig] = self._normalize_config(config)
        self._context: Optional[ToolUserContext] = self._normalize_context(context)
        self._config_error: Optional[str] = None

        if config is not None and self._config is None:
            self._config_error = "config_value 解析失败，请检查工具配置"

        if tool_key:
            self.name = tool_key
        if description:
            self.description = description
        elif display_name:
            self.description = display_name

        if self._config is not None:
            self.input_schema = self._config.build_input_schema()

        from app.middleware.sqlbot_client import sqlbot_client

        self._client = sqlbot_client

    # ------------------------------------------------------------------
    # 构造辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_config(config: Any) -> Optional[SqlBotToolConfig]:
        if config is None:
            return None
        if isinstance(config, SqlBotToolConfig):
            return config
        if isinstance(config, dict):
            try:
                return SqlBotToolConfig.model_validate(config)
            except Exception as exc:  # noqa: BLE001
                logger.warning("SqlBotTemplateTool 配置解析失败: %s", exc)
                return None
        logger.warning("SqlBotTemplateTool 收到不支持的配置类型: %s", type(config))
        return None

    @staticmethod
    def _normalize_context(context: Any) -> Optional[ToolUserContext]:
        if context is None:
            return None
        if isinstance(context, ToolUserContext):
            return context
        if isinstance(context, dict):
            try:
                return ToolUserContext.from_dict(context)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ToolUserContext 解析失败: %s", exc)
        return None

    def _current_user(self) -> Optional[ToolUserContext]:
        """优先取显式注入的上下文，其次取 ContextVar。"""
        return self._context or get_tool_user()

    # ------------------------------------------------------------------
    # 权限
    # ------------------------------------------------------------------
    async def check_permissions(
        self, tool_input: dict, context: PermissionContext
    ) -> PermissionDecision:
        allowed, message = self._check_tool_permission()
        if allowed:
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW, message=message
            )
        return PermissionDecision(behavior=PermissionBehavior.DENY, message=message)

    def _check_tool_permission(self) -> tuple[bool, str]:
        """Tool 级权限校验：权限码 + 角色黑白名单。"""
        if self._config is None:
            return False, self._config_error or "工具未配置，拒绝执行"

        perm = self._config.permission
        user = self._current_user()

        if user is None:
            if perm.allow_anonymous:
                return True, "配置允许匿名执行"
            return False, "无法获取当前用户上下文，已按最严格策略拒绝执行"

        if perm.deny_roles and user.has_any_role(perm.deny_roles):
            return False, "当前用户角色被显式禁止调用该工具"

        if user.is_admin:
            return True, "管理员放行"

        if perm.allow_roles and not user.has_any_role(perm.allow_roles):
            return False, "当前用户不在该工具的角色白名单内"

        if perm.permission_code and not user.has_permission(perm.permission_code):
            return False, f"缺少权限码 {perm.permission_code}"

        return True, "只读数据查询，权限校验通过"

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------
    async def call(self, **kwargs: Any) -> ToolChunk:
        started = time.perf_counter()
        tool_key = self.name
        config = self._config

        if config is None:
            return _text_chunk(
                {"error": self._config_error or "工具未配置 config_value，无法执行"}
            )

        user = self._current_user()

        # --- Tool 级权限 ---
        allowed, message = self._check_tool_permission()
        if not allowed:
            logger.warning("SQLBot 工具 %s 权限拒绝: %s", tool_key, message)
            self._audit(tool_key, user, {}, 0, 0, message, success=False)
            return _text_chunk({"error": f"权限不足: {message}"})

        # --- 1. 参数校验 ---
        try:
            values = validate_inputs(config, kwargs)
        except ParamValidationError as exc:
            return _text_chunk({"error": "参数校验失败", "details": exc.errors})

        # --- 2. 行级权限裁决 ---
        decision = resolve_scope(
            config.row_scope, user, allow_anonymous=config.permission.allow_anonymous
        )
        if decision.denied:
            logger.warning("SQLBot 工具 %s 行级权限拒绝: %s", tool_key, decision.reason)
            self._audit(tool_key, user, values, 0, 0, decision.reason, success=False)
            return _text_chunk({"error": decision.reason, "records": [], "total": 0})

        # --- 3/4. 模板渲染 + 约束组装 ---
        max_rows = config.result_format.max_rows
        try:
            question = render_question(config, values, decision.scope_text)
            constraint = build_constraint_text(config, decision.scope_text, max_rows)
            full_question = f"{question}{constraint}" if constraint else question
        except Exception as exc:  # noqa: BLE001
            logger.warning("SQLBot 工具 %s 模板渲染失败: %s", tool_key, exc)
            return _text_chunk({"error": f"提问模板渲染失败: {exc}"})

        # --- 5. SQLBot 取数 ---
        try:
            records: List[Dict[str, Any]] = await self._client.query(
                question=full_question,
                datasource_id=config.datasource_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("SQLBot 工具 %s 查询失败: %s", tool_key, exc)
            self._audit(tool_key, user, values, 0, 0, str(exc), success=False)
            return _text_chunk(
                {"error": f"数据查询失败: {exc}", "question": full_question}
            )

        records = [r for r in (records or []) if isinstance(r, dict)]
        fetched = len(records)

        # --- 6. 兜底行过滤（真实安全边界）---
        records, filtered_count, field_missing = filter_rows(
            records, decision, config.row_scope
        )

        # --- 7. 列级脱敏 + 结果格式化 ---
        records, masked_fields = apply_masking(records, config.masking, user)
        payload = format_results(records, config.result_format)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        payload.update(
            {
                "toolKey": tool_key,
                "question": full_question,
                "datasourceId": config.datasource_id,
                "elapsedMs": elapsed_ms,
            }
        )
        meta: Dict[str, Any] = {}
        if decision.enforced:
            meta["rowScopeEnforced"] = True
            meta["filteredRows"] = filtered_count
            if field_missing:
                meta["regionFieldMissing"] = True
        if masked_fields:
            meta["maskedFields"] = masked_fields
        if meta:
            payload["security"] = meta

        logger.info(
            "SQLBot 工具执行完成 tool_key=%s ds=%s fetched=%s filtered=%s returned=%s elapsed=%sms",
            tool_key,
            config.datasource_id,
            fetched,
            filtered_count,
            payload.get("total"),
            elapsed_ms,
        )

        self._audit(
            tool_key,
            user,
            values,
            payload.get("total", 0),
            filtered_count,
            None,
            success=True,
            elapsed_ms=elapsed_ms,
        )
        return _text_chunk(payload)

    # ------------------------------------------------------------------
    # 审计
    # ------------------------------------------------------------------
    def _audit(
        self,
        tool_key: str,
        user: Optional[ToolUserContext],
        params: Dict[str, Any],
        returned_rows: int,
        filtered_rows: int,
        error: Optional[str],
        success: bool = True,
        elapsed_ms: int = 0,
    ) -> None:
        """写入系统审计日志。失败不影响主流程。

        注意：``request_params`` 只记录已声明参数的键值，不记录结果集内容。
        """
        try:
            from app.db.database import SessionLocal
            from app.models.sys.sys_user import SysAuditLog

            safe_params = {
                k: (v if not isinstance(v, str) or len(v) <= 64 else v[:64])
                for k, v in (params or {}).items()
            }
            desc = f"调用 SQLBot 业务工具 {tool_key}"
            if error:
                desc = f"{desc} 失败: {error}"

            with SessionLocal() as db:
                db.add(
                    SysAuditLog(
                        user_id=user.user_id if user else None,
                        username=user.username if user else None,
                        operation_type="query",
                        operation_module=AUDIT_MODULE,
                        operation_desc=desc,
                        request_params={
                            "toolKey": tool_key,
                            "params": safe_params,
                            "returnedRows": returned_rows,
                            "filteredRows": filtered_rows,
                        },
                        response_status=200 if success else 403,
                        response_time_ms=elapsed_ms,
                    )
                )
                db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("写入 SQLBot 工具审计日志失败（已忽略）: %s", exc)
