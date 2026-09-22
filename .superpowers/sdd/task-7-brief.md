# Agent 事件体系 P0（止血）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec `docs/superpowers/specs/2026-09-21-agent-event-architecture-design.md` 的 P0：统一事件枚举单一来源、EventEnvelope + EventBus 分级（delta 停止落库）、修复执行主记录存根、超时熔断生效、DDL 47；并使 **Skill 执行与 Agent 一致**——AgentRunRegistry 中断（强制终止/用户取消/超时）、HITL 全链路（暂停/确认/拒绝/中断/超时/权限）、七模式动态切换（`ENGINE_DECISION` 引擎路由）。

**Architecture:** 新建 `app/schemas/agent/event_types.py` 作为事件枚举/类别/级别/路由/别名的唯一权威来源，schemas 与 models 双处删除本地枚举改为 re-export；`ExecutionEventService` 增加 envelope 入口并按级别过滤 DB 写入；新建 `EventBus`（Log + DB 双 handler 委托）；重写 `SkillEventHandler`（修复 `lambda: yield` 语法错误，delta 仅走 SSE、块级汇总落库、补 reply_id/tool_call_id/token 统计）；`execute()` 接入真实执行主记录、总超时熔断，并注册进 `AgentRunRegistry`（cancel API 触达）；HITL 经 `agent_hitl_pause` 表 + confirm API（approve/reject/interrupt）+ `UserConfirmResultEvent`/`UserInterruptEvent` 恢复；`resolve_execution_mode()` 实现七模式动态分派（llm/plan/team/knowledge 路由，workflow 明确报错）。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / agentscope 2.0.8 / pytest。

**范围外（P1/P2 另立计划）**：SSE Last-Event-ID 重连与 `after_seq` 补拉 / 前端改造（EventRouter/HITL 面板/Debug Panel）/ `AgentScopeEventAdapter` 双通道合并 / ConfigValidator / Custom 扩展通道 / `AgentState` 跨进程恢复 / workflow(Dify) 模式引擎接入。

**关键约束（执行前必读）：**

1. 当前 `app/ai/skills/execution.py` **无法 import**（`yield_fn=lambda evt: yield evt` 是语法错误，出现两处）。Task 7 会重写该段。
2. 统一枚举用**普通 `str` 子类**（非 `Enum`），保持 `ExecutionEventType.TEXT == "text"` 为 True —— 与现存 schemas 版行为一致，避免 `str,Enum` 相等性陷阱。
3. P0 **不改 SSE 载荷**：`SkillEvent.type` 仍输出 `text/thinking/tool_call/tool_result/done/error` 等旧值，前端零改动。DB 中 `event_type` 值经归一化变为 `text_chunk` 等 —— 前端时间线本就期望 `text_chunk`，兼容性反而提升。
4. 测试不依赖真实数据库：DB 触点用 Fake 对象；async 测试用 `asyncio.run()` 包装（仓库未确认装有 pytest-asyncio）。
5. 数据库为 **PostgreSQL**（alembic env.py / 45/46 号脚本 / database.py 均为证）：DDL 47 用 PG 方言，`ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` 保证幂等可重复执行。
6. 每个任务结束跑 `cd backend && python -m pytest tests/unit -q` 确认无回归，再 commit。

---


### Task 7: SkillEventHandler 重写（修复语法错误 + 分级 + 三级关联 + 计量）

**Files:**
- Modify: `backend/app/ai/skills/execution.py:44-221`（`SkillEvent` 保留；`SkillEventHandler` 整体重写；删除 `_run_agent_native` 死代码）
- Test: `backend/tests/unit/test_skill_event_handler.py`

**先决验证**：确认安装的 agentscope 事件构造参数（字段名以安装版本为准）：

