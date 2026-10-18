"""TenantScope 租户隔离单元测试（不依赖真实 semantica 后端）。"""
import pytest

from app.services.semantica.scope import TenantScope


def test_namespace_format():
    s = TenantScope(tenant_id=100, ontology_code="kb", group_id="minworkbuddy")
    assert s.namespace == "minworkbuddy_100_kb"


def test_default_group_id_from_settings():
    s = TenantScope(tenant_id=1, ontology_code="default")
    # GRAPHITI_GROUP_ID 默认 minworkbuddy
    assert s.group_id == "minworkbuddy"
    assert s.namespace == "minworkbuddy_1_default"


def test_collection_and_label_prefixes():
    s = TenantScope(tenant_id=1, ontology_code="default")
    assert s.collection("entity") == "minworkbuddy_1_default_entity"
    assert s.label("entity") == "minworkbuddy_sem_entity"


def test_assert_owned_allows_same_namespace():
    s = TenantScope(tenant_id=1)
    s.assert_owned(s.namespace)  # 不应抛异常


def test_assert_owned_rejects_foreign_namespace():
    s = TenantScope(tenant_id=1)
    with pytest.raises(PermissionError):
        s.assert_owned("minworkbuddy_2_default")
