# Task 4 Report: ExecutionEventService 支持 envelope 与级别过滤

**Status:** DONE
**Commit:** `58f2877` — `feat(agent): 事件服务支持信封分级写入，delta 停止落库`
**Branch:** `feature/agent-event-p0`

## Implementation

修改 `backend/app/ai/services/execution_event_service.py`（单文件）+ 新增测试 `backend/tests/unit/test_execution_event_service.py`。

1. **Import**（顶部）：新增 `from app.schemas.agent.event_types import (EventEnvelope, EventLevel, normalize_event_type, route_of)`。
2. **`record()` 重写（签名不变）**：事件值先经 `normalize_event_type()` 归一化（如 `text` → `text_chunk`），再查 `route_of()` 路由，构造 `EventEnvelope` 后走 `record_envelope()`；`async_write=False` 同步路径改为「仅 DB 级才写」（原为无条件写库，grep 确认当前无 `async_write=False` 调用方）。
3. **新增 `record_envelope(envelope)`**：`EventLevel.DB not in envelope.levels` → 仅 loguru debug 日志、不入队（delta 停止落库）；含 DB 级 → 分配 sequence、`_envelope_to_row()` 转行 dict、append 到 `_events`、`start()` 启动 writer、入队。
4. **新增 `_envelope_to_row(envelope, seq=None)`**：行 dict 含 DDL 47 新列（`level`/`category`/`reply_id`/`block_id`/`tool_call_id`/`interrupt_reason`/`ui_hint`/`event_version`），`level = min(levels)`，`sequence` 缺省时取 `self.sequence`。
5. **`_batch_write_sync` ORM 映射扩展**：构造 `AgentExecutionEvent` 时补齐全部新列（`event.get(...)` 容错），`event_version` 缺省 1。ORM 模型已有对应列（前序任务完成，`app/models/agent/agent_execution_event.py:43-50`）。

## TDD Evidence

- **RED**（实现前运行）：
  - `test_record_envelope_skips_db_for_stream_only` / `test_record_envelope_enqueues_db_level_with_new_columns` / `test_legacy_record_normalizes_and_filters` → `AttributeError: record_envelope`（及 category 等新键缺失）
  - `test_batch_write_sync_maps_new_columns` → `AttributeError: 'FakeEventORM' object has no attribute 'reply_id'`
  - 汇总：`4 failed, 2 warnings` ✅ 符合预期失败
- **GREEN**（实现后运行）：
  - `python -m pytest tests/unit/test_execution_event_service.py -v` → **4 passed**
  - `python -m pytest tests/unit -q` → **106 passed**（基线 102 + 新增 4，零回归；全量套件未触碰已知的 `app/ai/skills/execution.py` 语法错误文件）

## Files

- Modified: `backend/app/ai/services/execution_event_service.py`（+133/-34）
- Added: `backend/tests/unit/test_execution_event_service.py`（93 行，与 brief Step 1 逐字一致）

## Deviations from Brief（均为 Rule 1，测试为准）

1. **`_put_row()` 同 loop 直接入队**：brief 的 `record_envelope` 无条件 `call_soon_threadsafe(self._safe_put, row)`，但该回调要等事件循环取回控制权才执行——brief 测试在 `asyncio.run(main())` 协程内同步断言 `_queue.qsize() == 1`，会失败。新增 `_put_row()`：当前运行 loop 即 `_owning_loop` 时直接 `put_nowait`（同线程安全）；跨线程/其它 loop 时仍走 `call_soon_threadsafe`；loop 不可用时降级丢弃。原 `record()` 的跨线程语义（to_thread 工作线程调用）完整保留。
2. **行 dict 增加 `levels` 键**：brief 的 `_envelope_to_row` 实现未输出 `levels`，但测试断言 `EventLevel.DB in row["levels"]`。补 `"levels": list(levels)`（`_batch_write_sync` 不读该键，无副作用）。

## Self-Review

- ✅ **队列 + 单 writer 批量架构未动**：`_drain_loop` / `_flush_batch` / `start` / `stop` / `flush` / `_safe_put` / `_write_event_sync` 全部原样；`record_envelope` 仅替换原 `record()` 内部的入队段。
- ✅ **`record()` 签名不变**：6 个参数（名称/类型/默认值）与原来完全一致；返回注解 `int → Optional[int]`（no-DB 路径返回 None），现存调用方（run_collector.py / execution.py）不受影响。
- ✅ **delta 过滤双路径生效**：legacy `record('text')` 归一化为 `text_chunk` → 仅 STREAM → 不落库；`record_envelope()` 直接收 STREAM-only envelope → 不落库。`team_start` 等存量事件仍落库。
- ✅ 提交仅含两个目标文件，无意外删除（`git diff --diff-filter=D` 为空）。
- ⚠️ 已知（预期内）：`app/ai/skills/execution.py` 语法错误仍存在，Task 7 修复；本任务测试未 import 它，全量套件照旧通过。

## Metrics

- Duration: ~15 min
- Tests: 4 new (4 passed), full suite 106 passed / 0 failed