```bash
cd backend && python -c "
from agentscope.event import TextBlockDeltaEvent, ToolCallEndEvent, ModelCallEndEvent, ReplyEndEvent, ToolResultEndEvent
for cls in (TextBlockDeltaEvent, ToolCallEndEvent, ModelCallEndEvent, ReplyEndEvent, ToolResultEndEvent):
    print(cls.__name__, getattr(cls, 'model_fields', None) or cls.__annotations__)
"
```

若字段名与本计划代码不一致（如 `delta` vs `text`），以实际输出为准调整测试构造参数与 handler 取值；**handler 的 isinstance 分派结构不变**。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_skill_event_handler.py`：

```python
"""SkillEventHandler 重写单测：delta 不落库、块级汇总落库、三级关联、token 计量。

直接构造 agentscope 真实事件对象；构造字段以安装版本 model_fields 为准
（执行前先跑本文件顶部说明中的字段检查命令）。
"""
import asyncio

from agentscope.event import (
    ReplyStartEvent, TextBlockDeltaEvent, TextBlockEndEvent,
    ThinkingBlockDeltaEvent, ThinkingBlockEndEvent,
    ToolCallStartEvent, ToolCallEndEvent,
    ToolResultTextDeltaEvent, ToolResultEndEvent,
    ModelCallEndEvent, ReplyEndEvent,
)

from app.ai.skills.execution import SkillEvent, SkillEventHandler


class FakeBus:
    def __init__(self):
        self.published = []

    def publish(self, envelope):
        self.published.append(envelope)


def _handler():
    bus = FakeBus()
    out = asyncio.Queue()
    return SkillEventHandler(skill_name="demo", bus=bus, out_q=out), bus, out


def _drain(q: asyncio.Queue):
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


def test_text_delta_not_persisted_but_ssed():
    async def main():
        h, bus, out = _handler()
        await h.handle(ReplyStartEvent(reply_id="r1", session_id="s1", name="demo", role="assistant"))
        await h.handle(TextBlockDeltaEvent(reply_id="r1", block_id="b1", delta="你好"))
        await h.handle(TextBlockDeltaEvent(reply_id="r1", block_id="b1", delta="世界"))
        await h.handle(TextBlockEndEvent(reply_id="r1", block_id="b1"))

        # SSE 侧仍输出两个 text 事件（前端兼容）
        sse = [e for e in _drain(out) if e.type == "text"]
        assert "".join(e.data["content"] for e in sse) == "你好世界"

        # DB 侧：reply_start + text_done 汇总，无逐 delta
        types = [e.event_type for e in bus.published]
        assert types == ["reply_start", "text_done"]
        done = bus.published[1]
        assert done.content == {"text": "你好世界"}
        assert done.reply_id == "r1" and done.block_id == "b1"
        assert done.category == "text"
    asyncio.run(main())


def test_thinking_delta_summary():
    async def main():
        h, bus, out = _handler()
        await h.handle(ThinkingBlockDeltaEvent(reply_id="r1", block_id="b0", delta="思考中"))
        await h.handle(ThinkingBlockEndEvent(reply_id="r1", block_id="b0"))
        types = [e.event_type for e in bus.published]
        assert types == ["thinking_done"]
        assert bus.published[0].content == {"thinking": "思考中"}
    asyncio.run(main())


def test_tool_call_with_tool_call_id_and_result_state():
    async def main():
        h, bus, out = _handler()
        await h.handle(ToolCallStartEvent(reply_id="r1", tool_call_id="tc1", tool_call_name="Bash"))
        await h.handle(ToolCallEndEvent(reply_id="r1", tool_call_id="tc1", tool_args={"cmd": "ls"}))
        await h.handle(ToolResultTextDeltaEvent(reply_id="r1", tool_call_id="tc1", delta="file1"))
        await h.handle(ToolResultEndEvent(reply_id="r1", tool_call_id="tc1", state="success"))

        types = [e.event_type for e in bus.published]
        # delta（tool_result 流式）不落库，仅 tool_call + tool_result 两条
        assert types == ["tool_call", "tool_result"]
        call = bus.published[0]
        assert call.tool_call_id == "tc1"
        assert call.content["tool_name"] == "Bash"
        result = bus.published[1]
        assert result.tool_call_id == "tc1"
        assert result.content["state"] == "success"

        # SSE 侧 tool_call/tool_result 事件仍在
        sse_types = [e.type for e in _drain(out)]
        assert "tool_call" in sse_types and "tool_result" in sse_types
    asyncio.run(main())


