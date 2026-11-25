"""图谱知识库路由契约测试：端点可达性 / 权限矩阵 / 类型守卫 / 租户隔离。

鉴权走真实 ``require_kb_permission``：
- 管理员直通（不查权限表）；
- 非管理员用「权限查询替身」返回指定权限集，验证读/写权限边界。
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.routers.kb.kg import router as kg_router
from tests.kb.conftest import TENANT_A, TENANT_B


def _make_kb(db, tenant_id=TENANT_A, slug="kg-api-1", kb_type=4):
    kb = WikiKnowledge(name="图谱库", slug=slug, type=kb_type, tenant_id=tenant_id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


class _PermResult:
    def __init__(self, perms):
        self._perms = perms

    def scalars(self):
        return self

    def all(self):
        return list(self._perms)


class _SessionProxy:
    """按语句目标表分流：权限查询走替身，其余代理真实 session。"""

    def __init__(self, real, perms):
        self._real = real
        self._perms = perms

    def execute(self, stmt, *args, **kwargs):
        entity = None
        try:
            descs = stmt.column_descriptions
            entity = descs[0].get("entity") if descs else None
        except Exception:  # noqa: BLE001
            entity = None
        if getattr(entity, "__name__", "") == "SysMenu":
            return _PermResult(self._perms)
        return self._real.execute(stmt, *args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._real, item)


def _client(db, perms=(), is_admin=True, tenant_id=TENANT_A):
    app = FastAPI()
    app.include_router(kg_router)
    user = SimpleNamespace(user_id=1, is_admin=is_admin, tenant_id=tenant_id)
    app.dependency_overrides[get_db] = lambda: _SessionProxy(db, perms)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def kb(db):
    return _make_kb(db)


def test_entities_list_empty(db, kb):
    with _client(db) as client:
        r = client.get(f"/api/v1/kb/knowledges/{kb.id}/graph/entities")
        assert r.status_code == 200
        assert r.json()["items"] == []
        assert r.json()["total"] == 0


def test_entity_crud_roundtrip(db, kb):
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        r = client.post(f"{base}/entities", json={"name": "星海科技", "type_code": "CUS"})
        assert r.status_code == 201
        eid = r.json()["id"]
        assert r.json()["status"] == "suggested"

        r = client.get(f"{base}/entities/{eid}")
        assert r.status_code == 200
        assert r.json()["name"] == "星海科技"

        r = client.put(f"{base}/entities/{eid}", json={"name": "星海科技集团"})
        assert r.status_code == 200
        assert r.json()["name"] == "星海科技集团"

        r = client.patch(f"{base}/entities/{eid}/accept")
        assert r.status_code == 200
        assert r.json()["status"] == "active"

        r = client.delete(f"{base}/entities/{eid}")
        assert r.status_code == 200
        assert client.get(f"{base}/entities").json()["total"] == 0


def test_relation_crud_and_stats(db, kb):
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        a = client.post(f"{base}/entities", json={"name": "A"}).json()["id"]
        b = client.post(f"{base}/entities", json={"name": "B"}).json()["id"]

        r = client.post(f"{base}/relations", json={
            "from_entity_id": a, "to_entity_id": b,
            "relation_code": "BELONGS", "predicate": "隶属于", "weight": 0.9,
        })
        assert r.status_code == 201
        rid = r.json()["id"]
        assert r.json()["from_entity_name"] == "A"
        assert r.json()["to_entity_name"] == "B"

        r = client.get(f"{base}/relations")
        assert r.status_code == 200
        assert r.json()["total"] == 1

        r = client.patch(f"{base}/relations/{rid}/review", json={"verdict": "accepted"})
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"

        r = client.get(f"{base}/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["entities"] == 2
        assert body["relations"] == 1
        assert body["by_relation"]["BELONGS"] == 1

        assert client.delete(f"{base}/relations/{rid}").status_code == 200


def test_entity_batch_review_settype_delete(db, kb):
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        ids = [
            client.post(f"{base}/entities", json={"name": f"实体{i}", "type_code": "A"}).json()["id"]
            for i in range(3)
        ]
        ids.append(999999)  # 不存在 → 单条容错

        r = client.post(f"{base}/entities/batch-review",
                        json={"ids": ids, "verdict": "accepted"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok_count"] == 3 and body["failed_count"] == 1
        assert body["results"][-1]["ok"] is False
        r = client.get(f"{base}/entities/{ids[0]}")
        assert r.json()["status"] == "active"

        r = client.post(f"{base}/entities/batch-set-type",
                        json={"ids": ids[:3], "type_code": "B"})
        assert r.status_code == 200
        assert r.json()["ok_count"] == 3
        assert client.get(f"{base}/entities/{ids[0]}").json()["type_code"] == "B"

        r = client.post(f"{base}/entities/batch-delete", json={"ids": ids})
        assert r.status_code == 200
        assert r.json()["ok_count"] == 3 and r.json()["failed_count"] == 1
        assert client.get(f"{base}/entities").json()["total"] == 0


def test_relation_batch_review_delete(db, kb):
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        a = client.post(f"{base}/entities", json={"name": "A"}).json()["id"]
        b = client.post(f"{base}/entities", json={"name": "B"}).json()["id"]
        c = client.post(f"{base}/entities", json={"name": "C"}).json()["id"]
        r1 = client.post(f"{base}/relations", json={
            "from_entity_id": a, "to_entity_id": b, "relation_code": "R1"}).json()["id"]
        r2 = client.post(f"{base}/relations", json={
            "from_entity_id": a, "to_entity_id": c, "relation_code": "R2"}).json()["id"]

        r = client.post(f"{base}/relations/batch-review",
                        json={"ids": [r1, r2], "verdict": "rejected"})
        assert r.status_code == 200
        assert r.json()["ok_count"] == 2
        assert client.get(f"{base}/relations/{r1}").json()["status"] == "rejected"

        r = client.post(f"{base}/relations/batch-delete", json={"ids": [r1, 999999]})
        assert r.status_code == 200
        assert r.json()["ok_count"] == 1 and r.json()["failed_count"] == 1
        assert client.get(f"{base}/relations").json()["total"] == 1


def test_relation_patch_edit(db, kb):
    """关系编辑：类型/谓词/权重/证据/边属性可改，端点实体不可变。"""
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        a = client.post(f"{base}/entities", json={"name": "A"}).json()["id"]
        b = client.post(f"{base}/entities", json={"name": "B"}).json()["id"]
        rid = client.post(f"{base}/relations", json={
            "from_entity_id": a, "to_entity_id": b, "relation_code": "R1"}).json()["id"]

        r = client.patch(f"{base}/relations/{rid}", json={
            "relation_code": "SUPPLY", "predicate": "供应",
            "weight": 0.85, "evidence": {"text": "原文"}, "properties": {"k": "v"},
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["relation_code"] == "SUPPLY"
        assert body["weight"] == 0.85
        assert body["evidence"] == {"text": "原文"}
        assert body["from_entity_id"] == a, "端点不可变"

        r = client.patch(f"{base}/relations/{rid}", json={"weight": 3.5})
        assert r.status_code == 422, "权重越界要 422"


def test_export_graphml(db, kb):
    """graphml 导出：节点带 label 属性、边带 relation 标签，XML 可被 yEd/Gephi 读取。"""
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        a = client.post(f"{base}/entities", json={"name": "启明电子", "type_code": "供应商"}).json()["id"]
        b = client.post(f"{base}/entities", json={"name": "智联数码", "type_code": "产品"}).json()["id"]
        client.post(f"{base}/relations", json={
            "from_entity_id": a, "to_entity_id": b, "relation_code": "生产"})

        r = client.get(f"{base}/export?fmt=graphml")
        assert r.status_code == 200
        body = r.json()
        assert body["format"] == "graphml"
        xml = body["content"]
        assert xml.lstrip().startswith("<?xml")
        assert "<graph" in xml and "</graphml>" in xml
        assert "启明电子" in xml and "生产" in xml


def test_prompt_preview_endpoint(db, kb):
    """「输出当前抽取所用的提示词」：配置页展示按当前配置拼装的最终生效提示词。"""
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        r = client.get(f"{base}/prompt-preview")
        assert r.status_code == 200
        body = r.json()
        assert "你是知识图谱抽取器" in body["prompt"]
        assert "输出结构" in body["prompt"] and "文本：" in body["prompt"]
        assert "宁多勿漏" in body["prompt"], "强化后的关系召回导向措辞要可见"
        cfg = body["config"]
        assert cfg["max_output_tokens"] >= 4096
        assert cfg["max_text_chars"] >= 12000
        assert cfg["max_continuation_rounds"] == 3


def test_view_permission_cannot_write(db, kb):
    with _client(db, perms=["kb:view"], is_admin=False) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        assert client.get(f"{base}/entities").status_code == 200
        r = client.post(f"{base}/entities", json={"name": "X"})
        assert r.status_code == 403


def test_no_permission_rejected(db, kb):
    with _client(db, perms=[], is_admin=False) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        assert client.get(f"{base}/entities").status_code == 403


def test_non_graph_knowledge_returns_422(db):
    plain = _make_kb(db, slug="kg-api-plain", kb_type=2)
    with _client(db) as client:
        r = client.get(f"/api/v1/kb/knowledges/{plain.id}/graph/entities")
        assert r.status_code == 422


def test_unknown_knowledge_returns_404(db):
    with _client(db) as client:
        r = client.get("/api/v1/kb/knowledges/999999/graph/entities")
        assert r.status_code == 404


def test_cross_tenant_knowledge_returns_404(db, kb):
    with _client(db, tenant_id=TENANT_B) as client:
        r = client.get(f"/api/v1/kb/knowledges/{kb.id}/graph/entities")
        assert r.status_code == 404


def test_graph_document_endpoint(db, kb):
    """单文档实体与关系：文档成员实体 + 端点补桩 + 精确关系，未知文档 404。"""
    from app.models.kb.kb_document import KbDocument
    from app.models.kb.kg_entity import KgEntity
    from app.models.kb.kg_triple import KgTriple

    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        e1 = client.post(f"{base}/entities", json={"name": "本文档实体", "type_code": "A"}).json()
        e2 = client.post(f"{base}/entities", json={"name": "跨文档实体", "type_code": "B"}).json()
        r = client.post(f"{base}/relations", json={
            "from_entity_id": e1["id"], "to_entity_id": e2["id"],
            "relation_code": "REL_X",
        })
        assert r.status_code == 201, r.text
        rel_id = r.json()["id"]

        doc_uuid = "docuuid0001"
        db.add(KbDocument(
            uuid_code=doc_uuid, knowledge_id=kb.id,
            collection=f"kb_{kb.id}", name="测试文档", tenant_id=TENANT_A,
        ))
        db.commit()
        # 溯源：实体 1 与关系归本文档；实体 2 在其他文档首次创建（仅作端点补桩）
        db.get(KgEntity, e1["id"]).source_document_ids = [doc_uuid]
        db.get(KgTriple, rel_id).source_document_ids = [doc_uuid]
        db.commit()

        r = client.get(f"{base}/documents/{doc_uuid}")
        assert r.status_code == 200, r.text
        body = r.json()
        ent_ids = {e["id"] for e in body["entities"]}
        assert e1["id"] in ent_ids  # 本文档实体
        assert e2["id"] in ent_ids  # 端点补桩：缺它图谱连线会被丢弃
        assert [x["id"] for x in body["relations"]] == [rel_id]
        assert body["relations"][0]["from_entity_name"] == "本文档实体"

        r = client.get(f"{base}/documents/missing-uuid")
        assert r.status_code == 404
