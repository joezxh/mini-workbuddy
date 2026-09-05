"""Skill Metrics 采集中间件 - 基于 AgentScope MiddlewareBase。

在工具执行（on_acting）完成后，自动更新 ai_skill_metrics 表：
- execution_count += 1
- success_rate 滑动平均
- avg_latency 滑动平均

与 EvolutionEngine 的评估逻辑对接：metrics 数据驱动进化决策。
"""
from __future__ import annotations

import logging
import time

from agentscope.middleware import MiddlewareBase

logger = logging.getLogger(__name__)

# 滑动平均窗口（用于计算 success_rate / avg_latency）
_WINDOW_SIZE = 100


class SkillMetricsMiddleware(MiddlewareBase):
    """Skill 执行指标采集中间件。

    在 on_acting 钩子中：
    1. 记录工具执行开始时间
    2. 执行完成后计算耗时
    3. 更新 ai_skill_metrics 表（execution_count / success_rate / avg_latency）

    用法::

        middleware = SkillMetricsMiddleware(db=session)
        # 注册到 Agent 的 middleware 列表
    """

    def __init__(
        self,
        db=None,
        skill_id_resolver=None,
    ):
        """初始化。

        Args:
            db: SQLAlchemy Session（同步）
            skill_id_resolver: 可选回调 (tool_name) -> skill_id
                用于将工具名映射到 skill_id。默认使用 tool_name 本身。
        """
        self.db = db
        self._skill_id_resolver = skill_id_resolver or (lambda name: name)

    async def on_acting(self, agent, input_kwargs, next_handler):
        """工具执行指标采集。"""
        tool_call = input_kwargs.get("tool_call") or {}
        tool_name = tool_call.get("name", "unknown")
        skill_id = self._skill_id_resolver(tool_name)

        start_time = time.perf_counter()
        success = True

        try:
            result = await next_handler(input_kwargs)
            return result
        except Exception:
            success = False
            raise
        finally:
            elapsed = time.perf_counter() - start_time
            self._update_metrics(skill_id, success, elapsed)

    def _update_metrics(self, skill_id: str, success: bool, elapsed: float) -> None:
        """更新 ai_skill_metrics 表（滑动平均）。"""
        if self.db is None:
            return

        try:
            from app.models.ai.ai_skill_metrics import AiSkillMetrics

            metrics = (
                self.db.query(AiSkillMetrics)
                .filter(AiSkillMetrics.skill_id == skill_id)
                .first()
            )

            if metrics is None:
                # 首次记录
                metrics = AiSkillMetrics(
                    skill_id=skill_id,
                    execution_count=1,
                    success_rate=1.0 if success else 0.0,
                    avg_latency=elapsed,
                    user_rating=0.0,
                )
                self.db.add(metrics)
            else:
                # 滑动平均更新
                count = int(metrics.execution_count or 0)
                new_count = count + 1

                # success_rate: 滑动平均
                old_sr = float(metrics.success_rate or 0.0)
                new_sr = (old_sr * min(count, _WINDOW_SIZE) + (1.0 if success else 0.0)) / min(new_count, _WINDOW_SIZE)

                # avg_latency: 滑动平均
                old_latency = float(metrics.avg_latency or 0.0)
                new_latency = (old_latency * min(count, _WINDOW_SIZE) + elapsed) / min(new_count, _WINDOW_SIZE)

                metrics.execution_count = new_count
                metrics.success_rate = round(new_sr, 4)
                metrics.avg_latency = round(new_latency, 4)

            self.db.commit()
            logger.debug(
                "skill metrics updated: %s (success=%s, elapsed=%.3fs)",
                skill_id, success, elapsed,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to update skill metrics for %s: %s", skill_id, exc)
            try:
                self.db.rollback()
            except Exception:  # noqa: BLE001
                pass

    def get_middleware_key(self) -> str:
        return "skill_metrics"
