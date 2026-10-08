"""分段端点 HTTP 冒烟（spec §10.5）：路由接线与序列化。

服务层语义由 ``test_segment_service.py`` 覆盖，这里只验证端点可达、参数绑定正确、
删除后 404。用管理员用户（鉴权直通）隔离 RBAC，避免依赖权限表。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.deps import get_current_user, get_db
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.routers.kb.kb import router

TENANT = 100


@pytest.fixture
def env(db: Session):
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="kb", slug="kb-api",
                       type=2, kb_format="document", index_mode="high_quality")
    db.add(kn)
    db.commit()
    db.add(KbCollection(tenant_id=TENANT, name=f"kb_{kn.id}", dimensions=768,
                        knowledge_id=kn.id))
    db.add(KbDocument(tenant_id=TENANT, uuid_code="doc1", knowledge_id=kn.id,
                      collection=f"kb_{kn.id}", name="a.md", source_type="upload",
                      status="completed"))
    db.commit()
    return kn


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


def test_segment_crud_endpoints(db: Session, env, client: TestClient, monkeypatch):
    # 编辑会触发重嵌；此处只验接线，屏蔽真实嵌入调用（不联网）
    monkeypatch.setattr(
        "app.services.kb.segment_service._embed_one",
        lambda text, embed_fn: [0.0] * 768,
    )
    seg = KbSegment(tenant_id=TENANT, collection=f"kb_{env.id}", document_id="doc1",
                    chunk_index=0, content="原文", chunk_type="text")
    db.add(seg)
    db.commit()

    got = client.get(f"/api/v1/kb/segments/{seg.id}")
    assert got.status_code == 200 and got.json()["content"] == "原文"

    put = client.put(f"/api/v1/kb/segments/{seg.id}",
                     json={"content": "改后", "keywords": ["退款"]})
    assert put.status_code == 200
    assert put.json()["content"] == "改后" and put.json()["keywords"] == ["退款"]

    patched = client.patch(f"/api/v1/kb/segments/{seg.id}/keywords",
                           json={"keywords": ["时效"]})
    assert patched.status_code == 200 and patched.json()["keywords"] == ["时效"]

    cites = client.get(f"/api/v1/kb/segments/{seg.id}/citations")
    assert cites.status_code == 200
    assert cites.json()["document"]["document_id"] == "doc1"

    deleted = client.delete(f"/api/v1/kb/segments/{seg.id}")
    assert deleted.status_code == 200 and deleted.json() == {"deleted": seg.id}
    assert db.execute(select(KbSegment)).scalars().all() == []
    assert client.get(f"/api/v1/kb/segments/{seg.id}").status_code == 404
