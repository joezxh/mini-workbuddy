# Task 3 Report: 双处删除本地枚举，re-export 单一来源

**Commit:** `530e686` — `refactor(agent): 事件枚举收敛单一来源，schemas/models re-export`
**Branch:** `feature/agent-event-p0` (base 4a71d62)
**Files changed:** 2 files, +5 / −87 lines (only the two brief-listed files committed; working tree contains many unrelated pre-existing modifications that were deliberately left untouched)

## What Was Done

### Step 1: `backend/app/schemas/agent/agent.py`
- Deleted the entire local `class ExecutionEventType(str):` block (old lines 33–73, 41 lines with all members TEXT/THINKING/SKILL_LOAD/AGENT_COMPLETE/AGENT_ERROR/TIMEOUT etc.).
- Added to the top import region (right after `from pydantic import ...`):
  ```python
  from app.schemas.agent.event_types import ExecutionEventType  # noqa: F401 单一权威来源，re-export
  ```

### Step 2: `backend/app/models/agent/agent_execution_event.py`
- Deleted the entire local `class ExecutionEventType(str, Enum):` block (old lines 17–58).
- Removed the now-unused `from enum import Enum` import (verified: no other `Enum` usage remains in the file).
- Added after `from app.models.tenant_mixin import TenantMixin`:
  ```python
  # 事件类型枚举统一取自 schemas 权威模块（spec 2026-09-21 §4.2）。
  # schemas 不依赖 models，此处反向引用无循环风险。
  from app.schemas.agent.event_types import ExecutionEventType  # noqa: F401
  ```

## Verification (Brief Step 3)

### Identity check

Literal brief command:

```
python -c "... assert A is B is C; assert A.TEXT == 'text' and A.TEXT_CHUNK == 'text_chunk'; ..."
```

Result: `A is B is C` **PASSED** (all three import paths resolve to the same class object), but `A.TEXT == 'text'` raised `AttributeError: type object 'ExecutionEventType' has no attribute 'TEXT'`.

**Explanation (expected, not a defect of this task):** the brief's Step 3 assertion was written assuming the canonical enum kept a `TEXT` member. Task 2's authoritative `event_types.py` actually renamed `TEXT`→`TEXT_CHUNK` and `THINKING`→`THINKING_CHUNK`, with legacy *values* (not attributes) handled via `LEGACY_ALIAS`. Per the task instructions, the canonical enum is the authority and old members were NOT re-added. Adapted check that fully passes:

```
python -c "... assert A is B is C; assert A.TEXT_CHUNK == 'text_chunk'; assert normalize_event_type('text') == 'text_chunk'; print('single source ok ...')"
```

Output: `single source ok (identity + text_chunk + alias-normalization)`

### Full unit suite

```
python -m pytest tests/unit -q
→ 102 passed, 1 warning in 4.41s
```

Matches the baseline of 102 passing tests — no regression. Consumers importing via the old paths (`app.schemas.agent.agent`, `app.models.agent.agent_execution_event`) continue to work through re-export.

## Stale-Member Grep Results (report-only)

Grep of `backend/app` for `ExecutionEventType.(TEXT|THINKING|SKILL_LOAD|AGENT_COMPLETE|AGENT_ERROR|HITL_PAUSE|TEAM_*|COMPLETED|FAILED|TIMEOUT|SKILL_COMPLETE)`:

| File | Line | Usage | Exists on canonical enum? |
|------|------|-------|---------------------------|
| `app/ai/team/run_collector.py` | 25 | `ExecutionEventType.TEAM_START` | ✅ yes |
| `app/ai/team/run_collector.py` | 36 | `ExecutionEventType.TEAM_DONE` | ✅ yes |
| `app/ai/team/run_collector.py` | 47 | `ExecutionEventType.TEAM_ERROR` | ✅ yes |
| `app/ai/skills/execution.py` | 101 | `ExecutionEventType.THINKING` | ❌ **NO — renamed THINKING_CHUNK** |
| `app/ai/skills/execution.py` | 113 | `ExecutionEventType.TEXT` | ❌ **NO — renamed TEXT_CHUNK** |

Also grepped `backend/tests`: only one hit, a docstring in `tests/unit/test_event_types.py:29` (Task 2's test, no runtime impact).

**Known/expected (per task context):** `execution.py` is already un-importable due to the `lambda: yield` syntax error and is fully rewritten by Task 7, which will switch it to canonical members. The stale `TEXT`/`THINKING` attribute accesses would surface as `AttributeError` only at runtime once that file becomes importable — no action taken here, exactly as the brief scopes it (only the two files change). All other members used by `execution.py` (SKILL_RESULT/AGENT_START/ERROR/TOOL_CALL/TOOL_RESULT) exist on the canonical enum.

No usages of `SKILL_LOAD`, `AGENT_COMPLETE`, `AGENT_ERROR`, `HITL_PAUSE`, `COMPLETED`, `FAILED`, `TIMEOUT`, or `SKILL_COMPLETE` attributes found anywhere in `backend/app`.

## Self-Review

- ✅ Only the two brief-listed files were modified and committed; the many unrelated dirty files in the working tree were left untouched.
- ✅ `A is B is C` identity holds; single source of truth confirmed.
- ✅ 102/102 unit tests pass (baseline preserved).
- ✅ No tracked-file deletions in the commit (`git diff --diff-filter=D HEAD~1 HEAD` empty).
- ✅ Lints clean on both modified files.
- ⚠️ Minor observations (out of scope, not fixed):
  - `agent_execution_event.py` still imports `datetime` from the stdlib which appears unused — pre-existing, out of scope.
  - `models/agent/agent_execution_event.py` has `from __future__ import annotations`; the re-export works fine under it (verified by the runtime identity check).
  - The brief's Step 3 literal assertion `A.TEXT == 'text'` is stale relative to Task 2's enum design — flagging for the plan author (the plan's 关键约束 #2 also mentions `ExecutionEventType.TEXT == "text"` which no longer holds as an *attribute* access; value-level equality is preserved via LEGACY_ALIAS on the write side only).
- ⚠️ Runtime risk until Task 7: any code path reaching `execution.py` lines 101/113 would hit `AttributeError` — but that module currently fails at import (syntax error) anyway, so no new runtime breakage is introduced by this task.
