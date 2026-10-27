"""字节流 → Markdown 薄适配（Office / PDF / 纯文本）。

``doc_sources`` 层只负责把外部内容规约成 Markdown，**不做解析 / 切片 / 索引**。
因此这里直接复用 Wiki 文章导入既有的 ``convert_document``（内部用 python-docx /
pdfplumber / openpyxl / python-pptx，含 20MB 上限与截断），避免新增第二套解析器。

采用惰性 import：``doc_sources`` 属于连接器层，不应在导入期就把 Wiki 服务层的
解析依赖拉起来（也规避潜在的循环导入）。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.connectors.doc_sources.base import DocSourceError

logger = logging.getLogger(__name__)

# 与 app.services.wiki.doc_converter.SUPPORTED_EXTS 保持一致（此处不 import，避免层间耦合）
SUPPORTED_EXTS = (".pdf", ".docx", ".txt", ".md", ".markdown", ".pptx", ".xlsx", ".xls")

# 仓库 / 云盘类连接器共用的「可转成 Markdown 正文」的文档扩展名白名单。
# 图片与音频不在其内：它们无法转成正文，导入后只会是一篇空文档。
DOC_TEXT_EXTS = (
    ".md", ".markdown", ".mdx", ".rst", ".adoc", ".txt",
    ".html", ".htm", ".mhtml", ".json", ".csv", ".yaml", ".yml",
)
DOC_BINARY_EXTS = (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".epub")
DOC_EXTS = DOC_TEXT_EXTS + DOC_BINARY_EXTS


def is_doc_file(path: str) -> bool:
    """按文件路径（可含目录）判定是否属于可导入的文档类型。"""
    return ext_of((path or "").rsplit("/", 1)[-1]) in DOC_EXTS


def is_supported(filename: str) -> bool:
    """文件名后缀是否在可转换范围内（未知后缀应由调用方跳过而非尝试转换）。"""
    return _ext_of(filename) in SUPPORTED_EXTS


def bytes_to_markdown(filename: str, data: bytes) -> str:
    """把下载到的字节流转成 Markdown。

    :raises DocSourceError: 格式不支持 / 内容为空 / 超限 / 解析失败（文案可直接回显前端）。
    """
    if not data:
        raise DocSourceError(f"文件 {filename} 内容为空")
    try:
        from app.services.wiki.doc_converter import convert_document
    except ImportError as exc:  # 解析依赖缺失时不静默吞掉
        raise DocSourceError(
            f"缺少二进制文档解析依赖，无法转换 {filename}"
        ) from exc
    try:
        result = convert_document(filename, data)
    except ValueError as exc:
        # convert_document 的 ValueError 文案已面向前端
        raise DocSourceError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - 解析库任意异常统一收敛为连接器错误
        logger.warning("二进制文档转换失败 file=%s: %s", filename, exc)
        raise DocSourceError(f"文件 {filename} 转换失败：{exc}") from exc
    markdown = (result.markdown or "").strip()
    if not markdown:
        raise DocSourceError(f"文件 {filename} 未解析出任何文本")
    return markdown


def bytes_to_text(data: bytes) -> str:
    """纯文本类文件直接解码（去 BOM、容错非法字节）。"""
    if not data:
        return ""
    try:
        return data.decode("utf-8-sig", errors="ignore")
    except Exception:  # noqa: BLE001 - 解码失败不应中断导入
        return data.decode("utf-8", errors="ignore")


def _ext_of(filename: str) -> str:
    name = (filename or "").strip().lower()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1]


def ext_of(filename: str) -> str:
    """对外暴露后缀提取（连接器做扩展名白名单判定时复用，避免各写一份）。"""
    return _ext_of(filename)


def guess_name(title: Optional[str], fallback: str) -> str:
    """生成用于转换的文件名：优先用标题补上后缀，缺失时回退原始文件名。"""
    title = (title or "").strip()
    if title and is_supported(title):
        return title
    ext = _ext_of(fallback)
    if title and ext:
        return f"{title}{ext}"
    return fallback
