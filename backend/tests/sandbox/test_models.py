"""沙箱域 9 表模型测试（Task 1）：CHECK 生效、租户隔离、部分唯一索引两段式、种子存在。"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.ontology.ontology import MetaOntology
from app.models.sandbox.sandbox import (
    SandboxBranch, SandboxCheckpoint, SandboxEntity, SandboxObservation,
    SandboxScene,
)
from tests.sandbox.conftest import TENANT_A, TENANT_B


def _ontology_id(db):
    o = MetaOntology(tenant_id=TENANT_A, code="O1", name="汽车零部件供应链", status="published",
                     current_version=1)
    db.add(o)
    db.flush()
    return o.id


def _scene(db, tenant_id=TENANT_A, **kw):
    s = SandboxScene(tenant_id=tenant_id, ontology_id=_ontology_id(db), ontology_version=1,
                     name=kw.pop("name", "a场景"), **kw)
    db.add(s)
    db.flush()
    return s


def test_scene_crud_and_tenant_isolation(db):
    s = _scene(db)
    db.commit()
    got = db.execute(select(SandboxScene).where(SandboxScene.tenant_id == TENANT_B)).scalar()
    assert got is None and s.id is not None  # B 租户读不到 A 的场景


def test_scene_exec_mode_check(db):
    with pytest.raises(IntegrityError):
        _scene(db, exec_mode="turbo")
    db.rollback()


def test_scene_status_check(db):
    with pytest.raises(IntegrityError):
        _scene(db, status="paused")
    db.rollback()


def test_entity_partial_unique_two_phase(db):
    """当前态两段式：同分支两行当前态同 code 冲突；快照行按 (checkpoint_id, code) 唯一。"""
    s = _scene(db)
    br = SandboxBranch(tenant_id=TENANT_A, scene_id=s.id, name="基线分支")
    db.add(br)
    db.flush()
    cp = SandboxCheckpoint(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id,
                           tick=0, seq=0, label="基线快照")
    db.add(cp)
    db.flush()
    db.add(SandboxEntity(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id,
                         entity_code="SUP001", object_code="Supplier"))
    db.flush()
    db.add(SandboxEntity(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id,
                         entity_code="SUP001", object_code="Supplier"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()

    s = _scene(db, name="b场景")
    br = SandboxBranch(tenant_id=TENANT_A, scene_id=s.id, name="基线分支B")
    db.add_all([br])
    db.flush()
    cp1 = SandboxCheckpoint(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id, tick=0, seq=1, label="cp1")
    cp2 = SandboxCheckpoint(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id, tick=1, seq=2, label="cp2")
    db.add_all([cp1, cp2])
    db.flush()
    # 不同检查点下同 code 快照行允许共存
    db.add_all([
        SandboxEntity(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id, checkpoint_id=cp1.id,
                      entity_code="SUP001", object_code="Supplier"),
        SandboxEntity(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id, checkpoint_id=cp2.id,
                      entity_code="SUP001", object_code="Supplier"),
    ])
    db.flush()
    # 同一检查点内重复即冲突
    db.add(SandboxEntity(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id, checkpoint_id=cp1.id,
                         entity_code="SUP001", object_code="Supplier"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_observation_kind_check(db):
    s = _scene(db, name="c场景")
    br = SandboxBranch(tenant_id=TENANT_A, scene_id=s.id, name="分支C")
    db.add_all([br])
    db.flush()
    db.add(SandboxObservation(tenant_id=TENANT_A, scene_id=s.id, branch_id=br.id, tick=1,
                              kind="not_a_kind", title="x"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_action_templates_seeded(db):
    from app.models.sandbox.action_template import SandboxActionTemplate
    codes = {t.code for t in db.execute(select(SandboxActionTemplate)).scalars()}
    assert {"supply_cut", "delay", "price_up", "reroute"} <= codes
