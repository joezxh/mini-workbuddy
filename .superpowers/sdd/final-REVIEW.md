# Final Whole-Branch Review — feature/agent-event-p0

**Reviewed:** 2026-10-28
**Scope:** 637d441..1dc6072（13 commits，cross-task review，depth=deep）
**Files Reviewed:** 18 个后端源文件 + 8 个测试文件 + DDL 47 + spec P0 验收项
**Status:** issues_found

---

## Verdict

**Needs fixes (blocking list):**

1. **BLK-01** HITL 暂停期间 cancel API 是静默 no-op —— 执行最长 30 分钟不可终止。
2. **BLK-02** resume 之后 finally 只取消旧 `consumer`，不取消 `handle.task` —— 恢复后的 agent 任务在超时/断连路径泄漏继续运行。
3. **BLK-03** cancel API 无属主校验 —— 任何登录用户可终止他人的执行。

---

## Cross-task Findings

### Critical

#### BLK-01: registry.cancel 对 waiting_hitl 状态的执行无效

**File:** `backend/app/ai/events/registry.py:293-301` × `backend/app/ai/events/hitl.py:228-233` × `execution.py:550`

进入 HITL 暂停时，`handle.status = "waiting_hitl"`，此时原 consumer 任务**已正常结束**（reply_stream 在 yield RequireUserConfirm 后流终止，done_callback 已投过哨兵）。用户调 `POST /{id}/cancel`：

- 端点检查 `handle.status == "done"` → waiting_hitl 通过，`reg.cancel()` 返回 `ok=True`；
- `registry.cancel()` 只做 `handle.task.cancel()` —— 对已完成任务是 **no-op**；
- 主循环阻塞在 `out_q.get()`（deadline = 暂停时刻 + 30min），无人投递哨兵 → **不能被唤醒**。

结果：API 谎报取消成功，执行仍挂起最长 30 分钟；`interrupt_reason` 被覆写但无人消费。单测只覆盖了 running 态取消（`test_agent_run_registry.py::test_execute_cancel_emits_interrupt_events`），waiting_hitl 态取消是测试矩阵盲区——只有跨任务（registry 状态机 × execute 主循环 × consumer 生命周期）才能看到。

**Fix:** cancel() 增加分支：`status == "waiting_hitl"` 时投递哨兵/控制事件唤醒主循环（如 `handle.out_q.put_nowait(SkillEvent(type="hitl_cancel"))`），主循环收到后走 `timed_out` 同款收尾（标记 timeout 之外的 user_cancel 路径、resolve pause 行为 interrupted、record failed）。

#### BLK-02: resume 后的活跃任务泄漏（finally 引用失效）

**File:** `backend/app/ai/skills/execution.py:622-624` × `backend/app/ai/events/hitl.py:228`

`resume_hitl` 将新 consumer 存入 `handle.task`，但 execute() 的 finally 收尾只取消闭包变量 `consumer`（首轮任务）：

```python
if consumer is not None and not consumer.done():
    consumer.cancel()
```

恢复后两条路径会泄漏仍在运行的 `_resume` 任务：
- **断连**（GeneratorExit）：finally 触发时 consumer（旧）已 done → 跳过取消；`handle.task`（新）继续跑 `agent.reply_stream`，持续消耗 LLM token、继续经 handler 落库写事件，写入无人读取的 out_q。
- **恢复后超时**：resume 不重置 deadline（见 IMP-01），剩余预算耗尽时主循环 `timed_out=True; consumer.cancel()` —— 同样对已 done 的旧任务 no-op，`asyncio.gather` 立即返回，SSE 谎报"已熔断"但 `handle.task` 仍在跑。随后 finally unregister，cancel API 也再无法触达它。

同样只有跨任务可见：单测 Fake agent 两段式流在恢复后立即 ReplyEnd，新任务瞬间结束，掩盖了泄漏。

**Fix:** finally 改为取消活跃句柄：`active = handle.task if handle else consumer`，对 `active` 做 cancel+gather；超时分支同样取消 `_active` 而非 `consumer`。

#### BLK-03: cancel 端点缺少属主校验

**File:** `backend/app/routers/agent/agent_run.py:1894-1910`

`confirm_execution` 有属主校验（execution.user_id），`cancel_execution` 完全没有——`execution_id` 是路径参数，任何认证用户可枚举/终止任意他人的运行中执行（横向越权）。spec 0.6/0.7 验收均要求权限校验，两条端点标准不一致正是跨任务（Task 8 cancel × Task 10 confirm）才暴露的缺口。

**Fix:** cancel 复用 confirm 的属主校验（查 AgentExecution.user_id 比对 current_user），并考虑租户隔离。

