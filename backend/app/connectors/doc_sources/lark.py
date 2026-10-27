"""Lark 知识库文档源（``source_type=lark``）。

与飞书**共用同一套 API 与实现**，但两朵云彼此隔离：``open.feishu.cn`` 创建的应用
读不到 Lark 租户的 Wiki，凭据不通用，因此是独立的 source_type（域名
``https://open.larksuite.com``，权限标识符与飞书完全相同）。

控制台：https://open.larksuite.com/app ；权限：``wiki:wiki:readonly`` /
``docx:document:readonly`` / ``drive:drive:readonly`` / ``drive:export:readonly``，
且需把应用加入目标知识空间成员。
"""
from __future__ import annotations

from app.connectors.doc_sources.base import (
    CredField,
    ProviderMeta,
    register_doc_source,
)
from app.connectors.doc_sources.feishu_core import REGIONS, REGION_LARK, FeishuWikiSource

HOST = REGIONS[REGION_LARK]


class LarkDocSource(FeishuWikiSource):
    """Lark（国际版）知识库。"""

    source_type = "lark"
    region = REGION_LARK


register_doc_source(
    "lark",
    LarkDocSource,
    ProviderMeta(
        source_type="lark",
        name="Lark 知识库",
        desc="Lark 云文档 / 知识库节点（国际版）",
        host=HOST,
        credential_fields=(
            CredField("app_id", "App ID", required=True, placeholder="cli_a1b2c3d4"),
            CredField("app_secret", "App Secret", required=True, secret=True,
                      placeholder="Lark 应用凭证 Secret"),
            CredField("space_id", "知识空间 ID", placeholder="留空则列出全部可访问空间",
                      hint="飞书与 Lark 凭据不通用；填写后走「知识空间直连」模式"),
        ),
    ),
)
