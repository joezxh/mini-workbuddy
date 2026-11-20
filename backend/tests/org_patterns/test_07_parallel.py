# -*- coding: utf-8 -*-
"""范例07 并行聚合：时间戳证真并发 + 单路失败占位继续。"""
import asyncio
import time

from .conftest import load_example


def test_real_concurrency_by_timestamps():
    mod = load_example("07_parallel_budget.py")  # 首次 import 耗时不计入并发计时
    t0 = time.monotonic()
    out = asyncio.run(mod.run_demo(mock=True))
    elapsed = time.monotonic() - t0
    starts = sorted(t["at"] for t in out["trace"].kinds("worker_start"))
    assert len(starts) == 3
    assert starts[-1] - starts[0] < 0.2          # 三路几乎同时启动
    assert elapsed < 1.5                          # sleep 1s×3 串行会 ≥3s
    assert len(out["trace"].kinds("worker_done")) == 3
    assert out["final"]


def test_single_failure_continues():
    mod = load_example("07_parallel_budget.py")
    out = asyncio.run(mod.run_demo(mock=True, fail_channel="roi_meta"))
    failed = out["trace"].kinds("worker_failed")
    assert failed and failed[0]["channel"] == "roi_meta"
    assert len(out["trace"].kinds("worker_done")) == 2  # 其余两路照常完成
    assert "roi_meta" in out["final"] or "占位" in out["final"]  # 聚合含失败说明