"""HTML → Markdown 共用封装（从原 ``doc_sources/web.py`` 提取，供多平台复用）。

消费方：``web_crawler``（网页正文）、``rss``（文章页正文）、``imap``（HTML 邮件正文）、
``confluence``（``body.rendered`` 渲染结果）。

依赖 ``markdownify``（已在 requirements.txt）。库缺失时降级为「去标签 + 去脚本样式」
的纯文本，保证正文不丢而不是直接报错——转换是导入链路的最后一环，失败会让整篇
文档判为失败，降级更划算。
"""
from __future__ import annotations

import re
from typing import Optional

_SCRIPT_STYLE = re.compile(r"<(script|style)[\s\S]*?</\1>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>([\s\S]*?)</title>", re.IGNORECASE)
_WS = re.compile(r"[ \t　]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def _strip_tags(html: str) -> str:
    text = _SCRIPT_STYLE.sub(" ", html or "")
    text = _TAG.sub(" ", text)
    text = _WS.sub(" ", text)
    return text.strip()


def html_to_markdown(html: str) -> str:
    """把 HTML 转成 Markdown；``markdownify`` 不可用时降级为纯文本。"""
    if not html:
        return ""
    try:
        from markdownify import markdownify
    except ImportError:  # 依赖缺失：降级为去标签纯文本，保证正文不丢
        return _strip_tags(html) + "\n"
    try:
        md = markdownify(html, heading_style="ATX")
    except Exception:  # noqa: BLE001 - 单个畸形页面不应中断整次导入
        return _strip_tags(html) + "\n"
    md = (md or "").replace("\r\n", "\n")
    # markdownify 会留下连续空行，压缩掉以免切片时出现大段空白
    return _BLANK_LINES.sub("\n\n", md).strip() + "\n"


def html_to_text(html: str) -> str:
    """只取可见文本（邮件/页面摘要等不需要 Markdown 结构的场景）。"""
    if not html:
        return ""
    return _strip_tags(html)


def extract_title(html: str) -> Optional[str]:
    """从 ``<title>`` 抽取标题；缺失或空值返回 None，由调用方回退到 URL / 文件名。"""
    if not html:
        return None
    m = _TITLE.search(html)
    if not m:
        return None
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title[:200] or None