### Important

#### IMP-01: resume 不重置 deadline，暂停时长吞噬执行预算

**File:** `execution.py:554,564-573` × `hitl.py:222-234`

暂停时 `deadline = now + 30min`；resume 时仅置 status=running 并发 hitl_resume 事件，**deadline 不再调整**。用户在第 29 分钟确认后，恢复的执行只剩 1 分钟总预算即被熔断。主循环 hitl_resume 分支应 `deadline = time.monotonic() + self.timeout`（或至少剩余执行超时）。

#### IMP-02: HITL 超时/取消路径不 resolve pause 行，且与 confirm 存在竞态

**File:** `execution.py:522-530` × `hitl.py:154-180` × `agent_run.py:1920-1948`

HITL 暂停超时熔断后：`agent_hitl_pause` 行永远停在 `waiting`（超时提示时刻 `timeout_at` 只写不用，无后台对账）；BLK-01 修复后的 cancel 同理。另外 deadline 触发与 confirm API 并发时：confirm 已 `resolve_pause` + `resume_hitl`（status 置回 running），主循环随后按 timed_out 收尾——resume 出来的新任务无人收尾（叠加 BLK-02）。建议收尾时统一 `resolve_pause(interrupted)`，confirm 端点在 resume 前重读 handle.status。

#### IMP-03: handle.status 永远不会是 "done"——cancel 对刚结束的执行返回 ok=True

**File:** `registry.py:265,296` × `agent_run.py:1907`

`RunHandle.status` 注释声明 `running|waiting_hitl|done`，但全链路无任何代码写 "done"；执行完成到 finally unregister 之间存在窗口，cancel 端点 `status == "done"` 检查失效，`task.cancel()` 对 done 任务 no-op 却返回 `{"ok": True}`。小窗口竞态，但契约（done 态 404，commit 813962e 声称修复）未真正闭环。Fix: 主循环 break 后、finally 内先 `handle.status = "done"`（或 unregister 提前到记录终态之后立即执行）。

#### IMP-04: `skill_result` 不再落库 + "读取侧按别名双读"承诺未实现

**File:** `execution.py:967-990`（handler）× `event_types.py:2046` docstring × `services/agent/agent_execution_service.py:176-207`

旧链路在 ReplyEnd 落库 `skill_result`（含最终全文）；新链路只落 `reply_end`（content 仅有 finished_reason），最终全文只存在于按块的 `text_done`。而 `event_types.py` docstring 承诺"读取侧按别名双读"，本分支没有任何读取侧归一化代码——新执行的 DB 历史将携带 `text_done/reply_end` 等新值直接喂给现有前端时间线渲染。spec 0.1 验收"存量事件读写不报未知值"中**读侧**仅靠前端恰好兼容才成立，未验证。Fix: 在 `AgentExecutionEventItem.from_orm_event` 或读取侧补归一化映射，或在 reply_end content 中回填最终文本。

### Minor

#### MIN-01: cancel 端点 `db` 参数未使用
`agent_run.py:1897` — `db: Session = Depends(get_db)` 在 cancel 中无引用（属主校验加入后自然用上，与 BLK-03 一并修）。

#### MIN-02: source 值不一致
handler `_publish_db` 硬编码 `source="agent"`（`execution.py:697-705`），execute 主循环信封用 `source="skill_execution"`，同一 execution 的 DB 事件来源混用两种值，按 source 过滤的查询会漏。

#### MIN-03: levels 硬编码绕过路由表
handler/execute 多处直接写 `levels=[EventLevel.DB, ...]` 而不查 `route_of()`，与 `DEFAULT_ROUTES` 形成第二份真相（当前值一致，未来漂移无声）。建议统一 `route_of(etype)` 取 levels。

#### MIN-04: confirm 属主校验可被绕过
`agent_run.py:1941-1943` — `row is None`（record_execution_start 失败时必然发生）或 `row.user_id is None` 时直接放行；`and` 链应改为 fail-closed。

#### MIN-05: exceed_max_iters 不反映到主记录
`execution.py:960-965,642-658` — handler 落库 `iteration_limit`，但主记录 done 路径 finished_reason 恒为 "completed"，reply_end 的真实 finished_reason 被丢弃。

---

## 事件类型契约一致性（审查项 1）

