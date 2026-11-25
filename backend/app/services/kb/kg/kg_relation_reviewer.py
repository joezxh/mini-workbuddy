"""关系 LLM 二次复核（证据复核 pass）——对每条已抽取关系问一句「证据撑得住吗」。

为什么要二次复核（2026-11-24，供应链库实测教训）
------------------------------------------------
抽取与复核共用一个 LLM 但任务不同：抽取是「从文本里找出关系」，复核是
「给定关系与它的证据原文，判定证据是否真实支撑该关系」。抽取侧为拿到
足够的召回被提示词明确要求「宁多勿漏」，低置信关系也会输出——质量把关
后移到本环节，而不是靠提示词自断数量（那样只会得到一个「干净但空」的图）。

实测三类必复核的脏数据（qwen3.5-0.8b 抽取产物）：
* echo 占位：evidence 原样抄了提示词的「支撑该关系的原文片段」；
* 方向颠倒：上海仓 --库存--> 智联数码（应为 智联数码→上海仓）；
* 无关拼凑：依据与关系主体/谓词完全对不上。

判定词表
--------
* ``supported``   证据原文明确陈述了该关系（主体、谓词、方向一致）；
* ``weak``        间接支撑（方向存疑 / 谓词含义接近但不一致 / 主体客体只是相关）；
* ``unsupported`` 证据与关系无关、明确矛盾、或是提示词占位文本；
* ``review_failed`` 复核调用本身失败（网络/解析）——可重试，不算模型结论。

与人工评审的关系：复核**只标记不流转**，``status`` 仍由人工评审驱动
（suggested → accepted/rejected）；``unsupported`` 的关系在前端带红徽标，
供人工优先处理。
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Optional

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.orm import Session

VERDICT_SUPPORTED = "supported"
VERDICT_WEAK = "weak"
VERDICT_UNSUPPORTED = "unsupported"
VERDICT_FAILED = "review_failed"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_VALID_VERDICTS = {VERDICT_SUPPORTED, VERDICT_WEAK, VERDICT_UNSUPPORTED}


def build_review_prompt(
    *,
    source: str,
    relation: str,
    target: str,
    evidence: str,
    context: str = "",
) -> str:
    """组装单条关系的复核指令。``context`` 为源切片正文摘录（可选，给模型更多依据）。"""
    parts = [
        "你是知识图谱关系复核器。给定一条候选关系与它的抽取依据（原文片段），"
        "判断依据是否真实支撑该关系。只输出一个 JSON 对象，不要输出解释或代码块围栏。",
        "",
        '输出结构：{"verdict": "supported|weak|unsupported", '
        '"reason": "一句话理由", "confidence": 0.85}',
        "confidence 为 0-1 的置信度（一位小数）：supported 通常 ≥0.7，"
        "weak 0.4-0.7，unsupported <0.4。",
        "",
        "判定标准：",
        "- supported：依据原文明确陈述了该关系（主体、谓词、方向一致）；",
        "- weak：间接支撑（方向相反或存疑、谓词含义接近但不完全一致、主体客体只是相关）；",
        "- unsupported：依据与该关系无关、明确矛盾，或只是提示词占位文本"
        "（如「支撑该关系的原文片段」）；",
        "",
        f"关系：{source} --[{relation}]--> {target}",
        f"抽取依据：{evidence or '（无）'}",
    ]
    if context.strip():
        parts += ["", "源切片摘录（辅助判断）：", context.strip()[:800]]
    return "\n".join(parts)


# 解析失败/模型缺 confidence 时按判定推导默认置信度（回填 weight 用）
_DEFAULT_CONFIDENCE = {
    VERDICT_SUPPORTED: 0.8,
    VERDICT_WEAK: 0.5,
    VERDICT_UNSUPPORTED: 0.2,
}


def parse_review_response(raw: str) -> tuple[str, str, Optional[float]]:
    """复核响应 → ``(verdict, reason, confidence)``。

    ``confidence`` 为 0-1 置信度（越界钳制、非法/缺失按判定推导默认值）；
    解析失败/词表外判定 → ``(review_failed, 原文摘要, None)``（None 表示
    不回填 weight）。
    """
    text = _FENCE_RE.sub("", (raw or "").strip()).strip()
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no json object")
        data = json.loads(text[start:end + 1])
        verdict = str(data.get("verdict") or "").strip()
        reason = str(data.get("reason") or "").strip()
        if verdict not in _VALID_VERDICTS:
            raise ValueError(f"invalid verdict: {verdict!r}")
        confidence = _DEFAULT_CONFIDENCE[verdict]
        try:
            parsed = float(data.get("confidence"))
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None:
            confidence = max(0.0, min(1.0, parsed))
        return verdict, reason, round(confidence, 2)
    except Exception:
        return VERDICT_FAILED, f"复核响应无法解析: {(raw or '')[:120]!r}", None


def _evidence_text(triple) -> str:
    """``evidence`` JSONB → 评审用的纯文本（{"text": ...} 或 {"quote"/"sentence"/...}）。"""
    ev = triple.evidence
    if isinstance(ev, dict):
        for key in ("text", "quote", "sentence", "content"):
            v = ev.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""
    if isinstance(ev, str):
        return ev.strip()
    return ""


def run_review(
    db: Session,
    *,
    tenant_id: Optional[int],
    knowledge_id: int,
    complete: Callable[[str], str],
    relation_ids: Optional[list[int]] = None,
    status: str = "suggested",
    limit: int = 100,
    concurrency: int = 4,
    skip_reviewed: bool = False,
) -> dict:
    """批量复核关系并落库（verdict/note/reviewed_at，置信度回填 weight）。

    :param complete: LLM 补全函数（``prompt -> 响应文本``）；生产传
        ``LLMExtractor.complete``，测试注入假实现。
    :param relation_ids: 指定关系 ID 清单（手动触发指定条目）；None 时按
        ``status``（默认 suggested，即所有待人工评审的关系；``None`` = 全部状态）
        取前 ``limit`` 条。
    :param skip_reviewed: True 时跳过已有复核结论的关系（``reviewed_at`` 非空）。
        构建内自动复核必须传 True（增量语义：只复核新关系，不覆盖历史结论）；
        手动端点默认 False（显式重评换模型后的全部关系）。
    :return: 计数摘要 ``{selected, reviewed, supported, weak, unsupported,
        review_failed}``。

    并发只包 LLM 调用（线程池），落库在主线程串行（Session 非线程安全）；
    单条失败落 ``review_failed`` 不影响整批。

    事务边界（2026-11-25 复盘，启动卡死根因之一）：SELECT 会 autobegin 读
    事务，旧实现把分钟级 LLM 复核夹在读事务与落库 commit 之间——复核期间
    会话全程 ``idle in transaction``（kms_segment 上的 ACCESS SHARE 锁不放，
    与 ALTER TABLE 的 ACCESS EXCLUSIVE 冲突），把启动迁移堵死在 PG 锁队列。
    现改为三段：短读事务（读+快照+提交）→ 无事务 LLM 并发 → 短写事务
    （批量 UPDATE + 提交），LLM 期间不占用任何连接锁。
    """
    from app.models.kb.kg_entity import KgEntity
    from app.models.kb.kg_triple import KgTriple

    summary_empty = {"selected": 0, "reviewed": 0, VERDICT_SUPPORTED: 0,
                     VERDICT_WEAK: 0, VERDICT_UNSUPPORTED: 0, VERDICT_FAILED: 0}

    # ── 阶段 1：短读事务（读取 + 标量快照，随即提交结束事务）──────────────
    stmt = (
        select(KgTriple, KgEntity.name)
        .join(KgEntity, KgEntity.id == KgTriple.from_entity_id)
        .where(KgTriple.knowledge_id == knowledge_id)
    )
    if tenant_id is not None:
        stmt = stmt.where(KgTriple.tenant_id == tenant_id)
    if relation_ids:
        stmt = stmt.where(KgTriple.id.in_([int(x) for x in relation_ids]))
    elif status:
        stmt = stmt.where(KgTriple.status == status)
    if skip_reviewed:
        stmt = stmt.where(KgTriple.reviewed_at.is_(None))
    rows = list(db.execute(stmt.limit(max(1, int(limit or 1)))).all())
    if not rows:
        db.rollback()  # 结束 autobegin 的读事务再返回，不留 open transaction
        return summary_empty

    # 端点实体名与源切片摘录批量取（避免逐条查库）
    name_rows = db.execute(
        select(KgEntity.id, KgEntity.name).where(
            KgEntity.knowledge_id == knowledge_id,
            *([KgEntity.tenant_id == tenant_id] if tenant_id is not None else []),
        ).limit(20000)
    ).all()
    names = {eid: name for eid, name in name_rows}
    seg_ids = {
        sid
        for (t, _src) in rows
        for sid in (t.source_segment_ids or [])[:2]
        if isinstance(sid, int)
    }
    contexts: dict[int, str] = {}
    if seg_ids:
        from app.models.kb.kb_segment import KbSegment

        seg_rows = db.execute(
            select(KbSegment.id, KbSegment.content).where(
                KbSegment.id.in_(list(seg_ids)[:50]))
        ).all()
        contexts = {sid: (content or "")[:800] for sid, content in seg_rows}

    # 提交前把复核所需数据快照成纯 dict（commit 后 ORM 对象过期，LLM 阶段
    # 若访问属性会触发 refresh SELECT 重新打开事务，恰好破坏本修复的目的）
    tasks = [
        {
            "id": t.id,
            "relation": t.relation_code or t.predicate or "",
            "evidence": _evidence_text(t),
            "source": names.get(t.from_entity_id, ""),
            "target": names.get(t.to_entity_id, ""),
            "context": contexts.get((t.source_segment_ids or [None])[0], "")
            if t.source_segment_ids else "",
        }
        for (t, _src_name) in rows
    ]
    db.commit()  # 关键：读事务到此结束，LLM 复核期间不再持有任何锁

    # ── 阶段 2：无事务 LLM 并发复核 ──────────────────────────────────────
    def _one(task: dict):
        prompt = build_review_prompt(
            source=task["source"], relation=task["relation"],
            target=task["target"], evidence=task["evidence"],
            context=task["context"],
        )
        try:
            verdict, reason, confidence = parse_review_response(complete(prompt))
        except Exception as exc:  # noqa: BLE001 - 单条调用异常按 review_failed 隔离
            logger.warning(
                f"[kg-review] 关系复核调用失败 triple={task['id']}: {exc}"
            )
            return task["id"], VERDICT_FAILED, f"复核调用异常: {type(exc).__name__}", None
        return task["id"], verdict, reason, confidence

    workers = max(1, min(int(concurrency or 1), len(tasks)))
    if workers == 1:
        results = [_one(t) for t in tasks]
    else:
        with ThreadPoolExecutor(max_workers=workers,
                                thread_name_prefix="kg-review") as pool:
            results = list(pool.map(_one, tasks))

    # ── 阶段 3：短写事务（批量 UPDATE，一次提交）─────────────────────────
    summary = {"selected": len(tasks), "reviewed": 0,
               VERDICT_SUPPORTED: 0, VERDICT_WEAK: 0,
               VERDICT_UNSUPPORTED: 0, VERDICT_FAILED: 0}
    now = datetime.now()
    for tid, verdict, reason, confidence in results:
        values = {
            "review_verdict": verdict,
            "review_note": reason,
            "reviewed_at": now,
        }
        if confidence is not None:
            # 复核置信度回填 weight（0-1）：关系表权重条由此有了真实数值，
            # 不再依赖抽取侧输出（抽取不产置信度，遗留问题 weight 全 0）
            values["weight"] = confidence
        db.execute(update(KgTriple).where(KgTriple.id == tid).values(**values))
        summary[verdict] = summary.get(verdict, 0) + 1
        summary["reviewed"] += 1
    db.commit()
    logger.info(
        f"[kg-review] kb={knowledge_id} 复核完成：{summary}"
    )
    return summary


def build_review_channel(db, graph_cfg: dict):
    """按图谱配置构造复核通道（复用抽取的 LLM 通道构造，不另起一套模型栈）。

    :return: ``(complete | None, note)``——为 None 时 note 说明原因（写日志）。
    """
    from app.services.kb.kg.kg_llm_extractor import build_llm_extractor

    llm, note = build_llm_extractor(db, graph_cfg)
    if llm is None:
        return None, note
    return llm.complete, note
