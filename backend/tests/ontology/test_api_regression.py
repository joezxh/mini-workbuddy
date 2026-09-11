"""`/api/v1/wiki/owl/*` 全量端点回归测试。

`WikiOwlEngine` 由内存单例改为按租户持久化属于**行为变更**，
因此本文件把改造前各端点的对外契约固化下来：
改造前后都必须全绿（改造前先跑一遍作为基线）。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.wiki.wiki_article import WikiArticle

from .conftest import TENANT_A, TENANT_B, build_client

SAMPLE_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/ontology#> .

ex:Risk a owl:Class ;
    rdfs:label "风险" ;
    rdfs:comment "风险描述" .

ex:OperationalRisk a owl:Class ;
    rdfs:label "操作风险" ;
    rdfs:subClassOf ex:Risk .
"""


# ── POST /classes + GET /classes ─────────────────────────────────────────────

def test_create_and_list_classes_contract(client_a: TestClient) -> None:
    """注册类 → 返回 4 字段；列表接口返回同构数组。"""
    payload = {
        "uri": "http://example.org/ontology#Risk",
        "label": "风险",
        "comment": "风险描述",
        "parent_uris": [],
    }
    resp = client_a.post("/api/v1/wiki/owl/classes", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"uri", "label", "comment", "parent_uris"}
    assert body == {
        "uri": "http://example.org/ontology#Risk",
        "label": "风险",
        "comment": "风险描述",
        "parent_uris": [],
    }

    listed = client_a.get("/api/v1/wiki/owl/classes")
    assert listed.status_code == 200, listed.text
    assert listed.json() == [body]


