# AgentScope 2.0.8 内核替换全双工语音 Provider — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留 `/duplex/voice/ws` 协议 v2 网关外壳，把手写 dashscope/s2s/local Provider 内核替换为 AgentScope 2.0.8 `RealtimeAgent`（新增 openai 备选），清理废弃前后端代码，新增工具确认与麦克风韧性前端能力。

**Architecture:** 后端新增 `AgentscopeRealtimeProvider`（实现现有 `RealtimeProvider` ABC）+ `BrowserTransport`（继承 agentscope `TransportBase`），按模型名工厂化 `DashScopeRealtimeModel`/`DashScopeAudioRealtimeModel`/`OpenAIRealtimeModel`；网关外壳不动，仅增量处理 interrupt 透传、`tool.confirm` 上行、VAD barge-in 代际。前端主链路不动，新增 confirm UI 与 `useMicLifecycle`。

**Tech Stack:** Python 3.11 + FastAPI + agentscope==2.0.8（已安装于 `backend/.venv`）；Vue3 + TS + Vitest。

**Spec:** `docs/superpowers/specs/2026-09-20-agentscope-voice-s2s-design.md`

**命令约定**（Windows PowerShell）：
- 后端测试：`cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest <path> -v`
- 前端测试：`cd d:\projects\MinWorkBuddy\frontend; npx vitest run <path>`
- 前端 lint：`cd d:\projects\MinWorkBuddy\frontend; npm run lint`

**基点说明（2026-09-21 复核）**：main 已合并 agent-event-p0（20 个提交，HEAD `0288054`，全部位于 `backend/app/ai/**` HITL/EventBus 与前端 assistant 视图）。经 `git diff --stat 637d441..HEAD` 复核，**本计划全部目标路径（`backend/app/duplex/**`、`backend/app/config`、前端语音路径、协议）零变更**；`agentscope==2.0.8` 固定（含 `mcp>=1.15.0,<2.0.0`）已在工作区 requirements 未提交改动中就位，由 Task 6 收编提交。工作区另有一份已批准未实施的会话上下文架构 spec（multi-mode-session-context），与本计划无文件冲突。

**已验证 API 事实**（2026-09-21 对照本地安装包逐项核实，实施时直接引用，勿凭文档或 GitHub main 分支改写）：
- **安装包 2.0.8 的 `agentscope.realtime` 导出**（`dir()` 实测）：`TransportBase / AudioFrame / ControlFrame / ControlFrameType / PlayoutPosition / TransportFrame / TruncationSupport / RealtimeModelBase / RealtimeModelCard / LocalAudioTransport / DashScopeRealtimeModel / DashScopeAudioRealtimeModel / ModelDisconnectedError / VADBase / SpeechTransition` 及模型侧 ModelEvent。**没有 `OpenAIRealtimeModel` / `GeminiRealtimeModel` / `XAIRealtimeModel`**（官方文档与 GitHub main 超前于 2.0.8 发布版）
- `TransportBase` 抽象方法：`start/close/incoming/send_audio(pcm, item_id)/clear_audio()->PlayoutPosition/playout()`；`AudioFrame(pcm)`；`ControlFrame(type: ControlFrameType.TEXT|USER_CONFIRM|INTERRUPT, data: dict)`；`PlayoutPosition(item_id, played_ms, first_played_at)`
- `agentscope.agent.RealtimeAgent(name, system_prompt, model, toolkit=None, state=None, vad=None, aggregator=None)`：`await connect()/close()`、`async for ev in agent.reply_stream(transport)`、`await agent.send(str|Msg|UserConfirmResultEvent|UserInterruptEvent)`、`await agent.interrupt()`、`agent.model.supports_text_input`
- `agentscope.event`（已实测导入）：`ReplyStartEvent(session_id, reply_id, name, role)`、`ReplyEndEvent(reply_id, finished_reason, error)`、`TextBlockDeltaEvent(reply_id, block_id, delta)`、`DataBlockDeltaEvent(reply_id, block_id, media_type, data|url)`（data 为 base64）、`ToolCallStartEvent(reply_id, tool_call_id, tool_call_name)`、`ToolResultEndEvent(reply_id, tool_call_id, state, metadata)`、`RequireUserConfirmEvent(reply_id, tool_calls: List[ToolCallBlock])`、`UserConfirmResultEvent(reply_id, confirm_results)`、**`ConfirmResult(confirmed, tool_call, rules=None)`**、**`ToolResultState` 枚举也定义于 event 模块内部**（但**未**从 `agentscope.event.__init__` 导出；正确导入路径为 `agentscope.message`，见下）
- `agentscope.message`：`ToolCallBlock(id, name, input: str(JSON), state)`、**`ToolResultState`**（`tool/_response.py` 即从 `..message` 导入）
- `agentscope.tool` 导出（实测）：`Toolkit / ToolBase / ToolChunk / ToolGroup / FunctionTool / MCPTool / Bash / Read / ...`（**无 `ToolResultState`**）。`FunctionTool(func, name=None, description=None, input_schema=None, is_concurrency_safe=True, is_read_only=False, ...)`——自动从函数签名提取元数据并把返回值规范为 `ToolChunk`，是包装 MCP 工具回调的首选
- `agentscope.credential`：`DashScopeCredential(api_key)`；`agentscope.realtime.DashScopeRealtimeModel(model=, credential=, parameters=Parameters(voice=))`、`DashScopeAudioRealtimeModel(model=, credential=)`；模型属性 `input_sample_rate/output_sample_rate/card`
- 本仓库：`RealtimeProvider` ABC（`app/duplex/voice/providers/base.py`：`connect/send_audio/send_text/configure_session/events/close/get_capabilities`）；`ProviderEvent(type, data, capabilities)`；`ProviderRegistry`（`register/_ensure_defaults/resolve/resolve_backup/is_configured/select` + 模块尾 `_register_defaults()`）；`get_provider(key)`/`register_provider(key, cls)`；网关 `websocket_gateway.py`（`_normalize_outbound` 识别 `audio_delta/transcript/tts_transcript/transcript_delta/transcript_final/speech_started/speech_stopped/response_started/playback_cancelled`，其余透传）；`voice_config.py`（`_voice_row_platform/_voice_row_usable/resolve_voice_config`、`VALID_DASHSCOPE_REALTIME_MODELS`、`S2S_PLATFORM` 常量）；`McpSessionResolver.resolve_tools()` → `MCPAdapter().get_tool_schemas()`（`[{name, description, inputSchema}]`）；`MCPAdapter.call_tool(name, args)`；`ProviderCapabilities`（`server_vad/native_transcription/barge_in_mode/input_sample_rate/output_sample_rate` 等）

---

## Task 1: BrowserTransport（AgentScope 传输桥）

**Files:**
- Create: `backend/app/duplex/voice/providers/agentscope_transport.py`
- Test: `backend/tests/duplex/voice/test_agentscope_transport.py`

- [ ] **Step 1: 写失败测试**

```python
"""BrowserTransport 单测：上行桥接、下行水位记账、打断清零、重采样。"""
import asyncio
import pytest

from app.duplex.voice.providers.agentscope_transport import BrowserTransport


def _make_transport(in_rate=16000, out_rate=24000):
    uplink: asyncio.Queue = asyncio.Queue()
    events: asyncio.Queue = asyncio.Queue()
    t = BrowserTransport(input_sample_rate=in_rate, output_sample_rate=out_rate,
                         uplink=uplink, downlink_events=events)
    return t, uplink, events


@pytest.mark.asyncio
async def test_submit_audio_yields_audio_frame():
    t, uplink, _ = _make_transport()
    await t.start()
    t.submit_audio(b"\x01\x00" * 160)
    frame = await asyncio.wait_for(uplink.get(), timeout=1)
    assert type(frame).__name__ == "AudioFrame"
    assert frame.pcm == b"\x01\x00" * 160


@pytest.mark.asyncio
async def test_send_audio_updates_playout_watermark_and_emits():
    t, _, events = _make_transport()
    await t.start()
    await t.send_audio(b"\x00\x00" * 24000, item_id="item_1")  # 1s @24k
    pos = t.playout()
    assert pos.item_id == "item_1"
    assert pos.played_ms == 1000
    ev = events.get_nowait()
    assert ev.type == "audio_delta"
    assert ev.data["audio"] == b"\x00\x00" * 24000


@pytest.mark.asyncio
async def test_clear_audio_reports_and_resets():
    t, _, events = _make_transport()
    await t.start()
    await t.send_audio(b"\x00\x00" * 12000, item_id="item_1")  # 500ms
    pos = await t.clear_audio()
    assert pos.item_id == "item_1"
    assert pos.played_ms == 500
    assert t.playout().played_ms == 0
    types = [events.get_nowait().type for _ in range(events.qsize())]
    assert "playback_cancelled" in types


@pytest.mark.asyncio
async def test_resample_16k_to_24k():
    t, uplink, _ = _make_transport(in_rate=24000, out_rate=24000)
    await t.start()
    t.submit_resampled(b"\x00\x00" * 16000, source_rate=16000)
    frame = await asyncio.wait_for(uplink.get(), timeout=1)
    assert len(frame.pcm) == 48000  # 24000 样本 × 2B


@pytest.mark.asyncio
async def test_new_item_resets_watermark():
    t, _, _ = _make_transport()
    await t.start()
    await t.send_audio(b"\x00\x00" * 24000, item_id="a")
    await t.send_audio(b"\x00\x00" * 4800, item_id="b")  # 200ms
    assert t.playout().item_id == "b"
    assert t.playout().played_ms == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_agentscope_transport.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 实现 agentscope_transport.py**

```python
"""浏览器侧 TransportBase 桥接（协议 v2 网关 ⇄ AgentScope RealtimeAgent，spec §2.2）。

- 上行：网关 PCM/控制帧 → AudioFrame/ControlFrame（限深 100 块，满丢最旧）
- 下行：agent 音频 → 事件队列（audio_delta）+ 发送水位记账（服务端模拟 PlayoutPosition）
- clear_audio：返回水位并清零（barge-in truncate 事实来源），并产出 playback_cancelled
- 采样率契约：transport.input_sample_rate 必须等于模型上行率；
  浏览器 16k 与模型 24k 不一致时经 submit_resampled 线性插值重采样。
"""
import asyncio
import time
from typing import AsyncIterator

