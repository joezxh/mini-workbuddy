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

# 类名 → 类（pipeline_config.parser.type 的取值空间，spec §10.7）
PARSER_REGISTRY: Dict[str, Type[ParserBase]] = {
    cls.__name__: cls for cls in _PARSER_CLASSES
}


def supported_media_types() -> Dict[str, List[str]]:
    """能力发现表：{parser 类名: [支持的 IANA 媒体类型]}（供 /supported_content_types）。"""
    return {
        cls.__name__: list(cls.supported_media_types)
        for cls in _PARSER_CLASSES
    }


def parser_names() -> List[str]:
    """可选 parser 类名（前端向导 / Schema 发现）。"""
    return sorted(PARSER_REGISTRY)


# 扩展名 → IANA 媒体类型（仅用于上传入口按文件名推断；能力面仍以
# parser.supported_media_types 为唯一事实源）
_EXT_MEDIA = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp",
    "csv": "text/csv", "html": "text/html", "json": "application/json",
}


def guess_media_type(filename: str) -> str:
    """按扩展名推断媒体类型；未知按 md/markdown → text/markdown，其余 text/plain。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _EXT_MEDIA:
        return _EXT_MEDIA[ext]
    return "text/markdown" if ext in ("md", "markdown") else "text/plain"


def select_parser(media_type: str) -> ParserBase:
    """按请求媒体类型选择解析器；未支持显式失败。"""
    normalized = (media_type or "").split(";")[0].strip().lower()
    for cls in _PARSER_CLASSES:
        if normalized in cls.supported_media_types:
            return cls()
    raise ValueError(f"不支持的文件类型: {media_type!r}（可用: {supported_media_types()}）")


def select_parser_by_name(name: str) -> ParserBase:
    """按原生 Parser 类名选择解析器（pipeline_config.parser.type）；未知显式失败。"""
    cls = PARSER_REGISTRY.get(name or "")
    if cls is None:
        raise ValueError(f"未知 parser 类型: {name!r}；可选 {parser_names()}")
    return cls()
