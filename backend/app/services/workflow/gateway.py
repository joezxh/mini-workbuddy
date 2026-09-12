"""工作流网关 — 统一入口"""
import time
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow.workflow_flow import WorkflowFlow
from app.models.workflow.workflow_execution_log import WorkflowExecutionLog
from app.services.workflow.crypto import decrypt_api_key
from app.services.workflow.adapter_factory import AdapterFactory
from app.services.workflow.platform_adapter import PlatformResponse
from app.services.workflow.rate_limiter import WorkflowRateLimiter
from app.services.workflow.circuit_breaker import CircuitBreaker
from app.services.workflow.retry_policy import RetryPolicy
from app.services.workflow.webhook import WebhookDispatcher


class WorkflowGateway:
    """工作流网关 — 限流 + 熔断 + 重试 + 日志 + Webhook"""

    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.redis = redis_client
        self.rate_limiter = WorkflowRateLimiter(redis_client) if redis_client else None
        self.circuit_breaker = CircuitBreaker(redis_client) if redis_client else None
        self.retry_policy = RetryPolicy()
        self.webhook = WebhookDispatcher()

    async def execute(
        self,
        flow_code: str,
        tenant_id: int,
        inputs: Dict[str, Any],
        user_id: str,
        timeout: float = 600.0,
        execution_id: Optional[str] = None,
    ) -> PlatformResponse:
        """执行工作流（网关入口）"""
        # 1. 查找流程定义
        flow = self.db.scalars(
            select(WorkflowFlow).where(
                WorkflowFlow.flow_code == flow_code,
                WorkflowFlow.tenant_id == tenant_id,
                WorkflowFlow.is_deleted == False,
                WorkflowFlow.is_active == True,
            )
        ).first()
        if not flow:
            return PlatformResponse(success=False, error=f"流程未找到: {flow_code} (tenant={tenant_id})")

        # 2. 限流检查
        if self.rate_limiter:
            rate_cfg = (flow.config or {}).get("rate_limit", {})
            allowed = await self.rate_limiter.acquire(
                tenant_id, flow_code,
                max_tokens=rate_cfg.get("max_tokens", 10),
                refill_rate=rate_cfg.get("refill_rate", 0.167),
            )
            if not allowed:
                return PlatformResponse(success=False, error="请求频率超限", latency_ms=0)

        # 3. 熔断检查
        if self.circuit_breaker:
            can_exec = await self.circuit_breaker.can_execute(tenant_id, flow_code)
            if not can_exec:
                return PlatformResponse(success=False, error="服务熔断中，请稍后重试", latency_ms=0)

        # 4. 创建执行日志
        log = WorkflowExecutionLog(
            tenant_id=tenant_id,
            flow_id=flow.id,
            execution_id=execution_id,
            status="running",
            input_data=inputs,
        )
        self.db.add(log)
        self.db.flush()

        # 5. 解密 API Key + 创建适配器
        try:
            api_key = decrypt_api_key(flow.api_key_enc)
        except Exception as e:
            log.status = "failed"
            log.error_message = f"API Key 解密失败: {e}"
            self.db.commit()
            return PlatformResponse(success=False, error="API Key 解密失败")

        adapter = AdapterFactory.create(
            platform_type=flow.platform_type,
            base_url=flow.base_url,
            api_key=api_key,
            config=flow.config,
        )

        # 6. 执行（带重试）
        t0 = time.monotonic()
        try:
            result = await self.retry_policy.execute_with_retry(
                adapter.invoke,
                flow_type=flow.flow_type,
                inputs=dict(inputs),
                user_id=user_id,
                timeout=timeout,
            )
            latency = int((time.monotonic() - t0) * 1000)

            # 7. 更新日志
            if result.success:
                log.status = "success"
                log.output_data = result.output
                log.platform_trace = result.platform_trace
                if self.circuit_breaker:
                    await self.circuit_breaker.record_success(tenant_id, flow_code)
                event_type = "on_success"
            else:
                log.status = "failed"
                log.error_message = result.error
                if self.circuit_breaker:
                    await self.circuit_breaker.record_failure(tenant_id, flow_code)
                event_type = "on_failure"

            log.latency_ms = latency
            log.completed_at = datetime.utcnow()
            self.db.commit()

            # 8. Webhook
            await self.webhook.dispatch(event_type, flow.config or {}, {
                "flow_code": flow_code, "status": log.status, "latency_ms": latency,
            })

            return result

        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            log.status = "failed"
            log.error_message = str(e)
            log.latency_ms = latency
            log.completed_at = datetime.utcnow()
            self.db.commit()

            if self.circuit_breaker:
                await self.circuit_breaker.record_failure(tenant_id, flow_code)

            await self.webhook.dispatch("on_failure", flow.config or {}, {
                "flow_code": flow_code, "status": "failed", "error": str(e),
            })

            return PlatformResponse(success=False, error=str(e), latency_ms=latency)
