"""跨模式上下文记录器 — 9 模式策略注册表 + 统一收尾触发器。

设计要点:
- 策略驱动:STRATEGY_TABLE 注册 9 种模式,新增模式只改一行
- LocalMem0APIImpl 优先:Mem0Service 内部已经实现
- extract_summary 默认截断 2000 字符(本地无 token 约束,完整语义)
- is_cross_mode_accessible 默认 False;deep_research/agent/team 三种模式显式 True
- scheduled 不写 Mem0(write_mem0=False,只记输入)
- 失败静默:所有 try/except + logger,不阻断 SSE 主流程
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session


# 摘要截断长度(本地私有化 Mem0,无 token 成本约束,延长到 2000)
_SUMMARY_TRUNCATE = 2000


def _truncate(s: str, n: int = _SUMMARY_TRUNCATE) -> str:
    """截断字符串到 n 字符,避免超长摘要污染 L2/Mem0。"""
    return s if len(s) <= n else s[:n]


@dataclass(frozen=True)
class FinalizeStrategy:
    """单模式的 finalize 策略。"""

    session_type: str
    source_mode: str
    priority: int
    ttl_hours: int
    write_mem0: bool
    extract_payload: Callable[[Dict[str, Any]], Dict[str, Any]]
    extract_summary: Callable[[Dict[str, Any]], str]
    context_tags: Callable[[Dict[str, Any]], List[str]] = field(default=lambda p: [])
    is_cross_mode_accessible: bool = False


# ── 9 模式策略注册表 ─────────────────────────────────────────────
STRATEGY_TABLE: Dict[str, FinalizeStrategy] = {
    "general": FinalizeStrategy(
        session_type="general", source_mode="general",
        priority=3, ttl_hours=168, write_mem0=True,
        extract_payload=lambda p: {
            "user_input":      _truncate(p.get("user_input", "")),
            "answer":          _truncate(p.get("answer", "")),
            "tool_calls_count": len(p.get("tool_calls") or []),
        },
        extract_summary=lambda p: _truncate(p.get("answer", "")),
        context_tags=lambda p: ["general"],
    ),
    "react": FinalizeStrategy(
        session_type="react", source_mode="react",
        priority=3, ttl_hours=168, write_mem0=True,
        extract_payload=lambda p: {
            "user_input":      _truncate(p.get("user_input", "")),
            "answer":          _truncate(p.get("answer", "")),
            "plan_steps":      (p.get("plan_steps") or [])[:20],
            "tool_calls_count": len(p.get("tool_calls") or []),
        },
        extract_summary=lambda p: _truncate(p.get("answer", "")),
        context_tags=lambda p: ["react"],
    ),
    "thinking": FinalizeStrategy(
        session_type="thinking", source_mode="thinking",
        priority=4, ttl_hours=168, write_mem0=True,
        extract_payload=lambda p: {
            "user_input":     _truncate(p.get("user_input", "")),
            "thinking_steps": (p.get("thinking_steps") or [])[:20],
            "final_answer":   _truncate(p.get("final_answer", "")),
        },
        extract_summary=lambda p: _truncate(p.get("final_answer", "")),
        context_tags=lambda p: ["thinking"],
    ),
    "deep_research": FinalizeStrategy(
        session_type="deep_research", source_mode="deep_research",
        priority=4, ttl_hours=336, write_mem0=True,
        is_cross_mode_accessible=True,
        extract_payload=lambda p: {
            "user_input":    _truncate(p.get("user_input", "")),
            "sub_questions": (p.get("sub_questions") or [])[:10],
            "final_report":  _truncate(p.get("final_report", "")),
            "sources_count": len(p.get("sources") or []),
        },
        extract_summary=lambda p: _truncate(p.get("final_report", "")),
        context_tags=lambda p: ["deep_research"],
    ),
    "skill": FinalizeStrategy(
        session_type="skill", source_mode="skill",
        priority=2, ttl_hours=168, write_mem0=True,
        extract_payload=lambda p: {
            "skill_name":         p.get("skill_name", ""),
            "skill_display_name": p.get("skill_display_name", ""),
            "user_input":         _truncate(p.get("user_input", ""), 500),
            "result":             _truncate(p.get("result", "")),
            "execution_id":       p.get("execution_id"),
        },
        extract_summary=lambda p: (
            f"技能 {p.get('skill_display_name', '')} 执行结果:"
            f"{_truncate(p.get('result', ''), 1800)}"
        ),
        context_tags=lambda p: ["skill", p.get("skill_name", "")],
    ),
    "agent": FinalizeStrategy(
        session_type="agent", source_mode="agent",
        priority=2, ttl_hours=720, write_mem0=True,
        is_cross_mode_accessible=True,
        extract_payload=lambda p: {
            "agent_name":      p.get("agent_name", ""),
            "user_input":      _truncate(p.get("user_input", ""), 500),
            "final_answer":    _truncate(p.get("final_answer", "")),
            "tool_calls_count": len(p.get("tool_calls") or []),
            "execution_id":    p.get("execution_id"),
        },
        extract_summary=lambda p: _truncate(p.get("final_answer", "")),
        context_tags=lambda p: ["agent", p.get("agent_name", "")],
    ),
    "team": FinalizeStrategy(
        session_type="team", source_mode="team",
        priority=2, ttl_hours=168, write_mem0=True,
        is_cross_mode_accessible=True,
        extract_payload=lambda p: {
            "team_name":    p.get("team_name", ""),
            "user_input":   _truncate(p.get("user_input", ""), 500),
            "final_answer": _truncate(p.get("final_answer", "")),
            "member_count": p.get("member_count", 0),
            "speech_count": p.get("speech_count", 0),
        },
        extract_summary=lambda p: _truncate(p.get("final_answer", "")),
        context_tags=lambda p: ["team", p.get("team_name", "")],
    ),
    "scheduled": FinalizeStrategy(
        session_type="scheduled", source_mode="scheduled",
        priority=4, ttl_hours=720, write_mem0=False,  # 后台调度非永久记忆
        extract_payload=lambda p: {
            "task_id":      p.get("task_id"),
            "task_no":      p.get("task_no", ""),
            "target_mode":  p.get("target_mode", ""),
            "user_input":   _truncate(p.get("user_input", ""), 500),
            "priority":     p.get("priority", 5),
            "submitted_at": datetime.utcnow().isoformat(),
        },
        extract_summary=lambda p: "",
        context_tags=lambda p: ["scheduled", p.get("target_mode", "")],
    ),
    "shared": FinalizeStrategy(
        session_type="shared", source_mode="shared",
        priority=5, ttl_hours=168, write_mem0=False,
        extract_payload=lambda p: p.get("data", {}),
        extract_summary=lambda p: "",
        context_tags=lambda p: ["shared"],
    ),
}


class CrossModeContextRecorder:
    """跨模式上下文记录器。SSEBridge.finalize_session() 内统一调用。"""

    def __init__(self, db: Session):
        self.db = db
        self._mgr: Optional[Any] = None

    @staticmethod
    def has_strategy(session_type: str) -> bool:
        return session_type in STRATEGY_TABLE

    def record_finalize(
        self,
        session_id: int,
        user_id: int,
        tenant_id: int,
        session_type: str,
        payload: Dict[str, Any],
        case_number: Optional[str] = None,
    ) -> Optional[int]:
        """主入口:按 session_type 选择策略,执行 L2 + Mem0 + 审计日志。

        失败语义:
        - 整条 record_finalize 失败 → logger.warning(不阻断 SSE)
        - persist_l2_context 失败 → 由 ContextManager 内部 logger.warning
        - sync_to_long_term 失败 → 由 ContextManager 内部 logger.error
        - 审计日志写失败 → _write_audit 内部 logger.warning
        """
        strategy = STRATEGY_TABLE.get(session_type)
        if not strategy:
            logger.warning(
                f"[CrossModeRecorder] No strategy for session_type={session_type}"
            )
            return None

        try:
            data = strategy.extract_payload(payload)
            tags = strategy.context_tags(payload)
            context_key = (
                f"{strategy.source_mode}_{session_id}_"
                f"{int(datetime.utcnow().timestamp() * 1000)}"
            )

            mgr = self._ensure_manager(tenant_id, session_id, user_id, session_type)

            # 1) L2 落库
            record_id = mgr.persist_l2_context(
                session_id=session_id,
                source_mode=strategy.source_mode,
                context_key=context_key,
                context_data=data,
                priority=strategy.priority,
                ttl_hours=strategy.ttl_hours,
                is_cross_mode_accessible=strategy.is_cross_mode_accessible,
                context_tags=tags,
                case_number=case_number,
                tenant_id=tenant_id,
                user_id=user_id,
                db=self.db,
            )

            # 2) Mem0 永久记忆同步(可选)
            mem0_id: Optional[str] = None
            if strategy.write_mem0:
                summary = strategy.extract_summary(payload)
                if summary:
                    mem0_id = mgr.sync_to_long_term(
                        session_id=session_id,
                        user_id=user_id,
                        summary=summary,
                        metadata={
                            "source_mode": strategy.source_mode,
                            "session_type": session_type,
                            "tags": tags,
                        },
                        source_mode=strategy.source_mode,
                    )

            # 3) 审计日志
            self._write_audit(
                session_id=session_id, user_id=user_id, tenant_id=tenant_id,
                session_type=session_type, source_mode=strategy.source_mode,
                l2_record_id=record_id,
                mem0_synced=mem0_id is not None, mem0_memory_id=mem0_id,
                error_message=None,
            )
            return record_id

        except Exception as exc:
            logger.warning(f"[CrossModeRecorder] finalize failed: {exc}")
            try:
                self._write_audit(
                    session_id=session_id, user_id=user_id, tenant_id=tenant_id,
                    session_type=session_type,
                    source_mode=(
                        strategy.source_mode if strategy else "unknown"
                    ),
                    l2_record_id=None, mem0_synced=False, mem0_memory_id=None,
                    error_message=str(exc)[:500],
                )
            except Exception:
                pass
            return None

    def _ensure_manager(self, tenant_id, session_id, user_id, session_type):
        """惰性构建 ContextManager(每个 recorder 实例只构建一次)。"""
        if self._mgr is None:
            from app.ai.context_manager import ContextManager
            self._mgr = ContextManager(tenant_id=tenant_id)
        return self._mgr

    def _write_audit(
        self,
        *,
        session_id: int,
        user_id: int,
        tenant_id: int,
        session_type: str,
        source_mode: str,
        l2_record_id: Optional[int],
        mem0_synced: bool,
        mem0_memory_id: Optional[str],
        error_message: Optional[str],
    ) -> None:
        """写 ai_session_finalize_log,失败静默。"""
        try:
            from app.models.ai.ai_session_finalize_log import AISessionFinalizeLog
            row = AISessionFinalizeLog(
                tenant_id=tenant_id, session_id=session_id, user_id=user_id,
                session_type=session_type, source_mode=source_mode,
                l2_record_id=l2_record_id, mem0_synced=mem0_synced,
                mem0_memory_id=mem0_memory_id, error_message=error_message,
            )
            self.db.add(row)
            self.db.commit()
        except Exception as exc:
            try:
                self.db.rollback()
            except Exception:
                pass
            logger.warning(f"[CrossModeRecorder] audit log write failed: {exc}")