"""CDM 模型/服务 冒烟（B1）。"""
from sqlalchemy import inspect

TENANT_A = 100


def test_cdm_tables_created(db, engine):
    names = set(inspect(engine).get_table_names())
    for t in [
        "meta_standard_catalog", "meta_object_standard",
        "meta_object_standard_attribute", "meta_object_relation",
        "meta_table_standard", "meta_table_standard_history", "meta_relation_check",
    ]:
        assert t in names, f"{t} 未建出（检查 conftest._tables 登记）"
