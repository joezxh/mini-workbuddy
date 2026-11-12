"""ReflectorService —— Worker 产出校验（LLM / 启发式）+ 重试闭环。

Task 3.4 / TR-3.2：verify pass → engine.ticket_report(kind="ready")；
fail → re-enqueue launch effect（最多 max_retries 次）；超限 → kind="failed"。

LLM 推理路径与 assessor.py 同款（callable / ChatModelBase 子线程 asyncio.run），
无 LLM 时走启发式：输出非空且不含 stub 标记即 pass。
"""
from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


_LLM_VERIFY_TIMEOUT = 30.0  # 秒
_llm_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sa-reflector-llm")

# 启发式失败标记 —— Worker stub / AgentScope 报错输出
_STUB_MARKERS = ("[stub", "[AgentScope error]")


@dataclass
class ReflectCheck:
    """Reflector 校验结果。"""
    completed: bool
    quality: str = "unknown"
    completeness: str = "unknown"
    accuracy: str = "unknown"
    remaining_risks: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "completed": self.completed,
            "quality": self.quality,
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "remaining_risks": self.remaining_risks,
            "reason": self.reason,
        }


_REFLECT_SYS_PROMPT = (
    "你是 SuperAgent 的结果校验器（Reflector）。给定 Ticket 任务描述和 Worker 的输出，"
    "独立判断任务是否真正完成（与 Worker 不共享上下文，保证客观）。"
    '只输出 JSON：{"completed": true/false, "quality": "good/acceptable/poor", '
    '"completeness": "完整度简述", "accuracy": "准确性简述", '
    '"remaining_risks": ["遗留风险"], "reason": "简短中文理由"}。'
)


