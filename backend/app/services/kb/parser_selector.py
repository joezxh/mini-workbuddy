"""AgentScope Parser 能力发现与选择（spec §10.3，严格对齐 agentscope 2.0.8）。

Parser 能力以类属性 ``supported_media_types``（IANA 媒体类型）为唯一事实源，
本模块不做扩展名→类型的猜测映射；未命中显式失败（不静默降级）。
"""
from __future__ import annotations

from typing import Dict, List, Type

from agentscope.rag import (
    ExcelParser,
    ImageParser,
    ParserBase,
    PDFParser,
    TextParser,
    WordParser,
)

# 顺序即优先级：TextParser 兜底放最后（覆盖 text/* 大类）
_PARSER_CLASSES: List[Type[ParserBase]] = [
    PDFParser,
    WordParser,
    ExcelParser,
    ImageParser,
    TextParser,
]


def supported_media_types() -> Dict[str, List[str]]:
    """能力发现表：{parser 类名: [支持的 IANA 媒体类型]}（供 /supported_content_types）。"""
    return {
        cls.__name__: list(cls.supported_media_types)
        for cls in _PARSER_CLASSES
    }


def select_parser(media_type: str) -> ParserBase:
    """按请求媒体类型选择解析器；未支持显式失败。"""
    normalized = (media_type or "").split(";")[0].strip().lower()
    for cls in _PARSER_CLASSES:
        if normalized in cls.supported_media_types:
            return cls()
    raise ValueError(f"不支持的文件类型: {media_type!r}（可用: {supported_media_types()}）")
