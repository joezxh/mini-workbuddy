"""链式编排执行器"""
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.workflow.workflow_chain import WorkflowChain
from app.services.workflow.gateway import WorkflowGateway
from app.services.workflow.platform_adapter import PlatformResponse


class ChainExecutor:
    """链式编排执行器"""

    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.gateway = WorkflowGateway(db, redis_client)

    async def execute_chain(
        self,
        chain_code: str,
        tenant_id: int,
        initial_inputs: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        """执行链式编排"""
        from sqlalchemy import select
        chain = self.db.scalars(
            select(WorkflowChain).where(
                WorkflowChain.chain_code == chain_code,
                WorkflowChain.tenant_id == tenant_id,
                WorkflowChain.is_deleted == False,
                WorkflowChain.is_active == True,
            )
        ).first()
        if not chain:
            raise ValueError(f"链未找到: {chain_code}")

        context: Dict[str, Any] = {"user_input": initial_inputs, "steps": []}

        steps = sorted(chain.steps, key=lambda s: s.get("step_order", 0))
        for step in steps:
            # 1. 条件检查
            condition = step.get("condition")
            if condition and not self._evaluate_condition(condition, context):
                context["steps"].append({
                    "step_order": step["step_order"],
                    "flow_code": step["flow_code"],
                    "status": "skipped",
                    "output": {},
                })
                continue

            # 2. 输入映射
            step_inputs = self._resolve_mapping(step.get("input_mapping", {}), context)

            # 3. 通过网关执行
            try:
                result = await self.gateway.execute(
                    flow_code=step["flow_code"],
                    tenant_id=tenant_id,
                    inputs=step_inputs,
                    user_id=user_id,
                )
                context["steps"].append({
                    "step_order": step["step_order"],
                    "flow_code": step["flow_code"],
                    "status": "success" if result.success else "failed",
                    "output": result.output,
                    "error": result.error,
                })
            except Exception as e:
                strategy = step.get("error_strategy", "stop")
                if strategy == "stop":
                    context["steps"].append({
                        "step_order": step["step_order"],
                        "status": "failed", "error": str(e),
                    })
                    raise
                context["steps"].append({
                    "step_order": step["step_order"],
                    "status": "failed", "error": str(e), "output": {},
                })

        return context

    @staticmethod
    def _evaluate_condition(condition: str, context: Dict) -> bool:
        """简单条件评估：支持 $.steps[N].status == 'success' 格式"""
        try:
            # 极简实现：替换变量后 eval（生产环境应使用安全的表达式解析器）
            expr = condition
            for i, step in enumerate(context.get("steps", [])):
                expr = expr.replace(f"$.steps[{i}].status", f"'{step.get('status', '')}'")
            return bool(eval(expr))  # noqa: S307
        except Exception:
            return True  # 表达式解析失败时默认执行

    @staticmethod
    def _resolve_mapping(mapping: Dict[str, str], context: Dict) -> Dict[str, Any]:
        """解析输入映射"""
        result = {}
        for target_key, source_expr in mapping.items():
            if source_expr.startswith("$."):
                result[target_key] = ChainExecutor._json_path_get(source_expr, context)
            elif source_expr.startswith('"') and source_expr.endswith('"'):
                result[target_key] = source_expr[1:-1]
            else:
                result[target_key] = source_expr
        return result

    @staticmethod
    def _json_path_get(path: str, data: Dict) -> Any:
        """简单 JSONPath 取值（仅支持 $.a.b.c 和 $.steps[N].output.key）"""
        parts = path.lstrip("$.").replace("[", ".").replace("]", "").split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return None
            if current is None:
                return None
        return current
