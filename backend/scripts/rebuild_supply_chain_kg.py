"""供应链图谱知识库 · 重跑抽取（qwen3-32b + 供应链约束）与复核。

用法（backend/ 目录）：
    .venv/Scripts/python.exe scripts/rebuild_supply_chain_kg.py --list-models
    .venv/Scripts/python.exe scripts/rebuild_supply_chain_kg.py --model-id 3 --apply-config
    .venv/Scripts/python.exe scripts/rebuild_supply_chain_kg.py --model-id 3 --rebuild
    .venv/Scripts/python.exe scripts/rebuild_supply_chain_kg.py --review-only

步骤：
1. ``--apply-config``：把 KB 12 的 graph 配置切到指定对话模型 + 供应链 free_text 约束
   （取自 docs/prototypes/supply-chain-kg/free-text-schema-constraint.md 第一节）+
   大窗口默认预算（4096/12000/3 轮）。
2. ``--rebuild``：同步执行 KgBuildService('rebuild')（含向量投影与自动关系复核）。
3. ``--review-only``：只跑关系复核 pass。
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal  # noqa: E402
from app.services.kb.kg import kg_config, kg_relation_reviewer  # noqa: E402
from app.services.kb.kg.kg_build_service import KgBuildService  # noqa: E402
from app.services.kb.kg.kg_llm_extractor import build_llm_extractor  # noqa: E402

KB_ID = 12  # 供应链图谱

# 与 docs/prototypes/supply-chain-kg/free-text-schema-constraint.md 第一节同源
SUPPLY_CHAIN_SCHEMA = """本知识库为「供应链」场景，抽取实体与关系时必须严格使用以下类型集合，不得自造类型。

【实体类型】（仅允许这 10 类）
1. 部门   —— 公司内部组织单元，如：采购部、销售部、仓储部、品控部
2. 供应商 —— 向本公司供货的外部企业，如：华创制造、启明电子、恒信科技
3. 产品   —— 可销售的整机/成品，如：天枢服务器、智联数码、联影工作站
4. 物料   —— 生产投入的原材料与零部件，如：电芯、主板、结构件、包装材料
5. 仓库   —— 仓储节点，如：北京仓、上海仓、华南仓
6. 客户   —— 采购本公司产品的外部企业，如：星海科技、远航贸易
7. 订单   —— 采购订单或销售订单，如：PO-2026-031、年度框架订单
8. 物流   —— 运输/配送过程与单据，如：干线运输、冷链配送、发运批次 SH-092
9. 协议   —— 框架合同与合作协议，如：2026年度供应商框架协议、销售框架合同
10. 风险事件 —— 已发生或潜在的风险，如：断供、延迟交付、质量事故、价格波动

【关系类型】（仅允许这 15 类，格式：起点类型 —[关系]→ 终点类型）
- 供应：部门 → 供应商（部门接受供应商供货）
- 生产：供应商 → 产品（供应商生产该产品）
- 提供：供应商 → 物料（供应商提供某物料）
- 库存：产品 → 仓库（产品在仓库存有库存）
- 存储：物料 → 仓库（物料存放于仓库）
- 签约：部门 → 客户（部门与客户签署销售合同）
- 采购：客户 → 产品（客户采购该产品）
- 配套：产品 → 产品（两产品配套/组合销售）
- 代理：供应商 → 供应商（一方代理另一方产能或产品）
- 协作：部门 → 部门（部门间业务协同）
- 隶属订单：订单 → 客户 或 供应商（订单归属于某客户或某供应商）
- 包含：订单 → 产品（订单明细包含某产品）
- 承运：物流 → 仓库（物流运输至仓库）
- 覆盖：协议 → 供应商 或 客户（框架协议覆盖的合作方）
- 引发风险：供应商 或 物料 或 物流 → 风险事件（该主体/环节引发某风险）

