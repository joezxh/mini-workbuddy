# Task 5 Report: EventBus（Log + DB 双 handler）

**Status:** DONE
**Date:** 2026-09-21
**Branch:** feature/agent-event-p0
**Commit:** 2445846 — `feat(agent): EventBus 观察者分发（LOG+DB handler，异常隔离）`

## Files Created (3, nothing else modified)

| File | Purpose |
|------|---------|
| `backend/app/ai/events/__init__.py` | Package init, one-line docstring `"""Agent 事件总线包。"""` |
| `backend/app/ai/events/bus.py` | `EventBus` class (42 lines) |
| `backend/tests/unit/test_event_bus.py` | 3 unit tests |

## TDD Execution

1. **RED:** Wrote `test_event_bus.py` verbatim from brief. Ran → `ModuleNotFoundError: No module named 'app.ai.events'` (as expected).
2. **GREEN:** Implemented `__init__.py` + `bus.py` per brief Step 3. Import-merge note honored: `from typing import Any, Optional` as ONE top import line, no trailing `from typing import Any`.
3. **Fix iteration (Rule 1 auto-fix):** First GREEN run failed `test_log_only_does_not_hit_db` — the brief's reference `publish()` delegates to `event_service` unconditionally whenever it's set, so a LOG-only envelope reached the (non-filtering) FakeEventService. Fixed by adding a DB-level guard before delegation:
   ```python
   if self._event_service is not None and EventLevel.DB in envelope.levels:
   ```
   Evidence this was the brief's intent (not scope creep): the brief's reference code already imports `EventLevel` from `app.schemas.agent.event_types` — that import is otherwise unused without this check. Also consistent with the brief's own comment "service 内部会再次校验 DB 级并过滤" (the real `ExecutionEventService.record_envelope` re-filters; the bus-side check is the same contract, applied before the call). Re-run → 3/3 PASS.
4. **Full suite:** `python -m pytest tests/unit -q` → **109 passed, 1 warning** (106 baseline + 3 new; the 1 warning is the pre-existing SQLAlchemy `declarative_base` deprecation — expected, untouched).

## Self-Review

- **Handler exception isolation:** DB handler call wrapped in `try/except Exception` → `logger.opt(exception=True).warning(...)`. Failure never propagates to the publish caller. Log handler (loguru debug) executes for EVERY envelope before DB dispatch, and loguru does not raise on logging.
- **No extra features beyond P0 scope:** No subscribe/unsubscribe API, no async, no SSE/UI handling, no batching. Constructor takes optional `event_service` only.
- **Level check placement:** bus checks `EventLevel.DB in envelope.levels` (cheap, correct); real service re-validates internally per Task 4 — double guard is intentional defense-in-depth, both layers tested independently.
- **Third test** (`test_publish_always_debug_logs`) implemented exactly as written in the brief — minimal by design (no-exception smoke check).

## Deviations

- **[Rule 1 - Bug] Added `EventLevel.DB in envelope.levels` guard in `publish()`**
  - Found during: TDD GREEN step (test 2 failure)
  - Issue: brief's reference code delegated all envelopes to `event_service`; test expects LOG-only events not to reach the service; the Fake in the test does not filter.
  - Fix: one-line guard before delegation (see above). The otherwise-unused `EventLevel` import in the brief confirms this was the intended behavior.
  - Files: `backend/app/ai/events/bus.py`
  - Commit: 2445846

## Test Summary

- `tests/unit/test_event_bus.py`: 3 passed (`test_db_level_delegates_to_service`, `test_log_only_does_not_hit_db`, `test_publish_always_debug_logs`)
- Full unit suite: 109 passed, 1 pre-existing warning, 0 failures, 0 regressions.

## Notes for Downstream Tasks (Task 6/7)

- `EventBus(event_service=...)` is now importable from `app.ai.events.bus`; wiring happens in `execute()` / `SkillEventHandler` in later tasks.
- LOG-only events (e.g. `model_call`, `context_compressed`) are debug-logged but never sent to the DB service by the bus — matches the spec's DB-row-reduction goal.
- Working tree contains unrelated in-flight changes (skill-file-tree feature); only the three task files were staged/committed.