from agentscope.realtime import (
    AudioFrame, ControlFrame, ControlFrameType, PlayoutPosition, TransportBase,
)

from app.duplex.voice.providers.base import ProviderEvent

_UPLINK_MAX = 100


class BrowserTransport(TransportBase):
    """桥接浏览器 WebSocket 与 RealtimeAgent 的 TransportBase 实现。"""

    def __init__(self, input_sample_rate: int, output_sample_rate: int,
                 uplink: asyncio.Queue, downlink_events: asyncio.Queue) -> None:
        self.input_sample_rate = input_sample_rate
        self.output_sample_rate = output_sample_rate
        self._uplink = uplink
        self._events = downlink_events
        self._running = False
        self._item_id = ""
        self._played_samples = 0
        self._first_played_at: float | None = None

    async def start(self) -> None:
        self._running = True

    async def close(self) -> None:
        self._running = False

    async def incoming(self) -> AsyncIterator[AudioFrame | ControlFrame]:
        while True:
            frame = await self._uplink.get()
            if frame is None:  # 关闭哨兵
                return
            yield frame

    # ---- 上行入口（由 Provider 调用）----

    def submit_audio(self, pcm: bytes) -> None:
        self._put_uplink(AudioFrame(pcm=pcm))

    def submit_resampled(self, pcm: bytes, source_rate: int) -> None:
        if source_rate != self.input_sample_rate:
            pcm = _resample_pcm16(pcm, source_rate, self.input_sample_rate)
        self._put_uplink(AudioFrame(pcm=pcm))

    def submit_text(self, text: str) -> None:
        self._put_uplink(ControlFrame(type=ControlFrameType.TEXT, data={"text": text}))

    def submit_confirm(self, data: dict) -> None:
        self._put_uplink(ControlFrame(type=ControlFrameType.USER_CONFIRM, data=data))

    def submit_interrupt(self) -> None:
        self._put_uplink(ControlFrame(type=ControlFrameType.INTERRUPT, data={}))

    def _put_uplink(self, frame) -> None:
        if not self._running:
            return
        if self._uplink.qsize() >= _UPLINK_MAX:
            try:
                self._uplink.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._uplink.put_nowait(frame)

    def close_uplink(self) -> None:
        self._uplink.put_nowait(None)

    # ---- 下行（agent 调用）----

    async def send_audio(self, pcm: bytes, item_id: str) -> None:
        if item_id != self._item_id:
            self._item_id = item_id
            self._played_samples = 0
            self._first_played_at = time.monotonic()
        self._played_samples += len(pcm) // 2
        await self._events.put(
            ProviderEvent(type="audio_delta", data={"audio": pcm}))

    async def clear_audio(self) -> PlayoutPosition:
        pos = self.playout()
        self._played_samples = 0
        self._first_played_at = None
        await self._events.put(ProviderEvent(
            type="playback_cancelled",
            data={"item_id": pos.item_id, "played_ms": pos.played_ms,
                  "reason": "barge_in"}))
        return pos

    def playout(self) -> PlayoutPosition:
        return PlayoutPosition(
            item_id=self._item_id,
            played_ms=self._played_samples * 1000 // self.output_sample_rate,
            first_played_at=self._first_played_at,
        )