【抽取纪律】
1. 实体 name 取文本中最完整的叫法；简称、代号、英文名写入 aliases，不要另建实体。
2. 关系两端必须是已抽取的实体，禁止悬空边；方向按上文起点→终点，不得反向。
3. 数字、日期、金额、型号等属性写入 properties，不作为实体。
4. 关系宁多勿漏：文本中明确成立的关系都要输出（包括低置信的），不要输出自环关系。"""


def list_models() -> None:
    from sqlalchemy import select

    from app.models.ai.ai_api_key import AiChatModel

    with SessionLocal() as db:
        rows = db.execute(
            select(AiChatModel.id, AiChatModel.name, AiChatModel.model,
                   AiChatModel.platform, AiChatModel.status, AiChatModel.type,
                   AiChatModel.is_default)
        ).all()
        print("id | name | model | platform | status | type | default")
        for r in rows:
            print(" | ".join(str(x) for x in r))


def apply_config(model_id: int) -> None:
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    with SessionLocal() as db:
        kb = db.get(WikiKnowledge, KB_ID)
        if kb is None:
            raise SystemExit(f"kb {KB_ID} 不存在")
        pc = dict(kb.pipeline_config or {})
        graph = dict(pc.get("graph") or {})
        graph.update({
            "schema_source": "free_text",
            "schema": SUPPLY_CHAIN_SCHEMA,
            "model_spec": {"model_id": model_id},
            "max_output_tokens": 4096,
            "max_text_chars": 12000,
            "max_entities": 60,
            "max_relations": 120,
            "max_continuation_rounds": 3,
            "relation_review_enabled": True,
            "review_batch_size": 200,
            "review_concurrency": 4,
        })
        pc["graph"] = graph
        kb.pipeline_config = pc
        db.commit()
    print(f"[config] kb={KB_ID} 已切到 model_id={model_id} + 供应链约束 + 大窗口预算")


def _resolve_tenant(db) -> int:
    """租户解析：知识库行 tenant 可能为 NULL（KB 12 就是），此时以切片为准——
    图谱数据必须与切片同租户，否则前端按用户 tenant 查询会把新抽取全过滤掉。"""
    from sqlalchemy import text as _text

    row = db.execute(
        _text("SELECT tenant_id FROM kms_segment WHERE collection=:c "
              "AND tenant_id IS NOT NULL LIMIT 1"),
        {"c": f"kb_{KB_ID}"},
    ).first()
    if row:
        return int(row[0])
    row = db.execute(
        _text("SELECT tenant_id FROM kms_knowledge WHERE id=:kid"), {"kid": KB_ID}
    ).first()
    return int(row[0]) if row and row[0] is not None else 0


def rebuild() -> None:
    """逐文档恢复构建：每个文档一个独立 Session（单连接撑不住 40 分钟长事务，
    连接断开会 PendingRollbackError 级联毁掉整批）。action=build 增量补跑：
    已成功切片自动跳过，只重抽失败的。"""
    from sqlalchemy import text as _text

    with SessionLocal() as db:
        row = db.execute(
            _text("SELECT uuid_code, name FROM kms_document WHERE knowledge_id = :kid ORDER BY id"),
            {"kid": KB_ID},
        ).all()
    docs = [(r[0], r[1]) for r in row]
    print(f"[rebuild] {len(docs)} 个文档，逐文档增量构建")
    for uuid, name in docs:
        try:
            with SessionLocal() as db:
                tenant_id = _resolve_tenant(db)
                svc = KgBuildService(db, tenant_id, KB_ID)
                report = svc.run("build", uuid)
                print(f"[rebuild] {name}: {report.as_dict()}")
        except Exception as exc:  # noqa: BLE001 - 单文档失败不毁整批
            print(f"[rebuild] {name} 失败: {type(exc).__name__}: {str(exc)[:200]}")


def review_only() -> None:
    with SessionLocal() as db:
        tenant_id = _resolve_tenant(db)
        cfg = kg_config.get_graph_config(db, KB_ID)
        llm, note = build_llm_extractor(db, cfg)
        if llm is None:
            raise SystemExit(f"复核通道不可用: {note}")
        summary = kg_relation_reviewer.run_review(
            db, tenant_id=tenant_id, knowledge_id=KB_ID,
            complete=llm.complete, status=None,  # 全部状态重评
            limit=3000,  # 全量复核（review_batch_size 默认 200 只够增量补跑）
            concurrency=int(cfg.get("review_concurrency") or 4),
        )
        print("[review]", summary)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--model-id", type=int, default=None)
    ap.add_argument("--apply-config", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--review-only", action="store_true")
    args = ap.parse_args()

    if args.list_models:
        list_models()
    if args.apply_config:
        if args.model_id is None:
            raise SystemExit("--apply-config 需要 --model-id")
        apply_config(args.model_id)
    if args.rebuild:
        rebuild()
    if args.review_only:
        review_only()
    if not (args.list_models or args.apply_config or args.rebuild or args.review_only):
        print(__doc__)


if __name__ == "__main__":
    main()
