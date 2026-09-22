# Task 9 Review: AgentRunRegistry + cancel API

**Base:** `0adf19e` → **Head:** `2080aa0`
**Depth:** deep（跨文件核对 execution.py / registry.py / agent_run.py / router_registry.py / deps.py）
**Files Reviewed:** 5

## Spec Compliance

| 约束 | 结论 |
|---|---|
| 文件范围（3 新建 + 2 修改，不触其他文件） | ✅ diff 恰好 5 个文件 |
| registry.py：RunHandle 字段 / AgentRunRegistry 六方法 / 模块单例 + get_run_registry() | ✅ 与 brief 逐行一致（registry.py:29-95） |
| cancel()：None/done → False，否则记 interrupt_reason + task.cancel() | ✅（registry.py:66-74） |
| cancel API：404 / {ok, execution_id, interrupt_reason:"user_cancel"} | ✅（agent_run.py:12-24）；见 I-02 线程安全问题 |
| execute()：注册 + waiting_hitl 守卫 + finally 统一中断收尾 + unregister 总是执行 | ✅（execution.py:403-411, 481-501, 517-521） |
| 无双重记录（Task 8 exactly-once 保持） | ✅ `_finalized` 守卫 + `timed_out` 优先于 cancel 判定（execution.py:482-486），timeout 与 cancel 撞车只落一条 |
| `_exec_success` 语义守卫（cancel 后不得走成功路径） | ✅ execution.py:439-441 |
| HITL confirm 端点不存在 | ✅ agent_run.py 仅 cancel |
| get_run_registry 模块顶部导入 | ✅（execution.py:29） |
| unregister 在关闭 _record_db 之前 | ✅（execution.py:517-528） |
| 测试 patch `exec_mod.SessionLocal` | ✅（test:435） |
| dispatch #5 `self._run_handle = None` in `__init__` | ⚠️ 偏差：最终代码改用 execute() 内局部变量 `handle`（execution.py:315, 403），全文无 `_run_handle`。**功能等价且更优**（实例字段在 service 复用时会被并发执行覆盖，局部变量无此风险），但报告第 44 行声称"存入 self._run_handle"与实际代码不符 |
| dispatch #3 "user_cancel 路径无 SSE yield" | ⚠️ 偏差（已声明）：实现新增 user_cancel SSE yield（execution.py:447-450，try 体内，finally 之外）。brief Step 1 测试明确断言 SSE 含 `中断` error 事件（test:459），若遵从 dispatch #3 该测试不可能通过——两条指令本身互斥。实现取测试为权威、yield 放 try 体内满足"GeneratorExit 期间 finally 不得 yield"约束，是两害相权下的正确选择，且已实现并测试通过。**建议 controller 确认此裁决** |

**结论：** 核心需求全部落地，两处偏差均已声明且可辩护（其一为两条指令互斥）。

## Strengths

- **关键竞态守卫正确**：`_consumer_cancelled = handle is not None and handle.task.cancelled()`（execution.py:439）确保 registry.cancel 只取消 consumer 而非生成器时，主循环不会误走成功路径；`not timed_out and not _consumer_cancelled` 双条件精确。
- **exactly-once 收尾结构稳固**：`_finalized` 标志 + 单一收尾块；`timed_out` 分支优先于 `handle.task.cancelled()`（execution.py:483-486），timeout 与 user_cancel 撞车时只发布一轮双信封、只落一条 record_execution_failed——双记录风险已消除。
- **unregister 位置正确**：位于 `if not _finalized` 块**之外**（execution.py:517-521），GeneratorExit/异常/早退任何路径都执行，且先于 `_record_db.close()`；try/except 包裹不阻塞后续清理。
- **RouterSpec 与 sibling 完全同构**：仿 `agent_team`（router 自带相对 prefix，注册处叠加 `API_V1_PREFIX`），最终路径 `/api/v1/agents/executions/{id}/cancel`，附注释说明（router_registry.py:110-111）。
- **导入一致性修正合理**：`from app.deps import get_db`（agent_run.py:5）与其他 agent 路由统一，deps.py:7 确认 re-export 自 `app.db.database`，行为等价。
- **测试断言真实**：cancel 用例断言了 SSE `中断` 事件（test:459）、主记录 `interrupt_reason="user_cancel"` 落库（test:460-461）、注册表清理（test:463）——不是冒烟断言；autouse fixture 防单例跨用例泄漏（test:372-378）；`record_execution_failed` fake 捕获 kw 可真实校验 interrupt_reason。
- waiting_hitl 守卫按授权加入且当前无副作用（status 恒为 "running"，短路条件不受影响）。

## Issues

### Critical

无。

### Important

**I-01: cancel 后 SSE 流/收尾延迟至多一个完整 timeout 才生效（cancel 检测不即时）**

