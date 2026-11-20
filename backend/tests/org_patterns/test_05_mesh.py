# -*- coding: utf-8 -*-
"""范例05 对等网状：广播全员可见 + 发言预算/轮次上限 + 无中心汇总者。"""
import asyncio

from conftest import load_example

PLATFORMS = {"amazon_ops", "shopee_ops", "tiktok_ops", "indie_ops"}


def test_mesh_broadcast_visibility_and_budget():
    out = asyncio.run(load_example("05_mesh_multiplatform.py").run_demo(mock=True))
    broadcasts = out["trace"].kinds("broadcast")
    assert broadcasts
    for b in broadcasts:
        assert set(b["visible_to"]) == PLATFORMS  # 每条发言全员可见
    speeches = out["trace"].kinds("speech")
    assert len(speeches) <= 16                   # 发言预算
    rounds = {s["round"] for s in speeches}
    assert max(rounds) <= 4


def test_mesh_final_is_board_summary_not_agent_verdict():
    out = asyncio.run(load_example("05_mesh_multiplatform.py").run_demo(mock=True))
    # final 为消息板终态的代码拼接：四平台立场均在，且无裁判/汇总 Agent 出场
    for p in PLATFORMS:
        assert p in out["final"]
    speeches = out["trace"].kinds("speech")
    assert {s["platform"] for s in speeches} <= PLATFORMS
    assert max(s["round"] for s in speeches) < 4  # mock 第 3 轮无新实质消息提前终止