def _resample_pcm16(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """PCM16 单声道线性插值重采样（16k→24k 上行适配）。"""
    if from_rate == to_rate or not pcm:
        return pcm
    import array
    samples = array.array("h")
    samples.frombytes(pcm)
    if len(samples) < 2:
        return pcm
    ratio = from_rate / to_rate
    out_len = int(len(samples) / ratio)
    out = array.array("h", bytes(2 * out_len))
    for i in range(out_len):
        src = i * ratio
        i0 = int(src)
        i1 = min(i0 + 1, len(samples) - 1)
        frac = src - i0
        out[i] = int(samples[i0] * (1 - frac) + samples[i1] * frac)
    return out.tobytes()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_agentscope_transport.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/duplex/voice/providers/agentscope_transport.py backend/tests/duplex/voice/
git commit -m "feat(voice): BrowserTransport 桥接协议v2网关与 AgentScope TransportBase"
```

---

## Task 2: 模型工厂 + AgentscopeRealtimeProvider（事件映射）

**Files:**
- Create: `backend/app/duplex/voice/providers/agentscope.py`
- Test: `backend/tests/duplex/voice/test_agentscope_provider.py`

- [ ] **Step 1: 写失败测试**

测试用**真实 agentscope 事件类**构造（FakeEvent 无法通过 `match` 判别），`tool_calls` 内用真实 `ToolCallBlock`：

```python
"""AgentscopeRealtimeProvider 单测：AgentScope 事件 → ProviderEvent 映射。"""
import asyncio
import base64
import pytest

from agentscope.event import (
    DataBlockDeltaEvent, ReplyEndEvent, ReplyStartEvent,
    RequireUserConfirmEvent, TextBlockDeltaEvent,
)
from agentscope.message import ToolCallBlock

from app.duplex.voice.providers.agentscope import AgentscopeRealtimeProvider


class FakeModel:
    input_sample_rate = 16000
    output_sample_rate = 24000
    supports_text_input = True
    model_name = "qwen3.5-omni-flash-realtime"


class FakeAgent:
    def __init__(self, events=()):
        self.model = FakeModel()
        self._events = list(events)

    async def connect(self): ...
    async def close(self): ...

    async def reply_stream(self, transport):
        for ev in self._events:
            yield ev
        await asyncio.Event().wait()


def _reply_start(reply_id, role):
    return ReplyStartEvent(session_id="s", reply_id=reply_id, name="a", role=role)


def _reply_end(reply_id):
    return ReplyEndEvent(session_id="s", reply_id=reply_id)


def _make_provider(events):
    p = AgentscopeRealtimeProvider(key="dashscope")
    p._agent = FakeAgent(events)
    p._queue = asyncio.Queue()
    return p


async def _drain(p, n):
    got = []
    async for ev in p.events():
        got.append(ev)
        if len(got) == n:
            break
    return got


@pytest.mark.asyncio
async def test_assistant_reply_mapping():
    audio = base64.b64encode(b"\x00\x00" * 100).decode()
    p = _make_provider([
        _reply_start("r1", "assistant"),
        TextBlockDeltaEvent(reply_id="r1", block_id="b1", delta="你好"),
        DataBlockDeltaEvent(reply_id="r1", block_id="b2",
                            media_type="audio/pcm;rate=24000", data=audio),
        _reply_end("r1"),
    ])
    await p._start_pump()
    got = await _drain(p, 4)
    assert [e.type for e in got] == [
        "response_started", "tts_transcript", "audio_delta", "playback.ended"]
    assert got[1].data["text"] == "你好"
    assert got[2].data["audio"] == b"\x00\x00" * 100


@pytest.mark.asyncio
async def test_user_reply_mapping():
    p = _make_provider([
        _reply_start("u1", "user"),
        TextBlockDeltaEvent(reply_id="u1", block_id="b1", delta="查询天气"),
        _reply_end("u1"),
    ])
    await p._start_pump()
    got = await _drain(p, 3)
    assert [e.type for e in got] == ["speech_started", "transcript", "speech_stopped"]


@pytest.mark.asyncio
async def test_require_confirm_mapping():
    tc = ToolCallBlock(id="call_1", name="database_query", input='{"query": "x"}')
    p = _make_provider([RequireUserConfirmEvent(reply_id="r1", tool_calls=[tc])])
    await p._start_pump()
    ev = (await _drain(p, 1))[0]
    assert ev.type == "tool.confirm_required"
    assert ev.data["confirm_id"] == "call_1"
    assert ev.data["tool_name"] == "database_query"
    assert ev.data["arguments"] == {"query": "x"}
    assert "call_1" in p._pending_confirms


@pytest.mark.asyncio
async def test_send_text_unsupported_emits_error():
    p = _make_provider([])
    p._agent.model.supports_text_input = False
    await p._start_pump()
    await p.send_text("hi")
    ev = (await _drain(p, 1))[0]
    assert ev.type == "error"
    assert "不支持文本输入" in ev.data["message"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_agentscope_provider.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 providers/agentscope.py**

```python
"""AgentScope 2.0.8 RealtimeAgent 内核 Provider（spec §2）。

DashScopeAgentProvider(key="dashscope") / OpenAIAgentProvider(key="openai")。
事件映射（spec §3.1）：
ReplyStart(user)→speech_started；ReplyStart(assistant)→response_started；
TextBlockDelta→transcript|tts_transcript；DataBlockDelta→audio_delta；
ReplyEnd(user)→speech_stopped；ReplyEnd(assistant)→playback.ended；
ToolCallStart→tool_call；ToolResultEnd→tool_result；
RequireUserConfirm→tool.confirm_required。
"""
import asyncio
import json
from typing import Any, AsyncGenerator, Dict, Optional

from loguru import logger

from app.duplex.voice.providers.base import RealtimeProvider, ProviderEvent
from app.duplex.voice.providers.agentscope_transport import BrowserTransport


def build_realtime_model(provider_key: str, model_name: str, api_key: str,
                         base_url: Optional[str] = None,
                         voice: str = "default"):
    """模型工厂（spec §2.3）：按模型名前缀选择 AgentScope 模型类。"""
    from agentscope.credential import DashScopeCredential, OpenAICredential

    if model_name.startswith("qwen-audio-3.0-realtime"):
        from agentscope.realtime import DashScopeAudioRealtimeModel
        return DashScopeAudioRealtimeModel(
            model=model_name, credential=DashScopeCredential(api_key=api_key))
    if model_name.startswith(("qwen3.5-omni", "qwen3-omni", "qwen-omni")):
        from agentscope.realtime import DashScopeRealtimeModel
        return DashScopeRealtimeModel(
            model=model_name, credential=DashScopeCredential(api_key=api_key),
            parameters=DashScopeRealtimeModel.Parameters(voice=voice))
    if model_name.startswith("gpt-realtime"):
        # agentscope 2.0.8 发布版不含 OpenAIRealtimeModel（GitHub main 已有）。
        # 惰性导入：框架升级后此处自动启用，无需改代码。
        try:
            from agentscope.realtime import OpenAIRealtimeModel
        except ImportError as e:
            raise NotImplementedError(
                f"当前 agentscope 版本不含 OpenAIRealtimeModel（gpt-realtime "
                f"模型需升级 agentscope > 2.0.8 后使用）: {e}") from e
        return OpenAIRealtimeModel(
            model=model_name, credential=OpenAICredential(api_key=api_key))
    raise ValueError(f"未知实时模型: {model_name}（provider={provider_key}）")


def _safe_json(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"_raw": raw}


class AgentscopeRealtimeProvider(RealtimeProvider):
    """以 AgentScope RealtimeAgent 为内核的实时语音 Provider。"""

    def __init__(self, key: str) -> None:
        self.key = key
        self._system_prompt = ""
        self._mcp_tool_schemas: list = []
        self._agent = None
        self._transport: Optional[BrowserTransport] = None
        self._queue: Optional[asyncio.Queue] = None
        self._pump_task: Optional[asyncio.Task] = None
        self._user_replies: set = set()
        # confirm_id → (reply_id, ToolCallBlock)
        self._pending_confirms: Dict[str, tuple] = {}
        self._closed = False

    # ---- 组装（测试可覆写）----

    def _agent_factory(self, model, toolkit):
        from agentscope.agent import RealtimeAgent
        return RealtimeAgent(name="mediator", system_prompt=self._system_prompt,
                             model=model, toolkit=toolkit)

    def _toolkit_factory(self):
        from app.duplex.voice.toolkit_builder import build_toolkit
        return build_toolkit(self._mcp_tool_schemas)

    # ---- RealtimeProvider 接口 ----

    async def connect(self, session_config: Dict[str, Any]) -> None:
        self._system_prompt = session_config.get("instructions", "")
        self._mcp_tool_schemas = session_config.get("mcp_tools", [])
        model = build_realtime_model(
            provider_key=self.key,
            model_name=session_config.get("model", ""),
            api_key=session_config.get("api_key", ""),
            base_url=session_config.get("base_url"),
            voice=session_config.get("voice", "default"),
        )
        self._queue = asyncio.Queue()
        self._transport = BrowserTransport(
            input_sample_rate=model.input_sample_rate,
            output_sample_rate=model.output_sample_rate,
            uplink=asyncio.Queue(), downlink_events=self._queue,
        )
        self._agent = self._agent_factory(model, self._toolkit_factory())
        await self._agent.connect()
        await self._transport.start()
        await self._start_pump()

    async def _start_pump(self) -> None:
        if self._pump_task is not None or self._agent is None:
            return
        self._pump_task = asyncio.create_task(
            self._pump(self._agent, self._transport, self._queue))

    async def _pump(self, agent, transport, queue) -> None:
        from agentscope.event import (
            DataBlockDeltaEvent, ReplyEndEvent, ReplyStartEvent,
            RequireUserConfirmEvent, TextBlockDeltaEvent, ToolCallStartEvent,
            ToolResultEndEvent,
        )
        try:
            async for ev in agent.reply_stream(transport):
                match ev:
                    case ReplyStartEvent(role="user"):
                        self._user_replies.add(ev.reply_id)
                        await queue.put(ProviderEvent("speech_started", {}))
                    case ReplyStartEvent():
                        await queue.put(ProviderEvent("response_started", {}))
                    case TextBlockDeltaEvent():
                        is_user = ev.reply_id in self._user_replies
                        await queue.put(ProviderEvent(
                            "transcript" if is_user else "tts_transcript",
                            {"text": ev.delta}))
                    case DataBlockDeltaEvent() if ev.data:
                        import base64 as b64
                        await queue.put(ProviderEvent(
                            "audio_delta", {"audio": b64.b64decode(ev.data)}))
                    case ToolCallStartEvent():
                        await queue.put(ProviderEvent(
                            "tool_call", {"call_id": ev.tool_call_id,
                                          "name": ev.tool_call_name}))
                    case ToolResultEndEvent():
                        await queue.put(ProviderEvent(
                            "tool_result", {"call_id": ev.tool_call_id,
                                            "state": str(ev.state)}))
                    case RequireUserConfirmEvent():
                        for tc in ev.tool_calls:
                            self._pending_confirms[tc.id] = (ev.reply_id, tc)
                            await queue.put(ProviderEvent(
                                "tool.confirm_required",
                                {"confirm_id": tc.id, "tool_name": tc.name,
                                 "arguments": _safe_json(tc.input),
                                 "timeout_ms": 300000}))
                    case ReplyEndEvent() if ev.reply_id in self._user_replies:
                        await queue.put(ProviderEvent("speech_stopped", {}))
                    case ReplyEndEvent():
                        await queue.put(ProviderEvent(
                            "playback.ended",
                            {"reply_id": ev.reply_id,
                             "finished_reason": str(ev.finished_reason)}))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - 泵异常落事件流
            if not self._closed:
                logger.error(f"AgentScope 事件泵异常: {e}")
                await queue.put(ProviderEvent(
                    "error", {"code": "fatal", "message": str(e)}))

    async def send_audio(self, pcm_data: bytes) -> None:
        assert self._transport is not None
        if self._transport.input_sample_rate != 16000:
            self._transport.submit_resampled(pcm_data, source_rate=16000)
        else:
            self._transport.submit_audio(pcm_data)

    async def send_text(self, text: str) -> None:
        assert self._transport is not None
        if not self._agent.model.supports_text_input:
            await self._queue.put(ProviderEvent(
                "error", {"code": "text_unsupported",
                          "message": f"{type(self._agent.model).__name__} 不支持文本输入"}))
            return
        self._transport.submit_text(text)

    async def interrupt(self) -> None:
        if self._agent is not None:
            await self._agent.interrupt()

    async def resolve_confirm(self, confirm_id: str, approved: bool) -> None:
        entry = self._pending_confirms.pop(confirm_id, None)
        if entry is None:
            return
        reply_id, tool_call = entry
        from agentscope.event import ConfirmResult, UserConfirmResultEvent
        payload = UserConfirmResultEvent(
            reply_id=reply_id,
            confirm_results=[ConfirmResult(confirmed=approved,
                                           tool_call=tool_call)],
        ).model_dump(exclude_none=True)
        self._transport.submit_confirm(payload)

    async def configure_session(self, **kwargs) -> None:
        return None  # 会话在 connect 一次性配置

    async def events(self) -> AsyncGenerator[ProviderEvent, None]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def close(self) -> None:
        self._closed = True
        if self._pump_task is not None:
            self._pump_task.cancel()
            self._pump_task = None
        if self._transport is not None:
            self._transport.close_uplink()
            await self._transport.close()
        if self._agent is not None:
            try:
                await self._agent.close()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"agent close 异常（忽略）: {e}")
        if self._queue is not None:
            await self._queue.put(None)

    def get_capabilities(self):
        from app.duplex.voice.capabilities import ProviderCapabilities
        return ProviderCapabilities(
            input_sample_rate=16000, output_sample_rate=24000,
            server_vad=True, native_transcription=True,
            barge_in_mode="server")

    def is_configured(self) -> bool:
        from app.duplex.voice.voice_config import resolve_voice_config
        try:
            return bool(resolve_voice_config(self.key).get("configured"))
        except Exception:  # noqa: BLE001
            return False


class DashScopeAgentProvider(AgentscopeRealtimeProvider):
    key = "dashscope"


class OpenAIAgentProvider(AgentscopeRealtimeProvider):
    key = "openai"
```

- [ ] **Step 4: 运行确认通过**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_agentscope_provider.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/duplex/voice/providers/agentscope.py backend/tests/duplex/voice/test_agentscope_provider.py
git commit -m "feat(voice): AgentscopeRealtimeProvider 内核与事件映射"
```

---

## Task 3: Provider 注册与 Registry 更新

**Files:**
- Modify: `backend/app/duplex/voice/providers/registry.py:27-50,114-123`
- Modify: `backend/app/duplex/voice/constants.py:47-49`
- Modify: `backend/app/duplex/voice/websocket_gateway.py:44-46`
- Test: `backend/tests/duplex/voice/test_registry.py`

- [ ] **Step 1: 写失败测试**

```python
"""Registry 更新后：默认注册 dashscope/openai，local/s2s 移除。"""
from app.duplex.voice.providers.registry import ProviderRegistry


def test_default_keys_registered():
    ProviderRegistry._ensure_defaults()
    keys = ProviderRegistry.list_available()
    assert "dashscope" in keys
    assert "openai" in keys
    assert "local" not in keys
    assert "s2s" not in keys


def test_resolve_backup_mutual():
    assert ProviderRegistry.resolve_backup("dashscope") == "openai"
    assert ProviderRegistry.resolve_backup("openai") == "dashscope"
    assert ProviderRegistry.resolve_backup("unknown") is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_registry.py -v`
Expected: FAIL（local/s2s 仍注册、openai 缺失）

- [ ] **Step 3: registry.py `_ensure_defaults`（L27-50）替换**

```python
    @classmethod
    def _ensure_defaults(cls) -> None:
        """惰性确保默认 Provider 已注册（幂等）。"""
        if "dashscope" not in cls._providers:
            try:
                from app.duplex.voice.providers.agentscope import (
                    DashScopeAgentProvider)
                cls.register(DashScopeAgentProvider)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"默认 Provider dashscope 注册失败: {e}")
        if "openai" not in cls._providers:
            try:
                from app.duplex.voice.providers.agentscope import (
                    OpenAIAgentProvider)
                cls.register(OpenAIAgentProvider)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"备选 Provider openai 注册失败: {e}")
