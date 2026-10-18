"""表格知识库：多集合命名兼容 + 一行一段 CSV 切分 + 未选集合自动建集合。

覆盖本次改造的三个核心语义：
1. 集合名 ``kb_{kid}_{slug}`` 仍能被 ``resolve_knowledge_id`` 反查（兼容既有链路）；
2. 每行一段，``content`` 是「向量化字段组合」拼成的 CSV 行（逗号间隔、RFC4180 转义）；
3. 上传未选择集合时自动在知识库下新建集合并自动生成字段定义（默认全字段向量化）。
"""
from __future__ import annotations

import pytest

from app.db.database import Base
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.collection_service import (
    create_knowledge_collection,
    list_knowledge_collections,
    slugify,
    validate_collection_ownership,
)
from app.services.kb.index_mode import resolve_knowledge_id
from app.services.kb.rag.chunker_factory import build_table_row_chunks
from app.services.kb.rag.content_service import import_table_file
from app.services.kb.table_schema import embedding_fields, get_schema_fields

TENANT = 100
CSV = "商品,价格\n防水低价,9\nAAA,12\n"


# ── 1. 集合命名兼容 ──────────────────────────────────────────────────────

def test_resolve_knowledge_id_supports_multi_collection_names():
    # 文档库沿用 kb_{kid}
    assert resolve_knowledge_id("kb_7") == 7
    # 表格库多集合：kb_{kid}_{slug}
    assert resolve_knowledge_id("kb_7_sales") == 7
    assert resolve_knowledge_id("kb_7_sales_2026") == 7
    # 非约定命名 / 空值
    assert resolve_knowledge_id("sales") is None
    assert resolve_knowledge_id("kb_") is None
    assert resolve_knowledge_id("") is None


def test_slugify_falls_back_for_non_ascii():
    assert slugify("订单表.csv") == "csv"        # 仅保留 ascii 部分（中文被过滤）
    assert slugify("订单表") == "c"              # 全中文 → 回落 c
    assert slugify("Sales Report") == "sales-report"
    assert slugify("") == "c"


def test_create_knowledge_collection_naming_and_uniqueness(db):
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-multi", type=2, kb_format="table")
    db.add(kn)
    db.commit()

    first = create_knowledge_collection(db, TENANT, kn.id, slug="sales")
    assert first.name == f"kb_{kn.id}_sales"
    assert first.knowledge_id == kn.id

    # 同名 slug 自动加序号，避免唯一键冲突
    second = create_knowledge_collection(db, TENANT, kn.id, slug="sales")
    assert second.name == f"kb_{kn.id}_sales-2"
    db.commit()


def test_list_knowledge_collections_and_ownership(db):
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-list", type=2, kb_format="table")
    other = WikiKnowledge(tenant_id=TENANT, name="other", slug="kb-other", type=2, kb_format="table")
    db.add_all([kn, other])
    db.commit()

    create_knowledge_collection(db, TENANT, kn.id, slug="a")
    create_knowledge_collection(db, TENANT, kn.id, slug="b")
    create_knowledge_collection(db, TENANT, other.id, slug="c")
    db.commit()

    assert len(list_knowledge_collections(db, TENANT, kn.id)) == 2
    assert len(list_knowledge_collections(db, TENANT, other.id)) == 1

    # 跨知识库使用集合 → 拒绝
    foreign = list_knowledge_collections(db, TENANT, other.id)[0]
    with pytest.raises(ValueError, match="不属于知识库"):
        validate_collection_ownership(db, foreign, kn.id)
    # 同知识库 → 通过
    validate_collection_ownership(db, list_knowledge_collections(db, TENANT, kn.id)[0], kn.id)


# ── 2. 一行一段 CSV 切分 ─────────────────────────────────────────────────

def test_build_table_row_chunks_single_field():
    chunks = build_table_row_chunks([{"商品": "A", "价格": 9}], embed_fields=["商品"])
    assert chunks[0].content.text == "A"
    assert chunks[0].metadata["价格"] == 9
    assert chunks[0].metadata["chunk_type"] == "table_row"


