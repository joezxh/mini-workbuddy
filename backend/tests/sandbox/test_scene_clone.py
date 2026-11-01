"""Task 3：场景生命周期 + 克隆链路测试（钉版校验 / SQL 计划纯函数 / 端到端假取数克隆）。"""
from sqlalchemy import select

from app.models.dataops.data_source import DataSource
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.standard import MetaStandard
from app.models.ontology.ontology import (
    MetaOntology, MetaOntologyPublish, MetaOntologyVersion,
)
from app.models.sandbox.sandbox import (
    SandboxBranch, SandboxCheckpoint, SandboxEntity,
)
from app.services.sandbox.sandbox_clone_service import SandboxCloneService
from tests.sandbox.conftest import TENANT_A


def _seed_published_ontology(db):
    """建已发布本体 + 版本快照（Supplier 对象，映射 dwd_supp_item 两列，含一敏感列）+ 应用登记。"""
    on = MetaOntology(tenant_id=TENANT_A, code="O_SUP", name="汽车零部件供应链",
                      status="published", current_version=1)
    db.add(on)
    db.flush()
    snapshot = {
        "objects": [{"id": 11, "code": "Supplier", "name": "供应商"}],
        "properties": [{"id": 1, "object_id": 11, "standard_id": 201, "required": False},
                       {"id": 2, "object_id": 11, "standard_id": 202, "required": False}],
        "relations": [],
        "mappings": {
            "table": [{"id": 1, "table_id": 1, "object_standard_id": 11, "source": "std"}],
            "column": [{"id": 1, "column_id": 101, "standard_id": 201, "source": "std"},
                       {"id": 2, "column_id": 102, "standard_id": 202, "source": "std"}],
        },
    }
    db.add(MetaOntologyVersion(tenant_id=TENANT_A, ontology_id=on.id, version=1,
                               snapshot_json=snapshot))
    ds = DataSource(tenant_id=TENANT_A, name="dwh", source_type="postgresql",
                    host="localhost", port=5432, database="dwh")
    db.add(ds)
    db.flush()
    tbl = MetaTable(tenant_id=TENANT_A, source_id=ds.id, db_name="dwh", database="dwh",
                    table_name="dwd_supp_item")
    db.add(tbl)
    db.flush()
    db.add_all([
        MetaColumn(tenant_id=TENANT_A, id=101, table_id=tbl.id, column_name="supp_name"),
        MetaColumn(tenant_id=TENANT_A, id=102, table_id=tbl.id, column_name="mobile", pii_level="L3"),
    ])
    db.add_all([
        MetaStandard(tenant_id=TENANT_A, id=201, code="name", name="名称"),
        MetaStandard(tenant_id=TENANT_A, id=202, code="mobile", name="手机号",
                     mask_rule="mask_left(mobile,3,4)"),
    ])
    db.add(MetaOntologyPublish(tenant_id=TENANT_A, ontology_id=on.id, version=1,
                               target_type="skill", code="sk1", status="enabled"))
    db.commit()
    return on.id


# 用真实映射表 id（seed 里 MetaTable 自增，可能非 1）：build_select 走 db 查 MetaTable，
# 快照内 table_id=1 需与实际 MetaTable.id 对齐——故在纯函数测试里用同一 id 断言。

def test_create_scene_requires_published(db, client_a):
    r = client_a.post("/api/v1/dataops/ontologies/sandbox/scenes",
                      json={"ontology_id": 999, "name": "断供传导", "clone_scope": {}})
    assert r.status_code == 404 and r.json()["code"] == "ONTOLOGY_NOT_FOUND"


def test_create_scene_ok(db, client_a):
    oid = _seed_published_ontology(db)
    r = client_a.post("/api/v1/dataops/ontologies/sandbox/scenes",
                      json={"ontology_id": oid, "name": "断供传导",
                            "clone_scope": {"object_codes": ["Supplier"]}})
    assert r.status_code == 201 and r.json()["status"] == "draft"
    sid = r.json()["scene_id"]
    # 基线分支已建
    br = db.execute(select(SandboxBranch).where(SandboxBranch.scene_id == sid)).scalar_one()
    assert br.name == "基线分支" and br.base_checkpoint_id is None


