# -*- coding: utf-8 -*-
"""外贸询盘报价（流水线）：步骤严格顺序 + verifier 重试上限。"""
import asyncio

from app.ai.team.trade import inquiry_pipeline


def test_pipeline_order_and_retry():
    out = asyncio.run(inquiry_pipeline.run(mock=True))
    order = [t["subject"] for t in out["trace"].kinds("step_done")]
    assert order == ["解析询盘", "报价", "合同条款", "跟单催单"]


def test_pipeline_verifier_retry_capped():
    out = asyncio.run(inquiry_pipeline.run(mock=True, inject_bad_rate=True))
    retries = [t for t in out["trace"].kinds("step_retry") if t["subject"] == "报价"]
    assert 1 <= len(retries) <= 3
    order = [t["subject"] for t in out["trace"].kinds("step_done")]
    assert order == ["解析询盘", "报价", "合同条款", "跟单催单"]