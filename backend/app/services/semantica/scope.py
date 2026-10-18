"""租户隔离。

一切 semantica 的命名空间 / 集合名 / 图 label 都须经此解析，禁止裸集合名直查，
对标旧 ``ontology`` 模块的 ``_require_tenant_id`` / ``_owned_ontology`` 隔离语义。
"""
from __future__ import annotations

from app.config import settings


class TenantScope:
    """解析租户 + 本体 code → 命名空间 / 集合名 / 图 label。

    ``group_id`` 默认取自 ``GRAPHITI_GROUP_ID``，与 Graphiti 记忆共用同一 Neo4j
    实例时，作为实例内隔离前缀（semantica 写 ``minworkbuddy_sem_*``，graphiti 用
    自己的 group id 命名空间）。
    """

    def __init__(
        self,
        tenant_id: int,
        ontology_code: str = "default",
        *,
        group_id: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.ontology_code = ontology_code
        self.group_id = group_id or settings.GRAPHITI_GROUP_ID

    @property
    def namespace(self) -> str:
        """全局唯一命名空间根，如 ``minworkbuddy_100_default``。"""
        return f"{self.group_id}_{self.tenant_id}_{self.ontology_code}"

    def collection(self, kind: str) -> str:
        """向量集合名（实体 / 关系 / 文档）。"""
        return f"{self.namespace}_{kind}"

    def label(self, kind: str) -> str:
        """Neo4j label 前缀，避免与 Graphiti 同实例污染。"""
        return f"{self.group_id}_sem_{kind}"

    def assert_owned(self, namespace: str) -> None:
        """越权即拒：读取侧二次校验命名空间归属。"""
        if namespace != self.namespace:
            raise PermissionError(
                f"namespace {namespace!r} 不属于当前租户范围 {self.namespace!r}"
            )
