"""SOP 编排的数据契约与运行时状态模型。

spec: docs/design/sop-assistant-mode-design.md §4.2（定义契约）、§5.1（状态机）。

本模块只定义结构，不含任何执行逻辑；执行见 ``engine.py`` 与 ``goal_step.py``。
字段与 agentscope ``SOPStep(subject, description, executor, verifier, max_attempts)``
一一对应，便于后续按需对齐上游实现。
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SOPPhase(str, Enum):
    """步骤 / 整流程所处阶段（§5.1 状态机）。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING = "AWAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerifierType(str, Enum):
    """步骤验收方式。"""

    AI = "ai"
    HUMAN = "human"
    NONE = "none"


class LoopMode(str, Enum):
    """步骤内部的迭代模式。"""

    NONE = "none"
    GOAL = "goal"


class SOPStepDef(BaseModel):
    """单个 SOP 步骤定义。

    ``description`` 只写**终点结果**（要交付什么），不写路线（怎么做），
    由 executor 自行规划实现路径。
    """

    subject: str
    description: str = ""
    executor_agent: str = "general"
    verifier_type: VerifierType = VerifierType.NONE
    verifier_agent: Optional[str] = None
    max_attempts: int = 3
    loop: LoopMode = LoopMode.NONE
    goal_max_iters: int = 5
    goal_max_retries: int = 3
    goal_verifier_reset_ctx: bool = True
    exec_mode: Literal["serial", "parallel"] = "serial"
    group_id: Optional[str] = None
    artifact_key: Optional[str] = None


class SOPDefinition(BaseModel):
    """SOP 流程定义。"""

    name: str
    description: str = ""
    steps: List[SOPStepDef] = Field(default_factory=list)
    source: str = "template"
    template_id: Optional[int] = None


class StepRuntimeState(BaseModel):
    """单步运行时状态（可序列化，随 SOPRunState 一起持久化）。"""

    index: int
    subject: str
    phase: SOPPhase = SOPPhase.PENDING
    attempt: int = 0
    max_attempts: int = 3
    verifier_type: str = VerifierType.NONE.value
    feedback: Optional[str] = None
    output: Optional[str] = None
    goal_iter: int = 0
    exec_mode: str = "serial"
    group_id: Optional[str] = None


class SOPRunState(BaseModel):
    """引擎整体运行状态。

    ``definition`` 以快照形式内联（§4.8）：恢复时以持久化的定义为准，
    避免模板被改后步骤数与状态错位。
    """

    definition: SOPDefinition
    steps: List[StepRuntimeState] = Field(default_factory=list)
    current_index: int = 0
    phase: SOPPhase = SOPPhase.PENDING
    handovers: List[Dict[str, str]] = Field(default_factory=list)


class Verdict(BaseModel):
    """验收结论。"""

    passed: bool
    message: str = ""


def init_run_state(definition: SOPDefinition) -> SOPRunState:
    """按定义初始化运行状态（每步 PENDING、attempt=0）。"""
    steps = [
        StepRuntimeState(
            index=i,
            subject=s.subject,
            max_attempts=s.max_attempts,
            verifier_type=s.verifier_type.value,
            exec_mode=s.exec_mode,
            group_id=s.group_id,
        )
        for i, s in enumerate(definition.steps)
    ]
    return SOPRunState(
        definition=definition,
        steps=steps,
        current_index=0,
        phase=SOPPhase.PENDING,
    )