```

- [ ] **Step 4: registry.py 模块尾 `_register_defaults`（L114-123）替换**

```python
def _register_defaults() -> None:
    """默认注册 AgentScope 内核 Provider（导入即生效）。"""
    from app.duplex.voice.providers.agentscope import (
        DashScopeAgentProvider, OpenAIAgentProvider)
    ProviderRegistry.register(DashScopeAgentProvider)
    ProviderRegistry.register(OpenAIAgentProvider)
```

- [ ] **Step 5: constants.py `ProviderKey`（L47-49）替换**

```python
class ProviderKey(str, Enum):
    DASHSCOPE = "dashscope"
    OPENAI = "openai"
```

- [ ] **Step 6: websocket_gateway.py 删除 L44-46 local/s2s import**

删除以下三行：

```python
# LocalProvider / S2SProvider 自注册到 ProviderRegistry（import 即生效）
from app.duplex.voice.providers.local import LocalProvider  # noqa: F401
from app.duplex.voice.providers.s2s import S2SProvider  # noqa: F401
```

- [ ] **Step 7: 运行新测试 + 记录存量失败清单**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_registry.py -v`
Expected: PASS。随后运行 `pytest tests/duplex/voice/ -q`，把引用 local/s2s 的失败用例记入清单（Task 6 处理）

- [ ] **Step 8: Commit**

```bash
git add backend/app/duplex/voice/providers/registry.py backend/app/duplex/voice/constants.py backend/app/duplex/voice/websocket_gateway.py backend/tests/duplex/voice/test_registry.py
git commit -m "feat(voice): Provider 注册表切换为 AgentScope 内核（dashscope/openai）"
```

---

## Task 4: voice_config 平台化 + 网关增量（interrupt/confirm/ping/barge-in）

**Files:**
- Modify: `backend/app/duplex/voice/voice_config.py:19-58,136-141`
- Modify: `backend/app/duplex/voice/providers/base.py`（send_text 后追加）
- Modify: `backend/app/duplex/voice/constants.py`（EventType 追加）
- Modify: `backend/app/duplex/voice/websocket_gateway.py:135-176,232-260,301-316`
- Test: `backend/tests/duplex/voice/test_gateway_increment.py`

- [ ] **Step 1: 写失败测试**

```python
"""网关增量：ping 回客户端、interrupt 调 provider.interrupt、
tool.confirm 上行路由、voice_config 平台匹配。"""
import json
import pytest

from app.duplex.voice.voice_config import _platform_matches


class StubProvider:
    def __init__(self):
        self.interrupted = False
        self.confirmed = []

    async def interrupt(self):
        self.interrupted = True

    async def resolve_confirm(self, confirm_id, approved):
        self.confirmed.append((confirm_id, approved))


def test_platform_matches():
    assert _platform_matches("openai", "openai") is True
    assert _platform_matches("openai", "DashScope") is False
    assert _platform_matches("dashscope", "openai") is False
    assert _platform_matches(None, "s2s") is False


@pytest.mark.asyncio
async def test_ping_replies_to_client():
    from app.duplex.voice.websocket_gateway import _handle_control_frame
    from app.duplex.voice.turn_state import TurnState

    provider = StubProvider()
    sent = []

    class FakeWs:
        async def send_text(self, raw):
            sent.append(json.loads(raw))

    await _handle_control_frame({"type": "ping"}, provider, TurnState(), "s1",
                                FakeWs())
    assert sent == [{"type": "pong"}]


@pytest.mark.asyncio
async def test_interrupt_calls_provider():
    from app.duplex.voice.websocket_gateway import _handle_control_frame
    from app.duplex.voice.turn_state import TurnState

    provider = StubProvider()
    turn = TurnState()
    turn.turn_id = "t1"
    turn.on_speech_started()
    await _handle_control_frame({"type": "interrupt"}, provider, turn, "s1")
    assert provider.interrupted is True
    assert turn.generation >= 1


@pytest.mark.asyncio
async def test_tool_confirm_routed():
    from app.duplex.voice.websocket_gateway import _handle_control_frame
    from app.duplex.voice.turn_state import TurnState

    provider = StubProvider()
    await _handle_control_frame(
        {"type": "tool.confirm",
         "data": {"confirm_id": "c1", "approved": True}},
        provider, TurnState(), "s1")
    assert provider.confirmed == [("c1", True)]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_gateway_increment.py -v`
Expected: FAIL（`_platform_matches` 不存在；ping 走 send_text；interrupt 不调 provider；tool.confirm 未处理）

- [ ] **Step 3: base.py `send_text` 后追加**

```python
    async def interrupt(self) -> None:
        """请求打断当前回复（子类按需实现；默认 no-op 兼容测试桩）。"""
        return None

    async def resolve_confirm(self, confirm_id: str, approved: bool) -> None:
        """回传工具确认结果（子类按需实现）。"""
        return None
```

- [ ] **Step 4: voice_config.py 修改**

常量区（L28-32）：删除 `S2S_PLATFORM`/`DEFAULT_S2S_REALTIME_URL`/`DEFAULT_S2S_MODEL_NAME`，新增：

```python
# 支持的语音平台（provider key 与 ai_api_key.platform 对齐；
# DashScope 平台值历史上为 "DashScope"，openai 平台值小写）
SUPPORTED_VOICE_PLATFORMS = ("DashScope", "openai")
```

`_voice_row_usable`（L45-58）替换：

```python
def _voice_row_usable(model: AiChatModel, key: Optional[AiApiKey]) -> bool:
    """模型行是否可用于建立实时连接（列表过滤与默认解析共用）。"""
    platform = _voice_row_platform(model, key)
    api_key = key.api_key if key else None
    if platform == "DashScope":
        return model.model in VALID_DASHSCOPE_REALTIME_MODELS and bool(api_key)
    # openai 等其它平台：有 Key 且模型名非空即可用
    # （模型有效性由 AgentScope 模型卡片在 connect 时校验）
    return bool(api_key) and bool(model.model)


def _platform_matches(want: Optional[str], row_platform: str) -> bool:
    """provider key 与模型行平台匹配：None→仅排除 s2s；指定→忽略大小写精确匹配。"""
    if want is None:
        return row_platform != "s2s"
    return row_platform.lower() == want.lower()
```

`resolve_voice_config` 候选过滤（L136-141）替换：

```python
        candidates = [
            r for r in rows
            if _platform_matches(provider_key,
                                 _voice_row_platform(r, r.api_key_obj))
            and _voice_row_usable(r, r.api_key_obj)
        ]
```

`_row_dict`（L64-65）删除 s2s base_url 兜底两行。

- [ ] **Step 5: constants.py EventType（PLAYBACK_CANCELLED 之后）追加**

```python
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_CONFIRM_REQUIRED = "tool.confirm_required"
    TOOL_CONFIRM = "tool.confirm"
```

- [ ] **Step 6: websocket_gateway.py 修改**

(a) L232 配置解析 gate `if provider in ("dashscope", "s2s"):` 改为 `if provider in ("dashscope", "openai"):`；L248-249 错误文案删去 s2s 提示，改为 `"未配置语音模型：请在「语音模型配置」中新增并启用一个语音模型（type=7）"`。

(b) connect 前（L229 附近）追加 MCP 工具 schema 解析：

