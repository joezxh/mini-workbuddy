"""PipelineExecutor —— SuperAgent Pipeline 编排骨架（Task 1.5）。

组合 Repository + SuperAgentEngine + EffectQueue + SourceRegistry 四个运行时组件：

  start()   — 启动 EffectQueue workers + Source poll loops + resume()
  stop()    — 停止全部后台任务
  resume()  — 崩溃恢复：扫描未终态 Ticket（open/working/waiting_hitl/waiting_person）重新入队 launch effect

完整 Effect 主循环（6 kind handler + 指数退避）见 effects.EffectQueue；
本类只做生命周期编排，不复制调度逻辑。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from .repository import SuperAgentRepository


# resume 时视为「需要恢复执行」的 Ticket 状态（Task 3.6：未终态全部恢复）
RESUMABLE_TICKET_STATUSES = ("open", "working", "waiting_hitl", "waiting_person")


class PipelineExecutor:
    """Pipeline 主循环编排 —— EffectQueue worker 与 Source polling 的组合点。"""

    def __init__(self, repo: SuperAgentRepository, engine: Any | None = None,
                 queue: Any | None = None, registry: Any | None = None,
                 workspace_id: int = 1):
        self.repo = repo
        self.engine = engine
        self.queue = queue
        self.registry = registry
        self.workspace_id = workspace_id
        self._started = False
        self._resumed: set[str] = set()  # 本进程已恢复过的 ticket，防重复入队

    async def start(self) -> None:
        """启动 Pipeline：EffectQueue workers + Source poll loops，随后恢复遗留 Ticket。"""
        if self._started:
            return
        self._started = True
        if self.queue is not None:
            await self.queue.start()
        if self.registry is not None:
            await self.registry.start_all_polling(self.workspace_id, engine=self.engine)
        resumed = await self.resume()
        logger.info(f"PipelineExecutor started · resumed={resumed}")

    async def stop(self) -> None:
        """停止全部后台任务（幂等）。"""
        if not self._started:
            return
        self._started = False
        if self.registry is not None:
            await self.registry.stop_all_polling()
        if self.queue is not None:
            await self.queue.stop()
        logger.info("PipelineExecutor stopped")

    async def resume(self) -> int:
        """崩溃恢复 —— 扫描未终态 Ticket（open/working/waiting_hitl/waiting_person），
        逐个重新入队 launch effect（Task 3.6 / TR-3.3）。

        幂等：同一 Ticket 本进程内只恢复一次。

        Returns:
            本次重新入队的 Ticket 数量。
        """
        if self.queue is None:
            return 0
        pending_ticket_ids: list[str] = []

        with self.repo.atomic() as db:
            for status in RESUMABLE_TICKET_STATUSES:
                tickets = self.repo.list_tickets(
                    db, workspace_id=self.workspace_id, status=status, limit=100,
                )
                for ticket in tickets:
                    if ticket.id in self._resumed:
                        continue
                    pending_ticket_ids.append(ticket.id)

        for ticket_id in pending_ticket_ids:
            self._resumed.add(ticket_id)
            await self.queue.enqueue(
                workspace_id=self.workspace_id,
                kind="launch",
                ticket_id=ticket_id,
                payload={"ticket_id": ticket_id, "resumed": True},
            )
        if pending_ticket_ids:
            logger.info(
                f"PipelineExecutor.resume · 重新入队 {len(pending_ticket_ids)} 个 "
                f"open Ticket 的 launch effect"
            )
        return len(pending_ticket_ids)