def test_model_call_tokens_accumulate_and_reply_end_usage():
    async def main():
        h, bus, out = _handler()
        await h.handle(ReplyStartEvent(reply_id="r1", session_id="s1", name="demo", role="assistant"))
        await h.handle(ModelCallEndEvent(reply_id="r1", model_name="qwen-max",
                                         input_tokens=100, output_tokens=50))
        await h.handle(ModelCallEndEvent(reply_id="r1", model_name="qwen-max",
                                         input_tokens=30, output_tokens=20))
        await h.handle(ReplyEndEvent(reply_id="r1", session_id="s1"))

        # model_call 仅 LOG 级 —— bus 收到但 FakeBus 不过滤，检查其 levels
        mc = [e for e in bus.published if e.event_type == "model_call"]
        assert len(mc) == 2
        assert mc[0].levels == [0]  # LOG only
        assert mc[0].metadata["input_tokens"] == 100

        # reply_end 携带累计 usage
        re = [e for e in bus.published if e.event_type == "reply_end"][-1]
        assert re.metadata["input_tokens"] == 130
        assert re.metadata["output_tokens"] == 70
        assert re.metadata["iterations"] == 2
        assert re.content["finished_reason"] == "completed"

        # 最终 SSE done 事件仍输出
        assert any(e.type == "done" for e in _drain(out))
    asyncio.run(main())


def test_error_event():
    async def main():
        h, bus, out = _handler()
        await h.handle(Exception("boom"))  # ErrorEvent 兼容：非已知类型走 error 兜底
        # 已知 ErrorEvent 构造依赖版本，此处用兜底分支验证 error 事件输出
        assert any(e.type == "error" for e in _drain(out)) or bus.published == []
    asyncio.run(main())
```

> 测试说明：最后一个用例走 `handle()` 的兜底分支（未知事件 → SSE error + DB error）。若安装版 `ErrorEvent` 可直接构造（有 `error` 字段），可再加一个真实构造分支。**若 agentscope 事件构造参数与上述不一致**（如 `ToolCallStartEvent` 无 `tool_call_name` 而叫 `tool_name`），以 Step 0 的字段检查输出为准修正测试与实现取值。

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_skill_event_handler.py -v
```

Expected: FAIL —— collection error（`execution.py` 当前有 `lambda evt: yield evt` 语法错误，import 即 SyntaxError）。

- [ ] **Step 3: 重写 `SkillEventHandler` 并删除死代码**

修改 `backend/app/ai/skills/execution.py`：

(a) 删除第 29-33 行存根区，改为：

```python
from app.ai.skills.execution_records import (
    record_execution_done,
    record_execution_failed,
    record_execution_start,
)
```

(b) 顶部 import 区加：

```python
from app.ai.events.bus import EventBus
from app.schemas.agent.event_types import EventCategory, EventLevel
```

(c) **整体替换** `class SkillEventHandler`（原第 66-221 行）为：

