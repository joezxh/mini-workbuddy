"""AssessorService —— 接入 PolicyService + AgentScope LLM 推理。

Task 3.2：MasterAssessor 对每个 Thread 进行 Eval，输出 Candidate + Decision。

LLM 推理路径（llm_client 存在时启用，失败自动回退规则评估）：
- ``callable``：同步函数 ``(trigger_dict, rule_hint) -> dict``（测试友好）
- AgentScope ChatModelBase：子线程 asyncio.run 驱动真实推理
  （对齐 kg_llm_extractor 结论：build_model / await model(...) 必须在
  新建 loop 内执行，避免 AsyncClient 跨 loop 归属错乱）
"""
from __future__ import annotations

import asyncio
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger

from .policy import PolicyService, AssessmentOutcome


_LLM_EVAL_TIMEOUT = 30.0  # 秒
_llm_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sa-assessor-llm")


@dataclass
class Candidate:
    """Eval 输出的候选决策。"""
    trigger_id: str
    thread_id: str
    outcome: AssessmentOutcome
    confidence: float = 0.0
    reason: str = ""
    llm_verdict: dict | None = field(default=None)

    @property
    def should_accept(self) -> bool:
        # Policy 是硬约束：规则不 accept 一票否决；
        # LLM verdict 存在且拒绝时同样否决（保守策略）。
        if not self.outcome.can_accept():
            return False
        if self.llm_verdict and self.llm_verdict.get("accept") is False:
            return False
        return True


_EVAL_SYS_PROMPT = (
    "你是 SuperAgent 的准入评估器（Master Assessor）。给定一条触发消息"
    "（来自 GitHub Issue/PR/Comment 或飞书群聊）和策略规则命中提示，"
    "判断是否应该为它创建一个 Agent 工单（Ticket）并自动执行。"
    "只输出 JSON：{\"accept\": true/false, \"confidence\": 0.0~1.0, \"reason\": \"简短中文理由\"}。"
    "拒绝的场景：闲聊、无明确意图、与文案/视觉修复无关的重复消息、疑似垃圾信息。"
)


def build_assessor_llm(model_id: int | None = None) -> Any:
    """构造 Assessor 用的 AgentScope ChatModel（DB 配置 → ENV 兜底）。

    失败返回 None（AssessorService 自动降级为纯规则评估）。
    """
    try:
        from app.ai.strategy.factory_ext import (
            build_default_model_config,
            build_model,
            resolve_model_config,
        )

        cfg = {}
        if model_id:
            cfg = resolve_model_config(int(model_id))
        return build_model(cfg or build_default_model_config())
    except Exception as e:
        logger.warning(f"build_assessor_llm failed — 纯规则评估: {e}")
        return None


