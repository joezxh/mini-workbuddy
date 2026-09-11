"""数据源 CRUD 测试（P2 Task 2）。

重点：密码永不外显（只回 has_password）、更新留空不改、租户隔离、is_default 互斥。
"""
from __future__ import annotations

import pytest

from app.ai.dataops.crypto import decrypt_secret
from app.models.dataops.data_source import DataSource
from app.services.dataops.data_source_service import DataSourceService
from tests.dataops.conftest import TENANT_A, TENANT_B, build_client

PAYLOAD = {
    "name": "业务库",
    "source_type": "postgresql",
    "host": "127.0.0.1",
    "port": 5432,
    "username": "reader",
    "password": "s3cret-pw",
    "database": "bizdb",
}


def _create(client, **overrides):
    body = {**PAYLOAD, **overrides}
    return client.post("/api/v1/dataops/sources", json=body)


def test_create_and_list_never_exposes_password(client_a, db):
    r = _create(client_a)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["has_password"] is True
    assert "password" not in created and "password_enc" not in created
    assert "s3cret-pw" not in r.text

    # 落库的是密文
    row = db.query(DataSource).filter(DataSource.name == "业务库").first()
    assert row.password_enc != "s3cret-pw"
    assert decrypt_secret(row.password_enc) == "s3cret-pw"

    # 列表同样不含密码
    rlist = client_a.get("/api/v1/dataops/sources")
    assert rlist.status_code == 200
    items = rlist.json()
    assert len(items) == 1 and items[0]["has_password"] is True
    assert "s3cret-pw" not in rlist.text


def test_get_detail_no_password(client_a):
    source_id = _create(client_a).json()["id"]
    r = client_a.get(f"/api/v1/dataops/sources/{source_id}")
    assert r.status_code == 200
    assert "s3cret-pw" not in r.text and "password_enc" not in r.json()


def test_update_password_empty_keeps_old(client_a, db):
    source_id = _create(client_a).json()["id"]
    # 密码留空 = 不改
    r = client_a.put(f"/api/v1/dataops/sources/{source_id}", json={"password": "", "host": "10.0.0.2"})
    assert r.status_code == 200
    row = db.query(DataSource).get(source_id)
    assert row.host == "10.0.0.2"
    assert decrypt_secret(row.password_enc) == "s3cret-pw"

    # 传新密码 = 改
    r = client_a.put(f"/api/v1/dataops/sources/{source_id}", json={"password": "new-pw"})
    assert r.status_code == 200
    db.expire_all()
    row = db.query(DataSource).get(source_id)
    assert decrypt_secret(row.password_enc) == "new-pw"


def test_update_forbids_source_type_change(client_a):
    source_id = _create(client_a).json()["id"]
    r = client_a.put(f"/api/v1/dataops/sources/{source_id}", json={"source_type": "mysql"})
    assert r.status_code == 200
    # source_type 不允许改（服务层白名单剔除）
    row = client_a.get(f"/api/v1/dataops/sources/{source_id}").json()
    assert row["source_type"] == "postgresql"


def test_invalid_source_type_rejected(client_a):
    r = _create(client_a, source_type="oracle")
    assert r.status_code == 400


def test_tenant_isolation(client_a, client_b, db):
    source_id = _create(client_a).json()["id"]
    # B 列表看不到 A 的数据源
    assert client_b.get("/api/v1/dataops/sources").json() == []
    # B 获取/更新/删除 A 的数据源 → 404（不可探测存在性）
    assert client_b.get(f"/api/v1/dataops/sources/{source_id}").status_code == 404
    assert client_b.put(f"/api/v1/dataops/sources/{source_id}", json={"name": "x"}).status_code == 404
    assert client_b.delete(f"/api/v1/dataops/sources/{source_id}").status_code == 404


def test_missing_tenant_rejected(db):
    client = build_client(db, None)
    r = client.get("/api/v1/dataops/sources")
    assert r.status_code == 400
    assert r.json()["detail"] == "tenant_required"


def test_is_default_exclusive(client_a, db):
    first = _create(client_a, name="s1", is_default=True).json()
    second = _create(client_a, name="s2", is_default=True).json()
    assert first["is_default"] is True
    assert second["is_default"] is True
    items = {i["name"]: i["is_default"] for i in client_a.get("/api/v1/dataops/sources").json()}
    assert items == {"s1": False, "s2": True}


def test_delete_source(client_a, db):
    source_id = _create(client_a).json()["id"]
    assert client_a.delete(f"/api/v1/dataops/sources/{source_id}").status_code == 204
    assert client_a.get(f"/api/v1/dataops/sources/{source_id}").status_code == 404


def test_service_requires_tenant(db):
    with pytest.raises(ValueError):
        DataSourceService(db, None)
