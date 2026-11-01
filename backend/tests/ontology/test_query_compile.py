"""查询编译 7 步的失败路径必须逐类可判定（spec §4.1、§7.4、W10）。"""
import pytest

from app.core.api_error import (
    QUERY_COMPILE_FAILED, QUERY_DRAFT_FORBIDDEN, QUERY_JOIN_AMBIGUOUS,
    QUERY_MAPPING_MISSING, QUERY_SENSITIVE_UNCOVERED, QUERY_ELEMENTS_UNREVIEWED,
    QUERY_TOO_MANY_OBJECTS,
)
from app.services.ontology.ontology_query_service import OntologyQueryService

# spec_json 的 attributes 是**标准项 code**（meta_standard.code），不是属性主键
SHAPE_OK = {"objects": ["o_dev"], "attributes": ["a_oee"], "agg": None,
            "group_by": [], "filters": [], "time_window": None, "limit": 100}


def _svc(db):
    from tests.ontology.conftest import TENANT_A
    return OntologyQueryService(db, TENANT_A)


def test_draft_version_cannot_compile(db, seeded_ontology):
    svc = _svc(db)
    q = svc.create(ontology_id=seeded_ontology["id"], version=0, code="q_draft",
                   name="草稿", result_shape="kpi", spec_json=SHAPE_OK)
    with pytest.raises(Exception) as ei:
        svc.compile_query(q["id"])
    assert ei.value.code == QUERY_DRAFT_FORBIDDEN


def test_unreviewed_element_rejected(db, seeded_ontology):
    """② 只认 accepted：引用快照内 review_status != accepted 的属性即拒。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "attributes": ["a_pending"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_unrev",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_ELEMENTS_UNREVIEWED
    assert ei.value.detail["elements"] == ["a_pending"]


def test_missing_table_binding_reports_offenders(db, seeded_ontology):
    """③ 对象已采纳但未绑物理表 → 回传 offender 列表（前端直接列出待映射对象）。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "objects": ["o_nomap"], "attributes": ["a_linecode"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_nomap",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_MAPPING_MISSING
    assert "o_nomap" in ei.value.detail["objects"]


def test_attribute_without_column_binding_rejected(db, seeded_ontology):
    """③′ 属性在该对象表上无 accepted 列绑定 → 同样 fail-closed，不默默丢列。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "attributes": ["a_linecode"]}  # a_linecode 只绑在 o_line 上
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_nocol",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_MAPPING_MISSING
    assert ei.value.detail["attributes"] == ["a_linecode"]


def test_too_many_objects_blocked(db, seeded_ontology):
    svc = _svc(db)
    spec = {**SHAPE_OK, "objects": ["o_dev", "o_line", "o_site"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_many",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_TOO_MANY_OBJECTS


def test_ambiguous_join_returns_candidates(db, seeded_ontology):
    """③′ o_dev↔o_site 在夹具里有两条关系：不指定 join 则不猜，回传候选。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "objects": ["o_dev", "o_site"],
            "attributes": ["a_oee", "a_devcode"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_join",
                   name="n", result_shape="table", spec_json=spec)
    assert ei.value.code == QUERY_JOIN_AMBIGUOUS
    assert sorted(ei.value.detail["candidates"]) == ["r_dev_site_a", "r_dev_site_b"]


def test_sensitive_column_without_mask_rule_blocked(db, seeded_ontology):
    """④ 敏感闸：L2 列且标准无 mask_rule → 拒绝并回传 blocked_columns。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "attributes": ["a_idcard"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_pii",
                   name="n", result_shape="table", spec_json=spec)
    assert ei.value.code == QUERY_SENSITIVE_UNCOVERED
    assert ei.value.detail["blocked_columns"] == ["a_idcard"]


def test_happy_path_compiles_comment_free_single_statement(db, seeded_ontology):
    svc = _svc(db)
    q = svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_ok",
                   name="OEE", result_shape="kpi", spec_json=SHAPE_OK)
    out = svc.compile_query(q["id"])
    assert out["verify_status"] == "verified"
    sql = out["compiled_sql"]
    assert "--" not in sql and "/*" not in sql and sql.count(";") <= 1
    assert sql.startswith("SELECT ")
    assert out["sql_sha256"] and len(out["sql_sha256"]) == 64
    # 执行目标在编译期定死，运行期不再重复解析快照
    assert out["source_id"] == seeded_ontology["source_id"]
    assert seeded_ontology["table"].lower() in sql.lower()


def test_join_path_projects_both_sides(db, seeded_ontology):
    """③′ 成功分支：1 跳 JOIN，ON 由关系的 via 属性解析到两侧列名。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "objects": ["o_dev", "o_line"],
            "attributes": ["a_oee", "a_linecode"], "result_shape": "table"}
    out = svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_j",
                     name="n", result_shape="table", spec_json=spec)
    sql = out["compiled_sql"].lower()
    assert " join " in sql and " on " in sql
    assert sql.count("demo_device_stat") == 1 and "demo_line_stat" in sql


