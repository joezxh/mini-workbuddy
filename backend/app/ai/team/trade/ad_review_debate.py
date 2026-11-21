# -*- coding: utf-8 -*-
"""广告策略评审（辩论/群聊，轮次循环 + 裁判结构化裁决）。

模式语义：正反方广播辩论（全员互见全量记录），裁判每轮末输出结构化裁决
{verdict: continue|final, reason, final_plan}；max_rounds=3 硬终局——第 3 轮
裁判仍 continue 时代码兜底强制 final。与对等网状区别：有裁判、有终局裁决。

对应团队：xborder-debate-adreview（mode=msghub）。
离线运行：python scripts/run_org_pattern.py ad_review_debate --mock
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from agentscope.message import UserMsg

from app.ai.team.trade.scaffolding import Trace, make_agent, make_model

MAX_ROUNDS = 3
TOPIC = "黑五网一：$5000 预算押注 TikTok 激进投放 vs Google 稳健投放"
_GSO = "GenerateStructuredOutput"  # 结构化输出经内置工具完成（同 inquiry_pipeline）


class Verdict(BaseModel):
    """裁判裁决（Agent.reply(structured_schema=Verdict)）。"""

    verdict: str  # continue | final
    reason: str = ""
    final_plan: str = ""


def _verdict_script(verdict: str, reason: str, final_plan: str = "") -> dict:
    return {"tool_calls": [{"name": _GSO, "input": {
        "verdict": verdict, "reason": reason, "final_plan": final_plan}}]}


async def run(mock: bool, model_id: Optional[int] = None,
              judge_always_continue: bool = False) -> dict:
    """运行广告策略评审团队，返回 {"final": str, "trace": Trace}。

    Args:
        mock: True 走离线 FakeChatModel。
        model_id: DB 模型配置 id（factory_ext 构建）。
        judge_always_continue: 失败注入开关——裁判恒 continue，验证代码兜底硬终局。
    """
    trace = Trace()

    pro_script = con_script = judge_script = None
    if mock:
        pro_script = [
            "正方（第1轮）：TikTok 黑五流量红利显著，$5000 集中押注短视频素材可博 3 倍 ROI，激进但值得。",
            "正方（第2轮）：回应反方——可预留 20% 做对照，但主预算仍应押 TikTok，错过窗口成本更高。",
            "正方（第3轮）：总结——接受 70/30 分仓折中，TikTok 主投 + Google 兜底，保留激进上限。",
        ]
        con_script = [
            "反方（第1轮）：TikTok 转化波动大且素材合规风险高，主张 Google 稳健投放 + 小步 A/B 测试。",
            "反方（第2轮）：回应正方——窗口期每年都有，本金亏完没有下次；建议 50/50 起步按 ROI 滚动加仓。",
            "反方（第3轮）：总结——接受 70/30 但要求 TikTok 侧设单日止损线与素材合规预审。",
        ]
        if judge_always_continue:
            judge_script = [_verdict_script("continue", f"第{n}轮双方仍有实质分歧，继续辩论。")
                            for n in range(1, MAX_ROUNDS + 1)]
        else:
            judge_script = [
                _verdict_script("continue", "第1轮双方立场清晰但论据未交锋，继续。"),
                _verdict_script("final", "第2轮已收敛到分仓+止损共识，可终局。",
                                "终审方案：TikTok $3500（70%）激进投放 + Google $1500（30%）稳健兜底；"
                                "TikTok 侧设单日止损 20% 与素材合规预审，按周 ROI 滚动调仓。"),
            ]

    agents = {
        "xborder-pro-creative": make_agent(
            "xborder-pro-creative", "你是广告评审正方，主张激进创意与高预算押注 TikTok；回应反方质疑并推进共识。",
            max_iters=4, model=make_model(pro_script, name="xborder-pro-creative", model_id=model_id)),
        "xborder-con-creative": make_agent(
            "xborder-con-creative", "你是广告评审反方，主张合规优先与小步测试；指出激进方案风险并回应正方。",
            max_iters=4, model=make_model(con_script, name="xborder-con-creative", model_id=model_id)),
    }
    judge = make_agent(
        "xborder-ad-judge", "你是广告策略评审裁判，每轮末输出结构化裁决；第 3 轮必须 final 并给出终审投放方案。",
        max_iters=4, model=make_model(judge_script, name="xborder-ad-judge", model_id=model_id))

    record: list[dict] = []  # 全量辩论记录，全员可见
    final = ""
    for n in range(1, MAX_ROUNDS + 1):
        trace.record("round", n=n)
        for role in ("xborder-pro-creative", "xborder-con-creative"):
            sees = [s["role"] for s in record]
            history = "\n".join(f"[{s['role']}] {s['text']}" for s in record) or "（暂无发言）"
            msg = await agents[role].reply(UserMsg(name="moderator", content=(
                f"议题：{TOPIC}\n当前第 {n} 轮。全量辩论记录：\n{history}\n请发表本轮观点。")))
            text = msg.get_text_content() or ""
            record.append({"role": role, "text": text})
            trace.record("speech", role=role, sees=sees)

        history = "\n".join(f"[{s['role']}] {s['text']}" for s in record)
        verdict_msg = await judge.reply(UserMsg(name="moderator", content=(
            f"议题：{TOPIC}\n第 {n}/{MAX_ROUNDS} 轮辩论记录：\n{history}\n"
            f"请输出结构化裁决（第 {MAX_ROUNDS} 轮必须 final）。")), structured_schema=Verdict)
        v = verdict_msg.structured_output or {}
        verdict = v.get("verdict", "continue")
        if n == MAX_ROUNDS and verdict != "final":
            verdict = "final"  # 代码兜底硬终局，不依赖裁判自觉
            trace.record("forced_final", n=n)
        trace.record("verdict", verdict=verdict, reason=v.get("reason", ""))
        if verdict == "final":
            final = v.get("final_plan") or (
                "终审方案（代码兜底汇总）：" + "；".join(s["text"] for s in record[-2:]))
            break

    trace.record("final", text=final)
    return {"final": final, "trace": trace}


PATTERN = {
    "team_code": "xborder-debate-adreview",
    "name": "广告策略评审",
    "mode": "msghub",
    "sample_input": TOPIC,
    "run": run,
}