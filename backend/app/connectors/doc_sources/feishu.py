"""飞书知识库文档源（``source_type=feishu``）。

认证：``app_id`` / ``app_secret`` 换 ``tenant_access_token``。
枚举：Wiki 知识空间 → 节点树（分页 + 可下钻）。
正文：云文档 ``docx`` 块分页拉取 → Markdown。

域名取自 ``feishu_core.REGIONS`` 常量表（``https://open.feishu.cn``），不接受任意 base_url。
逻辑全部在 ``feishu_core.FeishuWikiSource``，本文件只声明区域并注册。
"""
from __future__ import annotations

from app.connectors.doc_sources.base import (
    CredField,
    ProviderMeta,
    register_doc_source,
)
from app.connectors.doc_sources.feishu_core import REGIONS, REGION_FEISHU, FeishuWikiSource

HOST = REGIONS[REGION_FEISHU]


class FeishuDocSource(FeishuWikiSource):
    """飞书（国内版）知识库。"""

    source_type = "feishu"
    region = REGION_FEISHU


register_doc_source(
    "feishu",
    FeishuDocSource,
    ProviderMeta(
        source_type="feishu",
        name="飞书",
        desc="云文档 / 知识库节点",
        host=HOST,
        credential_fields=(
            CredField("app_id", "App ID", required=True, placeholder="cli_a1b2c3d4"),
            CredField("app_secret", "App Secret", required=True, secret=True,
                      placeholder="应用凭证 Secret"),
            CredField("space_id", "知识空间 ID", placeholder="留空则列出全部可访问空间",
                      hint="填写后走「知识空间直连」：直接列出该空间下的文档，"
                           "不依赖「获取知识空间列表」权限（应用未加入空间时推荐）"),
        ),
    ),
)
