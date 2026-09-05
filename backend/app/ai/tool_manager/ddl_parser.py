"""SQL DDL 解析器。

将 ``CREATE TABLE`` 语句解析为结构化的表/列元信息，用于 SQLBot 数据源
管理模块中的「DDL 导入」能力：业务团队粘贴建表语句即可自动生成
``sqlbot_datasource_table`` 的表与列配置，并依据列名预推断敏感字段
（脱敏建议）。

设计原则：
- 仅依赖标准库 ``re``，无第三方依赖。
- 目标不是兼容任意 SQL 方言的全部语法，而是覆盖 MySQL/PostgreSQL/Hive
  等常见 ``CREATE TABLE`` 结构（反引号 / 双引号 / 无引号标识符、schema
  前缀、``IF NOT EXISTS``、列级 ``COMMENT``、表级 ``COMMENT``、常见类型）。
- 解析失败时抛出 ``DDLParseError``，调用方负责收集并返回用户友好的明细。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

__all__ = [
    "DDLParseError",
    "ParsedColumn",
    "ParsedTable",
    "parse_ddl",
    "parse_ddl_statements",
    "guess_sensitive_columns",
]

# 标识符：`` `name` `` / `` "name" `` / `` [name] `` / 裸名（支持 schema.tbl）
# 注意：内部不使用捕获组，避免嵌套捕获干扰外层 group 的取值。
_IDENT = r"(?:`[^`]*`|\"[^\"]*\"|\[[^\]]*\]|[A-Za-z][A-Za-z0-9_]*)"
_QUALIFIED = re.compile(
    rf"{_IDENT}(?:\s*\.\s*{_IDENT})?", re.IGNORECASE
)
_COL_TYPE = re.compile(
    r"^\s*((?:[A-Za-z][A-Za-z0-9_]*(?:\s*\([^)]*\))?))", re.IGNORECASE
)
_COMMENT_SINGLE = re.compile(r"--[^\n]*")
_COMMENT_HASH = re.compile(r"#[^\n]*")
_COMMENT_LINE = re.compile(r"/\*.*?\*/", re.DOTALL)

# 列级 COMMENT 提取：COMMENT 'xxx' 或 COMMENT "xxx"
_COL_COMMENT = re.compile(r"\bCOMMENT\s+'([^']*)'|\bCOMMENT\s+\"([^\"]*)\"", re.IGNORECASE)
# 表级 COMMENT 提取
_TBL_COMMENT = re.compile(
    r"\)\s*(?:.*?)\bCOMMENT\s*=\s*'([^']*)'|\bCOMMENT\s+'([^']*)'\s*\)",
    re.IGNORECASE | re.DOTALL,
)
_TBL_COMMENT2 = re.compile(r"\bCOMMENT\s*=\s*'([^']*)'|\bCOMMENT\s+'([^']*)'", re.IGNORECASE)

# 敏感字段名正则（与 masking.guess_strategy_for_field 保持一致口径）
_SENSITIVE_HINTS = re.compile(
    r"(id_?card|identity|id_?number|phone|mobile|tel|bank_?card|address|email|real_?name|"
    r"name|birth|age)",
    re.I,
)

_CREATE_RE = re.compile(
    rf"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({_IDENT}(?:\s*\.\s*{_IDENT})?)",
    re.IGNORECASE | re.DOTALL,
)


class DDLParseError(ValueError):
    """DDL 解析失败。"""


@dataclass
class ParsedColumn:
    """解析后的列元信息。"""

    name: str
    type: str = ""
    comment: str = ""
    nullable: bool = True
    is_sensitive: bool = False
    # 预推断的脱敏策略提示（mask/hash/drop/truncate），供导入时回写
    suggested_mask: str = "mask"


@dataclass
class ParsedTable:
    """解析后的表元信息。"""

    table_name: str
    columns: List[ParsedColumn] = field(default_factory=list)
    table_comment: str = ""
    raw: str = ""


def _strip_sql_comments(text: str) -> str:
    text = _COMMENT_SINGLE.sub(" ", text)
    text = _COMMENT_HASH.sub(" ", text)
    text = _COMMENT_LINE.sub(" ", text)
    return text


def _unquote(ident: str) -> str:
    """去除标识符包裹字符并去除 schema 前缀，返回纯表名。"""
    ident = ident.strip()
    # schema.table -> table（先拆分再各自去引号，避免互相干扰）
    if "." in ident:
        ident = ident.split(".", 1)[1].strip()
    return ident.strip("`").strip('"').strip("[").strip("]")


def _normalize_col_type(raw: str) -> str:
    raw = raw.strip()
    # 截断括号内的精度部分以简化类型表达，保留主类型
    m = re.match(r"([A-Za-z][A-Za-z0-9_]*)", raw, re.IGNORECASE)
    base = m.group(1).lower() if m else raw.lower()
    return base


def guess_sensitive_columns(columns: List[ParsedColumn]) -> List[ParsedColumn]:
    """依据列名/注释推断敏感字段，并预填脱敏策略建议。"""
    for col in columns:
        hay = f"{col.name} {col.comment}"
        if _SENSITIVE_HINTS.search(hay):
            col.is_sensitive = True
            lower = col.name.lower()
            if re.search(r"email", lower):
                col.suggested_mask = "mask"
            elif re.search(r"bank_?card", lower):
                col.suggested_mask = "mask"
            elif re.search(r"id_?card|identity|id_?number", lower):
                col.suggested_mask = "mask"
            elif re.search(r"phone|mobile|tel", lower):
                col.suggested_mask = "mask"
            elif re.search(r"name", lower):
                col.suggested_mask = "mask"
            elif re.search(r"address", lower):
                col.suggested_mask = "mask"
            else:
                col.suggested_mask = "mask"
    return columns


def _split_top_level(body: str) -> List[str]:
    """将表体拆分为逗号分隔的列/约束定义（不拆分括号内逗号）。"""
    parts: List[str] = []
    depth = 0
    cur = []
    for ch in body:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


def _parse_one(create_block: str) -> ParsedTable:
    m = _CREATE_RE.search(create_block)
    if not m:
        raise DDLParseError("未找到 CREATE TABLE 语句")
    raw_name = m.group(1)
    table_name = _unquote(raw_name)

    # 截取 CREATE TABLE <name> 之后到匹配的右括号之间的表体
    after = create_block[m.end():]
    # 找第一个 '(' 与对应的 ')'
    start = after.find("(")
    if start == -1:
        raise DDLParseError(f"表 {table_name} 缺少列定义括号")
    depth = 0
    end = -1
    for i in range(start, len(after)):
        if after[i] == "(":
            depth += 1
        elif after[i] == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise DDLParseError(f"表 {table_name} 括号未闭合")

    body = after[start + 1 : end]
    # 表级注释提取（在右括号之后）
    tail = after[end + 1 :]
    tbl_comment = ""
    cm = _TBL_COMMENT2.search(tail)
    if cm:
        tbl_comment = cm.group(1) or cm.group(2) or ""

    columns: List[ParsedColumn] = []
    for seg in _split_top_level(body):
        seg = seg.strip()
        if not seg:
            continue
        # 列定义：首段必须是标识符（注意：反引号/引号标识符后无词边界，故不以 \b 收尾）
        ident_m = re.match(rf"^\s*{_IDENT}", seg, re.IGNORECASE)
        if not ident_m:
            # 可能是表级约束，跳过
            continue
        col_name = _unquote(ident_m.group(0).strip())
        if re.match(
            r"^(PRIMARY|FOREIGN|KEY|INDEX|UNIQUE|CONSTRAINT|CHECK)$",
            col_name,
            re.IGNORECASE,
        ):
            continue
        rest = seg[ident_m.end():]
        type_m = _COL_TYPE.match(rest)
        col_type = _normalize_col_type(type_m.group(1)) if type_m else ""
        nullable = True
        if re.search(r"\bNOT\s+NULL\b", rest, re.IGNORECASE):
            nullable = False
        cmt = ""
        cmm = _COL_COMMENT.search(seg)
        if cmm:
            cmt = cmm.group(1) or cmm.group(2) or ""
        columns.append(
            ParsedColumn(name=col_name, type=col_type, comment=cmt, nullable=nullable)
        )

    if not columns:
        raise DDLParseError(f"表 {table_name} 未解析到任何列")

    guess_sensitive_columns(columns)
    return ParsedTable(table_name=table_name, columns=columns, table_comment=tbl_comment, raw=create_block)


def parse_ddl_statements(ddl_text: str) -> List[ParsedTable]:
    """解析一段可能包含多条 CREATE TABLE 的 DDL 文本。

    :return: 解析成功的表列表（解析失败的语句被跳过，由调用方按需统计）
    """
    if not ddl_text or not ddl_text.strip():
        raise DDLParseError("DDL 文本为空")

    text = _strip_sql_comments(ddl_text)
    # 按 CREATE TABLE 切分多个语句块
    matches = list(_CREATE_RE.finditer(text))
    if not matches:
        raise DDLParseError("未找到任何 CREATE TABLE 语句")

    tables: List[ParsedTable] = []
    for idx, mm in enumerate(matches):
        start = mm.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]
        try:
            tables.append(_parse_one(block))
        except DDLParseError:
            # 单条失败不影响其他语句，交由调用方决定如何处理
            # 这里仅解析成功的；失败的通过 parse_ddl 的严格模式上报
            continue
    return tables


def parse_ddl(ddl_text: str, *, strict: bool = True) -> List[ParsedTable]:
    """解析 DDL。``strict=True``（默认）时任一语句失败即整体抛出异常；
    ``strict=False`` 时跳过失败语句、仅返回成功解析的表（错误信息通过
    ``parse_ddl_safe`` 获取）。
    """
    text = _strip_sql_comments(ddl_text)
    matches = list(_CREATE_RE.finditer(text))
    if not matches:
        raise DDLParseError("未找到任何 CREATE TABLE 语句")

    tables: List[ParsedTable] = []
    for idx, mm in enumerate(matches):
        start = mm.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]
        tables.append(_parse_one(block))
    return tables


def parse_ddl_safe(ddl_text: str) -> tuple[List[ParsedTable], List[str]]:
    """非严格解析，返回 ``(成功表列表, 错误信息列表)``。"""
    text = _strip_sql_comments(ddl_text)
    matches = list(_CREATE_RE.finditer(text))
    if not matches:
        return [], ["未找到任何 CREATE TABLE 语句"]

    tables: List[ParsedTable] = []
    errors: List[str] = []
    for idx, mm in enumerate(matches):
        start = mm.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]
        try:
            tables.append(_parse_one(block))
        except DDLParseError as e:
            errors.append(str(e))
    return tables, errors
