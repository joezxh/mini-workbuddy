"""三域本体 demo 数据（销售 / 供应链 / 人力），图谱级：结构表 + 发布血统。

对齐原型 docs/prototypes/ontology-capability-preview.html：
- 销售域 ``sales_ontology``（published / current_version=3）：节点、关系与 review_status
  取自原型 ``NODES``/``EDGES``（accepted 者经只读口径在 architecture 图可见）；
- 供应链 ``supply_chain_ontology``（published / current_version=1）：合成 10 对象 + 9 关系，
  全 accepted → 图谱饱满；
- 人力 ``hr_ontology``（draft / current_version=0）：一条 running 构建任务 + 若干未采纳候选
  （``build_item(status='suggested')`` 无 element_id、无结构行）→ 图谱空，表达"构建中"。

图谱血统（消费面只读口径，§4.6）：
``OntologyGraphService.graph`` → ``OntologyPublishService.build_snapshot`` →
``build_job``→``build_item(status='accepted').element_id``→ ``meta_object_standard``/
``meta_object_relation``。故可渲染本体写满这 5 张表 + ``onto_ontology_version`` 版本快照。

对象/关系 code **按域加前缀**（``sales_*``/``sc_*``/``hr_*``）以满足 ``meta_object_standard``/
``meta_object_relation`` 的 ``(tenant_id, code)`` 唯一（obj_product 等跨域同名会撞约束）。

幂等：逐 ``sys_tenant`` 租户，若该租户下 ``onto_ontology.code`` 已存在则整域跳过（子行随之不重复）。
CDM 结构层（``meta_object_standard``/``meta_object_relation``）保留 ``meta_`` 前缀、留 dataops，
是本体→dataops 的合法跨层依赖。

Revision ID: 2026_11_01_0009_seed_demo_ontologies
Revises: 2026_11_01_0008_rename_meta_to_onto_prefix
Create Date: 2026-11-01
"""
from typing import Sequence, Union

import json

import sqlalchemy as sa
from alembic import op

revision: str = "2026_11_01_0009_seed_demo_ontologies"
down_revision: Union[str, None] = "2026_11_01_0008_rename_meta_to_onto_prefix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 域 code → 用于 downgrade 精确清理（demo 前缀保证不与既有数据混淆）
_DEMO_ONTOLOGY_CODES = ("sales_ontology", "supply_chain_ontology", "hr_ontology")

