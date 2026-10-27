"""飞书云盘文档源（``source_type=feishu_drive``）。

与「飞书知识库」的区别：云盘**没有列出根空间的接口**，根目录必须由用户给出
``folder_token``（从云盘文件夹 URL ``/drive/folder/<token>`` 复制），留空直接报错。

权限：``drive:drive:readonly`` / ``docx:document:readonly`` / ``drive:export:readonly``
（**不需要** ``wiki:wiki:readonly``）；资源授权：必须把目标文件夹分享给应用（或应用
所在群），否则读取报 403。

支持导入：``docx``（块 → Markdown）、``sheet`` / ``bitable``（导出任务 → xlsx → Markdown）、
上传型文件（下载后按扩展名转换）；``slides`` / ``mindnote`` 等无公开内容 API 的类型跳过。
"""
from __future__ import annotations

from app.connectors.doc_sources.base import (
    CredField,
    ProviderMeta,
    register_doc_source,
)
from app.connectors.doc_sources.feishu_core import REGIONS, REGION_FEISHU, FeishuDriveSource

HOST = REGIONS[REGION_FEISHU]


class FeishuDriveDocSource(FeishuDriveSource):
    """飞书（国内版）云盘。"""

    source_type = "feishu_drive"
    region = REGION_FEISHU


register_doc_source(
    "feishu_drive",
    FeishuDriveDocSource,
    ProviderMeta(
        source_type="feishu_drive",
        name="飞书云盘",
        desc="云盘文件夹（docx / 表格 / 上传文件）",
        host=HOST,
        credential_fields=(
            CredField("app_id", "App ID", required=True, placeholder="cli_a1b2c3d4"),
            CredField("app_secret", "App Secret", required=True, secret=True,
                      placeholder="应用凭证 Secret"),
            CredField("folder_token", "云盘文件夹 token", required=True,
                      placeholder="fldxxxxxxxxxxxx",
                      hint="打开云盘目标文件夹，从 URL /drive/folder/<token> 复制该段；"
                           "不能留空使用云空间根目录，且需先把文件夹分享给应用"),
        ),
    ),
)