def test_build_select_masks_sensitive_columns_in_sql(db):
    _seed_published_ontology(db)
    tbl = db.execute(select(MetaTable).where(MetaTable.tenant_id == TENANT_A)).scalar_one()
    snapshot = {
        "objects": [{"id": 11, "code": "Supplier", "name": "供应商"}],
        "properties": [{"id": 1, "object_id": 11, "standard_id": 201},
                       {"id": 2, "object_id": 11, "standard_id": 202}],
        "mappings": {
            "table": [{"id": 1, "table_id": tbl.id, "object_standard_id": 11}],
            "column": [{"id": 1, "column_id": 101, "standard_id": 201},
                       {"id": 2, "column_id": 102, "standard_id": 202}],
        },
    }
    svc = SandboxCloneService(db, TENANT_A)
    built = svc.build_select(snapshot, "Supplier", {"max_entities": 500})
    assert built is not None
    sql, meta = built
    assert f'FROM "{tbl.database}"."{tbl.table_name}"' in sql
    assert '"supp_name"' in sql
    assert "'***' AS mobile" in sql          # 脱敏在字面量层，明文不出源库（V4/A3）
    assert meta["masked_columns"] == ["mobile"]
    assert "DELETE" not in sql.upper() and sql.upper().startswith("SELECT")


def test_clone_with_fake_fetcher(db):
    oid = _seed_published_ontology(db)
    from app.services.sandbox.sandbox_scene_service import SandboxSceneService
    res = SandboxSceneService(db, TENANT_A).create_scene(
        ontology_id=oid, name="断供传导", clone_scope={"object_codes": ["Supplier"]})
    sid = res["scene_id"]
    # create_scene 会 submit_clone（后台线程走真实 fetcher → 因无源库落 failed）；
    # 测试用注入 fetcher 直接同步克隆，先把状态复位到 draft
    scene = db.get(_scene_model(), sid)
    scene.status = "draft"
    db.commit()

    fake_rows = {"columns": ["supp_name", "mobile"],
                 "rows": [["甲厂", "明文不应出现"], ["乙厂", "138xxxx"], ["丙厂", "139xxxx"]],
                 "row_count": 3, "truncated": False}

    def fake_fetcher(source_id, sql, limit):
        # 服务必须在 SELECT 层已把 mobile 替换为 '***'，取数结果直接返回脱敏列
        return {"columns": ["supp_name", "mobile"],
                "rows": [["甲厂", "***"], ["乙厂", "***"], ["丙厂", "***"]],
                "row_count": 3, "truncated": False}

    clone = SandboxCloneService(db, TENANT_A, fetcher=fake_fetcher)
    clone.clone_scene(sid)

    br = db.execute(select(SandboxBranch).where(SandboxBranch.scene_id == sid)).scalar_one()
    cur = db.execute(select(SandboxEntity).where(
        SandboxEntity.branch_id == br.id, SandboxEntity.checkpoint_id.is_(None))).scalars().all()
    assert len(cur) == 3
    assert all(e.masked is True for e in cur)         # mobile 命中脱敏 → masked=True
    assert all(e.props_json["mobile"] == "***" for e in cur)
    # 基线检查点 seq=0 + 快照行 3 条
    cps = db.execute(select(SandboxCheckpoint).where(SandboxCheckpoint.scene_id == sid)).scalars().all()
    assert len(cps) == 1 and cps[0].seq == 0
    snap = db.execute(select(SandboxEntity).where(
        SandboxEntity.checkpoint_id == cps[0].id)).scalars().all()
    assert len(snap) == 3
    # 幂等：再调一次不重复（status 已 running）
    clone.clone_scene(sid)
    cur2 = db.execute(select(SandboxEntity).where(
        SandboxEntity.branch_id == br.id, SandboxEntity.checkpoint_id.is_(None))).scalars().all()
    assert len(cur2) == 3


def _scene_model():
    from app.models.sandbox.sandbox import SandboxScene
    return SandboxScene