class AssessorService:
    """Thread 串行 Eval —— 对每个 open Thread 进行一次准入评估。"""

    def __init__(self, policy: PolicyService, llm_client: Any | None = None,
                 llm_timeout: float = _LLM_EVAL_TIMEOUT):
        self.policy = policy
        self.llm = llm_client  # callable | ChatModelBase | None
        self.llm_timeout = llm_timeout

    # ---- LLM 推理 ----

    def _parse_verdict(self, text: str) -> dict | None:
        """从模型输出提取 JSON verdict（容忍 ```json 围栏和前后杂文）。"""
        if not text:
            return None
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            v = json.loads(m.group(0))
            if isinstance(v, dict) and "accept" in v:
                return {
                    "accept": bool(v.get("accept")),
                    "confidence": float(v.get("confidence", 0.5)),
                    "reason": str(v.get("reason", ""))[:200],
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return None

    def _chat_model_eval(self, trigger: dict, rule_hint: str) -> dict | None:
        """AgentScope ChatModel 真实推理 —— 子线程 + 新 loop 驱动。"""
        from agentscope.message import Msg, TextBlock

        user_text = (
            f"[触发消息]\n标题: {trigger.get('title') or '(无)'}\n"
            f"正文: {(trigger.get('body') or '')[:1500]}\n"
            f"来源: {trigger.get('_source_kind', 'unknown')} · "
            f"发送者: {trigger.get('sender_name') or trigger.get('sender_id') or 'unknown'}\n"
            f"[策略命中]\n{rule_hint}\n\n请输出 JSON verdict。"
        )

        def _drive() -> dict | None:
            # 子线程内新建 loop：构造 Msg → await model([...]) → ChatResponse
            async def _run() -> str:
                msg = Msg(name="user", role="user", content=[TextBlock(text=user_text)])
                resp = await self.llm([msg])  # ChatModelBase.__call__(messages)
                return self._extract_response_text(resp)

            return self._parse_verdict(asyncio.run(_run()))

        fut = _llm_pool.submit(_drive)
        try:
            return fut.result(timeout=self.llm_timeout)
        except Exception as e:
            logger.warning(f"Assessor · LLM eval failed (回退规则): {type(e).__name__}: {e}")
            fut.cancel()
            return None

    @staticmethod
    def _extract_response_text(resp: Any) -> str:
        """ChatResponse → 文本（content 为 str 或 block 列表）。"""
        content = getattr(resp, "content", resp)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                text = (
                    block.get("text") if isinstance(block, dict)
                    else getattr(block, "text", None)
                )
                if isinstance(text, str) and text:
                    parts.append(text)
            return "\n".join(parts)
        return str(content)

    def _llm_eval(self, trigger: dict, rule_hint: str) -> dict | None:
        """统一入口：callable 同步调用 / ChatModel 子线程推理。"""
        if self.llm is None:
            return None
        if callable(self.llm) and not hasattr(self.llm, "__await__"):
            # 同步 callable（测试/自定义集成）—— 返回 dict 或 JSON 字符串均可
            try:
                raw = self.llm(trigger, rule_hint)
                if isinstance(raw, dict) and "accept" in raw:
                    return {
                        "accept": bool(raw.get("accept")),
                        "confidence": float(raw.get("confidence", 0.5)),
                        "reason": str(raw.get("reason", ""))[:200],
                    }
                return self._parse_verdict(str(raw))
            except Exception as e:
                logger.warning(f"Assessor · llm callable failed: {e}")
                return None
        return self._chat_model_eval(trigger, rule_hint)

    # ---- 主入口 ----

    def evaluate_thread(self, thread_id: str, triggers: list[dict],
                        source_kind: str, source: str) -> list[Candidate]:
        """对 Thread 的所有 Trigger 进行 Eval，返回 Candidate 列表。

        llm_client 为 None 时走纯规则（单元测试/离线模式）；
        存在时对每个 trigger 做 LLM 真实推理，失败自动回退规则结果。
        """
        candidates: list[Candidate] = []
        for t in triggers:
            outcome = self.policy.assess(
                source_kind=source_kind,
                source=source,
                sender_id=t.get("sender_id"),
                addressed=t.get("addressed", False),
                trigger_text=(t.get("title") or "") + "\n" + (t.get("body") or ""),
                sender_name=t.get("sender_name", ""),
            )

            confidence = 0.8 if outcome.can_accept() else 0.3
            reason = f"rules: matched={len(outcome.matched_rules)} direction={outcome.direction}"
            llm_verdict = None

            if self.llm is not None:
                rule_hint = json.dumps(
                    {"matched_rules": outcome.matched_rules, "direction": outcome.direction},
                    ensure_ascii=False,
                )
                llm_verdict = self._llm_eval(t, rule_hint)
                if llm_verdict is not None:
                    if llm_verdict["accept"] and outcome.can_accept():
                        confidence = max(confidence, llm_verdict["confidence"])
                        reason = f"rules+llm: {llm_verdict['reason']}"
                    elif llm_verdict["accept"] and not outcome.can_accept():
                        # policy 硬约束优先：LLM 同意但规则拒绝 → 仍拒绝
                        reason = f"rules veto (llm agreed): {llm_verdict['reason']}"
                    elif not llm_verdict["accept"]:
                        confidence = min(confidence, llm_verdict["confidence"])
                        reason = f"llm reject: {llm_verdict['reason']}"

            candidates.append(Candidate(
                trigger_id=t["id"],
                thread_id=thread_id,
                outcome=outcome,
                confidence=confidence,
                reason=reason,
                llm_verdict=llm_verdict,
            ))

        accepted = [c for c in candidates if c.should_accept]
        logger.info(
            f"Assessor · thread={thread_id} · {len(candidates)} candidates · "
            f"{len(accepted)} accepted · llm={'on' if self.llm else 'off'}"
        )
        return candidates
