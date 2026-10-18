"""集合 CRUD / 重命名级联 / 删除级联 / id 解析 404（spec §10.2 集合与字段定义管理）。

文档↔集合关联以 ``collection_id`` 为唯一事实来源，集合名仅作向量库命名空间标签；
重命名 = 对 kms_collection/kms_document/kms_segment 三张表的 name 标签做一致 UPDATE。
"""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.routers.kb.kb import get_current_user, get_db, router
from app.services.kb.collection_service import (
    delete_collection_cascade,
    ensure_default_collection,
    get_collection_by_id,
    get_collection_name_by_id,
    rename_collection,
)

TENANT = 0
# 物理列为 vector(settings.EMBEDDING_DIMENSION)，假向量必须同维，否则插入报维度不符
VEC = [0.0] * settings.EMBEDDING_DIMENSION


@pytest.fixture
def client(db: Session):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        user_id=1, is_admin=True, tenant_id=TENANT
    )
    with TestClient(app) as c:
        yield c


def _make_kb(db: "Session", fmt: str = "table", slug: str = "crud-kb") -> WikiKnowledge:
    kn = WikiKnowledge(
        tenant_id=TENANT, name=slug, slug=slug,
        type=2, kb_format=fmt, index_mode="high_quality",
    )
    db.add(kn)
    db.commit()
    return kn


def _seed_doc_and_segment(db: "Session", coll: KbCollection) -> tuple[KbDocument, KbSegment]:
    doc = KbDocument(
        tenant_id=TENANT, uuid_code=str(uuid.uuid4()), knowledge_id=coll.knowledge_id,
        name="d.csv", status="completed", collection=coll.name, collection_id=coll.id,
    )
    db.add(doc)
    db.flush()
    seg = KbSegment(
        tenant_id=TENANT, collection=coll.name, document_id=doc.uuid_code,
        chunk_index=0, content="x", chunk_type="table_row", embedding=VEC,
    )
    db.add(seg)
    db.commit()
    return doc, seg


