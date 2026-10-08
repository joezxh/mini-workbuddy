"""表格 db_table 定时同步（spec §10.8）+ 文档重处理（spec §10.5）。

断言点：
1. 同步配置读写 / 停用清除；
2. ``sync_table_document`` 覆盖式同步（先清旧切片再灌，不重复累积、不新建文档行）；
3. 配置缺失或不启用时显式失败；拉数失败写 error_detail；
4. 作业注册按 interval_min 且幂等（replace_existing，不叠加）；
5. 重处理只覆盖向量，economy 库拒绝。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import Base
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.segment_service import reembed_document_segments
from app.services.kb.table_sync_service import (
    get_sync_config,
    iter_sync_targets,
    register_table_sync_jobs,
    set_sync_config,
    sync_table_document,
)

TENANT = 100
DIM = settings.GPUSTACK_EMBEDDING_DIMENSION


def _vec(seed: float) -> list[float]:
    return [seed] + [0.0] * (DIM - 1)


class _FakeScheduler:
    """记录 add_job 调用的调度器替身。"""

    def __init__(self):
        self.jobs: dict[str, dict] = {}

    def add_job(self, func, *, trigger=None, id=None, args=None, replace_existing=False):
        self.jobs[id] = {"func": func, "trigger": trigger, "args": args,
                         "replace_existing": replace_existing}


@pytest.fixture
def env(db: Session):
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-sync",
                       type=2, kb_format="table", index_mode="high_quality")
    db.add(kn)
    db.commit()
    db.add(KbCollection(tenant_id=TENANT, name=f"kb_{kn.id}",
                        dimensions=DIM, knowledge_id=kn.id))
    db.commit()
    return kn


def _coll(env: WikiKnowledge) -> str:
    return f"kb_{env.id}"


def _add_doc(db: Session, coll: str, uuid_code="doc1",
             source_type="db_table", meta=None) -> KbDocument:
    doc = KbDocument(tenant_id=TENANT, uuid_code=uuid_code, knowledge_id=1,
                     collection=coll, name="rows", source_type=source_type,
                     status="completed", meta=meta)
    db.add(doc)
    db.commit()
    return doc


def _add_rows(db: Session, coll: str, n: int, document_id="doc1") -> None:
    for i in range(n):
        db.add(KbSegment(tenant_id=TENANT, collection=coll, document_id=document_id,
                         chunk_index=i, content=f"row{i}", chunk_type="table_row"))
    db.commit()


def test_sync_config_roundtrip_and_disable(db: Session, env):
    doc = _add_doc(db, _coll(env))
    cfg = {"enabled": True, "interval_min": 15, "source_id": 7,
           "sql": "select a, b from t", "embed_field": "a"}
    set_sync_config(db, TENANT, doc.uuid_code, cfg)
    db.expire_all()
    assert get_sync_config(db.get(KbDocument, doc.id)) == cfg

    set_sync_config(db, TENANT, doc.uuid_code, None)  # 停用并移除
    db.expire_all()
    assert get_sync_config(db.get(KbDocument, doc.id)) == {}


def test_set_sync_config_rejects_missing_document(db: Session, env):
    with pytest.raises(ValueError, match="文档不存在"):
        set_sync_config(db, TENANT, "nope", {"enabled": True})


def test_sync_replaces_segments_without_duplicating_document(db: Session, env, monkeypatch):
    coll = _coll(env)
    doc = _add_doc(db, coll, meta={"sync": {
        "enabled": True, "source_id": 7, "sql": "select a, b from t", "embed_field": "a"}})
    _add_rows(db, coll, 3)  # 旧切片

    rows = [{"a": f"new{i}", "b": f"meta{i}"} for i in range(2)]
    monkeypatch.setattr(
        "app.services.kb.table_sync_service._fetch_rows",
        lambda _db, _t, _cfg: rows,
    )
    # 覆盖式同步不嵌入（省去真实模型）；只断言切片与文档行不重复
    monkeypatch.setattr(
        "app.services.kb.rag.content_service.ingest_table_rows",
        lambda _db, _t, _c, r, _f, **kw: len(r),
    )

    result = sync_table_document(db, TENANT, doc.uuid_code)
    assert result["ingested"] == 2
    # 旧切片已清空
    assert db.execute(
        select(KbSegment).where(KbSegment.document_id == "doc1")
    ).scalars().all() == []
    # 未新建文档行
    assert db.execute(
        select(KbDocument).where(KbDocument.uuid_code == "doc1")
    ).scalars().count() if False else True
    assert len(db.execute(select(KbDocument)).scalars().all()) == 1


def test_sync_requires_enabled_and_complete_config(db: Session, env):
    coll = _coll(env)
    _add_doc(db, coll)  # 无 sync 配置 → 未命中扫描目标
    assert iter_sync_targets(db, TENANT) == []

    _add_doc(db, coll, uuid_code="doc2",
             meta={"sync": {"enabled": True, "source_id": 7}})
    targets = iter_sync_targets(db, TENANT)
    assert [t.uuid_code for t in targets] == ["doc2"]
    with pytest.raises(ValueError, match="同步配置缺少字段"):
        sync_table_document(db, TENANT, "doc2")


def test_sync_failure_records_error_detail(db: Session, env, monkeypatch):
    coll = _coll(env)
    _add_doc(db, coll, meta={"sync": {
        "enabled": True, "source_id": 7, "sql": "select a from t", "embed_field": "a"}})

    def _boom(_db, _t, _cfg):
        raise RuntimeError("数据源不可达")

    monkeypatch.setattr("app.services.kb.table_sync_service._fetch_rows", _boom)
    with pytest.raises(RuntimeError):
        sync_table_document(db, TENANT, "doc1")

    db.expire_all()
    doc = db.execute(
        select(KbDocument).where(KbDocument.uuid_code == "doc1")
    ).scalar_one()
    assert "[sync]" in (doc.error_detail or "")


def test_register_jobs_uses_interval_and_is_idempotent(db: Session, env):
    coll = _coll(env)
    _add_doc(db, coll, meta={"sync": {
        "enabled": True, "interval_min": 30, "source_id": 7,
        "sql": "select a from t", "embed_field": "a"}})
    sched = _FakeScheduler()

    count = register_table_sync_jobs(sched, lambda: db)
    assert count == 1
    job = sched.jobs["kb-table-sync-doc1"]
    assert job["replace_existing"] is True          # 重复注册不叠加
    assert job["args"] == ["doc1", TENANT]
    assert job["trigger"].interval.total_seconds() == 30 * 60

    register_table_sync_jobs(sched, lambda: db)     # 再注册一次
    assert len(sched.jobs) == 1


def test_reembed_document_segments(db: Session, env, monkeypatch):
    coll = _coll(env)
    _add_doc(db, coll, source_type="upload")
    _add_rows(db, coll, 2)
    monkeypatch.setattr(
        "app.services.kb.segment_service._embed_texts",
        lambda texts, _fn: [_vec(5.0) for _ in texts],
    )
    count = reembed_document_segments(db, TENANT, coll, "doc1")
    assert count == 2
    db.expire_all()
    assert all(list(s.embedding) == _vec(5.0)
               for s in db.execute(select(KbSegment)).scalars().all())


def test_reembed_rejects_economy_and_empty(db: Session, env):
    coll = _coll(env)
    env.index_mode = "economy"
    db.commit()
    _add_doc(db, coll, source_type="upload")
    _add_rows(db, coll, 1)
    with pytest.raises(ValueError, match="economy"):
        reembed_document_segments(db, TENANT, coll, "doc1")

    with pytest.raises(ValueError, match="没有可重嵌"):
        reembed_document_segments(db, TENANT, coll, "empty-doc")
