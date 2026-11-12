"""SuperAgent 引擎包。

目录结构（Task 2-4 完成后）：
├── __init__.py
├── engine/
│   ├── core.py          # SuperAgentEngine + Repository 接口 + 5 个 Part 实现
│   └── __init__.py
├── tools/               # Task 2 — MCP 对接
│   ├── mcp_config.py
│   ├── mcp_adapter.py
│   └── toolkit.py
├── executor/            # Task 4 — Worker + Transient Retry
│   ├── report.py
│   └── transient.py
├── repository.py        # Task 3 — SQLAlchemy Repository 实现
├── policy.py            # Task 3 — PolicyService + AdmissionTable
├── assessor.py          # Task 3 — AssessorService
├── effects.py           # Task 3 — EffectQueue Durable 队列
└── (Task 6+ 填充 sources/, worker/, outbox.py)
"""
from __future__ import annotations

# Policy
from .policy import PolicyService, AdmissionRule, AssessmentOutcome

# Assessor
from .assessor import AssessorService, Candidate

# Repository
from .repository import SuperAgentRepository

# Effects
from .effects import EffectQueue, EFFECT_KINDS, EFFECT_CONCURRENCY

# Engine
from .engine.core import (
    SuperAgentEngine, Repository,
    IntakePart, EvalsPart, TicketsPart, AssignmentsPart, RepliesPart,
)

__all__ = [
    # Policy
    "PolicyService", "AdmissionRule", "AssessmentOutcome",
    # Assessor
    "AssessorService", "Candidate",
    # Repository
    "SuperAgentRepository",
    # Effects
    "EffectQueue", "EFFECT_KINDS", "EFFECT_CONCURRENCY",
    # Engine
    "SuperAgentEngine", "Repository",
    "IntakePart", "EvalsPart", "TicketsPart", "AssignmentsPart", "RepliesPart",
]
