"""本体领域表结构校验（纯元数据，不连库）。"""
from app.models.dataops.meta import MetaTable
from app.models.ontology.domain import OntoDomain
from app.models.ontology.ontology import MetaOntology


def test_onto_domain_table_shape() -> None:
    assert OntoDomain.__tablename__ == "onto_domain"
    cols = OntoDomain.__table__.columns
    assert set(["id", "tenant_id", "code", "name", "description",
                "sort_order", "status", "creator_id", "updater_id",
                "created_at", "updated_at"]).issubset(cols.keys())
    assert cols["code"].nullable is False
    assert cols["name"].nullable is False
    assert cols["status"].server_default.arg == "active"
    assert cols["sort_order"].server_default.arg == "0"

    constraint_names = {c.name for c in OntoDomain.__table__.constraints}
    assert "uq_onto_domain_code" in constraint_names
    assert "ck_onto_domain_status" in constraint_names
    index_names = {i.name for i in OntoDomain.__table__.indexes}
    assert "idx_onto_domain_tenant_status" in index_names


def test_domain_id_fks() -> None:
    for model, expected_index in (
        (MetaTable, "idx_meta_table_domain_id"),
        (MetaOntology, "idx_onto_ontology_tenant_domain"),
    ):
        col = model.__table__.columns["domain_id"]
        assert col.nullable is True
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "onto_domain.id"
        assert fks[0].ondelete == "SET NULL"
        assert expected_index in {i.name for i in model.__table__.indexes}

    # 原 domain 字符串列必须保留
    assert MetaTable.__table__.columns["domain"].type.length == 64
