"""SkillExecutionService - 基于 AgentScope 2.0 的技能执行服务。

集成 AgentExecutionEvent 事件日志记录。
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

# TODO: 执行记录器待 AgentScope 原生 API 适配后重建
# from app.ai.gateway.execution_recorder import (
#     record_execution_start, record_execution_done,
#     record_execution_failed, record_execution_status,
# )

def record_execution_start(*a, **kw): pass
def record_execution_done(*a, **kw): pass
def record_execution_failed(*a, **kw): pass
def record_execution_status(*a, **kw): pass

from app.ai.services.execution_event_service import ExecutionEventService
from app.schemas.agent.agent import ExecutionEventType

logger = logging.getLogger(__name__)

# 技能包根目录（backend/data/skills/）
_SKILLS_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "skills"


@dataclass
class SkillEvent:
    """技能执行事件。

    Attributes:
        type: "start" | "thinking" | "text" | "tool_call" | "tool_result" | "done" | "error"
        data: 事件数据字典
    """
    type: str
    data: dict = field(default_factory=dict)


def parse_allowed_tools(markdown: str) -> list[str] | None:
    """从 SKILL.md frontmatter 解析 allowed-tools 字段。

    格式：allowed-tools: [tool_a, tool_b]
    返回 None 表示未声明（回退全量工具）。
    """
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


class SkillExecutionService:
    """基于 AgentScope 2.0 的技能执行服务。

    职责：
    1. 加载 Skill 指令（SKILL.md）—— 优先 workspace，fallback 到 data/skills/
    2. 构建 Toolkit（tools + skills）
    3. 创建轻量 Agent 并执行
    4. 流式返回执行结果
    5. 记录所有执行事件到 agent_execution_event 表
    """

    DEFAULT_TIMEOUT = 300
    SKILL_AGENT_CONFIG_ID = 0

    # ── 模块级缓存：避免每次执行都重新扫描技能目录 ──
    _cached_skill_loader: Any = None
    _cached_toolkits: dict[str, Any] = {}  # key: allowed_tools 指纹

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
        """流式执行技能。

        Args:
            skill_name: 技能名称（对应数据库 package_id）
            user_message: 用户输入消息
            session_id: 会话 ID
            user_id: 用户 ID
            extra_tools: 额外工具
            model_id: 用户选择的模型 ID（ai_chat_model.id），为空则使用默认启用模型
            execution_id: 执行ID，为空则自动生成
            trace_id: 链路追踪ID
        """
        _exec_start = time.perf_counter()
        _exec_success = False
        _recorded_error = False  # 标记是否已写入具体 error，避免 finally 兜底覆盖

        # 执行ID（供 agent_execution 统一记录使用；若调用方已传入则复用）
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        # 统一写一条 agent_execution 记录（execution_mode="skill"，target_id=package_id）
        # 复用单个 db session，不新建连接池；recorder 内部吞异常，不影响主流程。
        _record_db = None
        try:
            from app.db.database import SessionLocal
            _record_db = SessionLocal()
            record_execution_start(
                _record_db,
                execution_id=execution_id,
                session_id=session_id,
                user_id=user_id,
                execution_mode="skill",
                target_id=str(skill_name),
                user_input=user_message,
                metadata={"worker_skill": skill_name},
            )
        except Exception as _rec_err:
            logger.debug("record_execution_start failed (ignored): %s", _rec_err)

        # 初始化事件服务
        if self.event_service is None:
            self.event_service = ExecutionEventService(
                execution_id=execution_id,
                trace_id=trace_id,
                agent_config_id=self.SKILL_AGENT_CONFIG_ID,
                agent_code=f"skill_{skill_name}",
                session_id=session_id,
                user_id=user_id,
            )

        # 记录执行开始事件
        self.event_service.record(
            event_type=ExecutionEventType.AGENT_START,
            content={
                "skill_name": skill_name,
                "user_message": user_message,
                "session_id": session_id,
                "user_id": user_id,
                "model_id": model_id,
            },
            source="skill_execution",
            source_id=skill_name,
        )

        # 1. 加载 Skill（优先 workspace，fallback 到 data/skills/ 目录）
        self.event_service.record(
            event_type=ExecutionEventType.SKILL_LOAD,
            content={"skill_name": skill_name},
            source="skill_execution",
            source_id=skill_name,
        )

        skill = await self._load_skill(skill_name)
        if skill is None:
            self.event_service.record(
                event_type=ExecutionEventType.ERROR,
                content={"message": f"技能不存在: {skill_name}"},
                source="skill_execution",
                source_id=skill_name,
            )
            yield SkillEvent(type="error", data={"message": f"技能不存在: {skill_name}"})
            return

        self.event_service.record(
            event_type=ExecutionEventType.SKILL_LOADED,
            content={
                "skill_name": skill["name"],
                "description": skill.get("description", ""),
            },
            source="skill_execution",
            source_id=skill_name,
        )

        yield SkillEvent(type="start", data={
            "skill_name": skill["name"],
            "description": skill.get("description", ""),
        })

        # 2.0 子目录兼容：将 skill 目录及其一级子目录注入 sys.path，
        # 确保含 skill/、data/ 等子目录的第三方 skill 内部 import 可解析
        self._injected_sys_paths: list[str] = []
        _skill_dir = skill.get("dir")
        if _skill_dir:
            for _candidate in [Path(_skill_dir)] + list(Path(_skill_dir).iterdir()):
                if _candidate.is_dir() and str(_candidate) not in sys.path:
                    sys.path.insert(0, str(_candidate))
                    self._injected_sys_paths.append(str(_candidate))

        # 2. 构建组件（每个阶段都下发进度事件，避免前端长时无反馈）
        _skill_name = skill["name"]
        _allowed = skill.get("allowed_tools") or []
        logger.info("[Skill Execution] 开始构建组件：toolkit, system_prompt, model")
        yield SkillEvent(type="progress", data={
            "stage": "skill_toolkit_building",
            "message": f"正在为技能 {_skill_name} 组装工具集（{len(_allowed)} 个工具）...",
        })
        toolkit = self._build_toolkit(extra_tools, _allowed)
        yield SkillEvent(type="progress", data={
            "stage": "skill_prompt_building",
            "message": "正在构建系统提示词与上下文...",
        })
        system_prompt = self._build_system_prompt(skill, session_id, user_id)
        yield SkillEvent(type="progress", data={
            "stage": "skill_model_loading",
            "message": "正在加载 AI 模型...",
        })
        model = self._build_model(model_id)
        _model_name = "默认模型"
        try:
            _model_name = getattr(model, "model_name", None) or getattr(model, "config", {}).get("model", "默认模型")
        except Exception:
            pass
        logger.info("[Skill Execution] 模型构建完成：%s", model)
        yield SkillEvent(type="progress", data={
            "stage": "skill_agent_running",
            "message": f"模型 {_model_name} 就绪，正在执行技能 Agent...",
        })

        # 2.5 预检：估算输入 token 数，超出模型上下文窗口时主动截断用户输入
        max_input_tokens = self._get_model_max_input_tokens(model_id)
        if max_input_tokens:
            estimated_tokens = (
                self._estimate_tokens(system_prompt)
                + self._estimate_tokens(user_message)
            )
            if estimated_tokens > max_input_tokens:
                original_len = len(user_message)
                user_message = self._truncate_message(
                    user_message, max_input_tokens, system_prompt,
                )
                logger.warning(
                    "[Skill Execution] 输入估算 %d tokens 超过模型上下文限制 %d，"
                    "用户消息已从 %d 字符截断至 %d 字符",
                    estimated_tokens, max_input_tokens, original_len, len(user_message),
                )
                yield SkillEvent(type="progress", data={
                    "stage": "skill_input_truncated",
                    "message": f"输入内容过长（估算 {estimated_tokens} tokens，上限 {max_input_tokens}），已自动压缩",
                })

        # 3. 执行 Agent（若模型服务不支持 tool_choice，降级为无工具模式重试）
        logger.info(f"[Skill Execution] 开始执行 Agent...")
        try:
            async for event in self._run_agent(
                skill_name=skill["name"],
                system_prompt=system_prompt,
                model=model,
                toolkit=toolkit,
                user_message=user_message,
                execution_id=self.event_service.execution_id,
            ):
                logger.debug(f"[Skill Execution] 收到事件：{event.type}")
                if event.type == "done":
                    _exec_success = True
                yield event
        except asyncio.TimeoutError:
            self.event_service.record(
                event_type=ExecutionEventType.TIMEOUT,
                content={"message": f"执行超时（{self.timeout}秒）"},
                source="skill_execution",
            )
            yield SkillEvent(type="error", data={"message": f"执行超时（{self.timeout}秒）"})
        except Exception as e:
            err_msg = str(e)
            # 检测上下文长度超限错误
            # 先尝试去掉工具集重试（工具定义可能占用大量 token）
            if self._is_context_length_error(err_msg) and toolkit is not None:
                logger.warning(
                    "输入超出上下文窗口，尝试去掉工具集重试: %s",
                    err_msg,
                )
                yield SkillEvent(type="progress", data={
                    "stage": "skill_retry_without_tools",
                    "message": "输入过长，正在精简工具集重试...",
                })
                try:
                    async for event in self._run_agent(
                        skill_name=skill["name"],
                        system_prompt=system_prompt,
                        model=model,
                        toolkit=None,
                        user_message=user_message,
                        execution_id=self.event_service.execution_id,
                    ):
                        if event.type == "done":
                            _exec_success = True
                        yield event
                except Exception as e2:
                    err_msg2 = str(e2)
                    if self._is_context_length_error(err_msg2):
                        logger.warning("去掉工具集后仍超出上下文窗口: %s", err_msg2)
                        friendly_msg = (
                            "输入内容超出模型上下文窗口限制，请缩短输入内容后重试。"
                            "如需处理更长文本，请切换至支持更大上下文窗口的模型。"
                        )
                        self.event_service.record(
                            event_type=ExecutionEventType.ERROR,
                            content={"message": friendly_msg, "original_error": err_msg2},
                            source="skill_execution",
                        )
                        yield SkillEvent(type="error", data={"message": friendly_msg})
                    else:
                        logger.exception("去掉工具集重试时出现其他错误: %s", e2)
                        self.event_service.record(
                            event_type=ExecutionEventType.ERROR,
                            content={"message": str(e2)},
                            source="skill_execution",
                        )
                        yield SkillEvent(type="error", data={"message": str(e2)})
            elif self._is_context_length_error(err_msg):
                # 原本就无工具集，或预检已截断但仍超限
                logger.warning("技能执行因输入超出模型上下文窗口而失败: %s", err_msg)
                friendly_msg = (
                    "输入内容超出模型上下文窗口限制，请缩短输入内容后重试。"
                    "如需处理更长文本，请切换至支持更大上下文窗口的模型。"
                )
                self.event_service.record(
                    event_type=ExecutionEventType.ERROR,
                    content={"message": friendly_msg, "original_error": err_msg},
                    source="skill_execution",
                )
                yield SkillEvent(type="error", data={"message": friendly_msg})
            # 检测 vLLM 不支持 tool_choice 的错误，降级为纯对话模式
            elif "tool_choice" in err_msg or "tool-call-parser" in err_msg:
                logger.warning(
                    "模型服务不支持 tool_choice，降级为无工具模式: %s", err_msg
                )
                try:
                    async for event in self._run_agent(
                        skill_name=skill["name"],
                        system_prompt=system_prompt,
                        model=model,
                        toolkit=None,  # 降级：不传工具
                        user_message=user_message,
                        execution_id=self.event_service.execution_id,
                    ):
                        if event.type == "done":
                            _exec_success = True
                        yield event
                except Exception as e2:
                    logger.exception("降级执行也失败: %s", e2)
                    self.event_service.record(
                        event_type=ExecutionEventType.ERROR,
                        content={
                            "message": f"执行失败（模型服务需配置 --enable-auto-tool-choice --tool-call-parser）",
                            "error": str(e2),
                        },
                        source="skill_execution",
                    )
                    yield SkillEvent(type="error", data={
                        "message": f"执行失败（模型服务需配置 --enable-auto-tool-choice --tool-call-parser）: {e2}"
                    })
            else:
                logger.exception("技能执行异常: %s", e)
                # 统一记录失败（含真实错误信息），recorder 吞异常不影响主流程
                try:
                    if _record_db is not None:
                        record_execution_failed(
                            _record_db, execution_id, error=err_msg,
                            latency_ms=round((time.perf_counter() - _exec_start) * 1000),
                        )
                        _recorded_error = True
                except Exception as _rec_err:
                    logger.debug("record_execution_failed failed (ignored): %s", _rec_err)
                self.event_service.record(
                    event_type=ExecutionEventType.ERROR,
                    content={"message": err_msg},
                    source="skill_execution",
                )
                yield SkillEvent(type="error", data={"message": err_msg})
        finally:
            # 3.5 清理注入的 sys.path，避免跨 skill 执行污染
            for _p in getattr(self, "_injected_sys_paths", []):
                if _p in sys.path:
                    sys.path.remove(_p)
            self._injected_sys_paths = []

            # 4. 记录执行指标（异步写入，不阻塞主流程）
            elapsed = time.perf_counter() - _exec_start
            self._record_metrics(skill_name, _exec_success, elapsed)

            # 5. 记录执行完成事件
            self.event_service.record(
                event_type=ExecutionEventType.AGENT_COMPLETE,
                content={
                    "skill_name": skill_name,
                    "success": _exec_success,
                    "elapsed_ms": round(elapsed * 1000, 2),
                },
                source="skill_execution",
            )

            # 6. 统一写 agent_execution 终态（复用入口的 db session）
            try:
                if _record_db is not None:
                    if _exec_success:
                        record_execution_done(
                            _record_db, execution_id,
                            output=user_message, latency_ms=round(elapsed * 1000),
                        )
                    else:
                        # 失败兜底：仅当各 except 分支尚未写入具体 error 时才兜底标记 failed，
                        # 避免覆盖真实的 error 信息。
                        if not _recorded_error:
                            record_execution_failed(
                                _record_db, execution_id,
                                error="skill execution failed", latency_ms=round(elapsed * 1000),
                            )
            except Exception as _rec_err:
                logger.debug("record_execution done/failed failed (ignored): %s", _rec_err)
            finally:
                try:
                    if _record_db is not None:
                        _record_db.close()
                except Exception:
                    pass

    # ─── 上下文长度辅助方法 ──────────────────────────────────────────────

    @staticmethod
    def _is_context_length_error(error_msg: str) -> bool:
        """判断异常信息是否为上下文长度超限错误。

        需覆盖多种推理框架的错误文案，否则会漏判为普通异常而裸抛 400：
        - vLLM / OpenAI 兼容：  "maximum context length" / "context_length_exceeded"
        - llama.cpp / GPUStack："request (N tokens) exceeds the available
          context size (M tokens)" + type "exceed_context_size_error"
        """
        msg_lower = error_msg.lower()
        return (
            "maximum context length" in msg_lower
            or "context_length_exceeded" in msg_lower
            or "too many tokens" in msg_lower
            or ("max_tokens" in msg_lower and "exceed" in msg_lower)
            # ── llama.cpp / GPUStack 形态 ──
            or "exceed_context_size_error" in msg_lower
            or "exceeds the available context size" in msg_lower
            or "exceeds available context" in msg_lower
            or "beyond the context" in msg_lower
            or "n_prompt_tokens" in msg_lower
        )

    def _get_model_max_input_tokens(self, model_id: int | None = None) -> int | None:
        """返回可用于输入(prompt)的最大 token 数。

        硬约束：input + output <= 模型上下文窗口 - 安全余量。

        ⚠️ 注意 ai_chat_model.max_tokens 的语义是 **output(completion) 上限**，
        不是上下文窗口。旧实现误把它当窗口来减输出（max_tokens - 4096），
        在 qwen3-32b（DB max_tokens=4096）上算出 max(0, 4096)=4096，
        使 skill 的 prompt 被截断到仅 4096 token，窗口利用率不足 13%。
        现改为：窗口按模型名解析，减去 output 上限与安全余量。
        """
        from app.constants.llm_tokens import (
            DEFAULT_MAX_OUTPUT_TOKENS,
            clamp_input_budget,
            resolve_context_window,
        )

        model_name = (self.model_config or {}).get("model")
        output_tokens = int(
            (self.model_config or {}).get("max_tokens") or DEFAULT_MAX_OUTPUT_TOKENS
        )

        # 未拿到模型名时，尝试用 model_id 反查一次，避免误用兜底窗口
        if not model_name and model_id:
            try:
                from app.db.database import SessionLocal
                from app.models.ai.ai_api_key import AiChatModel

                db = SessionLocal()
                try:
                    row = (
                        db.query(AiChatModel)
                        .filter(AiChatModel.id == model_id)
                        .first()
                    )
                    if row:
                        model_name = row.model
                        if row.max_tokens:
                            output_tokens = int(row.max_tokens)
                finally:
                    db.close()
            except Exception as e:  # noqa: BLE001
                logger.debug("获取模型上下文窗口失败: %s", e)

        return clamp_input_budget(
            None,
            window=resolve_context_window(model_name),
            output_tokens=output_tokens,
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算文本的 token 数。

        中文约 1.5 字符/token，英文约 4 字符/token；取混合语言折中系数 2.5。
        """
        if not text:
            return 0
        return int(len(text) / 2.5)

    @staticmethod
    def _truncate_message(
        message: str, max_input_tokens: int, system_prompt: str = "",
    ) -> str:
        """截断用户消息使其适配模型上下文窗口。

        为 system prompt 和工具定义预留空间，用户消息最多占用 70% 的上下文预算。
        """
        system_tokens = SkillExecutionService._estimate_tokens(system_prompt)
        # 额外预留 8000 tokens 给工具定义 / function schema
        # （AgentScope toolkit 可能包含大量技能描述）
        reserved_for_tools = 8000
        available_tokens = max_input_tokens - system_tokens - reserved_for_tools
        if available_tokens < 1000:
            available_tokens = 1000

        # 用户消息最多占上下文预算的 70%
        max_user_tokens = int(max_input_tokens * 0.7)
        effective_limit = min(available_tokens, max_user_tokens)

        estimated = SkillExecutionService._estimate_tokens(message)
        if estimated <= effective_limit:
            return message

        # 按字符比例截断（2.5 字符/token 估算）
        max_chars = int(effective_limit * 2.5)
        truncated = message[:max_chars]
        return truncated + "\n\n[注：因输入过长，后续内容已被自动截断]"

    # ─── 指标记录 ─────────────────────────────────────────────────────────

    def _record_metrics(self, skill_id: str, success: bool, elapsed: float) -> None:
        """记录技能执行指标到 ai_skill_metrics 表（滑动平均）。"""
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
                logger.debug(
                    "skill metrics recorded: %s (success=%s, elapsed=%.3fs)",
                    skill_id, success, elapsed,
                )

                # 自动进化：若该技能开启了 is_auto_enabled，则执行进化评估与写回
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
                    logger.warning(
                        "auto evolution skipped for %s: %s", skill_id, exc
                    )
            except Exception as exc:
                logger.warning("failed to record metrics for %s: %s", skill_id, exc)
                db.rollback()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("metrics recording error: %s", exc)

    # ─── Skill 加载 ─────────────────────────────────────────────────────────

    async def _load_skill(self, skill_name: str) -> dict[str, Any] | None:
        """加载 Skill：优先级为 数据库 skill_markdown > workspace > data/skills/{package_id}/SKILL.md

        说明：数据库中保存的 SKILL.md 内容（skill_markdown）优先于文件系统，
        确保前端编辑并保存后的内容能即时生效。
        """
        # 方式 0：优先使用数据库中保存的 SKILL.md 内容
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
            logger.debug("从数据库加载 SKILL.md 失败，回退文件系统: %s, error: %s", skill_name, e)

        # 方式 1：从 AgentScope workspace 获取
        try:
            skill = await self.workspace.get_skill(skill_name)
            if skill and skill.get("markdown"):
                skill.setdefault("allowed_tools", parse_allowed_tools(skill.get("markdown", "")))
                skill["source"] = "workspace"
                return skill
        except Exception as e:
            logger.debug("workspace.get_skill failed for %s: %s", skill_name, e)

        # 方式 2：直接从 data/skills/{package_id}/SKILL.md 读取
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
                logger.error("读取 SKILL.md 失败: %s, error: %s", md_path, e)

        return None

    # ─── Toolkit 构建 ───────────────────────────────────────────────────────

    def _build_toolkit(
        self,
        extra_tools: list[ToolBase] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> Any:
        """构建 Toolkit（带缓存）。

        Args:
            extra_tools: 额外追加的工具
            allowed_tools: 白名单工具名列表。若提供，仅包含这些工具；
                          若为 None（未声明 allowed-tools），回退全量。
        """
        from agentscope.tool import Toolkit

        all_tools = list(self.tool_manager.tools.values())
        if extra_tools:
            all_tools.extend(extra_tools)

        if allowed_tools:
            allowed_set = set(allowed_tools)
            tools = [t for t in all_tools if getattr(t, "name", "") in allowed_set]
            cache_key = ",".join(sorted(allowed_set))
            logger.info(
                "toolkit filtered by allowed-tools: %d/%d tools",
                len(tools), len(all_tools),
            )
        else:
            tools = all_tools
            cache_key = "__all__"

        # 命中缓存则直接返回（无 extra_tools 时）
        if cache_key in self._cached_toolkits and not extra_tools:
            logger.debug("toolkit cache hit: key=%s", cache_key)
            return self._cached_toolkits[cache_key]

        # 使用 data/skills 目录作为 skill loader 源（缓存 loader 避免重复扫描）
        if self._cached_skill_loader is None:
            from agentscope.skill import LocalSkillLoader
            skills_dir = str(_SKILLS_BASE)
            self._cached_skill_loader = LocalSkillLoader(directory=skills_dir, scan_subdir=True)
            logger.info("skill loader 已缓存 (skills_dir=%s)", skills_dir)

        toolkit = Toolkit(tools=tools, skills_or_loaders=[self._cached_skill_loader])

        # 缓存 toolkit（无 extra_tools 时）
        if not extra_tools:
            self._cached_toolkits[cache_key] = toolkit

        return toolkit

    # ─── System Prompt ──────────────────────────────────────────────────────

    def _build_system_prompt(self, skill: dict, session_id: int | None, user_id: int | None) -> str:
        """构建 Agent 的 system prompt。"""
        parts = [
            "你是一个技能执行助手。请严格按照以下技能指令完成用户请求。",
            "如果需要使用工具，请先阅读技能指令了解可用工具和用法。",
            "",
            f"## 技能: {skill['name']}",
            skill.get("markdown", ""),
        ]
        if session_id:
            parts.append(f"\n当前会话 ID: {session_id}")
        if user_id:
            parts.append(f"当前用户 ID: {user_id}")
        return "\n".join(parts)

    # ─── 模型构建 ───────────────────────────────────────────────────────────

    def _build_model(self, model_id: int | None = None) -> Any:
        """构建 LLM 模型实例。

        优先级：
        1. 构造函数传入的 model_config
        2. 用户选择的 model_id（从 DB 查询 AiChatModel + AiApiKey）
        3. 数据库中第一个启用的模型
        4. 环境变量 fallback
        """
        from app.ai.strategy.factory_ext import build_model

        # 优先级 1：构造函数传入的 model_config
        if self.model_config:
            return build_model(self.model_config)

        # 优先级 2/3：从 DB 获取模型配置
        db_config = self._get_model_config_from_db(model_id)
        if db_config:
            return build_model(db_config)

        # 优先级 4：环境变量 fallback
        logger.warning("未找到数据库模型配置，使用环境变量 fallback")
        return build_model({
            "provider": "openai",
            "model": os.environ.get("DEFAULT_MODEL", "gpt-4o-mini"),
            "base_url": os.environ.get("OPENAI_BASE_URL", ""),
            "api_key_ref": "ENV:OPENAI_API_KEY",
        })

    def _get_model_config_from_db(self, model_id: int | None = None) -> dict | None:
        """从数据库获取模型配置，返回 factory_ext.build_model 所需的 dict。

        当 model_id 为空时，优先选取 is_default=True 且 type=1（文本）的模型，
        其次取任意启用的文本模型，避免误选 embedding / rerank 模型。
        """
        from app.db.database import SessionLocal
        from app.models.ai.ai_api_key import AiApiKey, AiChatModel

        db = SessionLocal()
        try:
            if model_id:
                # 用户指定模型
                model = db.query(AiChatModel).filter(
                    AiChatModel.id == model_id,
                    AiChatModel.status == 1,
                ).first()
            else:
                # 默认：优先 is_default=True 的文本模型（type=1）
                model = db.query(AiChatModel).filter(
                    AiChatModel.status == 1,
                    AiChatModel.type == 1,
                    AiChatModel.is_default == True,  # noqa: E712
                ).first()
                if not model:
                    # 其次取任意启用的文本模型
                    model = db.query(AiChatModel).filter(
                        AiChatModel.status == 1,
                        AiChatModel.type == 1,
                    ).order_by(AiChatModel.sort.desc(), AiChatModel.id.asc()).first()

            if not model:
                return None

            # 获取关联的 API Key
            api_key = db.query(AiApiKey).filter(
                AiApiKey.id == model.key_id,
                AiApiKey.status == 1,
            ).first()
            if not api_key:
                logger.warning("模型 %s 关联的 API Key 不存在或已禁用", model.name)
                return None

            raw_url = (api_key.url or "").rstrip("/")
            # OpenAI 兼容协议自动补全 /v1 路径后缀
            platform_lower = (api_key.platform or "openai").lower()
            _OPENAI_COMPATIBLE = {
                "openai", "智谱", "讯飞", "百度", "gpustack", "gpu_stack",
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
            # max_tokens 是 completion 上限，需留空间给 input；
            # 数据库若存了等于/接近上下文窗口的值会导致 400，这里做安全截断。
            # 原硬编码 8192 未考虑 input 侧预算（AgentTeam 的 27648），
            # 27648 + 8192 = 35840 > qwen3-32b 窗口 32768，必然报错。
            # 改为按「窗口 - 安全余量 - input 预算」动态 clamp。
            if model.max_tokens:
                from app.constants.llm_tokens import (
                    clamp_input_budget,
                    clamp_output_tokens,
                    resolve_context_window,
                )

                _window = resolve_context_window(getattr(model, "model", None))
                # skill 模式的 input 预算与 AgentTeam 保持一致口径，
                # 二者与 output 共享同一个上下文窗口，必须联合约束。
                _input_budget = clamp_input_budget(
                    None, window=_window, output_tokens=int(model.max_tokens)
                )
                config["max_tokens"] = clamp_output_tokens(
                    model.max_tokens,
                    window=_window,
                    input_budget=_input_budget,
                )

            logger.info("使用数据库模型: %s (model=%s, platform=%s)", model.name, model.model, api_key.platform)
            return config
        except Exception as e:
            logger.error("从数据库获取模型配置失败: %s", e)
            return None
        finally:
            db.close()

    async def _run_agent(
        self,
        skill_name: str,
        system_prompt: str,
        model: Any,
        toolkit: Any,
        user_message: str,
        execution_id: str | None = None,
    ) -> AsyncGenerator[SkillEvent, None]:
        """创建并运行 Agent，将 AgentEvent 映射为 SkillEvent 并记录日志。"""
        from agentscope.agent import Agent
        from agentscope.message import UserMsg
        from agentscope.event import (
            TextBlockDeltaEvent,
            ThinkingBlockStartEvent,
            ThinkingBlockDeltaEvent,
            ThinkingBlockEndEvent,
            ToolCallStartEvent,
            ToolCallDeltaEvent,
            ToolCallEndEvent,
            ToolResultTextDeltaEvent,
            ToolResultDataDeltaEvent,
            ReplyEndEvent,
        )

        agent = Agent(
            name=skill_name,
            system_prompt=system_prompt,
            model=model,
            toolkit=toolkit,
        )

        user_msg = UserMsg(name="user", content=user_message)
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        current_tool_name = ""
        current_tool_args = ""  # 累积工具调用参数的增量 JSON 片段（ToolCallDeltaEvent.delta）

        async for event in agent.reply_stream(inputs=user_msg):
            if isinstance(event, ThinkingBlockStartEvent):
                # 思考块开始 —— 仅记录日志，无需下发 SSE 事件
                logger.debug("[Skill Execution] thinking block start: %s", event.block_id)

            elif isinstance(event, ThinkingBlockDeltaEvent):
                # 思考内容增量 —— 作为 thinking 事件流式下发
                delta = event.delta or ""
                if not delta.strip():
                    continue
                thinking_parts.append(delta)
                self.event_service.record(
                    event_type=ExecutionEventType.THINKING,
                    content={"delta": delta},
                    source="agent",
                    source_id=skill_name,
                )
                yield SkillEvent(type="thinking", data={"content": delta})

            elif isinstance(event, ThinkingBlockEndEvent):
                # 思考块结束 —— 仅记录日志
                logger.debug("[Skill Execution] thinking block end: %s", event.block_id)

            elif isinstance(event, TextBlockDeltaEvent):
                # 累积到 text_parts，保证最终结果（done 事件）文本格式完整
                text_parts.append(event.delta)
                # 纯空白 delta（如 "\n"）不记录/不下发，避免产生噪声事件（前端亦会过滤空白 chunk）
                if not event.delta.strip():
                    continue
                # 记录文本事件
                self.event_service.record(
                    event_type=ExecutionEventType.TEXT,
                    content={"delta": event.delta},
                    source="agent",
                    source_id=skill_name,
                )
                yield SkillEvent(type="text", data={"content": event.delta})
            elif isinstance(event, ToolCallStartEvent):
                # 工具名在 tool_call_name 字段（非 name）
                current_tool_name = getattr(event, "tool_call_name", "") or ""
                current_tool_args = ""  # 重置参数累积器
                # 工具调用前，先发送一个 thinking 事件表示 AI 正在思考使用什么工具
                if current_tool_name:
                    yield SkillEvent(type="thinking", data={
                        "content": f"正在考虑使用工具：{current_tool_name}",
                        "step": 1,
                    })
            elif isinstance(event, ToolCallDeltaEvent):
                # 工具调用参数以增量 JSON 片段下发，需累积后在 ToolCallEndEvent 时解析
                current_tool_args += getattr(event, "delta", "") or ""
            elif isinstance(event, ToolCallEndEvent):
                # 解析累积的参数片段为字典
                tool_input: dict = {}
                if current_tool_args.strip():
                    try:
                        parsed_args = json.loads(current_tool_args)
                        if isinstance(parsed_args, dict):
                            tool_input = parsed_args
                    except (json.JSONDecodeError, ValueError):
                        tool_input = {}
                # 记录工具调用事件
                self.event_service.record(
                    event_type=ExecutionEventType.TOOL_CALL,
                    content={
                        "tool_name": current_tool_name,
                        "input": tool_input,
                    },
                    source="agent",
                    source_id=skill_name,
                )
                yield SkillEvent(type="tool_call", data={
                    "tool_name": current_tool_name,
                    "input": tool_input,
                })
            elif isinstance(event, ToolResultTextDeltaEvent):
                # 工具文本结果（delta 字段）；二进制结果 ToolResultDataDeltaEvent 无 delta，此处不处理
                result_delta = getattr(event, "delta", "") or ""
                if not result_delta.strip():
                    continue
                # 记录工具结果事件
                self.event_service.record(
                    event_type=ExecutionEventType.TOOL_RESULT,
                    content={
                        "tool_name": current_tool_name,
                        "delta": result_delta,
                        "state": "success",
                    },
                    source="agent",
                    source_id=skill_name,
                )
                yield SkillEvent(type="tool_result", data={
                    "tool_name": current_tool_name,
                    "delta": result_delta,
                    "state": "success",
                })
            elif isinstance(event, ToolResultDataDeltaEvent):
                # 二进制工具结果（如 DocumentGenerator 生成的文件字节流）
                # 不下发原始字节（前端无法渲染），仅记录元数据
                media_type = getattr(event, "media_type", "") or ""
                data_b64 = getattr(event, "data", None)
                url = getattr(event, "url", None)
                data_size = len(data_b64) if data_b64 else 0
                if data_size or url:
                    self.event_service.record(
                        event_type=ExecutionEventType.TOOL_RESULT,
                        content={
                            "tool_name": current_tool_name,
                            "media_type": media_type,
                            "data_size": data_size,
                            "url": url,
                            "state": "success",
                            "binary": True,
                        },
                        source="agent",
                        source_id=skill_name,
                    )
                    # 不 yield 二进制内容，避免 SSE 传输过大
            elif isinstance(event, ReplyEndEvent):
                final_text = "".join(text_parts)
                # 记录技能结果事件
                self.event_service.record(
                    event_type=ExecutionEventType.SKILL_RESULT,
                    content={"result": final_text},
                    source="agent",
                    source_id=skill_name,
                )
                # ── 扫描产物文件，发射 artifact 事件 ──
                from app.ai.skills.artifact_store import scan_artifacts
                if execution_id:
                    artifacts = scan_artifacts(execution_id)
                    for art in artifacts:
                        self.event_service.record(
                            event_type=ExecutionEventType.ARTIFACT,
                            content={
                                "file_id": art.file_id,
                                "filename": art.filename,
                                "size_bytes": art.size_bytes,
                                "mime_type": art.mime_type,
                            },
                            source="skill",
                            source_id=skill_name,
                        )
                        yield SkillEvent(type="artifact", data={
                            "file_id": art.file_id,
                            "filename": art.filename,
                            "size_bytes": art.size_bytes,
                            "mime_type": art.mime_type,
                        })
                yield SkillEvent(type="done", data={"result": final_text})