**File:** `backend/app/ai/skills/execution.py:408-432`
**Issue:** registry.cancel() 取消的是 consumer task，但主循环正阻塞在 `await asyncio.wait_for(asyncio.shield(out_q.get()), timeout=remaining)`（execution.py:422-423）。consumer 被取消后不会向 out_q 投递任何事件，也没有任何机制唤醒该 await——循环要等到 wait_for 超时（`remaining ≈ self.timeout`）才进入 `except asyncio.TimeoutError` 分支，此时才发现 `consumer.done() and out_q.empty()` 并 break。后果：用户调用 cancel API 后，中断 SSE 提示、interrupt 双信封发布、record_execution_failed 落库全部延迟至多 timeout 秒（默认 300s）才发生。旁证：报告记录 cancel 单测文件耗时 **33.41s**——三个测试本应 ~1.5s（SlowAgent 总时长 1s），33s 恰好 = 30s timeout 等待 + 开销，说明 cancel 检测确实等满了 timeout。
**Fix:** 让 consumer 完成时唤醒队列等待。最小改动：
```python
# 注册后立即挂 done 回调，向 out_q 投递哨兵以解除阻塞
_CANCEL_SENTINEL = object()
consumer.add_done_callback(lambda _t: out_q.put_nowait(_CANCEL_SENTINEL))
# 循环内：
evt = await asyncio.wait_for(asyncio.shield(out_q.get()), timeout=remaining)
if evt is _CANCEL_SENTINEL:
    break
```
或改用 `asyncio.wait({get_task, consumer}, timeout=remaining, return_when=FIRST_COMPLETED)` 同时等待队列事件与 consumer 完成。

**I-02: 同步 `def` cancel 端点在线程池线程中调用 `task.cancel()`——asyncio 非线程安全**

**File:** `backend/app/routers/agent/agent_run.py:13-23`
**Issue:** FastAPI 对 `def`（非 `async def`）端点在 threadpool 执行，`reg.cancel()` → `handle.task.cancel()`（registry.py:72）在事件循环线程之外调用。`asyncio.Task.cancel()` 不是线程安全 API：非 debug 模式下虽常因 GIL 而"碰巧"工作，但回调入队不会触发事件循环唤醒（本场景因 wait_for 有 pending timer 才侥幸被处理），且与 task 完成竞态时可产生状态损坏。事件系统是本任务的核心基础设施，不应依赖未定义行为。
**Fix:** 端点改为 `async def`（在事件循环线程内执行），或 `handle.task.get_loop().call_soon_threadsafe(handle.task.cancel)`。与 I-01 一并修复后建议补一条"cancel 后 SSE 流在亚秒级收到中断事件"的时序断言。

### Minor

**M-01: 报告与代码不符——`self._run_handle` 未实现**
**File:** `backend/app/ai/skills/execution.py:315`（对照 task-9-report.md:44）
**Issue:** 报告称 handle"存入 self._run_handle"，实际为 execute() 局部变量。局部变量是更好的设计（避免同 service 实例并发执行时实例字段互踩），但报告描述失实，且偏离 dispatch 决议 #5 而未如 SSE 偏差那样声明。
**Fix:** 修正报告描述；或在 controller 层面确认局部变量方案为最终决议。

**M-02: cancel API 对 status=="done" 返回 200 {ok: False} 而非 brief 要求的 404**
**File:** `backend/app/routers/agent/agent_run.py:21-24`
**Issue:** brief 要求"404（不存在/已结束）"，实现只对 `handle is None` 404；若 status=="done" 则走 `reg.cancel()` 返回 ok=False + 200。当前无 `mark_done` 调用点，此分支不可达（brief 自身代码同样如此），属继承性缺口，Task 10 引入状态流转时会暴露。
**Fix:** `if handle is None or handle.status == "done": raise HTTPException(404, ...)`。

**M-03: 端点注入 `db: Session = Depends(get_db)` 但从未使用**
**File:** `backend/app/routers/agent/agent_run.py:15`
**Issue:** 无用依赖，白占一个 DB 会话（brief 代码原样如此，继承性）。
**Fix:** 移除该参数。

**M-04: registry.cancel 的 `status == "done"` 守卫当前为死分支**
**File:** `backend/app/ai/events/registry.py:69`
**Issue:** 无任何代码将 status 置为 "done"（unregister 直接移除 handle）。brief 原文如此，Task 10 可能需要；仅提示确认后续任务是否补 `mark_done` 或删除该分支。

**M-05: timeout×cancel 交叉场景无测试**
**File:** `backend/tests/unit/test_agent_run_registry.py`
**Issue:** "timeout 与 cancel 同时发生只落一条记录"这一关键 exactly-once 属性仅靠代码结构保证，无用例覆盖；现有 cancel 用例也未断言中断提示的及时性（I-01 正因此漏网）。
**Fix:** 补一个 consumer 即将完成时注入 cancel/timeout 竞争的用例，断言 `len(records) == 1`。

## Assessment

**Task quality:** Needs fixes
**Reasoning:** 核心语义（成功路径守卫、exactly-once 收尾、unregister 保证执行、双信封+落库）均正确且测试断言真实，但 I-01 使"用户取消"的可见效果延迟至多一个完整 timeout（测试自身 33s 耗时即为实证），I-02 依赖非线程安全的跨线程 task.cancel()——两项都直击本任务"强制终止/用户取消"的核心目的，须修复后方可信任。
