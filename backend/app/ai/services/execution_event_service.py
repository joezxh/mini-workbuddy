"""AgentExecutionEventService - 执行事件日志记录服务

用于 Skill 和 Agent 执行过程中的事件日志记录，确保所有事件
都记录到统一的 agent_execution_event 表中。

架构：队列 + 单 writer + 批量写入
- record() 将事件放入 asyncio.Queue（O(1)，不阻塞 SSE 流）
- 单一后台 _drain_loop 从队列取事件，批量 flush 到 DB
- 每次 flush 使用一个 session，批量 INSERT 后统一 commit
- 避免每事件创建独立 session 导致的连接池耗尽 / 死循环重置
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional

from loguru import logger

from app.db.database import SessionLocal
from app.models.agent.agent_execution_event import AgentExecutionEvent
from app.schemas.agent.event_types import (
    EventEnvelope, EventLevel, normalize_event_type, route_of,
)


# ── 批量写入配置 ──────────────────────────────────────────────────────────────
_BATCH_SIZE = 50          # 每批最多处理事件数
_DRAIN_INTERVAL = 0.5     # 队列排空间隔（秒），平衡延迟与吞吐
_QUEUE_MAX_SIZE = 2000    # 队列上限，防止内存溢出
_BATCH_TIMEOUT = 2.0      # 即使未满，超过此秒数也强制 flush


class ExecutionEventService:
    """执行事件日志记录服务

    提供统一的接口用于记录 Skill 和 Agent 执行过程中的所有事件。
    内部使用队列缓冲 + 单 writer 批量写入，避免连接池耗尽。
    """

    SKILL_AGENT_CONFIG_ID = 0

    def __init__(
        self,
        execution_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        agent_config_id: Optional[int] = None,
        agent_code: Optional[str] = None,
        session_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> None:
        self.execution_id = execution_id or str(uuid.uuid4())
        self.trace_id = trace_id or str(uuid.uuid4())
        self.agent_config_id = agent_config_id or self.SKILL_AGENT_CONFIG_ID
        self.agent_code = agent_code or "dynamic_skill_agent"
        self.session_id = session_id
        self.user_id = user_id
        self._sequence = 0
        self._events: list[dict[str, Any]] = []

        # ── 队列 + 单 writer 架构 ──
        # 捕获创建本服务时的事件循环（主请求循环），drain loop 必须运行在此循环上，
        # 否则 asyncio.Queue「绑定到不同事件循环」会抛 RuntimeError。
        # record() 可能在 asyncio.to_thread 的工作线程（含新事件循环）中被调用，
        # 此时需用 call_soon_threadsafe 把 drain task 的创建调度回主循环。
        try:
            self._owning_loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_event_loop()
        except RuntimeError:
            self._owning_loop = None
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAX_SIZE)
        self._drain_task: Optional[asyncio.Task] = None
        self._stopped = False

    # ── 生命周期 ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """启动后台 writer（在首次 record 时自动调用）

        保证 drain task 始终创建在 _owning_loop（即队列所绑定的事件循环）上，
        即使本方法在线程池 / 新事件循环中被调用。
        """
        if self._drain_task is not None and not self._drain_task.done():
            return

        def _spawn() -> None:
            # 此回调运行在 _owning_loop 上
            if self._drain_task is None or self._drain_task.done():
                self._stopped = False
                self._drain_task = asyncio.create_task(
                    self._drain_loop(), name=f"event-writer-{self.execution_id[:8]}"
                )

        loop = self._owning_loop or asyncio.get_event_loop()
        if loop.is_closed():
            return
        if loop.is_running():
            # 可能不在 _owning_loop 上（如在 to_thread 的新循环中），切回主循环创建 task
            loop.call_soon_threadsafe(_spawn)
        else:
            _spawn()

    async def stop(self) -> None:
        """停止 writer，flush 剩余事件后关闭"""
        self._stopped = True
        # 等待队列排空
        if self._drain_task and not self._drain_task.done():
            # 给 drain_loop 一些时间排空
            try:
                await asyncio.wait_for(self._drain_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._drain_task.cancel()
                logger.warning("Event writer 排空超时，强制取消: {}", self.execution_id[:8])
            self._drain_task = None

    async def flush(self) -> None:
        """等待所有待写入事件完成"""
        if not self._queue.empty():
            # 等待队列排空
            for _ in range(100):  # 最多等 10s
                if self._queue.empty():
                    break
                await asyncio.sleep(0.1)
        # 确保最后一批被写入
        await self._flush_batch(force=True)

    # ── 事件记录 ──────────────────────────────────────────────────────────────

    @property
    def sequence(self) -> int:
        seq = self._sequence
        self._sequence += 1
        return seq

    def record(
        self,
        event_type: str,
        content: Optional[dict[str, Any]] = None,
        source: Optional[str] = None,
        source_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        async_write: bool = True,
    ) -> Optional[int]:
        """记录事件（兼容入口）。

        事件值先经 LEGACY_ALIAS 归一化，再按 DEFAULT_ROUTES 分级：
        仅 STREAM 的 delta 类不再落库（spec §4.2）。
        """
        etype = normalize_event_type(event_type)
        route = route_of(etype)
        envelope = EventEnvelope(
            execution_id=self.execution_id,
            trace_id=self.trace_id,
            event_type=etype,
            category=route.category,
            levels=sorted(route.levels),
            content=content or {},
            source=source or "skill_execution",
            source_id=source_id,
            ui_hint=route.ui_hint,
            metadata=metadata or {},
        )
        if async_write is False:
            # 同步路径：仅当需要落库时写
            if EventLevel.DB in route.levels:
                self._write_event_sync(self._envelope_to_row(envelope))
            return None
        return self.record_envelope(envelope)

    def record_envelope(self, envelope: EventEnvelope) -> Optional[int]:
        """按信封级别分发：含 DB 级才入队，否则仅结构化日志。"""
        if EventLevel.DB not in (envelope.levels or []):
            logger.debug(
                "event[{}] {} -> no-DB (levels={})",
                envelope.execution_id[:8], envelope.event_type, envelope.levels,
            )
            return None
        seq = self.sequence
        row = self._envelope_to_row(envelope, seq)
        self._events.append(row)
        self.start()
        self._put_row(row, seq)
        return seq

    def _put_row(self, row: dict[str, Any], seq: int) -> None:
        """将行放入队列。

        - 当前运行 loop 即 owning loop（同线程）：直接 put，立即对
          ``queue.qsize()`` 可见；
        - 在其它线程 / 其它 loop（如 asyncio.to_thread 的新循环）中：
          经 call_soon_threadsafe 调度回 owning loop；
        - owning loop 不可用：降级 put_nowait，失败则丢弃。
        """
        try:
            current_loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is not None and current_loop is self._owning_loop:
            self._safe_put(row)
            return
        if self._owning_loop is not None and self._owning_loop.is_running():
            try:
                self._owning_loop.call_soon_threadsafe(self._safe_put, row)
            except RuntimeError:
                # loop 已关闭等极端情况：降级丢弃
                logger.warning("事件队列 loop 不可用，丢弃事件 seq={}", seq)
        else:
            try:
                self._queue.put_nowait(row)
            except asyncio.QueueFull:
                logger.warning("事件队列已满（{}），丢弃事件 seq={}", _QUEUE_MAX_SIZE, seq)

    def _envelope_to_row(self, envelope: EventEnvelope, seq: Optional[int] = None) -> dict[str, Any]:
        """信封 → DB 行 dict（含 DDL 47 新列）。"""
        levels = envelope.levels or []
        return {
            "execution_id": envelope.execution_id,
            "trace_id": envelope.trace_id,
            "event_type": envelope.event_type,
            "sequence": seq if seq is not None else self.sequence,
            "content": envelope.content,
            "source": envelope.source,
            "source_id": envelope.source_id,
            "metadata": envelope.metadata or {},
            "level": min(levels) if levels else None,
            "levels": list(levels),
            "category": envelope.category,
            "reply_id": envelope.reply_id,
            "block_id": envelope.block_id,
            "tool_call_id": envelope.tool_call_id,
            "interrupt_reason": envelope.interrupt_reason,
            "ui_hint": envelope.ui_hint,
            "event_version": envelope.event_version,
        }

    def _safe_put(self, event: dict[str, Any]) -> None:
        """线程安全地放入队列（运行在 owning loop 上）"""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("事件队列已满（{}），丢弃事件", _QUEUE_MAX_SIZE)

    async def record_async(
        self,
        event_type: str,
        content: Optional[dict[str, Any]] = None,
        source: Optional[str] = None,
        source_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        return self.record(
            event_type=event_type,
            content=content,
            source=source,
            source_id=source_id,
            metadata=metadata,
            async_write=True,
        )

    # ── 后台 Writer ──────────────────────────────────────────────────────────

    async def _drain_loop(self) -> None:
        """后台循环：从队列中取事件，批量写入数据库"""
        batch: list[dict[str, Any]] = []
        last_flush_time = asyncio.get_event_loop().time()

        while not self._stopped or not self._queue.empty():
            try:
                # 非阻塞取事件
                try:
                    event = self._queue.get_nowait()
                    batch.append(event)
                except asyncio.QueueEmpty:
                    # 队列为空，等待一小段时间或超时
                    try:
                        event = await asyncio.wait_for(self._queue.get(), timeout=_DRAIN_INTERVAL)
                        batch.append(event)
                    except asyncio.TimeoutError:
                        pass

                now = asyncio.get_event_loop().time()

                # 批量 flush 条件：达到批次大小 或 超过超时时间
                if len(batch) >= _BATCH_SIZE or (batch and (now - last_flush_time) >= _BATCH_TIMEOUT):
                    await self._flush_batch(batch)
                    batch = []
                    last_flush_time = now

                # 让出控制权，避免饿死其他协程
                await asyncio.sleep(0)

            except asyncio.CancelledError:
                # 被取消时，尝试 flush 剩余事件
                if batch:
                    await self._flush_batch(batch)
                break
            except Exception as e:
                logger.opt(exception=True).error("drain_loop 异常: {}", e)
                await asyncio.sleep(1)  # 异常后短暂等待，避免紧密循环

        # 最终 flush
        if batch:
            await self._flush_batch(batch)

    async def _flush_batch(self, batch: Optional[list[dict[str, Any]]] = None, force: bool = False) -> None:
        """将一批事件批量写入数据库"""
        if batch is None:
            return

        if not batch and not force:
            return

        events_to_write = list(batch)
        if not events_to_write:
            return

        try:
            await asyncio.to_thread(self._batch_write_sync, events_to_write)
        except Exception as e:
            logger.opt(exception=True).error(
                "批量写入执行事件失败 ({} 条): {}",
                len(events_to_write), e,
            )

    def _batch_write_sync(self, events: list[dict[str, Any]]) -> None:
        """同步批量写入事件到数据库（在 to_thread 中执行）"""
        db = SessionLocal()
        try:
            for event in events:
                db_event = AgentExecutionEvent(
                    execution_id=event["execution_id"],
                    trace_id=event.get("trace_id"),
                    event_type=event["event_type"],
                    sequence=event["sequence"],
                    content=event.get("content"),
                    source=event.get("source"),
                    source_id=event.get("source_id"),
                    event_metadata=event.get("metadata"),
                    level=event.get("level"),
                    category=event.get("category"),
                    reply_id=event.get("reply_id"),
                    block_id=event.get("block_id"),
                    tool_call_id=event.get("tool_call_id"),
                    interrupt_reason=event.get("interrupt_reason"),
                    ui_hint=event.get("ui_hint"),
                    event_version=event.get("event_version") or 1,
                )
                db.add(db_event)
            db.commit()
            logger.debug("批量写入 {} 条执行事件成功", len(events))
        except Exception as e:
            logger.opt(exception=True).error(
                "批量写入执行事件失败 ({} 条): {} | 首条 event_type={}",
                len(events), e,
                events[0].get("event_type") if events else "N/A",
            )
            db.rollback()
            raise
        finally:
            db.close()

    # ── 兼容：单条同步写入（用于 fallback 或直接调用） ─────────────────────

    def _write_event_sync(self, event: dict[str, Any]) -> None:
        """同步写入单条事件到数据库（仅在 async_write=False 时使用）"""
        self._batch_write_sync([event])

    # ── 查询接口 ──────────────────────────────────────────────────────────────

    def get_events(self) -> list[dict[str, Any]]:
        """获取已记录的事件列表（内存中的完整列表）"""
        return self._events.copy()

    def clear(self) -> None:
        """清空事件缓存"""
        self._events.clear()
        self._sequence = 0
        # 清空队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break


# ── 便捷函数 ──────────────────────────────────────────────────────────────────

_event_services: dict[str, ExecutionEventService] = {}


def get_event_service(execution_id: str) -> Optional[ExecutionEventService]:
    """获取已存在的执行事件服务实例"""
    return _event_services.get(execution_id)


def create_event_service(
    execution_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    **kwargs,
) -> ExecutionEventService:
    """创建新的执行事件服务实例"""
    service = ExecutionEventService(
        execution_id=execution_id,
        trace_id=trace_id,
        **kwargs,
    )
    if execution_id:
        _event_services[execution_id] = service
    return service


async def stop_event_service(execution_id: str) -> None:
    """停止并移除执行事件服务实例"""
    service = _event_services.pop(execution_id, None)
    if service:
        await service.stop()


def remove_event_service(execution_id: str) -> None:
    """同步移除执行事件服务实例（不等待 writer 停止）"""
    _event_services.pop(execution_id, None)