# ── 路由层 CRUD ────────────────────────────────────────────────────────────
def test_create_collection_route(client, db: "Session"):
    kn = _make_kb(db)
    r = client.post(
        f"/api/v1/kb/knowledges/{kn.id}/collections", json={"slug": "sales"}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == f"kb_{kn.id}_sales"
    cid = body["id"]
    lst = client.get(f"/api/v1/kb/knowledges/{kn.id}/collections").json()
    assert any(i["id"] == cid for i in lst["items"])


def test_create_collection_default_slug(client, db: "Session"):
    kn = _make_kb(db)
    r = client.post(f"/api/v1/kb/knowledges/{kn.id}/collections", json={})
    assert r.status_code == 201, r.text
    # 缺省 slug：创建第二条时自动后缀，仍保持唯一（非空）
    assert r.json()["name"].startswith(f"kb_{kn.id}")


def test_update_collection_rename_route(client, db: "Session"):
    kn = _make_kb(db)
    cid = client.post(
        f"/api/v1/kb/knowledges/{kn.id}/collections", json={"slug": "a"}
    ).json()["id"]
    r = client.put(
        f"/api/v1/kb/knowledges/{kn.id}/collections/{cid}", json={"slug": "b"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == f"kb_{kn.id}_b"


def test_update_collection_schema_route(client, db: "Session"):
    kn = _make_kb(db)
    cid = client.post(
        f"/api/v1/kb/knowledges/{kn.id}/collections", json={}
    ).json()["id"]
    fields = [
        {"name": "c1", "type": "string", "enabled": True,
         "embedding": True, "filterable": False},
    ]
    r = client.put(
        f"/api/v1/kb/knowledges/{kn.id}/collections/{cid}",
        json={"schema_config": fields},
    )
    assert r.status_code == 200, r.text
    # 落库经 normalize_fields：补齐 order 并稳定排序（单字段 order=0）
    assert r.json()["schema_config"] == [
        {"name": "c1", "type": "string", "enabled": True,
         "embedding": True, "filterable": False, "order": 0},
    ]


def test_schema_config_order_preserved_and_sorted(client, db: "Session"):
    kn = _make_kb(db)
    cid = client.post(
        f"/api/v1/kb/knowledges/{kn.id}/collections", json={"slug": "ord"}
    ).json()["id"]
    fields = [
        {"name": "x", "type": "string", "enabled": True,
         "embedding": True, "filterable": False, "order": 5},
        {"name": "y", "type": "string", "enabled": True,
         "embedding": True, "filterable": False, "order": 1},
    ]
    r = client.put(
        f"/api/v1/kb/knowledges/{kn.id}/collections/{cid}",
        json={"schema_config": fields},
    )
    assert r.status_code == 200, r.text
    sc = r.json()["schema_config"]
    # 保存后按 order 稳定排序，且 order 值被原样保留
    assert [f["name"] for f in sc] == ["y", "x"]
    assert sc[0]["order"] == 1 and sc[1]["order"] == 5


def test_list_collections_returns_schema_config(client, db: "Session"):
    kn = _make_kb(db)
    cid = client.post(
        f"/api/v1/kb/knowledges/{kn.id}/collections", json={"slug": "o"}
    ).json()["id"]
    fields = [
        {"name": "b", "type": "string", "enabled": True,
         "embedding": True, "filterable": False, "order": 2},
        {"name": "a", "type": "number", "enabled": True,
         "embedding": False, "filterable": True, "order": 1},
    ]
    upd = client.put(
        f"/api/v1/kb/knowledges/{kn.id}/collections/{cid}",
        json={"schema_config": fields},
    )
    assert upd.status_code == 200, upd.text
    # 列表接口现返回 schema_config，且按 order 排序
    lst = client.get(f"/api/v1/kb/knowledges/{kn.id}/collections").json()
    item = next(i for i in lst["items"] if i["id"] == cid)
    sc = item["schema_config"]
    assert [f["name"] for f in sc] == ["a", "b"]
    assert all("order" in f for f in sc)


def test_update_collection_rejects_no_embedding(client, db: "Session"):
    kn = _make_kb(db)
    cid = client.post(
        f"/api/v1/kb/knowledges/{kn.id}/collections", json={}
    ).json()["id"]
    fields = [
        {"name": "c1", "type": "string", "enabled": True,
         "embedding": False, "filterable": False},
    ]
    r = client.put(
        f"/api/v1/kb/knowledges/{kn.id}/collections/{cid}",
        json={"schema_config": fields},
    )
    assert r.status_code == 422, r.text  # 至少 1 个向量化字段


def test_delete_collection_route(client, db: "Session"):
    kn = _make_kb(db)
    cid = client.post(
        f"/api/v1/kb/knowledges/{kn.id}/collections", json={"slug": "x"}
    ).json()["id"]
    rd = client.delete(f"/api/v1/kb/knowledges/{kn.id}/collections/{cid}")
    assert rd.status_code == 200, rd.text
    # 再次删除 → 404
    rd2 = client.delete(f"/api/v1/kb/knowledges/{kn.id}/collections/{cid}")
    assert rd2.status_code == 404, rd2.text


def test_collection_crud_ownership_mismatch(client, db: "Session"):
    kn1 = _make_kb(db)
    kn2 = _make_kb(db, fmt="doc", slug="crud-kb-2")
    cid = client.post(
        f"/api/v1/kb/knowledges/{kn1.id}/collections", json={"slug": "z"}
    ).json()["id"]
    # 用另一个知识库的 id 操作 → 404
    r = client.put(
        f"/api/v1/kb/knowledges/{kn2.id}/collections/{cid}", json={"slug": "y"}
    )
    assert r.status_code == 404, r.text


# ── 服务层级联 / 反查 ──────────────────────────────────────────────────────
def test_get_collection_name_by_id_404(db: "Session"):
    try:
        get_collection_name_by_id(db, 9_999_999)
        assert False, "应抛出 ValueError"
    except ValueError:
        pass


def test_rename_collection_cascade(db: "Session"):
    kn = _make_kb(db)
    coll = ensure_default_collection(db, TENANT, kn.id)
    db.commit()
    old_name = coll.name
    doc, seg = _seed_doc_and_segment(db, coll)

    rename_collection(db, coll.id, "renamed")
    db.commit()

    seg2 = db.execute(select(KbSegment).where(KbSegment.id == seg.id)).scalar_one()
    doc2 = db.execute(select(KbDocument).where(KbDocument.id == doc.id)).scalar_one()
    assert seg2.collection == f"kb_{kn.id}_renamed"
    assert doc2.collection == f"kb_{kn.id}_renamed"
    assert get_collection_by_id(db, coll.id).name != old_name


def test_delete_collection_cascade(db: "Session"):
    kn = _make_kb(db)
    coll = ensure_default_collection(db, TENANT, kn.id)
    db.commit()
    doc, seg = _seed_doc_and_segment(db, coll)

    delete_collection_cascade(db, TENANT, coll.id)
    db.commit()

    assert db.execute(
        select(KbSegment).where(KbSegment.id == seg.id)
    ).scalar_one_or_none() is None
    assert db.execute(
        select(KbDocument).where(KbDocument.id == doc.id)
    ).scalar_one_or_none() is None
    assert get_collection_by_id(db, coll.id) is None


def test_ensure_default_collection_idempotent(db: "Session"):
    kn = _make_kb(db)
    c1 = ensure_default_collection(db, TENANT, kn.id)
    c2 = ensure_default_collection(db, TENANT, kn.id)
    db.commit()
    assert c1.id == c2.id
    assert c1.name == f"kb_{kn.id}"
