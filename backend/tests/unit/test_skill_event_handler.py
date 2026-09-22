"""SkillEventHandler 重写单测：delta 不落库、块级汇总落库、三级关联、token 计量。

直接构造 agentscope 真实事件对象；构造字段以安装版本 model_fields 为准
（执行前先跑任务简报 Step 0 的字段检查命令）。

Step 0 字段检查结论（本机安装版 agentscope）：
- ReplyStartEvent / ReplyEndEvent 必填 session_id + reply_id（brief 测试已传，兼容）。
- TextBlockDeltaEvent / ThinkingBlockDeltaEvent：reply_id / block_id / delta ✓。
- ToolCallStartEvent：tool_call_id / tool_call_name ✓（与 brief 一致）。
- ToolCallEndEvent：仅 reply_id / tool_call_id，**无 tool_args** —— 测试中移除该 kwarg。
- ModelCallEndEvent：input_tokens / output_tokens，**无 model_name** —— 测试中移除该 kwarg。
- ToolResultEndEvent：state 接受 "success" 字符串（use_enum_values 存为 str）。
- **ErrorEvent 不存在**于安装版：错误经 ReplyEndEvent.error(ErrorInfo) 传递，
  新增 test_error_via_reply_end 覆盖该真实错误路径。
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
        # 安装版 ToolCallEndEvent 无 tool_args 字段（参数经 ToolCallDeltaEvent 流式传输）
        await h.handle(ToolCallEndEvent(reply_id="r1", tool_call_id="tc1"))
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
        # 安装版 ModelCallEndEvent 无 model_name 字段
        await h.handle(ModelCallEndEvent(reply_id="r1", input_tokens=100, output_tokens=50))
        await h.handle(ModelCallEndEvent(reply_id="r1", input_tokens=30, output_tokens=20))
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
        await h.handle(Exception("boom"))  # 未知类型走兜底分支（不落库、不打扰 SSE）
        assert bus.published == []
    asyncio.run(main())


def test_error_via_reply_end():
    """安装版 agentscope 无 ErrorEvent：错误经 ReplyEndEvent.error(ErrorInfo) 传递。"""
    async def main():
        h, bus, out = _handler()
        await h.handle(ReplyStartEvent(reply_id="r1", session_id="s1", name="demo", role="assistant"))
        await h.handle(ReplyEndEvent(
            reply_id="r1", session_id="s1", error={"message": "boom"},
        ))

        types = [e.event_type for e in bus.published]
        assert "error" in types and "reply_end" in types
        err = [e for e in bus.published if e.event_type == "error"][0]
        assert "boom" in err.content["message"]

        # SSE 侧：error + done 都输出
        sse_types = [e.type for e in _drain(out)]
        assert "error" in sse_types and "done" in sse_types
    asyncio.run(main())
