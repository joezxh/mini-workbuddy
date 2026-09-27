"""Compaction Audit Logger - Tracks all context compaction operations.

This module provides two classes:

* ``CompactionAuditLogger`` - generic audit log writer for compaction events.
* ``CrossModeHealthService`` - 跨模式健康度指标(weekly report),
  从 ``ai_session_finalize_log`` 统计 L2/Mem0 同步成功率,供 Task 5 调度器调用。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import insert, select

logger = logging.getLogger(__name__)


def _get_session_factory():
    """延迟导入 SessionLocal,避免测试无需 DB 时强依赖。"""
    try:
        from app.db.database import SessionLocal  # type: ignore

        return SessionLocal
    except Exception:  # pragma: no cover - 仅测试用
        return None


class CompactionAuditLogger:
    """Log and query context compaction operations"""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
    
    async def log_compaction(
        self,
        session_id: int,
        mode: str,
        key: str,
        strategy: str,
        result: Dict[str, Any],
        user_id: int | None = None,
    ) -> None:
        """Log a compaction operation"""
        
        log_entry = {
            "type": "context_compaction",
            "timestamp": datetime.now().isoformat(),
            "tenant_id": self.tenant_id,
            "session_id": session_id,
            "user_id": user_id,
            "mode": mode,
            "key": key,
            "strategy": strategy,
            "result": result,
        }
        
        # Store in audit_log table (implement according to your schema)
        from sqlalchemy import insert
        from app.models.audit.audit_log import AuditLog
        
        SessionLocal = _get_session_factory()
        if SessionLocal is None:
            logger.error("SessionLocal unavailable; skip compaction audit log")
            return

        try:
            stmt = insert(AuditLog).values(
                session_id=session_id,
                action="compaction_triggered",
                target_type="context",
                target_id=f"{mode}:{key}",
                details=log_entry,
            )

            async with SessionLocal() as session:
                await session.execute(stmt)
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    async def get_compaction_history(
        self,
        session_id: int | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent compaction history"""
        
        from sqlalchemy import select
        from app.models.audit.audit_log import AuditLog
        
        SessionLocal = _get_session_factory()
        if SessionLocal is None:
            logger.error("SessionLocal unavailable; skip compaction history query")
            return []

        try:
            stmt = select(AuditLog).where(
                AuditLog.tenant_id == self.tenant_id,
                AuditLog.action == "compaction_triggered",
            ).order_by(AuditLog.created_at.desc()).limit(limit)

            if session_id:
                stmt = stmt.where(AuditLog.session_id == session_id)

            async with SessionLocal() as session:
                results = await session.execute(stmt)
                logs = results.scalars().all()
                
                return [
                    {
                        "id": log.id,
                        "timestamp": log.created_at.isoformat(),
                        "action": log.action,
                        "target_type": log.target_type,
                        "target_id": log.target_id,
                        "details": log.details,
                    }
                    for log in logs
                ]
        
        except Exception as e:
            logger.error(f"Failed to get compaction history: {e}")
            return []
    
    async def manual_override(self, session_id: int, data: Dict[str, Any]) -> bool:
        """Log manual intervention on context"""

        from app.models.audit.audit_log import AuditLog

        log_entry = {
            "type": "manual_override",
            "timestamp": datetime.now().isoformat(),
            "tenant_id": self.tenant_id,
            "session_id": session_id,
            "override_data": data,
        }
        
        SessionLocal = _get_session_factory()
        if SessionLocal is None:
            logger.error("SessionLocal unavailable; skip manual override log")
            return False

        try:
            stmt = insert(AuditLog).values(
                session_id=session_id,
                action="context_manual_override",
                target_type="context",
                target_id=data.get("key"),
                details=log_entry,
            )

            async with SessionLocal() as session:
                await session.execute(stmt)
                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to log manual override: {e}")
            return False


class CrossModeHealthService:
    """跨模式健康度指标服务。

    数据源: ``ai_session_finalize_log`` 表(Task 1 已建)。
    输出字段: ``total`` / ``mem0_synced`` / ``mem0_failed`` / ``error`` / ``mem0_sync_rate``。
    所有 DB 异常被吞掉并返回兜底 dict(返回类型契约 > 抛错),
    这样 Task 5 的调度器调用不会因为 DB 抖动而崩溃。
    """

    def __init__(self, tenant_id: int = 0) -> None:
        self.tenant_id = tenant_id

    def _zero(self) -> Dict[str, Any]:
        return {
            "total": 0,
            "mem0_synced": 0,
            "mem0_failed": 0,
            "error": 0,
            "mem0_sync_rate": 0.0,
            "window_start": None,
            "window_end": None,
        }

    async def get_weekly_health_metrics(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """统计过去 N 天 finalize log 的 Mem0 同步健康度。"""
        try:
            from app.models.ai.ai_session_finalize_log import AISessionFinalizeLog
        except Exception as e:  # pragma: no cover - 模型导入失败
            logger.error(f"CompactionAuditService: cannot import AISessionFinalizeLog: {e}")
            return self._zero()

        SessionLocal = _get_session_factory()
        if SessionLocal is None:
            logger.error("CompactionAuditService: SessionLocal unavailable")
            return self._zero()

        window_end = datetime.utcnow()
        window_start = window_end - timedelta(days=days)

        try:
            async with SessionLocal() as session:
                stmt = select(AISessionFinalizeLog).where(
                    AISessionFinalizeLog.created_at >= window_start,
                )
                rows = (await session.execute(stmt)).scalars().all()

            total = len(rows)
            mem0_synced = sum(1 for r in rows if getattr(r, "mem0_synced", False))
            mem0_failed = sum(
                1
                for r in rows
                if getattr(r, "mem0_synced", None) is False
                and getattr(r, "mem0_error", None)
            )
            error = sum(
                1 for r in rows if getattr(r, "error_message", None)
            )

            rate = (mem0_synced / total) if total else 0.0
            return {
                "total": total,
                "mem0_synced": mem0_synced,
                "mem0_failed": mem0_failed,
                "error": error,
                "mem0_sync_rate": round(rate, 4),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
            }
        except Exception as e:
            logger.error(f"CompactionAuditService: weekly metrics query failed: {e}")
            return self._zero()