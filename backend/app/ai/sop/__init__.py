"""SOP / Goal 共享编排包。

spec: docs/design/sop-assistant-mode-design.md §4

- ``schemas``：SOPDefinition / SOPStepDef / SOPRunState 等数据契约
- ``engine``：SOPEngine 主干顺序编排（验收、重试、挂起/恢复）
- ``goal_step``：``loop=goal`` 单步内部的"执行→验证→修订"微循环
- ``agent``：SOPAgent，装配真实 LLM 与事件总线，对齐 ResearchAgent 形态
"""
from __future__ import annotations

from .schemas import (
    SOPDefinition,
    SOPPhase,
    SOPRunState,
    SOPStepDef,
    StepRuntimeState,
    Verdict,
    VerifierType,
    LoopMode,
    init_run_state,
)
from .engine import SOPEngine
from .goal_step import GoalStep

__all__ = [
    "SOPDefinition",
    "SOPPhase",
    "SOPRunState",
    "SOPStepDef",
    "StepRuntimeState",
    "Verdict",
    "VerifierType",
    "LoopMode",
    "init_run_state",
    "SOPEngine",
    "GoalStep",
]
