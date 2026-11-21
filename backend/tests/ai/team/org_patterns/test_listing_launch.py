# -*- coding: utf-8 -*-
"""跨境新品上架统筹（Supervisor-Worker）：4 成员均被派活、最终含 GO/NO-GO。"""
import asyncio

from app.ai.team.trade import listing_launch

WORKERS = {"xborder-product-picker", "xborder-listing-writer",
           "xborder-compliance-checker", "xborder-pricing-analyst"}


def test_supervisor_mock_semantics():
    out = asyncio.run(listing_launch.run(mock=True))
    dispatched = {t["member"] for t in out["trace"].kinds("dispatch")}
    assert dispatched == WORKERS
    assert "GO" in out["final"] or "NO-GO" in out["final"]


def test_supervisor_member_done_and_final_trace():
    out = asyncio.run(listing_launch.run(mock=True))
    done = {t["member"] for t in out["trace"].kinds("member_done")}
    assert done == WORKERS
    assert out["trace"].kinds("final")