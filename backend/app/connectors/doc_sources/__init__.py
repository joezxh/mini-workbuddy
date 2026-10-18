"""外部文档源（目录浏览 + 正文拉取 + Markdown 转换）。

与 ``app.connectors``（记录流型同步）并列，互不干扰：本包只服务于
「把外部平台的文档导入成知识库文档」这一条链路。

平台实现在本包内注册（见各 ``<platform>.py`` 末尾的 ``register_doc_source``），
新增平台只需实现三个方法并注册，不触碰导入服务。
"""
from app.connectors.doc_sources.base import (
    CredField,
    DocConnResult,
    DocSourceError,
    ExternalDocRef,
    FetchDocResult,
    ProviderMeta,
    BaseDocSource,
    get_doc_source,
    get_provider_meta,
    list_providers,
    register_doc_source,
    supported_source_types,
)
# 导入即注册各平台实现（顺序无关）
from app.connectors.doc_sources import (  # noqa: F401
    dingtalk,
    feishu,
    notion,
    web,
    wecom,
    yuque,
)
from app.connectors.doc_sources.markdown import (
    BULLETED,
    CALLOUT,
    CODE,
    DIVIDER,
    HEADING,
    IMAGE,
    NUMBERED,
    PARAGRAPH,
    QUOTE,
    TABLE,
    TODO,
    MdBlock,
    blocks_to_markdown,
)

__all__ = [
    "CredField",
    "DocConnResult",
    "DocSourceError",
    "ExternalDocRef",
    "FetchDocResult",
    "ProviderMeta",
    "BaseDocSource",
    "get_doc_source",
    "get_provider_meta",
    "list_providers",
    "register_doc_source",
    "supported_source_types",
    "MdBlock",
    "blocks_to_markdown",
    "HEADING",
    "PARAGRAPH",
    "BULLETED",
    "NUMBERED",
    "TODO",
    "QUOTE",
    "CODE",
    "DIVIDER",
    "IMAGE",
    "TABLE",
    "CALLOUT",
]