# ── 可渲染本体规格（销售 / 供应链）───────────────────────────────────────
# object: (code, name, review_status, confidence, description)
# relation: (code, name, from_obj_code, to_obj_code, review_status, confidence)
_RENDERABLE = [
    {
        "domain": "销售域",
        "ontology": dict(
            code="sales_ontology", name="销售域本体", namespace="urn:mwb:ontology:sales_ontology",
            description="销售域 demo：客户/订单/产品等对象与关系（对齐原型 ontology-capability-preview）",
            status="published", current_version=3,
        ),
        "job": dict(idempotency_key="demo-sales-build", status="succeeded", mode="rules", phase="done", progress=1.0),
        "objects": [
            ("sales_obj_customer", "客户", "accepted", 0.92, "客户主数据，销售归属主体"),
            ("sales_obj_order", "订单", "accepted", 0.90, "客户下单产生的销售订单"),
            ("sales_obj_order_item", "订单明细", "suggested", 0.72, "订单中的商品行项目，含数量与成交单价"),
            ("sales_obj_product", "产品", "accepted", 0.88, "可销售的产品主数据"),
            ("sales_obj_region", "区域", "suggested", 0.66, "行政区划维度，用于客户归属与销售分区统计"),
            ("sales_obj_payment", "回款", "rejected", 0.41, "订单回款记录（疑似维表判定被拒）"),
        ],
        "relations": [
            ("sales_rel_order_of_customer", "订单→客户", "sales_obj_order", "sales_obj_customer", "accepted", 0.89),
            ("sales_rel_item_of_order", "明细→订单", "sales_obj_order_item", "sales_obj_order", "accepted", 0.86),
            ("sales_rel_product_of_item", "明细→产品", "sales_obj_order_item", "sales_obj_product", "suggested", 0.71),
            ("sales_rel_region_of_customer", "客户→区域", "sales_obj_customer", "sales_obj_region", "suggested", 0.66),
            ("sales_rel_payment_of_order", "回款→订单", "sales_obj_payment", "sales_obj_order", "rejected", 0.41),
        ],
    },
    {
        "domain": "供应链域",
        "ontology": dict(
            code="supply_chain_ontology", name="供应链本体", namespace="urn:mwb:ontology:supply_chain_ontology",
            description="供应链 demo：采购/库存/配送全链路对象与关系（合成，全采纳）",
            status="published", current_version=1,
        ),
        "job": dict(idempotency_key="demo-sc-build", status="succeeded", mode="rules", phase="done", progress=1.0),
        "objects": [
            ("sc_obj_supplier", "供应商", "accepted", 0.90, "供应商主数据"),
            ("sc_obj_purchase_order", "采购单", "accepted", 0.91, "向供应商发起的采购单"),
            ("sc_obj_po_line", "采购单行", "accepted", 0.88, "采购单中的物料行项目"),
            ("sc_obj_product", "产品", "accepted", 0.89, "采购与库存对应的产品主数据"),
            ("sc_obj_warehouse", "仓库", "accepted", 0.87, "实物仓储节点"),
            ("sc_obj_inventory", "库存", "accepted", 0.90, "仓库中的产品库存"),
            ("sc_obj_shipment", "发货单", "accepted", 0.86, "供应商发货记录"),
            ("sc_obj_customer", "客户", "accepted", 0.92, "下游客户"),
            ("sc_obj_delivery", "配送", "accepted", 0.85, "面向客户的配送单"),
            ("sc_obj_contract", "供应商合同", "accepted", 0.83, "与供应商签订的框架合同"),
        ],
        "relations": [
            ("sc_rel_po_of_supplier", "采购单→供应商", "sc_obj_purchase_order", "sc_obj_supplier", "accepted", 0.90),
            ("sc_rel_line_of_po", "采购行→采购单", "sc_obj_po_line", "sc_obj_purchase_order", "accepted", 0.88),
            ("sc_rel_line_product", "采购行→产品", "sc_obj_po_line", "sc_obj_product", "accepted", 0.87),
            ("sc_rel_inventory_of_warehouse", "库存→仓库", "sc_obj_inventory", "sc_obj_warehouse", "accepted", 0.89),
            ("sc_rel_inventory_product", "库存→产品", "sc_obj_inventory", "sc_obj_product", "accepted", 0.88),
            ("sc_rel_shipment_of_po", "发货单→采购单", "sc_obj_shipment", "sc_obj_purchase_order", "accepted", 0.85),
            ("sc_rel_delivery_of_shipment", "配送→发货单", "sc_obj_delivery", "sc_obj_shipment", "accepted", 0.84),
            ("sc_rel_delivery_customer", "配送→客户", "sc_obj_delivery", "sc_obj_customer", "accepted", 0.86),
            ("sc_rel_contract_of_supplier", "合同→供应商", "sc_obj_contract", "sc_obj_supplier", "accepted", 0.82),
        ],
    },
]

# ── 构建中本体规格（人力）：仅 running 任务 + 未采纳候选，无结构行、无版本 ────
_BUILDING = [
    {
        "domain": "人力域",
        "ontology": dict(
            code="hr_ontology", name="人力本体", namespace="urn:mwb:ontology:hr_ontology",
            description="人力域 demo：构建中（运行中的构建任务 + 未采纳候选，图谱暂空）",
            status="draft", current_version=0,
        ),
        "job": dict(idempotency_key="demo-hr-build", status="running", mode="rules", phase="align", progress=0.4),
        "candidates": [
            ("object", "hr_obj_employee", "员工"),
            ("object", "hr_obj_department", "部门"),
            ("object", "hr_obj_position", "岗位"),
            ("object", "hr_obj_attendance", "考勤"),
            ("relation", "hr_rel_employee_dept", "员工→部门"),
            ("relation", "hr_rel_position_of_employee", "岗位→员工"),
        ],
    },
]


