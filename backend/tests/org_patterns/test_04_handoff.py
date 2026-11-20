# -*- coding: utf-8 -*-
"""范例04 交接式：只传摘要不传全量对话 + 交接跳数上限。"""
import asyncio

from .conftest import load_example


def test_handoff_summary_only_and_hops():
    out = asyncio.run(load_example("04_handoff_support.py").run_demo(mock=True))
    hops = out["trace"].kinds("handoff")
    assert [h["to"] for h in hops] == ["logistics_en", "returns_zh"]
    for fm in out["trace"].kinds("expert_first_msg"):
        assert fm["content"].startswith("<handover>")
        assert "西语客户完整对话" not in fm["content"]  # 前专家全量对话标记串不得出现
    assert len(hops) <= 3