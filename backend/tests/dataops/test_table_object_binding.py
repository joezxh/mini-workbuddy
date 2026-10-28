"""表→对象标准绑定（B3）：规则匹配 + bind_table 集成。"""
from __future__ import annotations

from sqlalchemy import select

from app.ai.dataops.rule_engine import RuleEngine
from app.models.dataops.meta import MetaTable
from app.models.dataops.standard_cdm import MetaObjectStandard, MetaTableStandard
from app.services.dataops.data_source_service import DataSourceService
from app.services.dataops.standard_binding_service import StandardBindingService
from tests.dataops.conftest import TENANT_A

OBJ_STDS = [
    {"id": 1, "code": "obj_order", "name": "订单", "aliases": ["order", "orders", "订单表"]},
    {"id": 2, "code": "obj_customer", "name": "客户", "aliases": ["customer", "客户"]},
]


def test_match_object_substr_hit():
    m = RuleEngine.match_object("t_order", "订单明细表", OBJ_STDS)
    assert m is not None and m.object_code == "obj_order"
    assert m.confidence >= 0.65


def test_match_object_none_below_min():
    assert RuleEngine.match_object("audit_log", "审计日志", OBJ_STDS) is None


def _make_source(db):
    return DataSourceService(db, TENANT_A).create(
        name="s", source_type="postgresql", host="h", port=5432,
        username="u", password="p", database="d",
    ).id


def test_bind_table_creates_object_binding(db):
    """一张已发布对象标准 + 物理表 → bind_table 产出 suggested 绑定。"""
    source_id = _make_source(db)
    db.add(MetaObjectStandard(tenant_id=TENANT_A, code="obj_order", name="订单",
                              aliases_json=["order"], status="published"))
    tbl = MetaTable(tenant_id=TENANT_A, source_id=source_id, database="public",
                    table_name="t_order", table_comment="订单表")
    db.add(tbl)
    db.flush()

    report = StandardBindingService(db, TENANT_A).bind_table(tbl.id)
    db.flush()

    assert report.objects_bound == 1
    binding = db.execute(
        select(MetaTableStandard).where(MetaTableStandard.table_id == tbl.id)
    ).scalar_one()
    assert binding.status == "suggested" and binding.source == "rule"


def test_bind_table_respects_human_object_binding(db):
    """人工 accepted 的表→对象绑定不被规则通道覆盖。"""
    source_id = _make_source(db)
    obj = MetaObjectStandard(tenant_id=TENANT_A, code="obj_order", name="订单",
                             aliases_json=["order"], status="published")
    other = MetaObjectStandard(tenant_id=TENANT_A, code="obj_audit", name="审计",
                               aliases_json=[], status="published")
    db.add_all([obj, other])
    tbl = MetaTable(tenant_id=TENANT_A, source_id=source_id, database="public",
                    table_name="t_order")
    db.add(tbl)
    db.flush()
    db.add(MetaTableStandard(tenant_id=TENANT_A, table_id=tbl.id,
                             object_standard_id=other.id, status="accepted", source="human"))
    db.flush()

    report = StandardBindingService(db, TENANT_A).bind_table(tbl.id)
    db.flush()

    assert report.objects_skipped_human == 1
    binding = db.execute(
        select(MetaTableStandard).where(MetaTableStandard.table_id == tbl.id)
    ).scalar_one()
    assert binding.object_standard_id == other.id and binding.source == "human"