```python
    mcp_tool_schemas: list = []
    if agent_id:
        try:
            from app.duplex.voice.mcp_session_resolver import McpSessionResolver
            mcp_tool_schemas = await McpSessionResolver().resolve_tools()
        except Exception as e:  # noqa: BLE001 - MCP 注入失败不阻塞语音
            logger.warning(f"MCP 工具注入失败（忽略）: {e}")
```

session_config（L253-260）追加一项 `"mcp_tools": mcp_tool_schemas,`。

(c) `_handle_control_frame`（L135-176）整体替换：

```python
async def _handle_control_frame(
    frame: Dict[str, Any],
    realtime_provider: RealtimeProvider,
    turn: TurnState,
    voice_session_id: str,
    websocket: Optional[WebSocket] = None,
) -> None:
    """处理客户端控制帧（协议 v2 + tool.confirm 增量）。"""
    ftype = frame.get("type")
    if ftype == "input.message":
        text = frame.get("text", "")
        turn.turn_id = str(uuid.uuid4())
        turn.on_speech_started()
        append_turn(voice_session_id, turn.turn_id, "user", "text", transcript=text)
        timeout_s = settings.VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS / 1000
        try:
            await asyncio.wait_for(
                realtime_provider.send_text(text), timeout=timeout_s)
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning("语音响应超时（inactivity），复位为聆听态")
            turn.reset_listening()
            if websocket is not None:
                await websocket.send_text(json.dumps({
                    "type": EventType.ERROR.value,
                    "code": ErrorCode.INACTIVITY.value,
                    "message": "响应超时",
                }, ensure_ascii=False))
    elif ftype == "tool.confirm":
        data = frame.get("data", {})
        confirm = getattr(realtime_provider, "resolve_confirm", None)
        if confirm is not None:
            await confirm(data.get("confirm_id", ""), bool(data.get("approved")))
    elif ftype in ("input.mute", "output.mode"):
        pass  # 存量 no-op
    elif ftype == "interrupt":
        _apply_interrupt(turn, voice_session_id)
        interrupt = getattr(realtime_provider, "interrupt", None)
        if interrupt is not None:
            await interrupt()
    elif ftype == "ping":
        # 修复：pong 回客户端，而非发给上游 Provider
        if websocket is not None:
            await websocket.send_text(
                json.dumps({"type": EventType.PONG.value}))


def _apply_interrupt(turn: TurnState, voice_session_id: str) -> None:
    """打断统一入口：代际 +1 + 轮次标记（客户端 interrupt 与 VAD barge-in 共用）。"""
    if turn.turn_id:
        turn.on_interrupt()
        turn.generation += 1
        mark_interrupted(turn.turn_id)
        bump_generation(turn.turn_id)
```

(d) `provider_reader`（L301-316）在 `async for` 首行后追加：

```python
            if event.type == "playback_cancelled":
                _apply_interrupt(turn, voice_session_id)
```

- [ ] **Step 7: 运行确认通过**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/ -v`
Expected: Task 1-4 全部 PASS（Task 3 清单中的 local/s2s 存量失败允许保留）

- [ ] **Step 8: Commit**

```bash
git add backend/app/duplex/voice/
git commit -m "feat(voice): 网关增量——interrupt 透传/tool.confirm 上行/ping 修复/VAD barge-in 代际/openai 平台"
```

---

## Task 5: Toolkit 构建（MCP 工具注入）

**Files:**
- Create: `backend/app/duplex/voice/toolkit_builder.py`
- Test: `backend/tests/duplex/voice/test_toolkit_builder.py`

- [ ] **Step 1: 写失败测试**

```python
"""toolkit_builder：MCPAdapter 工具 schema → AgentScope ToolBase 包装。"""
import pytest

from app.duplex.voice.toolkit_builder import build_toolkit, McpToolWrapper


@pytest.mark.asyncio
async def test_wrapper_calls_fn_and_returns_chunk():
    calls = []

    async def fake_call(name, args):
        calls.append((name, args))
        return {"ok": True, "rows": 3}

    tool = McpToolWrapper(
        schema={"name": "database_query", "description": "查询",
                "inputSchema": {"type": "object",
                                "properties": {"query": {"type": "string"}}}},
        call_fn=fake_call)
    chunk = await tool.call(query="select 1")
    assert calls == [("database_query", {"query": "select 1"})]
    assert chunk.is_last is True


@pytest.mark.asyncio
async def test_wrapper_error_returns_error_chunk():
    async def bad_call(name, args):
        raise RuntimeError("boom")

    tool = McpToolWrapper(
        schema={"name": "t", "description": "d", "inputSchema": {"type": "object"}},
        call_fn=bad_call)
    chunk = await tool.call()
    assert "boom" in str(chunk.content)


@pytest.mark.asyncio
async def test_build_toolkit_registers_all_schemas():
    async def fake_call(name, args):
        return {}

    schemas = [
        {"name": "t1", "description": "d1", "inputSchema": {"type": "object"}},
        {"name": "t2", "description": "d2", "inputSchema": {"type": "object"}},
    ]
    tk = build_toolkit(schemas, call_fn=fake_call)
    names = {t.name for g in tk.tool_groups for t in g.tools}
    assert names == {"t1", "t2"}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_toolkit_builder.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 toolkit_builder.py**

已核实事实：`ToolResultState` 从 `agentscope.message` 导入（`agentscope.tool` 不导出它），完成态成员为 `SUCCESS`（实测成员值 `['success','error','interrupted','denied','running']`）；`agentscope.tool` 另有 `FunctionTool(func, name, description, input_schema, ...)` 可自动包装函数（备选方案，本实现用手写 ToolBase 子类以显式控制成功/失败态）。

```python
"""RealtimeAgent Toolkit 构建（spec §2.4）。

MCPAdapter 工具 schema（{name, description, inputSchema}）→ AgentScope
ToolBase 包装，执行回调 call_fn（默认 MCPAdapter.call_tool）；权限确认由
RealtimeAgent 内建 PermissionEngine + RequireUserConfirmEvent 完成。
"""
import json
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


def _dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(obj)


class McpToolWrapper:
    """MCP 工具的 AgentScope ToolBase 包装。"""

    name: str
    description: str
    input_schema: dict
    is_concurrency_safe: bool = False
    is_read_only: bool = False
    is_mcp: bool = True
    mcp_name: str = "mwb-voice-mcp"

    def __init__(self, schema: Dict[str, Any],
                 call_fn: Optional[Callable] = None) -> None:
        self.name = schema["name"]
        self.description = schema.get("description", "")
        self.input_schema = schema.get("inputSchema") or {"type": "object"}
        self._call_fn = call_fn

    def _resolve_call_fn(self) -> Callable:
        if self._call_fn is not None:
            return self._call_fn
        from app.ai.mcp.tool_adapter import get_mcp_adapter
        adapter = get_mcp_adapter()

        async def call(name: str, args: dict):
            return await adapter.call_tool(name, args)
        return call

    async def call(self, **kwargs):
        from agentscope.message import TextBlock, ToolResultState
        from agentscope.tool import ToolChunk
        try:
            result = await self._resolve_call_fn()(self.name, kwargs)
            text = result if isinstance(result, str) else _dumps(result)
            return ToolChunk(content=[TextBlock(type="text", text=text)],
                             state=ToolResultState.SUCCESS)
        except Exception as e:  # noqa: BLE001 - 工具失败不中断语音流
            logger.warning(f"语音工具 {self.name} 执行失败: {e}")
            return ToolChunk(
                content=[TextBlock(type="text", text=f"工具执行失败: {e}")],
                state=ToolResultState.ERROR)


def build_toolkit(tool_schemas: List[Dict[str, Any]],
                  call_fn: Optional[Callable] = None):
    """构建 RealtimeAgent 所需 Toolkit；空 schema 返回空 Toolkit。"""
    from agentscope.tool import Toolkit
    return Toolkit(tools=[McpToolWrapper(s, call_fn) for s in tool_schemas])
```

