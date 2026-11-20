# -*- coding: utf-8 -*-
"""范例07 并行聚合 —— 多渠道投流预算测算（asyncio.gather 真并发 + 聚合 Agent）。

模式语义：拆分代码写死、三路无依赖扇出真并发（时间戳可证），单路失败→占位
结果继续聚合（对齐 NodeErrorPolicy.CONTINUE）；与 Supervisor 区别是拆分不由
leader 运行时决定，与流水线区别是无先后依赖。每路 asyncio.wait_for(60) 超时。

运行：python 07_parallel_budget.py --mock
"""
from __future__ import annotations

import asyncio
import json
import time

from agentscope.message import UserMsg
from agentscope.tool import FunctionTool

from _common import Trace, make_agent, make_model, mock_channel_roi, run_cli

CHANNELS = ["roi_google", "roi_meta", "roi_tiktok"]
TOTAL_BUDGET = 10000.0


async def run_demo(mock: bool, fail_channel: str | None = None) -> dict:
    trace = Trace()

    workers = {}
    for ch in CHANNELS:
        script = [
            {"tool_calls": [{"name": "mock_channel_roi", "input": {
                "channel": ch, "budget": round(TOTAL_BUDGET / 3, 2)}}]},
            f"{ch} 渠道测算完成：ROI 2.4，转化预期稳定，建议按测算占比分配预算。",
        ] if mock else None
        workers[ch] = make_agent(
            ch, f"你是 {ch} 渠道投放分析师，用 mock_channel_roi 测算 ROI 后输出渠道结论。",
            tools=[FunctionTool(mock_channel_roi)], max_iters=6,
            model=make_model(script, name=ch),
        )

    async def run_worker(ch: str) -> dict:
        trace.record("worker_start", channel=ch, at=time.monotonic())
        # 失败注入在协程层：工具异常会被 Agent 吞为错误 ToolResult 继续推理，
        # 不会传播到 reply，故在 worker 入口模拟渠道服务不可用
        if ch == fail_channel:
            raise RuntimeError(f"渠道 {ch} 测算服务不可用（演示注入）")
        task = UserMsg(name="user", content=(
            f"黑五总预算 ${TOTAL_BUDGET:.0f}，请测算 {ch} 渠道 ROI（按总额三分之一预算）。"))
        msg = await workers[ch].reply(task)
        trace.record("worker_done", channel=ch)
        return {"channel": ch, "conclusion": msg.get_text_content()}

    async def guarded(ch: str) -> dict:
        try:
            return await asyncio.wait_for(run_worker(ch), 60)
        except Exception as e:  # noqa: BLE001 —— 单路失败占位继续，不中断聚合
            trace.record("worker_failed", channel=ch, error=str(e))
            return {"channel": ch, "error": str(e), "placeholder": True}

    # 三路无依赖扇出：gather 真并发（mock_channel_roi 内 sleep 1s，串行会 ≥3s）
    results = await asyncio.gather(*[guarded(ch) for ch in CHANNELS])

    agg_text = (
        "预算分配方案：roi_google 40%（$4000）、roi_meta 30%（$3000）、roi_tiktok 30%（$3000）；"
        "综合预期 ROI 2.4。调优建议：每周复盘素材与转化，动态向高 ROI 渠道倾斜 10% 预算。"
    )
    if fail_channel:
        agg_text = (
            f"预算分配方案：{fail_channel} 测算失败，按占位结果聚合（暂配 0%，待服务恢复后补测）；"
            "其余两渠道各 50%（各 $5000），综合预期 ROI 2.4。调优建议：失败渠道恢复前冻结其预算。"
        )
    aggregator = make_agent(
        "budget_aggregator", "你是预算聚合师，汇总各渠道测算结果（含失败占位说明），输出分配方案与调优建议。",
        max_iters=4, model=make_model([agg_text] if mock else None, name="budget_aggregator"),
    )
    final_msg = await aggregator.reply(UserMsg(name="user", content=(
        "请汇总三渠道测算结果并输出预算分配方案：\n" + json.dumps(results, ensure_ascii=False))))
    final = final_msg.get_text_content() or ""
    trace.record("final", text=final)
    return {"final": final, "trace": trace}


if __name__ == "__main__":
    run_cli(run_demo)