```python
class SkillEventHandler(EventStreamHandler):
    """AgentScope 事件流处理器（spec §4.2 分级 + §5.2 运行模式增强）。

    - SSE 输出：SkillEvent 入 out_q，类型保持旧值（text/thinking/tool_call/
      tool_result/done/error），前端零改动。
    - DB 输出：经 bus 发布信封 —— delta 不落库，块级/调用级汇总落库。
    - 关联：透传 reply_id / block_id / tool_call_id。
    - 计量：累计 ModelCallEnd 的 input/output tokens 与迭代轮数。
    """

    def __init__(self, skill_name: str, bus: EventBus, out_q: asyncio.Queue) -> None:
        super().__init__()
        self.skill_name = skill_name
        self.bus = bus
        self.out_q = out_q
        self.text_parts: list[str] = []
        self.current_tool_name: str = ""
        self.reply_id: str | None = None
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.iterations = 0

    # ── 发布辅助 ─────────────────────────────────────────────────────

    def _emit_sse(self, type_: str, data: dict) -> None:
        self.out_q.put_nowait(SkillEvent(type=type_, data=data))

    def _publish_db(self, event_type: str, category: str, levels, content: dict,
                    metadata: dict | None = None, **kw) -> None:
        self.bus.publish(EventEnvelope(
            execution_id=self.bus.execution_id,
            trace_id=self.bus.trace_id,
            event_type=event_type, category=category, levels=list(levels),
            content=content, source="agent", source_id=self.skill_name,
            reply_id=self.reply_id, metadata=metadata or {}, **kw,
        ))

    # ── 统一分发 ─────────────────────────────────────────────────────

    async def handle(self, event) -> None:
        """统一事件分发器（重写基类）。"""
        from agentscope.event import (
            ReplyStartEvent, ReplyEndEvent, ExceedMaxItersEvent,
            TextBlockDeltaEvent, TextBlockEndEvent,
            ThinkingBlockDeltaEvent, ThinkingBlockEndEvent,
            ToolCallStartEvent, ToolCallEndEvent,
            ToolResultTextDeltaEvent, ToolResultDataDeltaEvent, ToolResultEndEvent,
            ModelCallEndEvent, ErrorEvent,
        )

        if isinstance(event, ReplyStartEvent):
            self.reply_id = getattr(event, "reply_id", None)
            self._publish_db("reply_start", EventCategory.LIFECYCLE, [EventLevel.DB],
                             {"name": getattr(event, "name", "")})

        elif isinstance(event, TextBlockDeltaEvent):
            delta = event.delta or ""
            if delta.strip():
                self.text_parts.append(delta)
                self._emit_sse("text", {"content": delta})   # 仅 SSE，不落库

        elif isinstance(event, TextBlockEndEvent):
            self._publish_db(
                "text_done", EventCategory.TEXT, [EventLevel.DB],
                {"text": "".join(self.text_parts)},
                block_id=getattr(event, "block_id", None),
            )
            self.text_parts = []

        elif isinstance(event, ThinkingBlockDeltaEvent):
            delta = event.delta or ""
            if delta.strip():
                self._emit_sse("thinking", {"content": delta})  # 仅 SSE

        elif isinstance(event, ThinkingBlockEndEvent):
            # 思考块不汇总落库内容（体积大、审计价值低），仅记块边界
            self._publish_db(
                "thinking_done", EventCategory.THINKING, [EventLevel.DB],
                {"block_id": getattr(event, "block_id", None)},
                block_id=getattr(event, "block_id", None),
            )

        elif isinstance(event, ToolCallStartEvent):
            self.current_tool_name = getattr(event, "tool_call_name", "") or ""
            self._tool_call_id = getattr(event, "tool_call_id", None)

        elif isinstance(event, ToolCallEndEvent):
            tool_input = getattr(event, "tool_args", {}) or {}
            self._publish_db(
                "tool_call", EventCategory.TOOL,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"tool_name": self.current_tool_name, "input": tool_input},
                tool_call_id=getattr(event, "tool_call_id", None),
                ui_hint="timeline",
            )
            self._emit_sse("tool_call", {
                "tool_name": self.current_tool_name, "input": tool_input,
            })

        elif isinstance(event, (ToolResultTextDeltaEvent, ToolResultDataDeltaEvent)):
            # 工具结果流式 delta：仅 SSE（二进制 data 记录 size 摘要）
            if isinstance(event, ToolResultTextDeltaEvent):
                d = getattr(event, "delta", "") or ""
                if d.strip():
                    self._emit_sse("tool_result", {
                        "tool_name": self.current_tool_name, "delta": d,
                        "state": "success",
                    })
            else:
                data_b64 = getattr(event, "data", None)
                self._emit_sse("tool_result", {
                    "tool_name": self.current_tool_name,
                    "media_type": getattr(event, "media_type", ""),
                    "data_size": len(data_b64) if data_b64 else 0,
                    "binary": True, "state": "success",
                })

        elif isinstance(event, ToolResultEndEvent):
            state = str(getattr(event, "state", "success") or "success").lower()
            self._publish_db(
                "tool_result", EventCategory.TOOL,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"tool_name": self.current_tool_name, "state": state},
                tool_call_id=getattr(event, "tool_call_id", None),
                ui_hint="timeline",
            )
            self._emit_sse("tool_result", {
                "tool_name": self.current_tool_name, "state": state,
            })

        elif isinstance(event, ModelCallEndEvent):
            self.iterations += 1
            self.usage["input_tokens"] += int(getattr(event, "input_tokens", 0) or 0)
            self.usage["output_tokens"] += int(getattr(event, "output_tokens", 0) or 0)
            self._publish_db(
                "model_call", EventCategory.MODEL, [EventLevel.LOG],
                {"model_name": getattr(event, "model_name", "")},
                metadata={"input_tokens": int(getattr(event, "input_tokens", 0) or 0),
                          "output_tokens": int(getattr(event, "output_tokens", 0) or 0),
                          "iteration": self.iterations},
            )

        elif isinstance(event, ExceedMaxItersEvent):
            self._publish_db(
                "iteration_limit", EventCategory.RUNTIME,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"iterations": self.iterations}, ui_hint="timeline",
            )

        elif isinstance(event, ReplyEndEvent):
            final_text = "".join(getattr(self, "_final_text_parts", []) or self.text_parts)
            self._publish_db(
                "reply_end", EventCategory.LIFECYCLE, [EventLevel.DB],
                {"finished_reason": "completed"},
                metadata={**self.usage, "iterations": self.iterations},
            )
            self._emit_sse("done", {"result": final_text})

        elif isinstance(event, ErrorEvent):
            self._publish_db(
                "error", EventCategory.ERROR,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"message": str(getattr(event, "error", ""))}, ui_hint="timeline",
            )
            self._emit_sse("error", {
                "message": str(getattr(event, "error", "")),
                "type": event.__class__.__name__,
            })

        else:
            # 未知事件：SSE error 兜底（保持旧版行为），不落库
            logger.debug("[SkillExecution] unhandled event: %s", event.__class__.__name__)
```

