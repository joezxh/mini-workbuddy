# Task 8 Report: execute() 接线（bus / 主记录 / 超时熔断）

**Status:** DONE
**Branch:** feature/agent-event-p0
**Commit:** 8f6a765 `feat(agent): execute() 接线 EventBus/主记录/总超时熔断`

## What Was Done

### TDD Flow
1. **RED:** Wrote `backend/tests/unit/test_skill_execution_timeout.py` per brief Step 1 (event constructors verified against installed agentscope — `ReplyStartEvent`/`ReplyEndEvent` take `reply_id`/`session_id`, same as Task 7's field check). Ran → **2 failed**:
   - `test_timeout_emits_interrupt_events_and_marks_cancelled` — AttributeError: module has no attribute `SessionLocal` (old code used function-internal import) + old execute() had no timeout/bus.
   - `test_normal_run_calls_start_and_done` — same + old handler's out_q never drained (no `done` SSE).
2. **GREEN:** Rewrote `execute()` per brief Step 3 + implementation notes. Ran → **2 passed**.
3. **Full suite:** `python -m pytest tests/unit -q` → **123 passed, 1 warning, 1 error**.

### Implementation Details (execution.py)
- **Bus wiring (Task 7 carry-over #2):** `self.bus = EventBus(event_service=self.event_service)` then `self.bus.execution_id = execution_id; self.bus.trace_id = trace_id` — handler prefers these over its uuid fallback, so envelopes carry correct IDs. `__init__` gains `self.bus: EventBus | None = None`.
- **out_q bridge (Task 7 carry-over #1):** `SkillEventHandler(skill_name, bus=self.bus, out_q=out_q)`; consumer task `_consume()` feeds `agent.reply_stream` → handler; main `while True` loop pulls from out_q with `asyncio.wait_for(asyncio.shield(out_q.get()), timeout=remaining)` and **yields each event** — agent SSE output is no longer dropped.
- **主记录 lifecycle:** `record_execution_start(...)` (with trace_id) at start; done/failed at end per path. Skill-not-found path guards `if _record_db is not None` before `record_execution_failed` (avoids noisy warnings when SessionLocal patched to None).
- **Timeout 熔断:** absolute `deadline = time.monotonic() + self.timeout`; loop breaks when consumer done AND queue empty; TimeoutError/remaining<=0 → `timed_out=True`, `consumer.cancel()`, break. Timeout finale publishes `interrupt_requested` + `interrupted` envelopes (INTERRUPT category, `interrupt_reason="timeout"`), yields "执行超时（>{timeout}s），已熔断" error SSE, and `record_execution_failed(..., interrupt_reason="timeout")` → row marked `status=cancelled, finished_reason=interrupted`.
- **Success flag:** after the while loop — propagate consumer exception first (`raise exc` if not timed_out), then `if not timed_out: _exec_success = True` (per brief's simplified note). `except` branch keeps False.
- **`finally`:** sys.path cleanup only; metrics (`_record_metrics`) + `_record_db.close()` after it, per brief structure.
- **SessionLocal:** moved to module-level `from app.db.database import SessionLocal` (import-time safe — engine creation is lazy, no connection at import), so both `exec_mod.SessionLocal` and `app.db.database.SessionLocal` patch targets are effective (latter for `_load_skill`/`_record_metrics` which keep function-internal imports).
- **Not added (deferred to later tasks as instructed):** AgentRunRegistry registration (Task 9), hitl pause/resume control plane (Task 10), mode routing after AGENT_START (Task 11), `record_execution_status` (Task 10).
- Removed now-unused `ExecutionEventType` from the top import (execute() no longer uses `event_service.record` directly; envelope path replaced it).

## Verification

| Command | Result |
|---|---|
| `python -m pytest tests/unit/test_skill_execution_timeout.py -v` (RED) | 2 failed ✓ |
| `python -m pytest tests/unit/test_skill_execution_timeout.py -v` (GREEN) | 2 passed |
| `python -m pytest tests/unit -q` | 123 passed, 1 warning, 1 error |

### Pre-existing error (NOT caused by this task)
`tests/unit/test_voice_services.py::test_create_and_append` errors at **setup** with psycopg2 `OperationalError` connecting to `postgresql://localhost:5432/miniworkbuddy` — local PostgreSQL is not running in this environment. Verified pre-existing by stashing execution.py changes and re-running the full suite at HEAD: **121 passed + same 1 error** (= baseline 122 total). With this task's changes: 121 + 2 new = **123 passed + same 1 pre-existing error**. No regression.

## Self-Review Checklist
- [x] Timeout path emits interrupt events + marks cancelled (interrupt_reason=timeout)
- [x] Normal path calls start→done (test asserts exact order)
- [x] out_q events actually yielded (main loop drains queue — Task 7 carry-over fixed)
- [x] bus IDs correct (explicit execution_id/trace_id set on bus)
- [x] Consumer exception propagated (re-raised when not timed_out)
- [x] Only brief-listed files committed (execution.py + test file)

## Deviations
None — plan executed as written, with the ambiguities resolved exactly per the task instructions (module-level SessionLocal import; `_exec_success` after loop; None-guard on skill-not-found record call).

---

# Task 8 审查修复报告（Review Fix）

**Date:** 2026-10-28
**Scope:** `backend/app/ai/skills/execution.py` + `backend/tests/unit/test_skill_execution_timeout.py`
**Findings fixed:** Important×2 + Minor×4

## What Changed (execution.py)

### Important-1: 收尾段移入 finally（GeneratorExit 路径主记录永久 running + DB 会话泄漏）
- 将整个执行主体（skill 加载 → sys.path 注入 → Agent 循环）包进外层 `try/finally`；原 try/finally 之后的直行收尾段（interrupt 双信封 + `record_execution_failed/done` + `_record_metrics` + `_record_db.close()`）全部移入 `finally`（位于 sys.path 清理之后）。
- 客户端断连（`aclose()` → GeneratorExit，BaseException，不被 `except Exception` 捕获）时 finally 仍执行 → 主记录收尾为 failed、metrics 记录、DB 会话关闭。
- 超时 SSE `yield SkillEvent(type="error", ...)` **保留在 finally 之外**（try 内、循环 break 之后）——GeneratorExit 传播期间禁止在 finally 内 yield；断连路径不 emit 该 SSE（可接受，DB 记录才是关键）。
- `consumer`/`handler`/`timed_out`/`_error_text`/`_finalized` 在 try 之前初始化（finally 中可安全引用）。
- finally 中对仍在运行的 consumer 任务做 `consumer.cancel()`（尽力而为，不 await）——断连时不再泄漏孤儿任务。

### Important-2: skill-not-found 早退泄漏 DB 会话 + 跳过 metrics
- 早退分支不再直接 `record_execution_failed(...)` 后裸 `return`；改为设置 `_error_text = f"技能不存在：{skill_name}"` 后 `return`，由统一 `finally` 完成 record failed + metrics + close。
- `_finalized` 标志保证 `record_execution_done/failed` 每次执行**恰好一次**。

### Minor-2: consumer.cancel() 后未 await
- 两个超时分支（`remaining <= 0` 与 `except asyncio.TimeoutError`）在 `consumer.cancel()` 后增加 `await asyncio.gather(consumer, return_exceptions=True)`。

### Minor-3: 完成与超时同时到达的边界
- 两个超时分支在置 `timed_out = True` 之前先复查 `if consumer.done() and out_q.empty(): break` —— 正常完成优先。

### Minor-4: 异常路径 DB 记录无错误内容
- `except Exception as e` 分支记录 `_error_text = str(e)`（try 前初始化为 None），finally 中 `record_execution_failed(..., error=_error_text, ...)`。

### 保持不变
- execute() 公共签名、SSE 事件类型值、record_execution_* 调用语义（超时 → interrupt 双信封 + `interrupt_reason="timeout"` → status=cancelled）；未引入 registry/HITL/mode-routing（Task 9-11 范围）。

## What Changed (test file)

- **Minor-1:** `_patch_all` 的假 `EventBus` 构造器改为捕获实例（`buses` 列表并返回）；超时测试新增断言 `{e.event_type for e in buses[-1].published} >= {"interrupt_requested", "interrupted"}`。
- **Minor-5:** 删除未使用的 `import pytest`；删除冗余 `monkeypatch.setattr(svc, "timeout", ...)`（构造器已设置，`_patch_all` 的 `timeout` 参数一并移除，单一事实来源）。
- **新增测试 `test_client_disconnect_finalizes_record`：** 消费 start/progress 两个事件后 `await gen.aclose()` 模拟断连 → 断言 `record_execution_failed` 恰好调用 1 次、无 `done`、metrics 已记录 —— 证明收尾在断连路径运行。
- **新增测试 `test_skill_not_found_finalizes_and_closes`：** 技能不存在早退 → 断言 failed 恰好 1 次 + metrics + FakeDB.close() 被调用（覆盖 Important-2）。

## Test Commands & Output

```
cd backend; python -m pytest tests/unit/test_skill_execution_timeout.py -v
→ 4 passed (test_timeout_emits_interrupt_events_and_marks_cancelled /
           test_normal_run_calls_start_and_done /
           test_client_disconnect_finalizes_record /
           test_skill_not_found_finalizes_and_closes), 1 warning

cd backend; python -m pytest tests/unit -q
→ 125 passed, 1 warning, 1 error
```

**Pre-existing error（非本次引入）:** `tests/unit/test_voice_services.py::test_create_and_append` 在 setup 阶段连接 `postgresql://localhost:5432/miniworkbuddy` 失败（本地 PostgreSQL 未运行）——Task 8 首次交付时已记录为环境性既有错误，与本次修复无关。125 = 原基线 123 + 新增 2 个测试，无回归。

## Fix Status Summary

| Finding | Status |
|---|---|
| Important-1 收尾移入 finally | ✅ fixed |
| Important-2 早退泄漏 DB 会话 | ✅ fixed |
| Minor-1 超时测试未断言 interrupt 双信封 | ✅ fixed |
| Minor-2 cancel 后未 await | ✅ fixed |
| Minor-3 完成/超时竞态 | ✅ fixed |
| Minor-4 异常路径无错误内容 | ✅ fixed |
| Minor-5 测试文件卫生 | ✅ fixed |