- [ ] **Step 4: 运行确认通过 + Commit**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/duplex/voice/test_toolkit_builder.py -v`
Expected: 3 passed

```bash
git add backend/app/duplex/voice/toolkit_builder.py backend/tests/duplex/voice/test_toolkit_builder.py
git commit -m "feat(voice): RealtimeAgent Toolkit 构建（MCP 工具注入）"
```

---

## Task 6: 后端清理（local/s2s/agent_adapter/config/requirements）

**Files:**
- Delete: `backend/app/duplex/voice/providers/dashscope.py`、`providers/s2s.py`、`providers/local.py`、`providers/pipeline/`（整目录）、`audio_codec.py`、`agent_adapter.py`、`tool_call_handler.py`
- Modify: `backend/app/config/_voice.py`、`backend/requirements.txt`、`backend/app/schemas/duplex/voice.py`（AiAgentConfig type 枚举）
- Test: 全量回归

- [ ] **Step 1: 全仓引用扫描**

Run: `cd d:\projects\MinWorkBuddy\backend; Get-ChildItem app tests -Recurse -Include *.py | Select-String -Pattern "agent_adapter|tool_call_handler|audio_codec|providers\.local|providers\.s2s|providers\.dashscope|LocalProvider|S2SProvider|DashScopeProvider" -List | Select-Object Path`
Expected: 列出全部引用点；逐个处理（本任务内删除或改引）

- [ ] **Step 2: 删除文件**

```bash
cd d:\projects\MinWorkBuddy\backend
git rm app/duplex/voice/providers/dashscope.py app/duplex/voice/providers/s2s.py app/duplex/voice/providers/local.py app/duplex/voice/audio_codec.py app/duplex/voice/agent_adapter.py app/duplex/voice/tool_call_handler.py
git rm -r app/duplex/voice/providers/pipeline/
```

- [ ] **Step 3: 修复残余引用**

- `app/schemas/duplex/voice.py`：`AiAgentConfig.type` 枚举 `agentscope|dify|direct` 收敛为 `agentscope`（Literal["agentscope"]），并同步 `app/routers/admin_voice_config.py` 的校验
- 存量 local/s2s 测试：纯 local/s2s 用例文件删除；混合文件删除相关用例函数
- `websockets` 依赖保留（agentscope 上游 WS 仍需要）

- [ ] **Step 4: config/_voice.py 更新**

删除六项 `VOICE_LOCAL_*`（`VOICE_LOCAL_PIPELINE_URL/VOICE_LOCAL_ENABLED/VOICE_LOCAL_VAD_MODEL/VOICE_LOCAL_STT_MODEL/VOICE_LOCAL_TTS_MODEL/VOICE_LOCAL_TTS_SPEED`）。`VOICE_DEFAULT_PROVIDER = "dashscope"` 保持，注释改为「值域：dashscope | openai」。

- [ ] **Step 5: requirements.txt 更新**

- **收编既有未提交改动**（2026-09-21 复核确认已在工作区）：`agentscope==2.0.8` 固定 + `mcp>=1.15.0,<2.0.0`（requirements.txt）与 `agentscope>=2.0.8,<3.0`（requirements-dev.txt）——这些本就是语音迁移的配套改动，随本任务一并提交；提交前 `git diff backend/requirements*.txt` 确认无其它无关混入
- 删除 `onnxruntime>=1.17.0`
- `torch`/`torchaudio`：先 `Get-ChildItem backend/app -Recurse -Include *.py | Select-String -Pattern "import torch|from torch|torchaudio"`——仅 funasr/cosyvoice 使用则删，否则保留
- `agentscope==2.0.8` 行验证 realtime 导入：`.venv\Scripts\python.exe -c "from agentscope.realtime import DashScopeRealtimeModel, DashScopeAudioRealtimeModel"`——成功则不改行，仅补注释「realtime 内核（2.0.8 暂不含 OpenAIRealtimeModel，见 spec §8）」

- [ ] **Step 6: 全量回归**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/ -q`
Expected: 语音相关全 PASS；非语音存量失败（历史 DB drift 等）记录不在本任务范围

- [ ] **Step 7: Commit**

```bash
git add -A backend/
git commit -m "refactor(voice): 清理手写 dashscope/s2s/local Provider 与 agent_adapter，收敛配置"
```

---

## Task 7: 协议文档

**Files:**
- Create: `docs/api/voice-ws-protocol.md`

- [ ] **Step 1: 撰写文档**，章节结构：
  1. 端点与握手：`ws(s)://<host>/api/v1/duplex/voice/ws?case_number=&session_id=&participant_id=&provider=dashscope|openai&model_id=&client_caps={json}`（`client_caps` 示例）
  2. 上行：二进制裸 PCM16（16kHz 单声道小端，无封装）；JSON 控制帧 `input.message` / `interrupt` / `ping` / `tool.confirm`（各含完整 JSON 示例，取自 Task 4 实现）
  3. 下行：`voice.ready` 全字段（取自 `ProtocolAdapter.build_ready_payload`）、二进制 PCM16（24kHz）、`transcript.delta|final`、`audio.delta`、`turn.started`、`response_started`、`playback_cancelled`、`voice.state`、`tool_call`、`tool_result`、`tool.confirm_required`、`error`（generation 语义与客户端丢弃规则：`generation < 当前值` 的帧丢弃）
  4. Provider 差异：dashscope（Qwen-Omni `supports_text_input=False`，文字输入返回 error 帧 `text_unsupported`）；openai（服务端 16k→24k 重采样）
  5. 错误码（`inactivity/provider_unavailable/fatal/text_unsupported`）与 WS 关闭码（4503）

- [ ] **Step 2: Commit**

```bash
git add docs/api/voice-ws-protocol.md
git commit -m "docs(voice): 协议 v2 全量文档（含 tool.confirm 增量帧）"
```

---

## Task 8: 前端类型与 useToolCalls confirm 流

**Files:**
- Modify: `frontend/src/types/voice.ts:12-27,58-65`
- Modify: `frontend/src/composables/useToolCalls.ts`
- Test: `frontend/src/composables/__tests__/useToolCalls.spec.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect } from 'vitest'
import { useToolCalls } from '../useToolCalls'

describe('useToolCalls confirm flow', () => {
  it('addConfirm 入 pending，update 补全结果', () => {
    const tc = useToolCalls()
    tc.addConfirm({ confirmId: 'c1', name: 'db_query', arguments: { q: 'x' }, timeoutMs: 300000 })
    expect(tc.pending.value).toHaveLength(1)
    tc.update('c1', { ok: true, result: 'done' })
    expect(tc.pending.value).toHaveLength(0)
    expect(tc.calls.value.find((c: any) => c.id === 'c1')?.status).toBe('executed')
  })

  it('clearPending 打断时清空待确认', () => {
    const tc = useToolCalls()
    tc.addConfirm({ confirmId: 'c2', name: 't', arguments: {}, timeoutMs: 1000 })
    tc.clearPending()
    expect(tc.pending.value).toHaveLength(0)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\frontend; npx vitest run src/composables/__tests__/useToolCalls.spec.ts`
Expected: FAIL（`addConfirm` 不存在）

- [ ] **Step 3: types/voice.ts 修改**

```typescript
// L27 VoiceProvider 收敛（删 's2s' | 'local' | 'loopback'；'openai' 转真实）：
export type VoiceProvider = 'dashscope' | 'openai'

// L12-24 VoiceEventType 联合类型追加：
  | 'tool_call'
  | 'tool_result'
  | 'tool.confirm_required'

// 新增载荷与状态：
export interface ToolConfirmPayload {
  confirm_id: string
  tool_name: string
  arguments: Record<string, unknown>
  timeout_ms: number
}

// ToolCall（L58-65）追加：
  status?: 'pending' | 'executed' | 'rejected'
```

- [ ] **Step 4: useToolCalls.ts 修改**（保留现有 `calls/add/update/clear` 结构与 `pending` computed）

```typescript
function addConfirm(p: { confirmId: string; name: string;
                         arguments: Record<string, unknown>; timeoutMs: number }) {
  calls.value.push({ id: p.confirmId, name: p.name, arguments: p.arguments,
                     status: 'pending' } as ToolCall)
}

function clearPending() {
  calls.value = calls.value.filter(c => c.status !== 'pending')
}

// update() 修改为落位状态：
function update(id: string, patch: Partial<ToolCall>) {
  const c = calls.value.find(x => x.id === id)
  if (c) {
    Object.assign(c, patch)
    if (patch.ok !== undefined) c.status = patch.ok ? 'executed' : c.status
  }
}
```

导出对象追加 `addConfirm, clearPending`。

- [ ] **Step 5: 运行确认通过 + Commit**

Run: `cd d:\projects\MinWorkBuddy\frontend; npx vitest run src/composables/__tests__/useToolCalls.spec.ts`
Expected: 2 passed

```bash
git add frontend/src/types/voice.ts frontend/src/composables/useToolCalls.ts frontend/src/composables/__tests__/useToolCalls.spec.ts
git commit -m "feat(voice-ui): 工具确认状态流与协议类型增量"
```

---

## Task 9: useVoiceChannel confirm 接入

**Files:**
- Modify: `frontend/src/composables/useVoiceChannel.ts`（handleFrame switch L138-178；动作导出区）

- [ ] **Step 1: handleFrame 新增 case（现有 `tool_call` case 之后）**

```typescript
case 'tool.confirm_required': {
  const p = msg.data as ToolConfirmPayload
  toolCalls.addConfirm({
    confirmId: p.confirm_id,
    name: p.tool_name,
    arguments: p.arguments ?? {},
    timeoutMs: p.timeout_ms ?? 300000,
  })
  break
}
case 'tool_result': {
  toolCalls.update(msg.data?.call_id, {
    ok: msg.data?.state === 'COMPLETED' || msg.data?.state === 'finished',
    result: String(msg.data?.state ?? ''),
  })
  break
}
```

（`msg` 为现有 handleFrame 解析出的 JSON 帧变量名；实施时对照文件实际命名。）

- [ ] **Step 2: 打断/取消联动清理**

在现有 `interrupt()` 发送函数内与 handleFrame 的 `playback_cancelled` case 中各追加：

```typescript
toolCalls.clearPending()
```

- [ ] **Step 3: 新增动作（return 导出对象）**

```typescript
function respondToolConfirm(confirmId: string, approved: boolean) {
  toolCalls.clearPending() // UI 侧先撤卡；结果由 tool_result 帧补全
  sendJson({ type: 'tool.confirm', data: { confirm_id: confirmId, approved } })
}
```

（`sendJson` 对照文件内现有 JSON 帧发送函数命名。）

- [ ] **Step 4: lint + 回归**

