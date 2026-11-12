"""SandboxTools —— 沙箱受控执行的 SuperAgent 工具封装（规格 2.4）。

MinWorkBuddy 的"沙箱执行"是确定性推演引擎的受控 AST 求值器
（``app.services.sandbox.ast_eval.eval_expr``：仅字面量/属性引用/四则/比较/逻辑/聚合，
Decimal 量化 4 位，禁止 eval/exec）。python_exec 直接复用该求值器做沙箱化表达式
执行，不重复实现求值逻辑。
service 不存在 / 求值失败 → 降级返回空列表或 error 字段，不抛异常。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from loguru import logger

from .toolkit import LocalTool

_PY_EXEC_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "expr": {"type": "object", "description": "受控 AST 表达式节点（含 op 的节点树）"},
        "params": {"type": "object", "description": "参数引用表：key → 数值（op=param）"},
        "props": {"type": "object", "description": "属性引用表：'entity.key' → 数值（op=prop）"},
    },
    "required": ["expr"],
}


class SandboxTools:
    """python_exec 工具 —— 受控 AST 表达式求值（无 eval/exec，确定性 Decimal）。"""

    @classmethod
    def build(cls, workspace_id: int | None) -> list[LocalTool]:
        try:
            return cls._build(workspace_id)
        except Exception as e:  # noqa: BLE001 —— 降级不抛
            logger.warning(f"SandboxTools degraded → no tools (ws={workspace_id}): {e}")
            return []

    @classmethod
    def _build(cls, workspace_id: int | None) -> list[LocalTool]:
        # service 可用性检查（ImportError → 降级）
        from app.services.sandbox.ast_eval import AstEvalError  # noqa: F401

        def _exec(args: dict[str, Any]) -> dict[str, Any]:
            import app.services.sandbox.ast_eval as _mod

            expr = args.get("expr")
            params = args.get("params") or {}
            props = args.get("props") or {}
            if not isinstance(expr, dict):
                return {"error": "expr 必须是 AST 节点对象（含 op 键）"}

            def get_prop(entity: str, key: str) -> Decimal:
                raw = props.get(f"{entity}.{key}")
                if raw is None:
                    raise _mod.AstEvalError("MISSING_PROP", f"{entity}.{key}")
                return Decimal(str(raw))

            def get_param(key: str) -> Decimal:
                raw = params.get(key)
                if raw is None:
                    raise _mod.AstEvalError("MISSING_PROP", f"param:{key}")
                return Decimal(str(raw))

            try:
                value = _mod.eval_expr(expr, get_prop, get_param)
            except _mod.AstEvalError as e:
                return {"error": str(e)}
            except Exception as e:  # noqa: BLE001 —— 工具调用错误折叠为 error 字段
                logger.warning(f"python_exec failed (ws={workspace_id}): {e}")
                return {"error": str(e)}
            return {"result": str(value)}

        logger.info(f"SandboxTools ws={workspace_id} · python_exec ready")
        return [LocalTool(
            name="python_exec",
            description=(
                "沙箱执行受控 Python 表达式（AST 白名单：四则/比较/逻辑/聚合/clip/if；"
                "Decimal 量化 4 位，禁止 eval/exec）。params/props 提供数值引用，"
                "返回 {result} 或 {error}。"
            ),
            input_schema=_PY_EXEC_SCHEMA,
            handler=_exec,
        )]
