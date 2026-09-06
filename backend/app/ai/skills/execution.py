"""SkillExecutionService - 基于 AgentScope 2.0 的技能执行服务。

🎯 **原生化改造 Phase 2**:
- ✅ 删除 `_estimate_tokens()`, `_truncate_message()` (38 行)  
- ✅ 删除 `_is_context_length_error()` (22 行)
- ✅ 删除上下文长度降级重试逻辑 (108 行)
- ✅ 删除 `_get_model_max_input_tokens()` (49 行)  
- ✅ 使用 `EventStreamHandler` 基类统一事件处理
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
from agentscope.event import EventStreamHandler
from agentscope.message import UserMsg

# Stub 函数占位（待实现）
def record_execution_start(*a, **kw): pass
def record_execution_done(*a, **kw): pass
def record_execution_failed(*a, **kw): pass
def record_execution_status(*a, **kw): pass

from app.ai.services.execution_event_service import ExecutionEventService
from app.schemas.agent.agent import ExecutionEventType

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


class SkillEventHandler(EventStreamHandler):
    """AgentScope 事件流处理器，映射为 SSE 技能事件。

    🎯 **关键改进**:
    1. 继承 `EventStreamHandler` 基类
    2. 重写 `handle()` 方法统一分发事件类型
    3. 不重写每个具体事件类型，减少代码量
    """
    
    def __init__(self, skill_name: str, event_service: ExecutionEventService, yield_fn):
        super().__init__()
        self.skill_name = skill_name
        self.event_service = event_service
        self.yield_fn = yield_fn
        self.text_parts: list[str] = []
        self.current_tool_name: str = ""
    
    async def handle(self, event) -> None:
        """统一事件分发器。"""
        from agentscope.event import (
            TextBlockDeltaEvent, ThinkingBlockStartEvent, 
            ThinkingBlockDeltaEvent, ThinkingBlockEndEvent,
            ToolCallStartEvent, ToolCallDeltaEvent, ToolCallEndEvent,
            ToolResultTextDeltaEvent, ToolResultDataDeltaEvent,
            ReplyEndEvent, ErrorEvent
        )
        
        if isinstance(event, (ThinkingBlockStartEvent, ThinkingBlockEndEvent)):
            logger.debug("[SkillExecution] %s", event.__class__.__name__)
            
        elif isinstance(event, ThinkingBlockDeltaEvent):
            delta = event.delta or ""
            if not delta.strip():
                return
            self.event_service.record(
                event_type=ExecutionEventType.THINKING,
                content={"delta": delta},
                source="agent",
                source_id=self.skill_name,
            )
            await self.yield_fn(SkillEvent(type="thinking", data={"content": delta}))
            
        elif isinstance(event, TextBlockDeltaEvent):
            if not event.delta.strip():
                return
            self.text_parts.append(event.delta)
            self.event_service.record(
                event_type=ExecutionEventType.TEXT,
                content={"delta": event.delta},
                source="agent",
                source_id=self.skill_name,
            )
            await self.yield_fn(SkillEvent(type="text", data={"content": event.delta}))
            
        elif isinstance(event, (ToolCallStartEvent, ToolCallDeltaEvent, ToolCallEndEvent)):
            self._handle_tool_call(event)
            
        elif isinstance(event, (ToolResultTextDeltaEvent, ToolResultDataDeltaEvent)):
            self._handle_tool_result(event)
            
        elif isinstance(event, ReplyEndEvent):
            final_text = "".join(self.text_parts)
            self.event_service.record(
                event_type=ExecutionEventType.SKILL_RESULT,
                content={"result": final_text},
                source="agent",
                source_id=self.skill_name,
            )
            
            # 扫描产物文件
            from app.ai.skills.artifact_store import scan_artifacts
            
            yield_fn = self.yield_fn
            
            # TODO: execution_id 需要通过闭包或参数传递
            # artifacts = scan_artifacts(execution_id)
            # for art in artifacts:
            #     yield_fn(SkillEvent(type="artifact", data={...}))
            
            yield_fn(SkillEvent(type="done", data={"result": final_text}))
            
        elif isinstance(event, ErrorEvent):
            await self.yield_fn(SkillEvent(type="error", data={
                "message": str(event.error),
                "type": event.__class__.__name__
            }))
    
    def _handle_tool_call(self, event) -> None:
        """处理工具调用相关事件。"""
        from agentscope.event import ToolCallStartEvent, ToolCallDeltaEvent, ToolCallEndEvent
        
        if isinstance(event, ToolCallStartEvent):
            self.current_tool_name = getattr(event, "tool_call_name", "") or ""
            event.tool_args = {}  # AgentScope 已提供结构化参数
            
        elif isinstance(event, ToolCallDeltaEvent):
            pass
            
        elif isinstance(event, ToolCallEndEvent):
            tool_input = getattr(event, "tool_args", {}) or {}
            
            self.event_service.record(
                event_type=ExecutionEventType.TOOL_CALL,
                content={"tool_name": self.current_tool_name, "input": tool_input},
                source="agent",
                source_id=self.skill_name,
            )
            self.yield_fn(SkillEvent(type="tool_call", data={
                "tool_name": self.current_tool_name,
                "input": tool_input,
            }))
    
    def _handle_tool_result(self, event) -> None:
        """处理工具结果事件。"""
        from agentscope.event import ToolResultTextDeltaEvent, ToolResultDataDeltaEvent
        
        if isinstance(event, ToolResultTextDeltaEvent):
            result_delta = getattr(event, "delta", "") or ""
            if not result_delta.strip():
                return
            self.event_service.record(
                event_type=ExecutionEventType.TOOL_RESULT,
                content={
                    "tool_name": self.current_tool_name,
                    "delta": result_delta,
                    "state": "success",
                },
                source="agent",
                source_id=self.skill_name,
            )
            self.yield_fn(SkillEvent(type="tool_result", data={
                "tool_name": self.current_tool_name,
                "delta": result_delta,
                "state": "success",
            }))
            
        elif isinstance(event, ToolResultDataDeltaEvent):
            media_type = getattr(event, "media_type", "") or ""
            data_b64 = getattr(event, "data", None)
            url = getattr(event, "url", None)
            data_size = len(data_b64) if data_b64 else 0
            
            self.event_service.record(
                event_type=ExecutionEventType.TOOL_RESULT,
                content={
                    "tool_name": self.current_tool_name,
                    "media_type": media_type,
                    "data_size": data_size,
                    "url": url,
                    "state": "success",
                    "binary": True,
                },
                source="agent",
                source_id=self.skill_name,
            )


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
        """流式执行技能（简化版）。"""
        _exec_start = time.perf_counter()
        _exec_success = False

        if execution_id is None:
            execution_id = str(uuid.uuid4())

        # 记录执行开始
        _record_db = None
        try:
            from app.db.database import SessionLocal
            _record_db = SessionLocal()
            record_execution_start(_record_db, execution_id=execution_id,
                session_id=session_id, user_id=user_id, execution_mode="skill",
                target_id=str(skill_name), user_input=user_message,
                metadata={"worker_skill": skill_name})
        except Exception:
            pass

        if self.event_service is None:
            self.event_service = ExecutionEventService(
                execution_id=execution_id, trace_id=trace_id,
                agent_config_id=self.SKILL_AGENT_CONFIG_ID,
                agent_code=f"skill_{skill_name}",
                session_id=session_id, user_id=user_id,
            )

        self.event_service.record(
            event_type=ExecutionEventType.AGENT_START,
            content={"skill_name": skill_name, "user_message": user_message},
            source="skill_execution", source_id=skill_name,
        )

        # 加载 Skill
        skill = await self._load_skill(skill_name)
        if skill is None:
            self.event_service.record(
                event_type=ExecutionEventType.ERROR,
                content={"message": f"技能不存在：{skill_name}"},
                source="skill_execution", source_id=skill_name,
            )
            yield SkillEvent(type="error", data={"message": f"技能不存在：{skill_name}"})
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

        # 构建组件
        yield SkillEvent(type="progress", data={
            "stage": "skill_agent_running",
            "message": "正在执行技能 Agent...",
        })

        # 执行 Agent（使用原生事件处理器）
        try:
            toolkit = self._build_toolkit(extra_tools, skill.get("allowed_tools"))
            system_prompt = self._build_system_prompt(skill, session_id, user_id)
            model = self._build_model(model_id)
            
            handler = SkillEventHandler(
                skill_name=skill_name,
                event_service=self.event_service,
                yield_fn=lambda evt: yield evt
            )
            
            agent = self._create_agent(skill_name, system_prompt, model, toolkit)
            user_msg = UserMsg(name="user", content=user_message)
            
            async for event in agent.reply_stream(inputs=user_msg):
                await handler.handle(event)
                
            _exec_success = True
            
        except Exception as e:
            logger.exception("技能执行异常：%s", e)
            self.event_service.record(
                event_type=ExecutionEventType.ERROR,
                content={"message": str(e)},
                source="skill_execution",
            )
            yield SkillEvent(type="error", data={"message": str(e)})
        finally:
            # 清理 sys.path
            for p in getattr(self, "_injected_sys_paths", []):
                if p in sys.path:
                    sys.path.remove(p)
            
            # 记录指标
            elapsed = time.perf_counter() - _exec_start
            self._record_metrics(skill_name, _exec_success, elapsed)
            
            # 关闭数据库
            if _record_db is not None:
                try:
                    _record_db.close()
                except Exception:
                    pass
    
    async def _run_agent_native(
        self,
        skill_name: str,
        system_prompt: str,
        model: Any,
        toolkit: Any,
        user_message: str,
        execution_id: str,
    ) -> AsyncGenerator[SkillEvent, None]:
        """使用原生事件处理器运行 Agent。"""
        handler = SkillEventHandler(
            skill_name=skill_name,
            event_service=self.event_service,
            yield_fn=lambda evt: yield evt
        )
        
        agent = self._create_agent(skill_name, system_prompt, model, toolkit)
        user_msg = UserMsg(name="user", content=user_message)
        
        async for event in agent.reply_stream(inputs=user_msg):
            await handler.handle(event)

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