class ReflectorService:
    """独立 verifier —— 对 Worker 产出做反思校验 + 重试决策。"""

    def __init__(self, repo: Any, engine: Any, queue: Any = None,
                 llm_client: Any | None = None,
                 llm_timeout: float = _LLM_VERIFY_TIMEOUT,
                 max_retries: int = 2):
        self.repo = repo
        self.engine = engine
        self.queue = queue  # EffectQueue —— re-enqueue launch 用
        self.llm = llm_client  # callable | ChatModelBase | None
        self.llm_timeout = llm_timeout
        self.max_retries = max_retries

    # ---- 主入口 ----

    def verify(self, ticket_id: str, worker_output: str) -> ReflectCheck:
        """校验 Worker 输出 —— LLM 优先（失败回退），无 LLM 走启发式。"""
        task_text = self._mandate_scope(ticket_id) or ""
        if self.llm is not None:
            verdict = self._llm_verify(task_text, worker_output)
            if verdict is not None:
                return ReflectCheck(
                    completed=bool(verdict.get("completed")),
                    quality=str(verdict.get("quality", "unknown")),
                    completeness=str(verdict.get("completeness", "unknown")),
                    accuracy=str(verdict.get("accuracy", "unknown")),
                    remaining_risks=list(verdict.get("remaining_risks") or []),
                    reason=str(verdict.get("reason", "")),
                )
        return self._heuristic_verify(worker_output)

    async def finalize(self, ticket_id: str, worker_output: str,
                       trigger_id: str | None = None) -> ReflectCheck:
        """verify + 结果回写 —— pass→ready / fail→re-enqueue launch / 超限→failed。"""
        check = self.verify(ticket_id, worker_output)

        if self.engine is None:
            logger.warning(f"Reflector.finalize · engine 缺失 · ticket={ticket_id} · 跳过回写")
            return check

        workspace_id = 0
        retries_used = 0
        with self.repo.atomic() as db:
            from app.models.superagent import SuperAgentEffect
            ticket = self.repo.get_ticket(db, ticket_id)
            if ticket is not None:
                workspace_id = ticket.workspace_id
            # 重试计数：launch effect 中带 ticket_id 的条目（首跑 effect 无 ticket_id）
            retries_used = db.query(SuperAgentEffect).filter(
                SuperAgentEffect.kind == "launch",
                SuperAgentEffect.ticket_id == ticket_id,
            ).count()

        if check.completed:
            self.engine.ticket_report(ticket_id, {
                "kind": "ready",
                "message": check.reason or "reflector verified",
                "reflect": check.to_dict(),
            })
            return check

        if self.queue is not None and workspace_id and retries_used < self.max_retries:
            logger.warning(
                f"Reflector · ticket={ticket_id} verify failed → "
                f"retry {retries_used + 1}/{self.max_retries} · reason={check.reason}"
            )
            await self.queue.enqueue(
                workspace_id=workspace_id, kind="launch", ticket_id=ticket_id,
                payload={
                    "ticket_id": ticket_id, "trigger_id": trigger_id,
                    "retry": True, "retries_used": retries_used,
                },
            )
            return check

        self.engine.ticket_report(ticket_id, {
            "kind": "failed",
            "error": "reflection failed after max retries"
            if retries_used >= self.max_retries else "no retry channel available",
            "reflect": check.to_dict(),
        })
        return check

    # ---- LLM 推理（对齐 assessor 模式）----

    def _llm_verify(self, task_text: str, worker_output: str) -> dict | None:
        """统一入口：callable 同步调用 / ChatModel 子线程推理。"""
        if callable(self.llm) and not hasattr(self.llm, "__await__"):
            try:
                raw = self.llm({"task": task_text, "output": worker_output})
                if isinstance(raw, dict) and "completed" in raw:
                    return self._normalize_verdict(raw)
                return self._parse_verdict(str(raw))
            except Exception as e:
                logger.warning(f"Reflector · llm callable failed: {e}")
                return None
        return self._chat_model_verify(task_text, worker_output)

    def _chat_model_verify(self, task_text: str, worker_output: str) -> dict | None:
        """AgentScope ChatModel 真实推理 —— 子线程 + 新 loop 驱动。"""
        try:
            from agentscope.message import Msg, TextBlock
            from .assessor import AssessorService
        except Exception as e:
            logger.warning(f"Reflector · agentscope unavailable: {e}")
            return None

        user_text = (
            f"[任务]\n{(task_text or '(未提供)')[:1500]}\n"
            f"[Worker 输出]\n{(worker_output or '')[:3000]}\n\n"
            f"请输出 JSON 校验结果。"
        )

        def _drive() -> dict | None:
            async def _run() -> str:
                msg = Msg(name="user", role="user", content=[TextBlock(text=user_text)])
                resp = await self.llm([msg])
                return AssessorService._extract_response_text(resp)

            return self._parse_verdict(asyncio.run(_run()))

        fut = _llm_pool.submit(_drive)
        try:
            return fut.result(timeout=self.llm_timeout)
        except Exception as e:
            logger.warning(f"Reflector · LLM verify failed (回退启发式): {type(e).__name__}: {e}")
            fut.cancel()
            return None

    @staticmethod
    def _parse_verdict(text: str) -> dict | None:
        """从模型输出提取 JSON verdict（容忍 ```json 围栏和前后杂文）。"""
        if not text:
            return None
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            v = json.loads(m.group(0))
            if isinstance(v, dict) and "completed" in v:
                return ReflectorService._normalize_verdict(v)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return None

    @staticmethod
    def _normalize_verdict(v: dict) -> dict:
        return {
            "completed": bool(v.get("completed")),
            "quality": str(v.get("quality", "unknown"))[:64],
            "completeness": str(v.get("completeness", "unknown"))[:64],
            "accuracy": str(v.get("accuracy", "unknown"))[:64],
            "remaining_risks": [
                str(r)[:200] for r in (v.get("remaining_risks") or []) if r
            ][:10],
            "reason": str(v.get("reason", ""))[:300],
        }

    # ---- 启发式 ----

    @staticmethod
    def _heuristic_verify(worker_output: str) -> ReflectCheck:
        text = (worker_output or "").strip()
        if not text:
            return ReflectCheck(
                completed=False, quality="poor", completeness="empty",
                accuracy="unknown", reason="worker output is empty",
            )
        for marker in _STUB_MARKERS:
            if marker in text:
                return ReflectCheck(
                    completed=False, quality="poor", completeness="stub",
                    accuracy="unknown", reason=f"stub output marker: {marker}",
                )
        return ReflectCheck(
            completed=True, quality="acceptable", completeness="unknown",
            accuracy="unknown", remaining_risks=["heuristic verification (no LLM)"],
            reason="non-empty output without stub markers",
        )

    # ---- 辅助 ----

    def _mandate_scope(self, ticket_id: str) -> str | None:
        try:
            with self.repo.atomic() as db:
                mandate = self.repo.get_mandate(db, ticket_id=ticket_id)
                return (mandate.scope or None) if mandate else None
        except Exception as e:
            logger.warning(f"Reflector · read mandate scope failed · ticket={ticket_id}: {e}")
            return None
