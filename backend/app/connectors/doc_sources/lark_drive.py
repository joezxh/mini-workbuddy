"""Lark 云盘文档源（``source_type=lark_drive``）。

与飞书云盘共用实现，域名 ``https://open.larksuite.com``。飞书与 Lark 凭据不通用，
且目标文件夹必须分享给 Lark 应用（或应用所在群）才能读取。
根目录 ``folder_token`` 必填（云盘无「列出根空间」接口）。
"""
from __future__ import annotations

from app.connectors.doc_sources.base import (
    CredField,
    ProviderMeta,
    register_doc_source,
)
from app.connectors.doc_sources.feishu_core import REGIONS, REGION_LARK, FeishuDriveSource

HOST = REGIONS[REGION_LARK]


class LarkDriveDocSource(FeishuDriveSource):
    """Lark（国际版）云盘。"""

    source_type = "lark_drive"
    region = REGION_LARK


register_doc_source(
    "lark_drive",
    LarkDriveDocSource,
    ProviderMeta(
        source_type="lark_drive",
        name="Lark 云盘",
        desc="Lark 云盘文件夹（国际版）",
        host=HOST,
        credential_fields=(
            CredField("app_id", "App ID", required=True, placeholder="cli_a1b2c3d4"),
            CredField("app_secret", "App Secret", required=True, secret=True,
                      placeholder="Lark 应用凭证 Secret"),
            CredField("folder_token", "云盘文件夹 token", required=True,
                      placeholder="fldxxxxxxxxxxxx",
                      hint="Lark 云盘文件夹 URL /drive/folder/<token> 中的 token 段；"
                           "需先把文件夹分享给应用"),
        ),
    ),
)