def test_build_table_row_chunks_multi_field_csv_line():
    """每行一段：向量化字段组合按逗号拼成 CSV 行（content 即向量化内容）。"""
    chunks = build_table_row_chunks(
        [{"商品": "防水低价", "价格": 9, "品牌": "X"}, {"商品": "AAA", "价格": 12, "品牌": "Y"}],
        embed_fields=["商品", "价格"],
    )
    assert chunks[0].content.text == "防水低价,9"
    assert chunks[1].content.text == "AAA,12"
    assert len(chunks) == 2
    # 一行一段
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_build_table_row_chunks_escapes_csv_special_chars():
    """值含逗号/引号时按 RFC4180 转义，保证「一行一段」可被解析回原值。"""
    import csv
    import io

    chunks = build_table_row_chunks(
        [{"a": "含,逗号", "b": '含"引号'}],
        embed_fields=["a", "b"],
    )
    line = chunks[0].content.text
    parsed = next(csv.reader(io.StringIO(line)))
    assert parsed == ["含,逗号", '含"引号']


def test_build_table_row_chunks_keeps_all_fields_in_metadata():
    """metadata 保留该行全部字段，便于按集合字段定义回显记录与过滤。"""
    chunks = build_table_row_chunks([{"a": 1, "b": 2}], embed_fields=["a"])
    assert chunks[0].metadata["a"] == 1
    assert chunks[0].metadata["b"] == 2


def test_build_table_row_chunks_legacy_embed_field_kwarg():
    """兼容旧调用：``embed_field="列名"`` 关键字（单字段组合）。"""
    chunks = build_table_row_chunks([{"a": 1, "b": 2}], embed_field="b")
    assert chunks[0].content.text == "2"


# ── 3. 未选集合 → 自动建集合 + 全字段向量化 ──────────────────────────────

def test_import_auto_creates_collection_when_not_selected(db, monkeypatch):
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-auto", type=2, kb_format="table")
    db.add(kn)
    db.commit()

    calls = []

    def _fake(_session_factory, **kwargs):
        calls.append({"chunks": kwargs["chunks"], "document_id": kwargs["document_id"]})

    monkeypatch.setattr("app.services.kb.rag.content_service._insert_via_kb", _fake)

    res = import_table_file(
        db, TENANT, "", CSV.encode("utf-8-sig"), "价格表.csv",
        knowledge_id=kn.id, auto_create_collection=True,
    )

    # 自动新建了属于该知识库的集合
    assert res["collection"].startswith(f"kb_{kn.id}_")
    assert res["collection_id"]
    coll = db.get(KbCollection, res["collection_id"])
    assert coll.knowledge_id == kn.id

    # 字段按文件表头自动生成，默认**所有字段**组合为向量化内容
    assert res["schema_created"] is True
    assert res["embed_fields"] == ["商品", "价格"]
    assert embedding_fields(get_schema_fields(db, res["collection"])) == ["商品", "价格"]

    # 一行一段：content 为向量化字段组合拼成的 CSV 行
    assert len(calls[0]["chunks"]) == 2
    assert calls[0]["chunks"][0].content.text == "防水低价,9"

    # 文档必有所属集合
    doc = db.execute(
        __import__("sqlalchemy").select(KbDocument).where(
            KbDocument.uuid_code == res["document_id"]
        )
    ).scalar_one()
    assert doc.collection_id == res["collection_id"]
    assert doc.collection == res["collection"]


def test_import_with_selected_collection_id_validates_schema(db, monkeypatch):
    """指定了集合 → 按该集合字段定义校验（列名不符直接拒绝，不落数据）。"""
    from app.services.kb.table_schema import TableSchemaMismatch

    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-sel", type=2, kb_format="table")
    db.add(kn)
    db.commit()
    coll = create_knowledge_collection(
        db, TENANT, kn.id, slug="sel",
        schema_config=[
            {"name": "商品", "type": "string", "enabled": True, "embedding": True, "filterable": False},
            {"name": "价格", "type": "number", "enabled": True, "embedding": True, "filterable": False},
        ],
    )
    db.commit()

    calls = []
    monkeypatch.setattr(
        "app.services.kb.rag.content_service._insert_via_kb",
        lambda _sf, **kw: calls.append(kw),
    )

    # 列完全匹配 → 通过，且按集合定义的字段组合切分
    res = import_table_file(
        db, TENANT, coll.name, CSV.encode("utf-8-sig"), "价格表.csv",
        knowledge_id=kn.id, collection_id=coll.id,
    )
    assert res["embed_fields"] == ["商品", "价格"]
    assert calls[0]["chunks"][0].content.text == "防水低价,9"

    # 缺列 → 拒绝且不落数据
    calls.clear()
    with pytest.raises(TableSchemaMismatch):
        import_table_file(
            db, TENANT, coll.name, "商品\nA\n".encode("utf-8-sig"), "缺列.csv",
            knowledge_id=kn.id, collection_id=coll.id,
        )
    assert calls == []
