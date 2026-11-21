# -*- coding: utf-8 -*-
"""跨境电商 AgentTeam 组织模式实现（正式收编自 examples/trade）。

8 个模式与系统 AgentTeam（xborder-* 团队）一一对应，每个模式模块暴露统一入口：

    async def run(mock: bool, model_id: Optional[int] = None, **flags) -> dict
    # 返回 {"final": str, "trace": Trace}

- mock=True：FakeChatModel 离线确定性运行（零网络零 Key），失败注入开关见各模块 run 签名；
- mock=False + model_id：复用 app.ai.strategy.factory_ext 从 DB 构建真实模型（与 orchestrator 同源）；
- 环境变量兜底：OPENAI_BASE_URL/OPENAI_API_KEY 或 DASHSCOPE_API_KEY（离线 CLI 无 DB 场景）。

语义边界：UI 会话（/api/v1/ai-team/{team_id}/run、/chat SSE）统一走 orchestrator 的
Leader+ask_xxx 派活（不读 team.mode）；本子包实现的是各组织模式的**真实编排语义**
（层级/交接/网状/辩论/并行/联邦等），供编排层或会话侧显式调用，不改 orchestrator。

CLI：python scripts/run_org_pattern.py <pattern_key> --mock
种子注册：python scripts/seed_org_pattern_teams.py [--dry-run]
"""
from __future__ import annotations

from app.ai.team.trade import (
    ad_review_debate,
    budget_parallel,
    inquiry_pipeline,
    listing_launch,
    market_expansion,
    multiplatform_ops,
    supply_chain_federation,
    support_handoff,
)
from app.ai.team.trade.scaffolding import Trace

# 模式 → 实现注册表：key 为业务模块名，value 为各模块 PATTERN 元数据
# （team_code / name / mode / sample_input / run），team_code 与 seed_data.TEAMS 对齐。
PATTERNS = {
    "listing_launch": listing_launch.PATTERN,
    "market_expansion": market_expansion.PATTERN,
    "inquiry_pipeline": inquiry_pipeline.PATTERN,
    "support_handoff": support_handoff.PATTERN,
    "multiplatform_ops": multiplatform_ops.PATTERN,
    "ad_review_debate": ad_review_debate.PATTERN,
    "budget_parallel": budget_parallel.PATTERN,
    "supply_chain_federation": supply_chain_federation.PATTERN,
}

__all__ = [
    "PATTERNS",
    "Trace",
    "listing_launch",
    "market_expansion",
    "inquiry_pipeline",
    "support_handoff",
    "multiplatform_ops",
    "ad_review_debate",
    "budget_parallel",
    "supply_chain_federation",
]