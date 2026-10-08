"""分段详情服务（spec §10.5）：单段读写 / 关键词 / 引用来源。

断言点：
1. 改文本后 high_quality 库重嵌（索引与内容一致），economy 库与父块不嵌；
2. 关键词按 D14 同时落 metadata 与冗余列，且不触发重嵌；
3. 删除分段即删除向量记录（无第二处存储）；
4. 引用来源返回来源文档 + 父块 + 子块 + 同文档切片数；
5. 跨租户/不存在分段显式失败。
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
from app.services.kb.segment_service import (
    delete_segment,
    get_citations,
    get_segment,
    list_document_segments,
    update_keywords,
    update_segment,
)

TENANT = 100
OTHER_TENANT = 200
DIM = settings.GPUSTACK_EMBEDDING_DIMENSION


def _vec(seed: float) -> list[float]:
    return [seed] + [0.0] * (DIM - 1)


@pytest.fixture
def env(db: Session):
    """high_quality 知识库 + collection + 文档 + 父子切片。"""
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-seg",
                       type=2, kb_format="document", index_mode="high_quality")
    db.add(kn)
    db.commit()
    db.add(KbCollection(tenant_id=TENANT, name=f"kb_{kn.id}",
                        dimensions=DIM, knowledge_id=kn.id))
    db.add(KbDocument(tenant_id=TENANT, uuid_code="doc1", knowledge_id=kn.id,
                      collection=f"kb_{kn.id}", name="a.md", source_type="upload",
                      status="completed"))
    db.commit()
    return kn


def _coll(env: WikiKnowledge) -> str:
    return f"kb_{env.id}"


def _add_segment(db: Session, coll: str, *, idx: int, content: str,
                 ctype: str = "text", parent_id=None, embedding=None) -> KbSegment:
    seg = KbSegment(tenant_id=TENANT, collection=coll, document_id="doc1",
                    chunk_index=idx, content=content, chunk_type=ctype,
                    parent_id=parent_id, embedding=embedding)
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


def test_update_content_reembeds_in_high_quality(db: Session, env):
    seg = _add_segment(db, _coll(env), idx=0, content="原文", embedding=_vec(1.0))
    updated = update_segment(db, TENANT, seg.id, content="改后文本",
                             embed_fn=lambda t: [_vec(2.0) for _ in t])
    assert updated.content == "改后文本"
    assert list(updated.embedding) == _vec(2.0)   # 索引随内容更新


def test_update_content_skips_embedding_in_economy(db: Session, env):
    env.index_mode = "economy"
    db.commit()
    seg = _add_segment(db, _coll(env), idx=0, content="原文")
    updated = update_segment(db, TENANT, seg.id, content="改后",
                             embed_fn=lambda t: [_vec(2.0) for _ in t])
    assert updated.embedding is None              # D11：economy 不消耗 embedding


def test_update_content_skips_parent_chunk(db: Session, env):
    seg = _add_segment(db, _coll(env), idx=0, content="父块", ctype="parent")
    updated = update_segment(db, TENANT, seg.id, content="父块改",
                             embed_fn=lambda t: [_vec(2.0) for _ in t])
    assert updated.embedding is None              # 父块设计上无向量（§10.2）


def test_keywords_update_projects_to_column_without_reembed(db: Session, env):
    seg = _add_segment(db, _coll(env), idx=0, content="原文", embedding=_vec(1.0))
    updated = update_keywords(db, TENANT, seg.id, ["退款", "时效"])

    assert updated.keywords == ["退款", "时效"]                 # 冗余列（SQL 过滤）
    assert updated.metadata_["keywords"] == ["退款", "时效"]     # D14：写入源
    assert list(updated.embedding) == _vec(1.0)                # 关键词不触发重嵌


def test_delete_removes_vector_record(db: Session, env):
    seg = _add_segment(db, _coll(env), idx=0, content="原文", embedding=_vec(1.0))
    delete_segment(db, TENANT, seg.id)
    assert db.execute(select(KbSegment)).scalars().all() == []


def test_citations_return_document_parent_and_children(db: Session, env):
    coll = _coll(env)
    parent = _add_segment(db, coll, idx=0, content="父块上下文", ctype="parent")
    child = _add_segment(db, coll, idx=1, content="子块", ctype="child",
                         parent_id=parent.id)
    _add_segment(db, coll, idx=2, content="另一子块", ctype="child", parent_id=parent.id)

    cites = get_citations(db, TENANT, child.id)
    assert cites["document"]["document_id"] == "doc1"
    assert cites["document"]["name"] == "a.md"
    assert cites["parent"]["id"] == parent.id
    assert cites["sibling_count"] == 3

    parent_cites = get_citations(db, TENANT, parent.id)
    assert [c["chunk_index"] for c in parent_cites["children"]] == [1, 2]


@pytest.mark.parametrize("op", ["update", "keywords", "delete", "citations"])
def test_operations_reject_foreign_or_missing_segment(db: Session, env, op):
    seg = _add_segment(db, _coll(env), idx=0, content="原文")
    calls = {
        "update": lambda t, i: update_segment(db, t, i, content="x"),
        "keywords": lambda t, i: update_keywords(db, t, i, ["k"]),
        "delete": lambda t, i: delete_segment(db, t, i),
        "citations": lambda t, i: get_citations(db, t, i),
    }
    with pytest.raises(ValueError, match="分段不存在"):
        calls[op](OTHER_TENANT, seg.id)   # 跨租户
    with pytest.raises(ValueError, match="分段不存在"):
        calls[op](TENANT, seg.id + 9999)  # 不存在


def test_list_document_segments_paged_and_filtered(db: Session, env):
    coll = _coll(env)
    _add_segment(db, coll, idx=0, content="t1", ctype="text")
    _add_segment(db, coll, idx=1, content="r1", ctype="table_row")
    _add_segment(db, coll, idx=2, content="t2", ctype="text")

    listed = list_document_segments(db, TENANT, "doc1")
    assert listed["total"] == 3 and len(listed["items"]) == 3
    # chunk_index 升序，父块优先展示
    assert [i["chunk_index"] for i in listed["items"]] == [0, 1, 2]

    filtered = list_document_segments(db, TENANT, "doc1", chunk_type="text")
    assert filtered["total"] == 2
    assert all(i["chunk_type"] == "text" for i in filtered["items"])

    paged = list_document_segments(db, TENANT, "doc1", page=2, page_size=2)
    assert paged["page"] == 2 and len(paged["items"]) == 1


def test_list_document_segments_rejects_other_tenant(db: Session, env):
    _add_segment(db, _coll(env), idx=0, content="t1")
    # 空列表而非报错：列表是过滤语义，不存在不属异常
    assert list_document_segments(db, OTHER_TENANT, "doc1")["total"] == 0


def test_get_segment_returns_none_for_other_tenant(db: Session, env):
    seg = _add_segment(db, _coll(env), idx=0, content="原文")
    assert get_segment(db, TENANT, seg.id) is not None
    assert get_segment(db, OTHER_TENANT, seg.id) is None
