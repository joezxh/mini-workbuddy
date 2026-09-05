"""AgentScope 团队编排器 — 基于 AgentScope 原生 Team API 的多 Agent 协作。

TODO: 完整实现待 AgentScope Team API 稳定后接入。
当前为骨架 stub，提供接口兼容层供 agent_team router 调用。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 全局编排器注册表（供干预端点触达运行中的编排器实例）
ORCHESTRATOR_REGISTRY: Dict[str, "AgentScopeOrchestrator"] = {}


class AgentScopeOrchestrator:
    """AgentScope 团队编排器。

    负责：
    1. 加载团队成员与配置
    2. 创建 Leader Agent（动态派发任务给 Worker）
    3. 运行团队并收集结果
    4. 支持运行态干预（暂停/恢复/取消/注入消息）

    TODO: 完整实现待 AgentScope Team API 稳定后接入。
    """

    def __init__(
        self,
        db: Any,
        team: Any,
        run: Any,
        event_svc: Any = None,
        user_id: Optional[int] = None,
        profile: Any = None,
        model_id: Optional[int] = None,
    ):
        self.db = db
        self.team = team
        self.run = run
        self.event_svc = event_svc
        self.user_id = user_id
        self.profile = profile
        self.model_id = model_id
        self._paused = False

    async def submit(
        self,
        input_text: str,
        input_context: Optional[dict] = None,
        created_by: Optional[int] = None,
    ) -> str:
        """提交团队运行任务并返回最终结果。

        TODO: 实现 AgentScope Team API 集成。
        当前返回 stub 响应。
        """
        team_code = getattr(self.team, "team_code", "unknown")
        logger.info(f"[Orchestrator] 团队 {team_code} 提交运行 (stub)")

        # 注册到全局注册表（供干预端点使用）
        run_id = getattr(self.run, "run_id", str(id(self)))
        ORCHESTRATOR_REGISTRY[run_id] = self

        try:
            # TODO: 实际编排逻辑
            # 1. 创建 Leader Agent
            # 2. 根据 profile.dispatch_mode 派发任务给 Worker
            # 3. 收集 Worker 结果
            # 4. Leader 汇总并输出最终结论
            return (
                f"团队 {team_code} 编排器已就绪（stub 模式）。"
                f"输入：{input_text[:100]}... "
                "完整编排待 AgentScope Team API 接入后实现。"
            )
        finally:
            ORCHESTRATOR_REGISTRY.pop(run_id, None)

    def request_pause(self) -> None:
        """请求暂停运行。"""
        self._paused = True
        logger.info("[Orchestrator] 收到暂停请求")

    def resume(self) -> None:
        """恢复运行。"""
        self._paused = False
        logger.info("[Orchestrator] 收到恢复请求")
