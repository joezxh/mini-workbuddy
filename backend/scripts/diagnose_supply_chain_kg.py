"""供应链图谱知识库 · 抽取结果现状诊断（只读）。

用法（在 backend/ 目录下）：
    .venv/Scripts/python.exe scripts/diagnose_supply_chain_kg.py            # 诊断全部 graph KB
    .venv/Scripts/python.exe scripts/diagnose_supply_chain_kg.py --kb 12   # 指定知识库
    .venv/Scripts/python.exe scripts/diagnose_supply_chain_kg.py --out r.md

只执行 SELECT，不写任何数据。输出：
* graph 知识库清单与生效抽取配置（schema_source / schema 是否为空 / max_output_tokens / model_spec）
* 实体/关系计数（按状态、类型分布；属性与别名覆盖率；evidence 覆盖率）
* 逐文档切片抽取聚合（entities / relations / dropped / truncated / 失败码）
* 失败切片明细（stage / error_code / error 摘要）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402


def _connect():
    return create_engine(settings.DATABASE_URL, echo=False)


def _rows(engine, sql: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(r._mapping) for r in result]


def _cfg_of(raw) -> dict:
    if isinstance(raw, dict):
        g = raw.get("graph")
        if isinstance(g, dict):
            return g
    return {}


def diagnose_kb(engine, kb: dict, out: list[str]) -> None:
    kid = kb["id"]
    out.append(f"\n## 知识库 {kid} · {kb['name']} (tenant={kb['tenant_id']})")
    g = _cfg_of(kb.get("pipeline_config"))
    out.append("### 生效抽取配置")
    out.append(f"- schema_source: `{g.get('schema_source')}`")
    schema = (g.get("schema") or "")
    out.append(f"- free_text 约束长度: **{len(schema)}** 字符" + ("（空 → 无类型约束！）" if not schema.strip() else ""))
    out.append(f"- max_output_tokens: `{g.get('max_output_tokens')}` · concurrency: `{g.get('concurrency_count')}` · timeout: `{g.get('timeout_seconds')}`s")
    out.append(f"- model_spec: `{json.dumps(g.get('model_spec'), ensure_ascii=False)}`")
    meta = (kb.get("pipeline_config") or {}).get("graph_build") if isinstance(kb.get("pipeline_config"), dict) else {}
    if isinstance(meta, dict) and meta:
        out.append(f"- 最近构建: `{json.dumps(meta, ensure_ascii=False)[:400]}`")

    # ── 实体 ──────────────────────────────────────────────────────────
    ents = _rows(engine, """
        SELECT id, name, type_code, status, aliases, properties
        FROM kg_entity WHERE knowledge_id = :kid
    """, {"kid": kid})
    out.append(f"\n### 实体（{len(ents)}）")
    st = Counter(e["status"] for e in ents)
    tp = Counter(e["type_code"] or "（未归类）" for e in ents)
    with_alias = sum(1 for e in ents if e["aliases"])
    with_props = sum(1 for e in ents if e["properties"])
    out.append(f"- 状态: {dict(st)} · 类型: {dict(tp)}")
    out.append(f"- 有别名: {with_alias}/{len(ents)} · 有属性: {with_props}/{len(ents)}")
    for e in ents[:40]:
        props = json.dumps(e["properties"], ensure_ascii=False) if e["properties"] else ""
        out.append(f"  - [{e['type_code'] or '-'}] {e['name']} ({e['status']}) {props[:120]}")

    # ── 关系 ──────────────────────────────────────────────────────────
    tris = _rows(engine, """
        SELECT t.id, t.relation_code, t.predicate, t.weight, t.status, t.evidence,
               a.name AS src, a.type_code AS src_type,
               b.name AS dst, b.type_code AS dst_type
        FROM kg_triple t
        JOIN kg_entity a ON a.id = t.from_entity_id
        JOIN kg_entity b ON b.id = t.to_entity_id
        WHERE t.knowledge_id = :kid
        ORDER BY t.id
    """, {"kid": kid})
    out.append(f"\n### 关系（{len(tris)}）")
    st = Counter(t["status"] for t in tris)
    rel = Counter(t["relation_code"] or "（自由谓词）" for t in tris)
    with_ev = sum(1 for t in tris if t["evidence"])
    no_weight = sum(1 for t in tris if t["weight"] in (None, 0))
    out.append(f"- 状态: {dict(st)} · 类型分布: {dict(rel)}")
    out.append(f"- 有 evidence: {with_ev}/{len(tris)} · weight 为空/0: {no_weight}/{len(tris)}")
    for t in tris:
        ev = json.dumps(t["evidence"], ensure_ascii=False) if t["evidence"] else ""
        out.append(f"  - {t['src']} --[{t['relation_code'] or t['predicate'] or '?'}]--> {t['dst']} w={t['weight']} ({t['status']}) ev={ev[:100]}")

    # ── 提及 ──────────────────────────────────────────────────────────
    em = _rows(engine, """
        SELECT count(*) AS n FROM kg_entity_mention m
        JOIN kg_entity e ON e.id = m.kg_entity_id
        WHERE e.knowledge_id = :kid
    """, {"kid": kid})
    tm = _rows(engine, """
        SELECT count(*) AS n FROM kg_triple_mention m
        JOIN kg_triple t ON t.id = m.kg_triple_id
        WHERE t.knowledge_id = :kid
    """, {"kid": kid})
    out.append(f"\n### 提及：实体提及 {em[0]['n']} · 关系提及 {tm[0]['n']}")

    # ── 逐文档切片聚合 ────────────────────────────────────────────────
    docs = _rows(engine, """
        SELECT d.id, d.uuid_code, d.name, d.status AS doc_status, d.meta
        FROM kms_document d WHERE d.knowledge_id = :kid ORDER BY d.id
    """, {"kid": kid})
    out.append(f"\n### 文档与切片抽取聚合（{len(docs)} 个文档）")
    tot = Counter()
    for d in docs:
        segs = _rows(engine, """
            SELECT id, chunk_index, graph_structure_indexed, graph_indexed, graph_extraction_details
            FROM kms_segment
            WHERE collection = :col AND document_id = :did AND parent_id IS NULL
            ORDER BY chunk_index
        """, {"col": f"kb_{kid}", "did": d["uuid_code"]})
        n = len(segs)
        ok = sum(1 for s in segs if s["graph_structure_indexed"] is True)
        fail = [s for s in segs if s["graph_structure_indexed"] is False]
        pend = sum(1 for s in segs if s["graph_structure_indexed"] is None)
        ent_sum = rel_sum = drop_rel = drop_ent = trunc = 0
        codes: Counter = Counter()
        for s in segs:
            det = s["graph_extraction_details"] or {}
            ent_sum += det.get("entities", 0) or 0
            rel_sum += det.get("relations", 0) or 0
            drop_ent += det.get("dropped_entities", 0) or 0
            drop_rel += det.get("dropped_relations", 0) or 0
            if det.get("truncated") or det.get("input_truncated"):
                trunc += 1
            if det.get("error_code"):
                codes[det["error_code"]] += 1
        gmeta = (d["meta"] or {}).get("graph_extract", {}) if isinstance(d["meta"], dict) else {}
        out.append(
            f"- **{d['name']}** ({d['doc_status']}) 切片 {n}：结构OK {ok} / 失败 {len(fail)} / 未跑 {pend}"
            f" ｜ 抽出 实体{ent_sum} 关系{rel_sum} ｜ 丢弃 实体{drop_ent} 关系{drop_rel} ｜ 截断 {trunc}"
            f" ｜ 失败码 {dict(codes)}"
        )
        if gmeta:
            out.append(f"  - doc.graph_extract: `{json.dumps(gmeta, ensure_ascii=False)[:300]}`")
        for s in fail[:8]:
            det = s["graph_extraction_details"] or {}
            out.append(f"  - 失败切片 #{s['chunk_index']} seg={s['id']}: {det.get('error_code')} / {str(det.get('error'))[:160]}")
        tot["seg"] += n; tot["ok"] += ok; tot["fail"] += len(fail)
        tot["ent"] += ent_sum; tot["rel"] += rel_sum
        tot["drop_rel"] += drop_rel; tot["drop_ent"] += drop_ent; tot["trunc"] += trunc
    out.append(f"\n### 汇总：切片 {tot['seg']}（OK {tot['ok']} / 失败 {tot['fail']}）· 抽出 实体{tot['ent']} 关系{tot['rel']}"
               f" · 丢弃 实体{tot['drop_ent']} 关系{tot['drop_rel']} · 截断切片 {tot['trunc']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", type=int, default=None, help="只诊断指定 knowledge_id")
    ap.add_argument("--out", type=str, default=None, help="同时写入 markdown 文件")
    args = ap.parse_args()

    engine = _connect()
    out: list[str] = ["# 供应链图谱知识库 · 抽取结果诊断报告（只读）"]

    kbs = _rows(engine, """
        SELECT id, name, tenant_id, pipeline_config
        FROM kms_knowledge WHERE type = 4 AND status = 1 ORDER BY id
    """)
    if args.kb is not None:
        kbs = [k for k in kbs if k["id"] == args.kb]
    kb_labels = [f"{k['id']}:{k['name']}" for k in kbs]
    out.append(f"\n发现 {len(kbs)} 个图谱知识库（type=4）: {kb_labels}")
    for kb in kbs:
        try:
            diagnose_kb(engine, kb, out)
        except Exception as exc:  # noqa: BLE001
            out.append(f"\n> ⚠ 诊断 kb={kb['id']} 失败: {exc}")

    report = "\n".join(out)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n[written] {args.out}")


if __name__ == "__main__":
    main()