def _existing_ontology_id(bind, tid: int, code: str):
    row = bind.execute(
        sa.text("SELECT id FROM onto_ontology WHERE tenant_id = :t AND code = :c"),
        {"t": tid, "c": code},
    ).first()
    return row[0] if row else None


def _insert_ontology(bind, tid: int, o: dict) -> int:
    return bind.execute(
        sa.text(
            "INSERT INTO onto_ontology (tenant_id, code, name, description, namespace_uri, status, current_version) "
            "VALUES (:t, :code, :name, :desc, :ns, :status, :cv) RETURNING id"
        ),
        {
            "t": tid, "code": o["code"], "name": o["name"], "desc": o["description"],
            "ns": o["namespace"], "status": o["status"], "cv": o["current_version"],
        },
    ).scalar()


def _insert_job(bind, tid: int, ontology_id: int, j: dict) -> int:
    return bind.execute(
        sa.text(
            "INSERT INTO onto_ontology_build_job "
            "(tenant_id, ontology_id, idempotency_key, mode, status, phase, progress) "
            "VALUES (:t, :oid, :key, :mode, :status, :phase, :progress) RETURNING id"
        ),
        {
            "t": tid, "oid": ontology_id, "key": j["idempotency_key"], "mode": j["mode"],
            "status": j["status"], "phase": j["phase"], "progress": j["progress"],
        },
    ).scalar()


def _insert_object(bind, tid: int, domain: str, spec: tuple) -> int:
    code, name, review, conf, desc = spec
    status = "published" if review == "accepted" else "draft"
    return bind.execute(
        sa.text(
            "INSERT INTO meta_object_standard "
            "(tenant_id, code, name, description, domain, status, source, review_status, confidence) "
            "VALUES (:t, :code, :name, :desc, :domain, :status, 'rule', :review, :conf) RETURNING id"
        ),
        {
            "t": tid, "code": code, "name": name, "desc": desc, "domain": domain,
            "status": status, "review": review, "conf": conf,
        },
    ).scalar()


def _insert_relation(bind, tid: int, domain: str, spec: tuple, obj_id_map: dict) -> int:
    code, name, from_code, to_code, review, conf = spec
    status = "published" if review == "accepted" else "draft"
    return bind.execute(
        sa.text(
            "INSERT INTO meta_object_relation "
            "(tenant_id, code, name, from_object_id, to_object_id, relation_type, status, source, review_status, confidence) "
            "VALUES (:t, :code, :name, :fid, :tid_, 'N:1', :status, 'rule', :review, :conf) RETURNING id"
        ),
        {
            "t": tid, "code": code, "name": name, "fid": obj_id_map[from_code], "tid_": obj_id_map[to_code],
            "status": status, "review": review, "conf": conf,
        },
    ).scalar()


def _insert_build_item(bind, tid: int, job_id: int, kind: str, code: str, status: str, element_id) -> None:
    bind.execute(
        sa.text(
            "INSERT INTO onto_ontology_build_item "
            "(tenant_id, job_id, element_kind, element_code, action, origin, status, element_id) "
            "VALUES (:t, :jid, :kind, :code, 'insert', 'rule', :status, :eid)"
        ),
        {"t": tid, "jid": job_id, "kind": kind, "code": code, "status": status, "eid": element_id},
    )


