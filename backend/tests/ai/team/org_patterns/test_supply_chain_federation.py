# -*- coding: utf-8 -*-
"""跨组织供应链协同（联邦式）：越界字段被网关拒绝 + 协调者只拿白名单字段。"""
import asyncio

from app.ai.team.org_patterns import supply_chain_federation


def test_cross_boundary_denied():
    out = asyncio.run(supply_chain_federation.run(mock=True, probe_boundary=True))
    denied = out["trace"].kinds("gateway_denied")
    assert any(d["domain"] == "logistics" and "cost_price" in d["denied"] for d in denied)


def test_coordinator_context_whitelist_only():
    out = asyncio.run(supply_chain_federation.run(mock=True))
    calls = out["trace"].kinds("gateway_call")
    assert {c["domain"] for c in calls} == {"erp", "logistics", "ads"}
    for c in calls:
        allowed = {"erp": {"capacity", "lead_time"},
                   "logistics": {"quote", "transit_time"},
                   "ads": {"budget_spent"}}
        assert set(c["fields"]) <= allowed[c["domain"]]
    assert out["final"]