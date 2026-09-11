"""租户 → AgentScope RAG Service user_id 映射（P1 Task 6：租户隔离纵深防御）。

MWB 侧以 ``tenant_id`` 做行级隔离（PGVectorStore 所有读写强制带 tenant_id 过滤）。
对接外部 AgentScope RAG Service 时，绝不透传原始 ``tenant_id``，而是映射为带命名空间
前缀的 ``as_user_id``，使外部服务的隔离键与 MWB 内部租户体系解耦、互不越权。

纵深防御：
- MWB 内部：所有 kb 查询强制 ``tenant_id`` 过滤（PGVectorStore 构造时 tenant_id 必填）。
- 跨服务桥接：只传 ``as_user_id``，外部服务看不见原始 tenant_id，也无法构造他人 user_id。
"""
from __future__ import annotations

# 命名空间前缀：与 AgentScope 自有 user 隔离，避免 tenant_id 直接暴露于外部服务。
PREFIX = "mw_tenant_"


def to_as_user_id(tenant_id: int) -> str:
    """把 MWB ``tenant_id`` 确定性映射为 AgentScope 侧 user_id。

    映射是单向、确定、带命名空间前缀的；相同 tenant_id 永远得到相同 user_id，
    不同 tenant_id 必然不同，避免与外部其它 user 冲突。
    """
    return f"{PREFIX}{tenant_id}"
