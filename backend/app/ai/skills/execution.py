"""SkillExecutionService - 基于 AgentScope 2.0 的技能执行服务。

🎯 **原生化改造 Phase 2**:
- ✅ 删除 `_estimate_tokens()`, `_truncate_message()` (38 行)  
- ✅ 删除 `_is_context_length_error()` (22 行)
- ✅ 删除上下文长度降级重试逻辑 (108 行)
- ✅ 删除 `_get_model_max_input_tokens()` (49 行)  
- ✅ 统一 `handle()` 事件分发（安装版 agentscope 无 EventStreamHandler 基类）
- ✅ 依赖 AgentScope 原生上下文窗口管理
- 代码缩减：1076 行 → ~650 行 (-40%)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from agentscope.tool import ToolBase
from agentscope.message import UserMsg

from app.ai.events.bus import EventBus
from app.ai.events.registry import get_run_registry
from app.ai.services.execution_event_service import ExecutionEventService
from app.db.database import SessionLocal  # noqa: E402 —— 顶部导入便于测试 monkeypatch
from app.ai.skills.execution_records import (
    record_execution_done,
    record_execution_failed,
    record_execution_start,
)
from app.schemas.agent.event_types import (
    EventCategory,
    EventEnvelope,
    EventLevel,
)

logger = logging.getLogger(__name__)

# 技能包根目录
_SKILLS_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "skills"


@dataclass
class SkillEvent:
    """技能执行事件。"""
    type: str
    data: dict = field(default_factory=dict)


def parse_allowed_tools(markdown: str) -> list[str] | None:
    """从 SKILL.md frontmatter 解析 allowed-tools 字段。"""
    import re
    fm_match = re.match(r'^---\n(.*?)\n---', markdown, re.DOTALL)
    if not fm_match:
        return None
    fm = fm_match.group(1)
    m = re.search(r'^allowed-tools:\s*\[([^\]]*)\]', fm, re.MULTILINE)
    if not m:
        return None
    raw = m.group(1)
    tools = [t.strip().strip('"\'') for t in raw.split(',') if t.strip()]
    return tools if tools else None


class SkillEventHandler:
    """AgentScope 事件流处理器（spec §4.2 分级 + §5.2 运行模式增强）。

    - SSE 输出：SkillEvent 入 out_q，类型保持旧值（text/thinking/tool_call/
      tool_result/done/error），前端零改动。
    - DB 输出：经 bus 发布信封 —— delta 不落库，块级/调用级汇总落库。
    - 关联：透传 reply_id / block_id / tool_call_id。
    - 计量：累计 ModelCallEnd 的 input/output tokens 与迭代轮数。
    - 错误：安装版 agentscope 无 ErrorEvent，错误经 ReplyEndEvent.error 传递。

    注：安装版 agentscope.event 无 ``EventStreamHandler`` 基类，故为普通类。
    """

    def __init__(
        self,
        skill_name: str,
        bus: EventBus,
        out_q: asyncio.Queue,
        execution_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.skill_name = skill_name
        self.bus = bus
        self.out_q = out_q
        # EventBus 本身不携带执行标识；优先显式传入，其次从 bus 读取，兜底生成
        self.execution_id = (
            execution_id
            or getattr(bus, "execution_id", None)
            or str(uuid.uuid4())
        )
        self.trace_id = trace_id if trace_id is not None else getattr(bus, "trace_id", None)
        self.text_parts: list[str] = []
        self._final_text_parts: list[str] = []  # 跨块累积全文，供 done SSE 使用
        self.thinking_parts: list[str] = []
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
            execution_id=self.execution_id,
            trace_id=self.trace_id,
            event_type=event_type, category=category, levels=list(levels),
            content=content, source="agent", source_id=self.skill_name,
            reply_id=self.reply_id, metadata=metadata or {}, **kw,
        ))

    # ── 统一分发 ─────────────────────────────────────────────────────

    async def handle(self, event) -> None:
        """统一事件分发器。"""
        from agentscope.event import (
            ReplyStartEvent, ReplyEndEvent, ExceedMaxItersEvent,
            TextBlockDeltaEvent, TextBlockEndEvent,
            ThinkingBlockDeltaEvent, ThinkingBlockEndEvent,
            ToolCallStartEvent, ToolCallEndEvent,
            ToolResultTextDeltaEvent, ToolResultDataDeltaEvent, ToolResultEndEvent,
            ModelCallEndEvent,
        )

        if isinstance(event, ReplyStartEvent):
            self.reply_id = getattr(event, "reply_id", None)
            self._publish_db("reply_start", EventCategory.LIFECYCLE, [EventLevel.DB],
                             {"name": getattr(event, "name", "")})

        elif isinstance(event, TextBlockDeltaEvent):
            delta = event.delta or ""
            if delta.strip():
                self.text_parts.append(delta)
                self._final_text_parts.append(delta)
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
                self.thinking_parts.append(delta)
                self._emit_sse("thinking", {"content": delta})  # 仅 SSE

        elif isinstance(event, ThinkingBlockEndEvent):
            # 思考块仅记块边界 + 全文汇总（体积大、审计价值低，不入 SSE）
            self._publish_db(
                "thinking_done", EventCategory.THINKING, [EventLevel.DB],
                {"thinking": "".join(self.thinking_parts)},
                block_id=getattr(event, "block_id", None),
            )
            self.thinking_parts = []

        elif isinstance(event, ToolCallStartEvent):
            self.current_tool_name = getattr(event, "tool_call_name", "") or ""
            self._tool_call_id = getattr(event, "tool_call_id", None)

        elif isinstance(event, ToolCallEndEvent):
            # 安装版 ToolCallEndEvent 无 tool_args（参数经 ToolCallDeltaEvent 流式）
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
            input_tokens = int(getattr(event, "input_tokens", 0) or 0)
            output_tokens = int(getattr(event, "output_tokens", 0) or 0)
            self.usage["input_tokens"] += input_tokens
            self.usage["output_tokens"] += output_tokens
            self._publish_db(
                "model_call", EventCategory.MODEL, [EventLevel.LOG],
                {"model_name": getattr(event, "model_name", "")},
                metadata={"input_tokens": input_tokens,
                          "output_tokens": output_tokens,
                          "iteration": self.iterations},
            )

        elif isinstance(event, ExceedMaxItersEvent):
            self._publish_db(
                "iteration_limit", EventCategory.RUNTIME,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"iterations": self.iterations}, ui_hint="timeline",
            )

        elif isinstance(event, ReplyEndEvent):
            final_text = "".join(self._final_text_parts or self.text_parts)
            error = getattr(event, "error", None)
            finished = str(getattr(event, "finished_reason", None) or "completed")
            if error is not None:
                message = str(getattr(error, "message", "") or error)
                self._publish_db(
                    "error", EventCategory.ERROR,
                    [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                    {"message": message}, ui_hint="timeline",
                )
                self._emit_sse("error", {
                    "message": message,
                    "type": str(getattr(error, "type", "error")),
                })
            self._publish_db(
                "reply_end", EventCategory.LIFECYCLE, [EventLevel.DB],
                {"finished_reason": finished},
                metadata={**self.usage, "iterations": self.iterations},
            )
            self._emit_sse("done", {"result": final_text})

        else:
            # 未知事件（含各类 Start/无关事件）：仅 debug 日志，不打扰 SSE/DB
            logger.debug("[SkillExecution] unhandled event: %s", event.__class__.__name__)


class SkillExecutionService:
    """基于 AgentScope 2.0 的技能执行服务（精简版）。"""

    DEFAULT_TIMEOUT = 300
    SKILL_AGENT_CONFIG_ID = 0
    _cached_skill_loader: Any = None
    _cached_toolkits: dict[str, Any] = {}

    def __init__(
        self,
        workspace: Any | None = None,
        tool_manager: Any | None = None,
        model_config: dict | None = None,
        timeout: int | None = None,
        event_service: Optional[ExecutionEventService] = None,
    ) -> None:
        from app.ai.workspace.manager import get_workspace_adapter
        from app.ai.tool_manager.manager import get_tool_manager

        self.workspace = workspace or get_workspace_adapter(auto_discover=True)
        self.tool_manager = tool_manager or get_tool_manager()
        self.model_config = model_config
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.event_service = event_service
        self.bus: EventBus | None = None

    async def execute(
        self,
        skill_name: str,
        user_message: str,
        session_id: int | None = None,
        user_id: int | None = None,
        extra_tools: list[ToolBase] | None = None,
        model_id: int | None = None,
        execution_id: str | None = None,
        trace_id: str | None = None,
    ) -> AsyncGenerator[SkillEvent, None]:
        """流式执行技能（分级事件 + 主记录 + 超时熔断）。"""
        _exec_start = time.perf_counter()
        _exec_success = False
        _error_text: str | None = None
        timed_out = False
        _finalized = False
        consumer: asyncio.Task | None = None
        handler: SkillEventHandler | None = None
        handle = None  # RunHandle（注册进 AgentRunRegistry 后非空）

        if execution_id is None:
            execution_id = str(uuid.uuid4())

        if self.event_service is None:
            self.event_service = ExecutionEventService(
                execution_id=execution_id, trace_id=trace_id,
                agent_config_id=self.SKILL_AGENT_CONFIG_ID,
                agent_code=f"skill_{skill_name}",
                session_id=session_id, user_id=user_id,
            )
        self.bus = EventBus(event_service=self.event_service)
        self.bus.execution_id = execution_id
        self.bus.trace_id = trace_id

        # ── 主记录：start（替换原 pass 存根调用）──────────────────────────
        _record_db = None
        try:
            _record_db = SessionLocal()
            record_execution_start(
                _record_db, execution_id=execution_id,
                session_id=session_id, user_id=user_id, execution_mode="skill",
                target_id=str(skill_name), user_input=user_message,
                metadata={"worker_skill": skill_name}, trace_id=trace_id,
            )
        except Exception:
            pass

        self.bus.publish(EventEnvelope(
            execution_id=execution_id, trace_id=trace_id,
            event_type="agent_start", category=EventCategory.AGENT,
            levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
            content={"skill_name": skill_name, "user_message": user_message},
            source="skill_execution", source_id=skill_name, ui_hint="timeline",
        ))

        try:
            # 加载 Skill
            skill = await self._load_skill(skill_name)
            if skill is None:
                self.bus.publish(EventEnvelope(
                    execution_id=execution_id, trace_id=trace_id,
                    event_type="error", category=EventCategory.ERROR,
                    levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                    content={"message": f"技能不存在：{skill_name}"},
                    source="skill_execution", source_id=skill_name,
                ))
                yield SkillEvent(type="error", data={"message": f"技能不存在：{skill_name}"})
                _error_text = f"技能不存在：{skill_name}"
                # 不直接 return 裸退：经 finally 统一收尾（record failed + metrics + close）
                return

            yield SkillEvent(type="start", data={
                "skill_name": skill["name"],
                "description": skill.get("description", ""),
            })

            # 注入 sys.path
            _skill_dir = skill.get("dir")
            self._injected_sys_paths = []
            if _skill_dir:
                for candidate in [Path(_skill_dir)] + list(Path(_skill_dir).iterdir()):
                    if candidate.is_dir() and str(candidate) not in sys.path:
                        sys.path.insert(0, str(candidate))
                        self._injected_sys_paths.append(str(candidate))

            yield SkillEvent(type="progress", data={
                "stage": "skill_agent_running",
                "message": "正在执行技能 Agent...",
            })

            # ── 执行 Agent：总超时 + 队列桥接 SSE ────────────────────────
            out_q: asyncio.Queue = asyncio.Queue()
            handler = SkillEventHandler(skill_name=skill_name, bus=self.bus, out_q=out_q)

            try:
                toolkit = self._build_toolkit(extra_tools, skill.get("allowed_tools"))
                system_prompt = self._build_system_prompt(skill, session_id, user_id)
                model = self._build_model(model_id)
                agent = self._create_agent(skill_name, system_prompt, model, toolkit)
                user_msg = UserMsg(name="user", content=user_message)

                async def _consume() -> None:
                    async for event in agent.reply_stream(inputs=user_msg):
                        await handler.handle(event)

                consumer = asyncio.create_task(_consume())

                def _on_consumer_done(_task: asyncio.Task) -> None:
                    # consumer 结束（含取消）时投递哨兵，唤醒阻塞在 out_q.get() 上的主循环
                    try:
                        out_q.put_nowait(None)
                    except Exception:
                        pass

                consumer.add_done_callback(_on_consumer_done)
                handle = get_run_registry().register(
                    execution_id, consumer, out_q=out_q, agent=agent,
                    handler=handler, user_id=user_id,
                )
                deadline = time.monotonic() + self.timeout
                while True:
                    if (consumer.done() and out_q.empty()
                            and handle.status != "waiting_hitl"):
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        # 完成与超时同时到达：正常完成优先
                        if consumer.done() and out_q.empty():
                            break
                        timed_out = True
                        consumer.cancel()
                        await asyncio.gather(consumer, return_exceptions=True)
                        break
                    try:
                        evt = await asyncio.wait_for(asyncio.shield(out_q.get()),
                                                     timeout=remaining)
                        if evt is None:
                            # 哨兵：consumer 已结束（含取消），立即退出主循环；
                            # 哨兵绝不 yield 到 SSE
                            break
                        yield evt
                    except asyncio.TimeoutError:
                        # 完成与超时同时到达：正常完成优先
                        if consumer.done() and out_q.empty():
                            break
                        timed_out = True
                        consumer.cancel()
                        await asyncio.gather(consumer, return_exceptions=True)
                        break

                # 传播消费者异常
                exc = consumer.exception() if consumer.done() and not consumer.cancelled() else None
                if exc is not None and not timed_out:
                    raise exc
                # 消费者被取消（registry.cancel 触达）→ 不算成功完成
                _consumer_cancelled = handle is not None and handle.task.cancelled()
                if not timed_out and not _consumer_cancelled:
                    _exec_success = True

                if timed_out:
                    # 超时 SSE 提示必须在 finally 之外 yield：
                    # GeneratorExit 传播期间禁止在 finally 内 yield
                    yield SkillEvent(type="error", data={"message": f"执行超时（>{self.timeout}s），已熔断"})
                elif _consumer_cancelled:
                    # 用户取消：SSE 中断提示同样在 finally 之外 yield（同上约束）
                    _reason = handle.interrupt_reason or "user_cancel"
                    yield SkillEvent(type="error", data={"message": f"执行被中断（{_reason}）"})

            except Exception as e:
                _error_text = str(e)
                logger.exception("技能执行异常：%s", e)
                self.bus.publish(EventEnvelope(
                    execution_id=execution_id, trace_id=trace_id,
                    event_type="error", category=EventCategory.ERROR,
                    levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                    content={"message": str(e)},
                    source="skill_execution", source_id=skill_name, ui_hint="timeline",
                ))
                yield SkillEvent(type="error", data={"message": str(e)})

        finally:
            # 清理 sys.path
            for p in getattr(self, "_injected_sys_paths", []):
                if p in sys.path:
                    sys.path.remove(p)
            self._injected_sys_paths = []

            # 断连（GeneratorExit）时尽力取消仍在运行的消费者任务
            if consumer is not None and not consumer.done():
                consumer.cancel()

            # ── 收尾：所有退出路径（正常/异常/超时/断连/技能不存在）统一执行，且仅执行一次 ──
            # record_execution_* 自身吞异常，finally 内调用安全；
            # 此处不可 yield（GeneratorExit 传播期禁止），仅做同步收尾。
            elapsed_ms = int((time.perf_counter() - _exec_start) * 1000)
            if not _finalized:
                _finalized = True
                # 统一中断收尾：超时熔断 或 registry.cancel 触发的用户取消
                cancel_reason = None
                if timed_out:
                    cancel_reason = "timeout"
                elif handle is not None and handle.task.cancelled():
                    cancel_reason = handle.interrupt_reason or "user_cancel"
                if cancel_reason:
                    for etype in ("interrupt_requested", "interrupted"):
                        self.bus.publish(EventEnvelope(
                            execution_id=execution_id, trace_id=trace_id,
                            event_type=etype, category=EventCategory.INTERRUPT,
                            levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                            content={"reason": cancel_reason},
                            interrupt_reason=cancel_reason, source="skill_execution",
                            source_id=skill_name, ui_hint="timeline",
                        ))
                    record_execution_failed(
                        _record_db, execution_id,
                        error=f"执行被中断（{cancel_reason}）", latency_ms=elapsed_ms,
                        interrupt_reason=cancel_reason,
                    )
                elif not _exec_success:
                    record_execution_failed(_record_db, execution_id,
                                            error=_error_text, latency_ms=elapsed_ms)
                else:
                    record_execution_done(
                        _record_db, execution_id,
                        output=None, latency_ms=elapsed_ms,
                        input_tokens=handler.usage.get("input_tokens") if handler else None,
                        output_tokens=handler.usage.get("output_tokens") if handler else None,
                        iterations=handler.iterations if handler else None,
                    )

                # 记录指标
                self._record_metrics(skill_name, _exec_success, elapsed_ms / 1000.0)

            # 反注册：任何退出路径都执行（cancel API 查询表随即失效）
            try:
                get_run_registry().unregister(execution_id)
            except Exception:
                logger.debug("run registry unregister failed: %s", execution_id)

            # 关闭数据库会话（含技能不存在早退路径）
            if _record_db is not None:
                try:
                    _record_db.close()
                except Exception:
                    pass
    
    def _create_agent(
        self,
        name: str,
        system_prompt: str,
        model: Any,
        toolkit: Any,
    ) -> Any:
        """创建 Agent 实例（原生 API）。"""
        from agentscope.agent import Agent
        
        return Agent(
            name=name,
            system_prompt=system_prompt,
            model=model,
            toolkit=toolkit,
        )

    async def _load_skill(self, skill_name: str) -> dict[str, Any] | None:
        """加载 Skill（保持原有逻辑不变）。"""
        # 方式 0：数据库优先
        try:
            from app.db.database import SessionLocal
            from app.models.ai.ai_skill_package import AiSkillPackage

            db = SessionLocal()
            try:
                pkg = db.query(AiSkillPackage).filter(
                    AiSkillPackage.package_id == skill_name,
                ).first()
                if pkg is not None and pkg.skill_markdown:
                    markdown = pkg.skill_markdown
                    return {
                        "name": skill_name,
                        "description": pkg.description or f"技能 {skill_name}",
                        "markdown": markdown,
                        "dir": str(_SKILLS_BASE / skill_name),
                        "allowed_tools": parse_allowed_tools(markdown),
                        "source": "db",
                    }
            finally:
                db.close()
        except Exception as e:
            logger.debug("从数据库加载 SKILL.md 失败：%s", e)

        # 方式 1：workspace
        try:
            skill = await self.workspace.get_skill(skill_name)
            if skill and skill.get("markdown"):
                skill.setdefault("allowed_tools", parse_allowed_tools(skill.get("markdown", "")))
                skill["source"] = "workspace"
                return skill
        except Exception:
            pass

        # 方式 2：文件系统
        md_path = _SKILLS_BASE / skill_name / "SKILL.md"
        if md_path.exists():
            try:
                markdown = md_path.read_text(encoding="utf-8")
                return {
                    "name": skill_name,
                    "description": f"技能 {skill_name}",
                    "markdown": markdown,
                    "dir": str(md_path.parent),
                    "allowed_tools": parse_allowed_tools(markdown),
                    "source": "file",
                }
            except OSError as e:
                logger.error("读取 SKILL.md 失败：%s", e)

        return None

    def _build_toolkit(
        self,
        extra_tools: list[ToolBase] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> Any:
        """构建 Toolkit（保持原有逻辑）。"""
        from agentscope.tool import Toolkit

        all_tools = list(self.tool_manager.tools.values())
        if extra_tools:
            all_tools.extend(extra_tools)

        if allowed_tools:
            allowed_set = set(allowed_tools)
            tools = [t for t in all_tools if getattr(t, "name", "") in allowed_set]
            cache_key = ",".join(sorted(allowed_set))
        else:
            tools = all_tools
            cache_key = "__all__"

        if cache_key in self._cached_toolkits and not extra_tools:
            return self._cached_toolkits[cache_key]

        if self._cached_skill_loader is None:
            from agentscope.skill import LocalSkillLoader
            skills_dir = str(_SKILLS_BASE)
            self._cached_skill_loader = LocalSkillLoader(directory=skills_dir, scan_subdir=True)

        toolkit = Toolkit(tools=tools, skills_or_loaders=[self._cached_skill_loader])

        if not extra_tools:
            self._cached_toolkits[cache_key] = toolkit

        return toolkit

    def _build_system_prompt(self, skill: dict, session_id: int | None, user_id: int | None) -> str:
        """构建 System Prompt（保持原有逻辑）。"""
        parts = [
            "你是一个技能执行助手。请严格按照以下技能指令完成用户请求。",
            "如果需要使用工具，请先阅读技能指令了解可用工具和用法。",
            "",
            f"## 技能：{skill['name']}",
            skill.get("markdown", ""),
        ]
        if session_id:
            parts.append(f"\n当前会话 ID: {session_id}")
        if user_id:
            parts.append(f"当前用户 ID: {user_id}")
        return "\n".join(parts)

    def _build_model(self, model_id: int | None = None) -> Any:
        """构建模型（保持原有逻辑）。"""
        from app.ai.strategy.factory_ext import build_model

        if self.model_config:
            return build_model(self.model_config)

        db_config = self._get_model_config_from_db(model_id)
        if db_config:
            return build_model(db_config)

        logger.warning("未找到数据库模型配置，使用环境变量 fallback")
        return build_model({
            "provider": "openai",
            "model": os.environ.get("DEFAULT_MODEL", "gpt-4o-mini"),
            "base_url": os.environ.get("OPENAI_BASE_URL", ""),
            "api_key_ref": "ENV:OPENAI_API_KEY",
        })

    def _get_model_config_from_db(self, model_id: int | None = None) -> dict | None:
        """获取模型配置（保持原有逻辑）。"""
        from app.db.database import SessionLocal
        from app.models.ai.ai_api_key import AiApiKey, AiChatModel

        db = SessionLocal()
        try:
            if model_id:
                model = db.query(AiChatModel).filter(
                    AiChatModel.id == model_id,
                    AiChatModel.status == 1,
                ).first()
            else:
                model = db.query(AiChatModel).filter(
                    AiChatModel.status == 1,
                    AiChatModel.type == 1,
                    AiChatModel.is_default == True,
                ).first()
                if not model:
                    model = db.query(AiChatModel).filter(
                        AiChatModel.status == 1,
                        AiChatModel.type == 1,
                    ).order_by(AiChatModel.sort.desc(), AiChatModel.id.asc()).first()

            if not model:
                return None

            api_key = db.query(AiApiKey).filter(
                AiApiKey.id == model.key_id,
                AiApiKey.status == 1,
            ).first()
            if not api_key:
                return None

            raw_url = (api_key.url or "").rstrip("/")
            platform_lower = (api_key.platform or "openai").lower()
            _OPENAI_COMPATIBLE = {
                "openai", "智谱", "讯飞", "百度", "gpustack", 
                "dify", "coze", "compatible", "deepseek", "moonshot",
            }
            if raw_url and platform_lower in _OPENAI_COMPATIBLE and not raw_url.endswith("/v1"):
                raw_url = raw_url + "/v1"

            config = {
                "provider": platform_lower,
                "model": model.model,
                "base_url": raw_url or None,
                "api_key": api_key.api_key,
                "temperature": model.temperature or 0.7,
            }
            
            if model.max_tokens:
                from app.constants.llm_tokens import (
                    clamp_input_budget,
                    clamp_output_tokens,
                    resolve_context_window,
                )
                _window = resolve_context_window(getattr(model, "model", None))
                _input_budget = clamp_input_budget(
                    None, window=_window, output_tokens=int(model.max_tokens)
                )
                config["max_tokens"] = clamp_output_tokens(
                    model.max_tokens,
                    window=_window,
                    input_budget=_input_budget,
                )

            logger.info("使用数据库模型：%s", model.name)
            return config
        except Exception as e:
            logger.error("从数据库获取模型配置失败：%s", e)
            return None
        finally:
            db.close()

    def _record_metrics(self, skill_id: str, success: bool, elapsed: float) -> None:
        """记录执行指标（保持原有逻辑）。"""
        try:
            from app.db.database import SessionLocal
            from app.models.ai.ai_skill_metrics import AiSkillMetrics

            db = SessionLocal()
            try:
                metrics = db.query(AiSkillMetrics).filter(
                    AiSkillMetrics.skill_id == skill_id
                ).first()

                if metrics is None:
                    metrics = AiSkillMetrics(
                        skill_id=skill_id,
                        execution_count=1,
                        success_rate=1.0 if success else 0.0,
                        avg_latency=round(elapsed, 4),
                        user_rating=0.0,
                    )
                    db.add(metrics)
                else:
                    count = int(metrics.execution_count or 0)
                    new_count = count + 1
                    window = min(new_count, 100)

                    old_sr = float(metrics.success_rate or 0.0)
                    new_sr = (old_sr * min(count, 100) + (1.0 if success else 0.0)) / window

                    old_lat = float(metrics.avg_latency or 0.0)
                    new_lat = (old_lat * min(count, 100) + elapsed) / window

                    metrics.execution_count = new_count
                    metrics.success_rate = round(new_sr, 4)
                    metrics.avg_latency = round(new_lat, 4)

                db.commit()
                logger.debug("skill metrics recorded: %s", skill_id)
                
                # 自动进化
                try:
                    from app.models.ai.ai_skill_evolution_config import AiSkillEvolutionConfig
                    cfg = db.query(AiSkillEvolutionConfig).filter(
                        AiSkillEvolutionConfig.skill_id == skill_id
                    ).first()
                    if cfg and cfg.is_auto_enabled:
                        from app.ai.skills.evolution.engine import SkillEvolutionEngine
                        SkillEvolutionEngine(db=db).evolve_if_needed(
                            skill_id, trigger="auto",
                            model_code=cfg.model_code or None,
                        )
                except Exception as exc:
                    logger.warning("auto evolution skipped for %s: %s", skill_id, exc)
            except Exception as exc:
                logger.warning("failed to record metrics for %s: %s", skill_id, exc)
                db.rollback()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("metrics recording error: %s", exc)