def test_create_class_with_parents_contract(client_a: TestClient) -> None:
    """带父类注册时 parent_uris 原样回显。"""
    client_a.post(
        "/api/v1/wiki/owl/classes",
        json={"uri": "http://example.org/ontology#Root", "label": "根"},
    )
    resp = client_a.post(
        "/api/v1/wiki/owl/classes",
        json={
            "uri": "http://example.org/ontology#Child",
            "label": "子",
            "parent_uris": ["http://example.org/ontology#Root"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["parent_uris"] == ["http://example.org/ontology#Root"]


def test_register_same_uri_twice_is_idempotent(client_a: TestClient) -> None:
    """重复注册同一 URI：只有一条记录，字段以最后一次为准。"""
    uri = "http://example.org/ontology#Dup"
    client_a.post("/api/v1/wiki/owl/classes", json={"uri": uri, "label": "旧"})
    client_a.post("/api/v1/wiki/owl/classes", json={"uri": uri, "label": "新"})

    listed = client_a.get("/api/v1/wiki/owl/classes").json()
    assert len(listed) == 1
    assert listed[0]["uri"] == uri
    assert listed[0]["label"] == "新"


def test_list_classes_empty_by_default(client_a: TestClient) -> None:
    """未注册任何类时列表为空数组（不是 null / 对象）。"""
    assert client_a.get("/api/v1/wiki/owl/classes").json() == []


# ── GET /hierarchy ───────────────────────────────────────────────────────────

def test_hierarchy_contract(client_a: TestClient) -> None:
    """层级树：返回根节点数组，节点为 {uri, label, children}。"""
    client_a.post(
        "/api/v1/wiki/owl/classes", json={"uri": "http://example.org/ontology#Root", "label": "根"}
    )
    client_a.post(
        "/api/v1/wiki/owl/classes",
        json={
            "uri": "http://example.org/ontology#Child",
            "label": "子",
            "parent_uris": ["http://example.org/ontology#Root"],
        },
    )
    client_a.post(
        "/api/v1/wiki/owl/classes",
        json={
            "uri": "http://example.org/ontology#GrandChild",
            "label": "孙",
            "parent_uris": ["http://example.org/ontology#Child"],
        },
    )

    resp = client_a.get("/api/v1/wiki/owl/hierarchy")
    assert resp.status_code == 200, resp.text
    tree = resp.json()
    assert len(tree) == 1
    root = tree[0]
    assert set(root) == {"uri", "label", "children"}
    assert root["uri"] == "http://example.org/ontology#Root"
    assert root["label"] == "根"
    assert len(root["children"]) == 1
    child = root["children"][0]
    assert child["uri"] == "http://example.org/ontology#Child"
    assert child["label"] == "子"
    assert [c["uri"] for c in child["children"]] == [
        "http://example.org/ontology#GrandChild"
    ]


def test_hierarchy_empty_by_default(client_a: TestClient) -> None:
    assert client_a.get("/api/v1/wiki/owl/hierarchy").json() == []


# ── POST /import-ttl ─────────────────────────────────────────────────────────

def test_import_ttl_contract(client_a: TestClient) -> None:
    """导入成功返回 {message, added}，且导入的类可被列表接口查到。"""
    resp = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={"file": ("ontology.ttl", SAMPLE_TTL.encode("utf-8"), "text/turtle")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"message", "added"}
    assert body["message"].startswith("导入成功, 新增 ")
    assert isinstance(body["added"], int)
    assert body["added"] > 0

    uris = {c["uri"] for c in client_a.get("/api/v1/wiki/owl/classes").json()}
    assert "http://example.org/ontology#Risk" in uris
    assert "http://example.org/ontology#OperationalRisk" in uris


def test_import_invalid_ttl_returns_400(client_a: TestClient) -> None:
    """非法 TTL 返回 400，detail 含「TTL 解析失败」。"""
    resp = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={"file": ("bad.ttl", b"this is not turtle @@@ {{{", "text/turtle")},
    )
    assert resp.status_code == 400, resp.text
    assert "TTL 解析失败" in resp.json()["detail"]


def test_import_non_utf8_returns_400(client_a: TestClient) -> None:
    """非 UTF-8 文件返回 400，detail 为固定文案。"""
    resp = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={"file": ("bad.ttl", b"\xff\xfe\x00\x01", "application/octet-stream")},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "TTL 文件必须为 UTF-8 编码"


# ── GET /export-ttl ──────────────────────────────────────────────────────────

def test_export_ttl_contract(client_a: TestClient) -> None:
    """导出返回 text/turtle 附件，内容含已注册类的 URI。"""
    client_a.post(
        "/api/v1/wiki/owl/classes", json={"uri": "http://example.org/ontology#Risk", "label": "风险"}
    )

    resp = client_a.get("/api/v1/wiki/owl/export-ttl")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/turtle")
    assert resp.headers["content-disposition"] == (
        "attachment; filename=wiki-ontology.ttl"
    )
    assert "http://example.org/ontology#Risk" in resp.text


def test_export_ttl_label_uses_zh_lang_tag(client_a: TestClient) -> None:
    """导出的标签带 `@zh` 语言标记（与改造前 register_class 的写入方式一致）。

    已知偏差：TTL 导入的标签若原文带其它语言标记（如 @en），
    持久化后只保留文本，导出统一为 @zh（模型未设计语言列）。
    """
    client_a.post(
        "/api/v1/wiki/owl/classes", json={"uri": "http://example.org/ontology#Risk", "label": "风险"}
    )
    ttl = client_a.get("/api/v1/wiki/owl/export-ttl").text
    assert '"风险"@zh' in ttl


def test_export_ttl_empty_by_default(client_a: TestClient) -> None:
    """空本体导出仍返回合法（可解析）的 TTL。"""
    resp = client_a.get("/api/v1/wiki/owl/export-ttl")
    assert resp.status_code == 200, resp.text
    from rdflib import Graph

    graph = Graph()
    graph.parse(data=resp.text, format="turtle")  # 能解析即合法


# ── GET /stats ───────────────────────────────────────────────────────────────

def test_stats_contract(client_a: TestClient) -> None:
    """统计返回 total_triples / class_count 两个整型。"""
    empty = client_a.get("/api/v1/wiki/owl/stats").json()
    assert set(empty) == {"total_triples", "class_count"}
    assert empty["class_count"] == 0

    client_a.post(
        "/api/v1/wiki/owl/classes", json={"uri": "http://example.org/ontology#A", "label": "A"}
    )
    client_a.post(
        "/api/v1/wiki/owl/classes", json={"uri": "http://example.org/ontology#B", "label": "B"}
    )
    filled = client_a.get("/api/v1/wiki/owl/stats").json()
    assert set(filled) == {"total_triples", "class_count"}
    assert filled["class_count"] == 2
    assert isinstance(filled["total_triples"], int)
    assert filled["total_triples"] >= filled["class_count"]


# ── GET /articles/{class_uri} ────────────────────────────────────────────────

RISK_URI = "http://example.org/ontology/Risk"


def _make_article(
    db: Session,
    slug: str,
    tenant_id: int,
    class_uris: Optional[List[str]],
    status: int = 1,
) -> WikiArticle:
    """在**真实数据库**里插一篇文章（不用桩）。"""
    article = WikiArticle(
        slug=slug,
        title=f"标题-{slug}",
        summary="摘要",
        content="正文",
        status=status,
        tenant_id=tenant_id,
        owl_class_uris=class_uris,
        version=2,
    )
    db.add(article)
    db.commit()
    return article


def test_articles_by_class_endpoint_contract(db: Session) -> None:
    """按 OWL 类查询文章：返回 {class_uri, total, items:[{...}]}。

    走**真实 SQL**（PostgreSQL JSONB `@>`），不再用桩会话 ——
    否则 SQL 写错、`contains` 语义反转都测不出来（评审 IM-02）。
    """
    article = _make_article(db, "risk-management", TENANT_A, [RISK_URI])
    _make_article(db, "unrelated", TENANT_A, ["http://example.org/ontology/Other"])

    client = build_client(db, TENANT_A)
    resp = client.get(f"/api/v1/wiki/owl/articles/{RISK_URI}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"class_uri", "total", "items"}
    assert body["class_uri"] == RISK_URI
    assert body["total"] == 1
    assert body["items"][0]["id"] == article.id
    assert body["items"][0]["slug"] == "risk-management"
    assert body["items"][0]["title"] == "标题-risk-management"
    assert body["items"][0]["summary"] == "摘要"
    assert body["items"][0]["version"] == 2


def test_articles_by_class_endpoint_is_tenant_scoped(db: Session) -> None:
    """同 URI 的文章在别的租户下**不可见**：端点自己带 tenant_id 过滤，不依赖全局拦截器。"""
    _make_article(db, "tenant-a-risk", TENANT_A, [RISK_URI])
    _make_article(db, "tenant-b-risk", TENANT_B, [RISK_URI])

    resp_a = build_client(db, TENANT_A).get(f"/api/v1/wiki/owl/articles/{RISK_URI}")
    assert resp_a.status_code == 200, resp_a.text
    assert [i["slug"] for i in resp_a.json()["items"]] == ["tenant-a-risk"]

    resp_b = build_client(db, TENANT_B).get(f"/api/v1/wiki/owl/articles/{RISK_URI}")
    assert resp_b.status_code == 200, resp_b.text
    assert [i["slug"] for i in resp_b.json()["items"]] == ["tenant-b-risk"]


def test_articles_by_class_endpoint_empty(db: Session) -> None:
    """无匹配文章时 total=0、items=[]（真实库，不是空桩）。"""
    _make_article(db, "draft-or-other", TENANT_A, ["http://example.org/ontology/Other"])

    client = build_client(db, TENANT_A)
    resp = client.get("/api/v1/wiki/owl/articles/http://example.org/ontology/None")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "class_uri": "http://example.org/ontology/None",
        "total": 0,
        "items": [],
    }


def test_articles_by_class_endpoint_filters_by_containment(db: Session) -> None:
    """`owl_class_uris` 是数组：只匹配**包含**该类的文章，不是子串匹配。"""
    _make_article(db, "has-both", TENANT_A, [RISK_URI, "http://example.org/ontology/Other"])
    _make_article(db, "has-prefix-only", TENANT_A, [RISK_URI + "Sub"])

    resp = build_client(db, TENANT_A).get(f"/api/v1/wiki/owl/articles/{RISK_URI}")
    assert resp.status_code == 200, resp.text
    assert [i["slug"] for i in resp.json()["items"]] == ["has-both"]


# ── 错误处理与事务边界（IM-05）──────────────────────────────────────────────

def _ttl_with_class_uri(uri: str) -> str:
    return f"""
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<{uri}> a owl:Class ;
    rdfs:label "超长" .
"""


def test_register_class_with_oversized_uri_returns_400(client_a: TestClient) -> None:
    """超长 URI 必须返回 400（客户端错误），不能因 PG DataError 冒泡成 500。"""
    resp = client_a.post(
        "/api/v1/wiki/owl/classes",
        json={"uri": "http://example.org/ontology#" + "A" * 2000, "label": "超长"},
    )
    assert resp.status_code == 400, resp.text
    assert "超过上限" in resp.json()["detail"]


def test_failed_import_returns_400_not_500(client_a: TestClient) -> None:
    """导入触发数据库错误时返回 400，而不是 500。"""
    resp = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={
            "file": (
                "big.ttl",
                _ttl_with_class_uri("http://example.org/ontology#" + "B" * 2000).encode("utf-8"),
                "text/turtle",
            )
        },
    )
    assert resp.status_code == 400, resp.text


def test_failed_import_leaves_no_partial_data(client_a: TestClient) -> None:
    """导入失败整体回滚：不会留下「导入了一半」的本体（导入是单事务）。

    R2-06：只比较类集合抓不住回滚退化 —— 单一真相源下失败导入会在
    `_reindex()` 抛错，但若 `auto_commit` 退化成 True，`ttl_content` 已先行
    提交、rollback 无效，类集合不变而**导出内容膨胀**。因此这里必须同时
    对比导出的完整文本。
    """
    ok = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={"file": ("ontology.ttl", SAMPLE_TTL.encode("utf-8"), "text/turtle")},
    )
    assert ok.status_code == 200, ok.text
    before = {c["uri"] for c in client_a.get("/api/v1/wiki/owl/classes").json()}
    assert before == {
        "http://example.org/ontology#Risk",
        "http://example.org/ontology#OperationalRisk",
    }
    before_export = client_a.get("/api/v1/wiki/owl/export-ttl").text

    failed = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={
            "file": (
                "big.ttl",
                _ttl_with_class_uri("http://example.org/ontology#" + "C" * 2000).encode("utf-8"),
            )
        },
    )
    assert failed.status_code == 400, failed.text

    after = {c["uri"] for c in client_a.get("/api/v1/wiki/owl/classes").json()}
    assert after == before, "失败的导入必须整体回滚，不能残留部分数据"
    after_export = client_a.get("/api/v1/wiki/owl/export-ttl").text
    assert after_export == before_export, (
        "失败的导入必须整体回滚（含 ttl_content），导出内容不得变化（R2-06）"
    )