def test_filters_compile_to_placeholders_never_literals(db, seeded_ontology):
    """⑤⑥ 过滤值一律落 :p_n 占位符，并追写进 params_json 供执行期校验。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "filters": [{"attribute": "a_oee", "op": "gt", "value": 0.5}]}
    out = svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_f",
                     name="n", result_shape="kpi", spec_json=spec)
    assert ":p_1" in out["compiled_sql"]
    assert "0.5" not in out["compiled_sql"]
    assert out["params_json"][0]["name"] == "p_1"
    assert out["params_json"][0]["type"] == "float"


def test_illegal_agg_operator_fails_closed(db, seeded_ontology):
    svc = _svc(db)
    spec = {**SHAPE_OK, "agg": {"op": "drop table", "attribute": "a_oee"}}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_agg",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_COMPILE_FAILED


def test_unsupported_dialect_rejected_without_db():
    """⑤ 非 PG 族直接拒编译（§10 U6），而不是编出一句只能跑错的 SQL。"""
    from app.services.ontology.ontology_query_service import _require_supported_dialect

    assert _require_supported_dialect("postgresql") == "postgres"
    for st in ("mysql", "doris"):
        with pytest.raises(Exception) as ei:
            _require_supported_dialect(st)
        assert ei.value.code == QUERY_COMPILE_FAILED


# --------------------------- 端点级（Q1/Q3/Q5）---------------------------


def test_q1_returns_400_with_code_on_sensitive_missing(client_a, seeded_ontology):
    r = client_a.post(f"/api/v1/dataops/ontologies/{seeded_ontology['id']}/queries", json={
        "version": 1, "code": "q_pii", "name": "身份证", "result_shape": "table",
        "spec_json": {"objects": ["o_dev"], "attributes": ["a_idcard"], "limit": 10},
    })
    assert r.status_code == 400
    assert r.json()["code"] == "QUERY_SENSITIVE_UNCOVERED"
    assert "a_idcard" in r.json()["detail"]["blocked_columns"]


def test_q1_happy_then_q3_preview(client_a, seeded_ontology):
    r = client_a.post(f"/api/v1/dataops/ontologies/{seeded_ontology['id']}/queries", json={
        "version": 1, "code": "q_ok", "name": "OEE", "result_shape": "kpi",
        "spec_json": {"objects": ["o_dev"], "attributes": ["a_oee"], "limit": 5},
    })
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    p = client_a.post(f"/api/v1/dataops/queries/{qid}/preview", json={"params": {}, "limit": 5})
    assert p.status_code == 200, p.text
    body = p.json()
    assert body["result_shape"] == "kpi" and "records" in body
    # 预览回写 verified，且编译产物命中缓存键所需的 sql_sha256 已在 Q1 响应里
    assert len(r.json()["sql_sha256"]) == 64


def test_q5_delete_blocked_when_widget_bound(client_a, seeded_ontology, bound_widget):
    r = client_a.delete(f"/api/v1/dataops/queries/{bound_widget['query_id']}")
    assert r.status_code == 409
    assert r.json()["code"] == "WIDGET_IN_USE"
