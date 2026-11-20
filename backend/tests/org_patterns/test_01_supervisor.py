# -*- coding: utf-8 -*-
"""范例01 Supervisor-Worker：4 成员均被派活、最终含 GO/NO-GO。"""
import asyncio

from .conftest import load_example


def test_supervisor_mock_semantics():
    mod = load_example("01_supervisor_worker.py")
    out = asyncio.run(mod.run_demo(mock=True))
    dispatched = {t["member"] for t in out["trace"].kinds("dispatch")}
    assert dispatched == {"product_picker", "listing_writer", "compliance_checker", "pricing_analyst"}
    assert "GO" in out["final"] or "NO-GO" in out["final"]


def test_supervisor_member_done_and_final_trace():
    mod = load_example("01_supervisor_worker.py")
    out = asyncio.run(mod.run_demo(mock=True))
    done = {t["member"] for t in out["trace"].kinds("member_done")}
    assert done == {"product_picker", "listing_writer", "compliance_checker", "pricing_analyst"}
    assert out["trace"].kinds("final")