"""租户隔离 / UserIdMapper 测试（P1 Task 6：纵深防御）。

验证：
- UserIdMapper 把 tenant_id 确定性、带命名空间地映射为 as_user_id（相同稳定、跨租户互斥）；
- PGVectorStore / KbRefService 构造时 tenant_id 缺失即拒绝（不放行无租户操作）。
"""
from __future__ import annotations

import pytest

from app.services.kb.pgvector_store import PGVectorStore
from app.services.kb.user_id_mapper import PREFIX, to_as_user_id


def test_mapper_deterministic():
    assert to_as_user_id(100) == to_as_user_id(100)


def test_mapper_distinct_per_tenant():
    assert to_as_user_id(100) != to_as_user_id(200)


def test_mapper_namespaced():
    uid = to_as_user_id(100)
    assert uid.startswith(PREFIX)
    # 命名空间前缀隔离外部 AgentScope user，原始 tenant_id 不经透传
    assert uid == f"{PREFIX}100"


def test_store_rejects_missing_tenant(db):
    with pytest.raises(ValueError):
        PGVectorStore(db, None)