def _seed_renderable(bind, tid: int, spec: dict) -> None:
    """可渲染本体：ontology + job + 结构对象/关系 + accepted/其它态 build_item + 版本快照。"""
    ontology_id = _insert_ontology(bind, tid, spec["ontology"])
    job_id = _insert_job(bind, tid, ontology_id, spec["job"])

    obj_id_map = {}
    accepted_objects = []
    for ospec in spec["objects"]:
        oid = _insert_object(bind, tid, spec["domain"], ospec)
        code, name, review, conf, _desc = ospec
        obj_id_map[code] = oid
        _insert_build_item(bind, tid, job_id, "object", code, review, oid)
        if review == "accepted":
            accepted_objects.append({"id": oid, "code": code, "name": name, "domain": spec["domain"],
                                     "aliases": [], "source": "rule", "review_status": review, "confidence": conf})

    accepted_relations = []
    for rspec in spec["relations"]:
        rid = _insert_relation(bind, tid, spec["domain"], rspec, obj_id_map)
        code, name, from_code, to_code, review, conf = rspec
        _insert_build_item(bind, tid, job_id, "relation", code, review, rid)
        if review == "accepted":
            accepted_relations.append({"id": rid, "code": code, "name": name,
                                       "from_object_id": obj_id_map[from_code], "to_object_id": obj_id_map[to_code],
                                       "relation_type": "N:1", "source": "rule", "review_status": review})

    cv = spec["ontology"]["current_version"]
    if cv and cv > 0:
        snapshot = {
            "objects": accepted_objects,
            "relations": accepted_relations,
            "properties": [],
            "mappings": {"table": [], "column": []},
            "cq": [],
        }
        diff = {
            "added": {"objects": [o["code"] for o in accepted_objects],
                      "relations": [r["code"] for r in accepted_relations], "properties": 0},
            "removed": {"objects": [], "relations": []}, "changed": [], "regressions": [],
        }
        gate = {"passed": True, "checks": [], "blocked_reasons": [], "exemptions": []}
        bind.execute(
            sa.text(
                "INSERT INTO onto_ontology_version "
                "(tenant_id, ontology_id, version, snapshot_json, diff_json, gate_json, change_note) "
                "VALUES (:t, :oid, :v, CAST(:snap AS jsonb), CAST(:diff AS jsonb), CAST(:gate AS jsonb), :note)"
            ),
            {
                "t": tid, "oid": ontology_id, "v": cv,
                "snap": json.dumps(snapshot), "diff": json.dumps(diff), "gate": json.dumps(gate),
                "note": "demo：三域初始化迁移内生成的发布快照",
            },
        )


def _seed_building(bind, tid: int, spec: dict) -> None:
    """构建中本体：ontology + running job + 未采纳候选（无结构行、无 accepted → 图谱空）。"""
    ontology_id = _insert_ontology(bind, tid, spec["ontology"])
    job_id = _insert_job(bind, tid, ontology_id, spec["job"])
    for kind, code, _name in spec["candidates"]:
        _insert_build_item(bind, tid, job_id, kind, code, "suggested", None)


def upgrade() -> None:
    bind = op.get_bind()
    tenant_ids = bind.execute(sa.text("SELECT tenant_id FROM sys_tenant")).scalars().all()
    for tid in tenant_ids:
        for spec in _RENDERABLE:
            if _existing_ontology_id(bind, tid, spec["ontology"]["code"]) is None:
                _seed_renderable(bind, tid, spec)
        for spec in _BUILDING:
            if _existing_ontology_id(bind, tid, spec["ontology"]["code"]) is None:
                _seed_building(bind, tid, spec)


def downgrade() -> None:
    bind = op.get_bind()
    onto_in = ", ".join(f"'{c}'" for c in _DEMO_ONTOLOGY_CODES)
    obj_codes = [o[0] for s in _RENDERABLE for o in s["objects"]]
    rel_codes = [r[0] for s in _RENDERABLE for r in s["relations"]]
    obj_in = ", ".join(f"'{c}'" for c in obj_codes)
    rel_in = ", ".join(f"'{c}'" for c in rel_codes)

    # 先删 CDM 结构关系（FK RESTRICT 引用对象），再删对象；本体子行（job/item/version）随本体 CASCADE
    bind.execute(sa.text(f"DELETE FROM meta_object_relation WHERE code IN ({rel_in})"))
    bind.execute(sa.text(f"DELETE FROM meta_object_standard WHERE code IN ({obj_in})"))
    bind.execute(
        sa.text(
            "DELETE FROM onto_ontology_build_item WHERE job_id IN ("
            "SELECT j.id FROM onto_ontology_build_job j "
            f"WHERE j.ontology_id IN (SELECT id FROM onto_ontology WHERE code IN ({onto_in})))"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM onto_ontology_version WHERE ontology_id IN ("
            f"SELECT id FROM onto_ontology WHERE code IN ({onto_in}))"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM onto_ontology_build_job WHERE ontology_id IN ("
            f"SELECT id FROM onto_ontology WHERE code IN ({onto_in}))"
        )
    )
    bind.execute(sa.text(f"DELETE FROM onto_ontology WHERE code IN ({onto_in})"))
