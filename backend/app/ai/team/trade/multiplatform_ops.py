# -*- coding: utf-8 -*-
"""多平台运营协同（对等网状，共享消息板 + 自建广播循环）。

模式语义：无中心节点，成员互见发言并按需响应，目标是状态一致而非裁决。
共享消息板为普通 list，轮转发言（每轮每人一次，增量喂给当前 Agent）；
连续一轮无新实质消息或 max_rounds=4 终止；总发言预算 16 条。
final 为消息板终态的代码拼接——没有汇总 Agent（与辩论/Supervisor 的本质区别）。

对应团队：xborder-mesh-multiplatform（mode=msghub）。
离线运行：python scripts/run_org_pattern.py multiplatform_ops --mock
"""
from __future__ import annotations

from typing import Optional

from agentscope.message import UserMsg
from agentscope.tool import FunctionTool

from app.ai.team.trade.scaffolding import (
    Trace,
    make_agent,
    make_model,
    mock_platform_price,
    mock_platform_stock,
)

PLATFORMS = ["xborder-amazon-ops", "xborder-shopee-ops", "xborder-tiktok-ops", "xborder-indie-ops"]
MAX_ROUNDS = 4
SPEECH_BUDGET = 16
TOPIC = "TikTok 闪购降价 15%，各平台同步应对"


def _substantive(text: str) -> bool:
    """实质消息判定：空话/客套不上消息板（防广播风暴）。"""
    return bool(text) and "无新实质" not in text and "无补充" not in text


async def run(mock: bool, model_id: Optional[int] = None) -> dict:
    """运行多平台运营协同团队，返回 {"final": str, "trace": Trace}。"""
    trace = Trace()

    agents = {}
    for p in PLATFORMS:
        script = [
            {"tool_calls": [{"name": "mock_platform_stock", "input": {"platform": p}}]},
            f"{p} 响应：已核库存 320 件，跟进降价 15% 对齐 TikTok 闪购价，避免跨平台比价流失。",
            f"{p} 确认：价格已对齐并设置库存预警（低于 50 件自动限购），与其他平台保持一致。",
            "本轮无新实质补充。",
        ] if mock else None
        agents[p] = make_agent(
            p, f"你是 {p} 平台运营，读到相关库存/价格变动必须回应，每轮最多 1 条发言，"
               "目标是多平台策略一致；无新信息时回复『本轮无新实质补充。』",
            tools=[FunctionTool(mock_platform_stock), FunctionTool(mock_platform_price)],
            max_iters=6, model=make_model(script, name=p, model_id=model_id),
        )

    # 共享消息板：每条实质发言全员可见
    board: list[dict] = [{"msg_id": 0, "platform": "xborder-tiktok-ops", "round": 0, "text": TOPIC}]
    trace.record("broadcast", msg_id=0, visible_to=list(PLATFORMS))
    cursors = {p: 0 for p in PLATFORMS}  # 各平台已读位置（增量喂入）
    budget = SPEECH_BUDGET
    next_id = 1

    for n in range(1, MAX_ROUNDS + 1):
        new_this_round = 0
        for p in PLATFORMS:
            if budget <= 0:
                break
            increment = board[cursors[p]:]
            history = "\n".join(f"[{m['platform']}] {m['text']}" for m in increment) or "（无新消息）"
            msg = await agents[p].reply(UserMsg(name="board", content=(
                f"议题：{TOPIC}\n第 {n} 轮，消息板增量：\n{history}\n请回应（每轮最多 1 条）。")))
            text = msg.get_text_content() or ""
            cursors[p] = len(board)
            budget -= 1
            trace.record("speech", platform=p, round=n)
            if _substantive(text):
                board.append({"msg_id": next_id, "platform": p, "round": n, "text": text})
                trace.record("broadcast", msg_id=next_id, visible_to=list(PLATFORMS))
                next_id += 1
                new_this_round += 1
        if new_this_round == 0 or budget <= 0:
            break  # 连续一轮无新实质消息 / 预算耗尽 → 终止

    # final = 消息板终态摘要（代码拼接，无中心汇总者）
    lines = []
    for p in PLATFORMS:
        last = next((m["text"] for m in reversed(board) if m["platform"] == p), "（未发言）")
        lines.append(f"[{p}] {last}")
    final = "多平台同步终态（消息板摘要，无中心裁决）：\n" + "\n".join(lines)
    trace.record("final", text=final)
    return {"final": final, "trace": trace}


PATTERN = {
    "team_code": "xborder-mesh-multiplatform",
    "name": "多平台运营协同",
    "mode": "msghub",
    "sample_input": TOPIC,
    "run": run,
}