"""索引模式升降级（spec §10.2 / §11 / 验收 7）。

断言点：
1. economy → high_quality 回填 NULL 向量并切换 index_mode；
2. 父块（chunk_type='parent'）设计上无向量，不参与回填；
3. 单文档失败不中断整批：失败文档保留 economy 且进报告，修复后可重试；
4. 维度与 collection 不一致按 D19 拒绝（落为文档失败）；
5. 降级仅置标志并保留向量 → 再次升级无需重嵌。
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
from app.services.kb.index_mode import (
    downgrade_to_economy,
    resolve_index_mode,
    resolve_knowledge_id,
    upgrade_to_high_quality,
)

TENANT = 100
# 物理列为 vector(settings.GPUSTACK_EMBEDDING_DIMENSION)，假向量必须同维
DIM = settings.GPUSTACK_EMBEDDING_DIMENSION


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[float(len(t))] + [0.0] * (DIM - 1) for t in texts]


def _bad_embed(texts: list[str]) -> list[list[float]]:
    raise RuntimeError("嵌入服务不可用")


@pytest.fixture
def env(db: Session):
    """economy 知识库 + collection（``kb_{knowledge_id}`` 命名约定）。"""
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-idx",
                       type=2, kb_format="document", index_mode="economy")
    db.add(kn)
    db.commit()
    db.add(KbCollection(tenant_id=TENANT, name=f"kb_{kn.id}",
                        dimensions=DIM, knowledge_id=kn.id))
    db.commit()
    return kn


def _coll(env: WikiKnowledge) -> str:
    return f"kb_{env.id}"


def _add_doc(db: Session, coll: str, uuid_code: str,
             chunks: list[tuple[int, str, str]]):
    """chunks: [(chunk_index, content, chunk_type)]，embedding 均为 NULL。"""
    db.add(KbDocument(tenant_id=TENANT, uuid_code=uuid_code, knowledge_id=1,
                      collection=coll, name=f"{uuid_code}.md", source_type="upload"))
    for idx, content, ctype in chunks:
        db.add(KbSegment(
            tenant_id=TENANT, collection=coll, document_id=uuid_code,
            chunk_index=idx, content=content, embedding=None, chunk_type=ctype,
        ))
    db.commit()


def test_resolve_helpers():
    assert resolve_knowledge_id("kb_7") == 7
    assert resolve_knowledge_id("kb_abc") is None
    assert resolve_knowledge_id("other") is None


def test_upgrade_fills_null_vectors_and_switches_mode(db: Session, env):
    coll = _coll(env)
    _add_doc(db, coll, "d1", [(0, "aaaa", "text"), (1, "bb", "text")])
    report = upgrade_to_high_quality(db, TENANT, env.id, coll, embed_fn=_fake_embed)

    assert report["changed"] is True
    assert report["filled"] == 2 and report["failed"] == []
    assert report["index_mode"] == "high_quality"

    rows = db.execute(
        select(KbSegment).where(KbSegment.collection == coll)
    ).scalars().all()
    assert all(r.embedding is not None for r in rows)
    assert resolve_index_mode(db, coll) == "high_quality"


def test_upgrade_skips_parent_chunks(db: Session, env):
    """父块只存上下文、设计上无向量，不能被回填（spec §10.2）。"""
    coll = _coll(env)
    _add_doc(db, coll, "d1", [(0, "child", "child"), (1, "parent-ctx", "parent")])
    upgrade_to_high_quality(db, TENANT, env.id, coll, embed_fn=_fake_embed)

    parent = db.execute(
        select(KbSegment).where(KbSegment.chunk_type == "parent")
    ).scalar_one()
    child = db.execute(
        select(KbSegment).where(KbSegment.chunk_type == "child")
    ).scalar_one()
    assert parent.embedding is None
    assert child.embedding is not None


def test_upgrade_keeps_economy_when_doc_fails(db: Session, env):
    coll = _coll(env)
    _add_doc(db, coll, "d1", [(0, "aaaa", "text")])
    report = upgrade_to_high_quality(db, TENANT, env.id, coll, embed_fn=_bad_embed)

    assert report["changed"] is False
    assert report["index_mode"] == "economy"     # 失败文档仍可走关键词分支
    assert report["failed"][0]["document_id"] == "d1"
    assert resolve_index_mode(db, coll) == "economy"

    # 修复后重试成功 → 切换
    retry = upgrade_to_high_quality(db, TENANT, env.id, coll, embed_fn=_fake_embed)
    assert retry["changed"] is True and retry["index_mode"] == "high_quality"


def test_upgrade_rejects_dimension_mismatch_per_d19(db: Session, env):
    coll = _coll(env)
    _add_doc(db, coll, "d1", [(0, "aaaa", "text")])
    report = upgrade_to_high_quality(
        db, TENANT, env.id, coll,
        embed_fn=lambda texts: [[0.0] * (DIM + 1) for _ in texts],
    )
    assert report["changed"] is False
    assert "维度" in report["failed"][0]["error"]


def test_downgrade_keeps_vectors_and_upgrade_is_instant(db: Session, env):
    coll = _coll(env)
    _add_doc(db, coll, "d1", [(0, "aaaa", "text")])
    upgrade_to_high_quality(db, TENANT, env.id, coll, embed_fn=_fake_embed)

    down = downgrade_to_economy(db, env.id)
    assert down["changed"] is True and down["index_mode"] == "economy"
    assert db.execute(select(KbSegment)).scalar_one().embedding is not None  # 保留向量

    # 再升级：无待回填切片 → 仅翻标志（embed 故意不可用也不受影响）
    again = upgrade_to_high_quality(db, TENANT, env.id, coll, embed_fn=_bad_embed)
    assert again["changed"] is True and again["filled"] == 0


def test_upgrade_noop_when_already_high_quality(db: Session, env):
    coll = _coll(env)
    _add_doc(db, coll, "d1", [(0, "aaaa", "text")])
    upgrade_to_high_quality(db, TENANT, env.id, coll, embed_fn=_fake_embed)
    again = upgrade_to_high_quality(db, TENANT, env.id, coll, embed_fn=_bad_embed)
    assert again["changed"] is False and again["index_mode"] == "high_quality"
