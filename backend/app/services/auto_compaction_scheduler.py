"""Auto-compaction Scheduler Service

Provides background job scheduling for automatic context compaction based on:
1. Time-based triggers (e.g., every hour)
2. Token threshold triggers (when tokens exceed limit)
3. Session inactivity triggers (after long period of no activity)

Uses APScheduler for async task scheduling.
"""

import asyncio  # noqa: F401  # 预存未使用 import,本 PR 不动
from typing import Dict, Any, Optional, List  # noqa: F401  # 预存未使用,本 PR 不动
from datetime import datetime, timedelta
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

try:  # pragma: no cover - 测试/CI 兼容 shim
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover
    AsyncSession = None  # type: ignore

try:  # pragma: no cover - 兼容不存在的 get_db_session 旧名
    from app.db.database import get_db_session  # type: ignore
except Exception:  # pragma: no cover
    get_db_session = None  # type: ignore

from app.services.compaction_audit_service import CompactionAuditLogger
from app.services.compaction_audit_service import CrossModeHealthService


class AutoCompactionScheduler:
    """Automatic context compaction scheduler"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.config: Dict[str, Any] = {
            # Schedule configuration
            "enabled": True,
            "time_based_enabled": True,
            "time_based_interval_hours": 60,  # Check every 60 minutes
            
            "threshold_based_enabled": True,
            "max_tokens_per_session": 32000,
            "compaction_target_tokens": 8000,
            
            "inactivity_based_enabled": True,
            "session_inactivity_hours": 24,
            
            # Default strategies per mode
            "default_strategies": {
                "shared": "summary_and_keep_latest",
                "dify": "priority_eviction",
                "sqlbot": "access_based",
                "agentscope": "sliding_window"
            }
        }
        
    async def start(self) -> None:
        """Start the scheduler"""
        if self.is_running:
            return
        
        try:
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            
            # Schedule periodic jobs
            self._schedule_jobs()
            
            logger.info("Auto-compaction scheduler started")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the scheduler"""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            
            logger.info("Auto-compaction scheduler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
            raise
    
    def _schedule_jobs(self) -> None:
        """Schedule all background jobs"""
        
        # Job 1: Periodic token usage check and auto-compaction
        if self.config["threshold_based_enabled"]:
            self.scheduler.add_job(
                func=self._check_and_compact_high_usage_sessions,
                trigger=IntervalTrigger(hours=1),  # Run every hour
                id="token_threshold_check",
                name="Check session token thresholds",
                replace_existing=True,
            )
        
        # Job 2: Cleanup inactive sessions
        if self.config["inactivity_based_enabled"]:
            self.scheduler.add_job(
                func=self._cleanup_inactive_sessions,
                trigger=IntervalTrigger(days=1),  # Run daily
                id="inactive_session_cleanup",
                name="Cleanup inactive sessions",
                replace_existing=True,
            )
        
        # Job 3: Generate weekly reports
        self.scheduler.add_job(
            func=self._generate_weekly_report,
            trigger=DateTrigger(run_date=datetime.now() + timedelta(days=7)),
            id="weekly_report",
            name="Generate weekly compaction report",
            replace_existing=True,
        )
    
    async def _check_and_compact_high_usage_sessions(self) -> None:
        """Check for sessions exceeding token limits and auto-compact"""
        
        logger.info("Running automatic token threshold check...")
        
        try:
            from app.services.ai_session_service import AISessionService
            from app.db.database import get_db_session  # noqa: F401
            
            session_service = AISessionService()
            
            # Get recent sessions that might be active
            recent_sessions = await session_service.get_recent_sessions(days=30)
            
            compacted_count = 0
            
            for session in recent_sessions[:50]:  # Limit to 50 sessions per run
                
                # Get session stats
                stats = await self._get_session_stats(session.session_id)
                
                # Check if exceeds threshold
                if stats.total_tokens > self.config["max_tokens_per_session"]:
                    
                    logger.info(
                        f"Session {session.session_id} exceeded threshold: "
                        f"{stats.total_tokens}/{self.config['max_tokens_per_session']} tokens"
                    )
                    
                    # Get appropriate strategy based on most common mode
                    mode = session.mode or "shared"
                    strategy = self.config["default_strategies"].get(mode, "summary_and_keep_latest")
                    
                    # Execute auto-compaction
                    result = await self._compact_context(
                        session=session.tenant_id,
                        key=f"session_{session.session_id}",
                        strategy=strategy,
                        target_tokens=self.config["compaction_target_tokens"]
                    )
                    
                    if result["success"]:
                        compacted_count += 1
                        logger.info(
                            f"Auto-compact session {session.session_id}: "
                            f"{result['tokens_before']}→{result['tokens_after']} tokens "
                            f"(ratio: {result['compaction_ratio']:.2f}x)"
                        )
                        
                        # Log to audit trail
                        await self._log_compaction_audit(session.session_id, mode, strategy, result)
            
            logger.info(f"Token threshold check complete. Compactted {compacted_count} sessions.")
            
        except Exception as e:
            logger.error(f"Error in token threshold check: {e}")
    
    async def _cleanup_inactive_sessions(self) -> None:
        """Cleanup old contexts for inactive sessions"""
        
        logger.info("Running inactive session cleanup...")
        
        try:
            from app.services.ai_session_service import AISessionService
            from app.db.database import get_db_session  # noqa: F401
            
            session_service = AISessionService()
            
            cutoff_date = datetime.now() - timedelta(
                hours=self.config["session_inactivity_hours"]
            )
            
            inactive_sessions = await session_service.get_inactive_sessions(cutoff_date)
            
            cleaned_count = 0
            
            for session in inactive_sessions[:100]:  # Limit to 100 per run
                try:
                    await self._purge_session_context(session.session_id)
                    cleaned_count += 1
                    
                    logger.info(f"Purged inactive session {session.session_id}")
                    
                except Exception as e:
                    logger.warning(f"Failed to purge session {session.session_id}: {e}")
                    continue
            
            logger.info(f"Inactive session cleanup complete. Cleaned {cleaned_count} sessions.")
            
        except Exception as e:
            logger.error(f"Error in inactive session cleanup: {e}")
    
    async def _get_session_stats(self, session_id: int) -> Dict[str, Any]:
        """Get stats for a session"""
        
        # Simplified version - in production, use full ContextManager
        return {
            "total_tokens": 0,
            "message_counts": {"local": 0, "vector_store": 0, "shared_context": 0},
            "last_accessed": datetime.now().isoformat()
        }
    
    async def _compact_context(
        self,
        tenant_id: str,
        key: str,
        strategy: str,
        target_tokens: int
    ) -> Dict[str, Any]:
        """Execute context compaction"""
        
        from app.ai.context_manager import ContextManager
        
        manager = ContextManager(tenant_id=tenant_id)
        
        result = manager.compact_context(
            mode="shared",
            key=key,
            strategy=strategy,
            target_tokens=target_tokens
        )
        
        return result
    
    async def _purge_session_context(self, session_id: int) -> bool:
        """Purge all contexts associated with a session"""
        
        # TODO: Implement actual purge logic using database operations
        # This would delete entries from AIChatContextStorage table
        
        logger.warning(f"Purging session {session_id} contexts not implemented yet")
        return False
    
    async def _log_compaction_audit(
        self,
        session_id: int,
        mode: str,
        strategy: str,
        result: Dict[str, Any]
    ) -> None:
        """Log compaction operation to audit log"""
        
        audit_logger = CompactionAuditLogger(tenant_id="__system_auto__")
        
        await audit_logger.log_compaction(
            session_id=session_id,
            mode=mode,
            key=f"session_{session_id}",
            strategy=strategy,
            result=result,
            user_id=None  # System triggered
        )
    
    async def _generate_weekly_report(self) -> Dict[str, Any]:
        """Generate weekly compaction metrics report

        数据源: ``CrossModeHealthService.get_weekly_health_metrics()``
        (即 ``ai_session_finalize_log`` 表,Task 1 创建)。
        任何 DB 异常都被吞掉并返回安全默认 dict,确保调度器主循环不挂。
        """

        logger.info("Generating weekly compaction report...")

        report: Dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "period_days": 7,
            "total": 0,
            "mem0_synced": 0,
            "mem0_failed": 0,
            "error": 0,
            "mem0_sync_rate": 0.0,
            "window_start": None,
            "window_end": None,
        }

        try:
            health = CrossModeHealthService()
            metrics = await health.get_weekly_health_metrics(days=7)
            report.update(metrics)
        except Exception as e:
            logger.error(f"Weekly report health metrics query failed: {e}")
            # 兜底保留默认零值

        logger.info(f"Weekly report generated: {report}")
        return report
    
    def get_schedule_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        
        return {
            "is_running": self.is_running,
            "jobs_scheduled": len(self.scheduler.get_jobs()),
            "config": self.config.copy(),
            "next_run_times": {
                job.id: job.next_run_time.isoformat() 
                for job in self.scheduler.get_jobs()
                if job.next_run_time
            }
        }
    
    def update_config(self, config_updates: Dict[str, Any]) -> None:
        """Update scheduler configuration"""
        
        self.config.update(config_updates)
        logger.info(f"Scheduler config updated: {config_updates}")
        
        # Reschedule jobs if settings changed
        if "time_based_interval_hours" in config_updates:
            # Re-schedule the periodic check
            self.scheduler.remove_job("token_threshold_check")
            self._schedule_jobs()


# Singleton instance
_scheduler_instance: Optional[AutoCompactionScheduler] = None


def get_scheduler() -> AutoCompactionScheduler:
    """Get scheduler singleton"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AutoCompactionScheduler()
    return _scheduler_instance


async def initialize_scheduler() -> None:
    """Initialize and start scheduler (call during app startup)"""
    scheduler = get_scheduler()
    await scheduler.start()
    logger.info("Auto-compaction scheduler initialized")


async def shutdown_scheduler() -> None:
    """Shutdown scheduler (call during app shutdown)"""
    scheduler = get_scheduler()
    await scheduler.stop()
    logger.info("Auto-compaction scheduler shut down")
