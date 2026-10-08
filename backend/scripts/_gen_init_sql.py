"""生成 MinWorkBuddy 完整初始化 SQL：DDL（表 + 索引 + 扩展）+ 初始化数据。

- DDL 由 SQLAlchemy metadata 编译（PostgreSQL dialect），为单一事实来源。
- 初始化数据从 docs/sql 下的种子文件抽取（仅保留 INSERT/UPDATE/DELETE/DO/
  ALTER/CREATE INDEX/SELECT setval 等数据/补齐语句，剥离 DROP TABLE / CREATE TABLE
  以免覆盖由模型生成的权威 DDL）。
- 不连接数据库，纯文本生成，可直接 psql -f 执行。
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DOCS_SQL = BACKEND.parent / "docs" / "sql"
sys.path.insert(0, str(BACKEND))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateTable, CreateIndex, Table  # noqa: E402

import app.db.init_models  # noqa: F401,E402  注册全部模型
from app.db.database import Base  # noqa: E402

DIALECT = postgresql.dialect()

# 种子文件执行顺序（保证菜单/角色/字典先于关联与依赖它们的补齐语句）
SEED_FILES = [
    "init_tenants.sql",
    "sys_dictionary.sql",
    "menu_init.sql",
    "dict_missing_items.sql",
    "menu_workflow.sql",
    "menu_knowledge_governance.sql",
    "menu_duplex_voice.sql",
    "fix_menu_private_kb.sql",
    "45_voice_realtime_init.sql",
    "46_voice_model_cleanup_and_local_s2s_init.sql",
    "47_agent_event_enhance.sql",
]


def _compile(obj) -> str:
    return str(obj.compile(dialect=DIALECT)).rstrip().rstrip(";") + ";"


def generate_ddl() -> str:
    out = io.StringIO()
    tables: list[Table] = list(Base.metadata.sorted_tables)
    out.write("-- ── 前置扩展 ───────────────────────────────────────────────\n")
    out.write("CREATE EXTENSION IF NOT EXISTS vector;\n")
    out.write("CREATE EXTENSION IF NOT EXISTS pg_trgm;\n\n")

    out.write(f"-- ── 表定义（共 {len(tables)} 张）──────────────────────────────\n")
    for t in tables:
        out.write(f"\n-- {t.name}\n")
        out.write(_compile(CreateTable(t)) + "\n")
        tcomment = getattr(t, "comment", None)
        if tcomment:
            out.write(
                f"COMMENT ON TABLE {t.name} IS '{tcomment.replace(chr(39), chr(39)*2)}';\n"
            )
        for col in t.columns:
            c = col.comment
            if c:
                out.write(
                    f"COMMENT ON COLUMN {t.name}.{col.name} IS "
                    f"'{str(c).replace(chr(39), chr(39)*2)}';\n"
                )

    indexes = [idx for t in tables for idx in t.indexes]
    if indexes:
        out.write("\n-- ── 索引定义 ───────────────────────────────────────────\n")
        for idx in indexes:
            out.write(f"\n-- index {idx.name} on {idx.table.name}\n")
            out.write(_compile(CreateIndex(idx)) + "\n")

    # 性能索引：向量 HNSW + 中文 gin_trgm（startup_migrations 中运行时补齐项，
    # 这里一并写入初始化脚本，保证全新库即具备检索性能）。
    out.write("\n-- ── 性能索引（向量 / 全文检索）────────────────────────────\n")
    out.write(
        "CREATE INDEX IF NOT EXISTS idx_kms_segment_embedding_hnsw "
        "ON kms_segment USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);\n"
    )
    out.write(
        "CREATE INDEX IF NOT EXISTS idx_kms_segment_content_trgm "
        "ON kms_segment USING gin (content gin_trgm_ops);\n"
    )
    out.write(
        "CREATE INDEX IF NOT EXISTS idx_kms_article_vector_hnsw "
        "ON kms_article USING hnsw (content_vector vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);\n"
    )
    return out.getvalue()


def _split_statements(text: str) -> list[str]:
    """按顶层 ';' 切分（忽略字符串、$$ 块、注释、括号内部的分号）。"""
    stmts: list[str] = []
    buf = []
    in_str = False
    in_dollar = False
    dollar_tag = ""
    paren = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_str:
            buf.append(ch)
            if ch == "'":
                if nxt == "'":  # 转义引号
                    buf.append(nxt)
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if in_dollar:
            buf.append(ch)
            if ch == "$" and nxt.startswith(dollar_tag) and (
                len(nxt) == len(dollar_tag) or nxt[len(dollar_tag)] in " \t\n;"
            ):
                buf.append(dollar_tag)
                i += 1 + len(dollar_tag)
                in_dollar = False
                continue
            i += 1
            continue
        # 普通字符（非字符串 / $$ 内部）
        # 行注释 -- 跳到行尾
        if ch == "-" and nxt == "-":
            nl = text.find("\n", i)
            i = n if nl == -1 else nl + 1
            continue
        # 块注释 /* ... */ 跳过
        if ch == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if ch == "'":
            in_str = True
            buf.append(ch)
            i += 1
            continue
        if ch == "$" and (nxt.isalpha() or nxt == "_" or nxt == "$"):
            # 可能的 $$ 或 $tag$
            m = re.match(r"\$([A-Za-z_]\w*)?\$", text[i:])
            if m:
                dollar_tag = m.group(0)
                buf.append(dollar_tag)
                i += len(dollar_tag)
                in_dollar = True
                continue
        if ch == "(":
            paren += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            paren = max(0, paren - 1)
            buf.append(ch)
            i += 1
            continue
        if ch == ";" and paren == 0:
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def _strip_comments_leading(stmt: str) -> str:
    s = stmt
    while True:
        s = s.lstrip()
        if s.startswith("--"):
            nl = s.find("\n")
            s = s[nl + 1:] if nl != -1 else ""
            continue
        if s.startswith("/*"):
            end = s.find("*/")
            s = s[end + 2:] if end != -1 else ""
            continue
        break
    return s


def _keep_statement(stmt: str) -> bool:
    s = _strip_comments_leading(stmt)
    low = s.lower()
    if low.startswith("drop table"):
        return False
    if low.startswith("create table"):
        return False
    if low.startswith("drop extension"):
        return False
    return True


def _add_on_conflict(stmt: str, pk: str) -> str:
    """为未自带幂等保护的 INSERT 追加 ON CONFLICT (pk) DO NOTHING。"""
    body = stmt.rstrip()
    if body.endswith(";"):
        body = body[:-1]
    if "ON CONFLICT" in body.upper():
        return body + ";"
    return body + f" ON CONFLICT ({pk}) DO NOTHING;"


# 非幂等 INSERT 的来源文件 → 表名(精确匹配) → 主键列
_ON_CONFLICT_RULES = {
    "sys_dictionary.sql": {
        '"public"."sys_dictionary"': "dict_id",
        '"public"."sys_dictionary_item"': "item_id",
    },
    "menu_init.sql": {
        '"public"."sys_role"': "role_id",
    },
}


def extract_seed(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    rules = _ON_CONFLICT_RULES.get(path.name, {})
    out = []
    for st in _split_statements(text):
        if not _keep_statement(st):
            continue
        for tbl, pk in rules.items():
            # 表名后接空白/左括号/结尾作为边界，避免 sys_dictionary 误匹配 sys_dictionary_item；
            # 同时兼容 INSERT 后换行再跟列列表的多行写法
            if re.search(rf'INSERT INTO {re.escape(tbl)}(\s|\(|$)', st):
                st = _add_on_conflict(st, pk)
                break
        out.append(st.rstrip().rstrip(";") + ";")
    return "\n\n".join(out)


def generate_seed() -> str:
    out = io.StringIO()
    out.write("\n-- ══════════════════════════════════════════════════════════════\n")
    out.write("-- 初始化数据（seed）\n")
    out.write("-- 来源：docs/sql 下的种子脚本，按依赖顺序拼接；全部幂等。\n")
    out.write("-- ══════════════════════════════════════════════════════════════\n")
    for fname in SEED_FILES:
        f = DOCS_SQL / fname
        if not f.exists():
            continue
        out.write(f"\n\n-- ───────────────────────────────────────────────────────\n")
        out.write(f"-- 来源：{fname}\n")
        out.write(f"-- ───────────────────────────────────────────────────────\n")
        out.write(extract_seed(f))
    return out.getvalue()


def generate_setval() -> str:
    """补齐自增序列当前值，避免显式 ID 插入后后续自增插入主键冲突。"""
    pairs = [
        ("sys_tenant", "tenant_id"),
        ("sys_user", "user_id"),
        ("sys_role", "role_id"),
        ("sys_user_role", "id"),
        ("sys_menu", "id"),
        ("sys_role_menu", "id"),
        ("sys_dictionary", "dict_id"),
        ("sys_dictionary_item", "item_id"),
        ("ai_api_key", "id"),
        ("ai_chat_model", "id"),
    ]
    out = io.StringIO()
    out.write("\n\n-- ── 重置自增序列（避免显式 ID 插入后与自增默认值冲突）────\n")
    for tbl, col in pairs:
        out.write(
            f"SELECT setval(pg_get_serial_sequence('{tbl}', '{col}'), "
            f"COALESCE((SELECT MAX({col}) FROM {tbl}), 1), true);\n"
        )
    return out.getvalue()


def build() -> str:
    header = (
        "-- ============================================================================\n"
        "-- MinWorkBuddy · 完整初始化 SQL（PostgreSQL 17+，需 pgvector / pg_trgm 扩展）\n"
        "-- ----------------------------------------------------------------------------\n"
        "-- 内容：\n"
        "--   1) 前置扩展（vector / pg_trgm）\n"
        "--   2) 全部表 DDL（由 SQLAlchemy 模型编译，表名/列/约束/注释为单一事实来源）\n"
        "--   3) 索引（含模型内联索引 + 向量 HNSW / 全文 gin_trgm 性能索引）\n"
        "--   4) 初始化数据（租户/用户/角色/字典/菜单/语音模型等，全部幂等）\n"
        "--   5) 自增序列重置\n"
        "--\n"
        "-- 用法：psql -h <host> -U <user> -d <db> -f docs/sql/init.sql\n"
        "-- 说明：本文件可由 backend/scripts/_gen_init_sql.py 重新生成。\n"
        "-- ============================================================================\n\n"
    )
    return header + generate_ddl() + generate_seed() + generate_setval() + "\n"


if __name__ == "__main__":
    result = build()
    out_path = DOCS_SQL / "init.sql"
    out_path.write_text(result, encoding="utf-8")
    # 统计
    n_create = result.count("CREATE TABLE")
    n_insert = len(re.findall(r"\bINSERT\s+INTO\b", result, re.I))
    print(f"written: {out_path}")
    print(f"CREATE TABLE 语句数: {n_create}")
    print(f"INSERT INTO 语句数: {n_insert}")
    print(f"总行数: {result.count(chr(10)) + 1}")