Run: `cd d:\projects\MinWorkBuddy\frontend; npm run lint`
Expected: 无新增错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useVoiceChannel.ts
git commit -m "feat(voice-ui): WS 通道接入 tool.confirm_required 下行与确认上行"
```

---

## Task 10: TurnTimeline 待确认卡片

**Files:**
- Modify: `frontend/src/components/voice/TurnTimeline.vue`
- Modify: `frontend/src/components/voice/VoiceChannel.vue`（桥接）

- [ ] **Step 1: TurnTimeline.vue 模板追加（工具标签区之后）**

```vue
<div v-for="c in pendingConfirms" :key="c.id" class="voice-confirm-card">
  <div class="voice-confirm-title">工具请求确认：{{ c.name }}</div>
  <pre class="voice-confirm-args">{{ JSON.stringify(c.arguments, null, 2) }}</pre>
  <div class="voice-confirm-actions">
    <a-button size="small" type="primary" @click="$emit('confirm', c.id, true)">同意</a-button>
    <a-button size="small" danger @click="$emit('confirm', c.id, false)">拒绝</a-button>
  </div>
</div>
```

脚本追加：

```typescript
props: { /* 现有 turns/toolCalls 之外增加 */ pendingConfirms: { type: Array as PropType<ToolCall[]>, default: () => [] } }
defineEmits<{ (e: 'confirm', id: string, approved: boolean): void }>()
```

- [ ] **Step 2: VoiceChannel.vue 桥接**

```vue
<TurnTimeline
  :turns="turns"
  :tool-calls="toolCalls"
  :pending-confirms="toolCallsCtl.pending.value"
  @confirm="(id, ok) => respondToolConfirm(id, ok)"
/>
```

（`toolCallsCtl` / `respondToolConfirm` 对照 useVoiceChannel 返回值解构命名。）

- [ ] **Step 3: lint + Commit**

Run: `cd d:\projects\MinWorkBuddy\frontend; npm run lint`

```bash
git add frontend/src/components/voice/TurnTimeline.vue frontend/src/components/voice/VoiceChannel.vue
git commit -m "feat(voice-ui): 工具确认卡片（同意/拒绝 → tool.confirm 上行）"
```

---

## Task 11: useMicLifecycle 麦克风韧性

**Files:**
- Create: `frontend/src/composables/useMicLifecycle.ts`
- Modify: `frontend/src/composables/useVoiceChannel.ts`（采集链拆分集成）
- Modify: `frontend/src/components/voice/VoiceToolbar.vue`（recovering/unavailable 展示）
- Test: `frontend/src/composables/__tests__/useMicLifecycle.spec.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createMicLifecycle } from '../useMicLifecycle'

