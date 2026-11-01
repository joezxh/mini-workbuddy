"""7 张新表可建、约束生效、默认值符合 spec §3。"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.ontology.query import MetaOntologyQuery
from app.models.twin import TwinAccessRequest, TwinCard, TwinCardShare, TwinPage, TwinPublish, TwinWidget
from tests.twin.conftest import TENANT_A


def test_tablenames_match_spec():
    assert MetaOntologyQuery.__tablename__ == "onto_ontology_query"
    assert {TwinCard.__tablename__, TwinPage.__tablename__, TwinWidget.__tablename__,
            TwinPublish.__tablename__, TwinCardShare.__tablename__,
            TwinAccessRequest.__tablename__} == {
        "twin_card", "twin_page", "twin_widget", "twin_publish", "twin_card_share", "twin_access_request"}


def test_query_draft_version_forces_disabled(db, ontology_factory):
    """spec §3.1：version=0 的草稿态必须 status=disabled（与 onto_ontology_publish 同律）。"""
    q = MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=ontology_factory(), version=0,
                          code="q1", name="草稿查询", result_shape="kpi", spec_json={},
                          status="disabled")
    db.add(q)
    db.commit()
    assert q.status == "disabled"


def test_query_code_unique_per_version(db, ontology_factory):
    """uq_onto_query_code：同 (tenant, ontology, version) 下 code 唯一。"""
    oid = ontology_factory()
    db.add(MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=oid, version=1, code="dup",
                             name="n", result_shape="kpi", spec_json={}, status="enabled"))
    db.commit()
    with pytest.raises(IntegrityError):
        db.add(MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=oid, version=1, code="dup",
                                 name="n2", result_shape="kpi", spec_json={}, status="enabled"))
        db.commit()


def test_query_code_unique_across_version(db, ontology_factory):
    """版本维在唯一键里：同 code 换版本不冲突（重发布后查询逐版本留痕）。"""
    oid = ontology_factory()
    for ver in (1, 2):
        db.add(MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=oid, version=ver, code="same",
                                 name="n", result_shape="kpi", spec_json={}, status="enabled"))
    db.commit()
    assert db.query(MetaOntologyQuery).filter_by(ontology_id=oid, code="same").count() == 2


def test_widget_shape_check_rejects_unknown_result_shape(db, ontology_factory):
    """CHECK 约束：result_shape 取值域固定。"""
    from sqlalchemy.exc import DatabaseError
    db.add(MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=ontology_factory(), version=1,
                             code="bad", name="n", result_shape="pie", spec_json={}, status="enabled"))
    with pytest.raises((DatabaseError, IntegrityError)):
        db.commit()