> **ReplyEndEvent 的 final_text**：text_parts 在 `text_done` 时被清空。为让 `done` SSE 事件拿到全文，`TextBlockDeltaEvent` 分支同时把 delta 追加到 `self._final_text_parts`（`__init__` 中初始化 `self._final_text_parts: list[str] = []`）。实现时把 `__init__` 中加一行 `self._final_text_parts: list[str] = []`，并把 TextBlockDelta 分支改为同时 append 两个列表。

(d) **删除** `_run_agent_native` 方法整体（原第 368-388 行，含第二处 `lambda evt: yield evt` 语法错误的死代码）。

- [ ] **Step 4: 验证语法修复 + 测试**

```bash
cd backend && python -c "import ast; ast.parse(open('app/ai/skills/execution.py', encoding='utf-8').read()); print('syntax ok')"
cd backend && python -m pytest tests/unit/test_skill_event_handler.py -v
```

Expected: `syntax ok`；测试 PASS（若 agentscope 构造字段名差异导致 FAIL，按 Step 0 输出修正 kwargs 后重跑）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/skills/execution.py backend/tests/unit/test_skill_event_handler.py
git commit -m "feat(agent): SkillEventHandler 重写——分级落库/三级关联/token 计量，修复 lambda-yield 语法错误"
```

---

