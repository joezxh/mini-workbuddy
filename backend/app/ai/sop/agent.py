"""SOPAgent — 把 SOPEngine 装配成 AgentScope Agent 接口。

spec: docs/design/sop-assistant-mode-design.md §4.1

形态对齐 ``ResearchAgent`` / ``SkillAgent``（``backend/app/ai/agent_factory.py``）：
实现 ``reply_stream(user_msg)``，yield ``{"type": ..., "data": ...}`` 事件 dict，
由 SSEBridge / ai_agent router 直接消费。

引擎本身不依赖 LLM：执行器与验收器是注入的异步函数；本模块提供基于
``app.ai.research.llm`` 的默认实现，测试可注入假函数完全离线驱动。
"""
from __future__ import annotations

from typing import AsyncGenerator, Awaitable, Callable, Optional

from loguru import logger

from .engine import ExecutorFn, SOPEngine, VerifierFn
from .schemas import SOPDefinition, SOPStepDef, Verdict, VerifierType

_PROMPT_EXECUTE = """你是标准作业流程（SOP）中的执行者。请完成当前这一步。

所属流程：{flow}
当前步骤：{subject}
交付标准（只描述终点结果）：{description}

上一步交接 / 用户原始输入：
{input_text}

要求：
1. 只输出本步骤的交付内容，不要复述流程、不要输出多余说明；
2. 交付内容必须直接回应「交付标准」，做到可验收；
3. 若输入不足以完成，基于领域常识给出最合理的版本并说明假设。
"""

_PROMPT_VERIFY = """你是标准作业流程（SOP）中的步骤验收人。

步骤：{subject}
交付标准：{description}

待验收的交付内容：
{output}

请判断交付内容是否满足交付标准。只输出如下 JSON，不要任何额外文字：
{{"passed": true, "message": "简短验收意见（不通过时写明具体缺口）"}}
"""


class SOPAgent:
    """SOP 流程 Agent。"""

    def __init__(
        self,
        db,
        definition: SOPDefinition,
        model_id: Optional[int] = None,
        name: Optional[str] = None,
        state_json: Optional[str] = None,
        executor: Optional[ExecutorFn] = None,
        verifier: Optional[VerifierFn] = None,
    ) -> None:
        self._db = db
        self._definition = definition
        self._model_id = model_id
        self.name = name or definition.name or "SOP 助手"
        self._state_json = state_json
        self._executor = executor
        self._verifier = verifier
        self.last_state_json: Optional[str] = None
        # 引擎实例必须跨 resume 复用：人工验收挂起后，续跑靠的是同一个
        # SOPEngine 的运行时状态，每次重建会导致流程从头重跑。
        self._engine: Optional[SOPEngine] = None
        # 记住首轮用户输入：resume 时 reply_stream 收不到用户消息
        self._last_user_input: str = ""

    # ── Agent 接口 ─────────────────────────────────────────────────────────

    async def reply_stream(
        self,
        user_msg,
        execution_id: str = "",
        resume: Optional[dict] = None,
    ) -> AsyncGenerator[dict, None]:
        """运行 SOP 并 yield 事件。

        :param user_msg: 用户消息（经 ``text_of`` 提取纯文本）
        :param execution_id: 执行标识，随 ``completed`` 事件回传
        :param resume: 人工验收答复 ``{"confirmed": bool, "message": str}``，
            用于从 AWAITING 挂起处续跑
        """
        from app.ai.msg_utils import text_of

        # HITL 恢复路径：resume_hitl 以 inputs=None 调用，沿用首轮输入
        if user_msg is not None:
            self._last_user_input = text_of(user_msg)

        engine = self._build_engine()
        async for event in engine.reply_stream(
            user_input=self._last_user_input, resume=resume, execution_id=execution_id
        ):
            yield event

        # 保留末态供上层持久化（刷新/重入恢复，§4.8）
        self.last_state_json = engine.snapshot()

    @property
    def definition(self) -> SOPDefinition:
        """当前生效的流程定义。

        引擎创建前返回构造时传入的定义；创建后以引擎实际使用的为准——
        恢复场景下引擎用的是快照内联的定义，可能与传入值不同（§4.8）。
        """
        if self._engine is not None:
            return self._engine.definition
        return self._definition

    @property
    def run_state(self) -> Optional[dict]:
        """当前运行状态快照（供前端持久化 ``sopRun``，§4.8 / §5.3）。

        引擎尚未创建（未开始执行）时返回 None。
        """
        if self._engine is None:
            return None
        state = self._engine.state
        return {
            "definition": state.definition.model_dump(mode="json"),
            "phase": state.phase.value,
            "steps": [s.model_dump(mode="json") for s in state.steps],
            "runStateJson": self._engine.snapshot(),
        }

    # ── 装配 ───────────────────────────────────────────────────────────────

    def _build_engine(self) -> SOPEngine:
        """构造并缓存引擎；恢复场景以快照内联的定义为准。"""
        if self._engine is not None:
            return self._engine

        executor = self._executor or self._default_executor
        verifier = self._verifier or self._default_verifier
        if self._state_json:
            self._engine = SOPEngine.restore(self._state_json, executor, verifier)
        else:
            self._engine = SOPEngine(self._definition, executor, verifier)
        return self._engine

    async def _default_executor(self, step: SOPStepDef, input_text: str) -> str:
        """默认执行器：一步一次 LLM 调用。"""
        from app.ai.research.llm import llm_complete

        prompt = _PROMPT_EXECUTE.format(
            flow=self._definition.name,
            subject=step.subject,
            description=step.description or step.subject,
            input_text=input_text or "（无上游输入）",
        )
        return await llm_complete(prompt, model_id=self._model_id)

    async def _default_verifier(self, step: SOPStepDef, output: str) -> Verdict:
        """默认 AI 验收器：LLM 输出 ``{passed, message}`` JSON。

        验收器解析失败时**放行并留痕**（记为通过 + feedback 说明），而非判失败：
        LLM 偶发不严格遵循 JSON 不该让整个 SOP 卡死或耗尽 attempt。
        """
        from app.ai.research.llm import llm_json

        if step.verifier_type == VerifierType.NONE:
            return Verdict(passed=True, message="")

        prompt = _PROMPT_VERIFY.format(
            subject=step.subject,
            description=step.description or step.subject,
            output=output or "（空）",
        )
        try:
            raw = await llm_json(prompt, model_id=self._model_id)
            if isinstance(raw, dict):
                return Verdict(
                    passed=bool(raw.get("passed", False)),
                    message=str(raw.get("message", "")),
                )
            raise ValueError(f"验收器返回非 dict: {type(raw).__name__}")
        except Exception as exc:  # noqa: BLE001 - 验收解析失败不阻断主流程
            logger.warning(f"[SOP] 步骤「{step.subject}」验收解析失败，放行: {exc}")
            return Verdict(passed=True, message="验收器输出无法解析，已自动放行")


# 供 AgentFactory 使用的类型别名（保持与 engine 一致的注入契约）
__all__ = ["SOPAgent"]
