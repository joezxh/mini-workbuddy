# Task 9 Report: AgentRunRegistry + cancel API（强制终止/用户取消）

## Status: DONE

**Commit:** `2080aa0` — `feat(agent): AgentRunRegistry + cancel API——Skill/Agent 共用强制终止与用户取消`（5 files changed, 264 insertions, 6 deletions, 无文件删除）

## 执行过程说明（重要上下文）

进入任务时发现工作区已存在一份**前次未完成的 Task 9 实现**（未提交）：

- 未跟踪：`registry.py`、`agent_run.py`、`test_agent_run_registry.py`
- 已修改未提交：`execution.py`、`router_registry.py`

经逐文件核对，该实现与 brief 完全一致（diff 逐行比对确认三处 patch 语义精确匹配）。因此 TDD 的 RED 阶段（ModuleNotFoundError）无法复现——模块已存在。采取策略：**以测试为唯一事实标准**，核对实现 → 修正偏差 → 直接验证 GREEN。

### 发现并修正的偏差

1. **`agent_run.py` 的 `get_db` 导入来源不一致**（已修正）：
   - 原实现：`from app.db.database import get_db` + `from app.deps import get_current_user`
   - 修正为：`from app.deps import get_db, get_current_user`
   - 依据：`agent_config.py` / `agent_execution.py` 等其他 agent 路由均统一从 `app.deps` 导入（`app.deps` 自身第 7 行 re-export 自 `app.db.database`）。行为等价，仅为导入一致性。

## 实现明细

### 1. `backend/app/ai/events/registry.py`（新建，82 行）
- `RunHandle` dataclass：execution_id/task/out_q/agent/handler/reply_id/status（running|waiting_hitl|done）/interrupt_reason/user_id/started_at
- `AgentRunRegistry`：register/get/unregister/cancel/mark_waiting_hitl/mark_running
  - `cancel()`：handle 不存在或 status=="done" 时返回 False；否则设置 interrupt_reason 并 `task.cancel()`
- 模块级单例 `_REGISTRY` + `get_run_registry()`
- 与 brief 代码逐行一致

### 2. `backend/app/routers/agent/agent_run.py`（新建，23 行）
- `POST /agents/executions/{execution_id}/cancel`，依赖 `Depends(get_db, get_current_user)`
- 404：执行不存在或已结束；成功：`{"ok": ok, "execution_id": ..., "interrupt_reason": "user_cancel"}`
- 已挂载到 `router_registry.py`（`prefix=API_V1_PREFIX`，与 `agent_team` 同模式；router 自带 `/agents/executions` 相对 prefix）

### 3. `backend/app/ai/skills/execution.py`（修改，+37/-6）
对 Task 8 最终结构的四处 patch（diff 逐行核对与 brief 语义一致）：
- **(a) 注册**：`consumer = asyncio.create_task(_consume())` 后调用 `get_run_registry().register(execution_id, consumer, out_q=out_q, agent=agent, handler=handler, user_id=user_id)`，存入 `self._run_handle`；模块顶部导入 `get_run_registry`（register 与 unregister 两处共用）
- **(b) 循环退出条件**：`consumer.done() and out_q.empty() and handle.status != "waiting_hitl"`（Task 10 前置守卫，当前无副作用）
- **(c) 统一中断收尾（finally 内，`_finalized` 守卫下）**：
  - `cancel_reason` 派生：`timed_out` → "timeout"；否则 `handle is not None and handle.task.cancelled()` → `handle.interrupt_reason or "user_cancel"`
  - 任意 cancel_reason：发布 `interrupt_requested` + `interrupted` 两个 EventEnvelope（category=INTERRUPT，content/interrupt_reason 均带 cancel_reason）+ `record_execution_failed(..., interrupt_reason=cancel_reason)`
  - **关键语义守卫**（brief patch 说明 + 任务上下文第 3 点）：`_consumer_cancelled = handle is not None and handle.task.cancelled()`；仅当 `not timed_out and not _consumer_cancelled` 才置 `_exec_success = True`——修复了"registry.cancel 只取消 consumer 而非 execute() 生成器，主循环会误走成功路径"的问题
- **(d) 反注册**：finally 内关闭 `_record_db` 之前，`get_run_registry().unregister(execution_id)`（try/except 包裹，任何退出路径必执行）

### 4. `backend/tests/unit/test_agent_run_registry.py`（新建，125 行，3 个测试）
- `test_registry_lifecycle_and_cancel`：register → cancel → task.cancelled → unregister → get 为 None → 二次 cancel 返回 False
- `test_waiting_hitl_status_transition`：mark_waiting_hitl(reply_id="r1") → status/reply_id 断言 → mark_running
- `test_execute_cancel_emits_interrupt_events`：SlowAgent（0.2s×5）+ canceller 协程轮询注册表并 cancel("exec-cancel", reason="user_cancel")；断言 SSE 含 `error`/`中断` 事件 + 主记录落 `interrupt_reason="user_cancel"` + 注册表已清理
- 测试适配（按任务指示）：patch `exec_mod.SessionLocal`（模块级名，匹配 Task 8 最终代码）；`EventBus`/`_record_metrics` 一并 Fake；autouse fixture `_clean_registry` 在 teardown 反注册三个 execution_id，避免跨用例泄漏

## 验证输出

