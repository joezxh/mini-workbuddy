"""P2 Task 11/12/13 测试：规则引擎（纯）/ 标准绑定（集成）/ 关系推断（集成）。"""
from __future__ import annotations

import pytest

from app.ai.dataops.rule_engine import (
    BUILTIN_STANDARDS, RuleEngine, TIER_ACCEPTED, TIER_SUGGESTED, TIER_DROP, tier,
)
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.standard import MetaColumnStandard, MetaStandard
from app.services.dataops.data_source_service import DataSourceService
from app.services.dataops.relation_inference_service import (
    RelationInferenceService, _vote_key, _vote_name,
)
from app.services.dataops.standard_binding_service import StandardBindingService
from app.services.dataops.standard_service import MetaStandardService
from tests.dataops.conftest import TENANT_A


# ── Task 12 规则引擎（纯单测）──────────────────────────────────────────────────
def test_tier_boundaries():
    assert tier(0.90) == TIER_ACCEPTED
    assert tier(0.85) == TIER_ACCEPTED
    assert tier(0.70) == TIER_SUGGESTED
    assert tier(0.65) == TIER_SUGGESTED
    assert tier(0.50) == TIER_DROP
    assert tier(None) == TIER_SUGGESTED


def test_detect_semantic_phone_by_name():
    r = RuleEngine.detect_semantic("user_mobile", data_type="varchar", comment="手机号")
    assert r.semantic_type == "phone" and r.pii_level == "L3"
    assert r.confidence >= 0.85


def test_detect_semantic_email_by_value():
    r = RuleEngine.detect_semantic(
        "email", data_type="varchar", profile_top_values=[{"value": "a@b.com", "count": 3}]
    )
    assert r.semantic_type == "email" and r.pii_level == "L3"
    assert r.confidence >= 0.9


def test_detect_semantic_amount_by_datatype():
    r = RuleEngine.detect_semantic("order_price", data_type="numeric")
    assert r.semantic_type == "amount"


def test_detect_semantic_no_match():
    r = RuleEngine.detect_semantic("random_flag", data_type="boolean")
    assert r.semantic_type is None


def test_match_standard_exact_alias():
    standards = [{"id": 1, "code": "std_phone", "name": "手机号",
                  "aliases": ["phone", "mobile", "手机"], "data_type_expect": ""}]
    m = RuleEngine.match_standard("user_mobile", "手机", "varchar", standards)
    assert m is not None and m.standard_code == "std_phone" and m.confidence >= 0.7


def test_match_standard_below_threshold():
    assert RuleEngine.match_standard("foo", "无关", "varchar", []) is None


# ── Task 11 标准绑定（集成）────────────────────────────────────────────────────
def _make_source(db):
    svc = DataSourceService(db, TENANT_A)
    return svc.create(name="s", source_type="postgresql", host="h", port=5432,
                      username="u", password="p", database="d").id


def _make_table(db, source_id, table_name, columns):
    t = MetaTable(tenant_id=TENANT_A, source_id=source_id, database="public",
                  table_name=table_name)
    db.add(t)
    db.flush()
    for name, dtype, key, comment in columns:
        db.add(MetaColumn(tenant_id=TENANT_A, table_id=t.id, column_name=name,
                          ordinal=0, data_type=dtype, column_key=key, column_comment=comment))
    db.flush()
    return t


def test_seed_and_bind(db):
    source_id = _make_source(db)
    MetaStandardService(db, TENANT_A).seed_builtins()
    tbl = _make_table(db, source_id, "customer", [
        ("phone_number", "varchar", None, "手机号"),
        ("email_addr", "varchar", None, "邮箱"),
        ("order_amount", "numeric", None, "金额"),
    ])
    rep = StandardBindingService(db, TENANT_A).bind_table(tbl.id)
    db.commit()
    assert rep.bound >= 3 and rep.annotated >= 3
    # 规则标注：手机号列应被标为 L3（PII）
    pcol = db.execute(
        __import__("sqlalchemy").select(MetaColumn).where(MetaColumn.column_name == "phone_number")
    ).scalar_one()
    assert pcol.pii_level == "L3"
    # 该列应有标准绑定（子串命中 0.72 → suggested/accepted 皆可）
    binds = db.execute(
        __import__("sqlalchemy").select(MetaColumnStandard)
        .join(MetaColumn, MetaColumnStandard.column_id == MetaColumn.id)
        .where(MetaColumn.column_name == "phone_number")
    ).scalars().all()
    assert binds and binds[0].status in (TIER_SUGGESTED, TIER_ACCEPTED)


def test_bind_respects_human_accepted(db):
    source_id = _make_source(db)
    MetaStandardService(db, TENANT_A).seed_builtins()
    tbl = _make_table(db, source_id, "t2", [("phone_number", "varchar", None, "手机号")])
    # 预置一条人工 accepted 绑定
    col = db.execute(
        __import__("sqlalchemy").select(MetaColumn).where(MetaColumn.column_name == "phone_number")
    ).scalar_one()
    human = MetaStandard(tenant_id=TENANT_A, code="std_custom", name="自定义", status="published",
                         aliases_json=["x"])
    db.add(human)
    db.flush()
    db.add(MetaColumnStandard(tenant_id=TENANT_A, column_id=col.id, standard_id=human.id,
                              status=TIER_ACCEPTED, source="human", confidence=0.9))
    db.flush()
    rep = StandardBindingService(db, TENANT_A).bind_table(tbl.id)
    db.commit()
    assert rep.skipped_human == 1
    final = db.execute(
        __import__("sqlalchemy").select(MetaColumnStandard).where(MetaColumnStandard.column_id == col.id)
    ).scalar_one()
    assert final.source == "human" and final.standard_id == human.id


# ── Task 13 三方投票关系推断（集成，无 overlap）────────────────────────────────
def test_vote_key_fk_naming():
    conf, why = _vote_key("id", "PRI", "users", "user_id", None, "orders")
    assert conf == 0.85


def test_vote_name_same_attr():
    conf, _ = _vote_name("created_at", "created_at")
    assert conf == 0.65


def test_infer_relations_persist(db):
    source_id = _make_source(db)
    users = _make_table(db, source_id, "users", [("id", "integer", "PRI", "主键")])
    # 给 users 补一列 created_at，与 orders 同名触发 name 票
    db.add(MetaColumn(tenant_id=TENANT_A, table_id=users.id, column_name="created_at",
                      ordinal=1, data_type="timestamp", column_key=None, column_comment="创建时间"))
    db.flush()
    _make_table(db, source_id, "orders", [
        ("user_id", "integer", None, "用户ID"),
        ("created_at", "timestamp", None, "创建时间"),
    ])
    rep = RelationInferenceService(db, TENANT_A).infer(source_id, with_overlap=False)
    db.commit()
    assert rep.relations >= 1
    key_rel = [d for d in rep.details if d["votes"]["key"] is not None]
    assert key_rel, "应至少有一条键命名法关系"
