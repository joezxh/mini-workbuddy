"""知识库检索设置面板（spec §10.5）+ 换模型重灌。

断言点：
1. 检索设置合并落库、可回读；
2. 未知设置项与维度不一致（D19）直接拒绝；
3. 索引模式降级即时生效、升档返回 ``upgrade_index`` 作业（不在此处执行）；
4. 换嵌入模型返回 ``reembed`` 作业；``reembed_collection`` 覆盖全部向量但跳过父块。
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
from app.services.kb.collection_settings import (
    apply_collection_settings,
    get_retrieval_settings,
)
from app.services.kb.index_mode import reembed_collection, resolve_index_mode

TENANT = 100
DIM = settings.GPUSTACK_EMBEDDING_DIMENSION


def _vec(seed: float) -> list[float]:
    return [seed] + [0.0] * (DIM - 1)


@pytest.fixture
def env(db: Session):
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-set",
                       type=2, kb_format="document", index_mode="high_quality")
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
    db.add(KbDocument(tenant_id=TENANT, uuid_code=uuid_code, knowledge_id=1,
                      collection=coll, name=f"{uuid_code}.md", source_type="upload"))
    for idx, content, ctype in chunks:
        db.add(KbSegment(tenant_id=TENANT, collection=coll, document_id=uuid_code,
                         chunk_index=idx, content=content, embedding=None,
                         chunk_type=ctype))
    db.commit()


def test_settings_roundtrip(db: Session, env):
    """仅改检索参数不触发重灌（嵌入模型未变）。"""
    applied = apply_collection_settings(db, _coll(env), {
        "top_k": 8, "score_threshold": 0.35, "rerank_model": "bge-reranker",
    })
    assert applied["jobs"] == []
    stored = get_retrieval_settings(db, _coll(env))
    assert stored["top_k"] == 8 and stored["score_threshold"] == 0.35
    assert stored["rerank_model"] == "bge-reranker"


def test_settings_rejects_unknown_key(db: Session, env):
    with pytest.raises(ValueError, match="未知设置项"):
        apply_collection_settings(db, _coll(env), {"bogus": 1})


def test_settings_rejects_dimension_mismatch_per_d19(db: Session, env):
    with pytest.raises(ValueError, match="维度"):
        apply_collection_settings(db, _coll(env), {"embedding_dimensions": DIM + 1})


def test_downgrade_applies_immediately(db: Session, env):
    applied = apply_collection_settings(db, _coll(env), {"index_mode": "economy"})
    assert applied["jobs"] == []
    assert applied["index_mode"] == "economy"
    assert resolve_index_mode(db, _coll(env)) == "economy"


def test_upgrade_returns_job_without_executing(db: Session, env):
    downgrade = apply_collection_settings(db, _coll(env), {"index_mode": "economy"})
    assert downgrade["index_mode"] == "economy"
    applied = apply_collection_settings(db, _coll(env), {"index_mode": "high_quality"})
    assert applied["jobs"] == ["upgrade_index"]
    assert applied["index_mode"] == "economy"  # 后台回填完成后才翻标志


def test_same_embedding_model_does_not_trigger_reembed(db: Session, env):
    """与上次配置相同的模型不重复重灌。"""
    apply_collection_settings(db, _coll(env), {"embedding_model": "v1"})
    applied = apply_collection_settings(db, _coll(env), {"embedding_model": "v1"})
    assert applied["jobs"] == []


def test_embedding_model_change_returns_reembed_job(db: Session, env):
    apply_collection_settings(db, _coll(env), {"embedding_model": "v1"})
    applied = apply_collection_settings(db, _coll(env), {"embedding_model": "v2"})
    assert applied["jobs"] == ["reembed"]


def test_reembed_overwrites_vectors_and_skips_parent(db: Session, env):
    coll = _coll(env)
    _add_doc(db, coll, "d1", [(0, "aaaa", "text"), (1, "parent-ctx", "parent")])
    reembed_collection(db, TENANT, env.id, coll, embed_fn=lambda t: [_vec(1.0) for _ in t])

    child = db.execute(
        select(KbSegment).where(KbSegment.chunk_type == "text")
    ).scalar_one()
    assert list(child.embedding) == _vec(1.0)

    # 换模型重灌：已有向量被覆盖，父块保持 NULL
    reembed_collection(db, TENANT, env.id, coll, embed_fn=lambda t: [_vec(9.0) for _ in t])
    db.expire_all()
    child = db.execute(
        select(KbSegment).where(KbSegment.chunk_type == "text")
    ).scalar_one()
    parent = db.execute(
        select(KbSegment).where(KbSegment.chunk_type == "parent")
    ).scalar_one()
    assert list(child.embedding) == _vec(9.0)
    assert parent.embedding is None