- handler 写入：`reply_start / text_done / thinking_done / tool_call / tool_result / model_call / iteration_limit / error / reply_end` —— 全部在 `DEFAULT_ROUTES` ✅
- execute 主循环写入：`agent_start / engine_decision / error / hitl_pause / hitl_resume / interrupt_requested / interrupted` ✅
- 非 llm 模式动态事件经 `normalize_event_type` + `route_of` 兜底（未知→保守落库）✅
- SSE 兼容：旧类型值 `text/thinking/tool_call/tool_result/done/error/start/progress` 全保留，`engine_decision/hitl_pause/hitl_resume` 为纯增量 ✅
- ⚠ 唯一缺口见 IMP-04：DB 侧 `skill_result` 消失、读取侧无归一化。

## RunHandle 生命周期状态机（审查项 2）

running → waiting_hitl → running（resume 换 task）→ 退出。正常路径与 running 态 cancel 自洽（哨兵机制正确，`test_execute_cancel_emits_interrupt_events` 回归守卫到位）。**三处不自洽**：waiting_hitl 态 cancel（BLK-01）、resume 后活跃任务引用（BLK-02）、done 态契约（IMP-03）。timeout × cancel × disconnect 三者交叉在 waiting_hitl/resume 场景下均失败（BLK-01/02、IMP-01/02）。

## exactly-once 与异常吞噬（审查项 3）

`_finalized` 守卫 + record_* 全吞异常：主记录不会双重写入 ✅。GeneratorExit 传播期 finally 内无 yield、无裸吞 ✅。`event_service.stop()` 有 5s 上界，不会挂死 aclose ✅。error 信封在 handler（ReplyEnd.error）与外层 except 可能重复发布——仅重复不影响正确性，Minor 不单列。

## 模块循环依赖（审查项 4）

`execution.py → registry/bus/event_types`（模块级，单向）；`hitl.py → execution` 仅函数内懒加载（`SkillEvent`）；`agent_run.py → registry`（模块级，registry 无反向依赖）；`execution_records → models` 懒加载。**无模块级循环** ✅。

## P0 验收核对

| # | 验收项 | 结论 |
|---|---|---|
| 0.1 | 枚举单一来源 + 双处删除 + LEGACY_ALIAS | ✅ 写侧归一化完备；读侧"别名双读"未实现（IMP-04，降级为兼容性赌注） |
| 0.2 | Envelope/EventBus 分级 + delta 停止落库 | ✅ 代码与单测成立；≥80% 行数下降待真实环境确认（DDL 未应用前新列写入会整批失败） |
| 0.3 | record_execution_* 真实写入 | ✅ start/done/failed/status 全落库，finally 单次收尾 |
| 0.4 | timeout 熔断 + reason=timeout | ✅ 主路径成立；恢复后预算被吞噬（IMP-01）为偏差 |
| 0.5 | DDL 47 + ORM | ✅ 脚本幂等、PG 方言正确；⚠ 未应用到任何库（部署前置） |
| 0.6 | Registry + cancel API（Skill/Agent 共用） | ❌ HITL 态取消无效（BLK-01）、无属主校验（BLK-03）、done 态 404 未闭环（IMP-03）；"Agent 共用"仅 Skill 链路实际注册 |
| 0.7 | HITL 全链路（暂停/确认/拒绝/中断/超时/权限） | ⚠ 暂停→确认→恢复成立；暂停超时→中断成立；pause 行不 resolve（IMP-02）、权限校验 fail-open（MIN-04）、拒绝→denied→模型重试仅有 Fake 证据 |
| 0.8 | 七模式 + ENGINE_DECISION + 引擎路由 | ✅ resolve/routing/unsupported 分支齐备；llm 外模式仅 Fake 验证，AgentFactory 真实集成未证 |

## 真实环境验证清单（合并前/后必须做）

1. **先应用 DDL 47** —— 否则 `_batch_write_sync` 每批 insert 因缺列失败，事件静默全丢（仅 error 日志），DB 行数下降验收项无法判定。
2. **HITL 暂停期间调 cancel API**（真实前端 + 真实 agent，工具确认面板挂起时取消）——当前预期失败（BLK-01），修复后回归。
3. **HITL 恢复后断开 SSE / 触发超时**，确认 agent 进程内任务真正终止（日志无后续 ModelCall/token 消耗）——验证 BLK-02 修复。
4. **真实 agentscope 2.0.8 流**跑一次 text+tool+ReplyEnd.error 全事件，对照 DB 行：tool_call.input/tool_result 全文/model_call 计量是否存在已知空值局限（P1 已接受，但需确认 delta 不落库后 text_done 汇总完整）。
5. **双用户越权探测**：用户 B 对用户 A 的运行中执行调 cancel/confirm，预期 403——验证 BLK-03/MIN-04 修复。

---

_Reviewer: adversarial whole-branch review (gsd-code-reviewer)_
_Depth: deep · 2026-10-28_