| 验证项 | 命令 | 结果 |
|---|---|---|
| 新增测试 | `python -m pytest tests/unit/test_agent_run_registry.py -v` | **3 passed** (33.41s) |
| 全量单测 | `python -m pytest tests/unit -q` | **128 passed + 1 error** (53.91s) |
| 路由加载 | `python -c "from app.routers.agent.agent_run import router; print('router ok', len(router.routes))"` | `router ok 1` |

- 全量结果 = 基线 125 passed + 3 新增 = 128 passed；唯一 error 为 `test_voice_services.py::test_create_and_append` 连接本地 PostgreSQL 失败——**既有环境错误，与本分支无关**，与基线完全一致。

## 自查清单

| 检查项 | 结论 |
|---|---|
| 取消路径 `interrupt_reason="user_cancel"` 恰好落一次 | ✅ `_finalized` 守卫保证收尾仅一次；cancel_reason 在 finally 内派生一次；测试 `records` 断言通过 |
| 超时路径行为不变 | ✅ `timed_out` → cancel_reason="timeout" → 双信封 + record_execution_failed；try 体内超时 SSE yield 条件未变（仅 `timed_out`）。注：DB error 文案按 brief patch (b) 统一为"执行被中断（timeout）"，SSE 文案不变 |
| unregister 总是执行 | ✅ finally 内、关闭 `_record_db` 前，try/except 包裹；早退路径（技能不存在）同样覆盖 |
| 无双重收尾 | ✅ `_finalized` 标志 + 单一收尾块 |
| `_exec_success` 语义守卫 | ✅ 仅 `not timed_out and not _consumer_cancelled` 才置 True |
| `.superpowers/` 未提交 | ✅ 仅提交 5 个指定文件 |

## 备注 / 与任务上下文的一处解释性差异

任务上下文提到"for user_cancel no SSE yield"，但 brief 的 Step 1 测试明确断言 SSE 输出含 `中断` error 事件（`assert any(e.type == "error" and "中断" in e.data["message"] ...)`），且 brief patch (b) 的收尾代码本身含 `yield SkillEvent(type="error", data={"message": f"执行被中断（{cancel_reason}）"})`。最终实现取**测试为权威**：user_cancel 的 SSE yield 放在 try 体内（`elif _consumer_cancelled` 分支），finally 内绝不 yield——这与"GeneratorExit 期间禁止 yield"约束兼容（registry.cancel 只取消 consumer，execute() 生成器本身未被取消，可安全 yield）。测试通过佐证该选择正确。

---

# Code Review Fix（REVIEW 追加节）

## Status: DONE

**Commit:** `813962e` — `fix(agent): cancel 即时唤醒主循环（哨兵+done_callback）+ 异步端点线程安全 + done 态 404`（3 files changed, 32 insertions, 6 deletions）

## 修复明细

| ID | 文件 | 修复内容 |
|---|---|---|
| I-01 | `backend/app/ai/skills/execution.py` | `consumer = asyncio.create_task(_consume())` 后新增 `_on_consumer_done` done_callback：consumer 结束（含被 cancel）时 `out_q.put_nowait(None)` 投递哨兵，唤醒阻塞在 `wait_for(shield(out_q.get()))` 的主循环；主循环在 `yield evt` **之前**判断 `if evt is None: break`——哨兵绝不进入 SSE。原有 `consumer.done() and out_q.empty() and status != "waiting_hitl"` 退出条件保留为二级出口；超时路径（TimeoutError → timed_out → 熔断）逻辑未变 |
| I-02 | `backend/app/routers/agent/agent_run.py` | `def cancel_execution` → `async def cancel_execution`（签名/依赖不变）。task.cancel() 只允许在事件循环线程内调用，同步 def 会落入 FastAPI 线程池导致跨线程取消不安全 |
| M-01 | —（无代码改动） | grep 全 backend 确认 `self._run_handle` **零引用**；实现本就使用局部变量 `handle`（更优设计），报告第 39 行"存入 `self._run_handle`"为文档笔误，代码无需改动 |
| M-02 | `backend/app/routers/agent/agent_run.py` | 404 判定改为 `if handle is None or handle.status == "done"`——已结束的执行取消返回 404（brief：不存在/已结束均 404） |
| M-05 | `backend/tests/unit/test_agent_run_registry.py` | `test_execute_cancel_emits_interrupt_events` 增加 wall-clock 回归守卫：`time.monotonic()` 计时 async-for 消费全程，`assert elapsed < 10`（svc.timeout=30），防止 I-01 类"cancel 后阻塞至满 timeout"问题再次漏网 |

约束确认：HITL confirm 端点未加（Task 10）；无模式路由（Task 11）；user_cancel 的 SSE yield 保留在 try 体内（controller 已确认的偏差）；`_finalized` exactly-once 收尾语义未动；哨兵不影响 genuine timeout 路径。

## 验证输出（含耗时证据）

| 验证项 | 结果 |
|---|---|
| `python -m pytest tests/unit/test_agent_run_registry.py -v --durations=5` | **3 passed** (2.60s)；`test_execute_cancel_emits_interrupt_events` call 耗时 **0.30s**（修复前 33.41s ≈ 30s timeout，**加速约 110 倍**） |
| `python -m pytest tests/unit -q` | **128 passed, 1 error** (20.75s)；唯一 error 为 `test_voice_services.py::test_create_and_append` PostgreSQL 连接拒绝——既有环境错误，与基线一致 |
| 语法检查 | `ast.parse` 三文件全部通过 |
| 提交隔离 | 工作区含其他并行改动，`git commit -- <3 files>` 仅提交本次修复的 3 个文件；`.superpowers/` 未提交 |
