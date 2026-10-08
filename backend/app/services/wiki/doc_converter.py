"""Wiki 文章导入：文档 → Markdown 转换 + 字段提取。

支持格式: ``.pdf .docx .txt .md .markdown .pptx .xlsx .xls``

解析复用 ``requirements.txt`` 中已有依赖（``python-docx`` / ``pdfplumber`` /
``openpyxl`` / ``python-pptx``），**不引入新依赖**。

产出两部分：
1. ``markdown`` —— 回填到文章正文（``kms_article.content``）；
2. 提取字段 —— ``title`` / ``summary`` / ``tags``（基础）与 ``okf_type``
   （OKF 合规层），以及溯源用的 ``source_meta.author`` / ``last_modified``。
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── 资源上限（防超大文件拖垮内存）───────────────────────────────────────
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 200
MAX_SHEET_ROWS = 2000
MAX_SHEET_COLS = 50
MAX_MARKDOWN_CHARS = 200_000
SUMMARY_MAX_CHARS = 1000          # kms_article.summary 列上限
TITLE_MAX_CHARS = 500             # kms_article.title 列上限
MAX_TAGS = 8

SUPPORTED_EXTS = (".pdf", ".docx", ".txt", ".md", ".markdown", ".pptx", ".xlsx", ".xls")

# okf_type 推断规则（顺序敏感：先命中先返回），缺省 concept
OKF_TYPE_RULES = (
    ("howto", ("手册", "指南", "教程", "操作", "步骤", "使用说明", "how to", "guide", "tutorial", "step")),
    ("reference", ("规范", "接口", "参考", "规格", "协议", "reference", "spec", "api")),
    ("decision", ("决策", "决议", "纪要", "评审", "decision", "adr")),
    ("metric", ("指标", "报表", "统计", "度量", "metric", "report", "statistics")),
)

_CN_WORD = re.compile(r"[\u4e00-\u9fa5]{2,6}")
_EN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_STOP_WORDS = {
    "the", "and", "for", "with", "this", "that", "from", "are", "was", "文档",
    "内容", "说明", "相关", "以下", "可以", "我们", "公司",
}


@dataclass
class SourceMeta:
    """文档溯源元信息（写入 ``kms_article.sources``）。"""

    author: Optional[str] = None
    last_modified: Optional[str] = None


@dataclass
class ConvertResult:
    """转换结果：正文 Markdown + 提取到的字段。"""

    markdown: str
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: list = field(default_factory=list)
    okf_type: Optional[str] = None
    source_meta: SourceMeta = field(default_factory=SourceMeta)


# ── 对外入口 ────────────────────────────────────────────────────────────

def convert_document(filename: str, data: bytes) -> ConvertResult:
    """把上传文档转换为 Markdown 并提取字段。

    :raises ValueError: 格式不支持 / 文件过大 / 解析失败（文案可直接返回给前端）。
    """
    ext = _ext_of(filename)
    if ext not in SUPPORTED_EXTS:
        raise ValueError(f"不支持的文件格式 '{ext or filename}'，仅支持 PDF / Word / TXT / Markdown / PPT / Excel")
    if not data:
        raise ValueError("文件内容为空")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 上限，请压缩后再上传")

    try:
        if ext in (".md", ".markdown", ".txt"):
            markdown, meta_title, meta = _from_text(data)
        elif ext == ".docx":
            markdown, meta_title, meta = _from_docx(data)
        elif ext == ".pdf":
            markdown, meta_title, meta = _from_pdf(data)
        elif ext == ".pptx":
            markdown, meta_title, meta = _from_pptx(data)
        else:  # .xlsx / .xls
            markdown, meta_title, meta = _from_xlsx(data, ext)
    except ValueError:
        raise
    except Exception as exc:  # 解析库抛出的任意异常统一包装
        logger.warning("文档解析失败 file=%s ext=%s: %s", filename, ext, exc)
        raise ValueError(f"文档解析失败：{exc}") from exc

    markdown = markdown.strip()
    if not markdown:
        raise ValueError("未能从文档中解析出任何文本内容")
    if len(markdown) > MAX_MARKDOWN_CHARS:
        markdown = markdown[:MAX_MARKDOWN_CHARS] + "\n\n> …（内容过长已截断）"

    return ConvertResult(
        markdown=markdown,
        title=_extract_title(markdown, meta_title, filename),
        summary=_extract_summary(markdown),
        tags=_extract_tags(markdown, meta.keywords, meta_title),
        okf_type=_infer_okf_type(markdown),
        source_meta=SourceMeta(author=meta.author, last_modified=meta.last_modified),
    )


# ── 各格式解析器 ────────────────────────────────────────────────────────

@dataclass
class _DocMeta:
    """解析器回填的文档属性。"""

    title: Optional[str] = None
    author: Optional[str] = None
    last_modified: Optional[str] = None
    keywords: Optional[str] = None


def _from_text(data: bytes):
    raw = _decode(data)
    return raw.replace("\r\n", "\n").replace("\r", "\n"), None, _DocMeta()


def _from_docx(data: bytes):
    import docx  # python-docx

    doc = docx.Document(io.BytesIO(data))
    lines: list[str] = []
    for para in doc.paragraphs:
        style_name = ""
        try:
            style_name = para.style.name or ""
        except Exception:
            style_name = ""
        text = (para.text or "").strip()
        if not text:
            continue
        heading = re.match(r"Heading\s*(\d)", style_name, re.I)
        if heading:
            level = min(max(int(heading.group(1)), 1), 6)
            lines.append("#" * level + " " + text)
        else:
            lines.append(text)

    for table in doc.tables:
        rows = [[(c.text or "").strip() for c in row.cells] for row in table.rows]
        md = _table_to_md(rows)
        if md:
            lines.append(md)

    props = doc.core_properties
    meta = _DocMeta(
        title=_clean(getattr(props, "title", None)),
        author=_clean(getattr(props, "author", None)),
        last_modified=_fmt_dt(getattr(props, "modified", None)),
        keywords=_clean(getattr(props, "keywords", None)),
    )
    return "\n\n".join(lines), meta.title, meta


def _from_pdf(data: bytes):
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for idx, page in enumerate(pdf.pages):
            if idx >= MAX_PDF_PAGES:
                pages.append(f"> …（超过 {MAX_PDF_PAGES} 页，其余已省略）")
                break
            pages.append((page.extract_text() or "").strip())

    meta = _DocMeta()
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            info = pdf.metadata or {}
            meta.title = _clean(info.get("Title"))
            meta.author = _clean(info.get("Author"))
            meta.keywords = _clean(info.get("Keywords"))
            meta.last_modified = _clean(info.get("ModDate") or info.get("CreationDate"))
    except Exception as exc:  # 元数据读取失败不影响正文
        logger.debug("PDF 元数据读取失败: %s", exc)

    return "\n\n---\n\n".join(p for p in pages if p), meta.title, meta


def _from_pptx(data: bytes):
    from pptx import Presentation

    prs = Presentation(io.BytesIO(data))
    blocks: list[str] = []
    for idx, slide in enumerate(prs.slides, start=1):
        lines = [f"## 第 {idx} 页"]
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            for para in shape.text_frame.paragraphs:
                text = "".join(run.text for run in para.runs).strip()
                if text:
                    lines.append(f"- {text}")
        try:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            notes = ""
        if notes:
            lines.append(f"> 备注：{notes}")
        blocks.append("\n".join(lines))

    # 核心属性无 title 时，退回首张幻灯片的标题占位符
    first_title = None
    for slide in prs.slides:
        title_shape = getattr(slide.shapes, "title", None)
        text = _clean(getattr(title_shape, "text", None))
        if text:
            first_title = text
            break

    props = prs.core_properties
    meta = _DocMeta(
        title=_clean(getattr(props, "title", None)) or first_title,
        author=_clean(getattr(props, "author", None)),
        last_modified=_fmt_dt(getattr(props, "modified", None)),
        keywords=_clean(getattr(props, "keywords", None)),
    )
    return "\n\n".join(blocks), meta.title, meta


def _from_xlsx(data: bytes, ext: str):
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        if ext == ".xls":
            raise ValueError("不支持旧版 .xls（二进制格式），请另存为 .xlsx 后重新上传") from exc
        raise ValueError(f"Excel 解析失败：{exc}") from exc

    blocks: list[str] = []
    try:
        for ws in wb.worksheets:
            rows: list[list[str]] = []
            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if row_idx >= MAX_SHEET_ROWS:
                    rows.append([f"…（超过 {MAX_SHEET_ROWS} 行，其余已省略）"])
                    break
                if row is None or all(v is None for v in row):
                    continue
                rows.append(["" if v is None else str(v).strip() for v in row[:MAX_SHEET_COLS]])
            md = _table_to_md(rows)
            if md:
                blocks.append(f"## {ws.title}\n\n{md}")
    finally:
        wb.close()

    props = wb.properties
    meta = _DocMeta(
        title=_clean(getattr(props, "title", None)),
        author=_clean(getattr(props, "creator", None)),
        last_modified=_fmt_dt(getattr(props, "modified", None)),
        keywords=_clean(getattr(props, "keywords", None)),
    )
    return "\n\n".join(blocks), meta.title, meta


# ── 字段提取 ────────────────────────────────────────────────────────────

def _extract_title(markdown: str, doc_title: Optional[str], filename: Optional[str]) -> Optional[str]:
    """优先级：文档核心属性 title → 正文首个 H1 → 首个非空行 → 文件名。"""
    if doc_title and doc_title.strip():
        return doc_title.strip()[:TITLE_MAX_CHARS]
    # 首个任意级别的标题（# ~ ######），去掉 # 号
    for line in markdown.splitlines():
        matched = re.match(r"^#{1,6}\s+(.*)$", line.strip())
        if matched:
            return matched.group(1).strip()[:TITLE_MAX_CHARS]
    # 首个普通行：跳过表格 / 分隔线 / 引用，并去掉列表符号
    for line in markdown.splitlines():
        line = line.strip()
        if not line or line.startswith(("|", "---", ">")):
            continue
        line = re.sub(r"^[-*+]\s+", "", line).strip()
        if line:
            return line[:TITLE_MAX_CHARS]
    if filename:
        return re.sub(r"\.[^.]+$", "", filename)[:TITLE_MAX_CHARS]
    return None


def _extract_summary(markdown: str) -> Optional[str]:
    """首个非标题 / 非表格 / 非引用 / 非分隔线的段落，截断到列上限。"""
    for line in markdown.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("#", "|", ">", "---", "- [", "* [")):
            continue
        return line[:SUMMARY_MAX_CHARS]
    return None


def _extract_tags(markdown: str, keywords: Optional[str], doc_title: Optional[str]) -> list:
    """优先级：文档 keywords 属性 → 正文高频词。"""
    tags: list[str] = []
    if keywords:
        tags = [k.strip() for k in re.split(r"[,;，、\s]+", keywords) if k.strip()]
    if not tags:
        # 无 keywords 属性时，从「标题 + 各级标题」取样（比全文高频词更有语义）
        headings = [ln.strip().lstrip("#").strip() for ln in markdown.splitlines() if ln.strip().startswith("#")]
        sample = "\n".join([doc_title or ""] + headings)
        freq: dict = {}
        for token in _EN_WORD.findall(sample):
            low = token.lower()
            if low in _STOP_WORDS:
                continue
            freq[token] = freq.get(token, 0) + 1
        for token in _CN_WORD.findall(sample):
            if token in _STOP_WORDS:
                continue
            freq[token] = freq.get(token, 0) + 1
        tags = [w for w, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_TAGS]]

    seen: set = set()
    out: list[str] = []
    for tag in tags:
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out[:MAX_TAGS]


def _infer_okf_type(text: str) -> str:
    """按关键词规则推断 OKF type，缺省 concept。"""
    lowered = (text or "").lower()
    for okf_type, words in OKF_TYPE_RULES:
        for word in words:
            if word in lowered:
                return okf_type
    return "concept"


# ── 通用工具 ────────────────────────────────────────────────────────────

def _ext_of(filename: str) -> str:
    if not filename:
        return ""
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _fmt_dt(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return _clean(value)


def _table_to_md(rows: list) -> str:
    """二维表 → Markdown 表格（首行为表头）。"""
    rows = [r for r in rows if r and any(str(c).strip() for c in r)]
    if not rows:
        return ""
    col_count = max(len(r) for r in rows)
    header = [str(rows[0][i]).strip() if i < len(rows[0]) else "" for i in range(col_count)]
    body = rows[1:]

    def fmt_row(cells: list) -> str:
        return "| " + " | ".join(
            str(cells[i]).replace("|", "\\|") if i < len(cells) else "" for i in range(col_count)
        ) + " |"

    widths = [
        max([len(header[i])] + [len(str(r[i])) for r in body if i < len(r)] or [3])
        for i in range(col_count)
    ]
    lines = [fmt_row(header), "| " + " | ".join("-" * max(3, w) for w in widths) + " |"]
    lines += [fmt_row(r) for r in body]
    return "\n".join(lines)