def test_api_without_tenant_returns_400(db) -> None:
    """IM-07（用户授权的行为变更）：无租户请求返回 `400 tenant_required`。

    改造前 / 修复前：tenant_id=None 落到 NULL 分区，所有无租户用户共享本体，
    与「全局单例」缺陷等价。现统一拦截（读/写路径都要拦）。
    """
    from .conftest import build_client

    client = build_client(db, None)

    read_resp = client.get("/api/v1/wiki/owl/classes")
    assert read_resp.status_code == 400, read_resp.text
    assert read_resp.json()["detail"] == "tenant_required"

    write_resp = client.post(
        "/api/v1/wiki/owl/classes",
        json={"uri": "http://example.org/ontology#X", "label": "无租户"},
    )
    assert write_resp.status_code == 400, write_resp.text
    assert write_resp.json()["detail"] == "tenant_required"

    import_resp = client.post(
        "/api/v1/wiki/owl/import-ttl",
        files={"file": ("ontology.ttl", SAMPLE_TTL.encode("utf-8"), "text/turtle")},
    )
    assert import_resp.status_code == 400, import_resp.text


# ── 端点清单（防漏测）────────────────────────────────────────────────────────

def test_all_owl_endpoints_are_covered(client_a: TestClient) -> None:
    """路由表里所有 /wiki/owl 路径都在本文件中有对应用例。"""
    paths = {
        route.path
        for route in client_a.app.routes  # type: ignore[attr-defined]
        if getattr(route, "path", "").startswith("/api/v1/wiki/owl")
    }
    assert paths == {
        "/api/v1/wiki/owl/classes",
        "/api/v1/wiki/owl/hierarchy",
        "/api/v1/wiki/owl/import-ttl",
        "/api/v1/wiki/owl/export-ttl",
        "/api/v1/wiki/owl/stats",
        "/api/v1/wiki/owl/articles/{class_uri:path}",
    }, paths
