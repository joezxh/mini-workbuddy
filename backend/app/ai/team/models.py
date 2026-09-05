"""Team 运行引擎配置 — 编排运行时参数。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionProfile:
    """团队编排运行时参数。"""

    max_rounds: int = 10
    worker_max_iters: int = 8
    worker_concurrency: int = 0        # 0=无限制
    worker_timeout_seconds: int = 120  # 单 worker 基础超时
    worker_timeout_per_batch: int = 60
    worker_timeout_max: int = 900      # 单 worker 超时硬上限
    run_timeout_seconds: int = 1800    # 团队整体超时
    max_worker_calls: int = 20         # spawn 预算上限
    plan_revise_limit: int = 3
    dispatch_mode: str = "batch_parallel"
    honor_canvas_hint: bool = False
    on_node_error: str = "continue"
    stream: bool = True
    max_context_tokens: int = 25600

    @classmethod
    def default(cls) -> "ExecutionProfile":
        return cls()

    @classmethod
    def from_run_config(cls, run_config: Optional[dict] = None) -> "ExecutionProfile":
        """由 run_config（JSONB 或快照）构造，缺失键回落默认值。"""
        from app.models.agent.agent_team import AgentTeam

        merged: dict = dict(AgentTeam.RUN_CONFIG_DEFAULTS)
        merged.update({k: v for k, v in (run_config or {}).items() if v is not None})
        try:
            concurrency = merged.get("max_parallel") or merged.get("max_concurrency") or 0
            return cls(
                max_rounds=int(merged.get("max_rounds") or 10),
                worker_concurrency=int(concurrency or 0),
                worker_timeout_seconds=int(merged.get("node_timeout_seconds") or 120),
                worker_timeout_per_batch=int(merged.get("node_timeout_per_batch") or 60),
                worker_timeout_max=int(merged.get("node_timeout_max") or 900),
                run_timeout_seconds=int(merged.get("total_timeout_seconds") or 1800),
                max_worker_calls=int(merged.get("max_worker_calls") or 20),
                plan_revise_limit=int(merged.get("plan_revise_limit") or 3),
                dispatch_mode=str(merged.get("dispatch_mode") or "batch_parallel"),
                honor_canvas_hint=bool(merged.get("honor_canvas_hint")),
                on_node_error=str(merged.get("on_node_error") or "continue"),
                stream=True,
                max_context_tokens=int(merged.get("max_context_tokens") or 25600),
            )
        except (TypeError, ValueError):
            return cls()
