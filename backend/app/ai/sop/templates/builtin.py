"""内置 SOP 模板 —— thinking / deep_research 的编排下沉骨架。

spec: docs/design/sop-assistant-mode-design.md §4.6

这两个模板是模式内置的编排主干：原 ``ThinkingAgent`` / ``ResearchOrchestrator``
的编排逻辑下沉到这里，统一由 ``SOPAgent`` 驱动；对外事件仍复用
``step`` / ``artifact`` 契约，前端渲染组件无需改动。
"""
from __future__ import annotations

from ..schemas import SOPDefinition, SOPStepDef
from .spec import SOPTemplateSpec

BUILTIN_THINKING = SOPTemplateSpec(
    id="builtin_thinking",
    name="深度思考",
    description="拆解问题结构 → 逐步推理 → 综合结论的结构化思考流程",
    tags=["内置", "思考", "推理", "thinking"],
    builtin=True,
    definition=SOPDefinition(
        name="深度思考",
        description="先理解问题结构，再生成思考步骤，逐步推理后综合结论",
        source="builtin:thinking",
        steps=[
            SOPStepDef(
                subject="理解问题",
                description="明确用户真正要解决的问题、已知条件、约束与成功标准",
                executor_agent="思考Agent",
                verifier_type="ai",
                max_attempts=2,
            ),
            SOPStepDef(
                subject="生成思考步骤",
                description="产出一份有序的思考步骤清单，覆盖解题所需的全部关键环节",
                executor_agent="思考Agent",
                verifier_type="ai",
                artifact_key="thinking_steps",
            ),
            SOPStepDef(
                subject="逐步推理",
                description="按思考步骤逐环展开论证，每环结论明确、前提可检验、无跳步",
                executor_agent="思考Agent",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=5,
            ),
            SOPStepDef(
                subject="综合结论",
                description="汇总推理过程，给出直接回应用户问题的最终结论与核心依据",
                executor_agent="思考Agent",
                verifier_type="none",
            ),
        ],
    ),
)

BUILTIN_RESEARCH = SOPTemplateSpec(
    id="builtin_research",
    name="深度研究",
    description="制定计划 → 并行检索 → 阅读摘录 → 综合报告的研究流程",
    tags=["内置", "研究", "检索", "research"],
    builtin=True,
    definition=SOPDefinition(
        name="深度研究",
        description="拆解子问题并检索取证，形成有来源支撑的结构化研究报告",
        source="builtin:research",
        steps=[
            SOPStepDef(
                subject="制定研究计划",
                description="产出不超过 8 个相互独立、可直接作为检索词的子问题清单",
                executor_agent="研究Agent",
                verifier_type="ai",
                artifact_key="researchPlan",
            ),
            SOPStepDef(
                subject="拆分子问题并行检索",
                description="逐个子问题给出检索所得的事实摘要与来源链接清单",
                executor_agent="研究Agent",
                verifier_type="none",
                exec_mode="parallel",
                group_id="subq",
                artifact_key="researchSources",
            ),
            SOPStepDef(
                subject="阅读与摘录",
                description="从来源中摘录与子问题直接相关的关键事实，标注来源与可信度",
                executor_agent="研究Agent",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="综合研究报告",
                description="产出含摘要、关键发现、详细分析与来源列表的完整研究报告",
                executor_agent="研究Agent",
                verifier_type="ai",
                artifact_key="researchReport",
            ),
        ],
    ),
)

BUILTIN_TEMPLATES = [BUILTIN_THINKING, BUILTIN_RESEARCH]