describe('useMicLifecycle', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  function makeEnv() {
    const states: any[] = []
    const track = makeTrack()
    let stream: any = { track }
    const acquire = vi.fn(async () => stream)
    const release = vi.fn()
    function makeTrack() {
      const listeners: Record<string, Function[]> = {}
      return {
        muted: false,
        addEventListener: (n: string, f: Function) => { (listeners[n] ??= []).push(f) },
        removeEventListener: () => {},
        __emit: (n: string) => (listeners[n] || []).forEach(f => f()),
      }
    }
    const lc = createMicLifecycle({
      acquire, release,
      onState: (s: any) => states.push(s),
      schedule: (cb: () => void, ms: number) => setTimeout(cb, ms),
      cancel: (t: any) => clearTimeout(t),
      mediaDevices: { addEventListener: () => {}, removeEventListener: () => {} },
    })
    return { lc, states, acquire, release, track }
  }

  it('track ended 立即重启', async () => {
    const { lc, acquire, track } = makeEnv()
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(acquire).toHaveBeenCalledTimes(1)
    track.__emit('ended')
    await vi.advanceTimersByTimeAsync(0)
    expect(acquire).toHaveBeenCalledTimes(2)
    lc.stop()
  })

  it('mute 宽限内 unmute 不重启', async () => {
    const { lc, acquire, track } = makeEnv()
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    track.__emit('mute')
    await vi.advanceTimersByTimeAsync(1000)
    track.muted = false
    track.__emit('unmute')
    await vi.advanceTimersByTimeAsync(1000)
    expect(acquire).toHaveBeenCalledTimes(1)
    lc.stop()
  })

  it('mute 超宽限触发重启', async () => {
    const { lc, acquire, track } = makeEnv()
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    track.muted = true
    track.__emit('mute')
    await vi.advanceTimersByTimeAsync(1600)
    expect(acquire).toHaveBeenCalledTimes(2)
    lc.stop()
  })

  it('不可恢复错误直接 unavailable', async () => {
    const { lc, states, acquire } = makeEnv()
    acquire.mockRejectedValueOnce(Object.assign(new Error('denied'), { name: 'NotAllowedError' }))
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(states.at(-1).state).toBe('unavailable')
    expect(states.at(-1).recoverable).toBe(false)
    lc.stop()
  })

  it('可恢复错误按 500ms 退避重试', async () => {
    const { lc, acquire } = makeEnv()
    acquire.mockRejectedValueOnce(Object.assign(new Error('busy'), { name: 'NotReadableError' }))
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(500)
    expect(acquire).toHaveBeenCalledTimes(2)
    lc.stop()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\frontend; npx vitest run src/composables/__tests__/useMicLifecycle.spec.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 useMicLifecycle.ts**（qwen-audio-agent `createMicrophoneCaptureLifecycle` 模式移植，spec §9.7）

```typescript
/**
 * 麦克风捕获生命周期：只负责媒体流获取与 track 监听，独立于 WS 通道与
 * 播放链——设备切换只重建流，不重连、不打断播放（spec §9.7）。
 */
export interface MicState {
  state: 'starting' | 'ready' | 'recovering' | 'unavailable'
  reason: string
  error?: unknown
  recoverable?: boolean
}

const FATAL_ERRORS = ['NotAllowedError', 'NotSupportedError', 'SecurityError', 'TypeError']

export function classifyMicError(error: unknown): string {
  const name = String((error as any)?.name || '')
  const message = String((error as any)?.message || '')
  if (['NotAllowedError', 'SecurityError'].includes(name)
    || /permission\s+denied|not\s+allowed/i.test(message)) return 'permission_denied'
  if (name === 'NotFoundError') return 'device_missing'
  if (name === 'NotReadableError') return 'device_unavailable'
  if (name === 'NotSupportedError') return 'unsupported'
  return 'unknown'
}

interface MicLifecycleOpts {
  acquire: (ctx: { reason: string; generation: number }) => Promise<any>
  release: (capture: any) => void
  onState: (s: MicState) => void
  retryDelays?: number[]
  debounceMs?: number
  muteGraceMs?: number
  schedule?: (cb: () => void, ms: number) => any
  cancel?: (timer: any) => void
  mediaDevices?: { addEventListener?: Function; removeEventListener?: Function }
}

export function createMicLifecycle(opts: MicLifecycleOpts) {
  const retryDelays = opts.retryDelays ?? [500, 1000, 2000, 4000]
  const debounceMs = opts.debounceMs ?? 300
  const muteGraceMs = opts.muteGraceMs ?? 1500
  const schedule = opts.schedule ?? ((cb: () => void, ms: number) => setTimeout(cb, ms))
  const cancel = opts.cancel ?? ((t: any) => clearTimeout(t))

  let running = false
  let generation = 0
  let current: any = null
  let restartTimer: any = null
  let retryTimer: any = null
  let muteTimer: any = null
  let retryAttempt = 0

  const trackOf = (c: any) => c?.track || c?.media?.getAudioTracks?.()[0] || null

  const clearTimer = (kind: 'restart' | 'retry' | 'mute') => {
    const t = kind === 'restart' ? restartTimer : kind === 'retry' ? retryTimer : muteTimer
    if (t !== null) cancel(t)
    if (kind === 'restart') restartTimer = null
    else if (kind === 'retry') retryTimer = null
    else muteTimer = null
  }

  const detach = () => {
    const c = current
    if (!c) return
    current = null
    clearTimer('mute')
    const track = trackOf(c)
    track?.removeEventListener?.('ended', c.handleEnded)
    track?.removeEventListener?.('mute', c.handleMute)
    track?.removeEventListener?.('unmute', c.handleUnmute)
    opts.release(c)
  }

  const installListeners = (c: any) => {
    const track = trackOf(c)
    if (!track?.addEventListener) return
    c.handleEnded = () => requestRestart('track-ended', 0)
    c.handleMute = () => {
      clearTimer('mute')
      muteTimer = schedule(() => {
        muteTimer = null
        if (track.muted !== false) requestRestart('track-muted', 0)
      }, muteGraceMs)
    }
    c.handleUnmute = () => clearTimer('mute')
    track.addEventListener('ended', c.handleEnded)
    track.addEventListener('mute', c.handleMute)
    track.addEventListener('unmute', c.handleUnmute)
  }

  const replaceCapture = async (reason: string) => {
    if (!running) return
    clearTimer('restart')
    clearTimer('retry')
    const gen = ++generation
    detach()
    opts.onState({ state: reason === 'initial' ? 'starting' : 'recovering', reason })
    try {
      const capture = await opts.acquire({ reason, generation: gen })
      if (!running || gen !== generation) { opts.release(capture); return }
      current = capture
      retryAttempt = 0
      installListeners(capture)
      opts.onState({ state: 'ready', reason })
    } catch (error) {
      if (!running || gen !== generation) return
      if (FATAL_ERRORS.includes(String((error as any)?.name || ''))) {
        opts.onState({ state: 'unavailable', reason, error, recoverable: false })
        return
      }
      const delay = retryDelays[retryAttempt]
      retryAttempt += 1
      const retrying = Number.isFinite(delay)
      opts.onState({ state: retrying ? 'recovering' : 'unavailable', reason,
                     error, recoverable: true,
                     ...(retrying ? {} : {}) })
      if (retrying) {
        retryTimer = schedule(() => { retryTimer = null; void replaceCapture('retry') }, delay)
      }
    }
  }

  function requestRestart(reason = 'devicechange', delay = debounceMs) {
    if (!running) return
    if (reason === 'devicechange') retryAttempt = 0
    clearTimer('restart')
    clearTimer('retry')
    restartTimer = schedule(() => { restartTimer = null; void replaceCapture(reason) }, delay)
  }

  const handleDeviceChange = () => requestRestart('devicechange')

  return {
    start() {
      if (running) return
      running = true
      opts.mediaDevices?.addEventListener?.('devicechange', handleDeviceChange)
      void replaceCapture('initial')
    },
    stop() {
      if (!running) return
      running = false
      generation += 1
      opts.mediaDevices?.removeEventListener?.('devicechange', handleDeviceChange)
      clearTimer('restart'); clearTimer('retry'); clearTimer('mute')
      detach()
    },
    restart(reason = 'manual') {
      retryAttempt = 0
      requestRestart(reason, 0)
    },
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd d:\projects\MinWorkBuddy\frontend; npx vitest run src/composables/__tests__/useMicLifecycle.spec.ts`
Expected: 5 passed

- [ ] **Step 5: 集成 useVoiceChannel**

把现有内联 `getUserMedia` 调用（采集启动处）替换为 lifecycle 集成：

```typescript
import { createMicLifecycle } from './useMicLifecycle'

// 组件内：
const mic = createMicLifecycle({
  acquire: async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    return { media: stream, track: stream.getAudioTracks()[0] }
  },
  release: (c) => c?.media?.getTracks?.().forEach((t: MediaStreamTrack) => t.stop()),
  onState: (s) => { micState.value = s },   // 新增 ref<MicState | null>
})
```

关键约束：**AudioContext（48kHz）不随设备重建**——`acquire` 成功回调后仅重连 `ctx.createMediaStreamSource(newStream)` 到既有 DSP 上行链（DcBlocker → NoiseGate → Resampler → PCM16 编码）；WS 连接生命周期与 mic lifecycle 完全解耦。`disconnect()` 清理路径中调用 `mic.stop()`。`micOn`（toggleMic）语义不变：仍门控上行发送。

- [ ] **Step 6: VoiceToolbar.vue 状态展示**

`ChannelStatus` 类型扩展（`useVoiceChannel.ts` 导出处）：

```typescript
export type ChannelStatus = 'idle' | 'connecting' | 'connected' | 'recovering' | 'unavailable' | 'error'
```

模板中状态徽标：`recovering` 显示「麦克风恢复中…」，`unavailable` 显示 `classifyMicError(error)` 对应文案（权限被拒/设备缺失/设备占用/不支持）。

- [ ] **Step 7: lint + 全部前端测试 + Commit**

Run: `cd d:\projects\MinWorkBuddy\frontend; npm run lint; npx vitest run src/composables/__tests__/`
Expected: 全 PASS

```bash
git add frontend/src/composables/ frontend/src/components/voice/
git commit -m "feat(voice-ui): 麦克风韧性生命周期（设备切换/track 宽限/退避重试）"
```

---

## Task 12: VoiceDemo 与管理页清理

**Files:**
- Modify: `frontend/src/views/duplex/VoiceDemo.vue:4-5,46-88`
- Modify: `frontend/src/views/admin/ai-config/agents/AgentConfigPanel.vue:86-90`

- [ ] **Step 1: VoiceDemo.vue**

- L4-5 过时里程碑文案（"M2 · 能力协商…/本地管线"）更新为当前说明
- L49-53 `providerOptions` 替换：

```typescript
const providerOptions = [
  { label: 'DashScope 实时（Qwen-Omni / Qwen-Audio）', value: 'dashscope' },
  { label: 'OpenAI Realtime（备选）', value: 'openai' },
]
```

- 删除 L62-64 `modelsFor` 的 `m.platform === 's2s'` 过滤分支与 L86-88 s2s→provider 自适应逻辑（改为：`applyDefault` 时按 `model.platform` 匹配 `providerOptions` 中的 value，无匹配保留当前选择）

- [ ] **Step 2: AgentConfigPanel.vue**

L86-90 `typeOptions` 硬编码替换为：

```typescript
const typeOptions = [{ label: 'AgentScope', value: 'agentscope' }]
```

存量行 `type` 为 `dify`/`direct` 时表格行内显示警告 tag「已废弃，请迁移为 agentscope」（只读提示，不阻塞列表渲染）。

- [ ] **Step 3: 清理验证**

Run: `cd d:\projects\MinWorkBuddy\frontend; Get-ChildItem src -Recurse -Include *.ts,*.vue | Select-String -Pattern "'s2s'|'loopback'|\"s2s\"|\"loopback\"|本地管线|本地回退" -List`
Expected: 语音目录（views/duplex、components/voice、composables、api/voice.ts、types/voice.ts）无命中；`workspace.ts` 的 `'local'`（沙箱模式）与 `views/assistant` 不属清理范围

- [ ] **Step 4: lint + Commit**

Run: `cd d:\projects\MinWorkBuddy\frontend; npm run lint`

```bash
git add frontend/src/views/duplex/VoiceDemo.vue frontend/src/views/admin/ai-config/agents/AgentConfigPanel.vue
git commit -m "refactor(voice-ui): 清理 s2s/local/loopback 死选项，收敛 provider 与 agent type"
```

---

## Task 13: 部署与联调文档

**Files:**
- Create: `docs/deploy/voice-agentscope-deploy.md`
- Create: `docs/guides/voice-frontend-integration-test.md`

- [ ] **Step 1: 部署文档** `docs/deploy/voice-agentscope-deploy.md`，内容：
  1. 依赖：`agentscope==2.0.8`（realtime 内核）；无新增外部服务（s2s Docker 已废除）
  2. 环境变量：`VOICE_DEFAULT_PROVIDER`（dashscope|openai）；`VOICE_OPENAI_*`（可选）
  3. 数据库配置：`ai_api_key`（platform=DashScope/openai + api_key）+ `ai_chat_model`（type=7 语音模型，model 名在 AgentScope 模型卡片内）；管理页入口「语音模型配置」
  4. 启动验证：`/api/v1/duplex/voice/metrics` 可访问；VoiceDemo 页连接返回 `voice.ready`

- [ ] **Step 2: 联调指南** `docs/guides/voice-frontend-integration-test.md`，冒烟步骤：
  1. 连接：VoiceDemo 选 dashscope + 模型 → 点连接 → 收到 `voice.ready`（核对 input/output_sample_rate）
  2. 对话：说一句话 → `transcript.delta`(user) → `audio.delta` 播放 + `transcript.delta`(assistant)
  3. 打断：回复中开口插话 → `playback_cancelled` + 播放立即停止；点停止按钮 → `interrupt`
  4. 工具确认：配置带 MCP 工具的 agent → 触发工具调用 → 确认卡片出现 → 同意 → `tool_result`；拒绝路径同理；5 分钟超时自动拒绝
  5. 文字输入：Omni 模型下输入文字 → 收到 `text_unsupported` error 帧且 UI 提示
  6. 麦克风韧性：通话中拔出 USB 麦克风 → 2s 内自动恢复（recovering 状态提示）；静音轨道 1.5s 宽限后恢复
  7. 重连：断网 10s → 前端退避重连 → 收到回放状态帧
  8. 降级：openai 未配置 Key 时 `provider=openai` 连接 → `provider_unavailable` error + 4503

- [ ] **Step 3: Commit**

```bash
git add docs/deploy/voice-agentscope-deploy.md docs/guides/voice-frontend-integration-test.md
git commit -m "docs(voice): 部署配置与前端联调测试指南"
```

---

## 依赖与顺序

- Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7（后端串行）
- Task 8 → Task 9 → Task 10（confirm 前端链）；Task 11、Task 12 可与 Task 9/10 并行
- Task 13 最后（依赖 Task 7/12 定稿的协议与 UI）

## 验收清单（对照 spec）

- [ ] 协议 v2 帧格式不变，`voice.ready` 字段语义不变（前端主链路无需迁移）
- [ ] dashscope/openai 均经 AgentScope RealtimeAgent 内核；s2s/local 手写实现删除
- [ ] `tool.confirm_required` 下行 + `tool.confirm` 上行闭环；打断清 pending；5min 超时拒绝
- [ ] ping→pong 回客户端；VAD barge-in 触发代际 bump
- [ ] `useMicLifecycle`：设备切换去抖 300ms 重置重试、track ended 立即重启、mute 1.5s 宽限、500/1000/2000/4000 退避、fatal 不重试
- [ ] 前端死代码清理：`'s2s'|'local'|'loopback'` 枚举、VoiceDemo 过滤逻辑、AgentConfigPanel dify/direct 选项
- [ ] `docs/api/voice-ws-protocol.md`、部署文档、联调指南交付

