"""共享的 Block → Markdown 转换器。

各平台（飞书 docx / Notion blocks / 企微 / 钉钉 / 语雀）的原生块结构各不相同，
这里定义一个**中间块结构** ``MdBlock``：平台侧只做「原生块 → MdBlock」的薄适配，
渲染统一由 ``blocks_to_markdown`` 完成，避免每个平台各写一份 Markdown 逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# 支持的块类型
HEADING = "heading"
PARAGRAPH = "paragraph"
BULLETED = "bulleted"
NUMBERED = "numbered"
TODO = "todo"
QUOTE = "quote"
CODE = "code"
DIVIDER = "divider"
IMAGE = "image"
TABLE = "table"
CALLOUT = "callout"


@dataclass
class MdBlock:
    """中间块结构。

    kind    块类型（见上方常量）
    text    文本内容（heading/paragraph/code/quote/callout/todo 的主文本）
    level   标题层级（1-6）
    language 代码块语言
    checked todo 是否勾选
    url     图片/链接地址
    rows    表格行（首行视为表头）
    children 子块（列表项嵌套）
    """

    kind: str
    text: str = ""
    level: int = 1
    language: str = ""
    checked: bool = False
    url: str = ""
    rows: Optional[List[List[str]]] = None
    children: List["MdBlock"] = field(default_factory=list)


def _clean(text: str) -> str:
    """去掉首尾空白并把连续空行压成单行，避免 Markdown 里出现大片空行。"""
    if not text:
        return ""
    lines = [line.rstrip() for line in str(text).replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def _cell(value: object) -> str:
    """表格单元格转义：竖线与换行会破坏 Markdown 表格结构。"""
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _render_table(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    header = [_cell(c) for c in rows[0]] + [""] * (width - len(rows[0]))
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in rows[1:]:
        cells = [_cell(c) for c in row] + [""] * (width - len(row))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _render_block(block: MdBlock, depth: int, order: int) -> List[str]:
    """渲染单个块，返回若干行 Markdown。"""
    kind = block.kind
    text = _clean(block.text)
    indent = "  " * depth

    if kind == HEADING:
        level = min(max(block.level, 1), 6)
        return [f"{'#' * level} {text}".rstrip()] if text else []

    if kind == PARAGRAPH:
        return [text] if text else []

    if kind == BULLETED:
        lines = [f"{indent}- {text}".rstrip()]
        lines += _render_children(block, depth + 1)
        return lines

    if kind == NUMBERED:
        lines = [f"{indent}{order}. {text}".rstrip()]
        lines += _render_children(block, depth + 1)
        return lines

    if kind == TODO:
        mark = "x" if block.checked else " "
        lines = [f"{indent}- [{mark}] {text}".rstrip()]
        lines += _render_children(block, depth + 1)
        return lines

    if kind == QUOTE:
        if not text:
            return []
        return [indent + "> " + line for line in text.split("\n")]

    if kind == CALLOUT:
        if not text:
            return []
        # callout 用引用块表达，保证在任意 Markdown 渲染器里都可读
        return [indent + "> " + line for line in text.split("\n")]

    if kind == CODE:
        lang = block.language or ""
        body = _clean(block.text)
        return [f"```{lang}", body, "```"] if body else []

    if kind == DIVIDER:
        return ["---"]

    if kind == IMAGE:
        alt = text or "image"
        return [f"![{alt}]({block.url})"] if block.url else []

    if kind == TABLE:
        rendered = _render_table(block.rows or [])
        return [rendered] if rendered else []

    # 未知块降级为段落，保证内容不丢失
    return [text] if text else []


def _render_children(block: MdBlock, depth: int) -> List[str]:
    if not block.children:
        return []
    out: List[str] = []
    order = 1
    for child in block.children:
        out += _render_block(child, depth, order)
        if child.kind == NUMBERED:
            order += 1
    return out


def blocks_to_markdown(blocks: List[MdBlock]) -> str:
    """把中间块列表渲染成 Markdown 全文。"""
    lines: List[str] = []
    order = 1
    for block in blocks or []:
        rendered = _render_block(block, 0, order)
        if rendered:
            lines += rendered
            lines.append("")  # 块之间空一行，保证 Markdown 段落分隔
        if block.kind == NUMBERED:
            order += 1
    return "\n".join(lines).strip() + ("\n" if lines else "")
